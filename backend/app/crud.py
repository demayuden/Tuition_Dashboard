from sqlalchemy.orm import Session
from datetime import date
from . import models, schemas
from .services.scheduler import generate_package_lessons


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
# PACKAGE CRUD
# --------------------------------------------------------
def create_package(db: Session, student: models.Student):
    """
    When a package is created, automatically generate lesson dates.
    """
    pkg = models.Package(
        student_id=student.id,
        package_size=student.package_size,
        payment_status=False  # unpaid by default
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # Get closure ranges
    closures = db.query(models.Closure).all()
    closures_list = [(c.start_date, c.end_date) for c in closures]

    # Determine lesson days
    lesson_days = [student.lesson_day_1]
    if student.package_size == 8 and student.lesson_day_2 is not None:
        lesson_days = sorted([student.lesson_day_1, student.lesson_day_2])

    # Generate lesson dates
    lesson_dates = generate_package_lessons(
        student.start_date,
        lesson_days,
        student.package_size,
        closures_list
    )

    # Save lessons into DB
    for i, d in enumerate(lesson_dates, start=1):
        lesson = models.Lesson(
            package_id=pkg.id,
            lesson_number=i,
            lesson_date=d,
            is_first=(i == 1)
        )
        db.add(lesson)

    db.commit()
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
# REGENERATE LESSONS
# --------------------------------------------------------
def regenerate_package(db: Session, package: models.Package):
    student = package.student

    # Delete non-manual lessons
    db.query(models.Lesson).filter(
        models.Lesson.package_id == package.id,
        models.Lesson.is_manual_override == False
    ).delete()

    closures = db.query(models.Closure).all()
    closures_list = [(c.start_date, c.end_date) for c in closures]

    # Lesson days
    lesson_days = [student.lesson_day_1]
    if package.package_size == 8 and student.lesson_day_2 is not None:
        lesson_days = sorted([student.lesson_day_1, student.lesson_day_2])

    # Generate
    lesson_dates = generate_package_lessons(
        student.start_date,
        lesson_days,
        package.package_size,
        closures_list
    )

    # Save new lessons
    for i, d in enumerate(lesson_dates, start=1):
        lesson = models.Lesson(
            package_id=package.id,
            lesson_number=i,
            lesson_date=d,
            is_first=(i == 1)
        )
        db.add(lesson)

    db.commit()
    return package
