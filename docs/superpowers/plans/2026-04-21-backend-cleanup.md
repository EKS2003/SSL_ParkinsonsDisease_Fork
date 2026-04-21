# Backend Cleanup & DI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend to use dependency injection, a service layer, typed error handling, environment-based config, and SQL-backed test history — without restructuring the folder tree.

**Architecture:** A new `core/` package holds config, exceptions, and DI wiring. `patient_manager.py` becomes `services/patient_service.py` (a class). `TestHistoryManager` (JSON singleton) is replaced by `TestHistoryService` (SQL-backed). FastAPI's native `Depends()` wires everything together.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, pydantic-settings, python-jose, passlib, pytest, SQLite (dev)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| CREATE | `backend/core/__init__.py` | package marker |
| CREATE | `backend/core/config.py` | Pydantic BaseSettings — all env/config values |
| CREATE | `backend/core/exceptions.py` | Typed domain exceptions |
| CREATE | `backend/core/dependencies.py` | FastAPI Depends() wiring |
| UPDATE | `backend/repo/db.py` | Engine + SessionLocal using config (replaces stub) |
| CREATE | `backend/services/__init__.py` | package marker |
| CREATE | `backend/services/patient_service.py` | PatientService class (replaces patient_manager.py) |
| CREATE | `backend/services/test_history_service.py` | TestHistoryService using SQL (replaces test_history_manager.py) |
| UPDATE | `backend/auth.py` | Use core/config.py; remove get_current_user |
| UPDATE | `backend/routes/patient.py` | Use Depends(get_patient_service) |
| UPDATE | `backend/routes/classifier.py` | Use Depends(get_patient_service); fix schema import |
| UPDATE | `backend/routes/websockets.py` | Use Depends(get_test_history_service) |
| CREATE | `backend/routes/patient_media.py` | Video upload/listing routes (moved from main.py) |
| CREATE | `backend/routes/classifier_schema.py` | Move from schema/classifier_schema.py |
| UPDATE | `backend/main.py` | Exception handlers; include patient_media router; use config for CORS |
| UPDATE | `backend/routes/contracts.py` | Remove `success: bool` from response models |
| CREATE | `backend/tests/test_patient_service.py` | PatientService unit tests |
| UPDATE | `backend/tests/test_patient_manager.py` | Re-target to PatientService |
| DELETE | `backend/patient_manager.py` | Replaced by services/patient_service.py |
| DELETE | `backend/test_history_manager.py` | Replaced by services/test_history_service.py |
| DELETE | `backend/schema/patient_schema.py` | Unused (routes/contracts.py is canonical) |
| DELETE | `backend/schema/visit_schema.py` | Unused |
| DELETE | `backend/schema/schema.py` | Empty |

---

## Task 1: Baseline — run existing tests

**Files:** none modified

- [ ] **Step 1: Run existing tests**

```bash
cd backend && python -m pytest tests/ -v 2>&1 | head -60
```

Expected: some tests pass (repository tests), test_patient_manager.py may have import issues. Document which pass/fail — this is the baseline.

- [ ] **Step 2: Commit baseline note**

```bash
git commit --allow-empty -m "chore: begin backend cleanup refactor"
```

---

## Task 2: Configuration — `core/config.py`

**Files:**
- Create: `backend/core/__init__.py`
- Create: `backend/core/config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add pydantic-settings to requirements.txt**

Open `backend/requirements.txt` and add this line after `pydantic==2.12.3`:
```
pydantic-settings==2.7.1
```

Install it:
```bash
cd backend && pip install pydantic-settings==2.7.1
```

- [ ] **Step 2: Create `backend/core/__init__.py`**

```python
```
(empty file)

- [ ] **Step 3: Create `backend/core/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:8001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ]

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Verify import works**

```bash
cd backend && python -c "from core.config import settings; print(settings.db_url)"
```

Expected: `sqlite:///./app.db`

- [ ] **Step 5: Commit**

```bash
git add backend/core/__init__.py backend/core/config.py backend/requirements.txt
git commit -m "feat: add core/config.py with Pydantic BaseSettings"
```

---

## Task 3: Database setup — `repo/db.py`

**Files:**
- Modify: `backend/repo/db.py`

- [ ] **Step 1: Replace the stub in `backend/repo/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from repo.sql_models import Base

engine = create_engine(settings.db_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from repo.db import SessionLocal, init_db; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/repo/db.py
git commit -m "feat: move DB setup to repo/db.py using config"
```

---

## Task 4: Typed exceptions — `core/exceptions.py`

**Files:**
- Create: `backend/core/exceptions.py`

- [ ] **Step 1: Create `backend/core/exceptions.py`**

```python
class PatientNotFoundError(Exception):
    def __init__(self, patient_id: str) -> None:
        self.patient_id = patient_id
        super().__init__(f"Patient {patient_id} not found")


class PatientValidationError(Exception):
    def __init__(self, errors: dict) -> None:
        self.errors = errors
        super().__init__(str(errors))


class DuplicatePatientError(Exception):
    def __init__(self, patient_id: str) -> None:
        self.patient_id = patient_id
        super().__init__(f"Patient {patient_id} already exists")
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from core.exceptions import PatientNotFoundError; raise PatientNotFoundError('P1')" 2>&1 | grep PatientNotFoundError
```

Expected: `core.exceptions.PatientNotFoundError: Patient P1 not found`

- [ ] **Step 3: Commit**

```bash
git add backend/core/exceptions.py
git commit -m "feat: add typed domain exceptions"
```

---

## Task 5: Test history service — `services/test_history_service.py`

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/test_history_service.py`

- [ ] **Step 1: Create `backend/services/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Create `backend/services/test_history_service.py`**

```python
from datetime import datetime
from sqlalchemy.orm import Session

from repo.sql_models import TestResult


class TestHistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_patient_tests(self, patient_id: str) -> list[TestResult]:
        return (
            self.db.query(TestResult)
            .filter(TestResult.patient_id == patient_id)
            .all()
        )

    def add_patient_test(self, patient_id: str, test_data: dict) -> TestResult:
        record = TestResult(
            patient_id=patient_id,
            test_name=test_data.get("test_name"),
            test_date=test_data.get("date"),
            recording_file=test_data.get("recording_file"),
            frame_count=test_data.get("frame_count"),
        )
        self.db.add(record)
        self.db.commit()
        return record

    def get_all_tests(self) -> list[TestResult]:
        return self.db.query(TestResult).all()
```

- [ ] **Step 3: Verify import**

```bash
cd backend && python -c "from services.test_history_service import TestHistoryService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/__init__.py backend/services/test_history_service.py
git commit -m "feat: add TestHistoryService backed by SQL"
```

---

## Task 6: Patient service — `services/patient_service.py`

**Files:**
- Create: `backend/services/patient_service.py`

- [ ] **Step 1: Write the failing test first**

Create `backend/tests/test_patient_service.py`:

```python
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repo.sql_models import Base, User
from repo.patient_repository import PatientRepository
from routes.contracts import PatientCreate, PatientUpdate
from services.patient_service import PatientService
from core.exceptions import PatientNotFoundError, PatientValidationError


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    u = User(
        username="doc",
        full_name="Dr. Test",
        email="doc@test.com",
        hashed_password="pw",
        location="UF",
        title="MD",
        speciality="Neurology",
    )
    session.add(u)
    session.commit()

    yield session, u.id
    session.close()


@pytest.fixture
def service(db):
    session, user_id = db
    return PatientService(PatientRepository(session), session), user_id


def test_create_patient_returns_id(service):
    svc, user_id = service
    data = PatientCreate(
        name="Alice",
        age=40,
        birthDate=date(1984, 1, 1),
        height=165.0,
        weight=60.0,
        severity="Stage 1",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    assert patient_id is not None
    assert isinstance(patient_id, str)


def test_create_patient_invalid_severity_raises(service):
    svc, user_id = service
    data = PatientCreate(
        name="Bob",
        age=50,
        birthDate=date(1974, 1, 1),
        height=170.0,
        weight=75.0,
        severity="Stage 99",
    )
    with pytest.raises(PatientValidationError) as exc_info:
        svc.create_patient(user_id=user_id, data=data)
    assert "severity" in exc_info.value.errors


def test_get_patient_not_found_raises(service):
    svc, _ = service
    with pytest.raises(PatientNotFoundError):
        svc.get_patient("nonexistent-id")


def test_get_patient_returns_response(service):
    svc, user_id = service
    data = PatientCreate(
        name="Carol",
        age=35,
        birthDate=date(1989, 6, 15),
        height=160.0,
        weight=55.0,
        severity="Stage 2",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    resp = svc.get_patient(patient_id)
    assert resp.name == "Carol"
    assert resp.patient_id == patient_id


def test_update_patient(service):
    svc, user_id = service
    data = PatientCreate(
        name="Dave",
        age=60,
        birthDate=date(1964, 3, 10),
        height=180.0,
        weight=85.0,
        severity="Stage 3",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    svc.update_patient(patient_id, PatientUpdate(severity="Stage 4"))
    resp = svc.get_patient(patient_id)
    assert resp.severity == "Stage 4"


def test_delete_patient(service):
    svc, user_id = service
    data = PatientCreate(
        name="Eve",
        age=45,
        birthDate=date(1979, 9, 20),
        height=158.0,
        weight=52.0,
        severity="Stage 1",
    )
    patient_id = svc.create_patient(user_id=user_id, data=data)
    svc.delete_patient(patient_id)
    with pytest.raises(PatientNotFoundError):
        svc.get_patient(patient_id)


def test_list_patients(service):
    svc, user_id = service
    for i in range(3):
        svc.create_patient(
            user_id=user_id,
            data=PatientCreate(
                name=f"Patient {i}",
                age=30 + i,
                birthDate=date(1990, 1, 1),
                height=170.0,
                weight=70.0,
                severity="Stage 1",
            ),
        )
    result = svc.list_patients(skip=0, limit=100)
    assert result["total"] >= 3


def test_search_patients(service):
    svc, user_id = service
    svc.create_patient(
        user_id=user_id,
        data=PatientCreate(
            name="Unique Search Name",
            age=55,
            birthDate=date(1969, 1, 1),
            height=172.0,
            weight=78.0,
            severity="Stage 2",
        ),
    )
    results = svc.search_patients("Unique Search Name")
    assert any(p.name == "Unique Search Name" for p in results)
```

- [ ] **Step 2: Run — expect ImportError (service doesn't exist yet)**

```bash
cd backend && python -m pytest tests/test_patient_service.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PatientService'`

- [ ] **Step 3: Create `backend/services/patient_service.py`**

```python
from __future__ import annotations

import re
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
    return f"{base}{int(datetime.now().timestamp())}"


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
```

- [ ] **Step 4: Run the new tests**

```bash
cd backend && python -m pytest tests/test_patient_service.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/patient_service.py backend/tests/test_patient_service.py
git commit -m "feat: add PatientService class with full test coverage"
```

---

## Task 7: Dependency injection — `core/dependencies.py`

**Files:**
- Create: `backend/core/dependencies.py`

- [ ] **Step 1: Create `backend/core/dependencies.py`**

```python
from typing import Generator

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from core.config import settings
from repo.db import SessionLocal
from repo.patient_repository import PatientRepository
from repo.sql_models import User
from services.patient_service import PatientService
from services.test_history_service import TestHistoryService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(PatientRepository(db), db)


def get_test_history_service(db: Session = Depends(get_db)) -> TestHistoryService:
    return TestHistoryService(db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    user = db.query(User).filter_by(username=username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from core.dependencies import get_db, get_patient_service, get_current_user; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/core/dependencies.py
git commit -m "feat: add core/dependencies.py with FastAPI DI wiring"
```

---

## Task 8: Update `auth.py`

**Files:**
- Modify: `backend/auth.py`

`auth.py` keeps `authenticate()` and `create_access_token()`. `get_current_user` is removed (it now lives in `core/dependencies.py`). Hardcoded constants replaced with `settings`.

- [ ] **Step 1: Replace `backend/auth.py` entirely**

```python
from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from core.config import settings
from repo.db import SessionLocal
from repo.sql_models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def authenticate(username: str, password: str) -> User | None:
    try:
        with SessionLocal() as session:
            user = session.query(User).filter_by(username=username).first()
            if user and pwd.verify(password, user.hashed_password):
                return user
    except Exception:
        return None


def create_access_token(sub: str) -> str:
    to_encode = {
        "sub": sub,
        "exp": datetime.now() + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from auth import authenticate, create_access_token; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/auth.py
git commit -m "refactor: auth.py uses core/config.py; remove get_current_user"
```

---

## Task 9: Update `routes/patient.py`

**Files:**
- Modify: `backend/routes/patient.py`

- [ ] **Step 1: Replace `backend/routes/patient.py` entirely**

```python
from fastapi import APIRouter, Depends, Query
from typing import Dict

from core.dependencies import get_patient_service, get_current_user
from routes.contracts import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientsListResponse,
    PatientSearchResponse,
    FilterCriteria,
)
from repo.sql_models import User
from services.patient_service import PatientService

router = APIRouter(prefix="/patients")


@router.post("/", response_model=Dict)
async def create_patient(
    patient: PatientCreate,
    service: PatientService = Depends(get_patient_service),
    current_user: User = Depends(get_current_user),
):
    patient_id = service.create_patient(user_id=current_user.id, data=patient)
    return {"patient_id": patient_id}


@router.get("/", response_model=PatientsListResponse)
async def get_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: PatientService = Depends(get_patient_service),
):
    return service.list_patients(skip, limit)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    return service.get_patient(patient_id)


@router.put("/{patient_id}", response_model=Dict)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    service: PatientService = Depends(get_patient_service),
):
    service.update_patient(patient_id, patient_update)
    return {"patient_id": patient_id}


@router.delete("/{patient_id}", response_model=Dict)
async def delete_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    service.delete_patient(patient_id)
    return {"patient_id": patient_id}


@router.get("/search/{query}", response_model=PatientSearchResponse)
async def search_patients(
    query: str,
    service: PatientService = Depends(get_patient_service),
):
    patients = service.search_patients(query)
    return {"patients": patients, "count": len(patients)}


@router.post("/filter/", response_model=PatientSearchResponse)
async def filter_patients(
    criteria: FilterCriteria,
    service: PatientService = Depends(get_patient_service),
):
    patients = service.filter_patients(criteria.model_dump(exclude_none=True))
    return {"patients": patients, "count": len(patients)}
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from routes.patient import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all previously passing tests still pass; new patient_service tests still pass.

- [ ] **Step 4: Commit**

```bash
git add backend/routes/patient.py
git commit -m "refactor: routes/patient.py uses PatientService via Depends()"
```

---

## Task 10: Move `classifier_schema.py` and update `routes/classifier.py`

**Files:**
- Create: `backend/routes/classifier_schema.py`
- Modify: `backend/routes/classifier.py`

- [ ] **Step 1: Create `backend/routes/classifier_schema.py`**

Copy the full content from `backend/schema/classifier_schema.py`:

```python
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LSTMCNNPredictRequest(BaseModel):
    sequence: list[list[float]] = Field(
        ...,
        description="Input sequence with shape (T, 24).",
    )
    return_attention: bool = Field(
        default=False,
        description="Include attention weights per window in the response.",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence_contract(cls, value: list[list[float]]) -> list[list[float]]:
        if not value:
            raise ValueError("sequence must not be empty")
        if len(value) < 30:
            raise ValueError("sequence length must be at least 30")
        for i, frame in enumerate(value):
            if len(frame) != 24:
                raise ValueError(f"frame {i} must have exactly 24 features")
            for j, feature in enumerate(frame):
                if not math.isfinite(feature):
                    raise ValueError(f"feature at frame {i}, index {j} is NaN or infinite")
        return value


class LSTMCNNPredictResponse(BaseModel):
    predicted_updrs_stage: int
    probabilities: dict[str, float]
    severity: str
    severity_stage: int
    prediction: str
    confidence: float
    lstm_output: list[float]
    logits: list[float]
    n_windows: int
    window_size: int
    stride: int
    model_version: str
    preprocessing_version: str
    checkpoint_path: str
    attention_weights: list[float] | None = None


class LSTMCNNPredictAndUpdateResponse(LSTMCNNPredictResponse):
    patient_id: str
    patient_updated: bool


class APIErrorResponse(BaseModel):
    detail: Any
```

- [ ] **Step 2: Update imports in `backend/routes/classifier.py`**

Change the two import lines at the top of `classifier.py`:

Old:
```python
from patient_manager import async_update_patient_info
from routes.contracts import PatientUpdate
from schema.classifier_schema import (
    APIErrorResponse,
    LSTMCNNPredictAndUpdateResponse,
    LSTMCNNPredictRequest,
    LSTMCNNPredictResponse,
)
```

New:
```python
from fastapi import Depends
from routes.contracts import PatientUpdate
from routes.classifier_schema import (
    APIErrorResponse,
    LSTMCNNPredictAndUpdateResponse,
    LSTMCNNPredictRequest,
    LSTMCNNPredictResponse,
)
from core.dependencies import get_patient_service
from services.patient_service import PatientService
```

- [ ] **Step 3: Update `predict_updrs_and_update_patient` to use DI**

Replace the `async_update_patient_info` call in the `predict_updrs_and_update_patient` endpoint. Change the function signature and body:

Old signature:
```python
async def predict_updrs_and_update_patient(
    patient_id: str,
    payload: LSTMCNNPredictRequest,
    persist_update: bool = Query(default=True, ...),
) -> LSTMCNNPredictAndUpdateResponse:
```

New signature and relevant body section:
```python
async def predict_updrs_and_update_patient(
    patient_id: str,
    payload: LSTMCNNPredictRequest,
    persist_update: bool = Query(
        default=True,
        description="When false, return prediction without updating patient severity.",
    ),
    service: PatientService = Depends(get_patient_service),
) -> LSTMCNNPredictAndUpdateResponse:
    try:
        result = inference_service.predict(
            sequence=payload.sequence,
            return_attention=payload.return_attention,
        )

        patient_updated = False
        if persist_update:
            service.update_patient(patient_id, PatientUpdate(severity=result["severity"]))
            patient_updated = True

        return LSTMCNNPredictAndUpdateResponse(
            **result,
            patient_id=patient_id,
            patient_updated=patient_updated,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to run LSTM-CNN integration flow: {exc}") from exc
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && python -c "from routes.classifier import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classifier_schema.py backend/routes/classifier.py
git commit -m "refactor: move classifier_schema.py to routes/; use PatientService DI"
```

---

## Task 11: Update `routes/websockets.py`

**Files:**
- Modify: `backend/routes/websockets.py`

The `_camera_ws_handler` currently calls `TestHistoryManager.get_instance()`. Change it to accept a `TestHistoryService` parameter.

- [ ] **Step 1: Update the import block at the top of `backend/routes/websockets.py`**

Remove:
```python
from test_history_manager import TestHistoryManager
```

Add:
```python
from core.dependencies import get_test_history_service
from services.test_history_service import TestHistoryService
```

- [ ] **Step 2: Update `_camera_ws_handler` signature**

Old:
```python
async def _camera_ws_handler(websocket: WebSocket):
```

New:
```python
async def _camera_ws_handler(websocket: WebSocket, test_history: TestHistoryService):
```

- [ ] **Step 3: Replace `TestHistoryManager.get_instance()` call in the `end` handler**

Old (inside the `elif mtype == "end":` block):
```python
                try:
                    thm = TestHistoryManager.get_instance()
                    thm.add_patient_test(patient_id or "unknown", {
                        "test_name": test_name or "unknown",
                        "date": datetime.utcnow().isoformat(),
                        "recording_file": saved_name,
                        "frame_count": len(frames)
                    })
                except Exception:
                    pass
```

New:
```python
                try:
                    test_history.add_patient_test(patient_id or "unknown", {
                        "test_name": test_name or "unknown",
                        "date": datetime.utcnow(),
                        "recording_file": saved_name,
                        "frame_count": len(frames),
                    })
                except Exception:
                    pass
```

- [ ] **Step 4: Update WebSocket endpoint functions to inject and pass `test_history`**

Old:
```python
@router.websocket("/{client_id}")
async def ws_client(websocket: WebSocket, client_id: str):
    await _camera_ws_handler(websocket)

@router.websocket("/camera")
async def ws_camera(websocket: WebSocket):
    await _camera_ws_handler(websocket)
```

New:
```python
from fastapi import Depends

@router.websocket("/{client_id}")
async def ws_client(
    websocket: WebSocket,
    client_id: str,
    test_history: TestHistoryService = Depends(get_test_history_service),
):
    await _camera_ws_handler(websocket, test_history)


@router.websocket("/camera")
async def ws_camera(
    websocket: WebSocket,
    test_history: TestHistoryService = Depends(get_test_history_service),
):
    await _camera_ws_handler(websocket, test_history)
```

- [ ] **Step 5: Verify import**

```bash
cd backend && python -c "from routes.websockets import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/websockets.py
git commit -m "refactor: websockets.py uses TestHistoryService via Depends()"
```

---

## Task 12: Create `routes/patient_media.py`

**Files:**
- Create: `backend/routes/patient_media.py`

These routes are currently inline in `main.py`. Moving them here keeps `main.py` clean.

- [ ] **Step 1: Create `backend/routes/patient_media.py`**

```python
import os
import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDINGS_DIR = os.path.join(BASE_DIR, "routes", "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

router = APIRouter(tags=["media"])


@router.post("/upload-video/")
async def upload_video(
    patient_id: str = Form(...),
    test_name: str = Form(...),
    video: UploadFile = File(...),
):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{patient_id}_{test_name}_{now_str}.mov"
        filepath = os.path.join(RECORDINGS_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        return {
            "success": True,
            "filename": filename,
            "path": f"recordings/{filename}",
            "patient_id": patient_id,
            "test_name": test_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/videos/{patient_id}/{test_name}", response_model=Dict)
def list_videos(patient_id: str, test_name: str):
    try:
        files = os.listdir(RECORDINGS_DIR)
        matching = [
            f for f in files
            if f.startswith(f"{patient_id}_{test_name}_") and (f.endswith(".mov") or f.endswith(".mp4"))
        ]
        matching.sort(
            key=lambda f: os.path.getmtime(os.path.join(RECORDINGS_DIR, f)),
            reverse=True,
        )
        return {"success": True, "videos": matching}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/recordings/{filename}", response_class=FileResponse)
def get_recording_file(filename: str):
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    media_type = "video/mp4" if filename.endswith(".mp4") else "video/quicktime"
    return FileResponse(file_path, media_type=media_type)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from routes.patient_media import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/routes/patient_media.py
git commit -m "feat: add routes/patient_media.py for video upload/listing"
```

---

## Task 13: Update `main.py`

**Files:**
- Modify: `backend/main.py`

Remove all inline route handlers. Add exception handlers. Use `settings` for CORS. Include `patient_media` router.

- [ ] **Step 1: Replace `backend/main.py` entirely**

```python
from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from core.config import settings
from core.exceptions import PatientNotFoundError, PatientValidationError, DuplicatePatientError
from core.dependencies import get_test_history_service
from repo.db import init_db
from services.test_history_service import TestHistoryService

from routes.dtw_rest import router as dtw_router
from routes.patient import router as patient_router
from routes.websockets import router as ws_router
from routes.classifier import router as classifier_router
from routes.patient_media import router as media_router

from auth import authenticate, create_access_token
from repo.sql_models import User
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI(title="Patient Management API")

init_db()

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(PatientNotFoundError)
async def patient_not_found_handler(request, exc: PatientNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PatientValidationError)
async def patient_validation_handler(request, exc: PatientValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors})


@app.exception_handler(DuplicatePatientError)
async def duplicate_patient_handler(request, exc: DuplicatePatientError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(dtw_router)
app.include_router(patient_router)
app.include_router(ws_router)
app.include_router(classifier_router)
app.include_router(media_router)


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(sub=user.username)
    return {"access_token": access_token, "token_type": "bearer"}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Welcome to the Patient Management API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}


# ── Test History ──────────────────────────────────────────────────────────────
@app.get("/patients/{patient_id}/tests")
async def get_patient_tests(
    patient_id: str,
    test_history: TestHistoryService = Depends(get_test_history_service),
):
    tests = test_history.get_patient_tests(patient_id)
    return {"tests": [
        {
            "test_name": t.test_name,
            "date": t.test_date.isoformat() if t.test_date else None,
            "recording_file": t.recording_file,
            "frame_count": t.frame_count,
        }
        for t in tests
    ]}


@app.post("/patients/{patient_id}/tests")
async def add_patient_test(
    patient_id: str,
    test_data: dict = Body(...),
    test_history: TestHistoryService = Depends(get_test_history_service),
):
    test_history.add_patient_test(patient_id, test_data)
    return {"patient_id": patient_id}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Verify the app starts (check for import errors)**

```bash
cd backend && python -c "from main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass (patient_repository, patient_service). `test_patient_manager.py` will fail — that's fixed in Task 14.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "refactor: main.py uses config, exception handlers, and DI; no inline routes"
```

---

## Task 14: Update `routes/contracts.py`

**Files:**
- Modify: `backend/routes/contracts.py`

Remove `success: bool` from `PatientsListResponse` and `PatientSearchResponse` since HTTP status codes now carry that meaning. **Note:** This is a breaking change to the frontend; the frontend is updated in the next phase.

- [ ] **Step 1: Update `PatientsListResponse` and `PatientSearchResponse` in `backend/routes/contracts.py`**

Old:
```python
class PatientsListResponse(BaseModel):
    success: bool
    patients: List[PatientResponse]
    total: int
    skip: int
    limit: int

class PatientSearchResponse(BaseModel):
    success: bool
    patients: List[PatientResponse]
    count: int
```

New:
```python
class PatientsListResponse(BaseModel):
    patients: List[PatientResponse]
    total: int
    skip: int
    limit: int

class PatientSearchResponse(BaseModel):
    patients: List[PatientResponse]
    count: int
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from routes.contracts import PatientsListResponse, PatientSearchResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/routes/contracts.py
git commit -m "refactor: remove success: bool from response models"
```

---

## Task 15: Rewrite `tests/test_patient_manager.py`

**Files:**
- Modify: `backend/tests/test_patient_manager.py`

The old tests import from `patient_manager`. Re-target them to `PatientService`.

- [ ] **Step 1: Replace `backend/tests/test_patient_manager.py`**

```python
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repo.sql_models import Base, User
from repo.patient_repository import PatientRepository
from services.patient_service import PatientService, _parse_number
from core.exceptions import PatientValidationError


@pytest.fixture
def service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    u = User(
        username="doc",
        full_name="Dr. Test",
        email="doc@test.com",
        hashed_password="pw",
        location="UF",
        title="MD",
        speciality="Neurology",
    )
    session.add(u)
    session.commit()
    svc = PatientService(PatientRepository(session), session)
    yield svc, u.id
    session.close()


def test_validate_severity_valid(service):
    svc, _ = service
    for valid in ["low", "medium", "high", "Stage 1", "Stage 2", "Stage 5"]:
        errors = svc._validate({"severity": valid})
        assert "severity" not in errors, f"Expected {valid!r} to be valid"


def test_validate_severity_invalid(service):
    svc, _ = service
    for invalid in ["Stage 6", "none", "very high", "1", "Stage"]:
        errors = svc._validate({"severity": invalid})
        assert "severity" in errors, f"Expected {invalid!r} to be invalid"


def test_validate_height_weight(service):
    svc, _ = service
    assert "height" not in svc._validate({"height": 180})
    assert "weight" not in svc._validate({"weight": 70})
    assert "height" in svc._validate({"height": 400})
    assert "weight" in svc._validate({"weight": 600})


def test_parse_number():
    assert _parse_number(180, 0, 300) == 180.0
    assert _parse_number(400, 0, 300) is None
    assert _parse_number("170cm", 0, 300) == 170.0
    assert _parse_number(None, 0, 300) is None
```

- [ ] **Step 2: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests in `test_patient_manager.py`, `test_patient_repository.py`, `test_patient_service.py` pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_patient_manager.py
git commit -m "test: re-target test_patient_manager.py to PatientService"
```

---

## Task 16: Delete dead code

**Files:**
- Delete: `backend/patient_manager.py`
- Delete: `backend/test_history_manager.py`
- Delete: `backend/schema/patient_schema.py`
- Delete: `backend/schema/visit_schema.py`
- Delete: `backend/schema/schema.py`
- Delete: `backend/schema/classifier_schema.py` (moved to routes/)

- [ ] **Step 1: Delete the files**

```bash
rm backend/patient_manager.py
rm backend/test_history_manager.py
rm backend/schema/patient_schema.py
rm backend/schema/visit_schema.py
rm backend/schema/schema.py
rm backend/schema/classifier_schema.py
rmdir backend/schema
```

- [ ] **Step 2: Run all tests to confirm nothing broke**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass; no import errors.

- [ ] **Step 3: Verify app still starts**

```bash
cd backend && python -c "from main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete patient_manager.py, test_history_manager.py, schema/ dead code"
```

---

## Task 17: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

Expected: all tests pass with 0 errors.

- [ ] **Step 2: Verify app starts cleanly**

```bash
cd backend && python -c "
from main import app
print('Routes:')
for route in app.routes:
    if hasattr(route, 'path'):
        print(f'  {route.path}')
"
```

Expected: all routes printed, no errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: backend cleanup complete — DI, config, typed exceptions, SQL test history"
```

---

## Notes for the frontend phase

- `PatientsListResponse` and `PatientSearchResponse` no longer include `success: bool`. Any frontend code checking `response.success` or `response.data.success` will need to be updated to rely on HTTP status codes instead.
- The `/patients/{patient_id}/tests` response shape changed: previously `{"success": True, "tests": [...]}`, now `{"tests": [...]}`.
- All other endpoints and URL paths are unchanged.
