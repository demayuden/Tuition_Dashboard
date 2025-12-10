# backend/app/crud.py
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy.exc import IntegrityError
from . import models, schemas
from .date_utils import parse_iso_date, ensure_end_after_start
from datetime import date, timedelta
from types import SimpleNamespace

# try to import the lesson generator; if unavailable keep None
try:
    from .services.scheduler import generate_lessons_for_package
except Exception:
    generate_lessons_for_package = None

# ---------- STUDENT CRUD ----------
def create_student(db: Session, payload: schemas.StudentCreate) -> models.Student:
    """Create a student, create an initial package and (optionally) generate lessons.
       Also, if payload.end_date is provided and extends beyond the generated lessons,
       create additional packages until end_date is covered.
    """
    # normalize dates from schemas (payload may already be date objects)
    start_date = parse_iso_date(getattr(payload, "start_date", None) or None)
    end_date = parse_iso_date(getattr(payload, "end_date", None) or None)
    ensure_end_after_start(start_date, end_date)

    student = models.Student(
        name=payload.name,
        cefr=payload.cefr,
        group_name=payload.group_name,
        lesson_day_1=payload.lesson_day_1,
        lesson_day_2=payload.lesson_day_2,
        package_size=payload.package_size,
        start_date=start_date,
        end_date=end_date,
    )

    try:
        db.add(student)
        db.flush()  # ensure student.student_id is available for package FK

        # ---- create first package ----
        pkg = models.Package(
            student_id=student.student_id,
            package_size=student.package_size,
            payment_status=False
        )
        db.add(pkg)
        db.flush()  # ensure pkg.package_id is available for lessons

        # generate and persist lessons for the first package
        if generate_lessons_for_package:
            lesson_objs = generate_lessons_for_package(db, student, pkg)
            for i, lesson_obj in enumerate(lesson_objs, start=1):
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
                    lesson_obj.lesson_number = i
                    if i == 1:
                        lesson_obj.is_first = True
                    db.merge(lesson_obj)

            # compute and set first_lesson_date for this package
            first_ld = (
                db.query(models.Lesson)
                .filter(models.Lesson.package_id == pkg.package_id)
                .order_by(models.Lesson.lesson_number)
                .first()
            )
            if first_ld:
                pkg.first_lesson_date = first_ld.lesson_date

        db.commit()
        # refresh objects with DB state
        db.refresh(student)
        db.refresh(pkg)

        # ---- if an end_date was provided, create extra packages to cover until end_date ----
        if end_date:
            # helper: fetch last lesson date for a package
            def last_lesson_date_for_package(p: models.Package):
                last = (
                    db.query(models.Lesson)
                    .filter(models.Lesson.package_id == p.package_id)
                    .order_by(models.Lesson.lesson_number.desc())
                    .first()
                )
                return last.lesson_date if last else None

            # determine last date after first package
            last_date = last_lesson_date_for_package(pkg)

            # safety limit (avoid infinite loop) - maximum additional packages (e.g. 12 months / pkg)
            max_additional_packages = 12

            added = 0
            while last_date is not None and last_date < end_date and added < max_additional_packages:
                # create a new package for the same student
                new_pkg = models.Package(
                    student_id=student.student_id,
                    package_size=student.package_size,
                    payment_status=False
                )
                db.add(new_pkg)
                db.flush()  # new_pkg.package_id available

                # prepare a temporary student-like object with same lesson days but next start_date
                next_start = last_date + timedelta(days=1)
                temp_student = SimpleNamespace(
                    lesson_day_1=student.lesson_day_1,
                    lesson_day_2=student.lesson_day_2,
                    start_date=next_start
                )

                # generate lessons for the new package using the temp student (scheduler uses .start_date)
                if generate_lessons_for_package:
                    lesson_objs = generate_lessons_for_package(db, temp_student, new_pkg, override_existing=False)
                    # persist enumerated lessons (CRUD expects to enumerate)
                    for i, lesson_obj in enumerate(lesson_objs, start=1):
                        if getattr(lesson_obj, "lesson_id", None) is None:
                            lesson = models.Lesson(
                                package_id=new_pkg.package_id,
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

                    # update first_lesson_date for new package
                    first_new = (
                        db.query(models.Lesson)
                        .filter(models.Lesson.package_id == new_pkg.package_id)
                        .order_by(models.Lesson.lesson_number)
                        .first()
                    )
                    if first_new:
                        new_pkg.first_lesson_date = first_new.lesson_date

                db.commit()
                db.refresh(new_pkg)

                # advance last_date to the last lesson of the new package
                last_date = last_lesson_date_for_package(new_pkg)
                added += 1

        return student

    except Exception:
        db.rollback()
        raise

def get_student(db: Session, student_id: int) -> Optional[models.Student]:
    return db.query(models.Student).filter(models.Student.student_id == student_id).first()


def get_all_students(db: Session):
    return db.query(models.Student).order_by(models.Student.name).all()


# ---------- PACKAGE CRUD ----------
def create_package(db: Session, student: models.Student) -> models.Package:
    """Create a package for an existing student and generate lessons if generator exists."""
    pkg = models.Package(
        student_id=student.student_id,
        package_size=student.package_size,
        payment_status=False
    )
    try:
        db.add(pkg)
        db.flush()  # ensure pkg.package_id is available

        if generate_lessons_for_package:
            lesson_objs = generate_lessons_for_package(db, student, pkg)
            for i, lesson_obj in enumerate(lesson_objs, start=1):
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
                    lesson_obj.lesson_number = i
                    if i == 1:
                        lesson_obj.is_first = True
                    db.merge(lesson_obj)

            first = (
                db.query(models.Lesson)
                .filter(models.Lesson.package_id == pkg.package_id)
                .order_by(models.Lesson.lesson_number)
                .first()
            )
            if first:
                pkg.first_lesson_date = first.lesson_date

        db.commit()
        db.refresh(pkg)
        return pkg

    except Exception:
        db.rollback()
        raise


def get_package(db: Session, package_id: int) -> Optional[models.Package]:
    return db.query(models.Package).filter(models.Package.package_id == package_id).first()


# ---------- PAYMENT TOGGLE ----------
def toggle_payment(db: Session, package: models.Package, status: bool) -> models.Package:
    package.payment_status = status
    db.commit()
    db.refresh(package)
    return package


# ---------- REGENERATE LESSONS ----------
def regenerate_package(db: Session, package: models.Package) -> models.Package:
    student = package.student
    try:
        # delete non-manual lessons
        db.query(models.Lesson).filter(
            models.Lesson.package_id == package.package_id,
            models.Lesson.is_manual_override == False
        ).delete(synchronize_session=False)
        db.flush()

        # load manual lessons that remain (map by date)
        manual_lessons = db.query(models.Lesson).filter(
            models.Lesson.package_id == package.package_id,
            models.Lesson.is_manual_override == True
        ).all()
        manual_by_date = {l.lesson_date: l for l in manual_lessons}

        if generate_lessons_for_package:
            try:
                lesson_objs = generate_lessons_for_package(db, student, package, override_existing=False)
            except TypeError:
                lesson_objs = generate_lessons_for_package(db, student, package)

            for i, lesson_obj in enumerate(lesson_objs, start=1):
                # CASE A: generator returned an existing ORM lesson (has lesson_id) -> merge and set number/flags
                if getattr(lesson_obj, "lesson_id", None) is not None:
                    lesson_obj.lesson_number = i
                    if i == 1:
                        lesson_obj.is_first = True
                    db.merge(lesson_obj)
                    continue

                # At this point lesson_obj is not an ORM instance (plain object with lesson_date)
                lesson_date = getattr(lesson_obj, "lesson_date", None)
                is_manual_flag = getattr(lesson_obj, "is_manual_override", False)

                # CASE B: there's an existing manual lesson for the same date -> reuse and merge it
                existing_manual = manual_by_date.get(lesson_date)
                if existing_manual is not None:
                    existing_manual.lesson_number = i
                    if i == 1:
                        existing_manual.is_first = True
                    # keep manual override flag true (preserve)
                    existing_manual.is_manual_override = True
                    db.merge(existing_manual)
                    continue

                # CASE C: create a fresh Lesson record
                new_lesson = models.Lesson(
                    package_id=package.package_id,
                    lesson_number=i,
                    lesson_date=lesson_date,
                    is_first=(i == 1),
                    is_manual_override=is_manual_flag
                )
                db.add(new_lesson)

            # commit-ish - compute and set first_lesson_date from stored lessons
            db.flush()
            first = (
                db.query(models.Lesson)
                .filter(models.Lesson.package_id == package.package_id)
                .order_by(models.Lesson.lesson_number)
                .first()
            )
            if first:
                package.first_lesson_date = first.lesson_date

        db.commit()
        db.refresh(package)
        return package

    except IntegrityError as ie:
        # Defensive: rollback and provide clearer message during dev
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
