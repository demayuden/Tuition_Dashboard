from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta
import io
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from fastapi.responses import StreamingResponse

from ..db import get_db
from .. import models, schemas, crud

router = APIRouter(prefix="/packages", tags=["Packages"])
extra_router = APIRouter(tags=["Packages"])


# =========================================================
# PAYMENT
# =========================================================
@extra_router.post("/students/packages/{package_id}/mark_paid")
def mark_paid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(404, "Package not found")
    pkg = crud.toggle_payment(db, pkg, True)
    return {"status": "ok", "payment_status": pkg.payment_status}


@extra_router.post("/students/packages/{package_id}/mark_unpaid")
def mark_unpaid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(404, "Package not found")
    pkg = crud.toggle_payment(db, pkg, False)
    return {"status": "ok", "payment_status": pkg.payment_status}


# =========================================================
# CREATE PACKAGE FROM FUTURE PREVIEW
# =========================================================
@extra_router.post(
    "/students/packages/{package_id}/create_from_preview",
    response_model=schemas.PackageOut
)
def create_package_from_preview(
    package_id: int,
    start_from: str = Query(...),
    mark_paid: bool = Query(False),
    db: Session = Depends(get_db),
):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(404, "Package not found")

    student = pkg.student
    if not student:
        raise HTTPException(404, "Student not found")

    try:
        start_dt = datetime.fromisoformat(start_from).date()
    except Exception:
        raise HTTPException(400, "start_from must be YYYY-MM-DD")

    if student.end_date and start_dt > student.end_date:
        raise HTTPException(
            400, "Start date is beyond student's end date"
        )

    # create new package
    new_pkg = models.Package(
        student_id=student.student_id,
        package_size=pkg.package_size,
        payment_status=bool(mark_paid),
    )
    db.add(new_pkg)
    db.flush()

    from ..services.scheduler import generate_lessons_for_package

    lessons = generate_lessons_for_package(
        db,
        student,
        new_pkg,          # ✅ IMPORTANT
        override_existing=False,
        start_from=start_dt,
    )

    if not lessons:
        db.delete(new_pkg)
        db.commit()
        raise HTTPException(400, "No lessons generated")

    for i, l in enumerate(lessons, start=1):
        if i > new_pkg.package_size:
            break
        db.add(models.Lesson(
            package_id=new_pkg.package_id,
            lesson_number=i,
            lesson_date=l.lesson_date,
            is_first=(i == 1),
            is_manual_override=False,
        ))

    first = (
        db.query(models.Lesson)
        .filter(models.Lesson.package_id == new_pkg.package_id)
        .order_by(models.Lesson.lesson_number)
        .first()
    )
    if first:
        new_pkg.first_lesson_date = first.lesson_date

    db.commit()
    db.refresh(new_pkg)
    return new_pkg


# =========================================================
# REGENERATE (POST)
# =========================================================
@extra_router.post("/students/packages/{package_id}/regenerate")
def regenerate_package(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(404, "Package not found")
    crud.regenerate_package(db, pkg)
    return {"status": "ok", "package_id": package_id}


# =========================================================
# REGENERATE PREVIEW (GET)
# =========================================================
@extra_router.get("/students/packages/{package_id}/regenerate")
def regenerate_preview(
    package_id: int,
    extend: bool = Query(False),
    db: Session = Depends(get_db)
):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(404, "Package not found")

    from ..services.scheduler import generate_lessons_for_package
    student = pkg.student

    if not extend:
        proposed = generate_lessons_for_package(db, student, pkg)
        return {
            "preview": True,
            "package_id": pkg.package_id,
            "proposed_lessons": [
                {
                    "lesson_number": i + 1,
                    "lesson_date": l.lesson_date.isoformat(),
                    "is_manual_override": False,
                    "is_first": (i == 0),
                }
                for i, l in enumerate(proposed or [])
            ]
        }

    # EXTENDED PREVIEW
    flat: List[Dict] = []
    cursor = (
        max([l.lesson_date for l in pkg.lessons], default=student.start_date)
        + timedelta(days=1)
    )

    end_cutoff = student.end_date or cursor + timedelta(days=365 * 2)

    while cursor <= end_cutoff:
        block = generate_lessons_for_package(
            db, student, pkg, start_from=cursor
        )
        if not block:
            break
        for l in block:
            flat.append({
                "lesson_date": l.lesson_date.isoformat(),
                "is_manual_override": False,
                "is_first": False,
            })
        cursor = block[-1].lesson_date + timedelta(days=1)

    return {
        "preview": True,
        "package_id": pkg.package_id,
        "proposed_lessons": flat,
    }


# =========================================================
# EDIT LESSON
# =========================================================
class LessonEditPayload(BaseModel):
    lesson_date: Optional[date] = None
    is_manual_override: Optional[bool] = None


@extra_router.patch("/lessons/{lesson_id}", response_model=schemas.LessonOut)
def edit_lesson(
    lesson_id: int,
    payload: LessonEditPayload,
    db: Session = Depends(get_db)
):
    lesson = db.query(models.Lesson).filter_by(lesson_id=lesson_id).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    if payload.lesson_date is not None:
        lesson.lesson_date = payload.lesson_date
    if payload.is_manual_override is not None:
        lesson.is_manual_override = payload.is_manual_override

    db.commit()
    db.refresh(lesson)
    return lesson


# =========================================================
# EXPORT DASHBOARD (UNCHANGED CORE LOGIC)
# =========================================================
@extra_router.get("/export/dashboard.xlsx")
def export_dashboard_xlsx(
    tab: str = Query("all"),
    group: str = Query(""),
    day: str = Query(""),
    db: Session = Depends(get_db)
):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dashboard"

    ws.append(["Name", "CEFR", "Group", "Day", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"])

    students = db.query(models.Student).order_by(models.Student.name).all()

    for s in students:
        if group and s.group_name != group:
            continue

        pkgs = s.packages or []
        if not pkgs:
            continue

        pkg = pkgs[0]
        lesson_map = {l.lesson_number: l.lesson_date.isoformat() for l in pkg.lessons}

        row = [
            s.name,
            s.cefr or "",
            s.group_name or "",
            s.lesson_day_1,
        ]
        for i in range(1, 9):
            row.append(lesson_map.get(i, ""))

        ws.append(row)

        if not pkg.payment_status and lesson_map.get(1):
            ws.cell(row=ws.max_row, column=5).font = Font(color="FF0000", bold=True)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dashboard.xlsx"},
    )
