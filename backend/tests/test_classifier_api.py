from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import routes.classifier as classifier_routes
from main import app
from core.dependencies import get_patient_service
from core.exceptions import PatientNotFoundError
from routes.contracts import PatientUpdate


def _valid_payload() -> dict:
    return {
        "sequence": [[0.1] * 24 for _ in range(30)],
        "return_attention": False,
    }


def _mock_prediction() -> dict:
    return {
        "predicted_updrs_stage": 2,
        "probabilities": {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1},
        "severity": "Stage 3",
        "severity_stage": 3,
        "prediction": "Stage 3",
        "confidence": 0.6,
        "lstm_output": [0.1, 0.2, 0.6, 0.1],
        "logits": [0.1, 0.2, 0.8, 0.05],
        "n_windows": 1,
        "window_size": 30,
        "stride": 10,
        "model_version": "lstm_cnn_mil_v1",
        "preprocessing_version": "window30_stride10_features24",
        "checkpoint_path": "checkpoint.pt",
        "attention_weights": None,
    }


def test_predict_and_update_success(monkeypatch):
    def fake_predict(sequence, return_attention=False):
        return _mock_prediction()

    monkeypatch.setattr(classifier_routes.inference_service, "predict", fake_predict)

    mock_service = MagicMock()
    mock_service.update_patient.return_value = None
    app.dependency_overrides[get_patient_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.post("/ml/updrs/predict/patients/patient123", json=_valid_payload())

        assert response.status_code == 200
        body = response.json()
        assert body["patient_id"] == "patient123"
        assert body["patient_updated"] is True
        assert body["severity"] == "Stage 3"
        mock_service.update_patient.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_patient_service, None)


def test_predict_and_update_unknown_patient_returns_404(monkeypatch):
    def fake_predict(sequence, return_attention=False):
        return _mock_prediction()

    monkeypatch.setattr(classifier_routes.inference_service, "predict", fake_predict)

    mock_service = MagicMock()
    mock_service.update_patient.side_effect = PatientNotFoundError("unknown")
    app.dependency_overrides[get_patient_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.post("/ml/updrs/predict/patients/unknown", json=_valid_payload())

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_patient_service, None)


def test_predict_and_update_bad_inference_returns_400(monkeypatch):
    def fake_predict(sequence, return_attention=False):
        raise ValueError("invalid sequence")

    monkeypatch.setattr(classifier_routes.inference_service, "predict", fake_predict)

    client = TestClient(app)
    response = client.post("/ml/updrs/predict/patients/patient123", json=_valid_payload())

    assert response.status_code == 400
    assert "invalid sequence" in response.json()["detail"]


def test_predict_only_mode_with_unknown_patient_returns_200(monkeypatch):
    def fake_predict(sequence, return_attention=False):
        return _mock_prediction()

    monkeypatch.setattr(classifier_routes.inference_service, "predict", fake_predict)

    mock_service = MagicMock()
    app.dependency_overrides[get_patient_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.post(
            "/ml/updrs/predict/patients/unknown?persist_update=false",
            json=_valid_payload(),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["patient_id"] == "unknown"
        assert body["patient_updated"] is False
        mock_service.update_patient.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_patient_service, None)


def test_predict_validation_error_returns_422():
    client = TestClient(app)
    payload = {
        "sequence": [[0.1] * 23 for _ in range(30)],
        "return_attention": False,
    }
    response = client.post("/ml/updrs/predict/patients/patient123", json=payload)
    assert response.status_code == 422


def test_predict_checkpoint_missing_returns_500(monkeypatch):
    def fake_predict(sequence, return_attention=False):
        raise FileNotFoundError("checkpoint missing")

    monkeypatch.setattr(classifier_routes.inference_service, "predict", fake_predict)

    client = TestClient(app)
    response = client.post("/ml/updrs/predict/patients/patient123", json=_valid_payload())

    assert response.status_code == 500
    assert "checkpoint missing" in response.json()["detail"]
