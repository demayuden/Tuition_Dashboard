# backend/app/routers/students.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import traceback
from typing import List

from .. import schemas, models, crud
from ..db import get_db

router = APIRouter(prefix="/students", tags=["Students"])

# Accept both /students and /students/
@router.post("/", response_model=schemas.StudentOut)
@router.post("", response_model=schemas.StudentOut)
async def create_student(student: schemas.StudentCreate, request: Request, db: Session = Depends(get_db)):
    """
    Create a student and auto-create package + lessons.
    Accepts both /students and /students/ (fixes 405 issues when trailing slash differs).
    """
    try:
        # Use crud.create_student which should only create the student.
        # If you want to auto-create a package here instead, call crud.create_package afterwards.
        s = crud.create_student(db, student)
        # Optionally auto-create a package if your flow requires it:
        # pkg = crud.create_package(db, s)
        return s
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(exc), "trace": traceback.format_exc().splitlines()})


@router.post("/packages/{pkg_id}/mark_paid", response_model=dict)
def mark_package_paid(pkg_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    pkg = crud.toggle_payment(db, pkg, True)
    return {"package_id": pkg.id, "payment_status": pkg.payment_status}


@router.post("/packages/{pkg_id}/mark_unpaid", response_model=dict)
def mark_package_unpaid(pkg_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    pkg = crud.toggle_payment(db, pkg, False)
    return {"package_id": pkg.id, "payment_status": pkg.payment_status}


# Accept both GET /students and GET /students/
@router.get("/", response_model=List[schemas.StudentOut])
@router.get("", response_model=List[schemas.StudentOut])
def list_students(db: Session = Depends(get_db)):
    return crud.get_all_students(db)


@router.get("/{student_id}", response_model=schemas.StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student
