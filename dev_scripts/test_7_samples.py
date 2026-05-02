import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from app.inference import DriftNetInference

print("Loading DriftNet engine...")
engine = DriftNetInference()
print("Engine ready!\n")

samples = [
    "sample1727", "sample1002", "sample6788",
    "sample152",  "sample6796", "sample1384", "sample7020"
]
ground_truth = {s: "Stage III" for s in samples}

clinical = {
    "demographic.gender": "female",
    "demographic.vital_status": "alive",
    "samples.sample_type": "Primary Tumor",
    "cases.disease_type": "Adenomas and Adenocarcinomas",
    "samples.tissue_type": "Not Reported",
    "diagnoses.primary_diagnosis": "Adenocarcinoma, NOS",
    "diagnoses.tissue_or_organ_of_origin": "Breast, NOS",
    "diagnoses.morphology": "8140/3",
    "diagnoses.age_at_diagnosis": 20000,
    "diagnoses.prior_treatment": "No",
    "diagnoses.prior_malignancy": "no",
    "demographic.race": "white",
    "demographic.ethnicity": "not hispanic or latino"
}

print("=" * 65)
print("PREDICTIONS - NEW RETRAINED MODEL")
print("=" * 65)

correct = 0
total = 0

for s in samples:
    txt = os.path.join(os.path.dirname(__file__), "..", "sample_main", s + ".txt")
    if not os.path.exists(txt):
        print(f"{s}: FILE NOT FOUND")
        continue
    try:
        result = engine.predict_stage(txt, clinical)
        pred   = result["predicted_stage"]
        conf   = result["confidence"] * 100
        gt     = ground_truth[s]
        tag    = "CORRECT" if pred == gt else "WRONG"
        if pred == gt:
            correct += 1
        total += 1
        probs  = result.get("all_probabilities", {})
        p1     = probs.get("Stage I",   0) * 100
        p2     = probs.get("Stage II",  0) * 100
        p3     = probs.get("Stage III", 0) * 100
        print(f"{s}: {pred} ({conf:.1f}%) | True={gt} | {tag}")
        print(f"   Probs -> Stage I: {p1:.1f}%  Stage II: {p2:.1f}%  Stage III: {p3:.1f}%")
    except Exception as e:
        print(f"{s}: ERROR -> {e}")

print()
print(f"FINAL SCORE: {correct}/{total}  ({correct/total*100:.1f}%)")
print("=" * 65)
