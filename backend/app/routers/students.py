from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import traceback

from typing import List

from .. import schemas, models, crud
from ..db import get_db

router = APIRouter(prefix="/students", tags=["Students"])

@router.post("/", response_model=schemas.StudentOut)
async def create_student(student: schemas.StudentCreate, request: Request, db: Session = Depends(get_db)):
    try:
        db_student = models.Student(
            name=student.name,
            cefr=student.cefr,
            group_name=student.group_name,
            lesson_day_1=student.lesson_day_1,
            lesson_day_2=student.lesson_day_2,
            package_size=student.package_size,
            start_date=student.start_date,
        )
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        return db_student

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "trace": traceback.format_exc().splitlines()
            }
        )


@router.get("/", response_model=List[schemas.StudentOut])
def list_students(db: Session = Depends(get_db)):
    return crud.get_all_students(db)

@router.get("/{student_id}", response_model=schemas.StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student
