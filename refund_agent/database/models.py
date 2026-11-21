from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    String,
    Integer,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Numeric
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from refund_agent.database.connection import Base


# 1. Student Model
class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)

    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="student"
    )

    refund_requests: Mapped[list[RefundRequest]] = relationship(
        back_populates="student"
    )


# 2. Course Model
class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course"
    )


# 3. Enrollment Model
class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id")
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id")
    )

    purchase_date: Mapped[date] = mapped_column(Date)

    completion_percentage: Mapped[float] = mapped_column(Float)

    student: Mapped[Student] = relationship(
        back_populates="enrollments"
    )

    course: Mapped[Course] = relationship(
        back_populates="enrollments"
    )

    refund_requests: Mapped[list[RefundRequest]] = relationship(
        back_populates="enrollment"
    )


# 4. Refund Request Model
class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id")
    )

    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id")
    )

    reason: Mapped[str] = mapped_column(String(500))

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    student: Mapped[Student] = relationship(
        back_populates="refund_requests"
    )

    enrollment: Mapped[Enrollment] = relationship(
        back_populates="refund_requests"
    )
