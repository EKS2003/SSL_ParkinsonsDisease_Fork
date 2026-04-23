from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LSTMCNNPredictRequest(BaseModel):
    sequence: list[list[float]] = Field(
        ...,
        description="Input sequence with shape (T, 24).",
    )
    return_attention: bool = Field(
        default=False,
        description="Include attention weights per window in the response.",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence_contract(cls, value: list[list[float]]) -> list[list[float]]:
        if not value:
            raise ValueError("sequence must not be empty")
        if len(value) < 30:
            raise ValueError("sequence length must be at least 30")
        for i, frame in enumerate(value):
            if len(frame) != 24:
                raise ValueError(f"frame {i} must have exactly 24 features")
            for j, feature in enumerate(frame):
                if not math.isfinite(feature):
                    raise ValueError(f"feature at frame {i}, index {j} is NaN or infinite")
        return value


class LSTMCNNPredictResponse(BaseModel):
    predicted_updrs_stage: int
    probabilities: dict[str, float]
    severity: str
    severity_stage: int
    prediction: str
    confidence: float
    lstm_output: list[float]
    logits: list[float]
    n_windows: int
    window_size: int
    stride: int
    model_version: str
    preprocessing_version: str
    checkpoint_path: str
    attention_weights: list[float] | None = None


class LSTMCNNPredictAndUpdateResponse(LSTMCNNPredictResponse):
    patient_id: str
    patient_updated: bool


class APIErrorResponse(BaseModel):
    detail: Any
