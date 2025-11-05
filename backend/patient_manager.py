import json
import os
import asyncio
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
            self._log(f"No patients file found at {self.file_path}. Starting with empty database.")

    def _backup_patients(self) -> bool:
        """Create a backup of the patients file before making changes"""
        if os.path.exists(self.file_path):
            backup_path = f"{self.file_path}.backup"
            try:
                with open(self.file_path, 'r') as src:
                    with open(backup_path, 'w') as dst:
                        dst.write(src.read())
                return True
            except Exception as e:
                self._log(f"Error creating backup: {str(e)}")
        return False

    def _restore_backup(self) -> bool:
        """Restore the patients file from backup if an operation fails"""
        backup_path = f"{self.file_path}.backup"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r') as src:
                    with open(self.file_path, 'w') as dst:
                        dst.write(src.read())
                return True
            except Exception as e:
                self._log(f"Error restoring backup: {str(e)}")
        return False

    def save_patients(self) -> bool:
        """Save all patients to the JSON file with backup support"""
        self._backup_patients()
        patients_data = {patient_id: patient.to_dict()
                         for patient_id, patient in self.patients.items()}

        try:
            with open(self.file_path, 'w') as f:
                json.dump(patients_data, f, indent=2)
            self._log(f"Saved {len(self.patients)} patients to {self.file_path}")
            return True
        except Exception as e:
            self._log(f"Error saving patients: {str(e)}")
            self._restore_backup()
            return False

    def validate_patient_data(self, data: Dict) -> Dict:
        """Validate patient data and return any errors"""
        errors = {}

        if "name" in data and not isinstance(data["name"], str):
            errors["name"] = "Name must be a string"

        if "age" in data:
            if not isinstance(data["age"], int):
                errors["age"] = "Age must be an integer"
            elif data["age"] < 0 or data["age"] > 120:
                errors["age"] = "Age must be between 0 and 120"

        if "height" in data:
            # Handle both string and numeric inputs
            height_value = data["height"]
            if isinstance(height_value, str):
                # Try to convert string to float
                try:
                    # Extract numeric part from string (e.g., "170.0 cm" -> 170.0)
                    import re
                    numeric_match = re.search(r'(\d+\.?\d*)', height_value)
                    if numeric_match:
                        height_value = float(numeric_match.group(1))
                    else:
                        errors["height"] = "Height must contain a valid number"
                        height_value = None
                except ValueError:
                    errors["height"] = "Height must be a valid number"
                    height_value = None
            elif not isinstance(height_value, (int, float)):
                errors["height"] = "Height must be a number"
                height_value = None
            
            if height_value is not None and (height_value < 0 or height_value > 300):
                errors["height"] = "Height must be between 0 and 300 cm"

        if "weight" in data:
            # Handle both string and numeric inputs
            weight_value = data["weight"]
            if isinstance(weight_value, str):
                # Try to convert string to float
                try:
                    # Extract numeric part from string (e.g., "70.0 kg" -> 70.0)
                    import re
                    numeric_match = re.search(r'(\d+\.?\d*)', weight_value)
                    if numeric_match:
                        weight_value = float(numeric_match.group(1))
                    else:
                        errors["weight"] = "Weight must contain a valid number"
                        weight_value = None
                except ValueError:
                    errors["weight"] = "Weight must be a valid number"
                    weight_value = None
            elif not isinstance(weight_value, (int, float)):
                errors["weight"] = "Weight must be a number"
                weight_value = None
            
            if weight_value is not None and (weight_value < 0 or weight_value > 500):
                errors["weight"] = "Weight must be between 0 and 500 kg"

        if "severity" in data:
            severity_norm = (str(data["severity"]) or "").strip().lower()
            allowed = {"low", "medium", "high", "mild", "moderate", "severe",
                       "stage 1", "stage 2", "stage 3", "stage 4", "stage 5"}
            if severity_norm not in allowed:
                errors["severity"] = "Severity must be one of: Stage 1-5 (or legacy mild/moderate/severe)"
            elif "severity" not in errors:
                data["severity"] = normalize_severity(data["severity"])

        return errors

    def add_patient(self, patient: Patient) -> Dict:
        """Add a new patient or update an existing one"""
        try:
            self.patients[patient.patient_id] = patient
            success = self.save_patients()
            if success:
                return {"success": True, "patient_id": patient.patient_id}
            else:
                return {"success": False, "error": "Failed to save patient data"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Get a patient by ID"""
        return self.patients.get(patient_id)

    def get_all_patients(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """
        Get all patients with pagination support

        Args:
            skip: Number of patients to skip
            limit: Maximum number of patients to return

        Returns:
            List of Patient objects
        """
        all_patients = list(self.patients.values())
        return all_patients[skip:skip + limit]

    def count_patients(self) -> int:
        """Return the total number of patients"""
        return len(self.patients)

    def delete_patient(self, patient_id: str) -> Dict:
        """Delete a patient by ID"""
        if patient_id in self.patients:
            try:
                del self.patients[patient_id]
                success = self.save_patients()
                if success:
                    return {"success": True}
                else:
                    return {"success": False, "error": "Failed to save changes"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Patient not found"}

    def update_patient(self, patient_id: str, updated_data: Dict) -> Dict:
        """Update a patient's information"""
        print(f"Updating patient {patient_id} with data: {updated_data}")
        
        patient = self.get_patient(patient_id)
        if not patient:
            print(f"Patient {patient_id} not found")
            return {"success": False, "error": "Patient not found"}

        print(f"Found patient: {patient.name}")

        # Validate the data
        validation_errors = self.validate_patient_data(updated_data)
        if validation_errors:
            print(f"Validation errors: {validation_errors}")
            return {"success": False, "errors": validation_errors}

        try:
            # Update patient fields
            if "name" in updated_data:
                patient.name = updated_data["name"]
            if "age" in updated_data:
                patient.age = updated_data["age"]
            if "height" in updated_data:
                # Convert string to float if needed
                height_value = updated_data["height"]
                if isinstance(height_value, str):
                    import re
                    numeric_match = re.search(r"(\d+\.?\d*)", height_value)
                    patient.height = float(numeric_match.group(1)) if numeric_match else 0.0
                else:
                    patient.height = float(height_value)
            if "weight" in updated_data:
                # Convert string to float if needed
                weight_value = updated_data["weight"]
                if isinstance(weight_value, str):
                    import re
                    numeric_match = re.search(r"(\d+\.?\d*)", weight_value)
                    patient.weight = float(numeric_match.group(1)) if numeric_match else 0.0
                else:
                    patient.weight = float(weight_value)
            if "lab_results_history" in updated_data:
                patient.lab_results_history = patient._normalize_lab_history_entries(
                    updated_data["lab_results_history"] or []
                )
            if "doctors_notes_history" in updated_data:
                patient.doctors_notes_history = patient._normalize_doctor_notes_history_entries(
                    updated_data["doctors_notes_history"] or []
                )
            if "severity" in updated_data:
                patient.severity = normalize_severity(updated_data["severity"])

            success = self.save_patients()
            if success:
                return {"success": True, "patient_id": patient_id}
            else:
                return {"success": False, "error": "Failed to save changes"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_patients(self, query: str) -> List[Patient]:
        """
        Search for patients by name

        Args:
            query: Search query string

        Returns:
            List of matching Patient objects
        """
        query = query.lower()
        return [
            patient for patient in self.patients.values()
            if query in patient.name.lower()
        ]

    def filter_patients(self, criteria: Dict) -> List[Patient]:
        """
        Filter patients based on criteria

        Args:
            criteria: Dictionary with filter criteria

        Returns:
            List of matching Patient objects
        """
        filtered_patients = list(self.patients.values())

        if "min_age" in criteria:
            filtered_patients = [p for p in filtered_patients if p.age >= criteria["min_age"]]

        if "max_age" in criteria:
            filtered_patients = [p for p in filtered_patients if p.age <= criteria["max_age"]]

        if "severity" in criteria:
            desired = normalize_severity(criteria["severity"])
            filtered_patients = [p for p in filtered_patients if p.severity == desired]

        return filtered_patients

    def add_patients_bulk(self, patients: List[Patient]) -> Dict:
        """
        Add multiple patients at once

        Args:
            patients: List of Patient objects to add

        Returns:
            Dictionary with success status and added patient IDs
        """
        try:
            added_ids = []
            for patient in patients:
                self.patients[patient.patient_id] = patient
                added_ids.append(patient.patient_id)

            success = self.save_patients()
            if success:
                return {"success": True, "patient_ids": added_ids}
            else:
                return {"success": False, "error": "Failed to save patients"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_patients_csv(self, file_path: str) -> bool:
        """
        Export all patients to a CSV file

        Args:
            file_path: Path to save the CSV file

        Returns:
            True if successful, False otherwise
        """
        try:
            import csv

            # Get all patient data
            patients = list(self.patients.values())

            # Define CSV fields using normalized history summaries
            fields = [
                "patient_id",
                "name",
                "birthDate",
                "height",
                "weight",
                "severity",
                "latest_lab_result",
                "latest_lab_result_date",
                "latest_lab_result_added_by",
                "latest_doctor_note",
                "latest_doctor_note_date",
                "latest_doctor_note_added_by",
            ]

            # Write to CSV
            with open(file_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()

                for patient in patients:
                    data = patient.to_dict()
                    latest_lab = data.get("latest_lab_result") or {}
                    latest_note = data.get("latest_doctor_note") or {}
                    row = {
                        "patient_id": data.get("patient_id", ""),
                        "name": data.get("name", ""),
                        "birthDate": data.get("birthDate", ""),
                        "height": data.get("height", ""),
                        "weight": data.get("weight", ""),
                        "severity": data.get("severity", ""),
                        "latest_lab_result": latest_lab.get("results", ""),
                        "latest_lab_result_date": latest_lab.get("date", ""),
                        "latest_lab_result_added_by": latest_lab.get("added_by", ""),
                        "latest_doctor_note": latest_note.get("note", ""),
                        "latest_doctor_note_date": latest_note.get("date", ""),
                        "latest_doctor_note_added_by": latest_note.get("added_by", ""),
                    }
                    writer.writerow(row)

            return True
        except Exception as e:
            self._log(f"Error exporting to CSV: {str(e)}")
            return False

    # Async methods for FastAPI
    async def async_add_patient(self, patient: Patient) -> Dict:
        """Add a patient with concurrency protection"""
        async with self._lock:
            return self.add_patient(patient)

    async def async_get_patient(self, patient_id: str) -> Optional[Patient]:
        """Get a patient with concurrency protection"""
        async with self._lock:
            return self.get_patient(patient_id)

    async def async_update_patient(self, patient_id: str, updated_data: Dict) -> Dict:
        """Update a patient with concurrency protection"""
        async with self._lock:
            return self.update_patient(patient_id, updated_data)

    async def async_delete_patient(self, patient_id: str) -> Dict:
        """Delete a patient with concurrency protection"""
        async with self._lock:
            return self.delete_patient(patient_id)

    async def async_get_all_patients(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all patients with concurrency protection"""
        async with self._lock:
            return self.get_all_patients(skip, limit)

    async def async_search_patients(self, query: str) -> List[Patient]:
        """Search patients with concurrency protection"""
        async with self._lock:
            return self.search_patients(query)

    async def async_filter_patients(self, criteria: Dict) -> List[Patient]:
        """Filter patients with concurrency protection"""
        async with self._lock:
            return self.filter_patients(criteria)

    async def async_count_patients(self) -> int:
        """Count patients with concurrency protection"""
        async with self._lock:
            return self.count_patients()


# Utility functions for API integration
def create_patient(name: str,
                   birthDate: str,
                   height: float,
                   weight: float,
                   severity: str = "low",
                   lab_results_history: Optional[List[Dict]] = None,
                   doctors_notes_history: Optional[List[Dict]] = None) -> Dict:
    """Create a new patient and return their data"""
    manager = PatientManager()

    patient = Patient(
        name=name,
        birthDate=birthDate,
        height=height,
        weight=weight,
        severity=severity,
        lab_results_history=lab_results_history or [],
        doctors_notes_history=doctors_notes_history or []
    )

    return manager.add_patient(patient)


def get_patient_info(patient_id: str) -> Dict:
    """Get a patient's information"""
    manager = PatientManager()
    patient = manager.get_patient(patient_id)

    if patient:
        return {"success": True, "patient": patient.to_dict()}
    return {"success": False, "error": "Patient not found"}


def get_all_patients_info(skip: int = 0, limit: int = 100) -> Dict:
    """Get information for all patients with pagination"""
    manager = PatientManager()
    patients = manager.get_all_patients(skip, limit)
    total = manager.count_patients()

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "total": total,
        "skip": skip,
        "limit": limit
    }


def update_patient_info(patient_id: str, updated_data: Dict) -> Dict:
    """Update a patient's information"""
    manager = PatientManager()
    return manager.update_patient(patient_id, updated_data)


def delete_patient_record(patient_id: str) -> Dict:
    """Delete a patient's record"""
    manager = PatientManager()
    return manager.delete_patient(patient_id)


def search_patients(query: str) -> Dict:
    """Search for patients by name"""
    manager = PatientManager()
    patients = manager.search_patients(query)

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "count": len(patients)
    }


def filter_patients(criteria: Dict) -> Dict:
    """Filter patients based on criteria"""
    manager = PatientManager()
    patients = manager.filter_patients(criteria)

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "count": len(patients)
    }


# Async utility functions for FastAPI
async def async_create_patient(name: str,
                               birthDate: str,
                               height: float,
                               weight: float,
                               severity: str = "low",
                               lab_results_history: Optional[List[Dict]] = None,
                               doctors_notes_history: Optional[List[Dict]] = None) -> Dict:
    """Create a new patient asynchronously"""
    manager = PatientManager()

    patient = Patient(
        name=name,
        birthDate=birthDate,
        height=height,
        weight=weight,
        severity=severity,
        lab_results_history=lab_results_history or [],
        doctors_notes_history=doctors_notes_history or []
    )

    return await manager.async_add_patient(patient)


async def async_get_patient_info(patient_id: str) -> Dict:
    """Get a patient's information asynchronously"""
    manager = PatientManager()
    patient = await manager.async_get_patient(patient_id)

    if patient:
        return {"success": True, "patient": patient.to_dict()}
    return {"success": False, "error": "Patient not found"}


async def async_get_all_patients_info(skip: int = 0, limit: int = 100) -> Dict:
    """Get information for all patients with pagination asynchronously"""
    manager = PatientManager()
    patients = await manager.async_get_all_patients(skip, limit)
    total = await manager.async_count_patients()

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "total": total,
        "skip": skip,
        "limit": limit
    }


async def async_update_patient_info(patient_id: str, updated_data: Dict) -> Dict:
    """Update a patient's information asynchronously"""
    manager = PatientManager()
    return await manager.async_update_patient(patient_id, updated_data)


async def async_delete_patient_record(patient_id: str) -> Dict:
    """Delete a patient's record asynchronously"""
    manager = PatientManager()
    return await manager.async_delete_patient(patient_id)


async def async_search_patients(query: str) -> Dict:
    """Search for patients by name asynchronously"""
    manager = PatientManager()
    patients = await manager.async_search_patients(query)

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "count": len(patients)
    }


async def async_filter_patients(criteria: Dict) -> Dict:
    """Filter patients based on criteria asynchronously"""
    manager = PatientManager()
    patients = await manager.async_filter_patients(criteria)

    return {
        "success": True,
        "patients": [patient.to_dict() for patient in patients],
        "count": len(patients)
    }


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