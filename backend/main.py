from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict
from datetime import datetime
import os
import shutil
import uvicorn
from sqlalchemy.exc import IntegrityError
from fastapi.staticfiles import StaticFiles


from routes.dtw_rest import router as dtw_router
from routes.patient import router as patient_router
from routes.websockets import router as ws_router
from routes import websockets 
from routes import videos
from fastapi.security import  OAuth2PasswordRequestForm
from repo.sql_models import User,TestResult, Patient
from patient_manager import SessionLocal
from schema.user import UserSignup
from auth import authenticate, create_access_token, pwd, get_current_user
from uuid import uuid4



# ============ Paths / Folders ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(BASE_DIR, "routes", "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# ============ Lazy imports (avoid libGL issues on boot) ============

# ============ Patient Manager ============


app = FastAPI(title="Patient Management API")
app.include_router(dtw_router)
app.include_router(patient_router)
app.include_router(ws_router)
app.include_router(videos.router)


# ============ CORS ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:5174",  # Add this line
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",  # Add this line too
        "http://127.0.0.1:3000",
        "http://localhost:8001",
        "http://localhost:8000/patients",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





    
@app.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(sub=user.username)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/signup", status_code=201)
async def signup(user_in: UserSignup):
    """
    Create a new user account and return a JWT so the frontend can log in immediately.
    """
    with SessionLocal() as session:
        # Check for existing username / email
        existing = (
            session.query(User)
            .filter(
                (User.username == user_in.username) |
                (User.email == user_in.email)
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username or email already registered."
            )

        # Hash password and create user
        hashed_pw = pwd.hash(user_in.password)
        user = User(
            username=user_in.username,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            email=user_in.email,
            hashed_password=hashed_pw,
            location=user_in.location,
            title=user_in.title,
            speciality=user_in.speciality,
            department=user_in.department,
        )

        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # In case of a race condition on unique constraints
            raise HTTPException(
                status_code=400,
                detail="Username or email already registered."
            )

        session.refresh(user)

    # Optional: immediately issue an access token like /token does
    access_token = create_access_token(sub=user.username)
    return {
        "ok": True,
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "access_token": access_token,
        "token_type": "bearer",
    }
# ============ REST: Health & Patients ============
@app.get("/")
async def root():
    return {"message": "Welcome to the Patient Management API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

# ============ REST: Test History ============
# ============ REST: Test History ============
@app.get("/patients/{patient_id}/tests", response_model=Dict)
async def get_patient_tests(
    patient_id: str,
    current_user=Depends(get_current_user),
):
    """
    Return all TestResult rows for this patient (only if they belong to current_user).
    """
    with SessionLocal() as session:
        patient = (
            session.query(Patient)
            .filter(
                Patient.patient_id == patient_id,
                Patient.user_id == current_user.id,
            )
            .first()
        )
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        results = (
            session.query(TestResult)
            .filter(TestResult.patient_id == patient_id)
            .order_by(TestResult.test_date.desc().nullslast())
            .all()
        )

        tests = []
        for r in results:
            tests.append(
                {
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_name": r.test_name,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "model": r.model,
                    "fps": r.fps,
                    "recording_file": r.recording_file,
                    "frame_count": r.frame_count,
                    "similarity_overall": r.similarity_overall,
                    "similarity_pos": r.similarity_pos,
                    "similarity_amp": r.similarity_amp,
                    "similarity_spd": r.similarity_spd,
                    "distance_pos": r.distance_pos,
                    "distance_amp": r.distance_amp,
                    "distance_spd": r.distance_spd,
                    "avg_step_pos": r.avg_step_pos,
                }
            )

    return {"success": True, "tests": tests}


@app.post("/patients/{patient_id}/tests", response_model=Dict)
async def add_patient_test(
    patient_id: str,
    test_data: dict = Body(...),
    current_user=Depends(get_current_user),
):
    """
    Insert a new TestResult row for this patient.
    test_data can contain any TestResult fields (similarities, distances, series, etc.).
    """
    with SessionLocal() as session:
        patient = (
            session.query(Patient)
            .filter(
                Patient.patient_id == patient_id,
                Patient.user_id == current_user.id,
            )
            .first()
        )
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        allowed_fields = {
            "test_id",
            "test_name",
            "test_date",
            "model",
            "fps",
            "recording_file",
            "frame_count",
            "similarity_overall",
            "similarity_pos",
            "similarity_amp",
            "similarity_spd",
            "distance_pos",
            "distance_amp",
            "distance_spd",
            "avg_step_pos",
            "R_pos",
            "R_amp",
            "R_spd",
            "L_pos",
            "L_amp",
            "L_spd",
            "pos_local_costs",
            "pos_aligned_ref_by_live",
            "amp_local_costs",
            "amp_aligned_ref_by_live",
            "spd_local_costs",
            "spd_aligned_ref_by_live",
        }

        data = {k: v for k, v in test_data.items() if k in allowed_fields}

        # Generate a test_id if not provided
        if not data.get("test_id"):
            data["test_id"] = test_data.get("session_id") or f"test-{uuid4().hex}"

        # Parse test_date if it's a string
        if "test_date" in data and isinstance(data["test_date"], str):
            try:
                data["test_date"] = datetime.fromisoformat(data["test_date"])
            except ValueError:
                data["test_date"] = datetime.utcnow()

        result = TestResult(
            patient_id=patient_id,
            **data,
        )
        session.add(result)
        session.commit()
        session.refresh(result)

        return {
            "success": True,
            "test_id": result.test_id,
        }




# ============ REST: Recordings ============
# ============ REST: Recordings ============
@app.post("/upload-video/")
async def upload_video(
    patient_id: str = Form(...),
    test_name: str = Form(...),
    video: UploadFile = File(...),
    current_user=Depends(get_current_user),
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
            "test_name": test_name
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/videos/{patient_id}/{test_name}", response_model=Dict)
def list_videos(
    patient_id: str,
    test_name: str,
    current_user=Depends(get_current_user),
):
    try:
        with SessionLocal() as session:
            patient = (
                session.query(Patient)
                .filter(
                    Patient.patient_id == patient_id,
                    Patient.user_id == current_user.id,
                )
                .first()
            )
            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")

            results = (
                session.query(TestResult)
                .filter(
                    TestResult.patient_id == patient_id,
                    TestResult.test_name == test_name,
                    TestResult.recording_file != None
                )
                .all()
            )

            matching = []
            for r in results:
                matching.append({
                    "test_id": r.test_id,
                    "recording_file": r.recording_file,
                })
        return {"success": True, "videos": matching}
    except Exception as e:
        return {"success": False, "error": str(e)}

app.mount(
    "/recordings",
    StaticFiles(directory=websockets.RECORDINGS_DIR),
    name="recordings",
)

@app.get("/recordings/{patient_id}/{test_id}", response_class=FileResponse)
def get_recording_file(
    patient_id: str,
    test_id: str,
    current_user=Depends(get_current_user),
):
    
    try:
        with SessionLocal() as session:
            patient = (
                session.query(Patient)
                .filter(
                    Patient.patient_id == patient_id,
                    Patient.user_id == current_user.id,
                )
                .first()
            )
            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")

            result = (
                session.query(TestResult)
                .filter(
                    TestResult.patient_id == patient_id,
                    TestResult.test_id == test_id,
                )
                .first()
            )
            if not result or not result.recording_file:
                raise HTTPException(status_code=404, detail="Video not found")
            filename = result.recording_file
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    media_type = "video/mp4" if filename.endswith(".mp4") else "video/quicktime"
    return FileResponse(file_path, media_type=media_type)

# ============ Uvicorn ============
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)