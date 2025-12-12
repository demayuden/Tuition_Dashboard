from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .. import schemas, models, crud
from ..db import get_db
from datetime import date
from typing import Optional, List, Dict
import openpyxl
from fastapi.responses import StreamingResponse
import io
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font

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
    # Normalize proposed lessons: compute lesson_number by chronological order
    if preview:
        try:
            from ..services.scheduler import generate_lessons_for_package
        except Exception:
            raise HTTPException(status_code=500, detail="Scheduler not available")

        student = pkg.student
        proposed = generate_lessons_for_package(db, student, pkg, override_existing=False)

        # convert to plain items, ensure each has a date and is_manual flag
        flat = []
        for l in proposed:
            ld = getattr(l, "lesson_date", None)
            flat.append({
                "lesson_date": ld.isoformat() if ld is not None else None,
                "is_manual_override": bool(getattr(l, "is_manual_override", False))
            })

        # assign lesson_number by chronological order (1..N)
        # filter out items without dates (should not happen) and sort by date
        dated = [f for f in flat if f["lesson_date"]]
        dated_sorted = sorted(dated, key=lambda x: x["lesson_date"])
        for idx, item in enumerate(dated_sorted, start=1):
            item["lesson_number"] = idx

        # if you want to preserve ordering of output exactly as lesson_number 1..N, return dated_sorted
        # but to be safe return a fixed-length list with None for missing positions up to package_size:
        out = []
        # create index map
        num_map = {i["lesson_number"]: i for i in dated_sorted}
        for n in range(1, pkg.package_size + 1):
            it = num_map.get(n)
            if it:
                out.append({
                    "lesson_number": n,
                    "lesson_date": it["lesson_date"],
                    "is_manual_override": it["is_manual_override"],
                    "is_first": (n == 1)
                })
            else:
                out.append({
                    "lesson_number": n,
                    "lesson_date": None,
                    "is_manual_override": False,
                    "is_first": (n == 1)
                })

        return {"preview": True, "package_id": package_id, "proposed_lessons": out}
    
    # Otherwise perform the real regeneration (existing behavior)
    crud.regenerate_package(db, pkg)
    return {"status": "ok", "message": "Regenerated", "package_id": package_id}

@extra_router.get("/students/packages/{package_id}/regenerate")
def regenerate_preview_get(
    package_id: int,
    extend: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    GET preview for regenerate (no DB changes).
    If extend=true -> return multiple package-sized blocks up to student's end_date (or a 2-year safety limit).
    Otherwise returns a single package's proposed lessons.
    """
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    try:
        from ..services.scheduler import generate_lessons_for_package
    except Exception:
        raise HTTPException(status_code=500, detail="Scheduler not available")

    student = pkg.student

    # simple single-block preview
    if not extend:
        proposed = generate_lessons_for_package(db, student, pkg, override_existing=False)
        out: List[Dict] = []
        for l in proposed or []:
            out.append({
                "lesson_number": getattr(l, "lesson_number", None),
                "lesson_date": getattr(l, "lesson_date").isoformat() if getattr(l, "lesson_date", None) else None,
                "is_manual_override": bool(getattr(l, "is_manual_override", False)),
                "is_first": bool(getattr(l, "is_first", False)),
            })
        return {"preview": True, "package_id": package_id, "proposed_lessons": out}

    # ---------- extend == True ----------
    from datetime import date, timedelta, datetime as _datetime

    chunks: List[List[Dict]] = []
    # determine cursor: day after last lesson in this package, or student.start_date, or today
    last_date = None
    if pkg.lessons:
        # pick the max lesson_date (some lessons might be None)
        lesson_dates = [l.lesson_date for l in pkg.lessons if getattr(l, "lesson_date", None)]
        if lesson_dates:
            last_date = max(lesson_dates)

    if last_date:
        cursor = last_date + timedelta(days=1)
    else:
        cursor = student.start_date or date.today()

    # compute end cutoff
    if getattr(student, "end_date", None):
        end_cutoff = student.end_date
    else:
        end_cutoff = cursor + timedelta(days=365 * 2)

    max_blocks = 52
    blocks_generated = 0

    while cursor <= end_cutoff and blocks_generated < max_blocks:
        # call generator starting from cursor
        try:
            block_items = generate_lessons_for_package(db, student, pkg, override_existing=False, start_from=cursor)
        except TypeError:
            # fallback if generator doesn't accept start_from
            try:
                block_items = generate_lessons_for_package(db, student, pkg, override_existing=False)
            except Exception as e:
                # abort on generator failure
                break
        except Exception:
            break

        if not block_items:
            # nothing returned for this cursor -> stop
            break

        # Keep only items that have a lesson_date
        dated_items = [x for x in block_items if getattr(x, "lesson_date", None)]
        if not dated_items:
            break

        # sort by date
        dated_items_sorted = sorted(dated_items, key=lambda x: getattr(x, "lesson_date"))

        # Normalize to dicts (per-block)
        normalized: List[Dict] = []
        for l in dated_items_sorted:
            normalized.append({
                "lesson_number": None,
                "lesson_date": getattr(l, "lesson_date").isoformat() if getattr(l, "lesson_date", None) else None,
                "is_manual_override": bool(getattr(l, "is_manual_override", False)),
                "is_first": False,
            })

        if not normalized:
            break

        # Append chunk and advance cursor to after last date in chunk
        chunks.append(normalized)
        last_date_in_block = None
        for it in reversed(normalized):
            if it["lesson_date"]:
                last_date_in_block = _datetime.fromisoformat(it["lesson_date"]).date()
                break
        if not last_date_in_block:
            break

        cursor = last_date_in_block + timedelta(days=1)
        blocks_generated += 1
        if cursor > end_cutoff:
            break

    # flatten chunks into a single list (frontend will chunk by package_size)
    flat: List[Dict] = []
    for ch in chunks:
        flat.extend(ch)

    return {"preview": True, "package_id": package_id, "proposed_lessons": flat}

@extra_router.get("/export/dashboard.xlsx")
def export_dashboard_xlsx(
    tab: str = Query("all", regex="^(all|4|8)$"),
    group: str = Query("", description="Group name (optional)"),
    day: str = Query("", description="Day number 0..6 (optional)"),
    db: Session = Depends(get_db)
):
    """
    Export improved student-level dashboard view.
    - tab = "4" or "8" => one row per student showing the FIRST package of that size
    - tab = "all" => single sheet "All" that includes first package for each student (if any)
    Filters: group (group_name), day (0..6)
    """

    # Optional alias map: edit to override names in the final exported sheet.
    # Example: {"Original Full Name": "Alias Name", "Brenda Lim": "B. Lim"}
    ALIASES = {
        # "Full Original Name": "Alias To Use",
        # "Dema Yuden": "Dema Y.",
    }

    # parse filters
    tab = tab or "all"
    group = group.strip()
    day_num = None
    if day != "":
        try:
            day_num = int(day)
            if day_num < 0 or day_num > 6:
                day_num = None
        except Exception:
            day_num = None

    # choose sheet and column count
    if tab == "4":
        sheet_name = "4-lesson"
        target_sizes = [4]
        lesson_count = 4
    elif tab == "8":
        sheet_name = "8-lesson"
        target_sizes = [8]
        lesson_count = 8
    else:
        sheet_name = "All"
        target_sizes = [4, 8]
        # For "All" we'll show up to 8 columns (keeps format consistent).
        lesson_count = 8

    wb = openpyxl.Workbook()
    # remove default sheet
    default = wb.active
    wb.remove(default)

    headers = [
        "Name", "CEFR", "Group", "Day", 
    ]
    # add L1..Ln headers based on lesson_count
    headers += [f"L{i}" for i in range(1, lesson_count + 1)]

    # create sheet
    ws = wb.create_sheet(title=sheet_name)
    ws.append(headers)

    # helper to convert day numbers to labels
    def day_label_for_student(s):
        d1 = s.lesson_day_1
        d2 = s.lesson_day_2
        if d2 is None or d2 == "" or d1 == d2:
            return ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][int(d1)]
        else:
            return f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][int(d1)]} & {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][int(d2)]}"

    students = db.query(models.Student).order_by(models.Student.name).all()

    rows_written = 0
    for s in students:
        # apply student-level filters
        if group and (s.group_name or "") != group:
            continue
        if day_num is not None:
            d1 = int(s.lesson_day_1)
            d2 = s.lesson_day_2 if s.lesson_day_2 is not None else None
            if d1 != day_num and d2 != day_num:
                continue

        # find the first package for this student matching target_sizes
        pkgs = s.packages or []
        chosen_pkg = None
        for pkg in pkgs:
            if int(pkg.package_size) in target_sizes:
                chosen_pkg = pkg
                break

        # if no matching package found, skip (we want one row per student that has a package)
        if not chosen_pkg:
            continue

        # build lesson map (lesson_number -> iso date)
        lessons_map = {l.lesson_number: (l.lesson_date.isoformat() if l.lesson_date else "") for l in (chosen_pkg.lessons or [])}

        # name (apply alias if present)
        name_to_use = ALIASES.get(s.name, None)
        if not name_to_use:
            # default alias: try to shorten "First Last" -> "First Last" (no change).
            # If you want custom aliases, add them to ALIASES dict above.
            name_to_use = s.name

        lesson_days_label = day_label_for_student(s)

        # assemble row values
        row_vals = [
            name_to_use,
            s.cefr or "",
            s.group_name or "",
            lesson_days_label
        ]
        for i in range(1, lesson_count + 1):
            row_vals.append(lessons_map.get(i, ""))

        ws.append(row_vals)
        rows_written += 1

        # apply red/bold style to the first lesson cell if the package is unpaid
        if not chosen_pkg.payment_status:
            # first lesson column index (1-based): Name=1, CEFR=2, Group=3, Day=4 -> L1 at 5
            first_lesson_col = 5
            first_cell = ws.cell(row=ws.max_row, column=first_lesson_col)
            if first_cell.value:
                first_cell.font = Font(color="FF0000", bold=True)

    # If no rows written, optionally add a note row
    if rows_written == 0:
        ws.append(["No matching students/packages for the selected filters."])

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                vlen = len(str(cell.value))
                if vlen > max_len:
                    max_len = vlen
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    # stream back
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"tuition_dashboard_{sheet_name}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
    
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
        lessons = generate_lessons_for_package(db, student, pkg, override_existing=False)

        # Ensure chronological order and enumerate lesson_number ourselves
        # Build list of (date, is_manual, orm_obj?) items
        items = []
        for l in lessons:
            if getattr(l, "lesson_date", None) is not None:
                items.append(l)

        # sort by date
        items_sorted = sorted(items, key=lambda x: getattr(x, "lesson_date"))

        # now enumerate and persist
        for i, l in enumerate(items_sorted, start=1):
            # if the scheduler returned an ORM Lesson (manual preserved), merge it but update numbers/flags
            if getattr(l, "lesson_id", None) is not None:
                l.lesson_number = i
                if i == 1:
                    l.is_first = True
                db.merge(l)
            else:
                # plain object (SimpleNamespace etc.)
                lesson = models.Lesson(
                    package_id=pkg.package_id,
                    lesson_number=i,
                    lesson_date=getattr(l, "lesson_date"),
                    is_first=(i == 1),
                    is_manual_override=getattr(l, "is_manual_override", False)
                )
                db.add(lesson)

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
