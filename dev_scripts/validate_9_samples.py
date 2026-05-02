"""
validate_9_samples.py
======================
1. Parse each sample .txt file -> apply global MinMax scaling -> run through
   the PyTorch autoencoder -> get 150 latent features.
2. Compare those live-computed latent features against the pre-computed latent
   values stored in Final_Processed_Data_with_MethylationID.csv.
3. Run the FULL DriftNet inference pipeline on each sample and compare the
   predicted stage against Detailed_Sample_Accuracy.csv.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import joblib
import torch
import torch.nn as nn
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE      = Path(__file__).resolve().parent.parent
ASSET_DIR = BASE / "assets"
SAMPLE_DIR = BASE / "sample_main"

PROCESSED_CSV = SAMPLE_DIR / "Final_Processed_Data_with_MethylationID.csv"
ACCURACY_CSV  = SAMPLE_DIR / "Detailed_Sample_Accuracy.csv"

SAMPLE_FILES = sorted(SAMPLE_DIR.glob("sample*.txt"))
SAMPLE_NAMES = [f.stem for f in SAMPLE_FILES]   # e.g. ['sample1546', ...]

print("=" * 65)
print("  DriftNet 9-Sample End-to-End Validation")
print("=" * 65)
print(f"  Samples found : {len(SAMPLE_FILES)}")
for f in SAMPLE_FILES:
    print(f"    {f.name}")
print()

# ────────────────────────────────────────────────────────────────
# PART 1 — Load PyTorch encoder + global scaling
# ────────────────────────────────────────────────────────────────
class Encoder(nn.Module):
    def __init__(self, input_dim=550_000, latent_dim=150):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 1024), nn.BatchNorm1d(1024), nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(1024, 512),       nn.BatchNorm1d(512),  nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),        nn.BatchNorm1d(256),  nn.ReLU(),
            nn.Linear(256, latent_dim),
        )
    def forward(self, x):
        return self.encoder(x)

print("[1] Loading PyTorch encoder + global scaling...")
global_min   = np.load(str(ASSET_DIR / "global_min.npy")).astype(np.float32)
global_max   = np.load(str(ASSET_DIR / "global_max.npy")).astype(np.float32)
scale_range  = global_max - global_min
scale_range[scale_range == 0] = 1.0

checkpoint = torch.load(str(ASSET_DIR / "best_encoder_150latent.pth"),
                        map_location="cpu", weights_only=False)
is_flat = isinstance(checkpoint, dict) and all(
    isinstance(v, torch.Tensor) for v in checkpoint.values()
)
state_dict = checkpoint if is_flat else checkpoint.get(
    "encoder_state_dict", checkpoint.get("model_state_dict", checkpoint)
)
adjusted = {}
for k, v in state_dict.items():
    if k.startswith("decoder."): continue
    if not k.startswith("encoder."): k = f"encoder.{k}"
    adjusted[k] = v.float() if (isinstance(v, torch.Tensor) and v.dtype == torch.float16) else v

encoder = Encoder(input_dim=550_000, latent_dim=150)
encoder.load_state_dict(adjusted)
encoder.eval()
print(f"   Encoder ready. input_dim=550000, latent_dim=150\n")

# ────────────────────────────────────────────────────────────────
# PART 2 — Parse .txt -> latent (live computation)
# ────────────────────────────────────────────────────────────────
MAX_CPGS = 550_000

def parse_and_encode(txt_path: Path) -> np.ndarray:
    """Parse methylation .txt -> apply global scaling -> encoder -> (150,)"""
    df = pd.read_csv(txt_path, sep="\t", index_col=0, header=None, dtype=str)
    series = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    arr = series.values.astype(np.float32)
    # truncate / pad to 550K
    if len(arr) > MAX_CPGS:
        arr = arr[:MAX_CPGS]
    elif len(arr) < MAX_CPGS:
        arr = np.pad(arr, (0, MAX_CPGS - len(arr)), constant_values=np.nan)
    # clean NaN
    arr = np.nan_to_num(arr, nan=0.5, posinf=1.0, neginf=0.0)
    arr = np.clip(arr, 0.0, 1.0)
    # global MinMax scaling (MUST match training)
    arr = (arr - global_min) / scale_range
    arr = np.clip(arr, 0.0, 1.0).astype(np.float32)
    # encode
    tensor = torch.tensor(arr.reshape(1, -1), dtype=torch.float32)
    with torch.no_grad():
        latent = encoder(tensor).cpu().numpy()[0]
    return latent

print("[2] Parsing .txt files -> computing latent features live...")
live_latents = {}
for f in SAMPLE_FILES:
    print(f"   Processing {f.name} ...", end=" ", flush=True)
    live_latents[f.stem] = parse_and_encode(f)
    print("done")

# ────────────────────────────────────────────────────────────────
# PART 3 — Compare live latents vs CSV pre-computed latents
# ────────────────────────────────────────────────────────────────
print("\n[3] Comparing live-computed latents vs CSV pre-computed latents...")
df_csv = pd.read_csv(str(PROCESSED_CSV))
latent_cols = [f"latent_{i+1}" for i in range(150)]

print(f"\n{'Sample':<15} {'Max Diff':>12} {'Mean Diff':>12} {'Corr':>8} {'Match?':>8}")
print("-" * 60)

all_match = True
for name in SAMPLE_NAMES:
    row = df_csv[df_csv["methylation_sample_id"] == name]
    if row.empty:
        print(f"{name:<15} {'NOT FOUND IN CSV':>40}")
        all_match = False
        continue

    csv_lat  = row[latent_cols].values[0].astype(np.float32)
    live_lat = live_latents[name]

    max_diff  = float(np.abs(csv_lat - live_lat).max())
    mean_diff = float(np.abs(csv_lat - live_lat).mean())
    corr      = float(np.corrcoef(csv_lat, live_lat)[0, 1])
    match     = "OK" if max_diff < 0.1 else "DIFF"
    if max_diff >= 0.1: all_match = False

    print(f"{name:<15} {max_diff:>12.6f} {mean_diff:>12.6f} {corr:>8.6f} {match:>8}")

print()
if all_match:
    print("LATENT MATCH: Live encoder output matches CSV pre-computed latents.")
else:
    print("WARN  MISMATCH: Some latents differ from CSV values.")
    print("   This may indicate a different autoencoder checkpoint was used.")

# ────────────────────────────────────────────────────────────────
# PART 4 — Full DriftNet inference on all 9 samples
# ────────────────────────────────────────────────────────────────
print("\n[4] Running full DriftNet inference pipeline on all 9 samples...")
print("    (Loading all models — this takes ~30 seconds)\n")

# Load clinical encoders + scalers
clinical_label_encoders  = joblib.load(str(ASSET_DIR / "clinical_label_encoders.pkl"))
stage_encoder            = joblib.load(str(ASSET_DIR / "stage_encoder.pkl"))
contrastive_scaler       = joblib.load(str(ASSET_DIR / "contrastive_scaler.pkl"))
driftnet_clinical_scaler = joblib.load(str(ASSET_DIR / "driftnet_clinical_scaler.pkl"))

# Get clinical rows for our 9 samples from the processed CSV
clinical_cols = [
    "demographic.gender", "demographic.vital_status", "samples.sample_type",
    "cases.disease_type", "samples.tissue_type", "diagnoses.primary_diagnosis",
    "diagnoses.tissue_or_organ_of_origin", "diagnoses.morphology",
    "diagnoses.age_at_diagnosis", "diagnoses.prior_treatment",
    "diagnoses.prior_malignancy", "demographic.race", "demographic.ethnicity",
]

def encode_clinical_row(row):
    parts = []
    for col in clinical_cols:
        val = row[col]
        if col == "diagnoses.age_at_diagnosis":
            parts.append(float(val))
        else:
            le = clinical_label_encoders[col]
            parts.append(float(le.transform([str(val)])[0]))
    return np.array(parts, dtype=np.float32).reshape(1, -1)

# Load Keras models (compat mode for contrastive encoder)
import os
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Monkey-patch Dense for Keras version compat
_orig_dense_from_config = layers.Dense.from_config.__func__
@classmethod
def _compat_dense_from_config(cls, config):
    config = dict(config); config.pop("quantization_config", None)
    return _orig_dense_from_config(cls, config)
layers.Dense.from_config = _compat_dense_from_config

@keras.utils.register_keras_serializable(package="val_script")
class L2Normalize(layers.Layer):
    def call(self, inputs): return tf.nn.l2_normalize(inputs, axis=1)
    def get_config(self): return super().get_config()

# Rebuild contrastive encoder and load weights
import zipfile, tempfile
reg = keras.regularizers.l2(5e-5)
cont_enc = keras.Sequential([
    layers.Input(shape=(163,), name="inp"),
    layers.Dense(512, activation="relu", kernel_regularizer=reg, name="d1"),
    layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="bn1"),
    layers.Dropout(0.35, name="dr1"),
    layers.Dense(256, activation="relu", kernel_regularizer=reg, name="d2"),
    layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="bn2"),
    layers.Dropout(0.25, name="dr2"),
    layers.Dense(128, activation=None, kernel_regularizer=reg, name="emb"),
    L2Normalize(name="l2"),
], name="Encoder")

with tempfile.TemporaryDirectory() as tmpdir:
    with zipfile.ZipFile(str(ASSET_DIR / "contrastive_encoder.keras"), "r") as zf:
        w_name = next(n for n in zf.namelist() if n.endswith(".h5"))
        zf.extract(w_name, tmpdir)
        cont_enc.load_weights(os.path.join(tmpdir, w_name))
print("   Contrastive encoder loaded.")

driftnet_model = keras.models.load_model(
    str(ASSET_DIR / "best_driftnet_final.keras"),
    compile=False, safe_mode=False,
    custom_objects={"tf": tf, "L2Normalize": L2Normalize}
)
print("   DriftNet model loaded.")

# Load expected results
acc_df = pd.read_csv(str(ACCURACY_CSV))

# Run inference on each of the 9 samples
print()
print(f"\n{'Sample':<15} {'True Stage':<12} {'Expected Pred':<14} {'Our Pred':<14} {'Conf':>6} {'Match?':>8}")
print("-" * 75)

correct = 0
results = []
for name in SAMPLE_NAMES:
    # Get CSV row for clinical data
    row = df_csv[df_csv["methylation_sample_id"] == name].iloc[0]
    true_stage = row["stage_clean"]

    # Get expected prediction from accuracy CSV
    acc_row = acc_df[acc_df["methylation_sample_id"] == name]
    expected_pred = acc_row["Predicted_Stage"].values[0] if not acc_row.empty else "N/A"

    # Encode clinical
    X_clin = encode_clinical_row(row)   # (1, 13)

    # Combine latent_150 + clinical_13 -> scale -> contrastive embedding
    latent_150 = live_latents[name].reshape(1, -1)   # (1, 150)
    combined   = np.hstack([latent_150, X_clin])     # (1, 163)
    scaled     = contrastive_scaler.transform(combined).astype(np.float32)
    embedding  = cont_enc.predict(scaled, verbose=0).astype(np.float32)   # (1, 128)

    # Scale clinical for DriftNet
    X_clin_scaled = driftnet_clinical_scaler.transform(X_clin).astype(np.float32)

    # DriftNet prediction
    probs      = driftnet_model.predict([embedding, X_clin_scaled], verbose=0)[0]
    pred_idx   = int(np.argmax(probs))
    pred_label = str(stage_encoder.inverse_transform([pred_idx])[0])
    confidence = float(np.max(probs))

    match = pred_label == expected_pred
    if match: correct += 1

    tag = "OK" if match else "FAIL"
    print(f"{name:<15} {true_stage:<12} {expected_pred:<14} {pred_label:<14} {confidence:>6.3f} {tag:>8}")
    results.append({
        "sample": name, "true_stage": true_stage,
        "expected_pred": expected_pred, "our_pred": pred_label,
        "confidence": round(confidence, 4),
        "matches_expected": match
    })

print()
print("=" * 75)
print(f"  Matches with expected predictions : {correct}/{len(SAMPLE_NAMES)}")
print(f"  Agreement rate                    : {correct/len(SAMPLE_NAMES)*100:.1f}%")
print()

# Per-class summary
for stage in ["Stage I", "Stage II", "Stage III"]:
    subset = [r for r in results if r["true_stage"] == stage]
    if subset:
        right = sum(1 for r in subset if r["our_pred"] == r["true_stage"])
        print(f"  {stage}: {right}/{len(subset)} correct vs true label")

print()
print("Done.")
