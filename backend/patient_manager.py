# legacy_api_sql_refactor.py
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- your models & repos ---
from repo.sql_models import Base, Patient  # Visit, TestResult defined there as well
from repo.patient_repository import PatientRepository
from repo.visit_repository import VisitRepository
from repo.test_repository import TestResultRepository
from repo.sql_models import Visit

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

def _patient_to_api_dict(session: Session, p: Patient) -> Dict[str, Any]:
    vrepo = VisitRepository(session)
    visits = vrepo.list(patient_id= p.patient_id)  # or however you fetch visits
    latest = visits[-1] if visits else None
    vitals = (latest.vitals_json or {}) if latest else {}

    return {
        "patient_id": p.patient_id,
        "name": p.name or "",
        "birthDate": p.dob.isoformat() if p.dob else "",
        "height": str(p.height) if p.height is not None else "0",
        "weight": str(p.weight) if p.weight is not None else "0",
        "lab_results": vitals.get("lab_results", {}),
        "doctors_notes": (latest.doctor_notes if latest else "") or "",
        "severity": vitals.get("severity", "low"),
        "lab_results_history": [
            (v.vitals_json or {}).get("lab_results", {}) for v in visits
        ],
        # 🔧 return dicts, not strings
        "doctors_notes_history": [
            {
                "note": v.doctor_notes or "",
                "visit_id": v.visit_id,
                "visit_date": v.visit_date.isoformat() if v.visit_date else None,
            }
            for v in visits
        ],
    }
# =========================
# Legacy public API (same names/signatures)
# =========================

def create_patient(
    name: str,
    birthDate: Union[str, date],
    height: Optional[float],
    weight: Optional[float],
    lab_results: Dict[str, Any],
    doctors_notes: str,
    severity: str,
) -> Dict[str, Any]:
    # Validate basic inputs (reuses your helper)
    errs = _validate({
        "name": name,
        "birthDate": birthDate,
        "height": height,
        "weight": weight,
        "severity": severity,
    })
    if errs:
        return {"success": False, "errors": errs}

    # Coerce types
    try:
        dob = birthDate if isinstance(birthDate, date) else date.fromisoformat(str(birthDate))
    except Exception:
        return {"success": False, "error": "Invalid birthDate; expected YYYY-MM-DD"}

    h = _parse_number(height, 0, 300)
    w = _parse_number(weight, 0, 500)

    # Ensure lab_results is a dict
    if not isinstance(lab_results, dict):
        try:
            import json
            parsed = json.loads(str(lab_results))
            lab_results = parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            lab_results = {"value": lab_results}

    patient_id = _gen_patient_id(name)

    try:
        with SessionLocal() as session:
            prepo = PatientRepository(session)
            vrepo = VisitRepository(session)

            # Create patient row
            dbp = Patient(
                patient_id=patient_id,
                name=name,
                dob=dob,
                height=int(h) if h is not None else None,
                weight=int(w) if w is not None else None,
            )
            prepo.add(dbp)  # commits

            # First visit snapshot to carry legacy fields
            visit = Visit(
                patient_id=patient_id,
                visit_date=datetime.utcnow(),
                doctor_notes=doctors_notes or "",
                progression_note=None,
                vitals_json={"lab_results": lab_results or {}, "severity": severity},
                status="closed",
            )
            vrepo.add(visit)

            return {"success": True, "patient_id": patient_id}
    except Exception as e:
        # Surface DB/repo errors back to the caller rather than returning None
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

def update_patient_info(patient_id: str, updated_data: Dict[str, Any]) -> Dict[str, Any]:
    errs = _validate(updated_data)
    if errs:
        return {"success": False, "errors": errs}

    with SessionLocal() as session:
        prepo = PatientRepository(session)
        vrepo = VisitRepository(session)

        dbp = prepo.get(patient_id)
        if not dbp:
            return {"success": False, "error": "Patient not found"}

        # Basic Patient columns
        patch: Dict[str, Any] = {}
        if "name" in updated_data:
            patch["name"] = updated_data["name"]
        if "birthDate" in updated_data:
            bd = updated_data["birthDate"]
            patch["dob"] = date.fromisoformat(bd) if bd else None
        if "height" in updated_data:
            h = _parse_number(updated_data["height"], 0, 300)
            patch["height"] = int(h) if h is not None else None
        if "weight" in updated_data:
            w = _parse_number(updated_data["weight"], 0, 500)
            patch["weight"] = int(w) if w is not None else None

        if patch:
            prepo.update(patient_id, patch)

        # Legacy JSON fields -> append a new Visit snapshot
        if any(k in updated_data for k in ("doctors_notes", "lab_results", "severity")):
            vitals_payload: Dict[str, Any] = {}
            if "lab_results" in updated_data:
                vitals_payload["lab_results"] = updated_data["lab_results"]
            if "severity" in updated_data:
                vitals_payload["severity"] = updated_data["severity"]

            vrepo.add_visit(
                patient_id=patient_id,
                doctor_notes=updated_data.get("doctors_notes") or "",
                vitals_json=vitals_payload or None,
                status="closed",
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

            # severity filter using latest visit
            sev = criteria.get("severity")
            if sev is not None:
                vrepo = VisitRepository(session)
                keep: List[Patient] = []
                for p in rows:
                    latest = vrepo.latest_visit(p.patient_id)
                    if latest and latest.vitals_json and latest.vitals_json.get("severity") == sev:
                        keep.append(p)
                rows = keep

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
        pass  # no file-path needed

    def get_patient_tests(self, patient_id: str) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            trepo = TestResultRepository(session)
            results = trepo.list_test_results(patient_id)
            # Map to a simple dict similar to your old JSON structure
            out: List[Dict[str, Any]] = []
            for r in results:
                out.append({
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_type": r.test_type,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "keypoints": r.keypoints,  # raw JSON/text as stored
                })
            return out

    def add_patient_test(self, patient_id: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        with SessionLocal() as session:
            trepo = TestResultRepository(session)
            new_tr = trepo.add_test_result(
                patient_id=patient_id,
                test_type=test_data.get("test_type"),
                test_date=date.fromisoformat(test_data["test_date"]) if test_data.get("test_date") else None,
                keypoints=test_data.get("keypoints"),
            )
            return {
                "success": True,
                "test_id": new_tr.test_id,
            }

    def get_all_tests(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns {patient_id: [tests...]} for convenience.
        """
        with SessionLocal() as session:
            trepo = TestResultRepository(session)
            # If your repo has a list_all() use it, else query directly:
            results = trepo.list_all() if hasattr(trepo, "list_all") else session.query(trepo.model).all()
            by_pid: Dict[str, List[Dict[str, Any]]] = {}
            for r in results:
                by_pid.setdefault(r.patient_id, []).append({
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_type": r.test_type,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "keypoints": r.keypoints,
                })
            return by_pid
