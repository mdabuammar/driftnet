"""
DriftNet FastAPI Backend

Pan-cancer stage classification (Stage I / II / III) from:
  • One uploaded DNA methylation .txt file
  • 13 manually entered clinical features

FOR RESEARCH USE ONLY — not validated for clinical diagnosis.

Run:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.inference import DriftNetInference
from app.schemas import HealthResponse, PredictionResponse

logger = logging.getLogger("driftnet.api")

# ─────────────────────────────────────────────────────────────────
# Global predictor — loaded once at startup, reused for every request
# ─────────────────────────────────────────────────────────────────
_predictor: DriftNetInference | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all models on startup; release on shutdown."""
    global _predictor
    logger.info("DriftNet API starting — loading models…")
    try:
        _predictor = DriftNetInference()
        logger.info("All DriftNet models loaded successfully ✓")
    except Exception as exc:
        logger.exception("Fatal: failed to load DriftNet models")
        raise RuntimeError(f"Model initialization failed: {exc}") from exc
    yield
    _predictor = None
    logger.info("DriftNet API shutdown complete")


# ─────────────────────────────────────────────────────────────────
# FastAPI application
# ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DriftNet API",
    description=(
        "**DriftNet** — Pan-cancer stage classification system.\n\n"
        "Predicts **Stage I, Stage II, or Stage III** from:\n"
        "- One uploaded DNA methylation `.txt` file (TCGA sesame level3 betas format)\n"
        "- 13 manually entered clinical features\n\n"
        "> ⚠️ **FOR RESEARCH USE ONLY.** Not intended for clinical diagnosis or treatment decisions."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────
# Helper: require models to be loaded
# ─────────────────────────────────────────────────────────────────
def _require_predictor() -> DriftNetInference:
    if _predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Models are not loaded. The server is not ready — try again shortly.",
        )
    return _predictor


# ─────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="API health check",
)
def health() -> HealthResponse:
    """Returns the API status and whether all models are loaded."""
    return HealthResponse(
        status="ok",
        models_loaded=_predictor is not None,
        message="DriftNet API is running. FOR RESEARCH USE ONLY.",
    )


# ─────────────────────────────────────────────────────────────────
# POST /predict
# ─────────────────────────────────────────────────────────────────
@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Prediction"],
    summary="Predict cancer stage",
    response_description="Predicted stage with probabilities and confidence level",
)
async def predict(
    # ── Methylation file ─────────────────────────────────────────
    methylation_file: UploadFile = File(
        ...,
        description=(
            "Tab-separated methylation text file. **No header.** "
            "Column 0 = CpG probe ID, Column 1 = beta value (0–1). "
            "NA values are supported. "
            "File must be from the **EPIC array** platform (same as training data)."
        ),
    ),
    # ── 13 clinical fields (Form fields because we also have a file upload) ──
    demographic_gender: str = Form(
        ..., description="Gender. Allowed: `female`, `male`"
    ),
    demographic_vital_status: str = Form(
        ..., description="Vital status. Allowed: `Alive`, `Dead`"
    ),
    samples_sample_type: str = Form(
        ..., description="Sample type. Allowed: `Primary Tumor`, `Solid Tissue Normal`"
    ),
    cases_disease_type: str = Form(
        ...,
        description=(
            "Disease type. E.g.: `Adenomas and Adenocarcinomas`, "
            "`Squamous Cell Neoplasms`, `Nevi and Melanomas` …"
        ),
    ),
    samples_tissue_type: str = Form(
        ..., description="Tissue type. Allowed: `Tumor`, `Normal`"
    ),
    diagnoses_primary_diagnosis: str = Form(
        ...,
        description=(
            "Primary diagnosis. E.g.: `Cholangiocarcinoma`, "
            "`Infiltrating duct carcinoma, NOS` …"
        ),
    ),
    diagnoses_tissue_or_organ_of_origin: str = Form(
        ...,
        description=(
            "Tissue or organ of origin. "
            "E.g.: `Intrahepatic bile duct`, `Lung, NOS`, `Breast, NOS` …"
        ),
    ),
    diagnoses_morphology: str = Form(
        ...,
        description="ICD-O morphology code. E.g.: `8160/3`, `8500/3`, `8070/3` …",
    ),
    diagnoses_age_at_diagnosis: float = Form(
        ...,
        description="Age at diagnosis **in days** (integer or float). E.g.: `25069`",
    ),
    diagnoses_prior_treatment: str = Form(
        ..., description="Prior treatment. Allowed: `No`, `Yes`"
    ),
    diagnoses_prior_malignancy: str = Form(
        ..., description="Prior malignancy. Allowed: `no`, `yes`"
    ),
    demographic_race: str = Form(
        ...,
        description=(
            "Race. Allowed: `white`, `asian`, "
            "`black or african american`, `american indian or alaska native`"
        ),
    ),
    demographic_ethnicity: str = Form(
        ...,
        description=(
            "Ethnicity. Allowed: `hispanic or latino`, `not hispanic or latino`"
        ),
    ),
) -> PredictionResponse:
    """
    **Predict cancer stage from DNA methylation data and clinical features.**

    ### Input
    - Upload one methylation `.txt` file and provide all 13 clinical fields.
    - Clinical field names use underscores in this form (e.g., `demographic_gender`)
      but are mapped internally to their dot-notation equivalents.

    ### Output
    - `predicted_stage`: Stage I, Stage II, or Stage III
    - `confidence`: softmax probability of the predicted class
    - `confidence_level`: high / medium / low
    - `probabilities`: full distribution over all three stages
    - `warning`: present when confidence is below 0.60

    ### Notes
    - `diagnoses_age_at_diagnosis` must be a **number of days** (not years).
    - All categorical fields must exactly match training-time strings.
      Use `/docs` to see allowed values for each field.
    - This system was trained on TCGA EPIC-array methylation data.
      Files from the 450 K array may produce less reliable results.

    > ⚠️ **FOR RESEARCH USE ONLY.**
    """
    predictor = _require_predictor()

    # Map form field names (underscores) back to internal dot-notation keys
    clinical_input = {
        "demographic.gender":                  demographic_gender,
        "demographic.vital_status":            demographic_vital_status,
        "samples.sample_type":                 samples_sample_type,
        "cases.disease_type":                  cases_disease_type,
        "samples.tissue_type":                 samples_tissue_type,
        "diagnoses.primary_diagnosis":         diagnoses_primary_diagnosis,
        "diagnoses.tissue_or_organ_of_origin": diagnoses_tissue_or_organ_of_origin,
        "diagnoses.morphology":                diagnoses_morphology,
        "diagnoses.age_at_diagnosis":          diagnoses_age_at_diagnosis,
        "diagnoses.prior_treatment":           diagnoses_prior_treatment,
        "diagnoses.prior_malignancy":          diagnoses_prior_malignancy,
        "demographic.race":                    demographic_race,
        "demographic.ethnicity":               demographic_ethnicity,
    }

    # Save uploaded file to a temp location (deleted after inference)
    suffix = (
        Path(methylation_file.filename).suffix
        if methylation_file.filename
        else ".txt"
    )
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await methylation_file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        result = predictor.run_full_inference_safe(tmp_path, clinical_input)

    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass  # Non-critical cleanup failure

    return PredictionResponse(**result)


# ─────────────────────────────────────────────────────────────────
# Global exception handler (catch-all)
# ─────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "request_id": None,
        },
    )
