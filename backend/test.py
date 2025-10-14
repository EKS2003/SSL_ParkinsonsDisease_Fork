# backend/routes/dtw_rest.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from pathlib import Path
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/dtw", tags=["dtw"])

# Point to {project}/backend
PROJECT_BACKEND = Path(__file__).resolve().parent               # .../project/backend
TEMPLATES_ROOT  = (PROJECT_BACKEND / "templates").resolve()     # .../backend/templates
DTW_BASE        = (PROJECT_BACKEND / "dtw_runs").resolve()  

print(f"[DTW REST] DTW_BASE = {DTW_BASE}")

print(f"[DTW] TEMPLATES_ROOT = {TEMPLATES_ROOT}")
print(f"[DTW] DTW_BASE       = {DTW_BASE}")


def _test_dir(test_name: str) -> Path:
    p = DTW_BASE / test_name
    print(p)
    if not p.is_dir():
        raise HTTPException(404, f"Unknown test '{test_name}' at {p}")
    return p

def list_sessions(test_name: str) -> List[Dict[str, Any]]:
    p = DTW_BASE / test_name
    p.mkdir(parents=True, exist_ok=True)
    print(f"[DTW REST] Listing sessions in {p}")

if(__name__ == "__main__"):
    list_sessions("finger-tapping")