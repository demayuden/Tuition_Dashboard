from pydantic import BaseModel
from datetime import date
from typing import List, Optional
from datetime import datetime

# --------------------------------------------
# Lesson Schema
# --------------------------------------------
class LessonOut(BaseModel):
    id: int
    lesson_number: int
    lesson_date: date
    is_first: bool
    is_manual_override: bool

    class Config:
        orm_mode = True


# --------------------------------------------
# Package Schema
# --------------------------------------------
class PackageOut(BaseModel):
    id: int
    package_size: int
    payment_status: bool
    created_at: Optional[datetime]
    lessons: List[LessonOut] = []

    class Config:
        orm_mode = True


# --------------------------------------------
# Student Schema
# --------------------------------------------
class StudentOut(BaseModel):
    id: int
    name: str
    cefr: Optional[str]
    group_name: Optional[str]
    lesson_day_1: int
    lesson_day_2: Optional[int]
    package_size: int
    start_date: date
    status: str

    packages: List[PackageOut] = []

    class Config:
        orm_mode = True


# --------------------------------------------
# Input Schema for Creating Students
# --------------------------------------------
class StudentCreate(BaseModel):
    name: str
    cefr: Optional[str] = None
    group_name: Optional[str] = None
    lesson_day_1: int
    lesson_day_2: Optional[int] = None  # <-- make optional properly
    package_size: int
    start_date: date

