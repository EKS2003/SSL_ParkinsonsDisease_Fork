# repo/patient_repository.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, and_, desc
from sqlalchemy.orm import Session

from repo.sql_models import Patient, Visit, TestResult

# Optional: align with your existing schema types if you have them
# from schema.patient_schema import PatientSearchResponse, FilterCriteria
# To avoid tight coupling here, we’ll type these as Dict/list where needed.


class PatientRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------------- Patient CRUD ----------------
    def get(self, patient_id: str) -> Optional[Patient]:
        return self.session.get(Patient, patient_id)

    def add(self, patient: Patient) -> Patient:
        self.session.add(patient)
        self.session.commit()
        return patient

    def update(self, patient_id: str, update_data: Dict[str, Any]) -> Optional[Patient]:
        patient = self.get(patient_id)
        if patient is None:
            return None
        for key, value in update_data.items():
            if hasattr(patient, key):
                setattr(patient, key, value)
        self.session.commit()
        return patient

    def delete(self, patient_id: str) -> bool:
        patient = self.get(patient_id)
        if patient is None:
            return False
        self.session.delete(patient)
        self.session.commit()
        return True

    def list(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        return (
            self.session.query(Patient)
            .order_by(Patient.name.asc().nulls_last())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.session.query(Patient).count()

    # ---------------- Visits ----------------
    def add_visit(
        self,
        patient_id: str,
        doctor_notes: Optional[str] = None,
        progression_note: Optional[str] = None,
        vitals_json: Optional[Dict[str, Any]] = None,
        status: str = "closed",
        visit_date: Optional[datetime] = None,
    ) -> Visit:
        v = Visit(
            patient_id=patient_id,
            visit_date=visit_date or datetime.utcnow(),
            doctor_notes=doctor_notes,
            progression_note=progression_note,
            vitals_json=vitals_json,
            status=status,
        )
        self.session.add(v)
        self.session.commit()
        return v

    def list_visits(self, patient_id: str) -> List[Visit]:
        return (
            self.session.query(Visit)
            .filter(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date.asc())
            .all()
        )

    def latest_visit(self, patient_id: str) -> Optional[Visit]:
        return (
            self.session.query(Visit)
            .filter(Visit.patient_id == patient_id)
            .order_by(Visit.visit_date.desc())
            .first()
        )

    # ---------------- Test Results ----------------
    def add_test_result(
        self,
        patient_id: str,
        test_type: Optional[str],
        test_date: Optional[date],
        keypoints: Optional[str],
    ) -> TestResult:
        t = TestResult(
            patient_id=patient_id,
            test_type=test_type,
            test_date=test_date,
            keypoints=keypoints,
        )
        self.session.add(t)
        self.session.commit()
        return t

    def list_test_results(self, patient_id: str) -> List[TestResult]:
        return (
            self.session.query(TestResult)
            .filter(TestResult.patient_id == patient_id)
            .order_by(TestResult.test_date.asc().nulls_last())
            .all()
        )

    # ---------------- Search & Filter ----------------
    def search_by_name(self, query_str: str) -> List[Patient]:
        like = f"%{query_str}%"
        return (
            self.session.query(Patient)
            .filter(Patient.name.ilike(like))
            .order_by(Patient.name.asc())
            .all()
        )

    def filter_patients(
        self,
        name: Optional[str] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        severity: Optional[str] = None,  # lives in latest Visit.vitals_json["severity"]
        skip: int = 0,
        limit: int = 100,
    ) -> List[Patient]:
        """
        Note: severity is derived from the latest Visit per patient. We implement that
        by first selecting candidate patients, then post-filtering by latest visit.
        This keeps SQL portable and simple.
        """
        q = self.session.query(Patient)

        if name:
            q = q.filter(Patient.name.ilike(f"%{name}%"))

        # Age filters based on dob
        today = date.today()
        if min_age is not None:
            cutoff = today - timedelta(days=int(min_age * 365.25))
            q = q.filter(Patient.dob <= cutoff)
        if max_age is not None:
            cutoff = today - timedelta(days=int(max_age * 365.25))
            q = q.filter(Patient.dob >= cutoff)

        candidates = (
            q.order_by(Patient.name.asc().nulls_last())
            .offset(skip)
            .limit(limit)
            .all()
        )

        if severity is None:
            return candidates

        # Post-filter by latest visit severity
        filtered: List[Patient] = []
        for p in candidates:
            latest = self.latest_visit(p.patient_id)
            sev = None
            if latest and latest.vitals_json:
                sev = latest.vitals_json.get("severity")
            if sev == severity:
                filtered.append(p)
        return filtered
