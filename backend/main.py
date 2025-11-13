from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict, List, Optional, Annotated
from datetime import datetime, timedelta
import os
import shutil
import uvicorn

from routes.dtw_rest import router as dtw_router
from routes.patient import router as patient_router
from routes.websockets import router as ws_router
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from repo.sql_models import User
from repo.db import engine
from jose import jwt, JWTError
from passlib.context import CryptContext
from patient_manager import SessionLocal

# ============ Paths / Folders ============
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# ============ Lazy imports (avoid libGL issues on boot) ============

# ============ Patient Manager ============
from patient_manager import (
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

SECRET_KEY = "stupid_hash_for_now"
ALGO = "HS256"
ACCESS_MIN = 30

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def authenticate(username: str, password: str) -> User | None:
    try:
        with SessionLocal() as session:
            user = session.query(User).filter_by(username=username).first()
            if user and pwd.verify(password, user.hashed_password):
                return user
    except Exception as e:
        return {"error": "Failed to auth"}
    
def create_access_token(sub: str) -> str:
    to_encode = {
        "sub": sub, 
        "exp": datetime.now() + timedelta(minutes=ACCESS_MIN)
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGO)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")   
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user
    
@app.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(sub=user.username)
    return {"access_token": access_token, "token_type": "bearer"}
# ============ REST: Health & Patients ============
@app.get("/")
async def root():
    return {"message": "Welcome to the Patient Management API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

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