from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union

import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException as HttpException

# --- your models & repos ---
from repo.sql_models import Base, Patient, LabResult, DoctorNote  # Visit, TestResult defined there as well
from repo.patient_repository import PatientRepository
from repo.test_repository import TestResultRepository
from routes.contracts import (
    PatientCreate, PatientUpdate,
    PatientResponse, PatientsListResponse,
    PatientSearchResponse, FilterCriteria,
    LabResultOut, DoctorNoteOut
)

# ----------------- DB bootstrap -----------------
DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)
Base.metadata.create_all(engine)

# ----------------- Helpers -----------------
_NUM_RE = re.compile(r"(\d+\.?\d*)")
_async_lock = asyncio.Lock()

def _parse_number(value, lo: float, hi: float) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        m = _NUM_RE.search(str(value))
        if not m:
            return None
        x = float(m.group(1))
    if not (lo <= x <= hi):
        return None
    return x

def _gen_patient_id(name: str) -> str:
    base = (name or "").lower().replace(" ", "")[:5] or "pt"
    return f"{base}{int(datetime.now().timestamp())}"

def _validate(data: Dict[str, Any]) -> Dict[str, str]:
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

    if "height" in data and _parse_number(data["height"], 0, 300) is None:
        errors["height"] = "Height must be a number between 0 and 300 (cm)"

    if "weight" in data and _parse_number(data["weight"], 0, 500) is None:
        errors["weight"] = "Weight must be a number between 0 and 500 (kg)"

    if "severity" in data:
        s = str(data["severity"]).strip()
        if s.lower() in {"low", "medium", "high"} or re.fullmatch(r"Stage [1-5]", s):
            pass
        else:
            errors["severity"] = f"Severity must be one of: low, medium, high, or Stage 1..5{s}"

    return errors

def _iso(dt: Optional[datetime | date]) -> Optional[str]:
    if not dt: return None
    # datetime/date both have isoformat()
    return dt.isoformat()

def _patient_to_api_dict(session: Session, p: Patient) -> Dict[str, Any]:
    prepo = PatientRepository(session)
    labs = sorted(prepo.list_lab_results(p.patient_id), key=lambda r: (r.result_date or date.min, r.lab_id))
    notes = sorted(prepo.list_doctor_notes(p.patient_id), key=lambda n: (n.note_date or date.min, n.note_id))

    latest_lr = LabResultOut.model_validate(labs[-1]) if labs else None
    latest_dn = DoctorNoteOut.model_validate(notes[-1]) if notes else None

    return {
        "patient_id": p.patient_id,
        "name": p.name or "",
        "birthDate": p.dob.isoformat() if p.dob else "",
        "height": str(p.height or 0),
        "weight": str(p.weight or 0),
        "doctors_notes": latest_dn,
        "severity": p.severity or "",
        "lab_results": latest_lr,
        "lab_results_history": [LabResultOut.model_validate(x) for x in labs],
        "doctors_notes_history": [DoctorNoteOut.model_validate(x) for x in notes],
    }
# Legacy public API (same names/signatures)
# =========================

from datetime import date, datetime
from typing import Union, Dict, Any, Optional

def create_patient(
    name: str,
    birthDate: Union[str, date],
    height: Optional[float],
    weight: Optional[float],
    lab_results: Optional[str],
    doctors_notes: str,
    severity: str,
) -> Dict[str, Any]:
    errs = _validate({
        "name": name,
        "birthDate": birthDate,
        "height": height,
        "weight": weight,
        "severity": severity,
    })
    if errs:
        return {"success": False, "errors": errs}

    try:
        dob = birthDate if isinstance(birthDate, date) else date.fromisoformat(str(birthDate))
    except Exception:
        return {"success": False, "error": "Invalid birthDate; expected YYYY-MM-DD"}

    h = _parse_number(height, 0, 300)
    w = _parse_number(weight, 0, 500)

    # coerce lab_results to a plain string value

    patient_id = _gen_patient_id(name)

    try:
        with SessionLocal() as session:
            prepo = PatientRepository(session)

            dbp = Patient(
                patient_id=patient_id,
                name=name,
                dob=dob,
                height=int(h) if h is not None else None,
                weight=int(w) if w is not None else None,
                severity=severity,
            )
            prepo.add(dbp)

            # first lab + first note rows
            prepo.add_lab_result(
                patient_id=patient_id,
                result_date=datetime.now(),  # was datetime.date()
                results=lab_results,
            )

            prepo.add_doctor_note(
                patient_id=patient_id,
                note_date=datetime.now(),
                note=doctors_notes,
                added_by="system",
            )

            return {"success": True, "patient_id": patient_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_patient_info(patient_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        prepo = PatientRepository(session)
        dbp = prepo.get(patient_id)
        if not dbp:
            return {"success": False, "error": "Patient not found"}
        return {"success": True, "patient": _patient_to_api_dict(session, dbp)}

def get_all_patients_info(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    with SessionLocal() as session:
        prepo = PatientRepository(session)
        rows = prepo.list(skip=skip, limit=limit)
        total = prepo.count()
        return {
            "success": True,
            "patients": [_patient_to_api_dict(session, r) for r in rows],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    

def _extract_lab_result_value(v: Any) -> Optional[str]:
    """Return only the textual value to persist into Visit.lab_result (Text)."""
    if v is None:
        return None
    if isinstance(v, dict):
        # Keep only the 'value' field if provided, otherwise stringify the dict
        return v.get("value", str(v))
    if isinstance(v, str):
        return v
    return str(v)

def update_patient_info(patient_id: str, updated_data: Dict[str, Any]) -> Dict[str, Any]:
    errs = _validate(updated_data)  # assumes your _validate handles partials
    if errs:
        return {"success": False, "errors": errs}

    with SessionLocal() as session:
        prepo = PatientRepository(session)

        dbp = prepo.get(patient_id)
        if not dbp:
            return {"success": False, "error": "Patient not found"}

        # --- Patch basic Patient columns ---
        changed = False
        if "name" in updated_data:
            dbp.name = updated_data["name"]; changed = True

        if "birthDate" in updated_data:
            bd = updated_data["birthDate"]
            dbp.dob = date.fromisoformat(bd) if bd else None
            changed = True

        if "height" in updated_data:
            h = _parse_number(updated_data["height"], 0, 300)
            dbp.height = int(h) if h is not None else None
            changed = True

        if "weight" in updated_data:
            w = _parse_number(updated_data["weight"], 0, 500)
            dbp.weight = int(w) if w is not None else None
            changed = True

        if changed:
            session.commit()

        # --- New Visit snapshot if any visit-scoped fields provided ---
        # Accept either 'lab_result' or 'lab_results' from caller
        lab_input = updated_data.get("lab_results")
        if lab_input is not None:
            lab_input = _extract_lab_result_value(lab_input)
            prepo.add_lab_result(
                patient_id=patient_id,
                result_date=datetime.now(),
                results= lab_input)
            
        if "doctors_notes" in updated_data:
            prepo.add_doctor_note(
                patient_id=patient_id,
                note_date=datetime.now(),
                note=updated_data["doctors_notes"][0]["note"],
                added_by="system",
            )


        
        return {"success": True, "patient_id": patient_id}

def delete_patient_record(patient_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        prepo = PatientRepository(session)
        ok = prepo.delete(patient_id)
        return {"success": ok} if ok else {"success": False, "error": "Patient not found"}

def search_patients(query: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        prepo = PatientRepository(session)
        # If your repo has search_by_name, use it; otherwise emulate:
        rows = prepo.filter(criteria=type("C", (), {"name": query, "min_age": None, "max_age": None})()) \
               if hasattr(prepo, "filter") else prepo.list()
        # If using .filter above returns List[Patient], keep it; otherwise, fallback name contains:
        if not hasattr(prepo, "filter"):
            rows = [p for p in rows if (p.name or "").lower().find(query.lower()) >= 0]
        return {"success": True, "patients": [_patient_to_api_dict(session, r) for r in rows], "count": len(rows)}

def filter_patients(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supports: name, min_age, max_age, severity (severity via latest visit.vitals_json).
    """
    with SessionLocal() as session:
        prepo = PatientRepository(session)

        # If your repo exposes a richer filter, prefer it:
        if hasattr(prepo, "filter_patients"):
            rows = prepo.filter_patients(
                name=criteria.get("name"),
                min_age=criteria.get("min_age"),
                max_age=criteria.get("max_age"),
                severity=criteria.get("severity"),
                skip=criteria.get("skip", 0),
                limit=criteria.get("limit", 100),
            )
        else:
            # Minimal fallback: list + name filter (age/severity omitted if repo lacks it)
            rows = prepo.list(skip=criteria.get("skip", 0), limit=criteria.get("limit", 100))
            if criteria.get("name"):
                q = criteria["name"].lower()
                rows = [p for p in rows if (p.name or "").lower().find(q) >= 0]



        return {"success": True, "patients": [_patient_to_api_dict(session, r) for r in rows], "count": len(rows)}

# ---------------- Async wrappers (same names) ----------------
async def async_create_patient(*args, **kwargs) -> Dict[str, Any]:
    async with _async_lock:
        return create_patient(*args, **kwargs)

async def async_get_patient_info(patient_id: str) -> Dict[str, Any]:
    async with _async_lock:
        return get_patient_info(patient_id)

async def async_get_all_patients_info(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    async with _async_lock:
        return get_all_patients_info(skip=skip, limit=limit)

async def async_update_patient_info(patient_id: str, updated_data: Dict[str, Any]) -> Dict[str, Any]:
    async with _async_lock:
        return update_patient_info(patient_id, updated_data)

async def async_delete_patient_record(patient_id: str) -> Dict[str, Any]:
    async with _async_lock:
        return delete_patient_record(patient_id)

async def async_search_patients(query: str) -> Dict[str, Any]:
    async with _async_lock:
        return search_patients(query)

async def async_filter_patients(criteria: Dict[str, Any]) -> Dict[str, Any]:
    async with _async_lock:
        return filter_patients(criteria)


# =========================
# TestHistoryManager refactor -> SQL TestResultRepository
# =========================
class TestHistoryManager:
    """
    Backed by TestResultRepository instead of a JSON file.
    """

    def __init__(self) -> None:
        pass

    def get_patient_tests(self, patient_id: str) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            trepo = TestResultRepository(session)
            results = trepo.get_by_patient(patient_id)
            out: List[Dict[str, Any]] = []
            for r in results:
                out.append({
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_name": r.test_name,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "recording_file": r.recording_file,
                    "frame_count": r.frame_count,
                    "keypoints": r.keypoints,
                })
            return out

    def add_patient_test(self, patient_id: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        with SessionLocal() as session:
            trepo = TestResultRepository(session)

            # parse date if sent as ISO string
            raw_dt = test_data.get("test_date")
            parsed_dt = None
            if raw_dt:
                parsed_dt = datetime.fromisoformat(raw_dt)

            from repo.sql_models import TestResult
            new_test = TestResult(
                patient_id=patient_id,
                test_name=test_data.get("test_name"),
                test_date=parsed_dt,
                recording_file=test_data.get("recording_file"),
                frame_count=test_data.get("frame_count"),
                keypoints=test_data.get("keypoints"),
            )
            new_test = trepo.add(new_test)
            return {"success": True, "test_id": new_test.test_id}

    def get_all_tests(self) -> Dict[str, List[Dict[str, Any]]]:
        with SessionLocal() as session:
            trepo = TestResultRepository(session)
            results = trepo.list()
            by_pid: Dict[str, List[Dict[str, Any]]] = {}
            for r in results:
                by_pid.setdefault(r.patient_id, []).append({
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_name": r.test_name,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "recording_file": r.recording_file,
                    "frame_count": r.frame_count,
                    "keypoints": r.keypoints,
                })
            return by_pid