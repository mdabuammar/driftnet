import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from app.inference import DriftNetInference, EXPECTED_CLINICAL_COLS

print("Loading DriftNet engine...")
engine = DriftNetInference()
print("Engine ready!\n")

samples = [
    "sample1546", "sample2376", "sample2889", # Stage I
    "sample7209", "sample7230", "sample7050", # Stage II
    "sample5510", "sample4869", "sample4826"  # Stage III
]

csv_path = os.path.join(os.path.dirname(__file__), "..", "sample_main", "Final_Processed_Data_with_MethylationID.csv")
df = pd.read_csv(csv_path)

print("=" * 80)
print("PREDICTIONS - 9 SAMPLES WITH EXACT CLINICAL DATA")
print("=" * 80)

correct = 0
total = 0

for s in samples:
    txt = os.path.join(os.path.dirname(__file__), "..", "sample_main", s + ".txt")
    if not os.path.exists(txt):
        print(f"{s}: FILE NOT FOUND")
        continue
    
    # Extract real clinical data from CSV
    row = df[df['methylation_sample_id'] == s]
    if len(row) == 0:
        print(f"{s}: METADATA NOT FOUND IN CSV")
        continue
    
    row = row.iloc[0]
    gt = row['stage_clean']
    
    clinical = {}
    for col in EXPECTED_CLINICAL_COLS:
        val = row[col]
        # Replace nan float with 'Unknown' string if it's a categorical feature that needs it, 
        # but our clinical encoder expects the same as training.
        # Actually our predict_stage expects whatever training used.
        if pd.isna(val):
            clinical[col] = "Unknown" if col != "diagnoses.age_at_diagnosis" else np.nan
        else:
            clinical[col] = val

    # Extract true latent features from CSV
    true_latent = []
    for i in range(1, 151):
        true_latent.append(row[f'latent_{i}'])
    true_latent = np.array(true_latent, dtype=np.float32)

    try:
        # Step 1 & 2
        methylation_raw, cpg_count = engine.parse_methylation_txt(txt)
        methylation_clean = engine.clean_methylation_array(methylation_raw)
        
        # Step 3 - PyTorch Encoder (just for MSE check)
        pred_latent = engine.get_latent_features(methylation_clean).flatten()
        mse = np.mean((pred_latent - true_latent)**2)
        mae = np.mean(np.abs(pred_latent - true_latent))
        
        print(f"{s}: PyTorch vs CSV Latent -> MSE = {mse:.1f} | MAE = {mae:.1f}")
        
        # ── BYPASS EXPERIMENT ──
        # Feed the TRUE latent features from the CSV directly into Step 4, 5, 6
        # to see if the Keras models predict perfectly!
        clinical_encoded = engine.encode_clinical_input(clinical)
        true_latent_batch = true_latent.reshape(1, -1)
        embedding = engine.get_contrastive_embedding(true_latent_batch, clinical_encoded)
        result = engine.predict_stage(embedding, clinical_encoded)
        
        pred   = result["predicted_stage"]
        conf   = result["confidence"] * 100
        tag    = "CORRECT" if pred == gt else "WRONG"
        if pred == gt:
            correct += 1
        total += 1
        probs  = result.get("probabilities", {})
        p1     = probs.get("Stage I",   0) * 100
        p2     = probs.get("Stage II",  0) * 100
        p3     = probs.get("Stage III", 0) * 100
        print(f"{s}: Pred={pred} ({conf:.1f}%) | True={gt} | {tag}")
        print(f"   Clinical: Age={clinical.get('diagnoses.age_at_diagnosis')} | Tissue={clinical.get('diagnoses.tissue_or_organ_of_origin')}")
        print(f"   Probs -> Stage I: {p1:.1f}%  Stage II: {p2:.1f}%  Stage III: {p3:.1f}%")
        print()
    except Exception as e:
        print(f"{s}: ERROR -> {e}\n")

print("=" * 80)
if total > 0:
    print(f"FINAL SCORE: {correct}/{total}  ({correct/total*100:.1f}%)")
print("=" * 80)
