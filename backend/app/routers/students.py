# backend/app/routers/students.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fastapi import Body
from .. import schemas, models, crud
from ..db import get_db

router = APIRouter(prefix="/students", tags=["Students"])

# CREATE STUDENT
@router.post("/", response_model=schemas.StudentOut)
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    # uses crud.create_student which returns the ORM student
    created = crud.create_student(db, student)
    return created


# LIST ALL STUDENTS
@router.get("/", response_model=List[schemas.StudentOut])
def list_students(db: Session = Depends(get_db)):
    return crud.get_all_students(db)


# GET ONE STUDENT
@router.get("/{student_id}", response_model=schemas.StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

# PATCH /students/{student_id} - update one or more fields on a student
@router.patch("/{student_id}", response_model=schemas.StudentOut)
def update_student(student_id: int, payload: schemas.StudentUpdate, db: Session = Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # apply only provided fields
    updateable = {
        "name", "cefr", "group_name", "lesson_day_1", "lesson_day_2",
        "package_size", "start_date", "status"
    }

    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        # field names in DB model match the schema field names
        if key in updateable:
            setattr(student, key, value)

    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}")
def delete_student(student_id:int, db:Session=Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student: raise HTTPException(404,"Student not found")
    db.delete(student)
    db.commit()
    return {"status":"ok"}