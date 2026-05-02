import joblib
import torch
from tensorflow import keras

ENCODER_PATH = "assets/best_encoder_150latent_fp16.pth"
CONTRASTIVE_PATH = "assets/contrastive_encoder.keras"
DRIFTNET_PATH = "assets/best_driftnet_final.keras"

CLINICAL_ENCODERS_PATH = "assets/clinical_label_encoders.pkl"
CONTRASTIVE_SCALER_PATH = "assets/contrastive_scaler.pkl"
DRIFTNET_SCALER_PATH = "assets/driftnet_clinical_scaler.pkl"
STAGE_ENCODER_PATH = "assets/stage_label_encoder.pkl"

print("Loading joblib objects...")
clinical_encoders = joblib.load(CLINICAL_ENCODERS_PATH)
contrastive_scaler = joblib.load(CONTRASTIVE_SCALER_PATH)
driftnet_scaler = joblib.load(DRIFTNET_SCALER_PATH)
stage_encoder = joblib.load(STAGE_ENCODER_PATH)

print("Loading Keras models...")
# The saved models include Lambda layers, so trusted deserialization is required.
contrastive_model = keras.models.load_model(CONTRASTIVE_PATH, compile=False, safe_mode=False)
driftnet_model = keras.models.load_model(DRIFTNET_PATH, compile=False, safe_mode=False)

print("Loading PyTorch checkpoint...")
ckpt = torch.load(ENCODER_PATH, map_location="cpu")

print("Checkpoint keys:", ckpt.keys() if isinstance(ckpt, dict) else type(ckpt))
print("All files loaded successfully!")

