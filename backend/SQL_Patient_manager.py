from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import uuid

# -----------------------------
# Dataclasses
# -----------------------------

@dataclass
class DBPatient:
    patient_id: str
    name: str
    dob: Optional[str] = None        # 'YYYY-MM-DD' or None
    height: Optional[int] = None     # centimeters
    weight: Optional[int] = None     # kilograms

    @property
    def age(self) -> Optional[int]:
        if not self.dob:
            return None
        try:
            y, m, d = map(int, self.dob.split("-"))
            born = date(y, m, d)
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except Exception:
            return None

    def to_row(self) -> Tuple:
        return (self.patient_id, self.name, self.dob, self.height, self.weight)

    @staticmethod
    def from_row(row: sqlite3.Row) -> "DBPatient":
        return DBPatient(
            patient_id=row["patient_id"],
            name=row["name"],
            dob=row["dob"],
            height=row["height"],
            weight=row["weight"],
        )


@dataclass
class DBVisit:
    visit_id: Optional[int]
    patient_id: str
    visit_date: str                   # ISO datetime string
    progression_note: Optional[str] = None
    doctor_notes: Optional[str] = None
    vitals_json: Optional[Dict[str, Any]] = None
    status: str = "closed"

    def to_row(self) -> Tuple:
        return (
            self.patient_id,
            self.visit_date,
            self.progression_note,
            self.doctor_notes,
            json.dumps(self.vitals_json) if isinstance(self.vitals_json, dict) else self.vitals_json,
            self.status,
        )

    @staticmethod
    def from_row(row: sqlite3.Row) -> "DBVisit":
        vjson = row["vitals_json"]
        try:
            vjson = json.loads(vjson) if vjson else None
        except Exception:
            pass
        return DBVisit(
            visit_id=row["visit_id"],
            patient_id=row["patient_id"],
            visit_date=row["visit_date"],
            progression_note=row["progression_note"],
            doctor_notes=row["doctor_notes"],
            vitals_json=vjson,
            status=row["status"],
        )


@dataclass
class DBTestResult:
    test_id: Optional[int]
    patient_id: str
    test_type: Optional[str] = None
    test_date: Optional[str] = None   # 'YYYY-MM-DD'
    keypoints: Optional[str] = None   # JSON/text

    def to_row(self) -> Tuple:
        return (self.patient_id, self.test_type, self.test_date, self.keypoints)

    @staticmethod
    def from_row(row: sqlite3.Row) -> "DBTestResult":
        return DBTestResult(
            test_id=row["test_id"],
            patient_id=row["patient_id"],
            test_type=row["test_type"],
            test_date=row["test_date"],
            keypoints=row["keypoints"],
        )


# -----------------------------
# Manager
# -----------------------------

class SQLitePatientManager:
    """High-level CRUD manager for patients, visits, and test results using SQLite.

    Schema expected (mirrors sql.py):
      - patients(patient_id TEXT PK, name TEXT, dob DATE, height INTEGER, weight INTEGER)
      - visits(visit_id INTEGER PK, patient_id TEXT FK, visit_date DATETIME NOT NULL,
               progression_note TEXT, doctor_notes TEXT, vitals_json TEXT, status TEXT)
      - testresults(test_id INTEGER PK, patient_id TEXT FK, test_type TEXT, test_date DATE, keypoints TEXT)
    """

    def __init__(self, db_path: str = "ParkinsonsPatients.db", ensure_schema: bool = True) -> None:
        self.db_path = db_path
        self._conn_kwargs = {"detect_types": sqlite3.PARSE_DECLTYPES}
        if ensure_schema:
            self._ensure_schema()

    # ---------- connection helpers ----------
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, **self._conn_kwargs)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS patients(
                    patient_id TEXT PRIMARY KEY,
                    name TEXT,
                    dob DATE,
                    height INTEGER,
                    weight INTEGER
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS visits(
                    visit_id INTEGER PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    visit_date DATETIME NOT NULL,
                    progression_note TEXT,
                    doctor_notes TEXT,
                    vitals_json TEXT,
                    status TEXT DEFAULT 'closed',
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS testresults(
                    test_id INTEGER PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    test_type TEXT,
                    test_date DATE,
                    keypoints TEXT,
                    FOREIGN KEY(patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
                )
                """
            )

    # ---------- utilities ----------
    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _gen_patient_id(name: str) -> str:
        base = "".join(ch for ch in name.lower() if ch.isalnum())[:5]
        return f"{base}-{uuid.uuid4().hex[:8]}"

    # ---------- PATIENTS ----------
    def add_patient(self, name: str, dob: Optional[str] = None, height: Optional[int] = None,
                    weight: Optional[int] = None, patient_id: Optional[str] = None) -> str:
        pid = patient_id or self._gen_patient_id(name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO patients(patient_id, name, dob, height, weight) VALUES(?,?,?,?,?)",
                (pid, name, dob, height, weight),
            )
        return pid

    def upsert_patient(self, patient: DBPatient) -> str:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO patients(patient_id, name, dob, height, weight)
                VALUES(?,?,?,?,?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    name=excluded.name,
                    dob=excluded.dob,
                    height=excluded.height,
                    weight=excluded.weight
                """,
                patient.to_row(),
            )
        return patient.patient_id

    def get_patient(self, patient_id: str) -> Optional[DBPatient]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
            row = cur.fetchone()
            return DBPatient.from_row(row) if row else None

    def list_patients(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[DBPatient]:
        with self._connect() as conn:
            if search:
                cur = conn.execute(
                    "SELECT * FROM patients WHERE name LIKE ? ORDER BY name LIMIT ? OFFSET ?",
                    (f"%{search}%", limit, skip),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM patients ORDER BY name LIMIT ? OFFSET ?",
                    (limit, skip),
                )
            return [DBPatient.from_row(r) for r in cur.fetchall()]

    def count_patients(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM patients").fetchone()
            return int(n)

    def update_patient(self, patient_id: str, **fields) -> bool:
        allowed = {k: v for k, v in fields.items() if k in {"name", "dob", "height", "weight"}}
        if not allowed:
            return False
        sets = ", ".join(f"{k} = ?" for k in allowed)
        params = list(allowed.values()) + [patient_id]
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE patients SET {sets} WHERE patient_id = ?", params)
            return cur.rowcount > 0

    def delete_patient(self, patient_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
            return cur.rowcount > 0

    # ---------- VISITS ----------
    def add_visit(self, patient_id: str, visit_date: Optional[str] = None, progression_note: Optional[str] = None,
                  doctor_notes: Optional[str] = None, vitals_json: Optional[Dict[str, Any]] = None,
                  status: str = "closed") -> int:
        vdate = visit_date or self._now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO visits(patient_id, visit_date, progression_note, doctor_notes, vitals_json, status)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    patient_id,
                    vdate,
                    progression_note,
                    doctor_notes,
                    json.dumps(vitals_json) if isinstance(vitals_json, dict) else vitals_json,
                    status,
                ),
            )
            return cur.lastrowid

    def list_visits(self, patient_id: Optional[str] = None) -> List[DBVisit]:
        with self._connect() as conn:
            if patient_id:
                cur = conn.execute("SELECT * FROM visits WHERE patient_id = ? ORDER BY visit_date DESC", (patient_id,))
            else:
                cur = conn.execute("SELECT * FROM visits ORDER BY visit_date DESC")
            return [DBVisit.from_row(r) for r in cur.fetchall()]

    def update_visit(self, visit_id: int, **fields) -> bool:
        allowed_keys = {"visit_date", "progression_note", "doctor_notes", "vitals_json", "status"}
        allowed = {k: (json.dumps(v) if k == "vitals_json" and isinstance(v, dict) else v)
                   for k, v in fields.items() if k in allowed_keys}
        if not allowed:
            return False
        sets = ", ".join(f"{k} = ?" for k in allowed)
        params = list(allowed.values()) + [visit_id]
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE visits SET {sets} WHERE visit_id = ?", params)
            return cur.rowcount > 0

    def delete_visit(self, visit_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM visits WHERE visit_id = ?", (visit_id,))
            return cur.rowcount > 0

    # ---------- TEST RESULTS ----------
    def add_test_result(self, patient_id: str, test_type: Optional[str] = None, test_date: Optional[str] = None,
                        keypoints: Optional[str] = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO testresults(patient_id, test_type, test_date, keypoints) VALUES(?,?,?,?)",
                (patient_id, test_type, test_date, keypoints),
            )
            return cur.lastrowid

    def list_test_results(self, patient_id: Optional[str] = None) -> List[DBTestResult]:
        with self._connect() as conn:
            if patient_id:
                cur = conn.execute("SELECT * FROM testresults WHERE patient_id = ? ORDER BY test_date DESC NULLS LAST",
                                   (patient_id,))
            else:
                cur = conn.execute("SELECT * FROM testresults ORDER BY test_date DESC NULLS LAST")
            return [DBTestResult.from_row(r) for r in cur.fetchall()]

    def delete_test_result(self, test_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM testresults WHERE test_id = ?", (test_id,))
            return cur.rowcount > 0


# -----------------------------
# Compatibility helpers (rough parity with old JSON API)
# -----------------------------

class API:
    """Static helpers to offer an API similar to the JSON-based manager (simplified)."""

    @staticmethod
    def create_patient(name: str, dob: Optional[str] = None, height: Optional[int] = None, weight: Optional[int] = None,
                       db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        pid = mgr.add_patient(name=name, dob=dob, height=height, weight=weight)
        return {"success": True, "patient_id": pid}

    @staticmethod
    def get_patient_info(patient_id: str, db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        p = mgr.get_patient(patient_id)
        if not p:
            return {"success": False, "error": "Patient not found"}
        data = asdict(p)
        data["age"] = p.age
        return {"success": True, "patient": data}

    @staticmethod
    def get_all_patients_info(skip: int = 0, limit: int = 100, db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        pts = mgr.list_patients(skip=skip, limit=limit)
        return {
            "success": True,
            "patients": [asdict(p) | {"age": p.age} for p in pts],
            "total": mgr.count_patients(),
            "skip": skip,
            "limit": limit,
        }

    @staticmethod
    def update_patient_info(patient_id: str, updated_data: Dict[str, Any], db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        ok = mgr.update_patient(patient_id, **updated_data)
        return {"success": ok, **({} if ok else {"error": "Update failed or no valid fields"})}

    @staticmethod
    def delete_patient_record(patient_id: str, db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        ok = mgr.delete_patient(patient_id)
        return {"success": ok, **({} if ok else {"error": "Patient not found"})}

    @staticmethod
    def search_patients(query: str, db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
        mgr = SQLitePatientManager(db_path)
        pts = mgr.list_patients(search=query)
        return {"success": True, "patients": [asdict(p) | {"age": p.age} for p in pts], "count": len(pts)}


# -----------------------------
# Optional: one-shot migration helper from old patients.json
# -----------------------------

def migrate_json_to_sql(json_path: str, db_path: str = "ParkinsonsPatients.db") -> Dict[str, Any]:
    """Best-effort migration: name/height/weight copied; dob is left NULL (age can't be reliably backfilled)."""
    import os
    if not os.path.exists(json_path):
        return {"success": False, "error": f"{json_path} not found"}

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    mgr = SQLitePatientManager(db_path)
    inserted = 0
    for pid, pdata in data.items():
        name = pdata.get("name")
        # Attempt numeric extraction for height/weight if strings
        def _to_int(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return int(val)
            try:
                import re
                m = re.search(r"(\d+)", str(val))
                return int(m.group(1)) if m else None
            except Exception:
                return None
        height = _to_int(pdata.get("height"))
        weight = _to_int(pdata.get("weight"))
        # Keep original id if unique; else generate
        try:
            with mgr._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO patients(patient_id, name, dob, height, weight) VALUES(?,?,?,?,?)",
                    (pid, name, None, height, weight),
                )
            inserted += 1
        except Exception:
            # fallback with generated id
            mgr.add_patient(name=name or "Unknown", dob=None, height=height, weight=weight)
            inserted += 1

    return {"success": True, "inserted": inserted}


if __name__ == "__main__":
    # quick sanity run creating the DB and inserting one patient
    mgr = SQLitePatientManager()
    pid = mgr.add_patient(name="Test Patient", dob="1970-01-01", height=170, weight=70)
    print("Inserted:", pid)
    print("Total patients:", mgr.count_patients())
