from fastapi import FastAPI, HTTPException, Body, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
import uvicorn

from core.config import settings
from core.exceptions import PatientNotFoundError, PatientValidationError, DuplicatePatientError
from core.dependencies import get_test_history_service, get_current_user
from repo.db import init_db, SessionLocal
from services.test_history_service import TestHistoryService

from routes.dtw_rest import router as dtw_router
from routes.patient import router as patient_router
from routes.websockets import router as ws_router
from routes.classifier import router as classifier_router
from routes.patient_media import router as media_router

from pydantic import BaseModel, field_validator

from auth import authenticate, create_access_token, hash_password
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
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    location: str = ""
    title: str = ""
    speciality: str = ""

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer")
        return v


@app.post("/register", status_code=201)
async def register(user_data: UserCreate):
    with SessionLocal() as session:
        if session.query(User).filter_by(username=user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        new_user = User(
            username=user_data.email,
            full_name=user_data.full_name,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            location=user_data.location,
            title=user_data.title,
            speciality=user_data.speciality,
        )
        session.add(new_user)
        session.commit()
    access_token = create_access_token(sub=user_data.email)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(sub=user.username)
    return {"access_token": access_token, "token_type": "bearer"}


# ── Me ───────────────────────────────────────────────────────────────────────
@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "email": current_user.email or "",
        "full_name": current_user.full_name or "",
        "title": current_user.title or "",
        "speciality": current_user.speciality or "",
        "location": current_user.location or "",
        "profile_image": current_user.profile_image or "",
    }


@app.put("/me/avatar")
async def update_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(status_code=400, detail="Unsupported image type")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 5 MB")
    data_url = f"data:{file.content_type};base64,{base64.b64encode(contents).decode()}"
    with SessionLocal() as session:
        user = session.get(User, current_user.id)
        user.profile_image = data_url
        session.commit()
    return {"profile_image": data_url}


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
