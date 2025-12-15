# backend/app/crud.py
from sqlalchemy.orm import Session, selectinload
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
    """
    Create a student and a single package. Generate up to `package_size` lessons,
    but stop at the student's end_date if provided. Do NOT auto-create additional packages.
    Keep package_size stored as the chosen value (4 or 8) even if fewer lessons are generated.
    """
    # normalize dates from schemas (payload may already be date objects)
    start_date = parse_iso_date(getattr(payload, "start_date", None) or None)
    end_date = parse_iso_date(getattr(payload, "end_date", None) or None)
    ensure_end_after_start(start_date, end_date)

    # normalize package_size to 4 or 8 only (defensive)
    try:
        incoming_ps = int(getattr(payload, "package_size", 4))
    except Exception:
        incoming_ps = 4
    pkg_size = 8 if incoming_ps >= 8 else 4

    student = models.Student(
        name=payload.name,
        cefr=payload.cefr,
        group_name=payload.group_name,
        lesson_day_1=payload.lesson_day_1,
        lesson_day_2=payload.lesson_day_2,
        package_size=pkg_size,
        start_date=start_date,
        end_date=end_date,
    )

    try:
        db.add(student)
        db.flush()  # ensure student.student_id is available

        # create exactly one package for this student (visible package)
        pkg = models.Package(
            student_id=student.student_id,
            package_size=pkg_size,
            payment_status=False
        )
        db.add(pkg)
        db.flush()  # ensure pkg.package_id is available

        # generate lesson objects for this single package (scheduler respects student.end_date)
        lesson_objs = []
        if generate_lessons_for_package:
            try:
                start_from = student.start_date
                
                lesson_objs = generate_lessons_for_package(db, student, pkg, override_existing=False, start_from=start_from)
                if lesson_objs is None:
                    lesson_objs = []
            except TypeError:
                # fallback for older scheduler signature
                try:
                    lesson_objs = generate_lessons_for_package(db, student, pkg)
                    if lesson_objs is None:
                        lesson_objs = []
                except Exception as e:
                    print("WARNING: generate_lessons_for_package failed in create_student (fallback):", e)
                    lesson_objs = []
            except Exception as e:
                print("WARNING: generate_lessons_for_package failed in create_student:", e)
                lesson_objs = []

        # Persist lessons safely
        added = 0
        for obj in lesson_objs:
            if getattr(obj, "lesson_date", None) is None:
                continue
            added += 1
            if added > pkg_size:
                break

            if getattr(obj, "lesson_id", None) is None:
                lesson = models.Lesson(
                    package_id=pkg.package_id,
                    lesson_number=added,
                    lesson_date=obj.lesson_date,
                    is_first=(added == 1),
                    is_manual_override=getattr(obj, "is_manual_override", False)
                )
                db.add(lesson)
            else:
                obj.lesson_number = added
                if added == 1:
                    obj.is_first = True
                db.merge(obj)


        # compute first_lesson_date based on persisted lessons (if any)
        first_ld = (
            db.query(models.Lesson)
            .filter(models.Lesson.package_id == pkg.package_id)
            .order_by(models.Lesson.lesson_number)
            .first()
        )
        if first_ld:
            pkg.first_lesson_date = first_ld.lesson_date

        db.commit()
        db.refresh(student)
        db.refresh(pkg)
        return student

    except Exception:
        db.rollback()
        raise


def get_student(db: Session, student_id: int) -> Optional[models.Student]:
    return db.query(models.Student).filter(models.Student.student_id == student_id).first()

def get_all_students(db: Session):
    return (
        db.query(models.Student)
        .options(
            selectinload(models.Student.packages)
            .selectinload(models.Package.lessons)
        )
        .order_by(models.Student.name)
        .all()
    )

# ---------- PACKAGE CRUD ----------
def create_package(db: Session, student: models.Student) -> models.Package:
    """Create a package for an existing student and generate lessons if generator exists."""
    pkg = models.Package(
        student_id=student.student_id,
        package_size=int(student.package_size),
        payment_status=False
    )
    try:
        db.add(pkg)
        db.flush()  # ensure pkg.package_id is available

        lesson_objs = []
        if generate_lessons_for_package:
            try:
                lesson_objs = generate_lessons_for_package(db, student, pkg)
                if lesson_objs is None:
                    lesson_objs = []
            except Exception as e:
                print("WARNING: generate_lessons_for_package failed in create_package:", e)
                lesson_objs = []

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
        # 🔹 SAME start_from logic as preview
        existing_dates = [
            l.lesson_date for l in package.lessons if l.lesson_date
        ]
        start_from = min(existing_dates) if existing_dates else student.start_date

        # 🔹 delete auto lessons only
        db.query(models.Lesson).filter(
            models.Lesson.package_id == package.package_id,
            models.Lesson.is_manual_override == False
        ).delete(synchronize_session=False)
        db.flush()

        from .services.scheduler import generate_lessons_for_package

        lesson_objs = generate_lessons_for_package(
            db,
            student,
            package,
            override_existing=False,
            start_from=start_from
        ) or []

        for idx, l in enumerate(lesson_objs, start=1):
            db.add(models.Lesson(
                package_id=package.package_id,
                lesson_number=idx,
                lesson_date=l.lesson_date,
                is_first=(idx == 1),
                is_manual_override=False
            ))

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

    except Exception:
        db.rollback()
        raise

def prune_packages_to_end_date(db: Session, student: models.Student, new_end_date: date):
    """
    Prune / remove / trim packages for student so no package *starts* after new_end_date.
    - Deletes packages where first_lesson_date > new_end_date (only if unpaid).
    - For packages that start <= new_end_date but contain lessons beyond new_end_date,
      delete those lessons and renumber remaining lessons.
    Returns: dict with summary: {"deleted_packages": [ids], "skipped_paid": [ids], "trimmed_packages": [ids]}
    """
    deleted = []
    skipped_paid = []
    trimmed = []

    # get packages ordered by first_lesson_date (nulls at end)
    pkgs = db.query(models.Package).filter(models.Package.student_id == student.student_id).order_by(models.Package.first_lesson_date.nulls_last()).all()

    for pkg in pkgs:
        first_ld = pkg.first_lesson_date
        # if package has no lessons (first_ld is None), decide policy: treat as start after end_date -> delete if unpaid
        if first_ld is None:
            # treat as starting after; delete if unpaid
            if pkg.payment_status:
                skipped_paid.append(pkg.package_id)
                continue
            # delete lessons (if any) and package
            db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).delete(synchronize_session=False)
            db.delete(pkg)
            deleted.append(pkg.package_id)
            continue

        if first_ld > new_end_date:
            # package starts entirely after allowed end_date
            if pkg.payment_status:
                skipped_paid.append(pkg.package_id)
                continue
            # delete package and its lessons
            db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).delete(synchronize_session=False)
            db.delete(pkg)
            deleted.append(pkg.package_id)
        else:
            # first lesson before or on new_end_date: check for lessons after new_end_date
            lessons_after = db.query(models.Lesson).filter(
                models.Lesson.package_id == pkg.package_id,
                models.Lesson.lesson_date > new_end_date
            ).order_by(models.Lesson.lesson_number).all()

            if lessons_after:
                # If package is paid, skip trimming (or you can still trim but safer to skip)
                if pkg.payment_status:
                    skipped_paid.append(pkg.package_id)
                    continue

                # delete lessons beyond end_date
                db.query(models.Lesson).filter(
                    models.Lesson.package_id == pkg.package_id,
                    models.Lesson.lesson_date > new_end_date
                ).delete(synchronize_session=False)

                # now renumber remaining lessons for this package
                remaining = db.query(models.Lesson).filter(models.Lesson.package_id == pkg.package_id).order_by(models.Lesson.lesson_date).all()
                for idx, l in enumerate(remaining, start=1):
                    l.lesson_number = idx
                    l.is_first = (idx == 1)
                # update package_size optionally (set to len(remaining))
                pkg.package_size = len(remaining)
                # update first_lesson_date
                if remaining:
                    pkg.first_lesson_date = remaining[0].lesson_date
                else:
                    pkg.first_lesson_date = None

                trimmed.append(pkg.package_id)

    db.commit()
    return {"deleted_packages": deleted, "skipped_paid": skipped_paid, "trimmed_packages": trimmed}