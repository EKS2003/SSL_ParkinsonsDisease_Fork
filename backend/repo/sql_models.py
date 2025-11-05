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
    dob: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # keep Date if you truly want date-only
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Correct relationships
    labresults: Mapped[List["LabResult"]] = relationship(
        "LabResult", back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )
    doctornotes: Mapped[List["DoctorNote"]] = relationship(
        "DoctorNote", back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )
    testresults: Mapped[List["TestResult"]] = relationship(
        "TestResult", back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )

class LabResult(Base):
    __tablename__ = "labresults"

    lab_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    result_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # was Date
    results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="labresults")

class DoctorNote(Base):
    __tablename__ = "doctornotes"

    note_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )
    note_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # was Date
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="doctornotes")

class TestResult(Base):
    __tablename__ = "testresults"

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False
    )

    # from JSON
    test_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "stand-and-sit"
    test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recording_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    frame_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="testresults")

if __name__ == "__main__":
    engine = create_engine("sqlite:///patients.db", echo=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    print("✅ Tables created successfully!")