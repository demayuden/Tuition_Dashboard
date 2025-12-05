from datetime import date, timedelta
from typing import List, Tuple


# --------------------------------------------
# Check if a date falls into any closure range
# --------------------------------------------
def is_in_closures(d: date, closures: List[Tuple[date, date]]) -> bool:
    for start, end in closures:
        if start <= d <= end:
            return True
    return False


# --------------------------------------------
# Find the next occurrence of a weekday on or after a given date
# --------------------------------------------
def next_weekday_on_or_after(d: date, target_wd: int) -> date:
    """
    target_wd: 0 = Monday ... 6 = Sunday
    """
    days_ahead = (target_wd - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


# --------------------------------------------
# Main generator function for lessons
# --------------------------------------------
def generate_package_lessons(
    start_date: date,
    lesson_days: List[int],
    package_size: int,
    closures: List[Tuple[date, date]],
    max_lookahead_weeks: int = 52
) -> List[date]:
    """
    Generate lesson dates for 4-lesson or 8-lesson packages.

    lesson_days:
        - For 4 lessons: [weekday]
        - For 8 lessons: [weekday1, weekday2]  (e.g., [1, 3] for Tue & Thu)

    package_size: 4 or 8
    closures: list of (start_date, end_date)
    """

    if not lesson_days:
        raise ValueError("lesson_days cannot be empty")

    lesson_days = sorted(lesson_days)
    lessons = []

    # ----------------------------------------
    # Find the first possible lesson day
    # ----------------------------------------
    first_candidates = [
        next_weekday_on_or_after(start_date, wd) for wd in lesson_days
    ]
    cursor_date = min(first_candidates)

    # Determine which index in lesson_days we are currently using
    try:
        current_idx = lesson_days.index(cursor_date.weekday())
    except ValueError:
        current_idx = 0

    weeks_checked = 0

    # ----------------------------------------
    # Main loop to generate each lesson date
    # ----------------------------------------
    while len(lessons) < package_size and weeks_checked < max_lookahead_weeks:

        target_wd = lesson_days[current_idx]
        candidate = next_weekday_on_or_after(cursor_date, target_wd)

        # Skip closure dates (add 7 days each retry)
        closure_attempts = 0
        while is_in_closures(candidate, closures):
            candidate = candidate + timedelta(days=7)
            closure_attempts += 1

            if closure_attempts > (max_lookahead_weeks * 2):
                raise RuntimeError("Too many closure collisions")

        # Ensure lessons are strictly increasing dates
        if lessons and candidate <= lessons[-1]:
            candidate = lessons[-1] + timedelta(days=1)
            candidate = next_weekday_on_or_after(candidate, target_wd)

            # Skip closures again
            while is_in_closures(candidate, closures):
                candidate = candidate + timedelta(days=7)

        # Add final accepted date
        lessons.append(candidate)

        # ----------------------------------------
        # Advance to next lesson slot
        # ----------------------------------------
        current_idx += 1

        # If we finished all weekdays for this week, go to next week
        if current_idx >= len(lesson_days):
            current_idx = 0
            cursor_date = candidate + timedelta(days=1)
            weeks_checked += 1
        else:
            cursor_date = candidate + timedelta(days=1)

    # If after all lookahead weeks we still don't have enough lessons
    if len(lessons) < package_size:
        raise RuntimeError("Could not generate enough lessons")

    return lessons
