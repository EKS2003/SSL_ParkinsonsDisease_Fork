from __future__ import annotations

import re
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from repo.sql_models import Patient, LabResult, DoctorNote
from repo.patient_repository import PatientRepository
from routes.contracts import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    LabResultOut,
    DoctorNoteOut,
)
from core.exceptions import PatientNotFoundError, PatientValidationError

_NUM_RE = re.compile(r"(\d+\.?\d*)")

_TEST_NAME_ALIASES: dict[str, str] = {
    "stand-and-sit": "stand-and-sit",
    "stand-sit": "stand-and-sit",
    "stand_to_sit": "stand-and-sit",
    "stand-and-sit-assessment": "stand-and-sit",
    "stand-and-sit-test": "stand-and-sit",
    "stand-&-sit": "stand-and-sit",
    "stand-&-sit-assessment": "stand-and-sit",
    "stand-and-sit-evaluation": "stand-and-sit",
    "finger-tapping": "finger-tapping",
    "finger_tapping": "finger-tapping",
    "finger-taping": "finger-tapping",
    "finger-tapping-test": "finger-tapping",
    "finger-tapping-assessment": "finger-tapping",
    "finger-tap": "finger-tapping",
    "fist-open-close": "fist-open-close",
    "fist_open_close": "fist-open-close",
    "fist-open-close-test": "fist-open-close",
    "fist-open-close-assessment": "fist-open-close",
    "palm-open": "fist-open-close",
    "palm_open": "fist-open-close",
}


def _parse_number(value: Any, lo: float, hi: float) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        m = _NUM_RE.search(str(value))
        if not m:
            return None
        x = float(m.group(1))
    return x if lo <= x <= hi else None


def _gen_patient_id(name: str) -> str:
    base = (name or "").lower().replace(" ", "")[:5] or "pt"
    return f"{base}{uuid.uuid4().hex[:8]}"


def normalize_severity(value: str) -> str:
    if not value:
        return "Stage 1"
    normalized = value.strip().lower()
    stage_map = {
        "stage 1": "Stage 1",
        "stage 2": "Stage 2",
        "stage 3": "Stage 3",
        "stage 4": "Stage 4",
        "stage 5": "Stage 5",
    }
    if normalized in stage_map:
        return stage_map[normalized]
    legacy_map = {
        "low": "Stage 1",
        "mild": "Stage 2",
        "medium": "Stage 3",
        "moderate": "Stage 3",
        "high": "Stage 4",
        "severe": "Stage 5",
    }
    return legacy_map.get(normalized, "Stage 1")


def normalize_test_name(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "unknown"
    normalized = normalized.replace(" ", "-").replace("_", "-").replace("&", "and")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return _TEST_NAME_ALIASES.get(normalized, normalized)


class PatientService:
    def __init__(self, repo: PatientRepository, db: Session) -> None:
        self.repo = repo
        self.db = db

    def _validate(self, data: Dict[str, Any]) -> Dict[str, str]:
        errors: Dict[str, str] = {}

        if "name" in data and data["name"] is not None and not isinstance(data["name"], str):
            errors["name"] = "Name must be a string"

        if "birthDate" in data:
            bd = data["birthDate"]
            if bd:
                try:
                    date.fromisoformat(str(bd))
                except Exception:
                    errors["birthDate"] = "birthDate must be YYYY-MM-DD"

        if "height" in data and data["height"] is not None and _parse_number(data["height"], 0, 300) is None:
            errors["height"] = "Height must be a number between 0 and 300 (cm)"

        if "weight" in data and data["weight"] is not None and _parse_number(data["weight"], 0, 500) is None:
            errors["weight"] = "Weight must be a number between 0 and 500 (kg)"

        if "severity" in data:
            s = str(data["severity"]).strip()
            if not (s.lower() in {"low", "medium", "high"} or re.fullmatch(r"Stage [1-5]", s)):
                errors["severity"] = "Severity must be low, medium, high, or Stage 1-5"

        return errors

    def _to_response(self, p: Patient) -> PatientResponse:
        labs = sorted(
            self.repo.list_lab_results(p.patient_id),
            key=lambda r: (r.result_date or date.min, r.lab_id),
        )
        notes = sorted(
            self.repo.list_doctor_notes(p.patient_id),
            key=lambda n: (n.note_date or date.min, n.note_id),
        )
        return PatientResponse(
            patient_id=p.patient_id,
            name=p.name or "",
            birthDate=p.dob,
            height=str(p.height or 0),
            weight=str(p.weight or 0),
            severity=p.severity or "",
            latest_lab_result=LabResultOut.model_validate(labs[-1]) if labs else None,
            latest_doctor_note=DoctorNoteOut.model_validate(notes[-1]) if notes else None,
            lab_results_history=[LabResultOut.model_validate(x) for x in labs],
            doctors_notes_history=[DoctorNoteOut.model_validate(x) for x in notes],
        )

    def create_patient(self, user_id: int, data: PatientCreate) -> str:
        errs = self._validate({
            "birthDate": data.birthDate,
            "height": data.height,
            "weight": data.weight,
            "severity": data.severity,
        })
        if errs:
            raise PatientValidationError(errs)

        dob = data.birthDate if isinstance(data.birthDate, date) else date.fromisoformat(str(data.birthDate))
        h = _parse_number(data.height, 0, 300)
        w = _parse_number(data.weight, 0, 500)
        patient_id = _gen_patient_id(data.name)

        dbp = Patient(
            patient_id=patient_id,
            user_id=user_id,
            name=data.name,
            dob=dob,
            height=int(h) if h is not None else None,
            weight=int(w) if w is not None else None,
            severity=data.severity,
        )
        self.repo.add(dbp)

        for lr in data.lab_results_history or []:
            self.repo.add_lab_result(
                lab_id=lr.id,
                patient_id=patient_id,
                result_date=lr.date or datetime.now(),
                results=lr.results or "",
                added_by=lr.added_by or "system",
            )

        for dn in data.doctors_notes_history or []:
            self.repo.add_doctor_note(
                note_id=dn.id,
                patient_id=patient_id,
                note_date=dn.date or datetime.now(),
                note=dn.note or "",
                added_by=dn.added_by or "system",
            )

        return patient_id

    def get_patient(self, patient_id: str) -> PatientResponse:
        p = self.repo.get(patient_id)
        if not p:
            raise PatientNotFoundError(patient_id)
        return self._to_response(p)

    def list_patients(self, skip: int = 0, limit: int = 100) -> dict:
        rows = self.repo.list(skip=skip, limit=limit)
        total = self.repo.count()
        return {
            "patients": [self._to_response(r) for r in rows],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_patient(self, patient_id: str, data: PatientUpdate) -> None:
        raw = data.model_dump(exclude_unset=True)
        errs = self._validate(raw)
        if errs:
            raise PatientValidationError(errs)

        dbp = self.repo.get(patient_id)
        if not dbp:
            raise PatientNotFoundError(patient_id)

        if "name" in raw:
            dbp.name = raw["name"]
        if "birthDate" in raw:
            dbp.dob = raw["birthDate"]
        if "height" in raw:
            h = _parse_number(raw["height"], 0, 300)
            dbp.height = int(h) if h is not None else None
        if "weight" in raw:
            w = _parse_number(raw["weight"], 0, 500)
            dbp.weight = int(w) if w is not None else None
        if "severity" in raw:
            dbp.severity = raw["severity"]

        if data.lab_results is not None:
            lr = data.lab_results
            self.repo.add_lab_result(
                lab_id=lr.id,
                patient_id=patient_id,
                result_date=lr.date or datetime.now(),
                results=lr.results or "",
                added_by=lr.added_by or "system",
            )

        if data.doctors_notes is not None:
            dn = data.doctors_notes
            self.repo.add_doctor_note(
                note_id=dn.id,
                patient_id=patient_id,
                note_date=dn.date or datetime.now(),
                note=dn.note or "",
                added_by=dn.added_by or "system",
            )

        self.db.commit()

    def delete_patient(self, patient_id: str) -> None:
        ok = self.repo.delete(patient_id)
        if not ok:
            raise PatientNotFoundError(patient_id)

    def search_patients(self, query: str) -> list[PatientResponse]:
        rows = self.repo.search_by_name(query)
        return [self._to_response(r) for r in rows]

    def filter_patients(self, criteria: dict) -> list[PatientResponse]:
        rows = self.repo.filter_patients(
            name=criteria.get("name"),
            min_age=criteria.get("min_age"),
            max_age=criteria.get("max_age"),
            severity=criteria.get("severity"),
            skip=criteria.get("skip", 0),
            limit=criteria.get("limit", 100),
        )
        return [self._to_response(r) for r in rows]
