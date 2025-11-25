# routes/videos.py
from fastapi import APIRouter
from typing import List
from patient_manager import SessionLocal
from repo.sql_models import TestResult
from routes.utils_dtw import normalize_test_name
from .websockets import RECORDINGS_DIR

router = APIRouter(prefix="/videos", tags=["videos"])

@router.get("/{patient_id}/{test_key}")
def list_videos(patient_id: str, test_key: str):
    """
    Return all recording filenames for a given patient + test.
    The frontend will turn these into /recordings/<filename> URLs.
    """
    norm = normalize_test_name(test_key)

    with SessionLocal() as db:
        q = (
            db.query(TestResult)
            .filter(
                TestResult.patient_id == patient_id,
                TestResult.test_name == norm,
            )
            .order_by(TestResult.test_date.desc())
        )
        filenames: List[str] = [
            tr.recording_file
            for tr in q
            if tr.recording_file  # may be NULL for older rows
        ]

    return {"success": True, "videos": filenames}
