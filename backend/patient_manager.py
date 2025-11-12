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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import threading
import copy
from uuid import uuid4
_TEST_NAME_ALIASES = {
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


def _normalize_test_name(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "unknown"
    normalized = normalized.replace(" ", "-").replace("_", "-").replace("&", "and")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return _TEST_NAME_ALIASES.get(normalized, normalized)


def normalize_severity(value: str) -> str:
    """Map various severity descriptors to a canonical Stage 1-5 label."""
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

TEST_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'test_history.json')

class Patient:
    def __init__(self,
                 name: str,
                 birthDate: str,
                 height: float,
                 weight: float,
                 severity: str = "low",
                 patient_id: str = None,
                 lab_results_history: Optional[List[Dict]] = None,
                 doctors_notes_history: Optional[List[Dict]] = None):
        self.name = name
        self.birthDate = birthDate
        self.height = height  # in cm
        self.weight = weight  # in kg
        self.severity = normalize_severity(severity)
        self.patient_id = patient_id or self._generate_id()
        self.lab_results_history = self._normalize_lab_history_entries(lab_results_history or [])
        self.doctors_notes_history = self._normalize_doctor_notes_history_entries(doctors_notes_history or [])

    @staticmethod
    def _normalize_date_value(value: Union[str, datetime, None]) -> str:
        """Return an ISO-8601 string for the provided value."""
        if isinstance(value, datetime):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.isoformat()
            except ValueError:
                return value
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    @staticmethod
    def _normalize_lab_history_entries(entries: List[Dict]) -> List[Dict]:
        normalized: List[Dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized.append({
                "id": str(entry.get("id") or f"lab_{uuid4().hex[:12]}").strip(),
                "date": Patient._normalize_date_value(entry.get("date")),
                "results": str(entry.get("results") or entry.get("result") or ""),
                "added_by": (entry.get("added_by") or entry.get("addedBy") or "Unknown").strip() or "Unknown"
            })
        return normalized

    @staticmethod
    def _normalize_doctor_notes_history_entries(entries: List[Dict]) -> List[Dict]:
        normalized: List[Dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized.append({
                "id": str(entry.get("id") or f"note_{uuid4().hex[:12]}").strip(),
                "date": Patient._normalize_date_value(entry.get("date")),
                "note": str(entry.get("note") or entry.get("notes") or ""),
                "added_by": (entry.get("added_by") or entry.get("addedBy") or "Unknown").strip() or "Unknown"
            })
        return normalized

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

    def latest_lab_result(self) -> Optional[Dict]:
        if not self.lab_results_history:
            return None
        latest = max(self.lab_results_history, key=lambda entry: self._parse_iso_datetime(entry.get("date")))
        return copy.deepcopy(latest)

    def latest_doctor_note(self) -> Optional[Dict]:
        if not self.doctors_notes_history:
            return None
        latest = max(self.doctors_notes_history, key=lambda entry: self._parse_iso_datetime(entry.get("date")))
        return copy.deepcopy(latest)

    def _generate_id(self) -> str:
        """Generate a unique ID for the patient based on name and current timestamp"""
        name_part = self.name.lower().replace(" ", "")[:5]
        time_part = str(int(datetime.now().timestamp()))
        return f"{name_part}{time_part}"

    def to_dict(self) -> Dict:
        """Convert patient object to dictionary for JSON serialization"""
        lab_history = [dict(entry) for entry in self.lab_results_history]
        note_history = [dict(entry) for entry in self.doctors_notes_history]
        latest_lab = self.latest_lab_result()
        latest_note = self.latest_doctor_note()
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "birthDate": self.birthDate,
            "height": str(self.height),  # Convert to string for API response
            "weight": str(self.weight),  # Convert to string for API response
            "severity": self.severity,
            "lab_results_history": lab_history,
            "doctors_notes_history": note_history,
            "latest_lab_result": latest_lab,
            "latest_doctor_note": latest_note
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Patient':
        """Create a Patient object from dictionary data"""
        # Handle height conversion from string to float
        height_raw = data.get("height", 0.0)
        if isinstance(height_raw, str):
            # Try to extract numeric value from strings like "5'8"" or "170 cm"
            try:
                # Remove common units and extract numbers
                height_str = str(height_raw).replace("'", "").replace('"', "").replace("cm", "").replace("lbs", "").strip()
                height = float(height_str) if height_str else 0.0
            except ValueError:
                height = 0.0
        else:
            height = float(height_raw) if height_raw is not None else 0.0
        
        # Handle weight conversion from string to float
        weight_raw = data.get("weight", 0.0)
        if isinstance(weight_raw, str):
            # Try to extract numeric value from strings like "145 lbs" or "70 kg"
            try:
                # Remove common units and extract numbers
                weight_str = str(weight_raw).replace("lbs", "").replace("kg", "").strip()
                weight = float(weight_str) if weight_str else 0.0
            except ValueError:
                weight = 0.0
        else:
            weight = float(weight_raw) if weight_raw is not None else 0.0
        
        lab_history = data.get("lab_results_history", []) or []
        note_history = data.get("doctors_notes_history", []) or []

        legacy_lab = data.get("lab_results")
        if legacy_lab:
            lab_history = cls._merge_legacy_lab_results(lab_history, legacy_lab, data)

        legacy_notes = data.get("doctors_notes")
        if legacy_notes:
            note_history = cls._merge_legacy_doctor_notes(note_history, legacy_notes, data)

        return cls(
            patient_id=data.get("patient_id"),
            name=data.get("name", ""),
            birthDate=data.get("birthDate", ""),
            height=height,
            weight=weight,
            severity=normalize_severity(data.get("severity", "Stage 1")),
            lab_results_history=lab_history,
            doctors_notes_history=note_history
        )

    @staticmethod
    def _merge_legacy_lab_results(history: List[Dict], legacy_value: Union[Dict, str], data: Dict) -> List[Dict]:
        history_copy = list(history or [])
        if isinstance(legacy_value, dict) and not legacy_value:
            return history_copy
        if isinstance(legacy_value, str) and not legacy_value.strip():
            return history_copy

        legacy_id = f"legacy_lab_{data.get('patient_id', 'unknown')}"
        if any(entry.get("id") == legacy_id for entry in history_copy):
            return history_copy

        if isinstance(legacy_value, dict):
            results_value = json.dumps(legacy_value, indent=2)
        else:
            results_value = str(legacy_value)

        if not results_value.strip():
            return history_copy

        history_copy.append({
            "id": legacy_id,
            "date": Patient._normalize_date_value(data.get("last_lab_update")),
            "results": results_value,
            "added_by": data.get("last_updated_by", "Legacy Import")
        })
        return history_copy

    @staticmethod
    def _merge_legacy_doctor_notes(history: List[Dict], legacy_value: str, data: Dict) -> List[Dict]:
        history_copy = list(history or [])
        if not legacy_value or not str(legacy_value).strip():
            return history_copy

        legacy_id = f"legacy_note_{data.get('patient_id', 'unknown')}"
        if any(entry.get("id") == legacy_id for entry in history_copy):
            return history_copy

        history_copy.append({
            "id": legacy_id,
            "date": Patient._normalize_date_value(data.get("last_doctor_note_date")),
            "note": str(legacy_value),
            "added_by": data.get("last_updated_by", "Legacy Import")
        })
        return history_copy


#Refacto to sqlite
class PatientManager:
    # Class lock for async operations
    _lock = asyncio.Lock()

    def __init__(self, file_path: str = "patients.json", verbose: bool = False):
        self.file_path = file_path
        self.patients: Dict[str, Patient] = {}
        self.verbose = verbose
        self._load_patients()

    def _log(self, message: str) -> None:
        """Log a message if verbose mode is enabled"""
        if self.verbose:
            print(message)

    def _load_patients(self) -> None:
        """Load patients from the JSON file if it exists"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    patients_data = json.load(f)

                for patient_id, patient_data in patients_data.items():
                    self.patients[patient_id] = Patient.from_dict(patient_data)

                self._log(f"Loaded {len(self.patients)} patients from {self.file_path}")
            except Exception as e:
                self._log(f"Error loading patients: {str(e)}")
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
    _lock = threading.Lock()

    _TEST_LABELS = {
        "finger-tapping": "Finger Tapping Test",
        "fist-open-close": "Fist Open and Close Test",
        "stand-and-sit": "Stand and Sit Test",
    }

    _STATUS_INDICATORS = {
        "completed": {
            "color": "success",
            "label": "Completed",
            "description": "Recording captured successfully.",
        },
        "in-progress": {
            "color": "warning",
            "label": "In Progress",
            "description": "Test recording underway; results may be incomplete.",
        },
        "pending": {
            "color": "muted",
            "label": "Pending",
            "description": "Test scheduled but no recording stored yet.",
        },
    }

    def __init__(self, file_path: str = TEST_HISTORY_FILE):
        self.file_path = file_path
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def _save(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def _default_display_name(self, test_name: str) -> str:
        if not test_name:
            return "Unknown Test"
        if test_name in self._TEST_LABELS:
            return self._TEST_LABELS[test_name]
        return test_name.replace("-", " ").title()

    def _normalize_indicator(self, status: str, indicator: Optional[Dict[str, Any]]) -> Dict[str, str]:
        status_key = (status or "").strip().lower() or "pending"
        base = self._STATUS_INDICATORS.get(status_key, self._STATUS_INDICATORS["pending"]).copy()
        if not indicator or not isinstance(indicator, dict):
            return base
        merged = base
        if "color" in indicator:
            merged["color"] = str(indicator["color"]) or base["color"]
        if "label" in indicator:
            merged["label"] = str(indicator["label"]) or base["label"]
        if "description" in indicator:
            merged["description"] = str(indicator["description"]) or base["description"]
        return merged

    def _normalize_entry(self, patient_id: str, raw_entry: Dict[str, Any]) -> Dict[str, Any]:
        entry = dict(raw_entry or {})

        test_name_raw = entry.get("test_name") or entry.get("name") or entry.get("test") or ""
        normalized_test_name = _normalize_test_name(test_name_raw)
        entry["test_name"] = normalized_test_name
        entry["display_name"] = entry.get("display_name") or self._default_display_name(normalized_test_name)
        entry["patient_id"] = patient_id

        entry["date"] = Patient._normalize_date_value(entry.get("date"))

        recording_file = entry.get("recording_file") or entry.get("recording")
        if recording_file:
            base_file = os.path.basename(str(recording_file))
            entry["recording_file"] = base_file
            entry.setdefault("recording_url", f"/recordings/{base_file}")

        existing_id = entry.get("test_id") or entry.get("id")
        if existing_id:
            token = str(existing_id)
        else:
            candidate = entry.get("recording_file") or entry.get("session_id") or entry.get("date")
            if candidate:
                token = os.path.splitext(os.path.basename(str(candidate)))[0]
            else:
                token = uuid4().hex[:12]
        if not token.startswith(normalized_test_name):
            token = f"{normalized_test_name}-{token}"
        entry["test_id"] = token
        entry["id"] = token

        status_raw = (entry.get("status") or "").strip().lower()
        if not status_raw:
            status_raw = "completed" if entry.get("recording_file") else "pending"
        if status_raw not in self._STATUS_INDICATORS:
            status_raw = "pending"
        entry["status"] = status_raw
        entry["indicator"] = self._normalize_indicator(status_raw, entry.get("indicator"))

        frame_count = entry.get("frame_count")
        try:
            entry["frame_count"] = int(frame_count) if frame_count is not None else None
        except (TypeError, ValueError):
            entry["frame_count"] = None

        fps_value = entry.get("fps")
        try:
            entry["fps"] = float(fps_value) if fps_value is not None else None
        except (TypeError, ValueError):
            entry["fps"] = None

        dtw_data = entry.get("dtw")
        if isinstance(dtw_data, dict):
            dtw_clean = {
                "distance": float(dtw_data.get("distance")) if dtw_data.get("distance") is not None else None,
                "avg_step_cost": float(dtw_data.get("avg_step_cost")) if dtw_data.get("avg_step_cost") is not None else None,
                "similarity": float(dtw_data.get("similarity")) if dtw_data.get("similarity") is not None else None,
                "session_id": dtw_data.get("session_id"),
                "artifacts_dir": dtw_data.get("artifacts_dir") or dtw_data.get("artifacts"),
            }
            entry["dtw"] = dtw_clean
        else:
            entry["dtw"] = None

        summary_available = entry.get("summary_available")
        if summary_available is None:
            entry["summary_available"] = bool(entry.get("recording_file"))
        else:
            entry["summary_available"] = bool(summary_available)

        return entry

    def get_patient_tests(self, patient_id: str):
        with self._lock:
            self._load()
            raw_entries = self.data.get(patient_id, [])
            normalized_entries = [self._normalize_entry(patient_id, entry) for entry in raw_entries]
            normalized_entries.sort(key=lambda item: Patient._parse_iso_datetime(item.get("date")), reverse=True)
            if raw_entries != normalized_entries:
                self.data[patient_id] = [dict(entry) for entry in normalized_entries]
                self._save()
            return normalized_entries

    def add_patient_test(self, patient_id: str, test_data: dict):
        with self._lock:
            self._load()
            normalized_entry = self._normalize_entry(patient_id, test_data)
            patient_tests = self.data.setdefault(patient_id, [])
            patient_tests.append(dict(normalized_entry))
            self._save()
            return normalized_entry

    def get_all_tests(self):
        with self._lock:
            self._load()
            changed = False
            all_tests: Dict[str, List[Dict]] = {}
            for pid, entries in self.data.items():
                normalized = [self._normalize_entry(pid, entry) for entry in entries]
                normalized.sort(key=lambda item: Patient._parse_iso_datetime(item.get("date")), reverse=True)
                all_tests[pid] = normalized
                if entries != normalized:
                    self.data[pid] = [dict(entry) for entry in normalized]
                    changed = True
            if changed:
                self._save()
            return all_tests
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