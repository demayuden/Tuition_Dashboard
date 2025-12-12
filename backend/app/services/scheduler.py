# backend/app/services/scheduler.py
from datetime import date, timedelta
from typing import List, Set
from sqlalchemy.orm import Session
from types import SimpleNamespace

from ..models import Closure, Student, Package

# ---------------------------------------------------------
# Helper: iterate date range
# ---------------------------------------------------------
def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

# ---------------------------------------------------------
# Load blocked closure dates
# ---------------------------------------------------------
def load_closure_dates(db: Session) -> Set[date]:
    blocked = set()
    closures = db.query(Closure).all()
    for c in closures:
        for d in _daterange(c.start_date, c.end_date):
            blocked.add(d)
    return blocked

# ---------------------------------------------------------
# Produce valid lesson dates
# ---------------------------------------------------------
def collect_valid_dates(
    start_from: date,
    days_of_week: List[int],
    package_size: int,
    blocked: Set[date],
    end_date: date | None
) -> List[date]:

    results: List[date] = []
    cur = start_from

    # safety cutoff = 2 years
    cutoff = start_from + timedelta(days=365 * 2)
    if end_date and end_date < cutoff:
        cutoff = end_date

    while len(results) < package_size and cur <= cutoff:
        if cur.weekday() in days_of_week and cur not in blocked:
            results.append(cur)
        cur += timedelta(days=1)

    return results

# ---------------------------------------------------------
# MAIN FUNCTION: generate lessons
# ---------------------------------------------------------
def generate_lessons_for_package(
    db: Session,
    student: Student,
    pkg: Package,
    override_existing: bool = False,
    start_from: date | None = None
):
    """
    Final clean generator.
    Produces up to pkg.package_size lessons OR until student.end_date.
    """

    blocked = load_closure_dates(db)

    # Determine weekdays
    if pkg.package_size == 8 and student.lesson_day_2 is not None:
        days = sorted({student.lesson_day_1, student.lesson_day_2})
    else:
        days = [student.lesson_day_1]

    # Determine starting date
    start_date = start_from or student.start_date
    if start_date is None:
        start_date = date.today()

    end_date = student.end_date   # may be None → fallback to 2-year safety below
    pkg_size = int(pkg.package_size)

    # Build lesson dates
    results = []
    cur = start_date
    limit = start_date + timedelta(days=365 * 2)
    if end_date and end_date < limit:
        limit = end_date

    while len(results) < pkg_size and cur <= limit:
        if cur.weekday() in days and cur not in blocked:
            results.append(cur)
        cur += timedelta(days=1)

    # Convert to objects
    lessons = []
    for i, d in enumerate(results, start=1):
        lessons.append(
            SimpleNamespace(
                lesson_date=d,
                lesson_number=i,
                is_manual_override=False,
                is_first=(i == 1),
            )
        )

    return lessons

