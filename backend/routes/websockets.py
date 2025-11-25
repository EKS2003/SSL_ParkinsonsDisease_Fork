from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

import os
import base64
import json
from datetime import datetime
import uuid


import numpy as np
from typing import List, Optional, Dict
from routes.utils_dtw import EndOnlyDTW, normalize_test_name

from patient_manager import (
    SessionLocal,
)
from repo.sql_models import TestResult
from fastapi import APIRouter

router = APIRouter(prefix="/ws", tags=["websockets"])

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)


def _cv2():
    try:
        import cv2
        return cv2
    except Exception as e:
        raise RuntimeError(
            "OpenCV not available. Install opencv-python-headless."
        ) from e

def _mp():
    try:
        import mediapipe as mp
        return mp
    except Exception as e:
        raise RuntimeError(
            "MediaPipe not available. Install mediapipe.", e
        ) from e


# ============ Media helpers ============
def _decode_base64_image(data_str: str) -> np.ndarray:
    """Accepts 'data:*;base64,...' or raw base64 and returns BGR frame."""
    if "," in data_str:
        b64 = data_str.split(",", 1)[1]
    else:
        b64 = data_str
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    cv2 = _cv2()
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode frame from provided data.")
    return frame

def _save_frames_to_mp4(test_id: str ,frames: List[np.ndarray], fps: float = 30.0) -> str:
    if not frames:
        raise ValueError("No frames to save.")

    cv2 = _cv2()
    h, w = frames[0].shape[:2]

    filename = f"ws_recording_{test_id}.mp4"
    path = os.path.join(RECORDINGS_DIR, filename)

    # Try H.264 first, fall back to mp4v if unavailable
    for fourcc_str in ("avc1", "H264", "mp4v"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
        if writer.isOpened():
            print("Using fourcc:", fourcc_str)
            break
    else:
        raise RuntimeError("Could not open VideoWriter with any codec")

    for f in frames:
        writer.write(f)
    writer.release()
    return filename


# ============ MediaPipe extractor ============
class MPExtractor:
    """Create once per WebSocket connection to reuse Mediapipe graph."""
    def __init__(self, model: str = "hands"):
        self.model = model
        mp = _mp()
        if model == "hands":
            self.solution = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=2,
                min_detection_confidence=0.5, min_tracking_confidence=0.5
            )
        elif model == "pose":
            self.solution = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        else:
            self.solution = None

    def process(self, frame_bgr):
        if self.solution is None:
            return {"error": f"Unsupported model {self.model}"}
        cv2 = _cv2()
        mp = _mp()
        # MediaPipe expects RGB
        results = self.solution.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

        if self.model == "hands":
            out = {"model": "hands", "hands": []}
            if getattr(results, "multi_hand_landmarks", None):
                handed = []
                if getattr(results, "multi_handedness", None):
                    handed = [h.classification[0].label for h in results.multi_handedness]
                for i, lm in enumerate(results.multi_hand_landmarks):
                    pts = [{"x": p.x, "y": p.y, "z": p.z} for p in lm.landmark]
                    out["hands"].append({
                        "landmarks": pts,
                        "handedness": handed[i] if i < len(handed) else None
                    })
            return out

        elif self.model == "pose":
            out = {"model": "pose", "pose": []}
            if getattr(results, "pose_landmarks", None):
                lm = results.pose_landmarks.landmark
                pts = [{"x": p.x, "y": p.y, "z": p.z, "v": getattr(p, "visibility", 0.0)} for p in lm]
                out["pose"] = pts
            return out

        return {"error": "Unknown model"}
    



# ============ WebSocket handler ============
async def _camera_ws_handler(websocket: WebSocket):
    await websocket.accept()

    frames: List[np.ndarray] = []
    fps_hint: float = 30.0
    patient_id: Optional[str] = None
    test_name: Optional[str] = None
    test_id: Optional[str] = None
    model: str = "hands"      # "hands" | "pose"
    started: bool = False

    mp_extractor: Optional[MPExtractor] = None
    dtw_end: Optional[EndOnlyDTW] = None

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            mtype = data.get("type")

            if mtype == "init":
                try:
                    patient_id = data.get("patientId") or data.get("patient_id")
                    raw_test = data.get("testType") or data.get("test_name")
                    test_name = normalize_test_name(raw_test)          # canonicalize
                    model = data.get("model", model)                   # "hands" | "pose"
                    fps_hint = float(data.get("fps", fps_hint))
                    test_id = data.get("testId")     # unique per test run
                    mp_extractor = MPExtractor(model=model)
                    dtw_end = EndOnlyDTW(test_name or "unknown", model, test_id)

                    # Surface template init errors immediately
                    if getattr(dtw_end, "init_error", None):
                        await websocket.send_json({
                            "type": "error",
                            "where": "init",
                            "message": dtw_end.init_error,
                            "testName": test_name,
                            "model": model
                        })

                    started = True
                    await websocket.send_json({
                        "type": "status",
                        "status": "initialized",
                        "patientId": patient_id,
                        "testName": test_name,  # canonical test
                        "model": model,
                        "fps": fps_hint
                    })
                except Exception as e:
                    started = False
                    await websocket.send_json({"type": "error", "where": "init", "message": str(e)})

            elif mtype == "frame":
                try:
                    if not started or not mp_extractor:
                        await websocket.send_json({"type": "error", "where": "frame", "message": "Not initialized"})
                        continue

                    frame = _decode_base64_image(data["data"])
                    frames.append(frame)

                    kp = mp_extractor.process(frame)
                    if dtw_end and "error" not in kp:
                        dtw_end.push(kp)

                    resp = {"type": "keypoints", "model": model, "frame_idx": len(frames)}
                    resp.update(kp)
                    await websocket.send_json(resp)

                except Exception as e:
                    await websocket.send_json({"type": "error", "where": "frame", "message": f"{e}"})

            elif mtype == "pause":
                paused = bool(data.get("paused", False))
                await websocket.send_json({
                    "type": "status",
                    "status": "paused" if paused else "resumed"
                })

            elif mtype == "end":
                if not started:
                    await websocket.send_json({"type": "error", "where": "end", "message": "Test not initialized"})
                    continue
                if not frames:
                    await websocket.send_json({"type": "error", "where": "end", "message": "No frames received"})
                    continue
                if not dtw_end:
                    await websocket.send_json({"type": "error", "where": "end", "message": "DTW not initialized"})
                    continue

                # 1) Compute DTW (no disk)
                dtw_payload = dtw_end.finalize_and_save(
                    meta_sidecar={"patientId": patient_id, "fps": fps_hint}
                )
                if not dtw_payload.get("ok"):
                    await websocket.send_json({
                        "type": "dtw_error",
                        **dtw_payload,
                        "testName": test_name,
                        "model": model,
                    })
                    continue

                # 2) Save MP4 recording
                try:
                    saved_name = _save_frames_to_mp4(test_id, frames, fps=fps_hint)
                except Exception as e:
                    await websocket.send_json({"type": "error", "where": "save_mp4", "message": f"{e}"})
                    frames = []
                    continue

                # 3) Persist DTW run + video into TestResult
                try:
                    with SessionLocal() as db:
                        tr = TestResult(
                            test_id=test_id,
                            patient_id=patient_id or "unknown",
                            test_name=test_name or "unknown",
                            test_date=datetime.utcnow(),
                            model=model,
                            fps=fps_hint,
                            recording_file=saved_name,
                            frame_count=len(frames),

                            similarity_overall=dtw_payload["similarity_overall"],
                            similarity_pos=dtw_payload["similarity_pos"],
                            similarity_amp=dtw_payload["similarity_amp"],
                            similarity_spd=dtw_payload["similarity_spd"],
                            distance_pos=dtw_payload["pos_dtw"],
                            distance_amp=dtw_payload["amp_dtw"],
                            distance_spd=dtw_payload["spd_dtw"],
                            avg_step_pos=dtw_payload["avg_step_pos"],
                            R_pos=dtw_payload["R_pos"],
                            R_amp=dtw_payload["R_amp"],
                            R_spd=dtw_payload["R_spd"],
                            L_pos=dtw_payload["L_pos"],
                            L_amp=dtw_payload["L_amp"],
                            L_spd=dtw_payload["L_spd"],

                            pos_local_costs={"values": dtw_payload["pos_local_costs"]},
                            pos_aligned_ref_by_live={"indices": dtw_payload["pos_aligned_ref_by_live"]},
                            amp_local_costs={"values": dtw_payload["amp_local_costs"]},
                            amp_aligned_ref_by_live={"indices": dtw_payload["amp_aligned_ref_by_live"]},
                            spd_local_costs={"values": dtw_payload["spd_local_costs"]},
                            spd_aligned_ref_by_live={"indices": dtw_payload["spd_aligned_ref_by_live"]},
                        )
                        db.add(tr)
                        db.commit()
                        db.refresh(tr)

                    # 4) Tell frontend everything is done
                    await websocket.send_json({
                        "type": "complete",
                        "testResultId": tr.test_id,
                        "patientId": patient_id,
                        "testName": test_name,
                        "model": model,
                        "recording": saved_name,
                        "path": f"recordings/{saved_name}",
                        "frame_count": len(frames),
                        "similarity_overall": tr.similarity_overall,
                        "similarity_pos": tr.similarity_pos,
                        "similarity_amp": tr.similarity_amp,
                        "similarity_spd": tr.similarity_spd,
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "where": "sql_save", "message": f"{e}"})

                frames = []


            else:
                await websocket.send_json({"type": "error", "message": f"Unknown message: {data}"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass


# Primary WS endpoint: ws://.../ws/{client_id}
@router.websocket("/{client_id}")
async def ws_client(websocket: WebSocket, client_id: str):
    await _camera_ws_handler(websocket)

@router.websocket("/camera")
async def ws_camera(websocket: WebSocket):
    await _camera_ws_handler(websocket)

@router.get("/test")
async def test_ws():
    return{"message": "WebSocket endpoint is at /ws/{client_id} or /ws/camera"}