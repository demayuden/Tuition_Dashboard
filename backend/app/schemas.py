# backend/app/schemas.py
from pydantic import BaseModel
from datetime import date, datetime
from typing import List, Optional

# --------------------------------------------
# Lesson Schema
# --------------------------------------------
class LessonOut(BaseModel):
    lesson_id: int
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
    package_id: int
    package_size: int
    payment_status: bool
    first_lesson_date: Optional[date]
    created_at: Optional[datetime]
    lessons: List[LessonOut] = []

    class Config:
        orm_mode = True


# --------------------------------------------
# Student Schema
# --------------------------------------------
class StudentOut(BaseModel):
    student_id: int
    name: str
    cefr: Optional[str]
    group_name: Optional[str]
    lesson_day_1: int
    lesson_day_2: Optional[int]
    package_size: int
    start_date: date
    end_date: Optional[date]  
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
    lesson_day_2: Optional[int] = None
    package_size: int
    start_date: date
    end_date: Optional[date] = None  

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    cefr: Optional[str] = None
    group_name: Optional[str] = None
    lesson_day_1: Optional[int] = None
    lesson_day_2: Optional[int] = None
    package_size: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None  
    status: Optional[str] = None