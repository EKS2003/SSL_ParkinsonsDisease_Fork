# backend/routes/dtw_rest.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
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

def _session_dir(test_name: str, session_id: str) -> Path:
    p = _test_dir(test_name) / session_id
    if not p.is_dir():
        raise HTTPException(404, f"Session '{session_id}' not found under {p.parent}")
    return p

# --- add these helpers anywhere above the endpoint (e.g., near other helpers) ---
def _apply_reduce(arr: np.ndarray, how: str) -> np.ndarray:
    how = (how or "mean").lower()
    if how == "mean":
        return arr.mean(axis=1)
    if how == "median":
        return np.median(arr, axis=1)
    if how == "sum":
        return arr.sum(axis=1)
    if how == "min":
        return arr.min(axis=1)
    if how == "max":
        return arr.max(axis=1)
    raise HTTPException(400, f"Unsupported reduce='{how}' (use mean|median|sum|min|max)")

def _parse_landmarks_param(landmarks: str | None, model: str, points: int) -> list[int]:
    """
    Accepts:
      - None or "all": all landmarks (0..points-1)
      - CSV like "1,2,3" (0-based indices for pose 0..32; hands 0..20)
    Returns 0-based positions inside the flattened feature vector.
    """
    if landmarks is None or str(landmarks).lower() == "all":
        return list(range(points))

    raw = [s.strip() for s in str(landmarks).split(",") if s.strip() != ""]
    try:
        req = [int(s) for s in raw]
    except ValueError:
        raise HTTPException(400, f"Invalid landmarks list '{landmarks}'. Use 'all' or CSV of integers.")

    for lm in req:
        if not (0 <= lm < points):
            raise HTTPException(400, f"landmark {lm} out of range 0..{points-1} for model {model}")
    return req


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
    raise HTTPException(404, {"error": str(DTW_BASE)})

def _infer_points_and_kpp(D: int, model: str) -> Tuple[int, int]:
    """
    Infer (#points, dims-per-point) from feature dimension D and model.
    - pose: 33 points
    - hands: 21 points (full Mediapipe hand)
    """
    model = (model or "").lower()
    if model == "pose":
        points = 33
        if D % points != 0:
            raise HTTPException(500, f"Template dimension {D} not divisible by pose points {points}")
        return points, D // points

    if model == "hands":
        points = 21
        if D % points != 0:
            raise HTTPException(500, f"Template dimension {D} not divisible by hands points {points}")
        return points, D // points

    raise HTTPException(500, f"Unknown model '{model}' in meta.json")

def _downsample_xy(x: np.ndarray, y: np.ndarray, kmax: int) -> Tuple[List[int], List[float]]:
    n = int(len(x))
    if n <= kmax:
        return x.astype(int).tolist(), y.astype(float).tolist()
    step = max(1, n // kmax)
    return x[::step].astype(int).tolist(), y[::step].astype(float).tolist()

@router.get("/sessions/{test_name}/{session_id}/channel")
def get_channel_series(
    test_name: str,
    session_id: str,
    landmark: int = Query(0, ge=0, description="0..20 for hands; 0..32 for pose"),
    axis: str = Query("x", regex="^(x|y|z)$"),
    max_points: int = Query(400, ge=50, le=3000),
) -> Dict[str, Any]:
    """
    Returns original live/ref series for a single channel (landmark+axis),
    along with the DTW path and the aligned (warped) pair series.
    """
    folder = _session_dir(test_name, session_id)
    npz_path, meta_path = folder / "dtw_artifacts.npz", folder / "meta.json"
    if not npz_path.is_file() or not meta_path.is_file():
        raise HTTPException(404, "Artifacts missing")

    try:
        npz = np.load(npz_path, allow_pickle=False)
        X_live = npz["X_live"]          # (T_live, D)
        Y_ref  = npz["Y_ref"]           # (T_ref, D)
        path   = npz["path"]            # (L, 2) int32
    except Exception as e:
        raise HTTPException(500, f"Failed to load artifacts: {e}")

    try:
        meta = json.loads(meta_path.read_text())
        model = (meta.get("model") or "pose").lower()
    except Exception as e:
        raise HTTPException(500, f"Failed to read meta.json: {e}")

    T_live, D = int(X_live.shape[0]), int(X_live.shape[1])
    T_ref     = int(Y_ref.shape[0])
    points, kpp = _infer_points_and_kpp(D, model)

    if not (0 <= landmark < points):
        raise HTTPException(400, f"landmark index {landmark} out of range 0..{points-1}")

    axis_idx = {"x": 0, "y": 1, "z": 2}.get(axis, 0)
    if kpp <= axis_idx:
        # z requested but features are 2D, or bad axis
        raise HTTPException(400, f"axis '{axis}' not available (dims-per-point={kpp})")

    d_index = landmark * kpp + axis_idx

    # Original series (indices are frame numbers)
    live_y = X_live[:, d_index]
    ref_y  = Y_ref[:,  d_index]
    live_x = np.arange(T_live, dtype=np.int32)
    ref_x  = np.arange(T_ref,  dtype=np.int32)

    # Aligned (warped) pairs along the DTW path
    i_idx = path[:, 0].astype(np.int32)
    j_idx = path[:, 1].astype(np.int32)
    k_idx = np.arange(len(path), dtype=np.int32)

    warped_live = live_y[i_idx]
    warped_ref  = ref_y[j_idx]

    # Downsample for plotting
    live_x_ds, live_y_ds = _downsample_xy(live_x, live_y, max_points)
    ref_x_ds,  ref_y_ds  = _downsample_xy(ref_x,  ref_y,  max_points)

    if len(k_idx) > max_points:
        step = max(1, len(k_idx) // max_points)
        k_idx_ds = k_idx[::step]
        i_idx_ds = i_idx[::step]
        j_idx_ds = j_idx[::step]
        warped_live_ds = warped_live[::step]
        warped_ref_ds  = warped_ref[::step]
    else:
        k_idx_ds = k_idx
        i_idx_ds = i_idx
        j_idx_ds = j_idx
        warped_live_ds = warped_live
        warped_ref_ds  = warped_ref

    return {
        "ok": True,
        "model": model,
        "D": D,
        "points": points,
        "dims_per_point": kpp,
        "channel": {"landmark": landmark, "axis": axis, "d_index": int(d_index)},
        "live": {"x": [int(v) for v in live_x_ds], "y": [float(v) for v in live_y_ds]},
        "ref":  {"x": [int(v) for v in ref_x_ds],  "y": [float(v) for v in ref_y_ds]},
        "warped": {
            "k":  [int(v) for v in k_idx_ds],
            "live": [float(v) for v in warped_live_ds],
            "ref":  [float(v) for v in warped_ref_ds],
        },
        "path": {
            "i": [int(v) for v in i_idx_ds],
            "j": [int(v) for v in j_idx_ds],
        }
    }

   
# --- Aggregate one axis across many (or all) landmarks into a 1D series ---
@router.get("/sessions/{test_name}/{session_id}/axis_agg")
def get_axis_aggregate(
    test_name: str,
    session_id: str,
    axis: str = Query("x", regex="^(x|y|z)$"),
    landmarks: str | None = Query(
        None,
        description="Use 'all' or CSV (e.g., '0,1,2'). Hands: 0..20. Pose: 0..32."
    ),
    reduce: str = Query("mean", description="Aggregation over selected landmarks per frame: mean|median|sum|min|max"),
    max_points: int = Query(600, ge=50, le=5000),
) -> Dict[str, Any]:
    folder = _session_dir(test_name, session_id)
    npz_path, meta_path = folder / "dtw_artifacts.npz", folder / "meta.json"
    if not npz_path.is_file() or not meta_path.is_file():
        raise HTTPException(404, "Artifacts missing")

    try:
        npz = np.load(npz_path, allow_pickle=False)
        X_live = npz["X_live"]          # (T_live, D)
        Y_ref  = npz["Y_ref"]           # (T_ref, D)
        path   = npz["path"]            # (L, 2) int32
    except Exception as e:
        raise HTTPException(500, f"Failed to load artifacts: {e}")

    try:
        meta = json.loads(meta_path.read_text())
        model = (meta.get("model") or "pose").lower()
    except Exception as e:
        raise HTTPException(500, f"Failed to read meta.json: {e}")

    T_live, D = int(X_live.shape[0]), int(X_live.shape[1])
    T_ref     = int(Y_ref.shape[0])
    points, kpp = _infer_points_and_kpp(D, model)

    axis_idx = {"x": 0, "y": 1, "z": 2}.get(axis, 0)
    if kpp <= axis_idx:
        raise HTTPException(400, f"axis '{axis}' not available (dims-per-point={kpp})")

    # Resolve landmarks (supports 'all' and CSV)
    lm_positions = _parse_landmarks_param(landmarks, model, points)
    if len(lm_positions) == 0:
        raise HTTPException(400, "No valid landmarks selected for aggregation")

    # Compute channel indices for chosen axis and aggregate per frame
    d_indices = np.asarray([lm * kpp + axis_idx for lm in lm_positions], dtype=np.int32)
    live_mat = X_live[:, d_indices]
    ref_mat  = Y_ref[:,  d_indices]
    live_series = _apply_reduce(live_mat, reduce).astype(np.float32)
    ref_series  = _apply_reduce(ref_mat,  reduce).astype(np.float32)

    # Original x-axes
    live_x = np.arange(T_live, dtype=np.int32)
    ref_x  = np.arange(T_ref,  dtype=np.int32)

    # Warped series along DTW path
    i_idx = path[:, 0].astype(np.int32)
    j_idx = path[:, 1].astype(np.int32)
    k_idx = np.arange(len(path), dtype=np.int32)
    warped_live = live_series[i_idx]
    warped_ref  = ref_series[j_idx]

    # Downsample for plotting
    live_x_ds, live_y_ds = _downsample_xy(live_x, live_series, max_points)
    ref_x_ds,  ref_y_ds  = _downsample_xy(ref_x,  ref_series,  max_points)

    if len(k_idx) > max_points:
        step = max(1, len(k_idx) // max_points)
        k_idx_ds = k_idx[::step]
        i_idx_ds = i_idx[::step]
        j_idx_ds = j_idx[::step]
        warped_live_ds = warped_live[::step]
        warped_ref_ds  = warped_ref[::step]
    else:
        k_idx_ds = k_idx
        i_idx_ds = i_idx
        j_idx_ds = j_idx
        warped_live_ds = warped_live
        warped_ref_ds  = warped_ref

    return {
        "ok": True,
        "model": model,
        "D": D,
        "points": points,
        "dims_per_point": kpp,
        "axis": axis,
        "reduce": reduce,
        "landmarks_in": "all" if (landmarks is None or str(landmarks).lower()=="all") else landmarks,
        "resolved_positions": [int(v) for v in lm_positions],
        "live": {"x": [int(v) for v in live_x_ds], "y": [float(v) for v in live_y_ds]},
        "ref":  {"x": [int(v) for v in ref_x_ds],  "y": [float(v) for v in ref_y_ds]},
        "warped": {
            "k":  [int(v) for v in k_idx_ds],
            "live": [float(v) for v in warped_live_ds],
            "ref":  [float(v) for v in warped_ref_ds],
        },
        "path": {
            "i": [int(v) for v in i_idx_ds],
            "j": [int(v) for v in j_idx_ds],
        }
    }