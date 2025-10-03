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
DTW_BASE        = (PROJECT_BACKEND / "dtw_runs").resolve()
DTW_BASE.mkdir(parents=True, exist_ok=True)

print(f"[DTW REST] DTW_BASE = {DTW_BASE}")

def _test_dir(test_name: str) -> Path:
    p = DTW_BASE / test_name
    if not p.is_dir():
        raise HTTPException(404, f"Unknown test '{test_name}' at {p}")
    return p

def list_sessions(test_name: str) -> List[Dict[str, Any]]:
    root = _test_dir(test_name)
    print(root)
    out: List[Dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text())
            out.append({
                "session_id": d.name,
                "created_utc": meta.get("created_utc"),
                "model": meta.get("model"),
                "live_len": meta.get("live_len"),
                "ref_len": meta.get("ref_len"),
                "distance": meta.get("distance"),
                "similarity": meta.get("similarity"),
            })
        except Exception:
            continue
    # newest first by timestamp string
    return sorted(out, key=lambda x: x.get("created_utc") or "", reverse=True)



def _session_dir(test_name: str, session_id: str) -> Path:
    p = _test_dir(test_name) / session_id
    if not p.is_dir():
        raise HTTPException(404, f"Session '{session_id}' not found under {p.parent}")
    return p

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "base": str(DTW_BASE), "exists": DTW_BASE.exists()}

@router.get("/diag")
def diag() -> Dict[str, Any]:
    return {
        "base": str(DTW_BASE),
        "exists": DTW_BASE.exists(),
        "tests": sorted([d.name for d in DTW_BASE.iterdir() if d.is_dir()]) if DTW_BASE.exists() else []
    }

@router.get("/tests", response_model=List[str])
def list_tests() -> List[str]:
    if not DTW_BASE.exists():
        return []
    return sorted([d.name for d in DTW_BASE.iterdir() if d.is_dir()])

@router.get("/sessions/{test_name}")
def list_sessions(test_name: str) -> List[Dict[str, Any]]:
    root = _test_dir(test_name)
    out: List[Dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text())
            out.append({
                "session_id": d.name,
                "created_utc": meta.get("created_utc"),
                "model": meta.get("model"),
                "live_len": meta.get("live_len"),
                "ref_len": meta.get("ref_len"),
                "distance": meta.get("distance"),
                "similarity": meta.get("similarity"),
            })
        except Exception:
            continue
    # newest first by timestamp string
    return sorted(out, key=lambda x: x.get("created_utc") or "", reverse=True)

@router.get("/sessions/{test_name}/{session_id}/series")
def get_series(
    test_name: str,
    session_id: str,
    max_points: int = Query(200, ge=50, le=2000)
) -> Dict[str, Any]:
    folder = _session_dir(test_name, session_id)
    npz_path, meta_path = folder / "dtw_artifacts.npz", folder / "meta.json"
    if not npz_path.is_file() or not meta_path.is_file():
        raise HTTPException(404, "Artifacts missing")

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception as e:
        raise HTTPException(500, f"Failed to load artifacts: {e}")

    local = npz.get("local_costs")
    align = npz.get("aligned_ref_by_live")
    if local is None or align is None:
        raise HTTPException(500, "Corrupt artifacts: missing arrays")

    try:
        meta = json.loads(meta_path.read_text())
    except Exception as e:
        raise HTTPException(500, f"Failed to read meta.json: {e}")

    def _downsample(arr: np.ndarray, kmax: int = 200) -> Tuple[List[int], List[float]]:
        n = int(arr.shape[0])
        if n <= kmax:
            return list(range(n)), arr.astype(float).tolist()
        step = max(1, n // kmax)
        return list(range(0, n, step)), arr[::step].astype(float).tolist()

    x_lc, y_lc = _downsample(local, max_points)
    cum = (np.cumsum(local, dtype=np.float64) / (float(local.sum()) + 1e-9)).astype(float)

    return {
        "ok": True,
        "testName": test_name,
        "sessionId": session_id,
        "distance": meta.get("distance"),
        "avg_step_cost": meta.get("avg_step_cost"),
        "similarity": meta.get("similarity"),
        "series": {
            "local_cost_path": {"x": x_lc, "y": y_lc},
            "cumulative_progress": {"x": list(range(len(cum))), "y": cum.tolist()},
            "alignment_map": {"x": list(range(len(align))), "y": align.astype(int).tolist()},
        }
    }

@router.get("/sessions/{test_name}/{session_id}/download")
def download_paths(test_name: str, session_id: str) -> Dict[str, str]:
    folder = _session_dir(test_name, session_id)
    return {
        "npz": str(folder / "dtw_artifacts.npz"),
        "meta": str(folder / "meta.json"),
    }

@router.get("/sessions/lookup/{session_id}")
def lookup_session(session_id: str) -> Dict[str, str]:
    if not DTW_BASE.exists():
        raise HTTPException(404, "DTW base not found")
    for t in DTW_BASE.iterdir():
        if not t.is_dir():
            continue
        if (t / session_id).is_dir():
            return {"testName": t.name, "sessionId": session_id}
    raise HTTPException(404, "Session not found")


if(__name__ == "__main__"):
    list_sessions("finger-tapping")