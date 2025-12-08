from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .. import schemas, models, crud
from ..db import get_db
from datetime import date
from fastapi import Query
from typing import Optional, List, Dict

router = APIRouter(prefix="/packages", tags=["Packages"])
extra_router = APIRouter(tags=["Packages"])

@extra_router.post("/students/packages/{package_id}/mark_paid")
def mark_paid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    updated = crud.toggle_payment(db, pkg, True)
    return {"status": "ok", "payment_status": updated.payment_status}


@extra_router.post("/students/packages/{package_id}/mark_unpaid")
def mark_unpaid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    updated = crud.toggle_payment(db, pkg, False)
    return {"status": "ok", "payment_status": updated.payment_status}


@extra_router.post("/students/packages/{package_id}/regenerate")
def regenerate_lessons(package_id: int, preview: bool = Query(False), db: Session = Depends(get_db)):
    """
    Regenerate lesson dates for a package.

    Query param:
      preview=true  -> returns proposed lesson dates (no DB changes)
      preview=false -> performs regeneration and persists changes (existing behavior)

    Response shape for preview:
    {
      "preview": true,
      "package_id": 123,
      "proposed_lessons": [
        {"lesson_number":1, "lesson_date":"2026-01-12", "is_manual_override":false, "is_first": true},
        ...
      ]
    }
    """
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    # If user asked for a preview, call the scheduler directly and return the results (no DB writes)
    if preview:
        # ensure we can import the scheduler generator
        try:
            from ..services.scheduler import generate_lessons_for_package
        except Exception:
            raise HTTPException(status_code=500, detail="Scheduler not available")

        student = pkg.student
        # Call scheduler - it uses db for closures but does not commit anything here.
        proposed = generate_lessons_for_package(db, student, pkg, override_existing=False)

        # Normalize to safe JSON-friendly structure
        out: List[Dict] = []
        for l in proposed:
            out.append({
                "lesson_number": getattr(l, "lesson_number", None),
                "lesson_date": getattr(l, "lesson_date").isoformat() if getattr(l, "lesson_date", None) else None,
                "is_manual_override": bool(getattr(l, "is_manual_override", False)),
                "is_first": bool(getattr(l, "is_first", False)),
            })

        return {"preview": True, "package_id": package_id, "proposed_lessons": out}

    # Otherwise perform the real regeneration (existing behavior)
    crud.regenerate_package(db, pkg)
    return {"status": "ok", "message": "Regenerated", "package_id": package_id}

@extra_router.get("/students/packages/{package_id}/regenerate")
def regenerate_preview_get(package_id: int, db: Session = Depends(get_db)):
    """
    GET preview for regenerate (no DB changes).
    Returns proposed lesson dates for the package without persisting them.
    """
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    try:
        from ..services.scheduler import generate_lessons_for_package
    except Exception:
        raise HTTPException(status_code=500, detail="Scheduler not available")

    student = pkg.student
    proposed = generate_lessons_for_package(db, student, pkg, override_existing=False)

    out: List[Dict] = []
    for l in proposed:
        out.append({
            "lesson_number": getattr(l, "lesson_number", None),
            "lesson_date": getattr(l, "lesson_date").isoformat() if getattr(l, "lesson_date", None) else None,
            "is_manual_override": bool(getattr(l, "is_manual_override", False)),
            "is_first": bool(getattr(l, "is_first", False)),
        })

    return {"preview": True, "package_id": package_id, "proposed_lessons": out}

# Edit a single lesson (date and/or manual override flag)
class LessonEditPayload(BaseModel):
    lesson_date: Optional[date] = None
    is_manual_override: Optional[bool] = None

@extra_router.patch("/lessons/{lesson_id}", response_model=schemas.LessonOut)
def edit_lesson(lesson_id: int, payload: LessonEditPayload, db: Session = Depends(get_db)):
    """
    Edit a lesson's date and/or toggle manual override.
    - lesson_date : YYYY-MM-DD (optional)
    - is_manual_override : true/false (optional)
    """
    lesson = db.query(models.Lesson).filter(models.Lesson.lesson_id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    data = payload.dict(exclude_unset=True)
    if "lesson_date" in data:
        lesson.lesson_date = data["lesson_date"]
    if "is_manual_override" in data:
        lesson.is_manual_override = bool(data["is_manual_override"])

    # commit and refresh
    db.commit()
    db.refresh(lesson)

    # If we changed dates we might want to update package.first_lesson_date
    # Recompute first_lesson_date for the package if needed.
    pkg = db.query(models.Package).filter(models.Package.package_id == lesson.package_id).first()
    if pkg:
        first = db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).order_by(models.Lesson.lesson_number).first()
        if first:
            pkg.first_lesson_date = first.lesson_date
            db.commit()
            db.refresh(pkg)

    return lesson
# --------------------------------------------------------
# GET ONE PACKAGE
# --------------------------------------------------------
@router.get("/{package_id}", response_model=schemas.PackageOut)
def get_package(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg

# --------------------------------------------------------
# TOGGLE PAYMENT STATUS
# --------------------------------------------------------
class PaymentToggle(BaseModel):
    paid: bool

@router.post("/students/packages/{package_id}/mark_paid")
def mark_paid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    updated = crud.toggle_payment(db, pkg, True)
    return {"status": "ok", "package_id": updated.package_id, "payment_status": updated.payment_status}

@router.post("/students/packages/{package_id}/mark_unpaid")
def mark_unpaid(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    updated = crud.toggle_payment(db, pkg, False)
    return {"status": "ok", "package_id": updated.package_id, "payment_status": updated.payment_status}

@extra_router.post("/students/{student_id}/packages", response_model=schemas.PackageOut)
def create_extra_package(student_id: int, package_size: int = Query(4, ge=1, le=8), db: Session = Depends(get_db)):
    """
    Create an additional package for an existing student.
    - package_size: 4 or 8 (defaults to 4)
    """
    # fetch student
    student = db.query(models.Student).filter(models.Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # create package record
    pkg = models.Package(
        student_id=student_id,
        package_size=package_size,
        payment_status=False
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # generate lessons using scheduler (if available)
    try:
        from ..services.scheduler import generate_lessons_for_package
    except Exception:
        generate_lessons_for_package = None

    if generate_lessons_for_package:
        # generate Lesson objects (function returns Lesson-like objects)
        lessons = generate_lessons_for_package(db, student, pkg, override_existing=False)

        for l in lessons:
            # if scheduler returned ORM Lesson objects they may already be attached; handle both cases
            if getattr(l, "lesson_id", None) is None:
                lesson = models.Lesson(
                    package_id=pkg.package_id,
                    lesson_number=l.lesson_number,
                    lesson_date=l.lesson_date,
                    is_first=getattr(l, "is_first", False),
                    is_manual_override=getattr(l, "is_manual_override", False)
                )
                db.add(lesson)
            else:
                # already an ORM object (manual preserved) — ensure it's merged
                db.merge(l)

    # update package.first_lesson_date from actual lessons persisted
    first = db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).order_by(models.Lesson.lesson_number).first()
    if first:
        pkg.first_lesson_date = first.lesson_date

    db.commit()
    db.refresh(pkg)
    return pkg
# --------------------------------------------------------
# REGENERATE LESSON DATES (skip closures, recalc)
# --------------------------------------------------------

@router.post("/students/packages/{package_id}/regenerate")
def regenerate_lessons(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    crud.regenerate_package(db, pkg)
    return {"status": "ok", "message": "Regenerated", "package_id": package_id}

class PackageCreate(BaseModel):
    student_id: int
    package_size: int

@router.post("/", response_model=schemas.PackageOut)
def create_package_route(payload: PackageCreate, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.student_id == payload.student_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    pkg = crud.create_package(db, student)
    return pkg

class LessonEdit(BaseModel):
    lesson_date: date
    is_manual_override: bool | None = None

@router.patch("/lessons/{lesson_id}")
def edit_lesson(lesson_id:int, payload:LessonEdit, db:Session=Depends(get_db)):
    lesson = db.query(models.Lesson).filter(models.Lesson.lesson_id==lesson_id).first()
    if not lesson: raise HTTPException(404, "Lesson not found")
    if payload.lesson_date:
        lesson.lesson_date = payload.lesson_date
    if payload.is_manual_override is not None:
        lesson.is_manual_override = payload.is_manual_override
    db.commit(); db.refresh(lesson)
    return lesson
