from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    cefr = Column(String, nullable=True)
    group_name = Column(String, nullable=True)

    # 0=Mon, 1=Tue, ..., 6=Sun
    lesson_day_1 = Column(Integer, nullable=False)
    lesson_day_2 = Column(Integer, nullable=True)

    package_size = Column(Integer, nullable=False)  # 4 or 8
    start_date = Column(Date, nullable=False)

    status = Column(String, default="active")

    # Relationships
    packages = relationship("Package", back_populates="student", cascade="all, delete-orphan")


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    package_size = Column(Integer, nullable=False)  # 4 or 8
    payment_status = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    student = relationship("Student", back_populates="packages")
    lessons = relationship("Lesson", back_populates="package", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)

    lesson_number = Column(Integer, nullable=False)   # 1..4 or 1..8
    lesson_date = Column(Date, nullable=False)

    is_first = Column(Boolean, default=False)
    is_manual_override = Column(Boolean, default=False)

    package = relationship("Package", back_populates="lessons")

    __table_args__ = (
        UniqueConstraint('package_id', 'lesson_number', name='unique_lesson_per_package'),
    )


class Closure(Base):
    __tablename__ = "closures"

    id = Column(Integer, primary_key=True, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    type = Column(String, nullable=True)
