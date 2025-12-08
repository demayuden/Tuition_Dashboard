# backend/app/crud.py
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from . import models, schemas

try:
    from .services.scheduler import generate_lessons_for_package
except Exception:
    generate_lessons_for_package = None


# STUDENT CRUD
def create_student(db: Session, payload: schemas.StudentCreate):
    student = models.Student(
        name=payload.name,
        cefr=payload.cefr,
        group_name=payload.group_name,
        lesson_day_1=payload.lesson_day_1,
        lesson_day_2=payload.lesson_day_2,
        package_size=payload.package_size,
        start_date=payload.start_date,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # create package for the student
    pkg = models.Package(
        student_id=student.student_id,
        package_size=student.package_size,
        payment_status=False
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # generate and persist lessons using new signature: (db, student, pkg)
    if generate_lessons_for_package:
        lesson_objs = generate_lessons_for_package(db, student, pkg)
        for i, lesson_obj in enumerate(lesson_objs, start=1):
            # if lesson_obj already is a DB object (manual preserved) it may already be in session
            if getattr(lesson_obj, "lesson_id", None) is None:
                lesson = models.Lesson(
                    package_id=pkg.package_id,
                    lesson_number=i,
                    lesson_date=lesson_obj.lesson_date,
                    is_first=(i == 1),
                    is_manual_override=getattr(lesson_obj, "is_manual_override", False)
                )
                db.add(lesson)
            else:
                # ensure numbers / flags are set and merged
                lesson_obj.lesson_number = i
                if i == 1:
                    lesson_obj.is_first = True
                db.merge(lesson_obj)

        # set first_lesson_date if any lessons
        first_date = None
        ld = db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).order_by(models.Lesson.lesson_number).first()
        if ld:
            first_date = ld.lesson_date
        pkg.first_lesson_date = first_date
        db.commit()
        db.refresh(pkg)

    return student


def get_student(db: Session, student_id: int):
    return db.query(models.Student).filter(models.Student.student_id == student_id).first()


def get_all_students(db: Session):
    return db.query(models.Student).order_by(models.Student.name).all()


# PACKAGE CRUD
def create_package(db: Session, student: models.Student):
    pkg = models.Package(
        student_id=student.student_id,
        package_size=student.package_size,
        payment_status=False
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    if generate_lessons_for_package:
        lesson_objs = generate_lessons_for_package(db, student, pkg)
        for i, lesson_obj in enumerate(lesson_objs, start=1):
            if getattr(lesson_obj, "lesson_id", None) is None:
                lesson = models.Lesson(
                    package_id=pkg.package_id,
                    lesson_number=i,
                    lesson_date=lesson_obj.lesson_date,
                    is_first=(i == 1)
                )
                db.add(lesson)
            else:
                lesson_obj.lesson_number = i
                if i == 1:
                    lesson_obj.is_first = True
                db.merge(lesson_obj)

        # set first_lesson_date
        first = db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).order_by(models.Lesson.lesson_number).first()
        if first:
            pkg.first_lesson_date = first.lesson_date

    db.commit()
    db.refresh(pkg)
    return pkg


def get_package(db: Session, package_id: int):
    return db.query(models.Package).filter(models.Package.package_id == package_id).first()


# PAYMENT TOGGLE
def toggle_payment(db: Session, package: models.Package, status: bool):
    package.payment_status = status
    db.commit()
    db.refresh(package)
    return package


# REGENERATE LESSONS
def regenerate_package(db: Session, package: models.Package):
    student = package.student

    # delete non-manual lessons
    db.query(models.Lesson).filter(
        models.Lesson.package_id == package.package_id,
        models.Lesson.is_manual_override == False
    ).delete(synchronize_session=False)
    db.flush()

    if generate_lessons_for_package:
        lesson_objs = generate_lessons_for_package(db, student, package, override_existing=False)
        for i, lesson_obj in enumerate(lesson_objs, start=1):
            if getattr(lesson_obj, "lesson_id", None) is None:
                lesson = models.Lesson(
                    package_id=package.package_id,
                    lesson_number=i,
                    lesson_date=lesson_obj.lesson_date,
                    is_first=(i == 1),
                    is_manual_override=getattr(lesson_obj, "is_manual_override", False)
                )
                db.add(lesson)
            else:
                lesson_obj.lesson_number = i
                if i == 1:
                    lesson_obj.is_first = True
                db.merge(lesson_obj)

        # update first_lesson_date
        first = db.query(models.Lesson).filter(models.Lesson.package_id == package.package_id).order_by(models.Lesson.lesson_number).first()
        if first:
            package.first_lesson_date = first.lesson_date

    db.commit()
    db.refresh(package)
    return package
