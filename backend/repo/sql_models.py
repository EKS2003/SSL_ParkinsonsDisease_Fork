from datetime import date, datetime
from typing import List, Dict, Optional

from sqlalchemy import (
    String,
    Integer,
    Date,
    DateTime,
    Text,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import JSON

class Base(DeclarativeBase):
    pass

class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    visits: Mapped[List["Visit"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    testresults: Mapped[List["TestResult"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Visit(Base):
    __tablename__ = "visits"

    visit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    visit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    progression_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vitals_json: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="closed")

    # Reverse relationship to Patient
    patient: Mapped["Patient"] = relationship(back_populates="visits")

class TestResult(Base):
    __tablename__ = "testresults"

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    test_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    keypoints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reverse relationship to Patient
    patient: Mapped["Patient"] = relationship(back_populates="testresults")