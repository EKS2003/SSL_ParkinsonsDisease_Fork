from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    Date,
    DateTime,
    Text,
    ForeignKey,
    create_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

# ---------- Base ----------
class Base(DeclarativeBase):
    pass

# ---------- Patient Table ----------
class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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

# ---------- Visit Table ----------
class Visit(Base):
    __tablename__ = "visits"

    visit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    visit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lab_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="closed")

    patient: Mapped["Patient"] = relationship(back_populates="visits")

# ---------- TestResult Table ----------
class TestResult(Base):
    __tablename__ = "testresults"

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    test_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    keypoints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="testresults")

# ---------- Create Database ----------
if __name__ == "__main__":
    # Replace with your database URL (e.g., "sqlite:///patients.db" or PostgreSQL URL)
    engine = create_engine("sqlite:///patients.db", echo=True)

    # Create all tables
    Base.metadata.create_all(engine)

    # Optional: create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    print("✅ Tables created successfully!")
