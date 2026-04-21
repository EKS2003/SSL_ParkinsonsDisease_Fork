# Backend Cleanup & DI Design

**Date:** 2026-04-21  
**Branch:** ml-demo-refactor  
**Scope:** Backend only (frontend is a separate phase)

## Goals

- Clean up the existing structure without a full folder reorganization
- Introduce dependency injection via FastAPI's native `Depends()`
- Add configuration management for multi-deployment (local, Docker, cloud)
- Add typed error handling with global exception handlers
- Migrate `TestHistoryManager` from JSON to SQL
- Consolidate duplicate schemas
- Run existing tests green after refactor

---

## 1. Folder Structure

Minimal changes to the existing tree. A new `core/` directory is introduced. `patient_manager.py` is replaced by `services/patient_service.py`. The `schema/` directory is deleted (unused dead code). `test_history_manager.py` is deleted.

```
backend/
  core/
    config.py               ← NEW: Pydantic BaseSettings
    exceptions.py           ← NEW: Custom domain exceptions
    dependencies.py         ← NEW: FastAPI Depends() wiring
  repo/
    db.py                   ← UPDATED: DB setup moved here from patient_manager.py
    sql_models.py           ← unchanged
    patient_repository.py   ← unchanged
    test_repository.py      ← unchanged
  services/
    patient_service.py      ← NEW: PatientService class (replaces patient_manager.py)
    test_history_service.py ← NEW: replaces TestHistoryManager, uses SQL
  routes/
    contracts.py            ← unchanged (single source of schemas)
    patient.py              ← UPDATED: uses Depends(get_patient_service)
    websockets.py           ← UPDATED: uses Depends(get_test_history_service)
    patient_media.py        ← NEW: video upload/listing routes (moved from main.py)
    classifier.py           ← unchanged
    dtw_rest.py             ← unchanged
  auth.py                   ← UPDATED: imports from core/ only
  main.py                   ← UPDATED: no inline routes, only includes + middleware + handlers
  patient_manager.py        ← DELETED
  test_history_manager.py   ← DELETED
  schema/                   ← DELETED (all contents unused)
```

---

## 2. Configuration Management

`core/config.py` uses Pydantic `BaseSettings`. Values are read from environment variables, with a `.env` file fallback for local development.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
```

**Deployment scenarios:**
- **Local dev:** `.env` file with overrides (gitignored)
- **Docker:** container env vars (`DB_URL`, `SECRET_KEY`, etc.)
- **Cloud (Render, Railway, AWS):** platform env var dashboard

All hardcoded values in `auth.py` (`SECRET_KEY`, `ACCESS_MIN`) and `patient_manager.py` (`DB_URL`) are replaced with `settings.*` references.

---

## 3. Error Handling

Services raise typed exceptions. A set of global handlers in `main.py` converts them to proper HTTP responses. The `{"success": bool}` dict pattern is removed from service return values.

**Exceptions (`core/exceptions.py`):**
```python
class PatientNotFoundError(Exception):
    def __init__(self, patient_id: str): self.patient_id = patient_id

class PatientValidationError(Exception):
    def __init__(self, errors: dict): self.errors = errors

class DuplicatePatientError(Exception):
    pass
```

**Handlers registered in `main.py`:**
- `PatientNotFoundError` → 404
- `PatientValidationError` → 422
- `DuplicatePatientError` → 409

Routes no longer check `result.get("success")`. The `success: bool` field is removed from response models since HTTP status codes carry that meaning.

---

## 4. Dependency Injection

`core/dependencies.py` is the single wiring point. FastAPI's `Depends()` handles injection — no external DI library.

```python
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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    # auth logic moved here from auth.py
    ...
```

`PatientService` receives its dependencies through `__init__`:

```python
class PatientService:
    def __init__(self, repo: PatientRepository, db: Session): ...
```

**Key wins:**
- No more global `SessionLocal()` calls inside business logic
- No more `async_*` wrapper functions — async routes call service methods directly
- `auth.py` no longer imports from `patient_manager.py` (circular coupling removed)
- Tests inject a fake repo without monkeypatching globals

---

## 5. TestHistoryManager → SQL

`TestHistoryManager` (JSON singleton) is replaced by `TestHistoryService` which uses the existing `TestResult` SQL table.

```python
class TestHistoryService:
    def __init__(self, db: Session): self.db = db

    def get_patient_tests(self, patient_id: str) -> list[TestResult]:
        return self.db.query(TestResult).filter_by(patient_id=patient_id).all()

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
```

`websockets.py` replaces its `TestHistoryManager.get_instance()` call with `Depends(get_test_history_service)`.

Existing `test_history.json` data is **not** migrated — out of scope.

---

## 6. Schema Consolidation

`schema/` directory is deleted. `routes/contracts.py` is the single source of all Pydantic request/response models. No behavior changes to existing schemas.

---

## Testing Strategy

- Run existing tests (`pytest`) before and after each step to confirm nothing regresses
- Update `test_patient_manager.py` to import from `services/patient_service.py` instead of `patient_manager.py`
- Update `test_patient_repository.py` — no changes needed (repo is unchanged)
- New unit tests for `PatientService` methods using an in-memory SQLite session (same pattern as existing repo tests)

---

## Out of Scope

- Frontend refactor (separate phase)
- Migration of `test_history.json` data to SQL
- Changes to ML/DTW/classifier logic
- Database migrations (schema is unchanged)
