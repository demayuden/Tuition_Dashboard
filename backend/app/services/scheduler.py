# backend/app/services/scheduler.py
from datetime import date, timedelta
from typing import List, Set
from sqlalchemy.orm import Session
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

def generate_lessons_for_package(db: Session, student: Student, pkg: Package, override_existing: bool = False) -> List[Lesson]:
    blocked = load_closure_dates(db)

    # Decide which weekdays to use
    if pkg.package_size == 8 and student.lesson_day_2 is not None:
        days = sorted({student.lesson_day_1, student.lesson_day_2})
    else:
        days = [student.lesson_day_1]

    start_date = student.start_date

    # Optionally remove old non-manual lessons
    if override_existing:
        db.query(Lesson).filter(Lesson.package_id == pkg.package_id, Lesson.is_manual_override == False).delete(synchronize_session=False)
        db.flush()

    # Load manual lessons to preserve them (ordered by date)
    manual_lessons = db.query(Lesson).filter(Lesson.package_id == pkg.package_id, Lesson.is_manual_override == True).order_by(Lesson.lesson_date).all()
    manual_dates = {l.lesson_date: l for l in manual_lessons}
    manual_count = len(manual_lessons)

    needed = pkg.package_size - manual_count
    if needed <= 0:
        for idx, l in enumerate(sorted(manual_lessons, key=lambda x: x.lesson_date), start=1):
            l.lesson_number = idx
        if manual_lessons:
            first = sorted(manual_lessons, key=lambda x: x.lesson_date)[0]
            first.is_first = True
            pkg.first_lesson_date = first.lesson_date
        return manual_lessons

    candidates = next_dates_for_days(start_date, days, needed + 20, blocked)

    lessons = []
    lesson_number = 1
    i = 0
    while len(lessons) + manual_count < pkg.package_size and i < len(candidates):
        cand = candidates[i]
        if cand in manual_dates:
            preserved = manual_dates[cand]
            preserved.lesson_number = lesson_number
            lessons.append(preserved)
        else:
            new = Lesson(package_id=pkg.package_id, lesson_number=lesson_number, lesson_date=cand, is_first=False, is_manual_override=False)
            lessons.append(new)
        lesson_number += 1
        i += 1

    cur = candidates[-1] + timedelta(days=1) if candidates else start_date
    while len(lessons) + manual_count < pkg.package_size and cur <= start_date + timedelta(days=365*2):
        if cur.weekday() in days and cur not in blocked and cur not in manual_dates:
            new = Lesson(package_id=pkg.package_id, lesson_number=lesson_number, lesson_date=cur, is_first=False, is_manual_override=False)
            lessons.append(new)
            lesson_number += 1
        cur += timedelta(days=1)

    if lessons:
        lessons_sorted = sorted(lessons, key=lambda l: l.lesson_number)
        lessons_sorted[0].is_first = True
        pkg.first_lesson_date = lessons_sorted[0].lesson_date

    return lessons
