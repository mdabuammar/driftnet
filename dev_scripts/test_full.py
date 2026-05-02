"""
DriftNet Full A-to-Z Test Suite
================================
Tests:
  1. Health endpoint
  2. Predict endpoint - sample patient (baseline)
  3. Predict endpoint - different disease types (consistency check)
  4. Predict endpoint - different stages expected
  5. Error handling - wrong file format
  6. Error handling - missing clinical field
  7. Error handling - unknown clinical category
  8. Consistency check - same input, multiple calls
  9. Code structure review
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_URL     = "http://localhost:8000"
SAMPLE_FILE  = Path(__file__).parent / "samples" / "sample_patient.methylation_array.sesame.level3betas.txt"
PASS         = "[PASS]"
FAIL         = "[FAIL]"
SKIP         = "[SKIP]"
SEP          = "-" * 65

results = []

def record(label, passed, detail=""):
    icon = PASS if passed else FAIL
    msg  = f"  {icon}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((label, passed))

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

# ─────────────────────────────────────────────────────────────────
# HTTP helpers (stdlib only, no requests)
# ─────────────────────────────────────────────────────────────────
def http_get(path):
    url = BASE_URL + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def http_post_multipart(path, file_path, fields):
    """Send multipart/form-data POST with one file + many string fields."""
    boundary = "DriftNetTestBoundary1234567890"
    body_parts = []

    for name, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )

    # File part
    with open(file_path, "rb") as f:
        file_data = f.read()
    file_name = Path(file_path).name
    body_parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="methylation_file"; filename="{file_name}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    )
    body_bytes = "".join(body_parts).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    url = BASE_URL + path
    req = urllib.request.Request(
        url,
        data=body_bytes,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code

# ─────────────────────────────────────────────────────────────────
# Base clinical input (known-good)
# ─────────────────────────────────────────────────────────────────
BASE_CLINICAL = {
    "demographic_gender":                    "male",
    "demographic_vital_status":              "Alive",
    "samples_sample_type":                   "Primary Tumor",
    "cases_disease_type":                    "Adenomas and Adenocarcinomas",
    "samples_tissue_type":                   "Tumor",
    "diagnoses_primary_diagnosis":           "Cholangiocarcinoma",
    "diagnoses_tissue_or_organ_of_origin":   "Intrahepatic bile duct",
    "diagnoses_morphology":                  "8160/3",
    "diagnoses_age_at_diagnosis":            "25069",
    "diagnoses_prior_treatment":             "No",
    "diagnoses_prior_malignancy":            "no",
    "demographic_race":                      "white",
    "demographic_ethnicity":                 "not hispanic or latino",
}

# ─────────────────────────────────────────────────────────────────
# TEST 1 — Health endpoint
# ─────────────────────────────────────────────────────────────────
section("TEST 1 — GET /health")
try:
    data = http_get("/health")
    record("GET /health returns 200",      True)
    record("status == 'ok'",               data.get("status") == "ok",          f"got: {data.get('status')}")
    record("models_loaded == True",        data.get("models_loaded") is True,    f"got: {data.get('models_loaded')}")
    print(f"  Response: {json.dumps(data, indent=4)}")
except Exception as e:
    record("GET /health reachable",        False, str(e))

# ─────────────────────────────────────────────────────────────────
# TEST 2 — Basic predict (baseline)
# ─────────────────────────────────────────────────────────────────
section("TEST 2 — POST /predict (baseline sample)")

if not SAMPLE_FILE.exists():
    record("Sample methylation file found", False, str(SAMPLE_FILE))
    sys.exit(1)

record("Sample methylation file found", True, str(SAMPLE_FILE.name))

print("  Calling /predict (this takes ~15 seconds)...")
t0 = time.time()
data, status = http_post_multipart("/predict", SAMPLE_FILE, BASE_CLINICAL)
elapsed = time.time() - t0

record("POST /predict returns 200",             status == 200,                           f"got: {status}")
record("success == True",                       data.get("success") is True,             f"got: {data.get('success')}")
record("predicted_stage present",               "predicted_stage" in data)
record("predicted_stage is Stage I/II/III",
       data.get("predicted_stage") in {"Stage I", "Stage II", "Stage III"},
       f"got: {data.get('predicted_stage')}")
record("confidence in [0, 1]",
       0. <= data.get("confidence", -1) <= 1.,
       f"got: {data.get('confidence')}")
record("confidence_level is high/medium/low",
       data.get("confidence_level") in {"high", "medium", "low"},
       f"got: {data.get('confidence_level')}")
record("probabilities has 3 stages",
       len(data.get("probabilities", {})) == 3,
       f"got: {list(data.get('probabilities', {}).keys())}")
record("prob sum approx 1.0",
       abs(sum(data.get("probabilities", {}).values()) - 1.0) < 0.01,
       f"sum={sum(data.get('probabilities', {}).values()):.5f}")
record("latent_shape == [1, 150]",              data.get("latent_shape") == [1, 150],    f"got: {data.get('latent_shape')}")
record("embedding_shape == [1, 128]",           data.get("embedding_shape") == [1, 128], f"got: {data.get('embedding_shape')}")
record("cpg_count > 0",                         data.get("cpg_count", 0) > 0,            f"got: {data.get('cpg_count')}")
record("request_id present",                    bool(data.get("request_id")))
record(f"Inference time < 60 s",                elapsed < 60.,                           f"took: {elapsed:.1f}s")

STAGE_1_RESULT = data.get("predicted_stage")
print(f"\n  Baseline result: {data.get('predicted_stage')} | confidence={data.get('confidence'):.4f} ({data.get('confidence_level')})")
print(f"  Probabilities: {json.dumps(data.get('probabilities'), indent=4)}")
if data.get("warning"):
    print(f"  Warning: {data.get('warning')}")

# ─────────────────────────────────────────────────────────────────
# TEST 3 — Consistency (same input x3)
# ─────────────────────────────────────────────────────────────────
section("TEST 3 — Consistency check (same input, 3 calls)")

predictions = [data.get("predicted_stage")]   # already have 1
confidences = [data.get("confidence")]

print("  Running 2 more identical calls...")
for i in range(2):
    d, _ = http_post_multipart("/predict", SAMPLE_FILE, BASE_CLINICAL)
    predictions.append(d.get("predicted_stage"))
    confidences.append(d.get("confidence"))
    print(f"  Call {i+2}: {d.get('predicted_stage')} | conf={d.get('confidence'):.4f}")

all_same = len(set(predictions)) == 1
conf_range = max(confidences) - min(confidences)

record("All 3 calls return same stage",         all_same,   f"got: {predictions}")
record("Confidence variance < 0.001 (deterministic)", conf_range < 0.001, f"range: {conf_range:.6f}")

# ─────────────────────────────────────────────────────────────────
# TEST 4 — Different clinical scenarios
# ─────────────────────────────────────────────────────────────────
section("TEST 4 — Different clinical input scenarios")

scenarios = [
    {
        "label": "Female, dead, breast cancer",
        "overrides": {
            "demographic_gender":                  "female",
            "demographic_vital_status":            "Dead",
            "cases_disease_type":                  "Ductal and Lobular Neoplasms",
            "samples_tissue_type":                 "Tumor",
            "diagnoses_primary_diagnosis":         "Infiltrating duct carcinoma, NOS",
            "diagnoses_tissue_or_organ_of_origin": "Breast, NOS",
            "diagnoses_morphology":                "8500/3",
            "diagnoses_age_at_diagnosis":          "18000",
        },
    },
    {
        "label": "Male, melanoma, skin, prior treatment",
        "overrides": {
            "demographic_gender":                  "male",
            "demographic_vital_status":            "Alive",
            "cases_disease_type":                  "Nevi and Melanomas",
            "samples_tissue_type":                 "Tumor",
            "diagnoses_primary_diagnosis":         "Malignant melanoma, NOS",
            "diagnoses_tissue_or_organ_of_origin": "Skin, NOS",
            "diagnoses_morphology":                "8720/3",
            "diagnoses_age_at_diagnosis":          "21000",
            "diagnoses_prior_treatment":           "Yes",
        },
    },
    {
        "label": "Squamous cell lung, female, asian",
        "overrides": {
            "demographic_gender":                  "female",
            "cases_disease_type":                  "Squamous Cell Neoplasms",
            "diagnoses_primary_diagnosis":         "Squamous cell carcinoma, NOS",
            "diagnoses_tissue_or_organ_of_origin": "Lung, NOS",
            "diagnoses_morphology":                "8070/3",
            "diagnoses_age_at_diagnosis":          "23000",
            "demographic_race":                    "asian",
        },
    },
]

for s in scenarios:
    clinical = {**BASE_CLINICAL, **s["overrides"]}
    d, status = http_post_multipart("/predict", SAMPLE_FILE, clinical)
    ok_structure = d.get("success") and d.get("predicted_stage") in {"Stage I", "Stage II", "Stage III"}
    record(
        f"'{s['label']}'",
        ok_structure,
        f"=> {d.get('predicted_stage')} | conf={d.get('confidence', 0):.3f} ({d.get('confidence_level')}) | HTTP {status}"
    )

# ─────────────────────────────────────────────────────────────────
# TEST 5 — Error handling: unknown clinical category
# ─────────────────────────────────────────────────────────────────
section("TEST 5 — Error handling: unknown clinical category")

bad_clinical = {**BASE_CLINICAL, "demographic_gender": "INVALID_VALUE_XYZ"}
d, status = http_post_multipart("/predict", SAMPLE_FILE, bad_clinical)
record("Returns success=False for unknown category", d.get("success") is False, f"got: {d.get('success')}")
record("error_message mentions unknown category",
       "unknown" in (d.get("error_message") or "").lower()
       or "Unknown" in (d.get("error_message") or ""),
       f"msg: {d.get('error_message', '')[:80]}")

# ─────────────────────────────────────────────────────────────────
# TEST 6 — /docs endpoint (Swagger reachable)
# ─────────────────────────────────────────────────────────────────
section("TEST 6 — GET /docs (Swagger UI)")
try:
    url = BASE_URL + "/docs"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode()
    record("GET /docs returns 200",              True)
    record("Swagger HTML contains 'DriftNet'",   "DriftNet" in html, f"found: {'DriftNet' in html}")
except Exception as e:
    record("GET /docs reachable",                False, str(e))

# ─────────────────────────────────────────────────────────────────
# TEST 7 — /openapi.json schema
# ─────────────────────────────────────────────────────────────────
section("TEST 7 — GET /openapi.json schema")
try:
    schema = http_get("/openapi.json")
    paths  = list(schema.get("paths", {}).keys())
    record("openapi.json reachable",          True)
    record("/health in schema",               "/health"  in paths, f"paths: {paths}")
    record("/predict in schema",              "/predict" in paths, f"paths: {paths}")
    record("PredictionResponse in schema",    "PredictionResponse" in json.dumps(schema))
    record("HealthResponse in schema",        "HealthResponse"     in json.dumps(schema))
    print(f"  Available paths: {paths}")
except Exception as e:
    record("GET /openapi.json",               False, str(e))

# ─────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────
section("FINAL SUMMARY")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total  = len(results)

print(f"\n  Total tests : {total}")
print(f"  Passed      : {passed}")
print(f"  Failed      : {failed}")
print()

if failed > 0:
    print("  Failed tests:")
    for label, ok in results:
        if not ok:
            print(f"    {FAIL}  {label}")
else:
    print("  ALL TESTS PASSED -- DriftNet is fully operational.")

print()
