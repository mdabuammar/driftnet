"""
DriftNet -- Local Pipeline Validation Script

Run this script to confirm the full inference pipeline is healthy
before starting the FastAPI server.

Usage (from the deployment/ directory):
    python validate_pipeline.py

What it checks
--------------
1. All asset files exist
2. PyTorch encoder loads and produces (1, 150) latent vector
3. Clinical encoding produces (1, 13) vector
4. Contrastive model produces (1, 128) embedding
5. DriftNet final model produces a 3-class softmax output
6. Full end-to-end prediction completes without error
7. Confidence level and warning are present in output
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make sure imports resolve when run from deployment/ root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.inference import DriftNetInference, BASE_DIR

SEPARATOR = "-" * 60


def banner(title: str) -> None:
    print("\n" + SEPARATOR)
    print("  " + title)
    print(SEPARATOR)


def check(label: str, condition: bool, detail: str = "") -> None:
    icon = "[OK]  " if condition else "[FAIL]"
    line = "  " + icon + "  " + label
    if detail:
        line += "  [" + detail + "]"
    print(line)
    if not condition:
        raise AssertionError("FAILED: " + label)


def main() -> None:
    banner("DriftNet Pipeline Validation")
    print("  Project root: " + str(BASE_DIR))

    # Step 1: Init (loads all assets + models)
    banner("Step 1 - Initialising DriftNetInference")
    try:
        predictor = DriftNetInference()
        check("DriftNetInference initialised", True)
    except Exception as exc:
        check("DriftNetInference initialised", False, str(exc))
        sys.exit(1)

    # Step 2: Locate sample file
    banner("Step 2 - Locating sample methylation file")
    sample_txt = BASE_DIR / "samples" / "sample_patient.methylation_array.sesame.level3betas.txt"
    check("Sample methylation file exists", sample_txt.exists(), str(sample_txt))

    # Step 3: Parse methylation
    banner("Step 3 - Parsing methylation file")
    meth_raw, cpg_count = predictor.parse_methylation_txt(sample_txt)
    check("parse_methylation_txt returned array", meth_raw is not None)
    check("Methylation shape == (1, 550000)", meth_raw.shape == (1, 550_000), str(meth_raw.shape))
    check("CpG count logged", cpg_count > 0, str(cpg_count))

    # Step 4: Clean methylation
    banner("Step 4 - Cleaning methylation array")
    meth_clean = predictor.clean_methylation_array(meth_raw)
    check("Cleaned methylation shape == (1, 550000)", meth_clean.shape == (1, 550_000), str(meth_clean.shape))
    import numpy as np
    check("No NaN after cleaning", not np.isnan(meth_clean).any())
    check("All values in [0, 1]", bool((meth_clean >= 0).all() and (meth_clean <= 1).all()))

    # Step 5: PyTorch encoder -> latent
    banner("Step 5 - PyTorch encoder -> latent (1, 150)")
    latent = predictor.get_latent_features(meth_clean)
    check("Latent shape == (1, 150)", latent.shape == (1, 150), str(latent.shape))
    check("Latent contains finite values", bool(np.isfinite(latent).all()))

    # Step 6: Clinical encoding
    banner("Step 6 - Clinical encoding -> (1, 13)")
    sample_clinical = {
        "demographic.gender":                  "male",
        "demographic.vital_status":            "Alive",
        "samples.sample_type":                 "Primary Tumor",
        "cases.disease_type":                  "Adenomas and Adenocarcinomas",
        "samples.tissue_type":                 "Tumor",
        "diagnoses.primary_diagnosis":         "Cholangiocarcinoma",
        "diagnoses.tissue_or_organ_of_origin": "Intrahepatic bile duct",
        "diagnoses.morphology":                "8160/3",
        "diagnoses.age_at_diagnosis":          25069,
        "diagnoses.prior_treatment":           "No",
        "diagnoses.prior_malignancy":          "no",
        "demographic.race":                    "white",
        "demographic.ethnicity":               "not hispanic or latino",
    }
    clinical_enc = predictor.encode_clinical_input(sample_clinical)
    check("Clinical shape == (1, 13)", clinical_enc.shape == (1, 13), str(clinical_enc.shape))

    # Step 7: Contrastive embedding
    banner("Step 7 - Contrastive embedding -> (1, 128)")
    embedding = predictor.get_contrastive_embedding(latent, clinical_enc)
    check("Embedding shape == (1, 128)", embedding.shape == (1, 128), str(embedding.shape))
    check("Embedding contains finite values", bool(np.isfinite(embedding).all()))

    # Step 8: DriftNet prediction
    banner("Step 8 - DriftNet final prediction")
    pred = predictor.predict_stage(embedding, clinical_enc)
    check("predicted_stage present", "predicted_stage" in pred)
    check("confidence present", "confidence" in pred)
    check(
        "confidence_level is high/medium/low",
        "confidence_level" in pred and pred["confidence_level"] in {"high", "medium", "low"},
        str(pred.get("confidence_level")),
    )
    check(
        "probabilities has 3 stages",
        "probabilities" in pred and len(pred["probabilities"]) == 3,
    )
    prob_sum = sum(pred["probabilities"].values())
    check(
        "Probabilities sum approx 1.0",
        abs(prob_sum - 1.0) < 0.01,
        "sum=" + str(round(prob_sum, 6)),
    )

    # Step 9: Full safe wrapper
    banner("Step 9 - Full safe inference wrapper")
    result = predictor.run_full_inference_safe(sample_txt, sample_clinical)
    check("success == True", result.get("success") is True)
    check("request_id present", bool(result.get("request_id")))
    check("cpg_count present", result.get("cpg_count", 0) > 0, str(result.get("cpg_count")))
    check("latent_shape == [1, 150]", result.get("latent_shape") == [1, 150])
    check("embedding_shape == [1, 128]", result.get("embedding_shape") == [1, 128])

    # Summary
    banner("ALL CHECKS PASSED -- Pipeline is healthy")
    print()
    print("  Prediction result:")
    print(json.dumps(result, indent=4))
    print()


if __name__ == "__main__":
    main()
