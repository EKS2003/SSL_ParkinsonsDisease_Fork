# backend/routes/dtw_rest.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import os

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import func

from repo.sql_models import TestResult
from patient_manager import SessionLocal as DBSession
from auth import get_current_user
router = APIRouter(prefix="/dtw", tags=["dtw"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_scope() -> OrmSession:
    """Small helper to create/close a DB session."""
    db = DBSession()
    return db


def _json_list(value: Any, key: str = "values") -> List:
    """
    Normalise JSON column into a plain Python list.

    Accepts:
      - None -> []
      - list -> as is
      - {"values": [...]} -> that list (default key) or given key
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        v = value.get(key)
        if isinstance(v, list):
            return v
    return []


def _downsample(series: List[float], max_points: int) -> List[float]:
    if not series:
        return []
    n = len(series)
    if n <= max_points:
        return series
    step = max(1, n // max_points)
    idxs = list(range(0, n, step))[:max_points]
    return [series[i] for i in idxs]


def _series_bundle(
    local_costs: List[float],
    aligned_idx: List[int],
    max_points: int,
) -> Dict[str, Any]:
    """
    Build the structure expected by the frontend for a single series.
    We only have per-step local costs + the mapping from each live
    index to some reference index.
    """
    local_costs = list(local_costs or [])
    aligned_idx = list(aligned_idx or [])
    n = len(local_costs)

    if n == 0:
        return {"local_costs": [], "alignment_map": {"x": [], "y": []}}

    # When downsampling, we keep the relative shape and subsample alignment.
    if n > max_points:
        step = max(1, n // max_points)
        idxs = list(range(0, n, step))[:max_points]
    else:
        idxs = list(range(n))

    ds_costs = [local_costs[i] for i in idxs]
    if aligned_idx and len(aligned_idx) == n:
        ds_align = [aligned_idx[i] for i in idxs]
    else:
        # fallback: simple diagonal mapping
        ds_align = idxs

    xs = list(range(len(ds_costs)))
    return {
        "local_costs": ds_costs,
        "alignment_map": {"x": xs, "y": ds_align},
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> Dict[str, Any]:
    """Simple health check for the DTW REST endpoints."""
    # We don't touch the DB here; just report basic metadata.
    return {"ok": True, "backend": "sql", "model": "TestResult"}


@router.get("/diag")
def diag(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return a tiny diagnostic snapshot about stored DTW runs."""
    db = _session_scope()
    try:
        total = db.query(TestResult).count()
        by_test = (
            db.query(TestResult.test_name, func.count(TestResult.test_id))
            .group_by(TestResult.test_name)
            .all()
        )
        return {
            "backend": "sql",
            "total_runs": total,
            "tests": {name or "": count for name, count in by_test},
        }
    finally:
        db.close()


@router.get("/tests", response_model=List[str])
def list_tests(current_user=Depends(get_current_user)) -> List[str]:
    """
    List all distinct test names that have DTW/TestResult entries.

    Previously this scanned folders under backend/dtw_runs; now it
    just uses DISTINCT test_name from the TestResult table.
    """
    db = _session_scope()
    try:
        rows = db.query(TestResult.test_name).distinct().all()
        tests = sorted(
            {name for (name,) in rows if name is not None and str(name).strip() != ""}
        )
        return tests
    finally:
        db.close()


@router.get("/sessions/{test_name}")
def list_sessions(
    test_name: str,
    current_user=Depends(get_current_user),
) -> List[Dict[str, Any]]:

    """
    List all DTW sessions for a given test name.

    A "session" here is just a row in testresults for that test_name.
    We expose test_id as the session_id so existing frontend routes
    can keep working with minimal changes.
    """
    db = _session_scope()
    try:
        rows = (
            db.query(TestResult)
            .filter(TestResult.test_name == test_name)
            .order_by(TestResult.test_date.desc().nullslast())
            .all()
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "session_id": r.test_id,  # already string
                    "test_id": r.test_id,
                    "patient_id": r.patient_id,
                    "test_name": r.test_name,
                    "test_date": r.test_date.isoformat() if r.test_date else None,
                    "recording_file": r.recording_file,
                    "frame_count": r.frame_count,
                    # DTW metrics are optional – they may not exist yet on the model.
                    "similarity_overall": getattr(r, "similarity_overall", None),
                    "similarity_pos": getattr(r, "similarity_pos", None),
                    "similarity_amp": getattr(r, "similarity_amp", None),
                    "similarity_spd": getattr(r, "similarity_spd", None),
                    "distance_pos": getattr(r, "distance_pos", None),
                    "distance_amp": getattr(r, "distance_amp", None),
                    "distance_spd": getattr(r, "distance_spd", None),
                }
            )
        return out
    finally:
        db.close()


@router.get("/sessions/{test_name}/{session_id}/series")
def get_series(
    test_name: str,
    session_id: str,
    max_points: int = Query(200, ge=50, le=2000),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return DTW series for a given session.

    This is now backed by TestResult JSON columns instead of NPZ files.
    We assume the TestResult has JSON columns such as:
      - pos_local_costs
      - pos_aligned_ref_by_live
      - amp_local_costs
      - amp_aligned_ref_by_live
      - spd_local_costs
      - spd_aligned_ref_by_live
    but we degrade gracefully if they are missing.
    """
    sid = session_id  # string-based test_id

    db = _session_scope()
    try:
        r: Optional[TestResult] = (
            db.query(TestResult)
            .filter(TestResult.test_id == sid, TestResult.test_name == test_name)
            .first()
        )
        if r is None:
            raise HTTPException(status_code=404, detail="Session not found")

        pos_local = _json_list(getattr(r, "pos_local_costs", None))
        pos_align = _json_list(
            getattr(r, "pos_aligned_ref_by_live", None), key="indices"
        )
        amp_local = _json_list(getattr(r, "amp_local_costs", None))
        amp_align = _json_list(
            getattr(r, "amp_aligned_ref_by_live", None), key="indices"
        )
        spd_local = _json_list(getattr(r, "spd_local_costs", None))
        spd_align = _json_list(
            getattr(r, "spd_aligned_ref_by_live", None), key="indices"
        )

        return {
            "ok": True,
            "testName": r.test_name,
            "sessionId": r.test_id,
            "patient_id": r.patient_id,
            "test_date": r.test_date.isoformat() if r.test_date else None,
            # meta: distances & similarities (optional)
            "distance_pos": getattr(r, "distance_pos", None),
            "distance_amp": getattr(r, "distance_amp", None),
            "distance_spd": getattr(r, "distance_spd", None),
            "avg_step_pos": getattr(r, "avg_step_pos", None),
            "similarity_overall": getattr(r, "similarity_overall", None),
            "similarity_pos": getattr(r, "similarity_pos", None),
            "similarity_amp": getattr(r, "similarity_amp", None),
            "similarity_spd": getattr(r, "similarity_spd", None),
            "series": {
                "position": _series_bundle(pos_local, pos_align, max_points),
                "amplitude": _series_bundle(amp_local, amp_align, max_points),
                "speed": _series_bundle(spd_local, spd_align, max_points),
            },
        }
    finally:
        db.close()


@router.get("/sessions/{test_name}/{session_id}/download")
def download_recording(
    test_name: str,
    session_id: str,
) -> FileResponse:
    """
    Previously this endpoint streamed the NPZ artifacts. Now that DTW runs live
    in SQL, the most useful thing to download is the underlying recording
    associated with this session.
    """
    sid = session_id  # string-based test_id

    db = _session_scope()
    try:
        r: Optional[TestResult] = (
            db.query(TestResult)
            .filter(TestResult.test_id == sid, TestResult.test_name == test_name)
            .first()
        )
        if r is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if not r.recording_file:
            raise HTTPException(
                status_code=404, detail="No recording linked to this session"
            )

        # recordings folder is alongside this routes module (backend/routes/recordings)
        recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
        path = os.path.join(recordings_dir, r.recording_file)
        if not os.path.isfile(path):
            raise HTTPException(
                status_code=404, detail="Recording file not found on disk"
            )

        return FileResponse(
            path,
            filename=os.path.basename(path),
            media_type="video/mp4",
        )
    finally:
        db.close()


@router.get("/sessions/lookup/{session_id}")
def lookup_session(session_id: str) -> Dict[str, Any]:
    """
    Convenience endpoint: given a global session_id (test_id), return
    its associated test_name and basic metadata.
    """
    sid = session_id  # string-based test_id

    db = _session_scope()
    try:
        r: Optional[TestResult] = (
            db.query(TestResult)
            .filter(TestResult.test_id == sid)
            .first()
        )
        if r is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": r.test_id,
            "test_name": r.test_name,
            "patient_id": r.patient_id,
            "test_date": r.test_date.isoformat() if r.test_date else None,
            "recording_file": r.recording_file,
        }
    finally:
        db.close()


@router.get("/sessions/{test_name}/{session_id}/channel")
def get_channel(
    test_name: str,
    session_id: str,
    model: str = Query(..., description="pose|hands|finger"),
    landmark: int = Query(..., ge=0),
    axis: str = Query("x", regex="^[xyz]$"),
    max_points: int = Query(200, ge=50, le=2000),
) -> Dict[str, Any]:
    """
    In the original filesystem-based implementation this endpoint returned
    a single landmark+axis channel with the aligned live/ref series.

    With the current SQL schema we only persist aggregate DTW series, not
    per-axis raw trajectories, so we can't faithfully reconstruct that view.
    For now we return a 501 so it's clear to the caller that this endpoint
    is not wired up in the SQL-backed version.
    """
    raise HTTPException(
        status_code=501,
        detail="Per-channel series are not available in the SQL-backed DTW storage.",
    )


@router.get("/sessions/{test_name}/{session_id}/axis_agg")
def axis_agg(
    test_name: str,
    session_id: str,
    model: str = Query(
        "pose",
        description="pose|hands|finger (kept for compatibility; not used)"
    ),
    axis: str = Query("x", regex="^[xyz]$"),
    landmarks: Optional[str] = Query(
        None,
        description=(
            "Landmark indices CSV or 'all'; kept for compatibility but not "
            "currently used in the SQL-backed implementation."
        ),
    ),
    how: str = Query(
        "mean",
        alias="reduce",
        description="Reduction over landmarks: mean|median|sum|min|max",
    ),
    max_points: int = Query(200, ge=50, le=2000),
) -> Dict[str, Any]:
    sid = session_id
    db = _session_scope()
    try:
        r: Optional[TestResult] = (
            db.query(TestResult)
            .filter(TestResult.test_id == sid, TestResult.test_name == test_name)
            .first()
        )
        if r is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # Pull stored arrays
        pos_local = _json_list(getattr(r, "pos_local_costs", None))
        pos_align = _json_list(
            getattr(r, "pos_aligned_ref_by_live", None),
            key="indices",
        )

        # New-style bundle (kept so you can use it later if you want)
        bundle = _series_bundle(pos_local, pos_align, max_points)

        # ---- Backward-compat: synthesize old AxisAggResponse shape ----
        local_costs = bundle.get("local_costs") or []
        align = bundle.get("alignment_map") or {}
        map_x = align.get("x") or list(range(len(local_costs)))
        map_y = align.get("y") or map_x

        n = min(len(local_costs), len(map_x), len(map_y))
        local_costs = local_costs[:n]
        map_x = map_x[:n]
        map_y = map_y[:n]

        # Simple index for plotting on the x-axis
        xs = list(range(n))

        live = {"x": xs, "y": local_costs}
        ref = {"x": xs, "y": local_costs}
        path = {"i": map_x, "j": map_y}
        warped = {"k": xs, "live": local_costs, "ref": local_costs}

        return {
            "ok": True,
            "testName": r.test_name,
            "sessionId": str(r.test_id),
            "axis": axis,
            "how": how,
            "reduce": how,   # what your React UI displays as {data.reduce}
            "landmarks": "all",  # new line: matches AxisAggResponse.landmarks?
            "series": bundle,  # new-style data (optional, not used yet)
            "live": live,
            "ref": ref,
            "path": path,
            "warped": warped,
        }
    finally:
        db.close()
