# backend/app/routers/students.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Any

from .. import crud, schemas, models
from ..db import get_db
from ..date_utils import parse_iso_date, ensure_end_after_start

router = APIRouter(prefix="/students", tags=["students"])

# ... other endpoints (GET / POST etc.)
@router.post("/", response_model=schemas.StudentOut)
def create_student(payload: schemas.StudentCreate, db: Session = Depends(get_db)):
    student = crud.create_student(db, payload)
    return student

@router.get("", response_model=list[schemas.StudentOut])
@router.get("/", response_model=list[schemas.StudentOut])
def list_students(db: Session = Depends(get_db)):
    return crud.get_all_students(db)

@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    # optional: delete cascade packages/lessons (your models may already cascade)
    db.delete(student)
    db.commit()
    return {"status": "ok", "student_id": student_id}

@router.patch("/{student_id}", response_model=schemas.StudentOut)
def update_student(student_id: int, payload: schemas.StudentUpdate, db: Session = Depends(get_db)):
    """
    Partial update (PATCH) for student.
    schemas.StudentUpdate should have optional fields such as:
      name?: str, cefr?: str, group_name?: str, lesson_day_1?: int, lesson_day_2?: Optional[int],
      package_size?: int, start_date?: date | str, end_date?: date | str
    """
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # parse dates if provided and validate
    start_date = parse_iso_date(getattr(payload, "start_date", None))
    end_date = parse_iso_date(getattr(payload, "end_date", None))
    # if payload provides both, ensure end >= start; if only end provided and student has start_date, validate
    effective_start = start_date or student.start_date
    effective_end = end_date or student.end_date
    ensure_end_after_start(effective_start, effective_end)

    # apply provided fields (only update when not None)
    if getattr(payload, "name", None) is not None:
        student.name = payload.name
    if getattr(payload, "cefr", None) is not None:
        student.cefr = payload.cefr
    if getattr(payload, "group_name", None) is not None:
        student.group_name = payload.group_name
    if getattr(payload, "lesson_day_1", None) is not None:
        student.lesson_day_1 = payload.lesson_day_1
    # lesson_day_2 may be explicit null
    if hasattr(payload, "lesson_day_2"):
        student.lesson_day_2 = payload.lesson_day_2
    if getattr(payload, "package_size", None) is not None:
        student.package_size = payload.package_size
    if start_date is not None:
        student.start_date = start_date
    if end_date is not None or (hasattr(payload, "end_date") and payload.end_date is None):
        # set to parsed date or explicit null
        student.end_date = end_date

    # if package_size changed and you want to auto-create new package, call crud.create_package(student)
    # (be careful — you may prefer an explicit endpoint to add packages)
    db.commit()
    db.refresh(student)
    return student
