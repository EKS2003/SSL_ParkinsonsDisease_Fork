# Backend Reference

FastAPI service providing patient management, real-time pose estimation, DTW-based motor scoring, LSTM-MIL severity prediction, and a doctor labelling workflow.

---

## Starting the Server

```bash
# From the repository root
source .venv/bin/activate
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs: `http://localhost:8000/docs`

---

## API Endpoints

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/token` | OAuth2 password flow — returns `{ access_token, token_type }` |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Welcome message |
| `GET` | `/health` | Liveness check |

### Patients  `/patients`

| Method | Path | Description |
|---|---|---|
| `POST` | `/patients/` | Create patient |
| `GET` | `/patients/` | List patients (paginated) |
| `GET` | `/patients/{id}` | Get patient |
| `PUT` | `/patients/{id}` | Update patient |
| `DELETE` | `/patients/{id}` | Delete patient |
| `GET` | `/patients/search/{query}` | Full-text search |
| `POST` | `/patients/filter/` | Filtered list |
| `GET` | `/patients/{id}/tests` | Test history |
| `POST` | `/patients/{id}/tests` | Add test result |

### Recordings

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload-video/` | Upload `.mov` / `.mp4` (multipart) |
| `GET` | `/videos/{patient_id}/{test_name}` | List recordings for a patient + test |
| `GET` | `/recordings/{filename}` | Serve video file |

### WebSocket  `/ws`

| Path | Description |
|---|---|
| `/ws/{client_id}` | Per-client keypoint stream |
| `/ws/camera` | Camera feed WebSocket |

The backend runs MediaPipe **HandLandmarker** and **PoseLandmarker** (Tasks API) on each frame and emits structured keypoint JSON back to the client in real-time. Model files must be present at `backend/models/`:

```
models/
├── hand_landmarker.task
└── pose_landmarker_lite.task
```

Download (one-time):

```bash
mkdir -p backend/models
curl -L "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task" \
  -o backend/models/hand_landmarker.task
curl -L "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task" \
  -o backend/models/pose_landmarker_lite.task
```

### DTW Sessions  `/dtw`

Session artifacts are stored at `backend/routes/dtw_runs/<test_name>/<session_id>/`:
- `dtw_artifacts.npz` — `X_live`, `Y_ref`, warp paths, costs
- `meta.json` — timestamps, DTW scores, ML/doctor labels

| Method | Path | Description |
|---|---|---|
| `GET` | `/dtw/health` | DTW subsystem health |
| `GET` | `/dtw/diag` | Diagnostics (template paths, counts) |
| `GET` | `/dtw/tests` | List available test types |
| `GET` | `/dtw/sessions/lookup/{session_id}` | Find session across all test types |
| `GET` | `/dtw/sessions/{test_name}` | List sessions for a test |
| `GET` | `/dtw/sessions/{test_name}/{session_id}/series` | Full time-series (live + warped ref) |
| `GET` | `/dtw/sessions/{test_name}/{session_id}/channel` | Per-channel DTW decomposition |
| `GET` | `/dtw/sessions/{test_name}/{session_id}/axis_agg` | Axis-aggregated DTW data |
| `GET` | `/dtw/sessions/{test_name}/{session_id}/download` | Download raw `.npz` artifact |
| `PATCH` | `/dtw/sessions/{test_name}/{session_id}/label` | Doctor stage confirmation / correction |

#### `PATCH /dtw/sessions/{test}/{session_id}/label` — Doctor Label

Request body:

```json
{
  "confirmed_stage": 2,
  "patient_id": "abc123",
  "notes": "Mild tremor visible; AI over-estimated."
}
```

- `confirmed_stage` — integer 1–5 (required)
- `patient_id` — if provided, updates patient `severity` field to `"Stage N"`
- `notes` — optional free-text (max 1 000 chars)

Response:

```json
{
  "ok": true,
  "session_id": "...",
  "confirmed_stage": 2,
  "label_source": "doctor_correction",
  "training_copy": ".../_labelled_training_data/finger-tapping/stage_2/<session_id>",
  "patient_updated": true
}
```

`label_source` is `"doctor_confirmed"` when the doctor's choice matches the ML prediction, or `"doctor_correction"` when they differ. The session folder is copied to `_labelled_training_data/<test>/stage_<N>/<session_id>/` for future model retraining.

### ML Inference  `/ml`

The classifier is an LSTM + Attention MIL model trained on hand-keypoint sequences. Input shape: `(T, 24)` — 8 landmarks × 3 coordinates. Windowing: window=30, stride=10.

| Method | Path | Description |
|---|---|---|
| `POST` | `/ml/updrs/predict` | Predict from raw `(T, 24)` sequence |
| `POST` | `/ml/updrs/predict/patients/{id}` | Predict + optionally update patient severity |
| `GET` | `/ml/updrs/from_session/{test}/{session_id}` | Predict from a saved DTW session |

#### `POST /ml/updrs/predict`

Request:

```json
{
  "sequence": [[...], ...],
  "return_attention": false
}
```

Validation: `T >= 30`, exactly 24 features per frame, no `NaN`/`inf`.

Response fields:

| Field | Type | Notes |
|---|---|---|
| `predicted_updrs_stage` | int 0–3 | Classifier-native output |
| `severity` | string | `"Stage 1"` – `"Stage 5"` |
| `confidence` | float | Max class probability |
| `probabilities` | float[] | Per-class (0–3) |
| `severity_stage` | int | Compatibility alias |
| `prediction` | string | Compatibility alias |
| `lstm_output` | float[] | Raw LSTM output |
| `logits` | float[] | Pre-softmax logits |

#### `POST /ml/updrs/predict/patients/{patient_id}`

Same body as above. Query parameter `persist_update` (default `true`) controls whether the patient's severity field is written.

Additional response fields: `patient_id`, `patient_updated`, `model_version`, `preprocessing_version`, `checkpoint_path`.

#### `GET /ml/updrs/from_session/{test_name}/{session_id}`

Loads `X_live` from the session's `dtw_artifacts.npz`, extracts the 8 key landmarks appropriate for the test type, pads z=0, and runs inference. Returns the same shape as `POST /ml/updrs/predict`.

> **Note — model output range:** The classifier was trained on data with limited Stage 0 (healthy) and Stage 4 (severe) representation. Predictions are most reliable for **Stages 1–3**. Do not use Stage 0 or Stage 4 outputs for clinical decisions until the model is retrained with a more balanced dataset.

---

## Model Checkpoint

```
../Park-LSTM-Autoencoder/checkpoints/lstm_mil_classifier.pt
```

The path is resolved relative to the backend directory. The legacy-incompatible checkpoint (`lstm_cnn_classifier.legacy_incompatible.pt`) kept in `backend/` is not loaded.

---

## Healthy Reference Templates

DTW compares live keypoints against healthy-control templates stored as NPZ files. Templates are built offline from reference videos:

```bash
cd backend
python process_healthy_videos.py                        # all test types
python process_healthy_videos.py --test finger-tapping  # single type
python process_healthy_videos.py --force                # re-process already-done videos
python process_healthy_videos.py --no-rebuild-template  # skip template rebuild step
```

Source videos: `backend/healthy_data/<test-type>/`  
Generated templates: `backend/routes/templates/<test-type>.npz`

Supported test types: `finger-tapping`, `fist-open-close`, `stand-and-sit`

---

## Data Storage

| Path | Contents |
|---|---|
| `routes/dtw_runs/<test>/<session>/` | Live DTW session artifacts |
| `routes/_labelled_training_data/<test>/stage_N/<session>/` | Doctor-labelled training archive |
| `routes/recordings/` | Uploaded patient videos |
| `healthy_data/<test>/` | Healthy reference videos |
| `models/` | MediaPipe `.task` files |
| `patients.json` | Legacy flat-file patient store |
| `test_history.json` | Test history flat store |

---

## Database

SQLite via SQLAlchemy 2.0. Session factory: `patient_manager.SessionLocal`.  
Models: `repo/sql_models.py` — `User`, `Patient`, `Visit`, `TestResult`.

Excel import utility: `repo/excel_to_repository.py`  
Expected sheets: `patients`, `visits`, `test_results` (see column names in that file).

---

## Authentication

JWT bearer tokens issued at `POST /token` (OAuth2 password flow).  
Token lifetime: 30 minutes. Secret key configured in `main.py` (`SECRET_KEY`).  
Passwords hashed with BCrypt via `passlib`.

---

## Tests

```bash
cd backend
python -m pytest -q tests/
```

`tests/test_classifier_api.py` covers:
1. Predict + update (success)
2. Patient not found (404)
3. Invalid inference payload (400)
4. Predict-only mode (`persist_update=false`)
5. Request validation failure (422)
6. Missing checkpoint (500)


