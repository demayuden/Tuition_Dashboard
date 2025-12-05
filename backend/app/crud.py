from sqlalchemy.orm import Session
from datetime import date
from . import models, schemas
# correct import
from .services.scheduler import generate_lessons_for_package


# --------------------------------------------------------
# STUDENT CRUD
# --------------------------------------------------------
def create_student(db: Session, payload: schemas.StudentCreate):
    student = models.Student(**payload.dict())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_student(db: Session, student_id: int):
    return db.query(models.Student).filter(models.Student.id == student_id).first()


def get_all_students(db: Session):
    return db.query(models.Student).order_by(models.Student.name).all()


# --------------------------------------------------------
# PACKAGE CRUD (updated to use generate_lessons_for_package)
# --------------------------------------------------------
def create_package(db: Session, student: models.Student):
    """
    When a package is created, automatically generate lesson rows using
    generate_lessons_for_package(db, student, pkg).
    """
    pkg = models.Package(
        student_id=student.id,
        package_size=student.package_size,
        payment_status=False  # unpaid by default
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # Use the scheduler service to produce Lesson objects (may be DB objects or new objects)
    lessons = generate_lessons_for_package(db, student, pkg, override_existing=False)

    # Persist lessons: if object is attached to session it's fine; otherwise add/merge
    for l in lessons:
        # If l is already persistent, merge will just return it; otherwise it inserts
        db.merge(l)

    # commit once
    db.commit()
    db.refresh(pkg)
    return pkg


def get_package(db: Session, package_id: int):
    return db.query(models.Package).filter(models.Package.id == package_id).first()


# --------------------------------------------------------
# PAYMENT TOGGLE
# --------------------------------------------------------
def toggle_payment(db: Session, package: models.Package, status: bool):
    package.payment_status = status
    db.commit()
    db.refresh(package)
    return package


# --------------------------------------------------------
# REGENERATE LESSONS (updated)
# --------------------------------------------------------
def regenerate_package(db: Session, package: models.Package):
    student = package.student

    # delete non-manual lessons (we will regenerate)
    db.query(models.Lesson).filter(
        models.Lesson.package_id == package.id,
        models.Lesson.is_manual_override == False
    ).delete(synchronize_session=False)
    db.flush()

    # Call scheduler with override_existing=True so it will remove/replace non-manual lessons
    lessons = generate_lessons_for_package(db, student, package, override_existing=True)

    # Persist merged/new lessons
    for l in lessons:
        db.merge(l)

    db.commit()
    db.refresh(package)
    return package
