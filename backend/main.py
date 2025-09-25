from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime,date
import os
import shutil
import uvicorn
from subprocess import run, PIPE
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


from repo.sql_models import Base, Patient, Visit
from repo.patient_repository import PatientRepository
from repo.visit_repository import VisitRepository
from repo.excel_to_repository import ExcelToRepository


from schema.patient_schema import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientsListResponse,
)

from schema.visit_schema import (
    VisitCreate,
    VisitUpdate,
    VisitResponse,
    VisitsListResponse,
)

from test_history_manager import TestHistoryManager

# setting up recording directory
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# SQLAlchemy session setup

engine = create_engine("sqlite:///./test.db", echo=True, future=True)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally:
        db.close()


#FastAPI app setup
app = FastAPI(title="Patient Management API")

# Configure CORS to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:5173",  # Vite default port
        "http://localhost:3000",  # React default port
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],  # Adjust this in production to your frontend's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation
#Metric units: height in cm, weight in kg



# API Routes
@app.get("/")
async def root():
    return {"message": "Welcome to the Patient Management API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}


@app.post("/patients/", status_code=201, response_model=PatientResponse)
async def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    # Convert types to match async_create_patient signature
    # Handle height conversion - try to convert to float, keep as string if it fails
    try:
        height = float(payload.height) if payload.height is not None else 0.0
    except ValueError:
        height = 0.0  # Default if conversion fails
    
    # Handle weight conversion - try to convert to float, keep as string if it fails
    try:
        weight = float(payload.weight) if payload.weight is not None else 0.0
    except ValueError:
        weight = 0.0  # Default if conversion fails
        
    repo = PatientRepository(db)

    patient = Patient(
        patient_id=payload.patient_id,
        name=payload.name,
        dob=payload.dob,  # DOB not provided in PatientCreate
        height=int(height) if isinstance(height, float) else None,
        weight=int(weight) if isinstance(weight, float) else None,
    )
    try:
        created_patient = repo.add(patient)
        return created_patient
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/patients/", response_model=PatientsListResponse)
async def get_patients(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db)
):
    repo = PatientRepository(db)
    patients = repo.list(skip=skip, limit=limit)
    return PatientsListResponse(
        success=True,
        patients=patients,
        total=len(patients)
        )

@app.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str, db: Session = Depends(get_db)):
    repo = PatientRepository(db)
    patient = repo.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.put("/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: str, patient_update: PatientUpdate, db: Session = Depends(get_db)):
    # Convert Pydantic model to dict, excluding None values
    repo = PatientRepository(db)
    patient = repo.update(patient_id, patient_update.model_dump(exclude_unset=True))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.delete("/patients/{patient_id}", status_code=204)
def delete_patient(
    patient_id: str, db: Session = Depends(get_db)
) -> None:
    repo = PatientRepository(db)
    success = repo.delete(patient_id)
    if not success:
        raise HTTPException(status_code=404, detail="Patient not found")

'''
@app.get("/patients/search/{query}", response_model=PatientSearchResponse)
async def search_patients_endpoint(query: str):
    return await async_search_patients(query)


@app.post("/patients/filter/", response_model=PatientSearchResponse)
async def filter_patients_endpoint(criteria: FilterCriteria):
    return await async_filter_patients(criteria.dict(exclude_none=True))
'''

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

@app.post("/upload-video/")
async def upload_video(
    patient_id: str = Form(...),
    test_name: str = Form(...),
    video: UploadFile = File(...)
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
def list_videos(patient_id: str, test_name: str):
    try:
        files = os.listdir(RECORDINGS_DIR)
        matching = [
            f for f in files
            if f.startswith(f"{patient_id}_{test_name}_") and f.endswith(".mov")
        ]
        matching.sort(
            key=lambda f: os.path.getmtime(os.path.join(RECORDINGS_DIR, f)),
            reverse=True
        )
        return {"success": True, "videos": matching}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/recordings/{filename}", response_class=FileResponse)
def get_recording_file(filename: str):
    file_path = os.path.join(RECORDINGS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(file_path, media_type="video/quicktime")

@app.post("/start-test/")
async def start_test(patient_id: str = Form(...), test_name: str = Form(...)):
    """
    Start a test by running the appropriate script based on test_name.
    Returns output or error from the script.
    """
    script_map = {
        "finger-tapping": os.path.join(os.path.dirname(__file__), "finger_tapping.py"),
        "fist-open-close": os.path.join(os.path.dirname(__file__), "fist_open_close.py"),
    }
    script_path = script_map.get(test_name)
    if not script_path or not os.path.exists(script_path):
        return {"success": False, "error": f"Unknown or missing script for test: {test_name}"}

    try:
        result = run(["python", script_path], stdout=PIPE, stderr=PIPE, text=True, check=False)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

## Frontend -> Backend() -> Frontend 
@app.get("/patients/{patient_id}/tests", response_model=Dict)
async def get_patient_tests(patient_id: str):
    thm = TestHistoryManager()
    tests = thm.get_patient_tests(patient_id)
    return {"success": True, "tests": tests}

@app.post("/patients/{patient_id}/tests", response_model=Dict)
async def add_patient_test(patient_id: str, test_data: dict = Body(...)):
    thm = TestHistoryManager()
    thm.add_patient_test(patient_id, test_data)
    return {"success": True}


@app.post("/visit/", response_model=Dict)
async def create_visit(payload: VisitCreate, db: Session = Depends(get_db)):
    visit_repo = VisitRepository(db)
    patient_repo = PatientRepository(db)
    patient = patient_repo.get(payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
   
    try:
        visit = Visit(
            patient_id=payload.patient_id,
            visit_date=payload.visit_date,
            progression_note=payload.progression_note,
            doctor_notes=payload.doctor_notes,
            vitals_json=payload.vitals_json,
            status=payload.status
        )
        visit_repo.add(visit)
        return {"success": True, "visits": patient.visits}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/visit/", response_model=VisitsListResponse)
async def get_visits(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db)
):
    visit_repo = VisitRepository(db)
    visits = visit_repo.list(skip=skip, limit=limit)
    return VisitsListResponse(
        success=True,
        visits=visits,
        total=len(visits),
        skip=skip,
        limit=limit
    )


@app.post("/import-excel/")
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    importer = ExcelToRepository(db)
    workbook = importer.load_workbook_from_bytes(data)
    try:
        importer.import_workbook(workbook)
        return {"success": True, "message": f"{file.filename} imported successfully"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))