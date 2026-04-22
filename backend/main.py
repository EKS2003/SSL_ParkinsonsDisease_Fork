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
