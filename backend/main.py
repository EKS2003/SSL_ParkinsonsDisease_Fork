from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict, List, Optional
from datetime import datetime
import os
import shutil
import uvicorn
from subprocess import run, PIPE
import uuid
import json
import base64
import numpy as np
from uuid import uuid4
from routes.dtw_rest import router as dtw_router
from routes.patient import router as patient_router
from routes.websockets import router as ws_router

from pathlib import Path




# ============ Paths / Folders ============
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# ============ Lazy imports (avoid libGL issues on boot) ============

# ============ Patient Manager ============
from patient_manager import (
    Patient, PatientManager,
    async_create_patient, async_get_patient_info,
    async_update_patient_info, async_delete_patient_record,
    async_get_all_patients_info, async_search_patients,
    async_filter_patients,
    TestHistoryManager
)

app = FastAPI(title="Patient Management API")
app.include_router(dtw_router)
app.include_router(patient_router)
app.include_router(ws_router)

# ============ CORS ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:5174"
    ],  # Adjust this in production to your frontend's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ REST: Health & Patients ============
@app.get("/")
async def root():
    return {"message": "Welcome to the Patient Management API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

# ============ REST: Recordings ============
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
            if f.startswith(f"{patient_id}_{test_name}_") and (f.endswith(".mov") or f.endswith(".mp4"))
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
    media_type = "video/mp4" if filename.endswith(".mp4") else "video/quicktime"
    return FileResponse(file_path, media_type=media_type)

# ============ REST: Start Scripts ============
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

# ============ REST: Test History ============
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

# ============ Uvicorn ============
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)