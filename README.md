# DriftNet Deployment

**Pan-cancer stage classification — Stage I / II / III**  
DNA methylation + 13 clinical features → DriftNet

> ⚠️ **FOR RESEARCH USE ONLY.** Not validated for clinical diagnosis or treatment decisions.

---

## Project Overview

DriftNet predicts cancer stage from:
1. One uploaded **DNA methylation `.txt`** file (TCGA sesame level3 betas format, EPIC array)
2. **13 manually entered clinical features**

### Inference pipeline

```
methylation .txt
    → parse (550 000-dim vector)
    → clean (NaN→0.5, clip [0,1])
    → PyTorch encoder → latent (1, 150)
    ↘
      combined (1, 163) → contrastive_scaler → contrastive_encoder.keras → embedding (1, 128)
    ↗
clinical fields (13) → label encode (1, 13)
    → driftnet_clinical_scaler → (1, 13 scaled)

embedding (1,128) + clinical_scaled (1,13) → DriftNet → Stage I / II / III
```

---

## Requirements

- Python **3.11**
- Windows (tested), Linux should work
- CPU inference (no GPU required)

---

## Setup

```powershell
# 1. Create and activate virtual environment
python -m venv .venv311
.\.venv311\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Validate the Pipeline (Before Starting the Server)

```powershell
python validate_pipeline.py
```

This runs a full end-to-end check with shape assertions and prints the prediction result.
All steps should show ✓.

---

## Run the FastAPI Server

```powershell
# From the deployment/ directory with venv active:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open: **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Endpoints

### `GET /health`

Returns API status and whether models are loaded.

```json
{
  "status": "ok",
  "models_loaded": true,
  "message": "DriftNet API is running. FOR RESEARCH USE ONLY."
}
```

---

### `POST /predict`

Upload one methylation file + 13 clinical form fields.

**Request** (multipart/form-data):

| Field | Type | Example |
|-------|------|---------|
| `methylation_file` | File | `.txt` tab-separated |
| `demographic_gender` | string | `male` |
| `demographic_vital_status` | string | `Alive` |
| `samples_sample_type` | string | `Primary Tumor` |
| `cases_disease_type` | string | `Adenomas and Adenocarcinomas` |
| `samples_tissue_type` | string | `Tumor` |
| `diagnoses_primary_diagnosis` | string | `Cholangiocarcinoma` |
| `diagnoses_tissue_or_organ_of_origin` | string | `Intrahepatic bile duct` |
| `diagnoses_morphology` | string | `8160/3` |
| `diagnoses_age_at_diagnosis` | float | `25069` (days) |
| `diagnoses_prior_treatment` | string | `No` |
| `diagnoses_prior_malignancy` | string | `no` |
| `demographic_race` | string | `white` |
| `demographic_ethnicity` | string | `not hispanic or latino` |

**Response**:

```json
{
  "success": true,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "predicted_stage": "Stage I",
  "predicted_index": 0,
  "confidence": 0.49,
  "confidence_level": "low",
  "probabilities": {
    "Stage I": 0.49,
    "Stage II": 0.16,
    "Stage III": 0.35
  },
  "warning": "Low-confidence prediction. Expert clinical review is strongly recommended.",
  "cpg_count": 485000,
  "latent_shape": [1, 150],
  "embedding_shape": [1, 128],
  "error_type": null,
  "error_message": null
}
```

---

## Allowed Clinical Values

See `assets/clinical_label_mappings.json` for the full list of valid values for each categorical field.

**Key allowed values:**

| Field | Allowed values |
|-------|---------------|
| `demographic_gender` | `female`, `male` |
| `demographic_vital_status` | `Alive`, `Dead` |
| `samples_sample_type` | `Primary Tumor`, `Solid Tissue Normal` |
| `samples_tissue_type` | `Tumor`, `Normal` |
| `diagnoses_prior_treatment` | `No`, `Yes` |
| `diagnoses_prior_malignancy` | `no`, `yes` |
| `demographic_race` | `white`, `asian`, `black or african american`, `american indian or alaska native` |
| `demographic_ethnicity` | `not hispanic or latino`, `hispanic or latino` |

> **Note on case sensitivity:** Values must exactly match the allowed strings (case-sensitive).  
> E.g. `Alive` not `alive`, `No` not `no` for prior_treatment.

---

## Confidence Levels

| Level | Confidence | Meaning |
|-------|------------|---------|
| `high` | ≥ 0.70 | Strong prediction |
| `medium` | 0.50 – 0.69 | Moderate certainty |
| `low` | < 0.50 | Uncertain — expert review recommended |

A `warning` message is included in the response whenever confidence < 0.60.

---

## Methylation File Format

```
cg00000029    0.125476889405403
cg00000108    0.967176904452353
cg00000807    NA
...
```

- Tab-separated
- No header row
- Column 0: CpG probe ID
- Column 1: beta value (0–1) or `NA`

> ⚠️ **Platform assumption:** The model was trained on TCGA sesame level3 betas files  
> from the **EPIC array** platform (~866 K probes, truncated to 550 000).  
> Files from the **450 K array** (~485 K probes) may produce less reliable predictions  
> due to probe ordering and count differences.

---

## Assets Directory

```
assets/
├── best_encoder_150latent_fp16.pth      PyTorch VAE encoder (fp16 checkpoint)
├── contrastive_encoder_clean.keras      Keras contrastive encoder (128-dim output)
├── best_driftnet_final.keras            Keras DriftNet final classifier
├── clinical_label_encoders.pkl          Fitted sklearn LabelEncoders (12 categorical fields)
├── clinical_label_mappings.json         Human-readable allowed values per field
├── contrastive_scaler.pkl               StandardScaler for 163-dim contrastive input
├── driftnet_clinical_scaler.pkl         StandardScaler for 13-dim clinical branch
├── stage_label_encoder.pkl              LabelEncoder for stage output decoding
└── preprocessing_metadata.json          Feature column names and dimensions
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Unknown category for 'X': 'Y'` | Category value not in training data | Check `clinical_label_mappings.json` for valid values |
| `Missing clinical input fields` | Not all 13 fields provided | Provide all 13 fields |
| Probe count warning | File may be from 450K array | Use EPIC array files matching training data |
| Exit code -1073741819 | Keras Lambda layer crash | Use `contrastive_encoder_clean.keras` (already set) |
| sklearn InconsistentVersionWarning | Version mismatch | Reinstall with `pip install scikit-learn==1.6.1` |

---

## Research Safety Disclaimer

DriftNet is a **research prototype**. Predictions are based on a model trained on TCGA data.
- Results have not been clinically validated
- Low-confidence predictions (< 0.60) are flagged automatically
- All outputs should be reviewed by a qualified oncologist or researcher
- Do not use for direct patient care decisions
