from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .. import schemas, models, crud
from ..db import get_db
from datetime import date


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
def regenerate_lessons(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    crud.regenerate_package(db, pkg)
    return {"status": "ok", "package_id": package_id}
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
