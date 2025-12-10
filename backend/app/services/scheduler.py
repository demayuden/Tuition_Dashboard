# backend/app/services/scheduler.py
from datetime import date, timedelta
from typing import List, Set
from sqlalchemy.orm import Session
from types import SimpleNamespace

from ..models import Closure, Lesson, Package, Student

def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def load_closure_dates(db: Session) -> Set[date]:
    blocked: Set[date] = set()
    for c in db.query(Closure).all():
        for d in _daterange(c.start_date, c.end_date):
            blocked.add(d)
    return blocked

def next_dates_for_days(start_from: date, days_of_week: List[int], needed: int, blocked: Set[date]) -> List[date]:
    results: List[date] = []
    cur = start_from
    limit_date = start_from + timedelta(days=365*2)
    while len(results) < needed and cur <= limit_date:
        if cur.weekday() in days_of_week and cur not in blocked:
            results.append(cur)
        cur += timedelta(days=1)
    return results

def generate_lessons_for_package(db: Session, student: Student, pkg: Package, override_existing: bool = False) -> List:
    """
    Generate a list of lesson-like objects for the package.

    - Returns ORM Lesson objects for existing manual lessons (so CRUD will merge them).
    - Returns simple objects (SimpleNamespace with .lesson_date and .is_manual_override) for new lessons.
    - Does NOT set lesson_number. CRUD will enumerate and assign lesson_number and is_first.
    - Manual lessons are always preserved (included) even if their dates are in closure/blocked dates.
    """
    blocked = load_closure_dates(db)

    # Decide which weekdays to use
    if pkg.package_size == 8 and student.lesson_day_2 is not None:
        days = sorted({student.lesson_day_1, student.lesson_day_2})
    else:
        days = [student.lesson_day_1]

    start_date = student.start_date

    # Optionally remove old non-manual lessons (only when generator asked to override)
    if override_existing:
        db.query(Lesson).filter(
            Lesson.package_id == pkg.package_id,
            Lesson.is_manual_override == False
        ).delete(synchronize_session=False)
        db.flush()

    # Load manual lessons to preserve them (map by date)
    manual_lessons = db.query(Lesson).filter(
        Lesson.package_id == pkg.package_id,
        Lesson.is_manual_override == True
    ).order_by(Lesson.lesson_date).all()
    manual_by_date = {l.lesson_date: l for l in manual_lessons}
    manual_count = len(manual_lessons)

    # Quick exit: if manual lessons already satisfy package size, return them (no new lessons)
    needed = pkg.package_size - manual_count
    if needed <= 0:
        # Let CRUD assign numbers; just return ORM objects (sorted)
        return sorted(manual_lessons, key=lambda x: x.lesson_date)

    # Build candidate dates but treat manual dates specially:
    # - When selecting candidate dates for NEW lessons, exclude blocked dates.
    # - But ensure manual dates are included in the output even if they are blocked.
    # We'll collect candidate dates (excluding blocked), then interleave manual lessons by date when found.
    candidates = next_dates_for_days(start_date, days, needed + 50, blocked)

    lessons_out = []
    used_manual_dates = set()

    # We iterate through candidates and pick either existing manual lesson (if date matches)
    # or create a new simple object for that candidate.
    i = 0
    while len([x for x in lessons_out if getattr(x, "lesson_date", None)]) + manual_count < pkg.package_size and i < len(candidates):
        cand = candidates[i]
        if cand in manual_by_date:
            # include the existing manual ORM object (preserve flags)
            preserved = manual_by_date[cand]
            lessons_out.append(preserved)
            used_manual_dates.add(cand)
        else:
            # create a plain lightweight object for CRUD to convert into DB row later
            lessons_out.append(SimpleNamespace(lesson_date=cand, is_manual_override=False))
        i += 1

    # If we still need more (candidates exhausted), continue scanning forward date-by-date
    cur = candidates[-1] + timedelta(days=1) if candidates else start_date
    while len([x for x in lessons_out if getattr(x, "lesson_date", None)]) + manual_count < pkg.package_size and cur <= start_date + timedelta(days=365*2):
        # allow manual dates even if blocked (they're already handled), but only add new when not blocked and not manual
        if cur.weekday() in days and cur not in blocked and cur not in manual_by_date:
            lessons_out.append(SimpleNamespace(lesson_date=cur, is_manual_override=False))
        cur += timedelta(days=1)

    # Finally, ensure manual lessons that were not included above (because their date was earlier than the first candidate)
    # are included — manual lessons must always be preserved.
    for m in manual_lessons:
        if m.lesson_date not in used_manual_dates:
            lessons_out.append(m)

    # Sort output by date so CRUD assigns lesson numbers in chronological order
    # Keep ORM manual objects and SimpleNamespace objects mixed — CRUD will handle both.
    lessons_out = sorted(lessons_out, key=lambda l: getattr(l, "lesson_date", date.max))

    # Do NOT set lesson_number or is_first here — let crud.py set numbering and is_first flag when persisting.
    # However we can set pkg.first_lesson_date candidate (optional) — but crud will compute after persisting.
    return lessons_out
