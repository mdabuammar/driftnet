"""
DriftNet — Pydantic request/response schemas.

These models define the exact contract between the FastAPI backend
and any frontend or API client.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    models_loaded: bool = Field(..., description="True when all models are ready")
    message: str = Field(
        default="DriftNet API is running. FOR RESEARCH USE ONLY.",
    )


# ─────────────────────────────────────────────────────────────────
# Prediction response
# ─────────────────────────────────────────────────────────────────
class PredictionResponse(BaseModel):
    """
    Unified response for both successful predictions and errors.
    On success  : `success=True`  and prediction fields are populated.
    On failure  : `success=False` and error fields are populated.
    """

    success: bool = Field(..., description="True if inference completed without error")
    request_id: str = Field(..., description="Unique UUID for this request (for tracing)")

    # ── Prediction outputs ────────────────────────────────────────
    predicted_stage: Optional[str] = Field(
        default=None,
        description="Predicted cancer stage: 'Stage I', 'Stage II', or 'Stage III'",
        examples=["Stage I"],
    )
    predicted_index: Optional[int] = Field(
        default=None,
        description="Zero-based index of the predicted stage class",
        examples=[0],
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Softmax probability of the predicted class (0.0–1.0)",
        examples=[0.49],
    )
    confidence_level: Optional[str] = Field(
        default=None,
        description=(
            "Categorical confidence: 'high' (≥0.70), 'medium' (≥0.50), 'low' (<0.50)"
        ),
        examples=["low"],
    )
    probabilities: Optional[Dict[str, float]] = Field(
        default=None,
        description="Full softmax probability for each stage",
        examples=[{"Stage I": 0.49, "Stage II": 0.16, "Stage III": 0.35}],
    )
    warning: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable warning when confidence is below threshold. "
            "Null when confidence is acceptable."
        ),
    )

    # ── Diagnostic info ───────────────────────────────────────────
    cpg_count: Optional[int] = Field(
        default=None,
        description="Number of CpG probes in the uploaded file before truncation/padding",
        examples=[485000],
    )
    latent_shape: Optional[List[int]] = Field(
        default=None,
        description="Shape of the methylation latent vector (should be [1, 150])",
        examples=[[1, 150]],
    )
    embedding_shape: Optional[List[int]] = Field(
        default=None,
        description="Shape of the contrastive embedding (should be [1, 128])",
        examples=[[1, 128]],
    )

    # ── Error info ────────────────────────────────────────────────
    error_type: Optional[str] = Field(
        default=None,
        description="Python exception type name (populated on failure only)",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error description (populated on failure only)",
    )
    hint: Optional[str] = Field(
        default=None,
        description="Troubleshooting hint for common errors",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "predicted_stage": "Stage I",
                    "predicted_index": 0,
                    "confidence": 0.49,
                    "confidence_level": "low",
                    "probabilities": {
                        "Stage I": 0.49,
                        "Stage II": 0.16,
                        "Stage III": 0.35,
                    },
                    "warning": (
                        "Low-confidence prediction. "
                        "Expert clinical review is strongly recommended."
                    ),
                    "cpg_count": 485000,
                    "latent_shape": [1, 150],
                    "embedding_shape": [1, 128],
                    "error_type": None,
                    "error_message": None,
                    "hint": None,
                }
            ]
        }
    }
