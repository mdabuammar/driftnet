"""
fix_keras_models.py
===================
Rebuilds contrastive_encoder.keras and best_driftnet_final.keras
from their saved weights WITHOUT relying on the config metadata.

This eliminates two bugs:
  1. `quantization_config` — a Keras 3.x Colab field unrecognized by TF2.17
  2. Lambda layer bytecode — Python version mismatch on Lambda layers

Run once from the deployment root:
    python fix_keras_models.py

This produces:
    assets/contrastive_encoder_fixed.keras
    assets/best_driftnet_final_fixed.keras

Then the inference.py is updated to point to these fixed files.
"""
import os
import sys
import zipfile
import json
import numpy as np

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import warnings
warnings.filterwarnings("ignore")

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# dev_scripts/ is one level below the project root
ASSET_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
ASSET_DIR = os.path.normpath(ASSET_DIR)


# ─────────────────────────────────────────────────────────────────
# Custom L2 normalisation layer (replaces the Lambda layer)
# ─────────────────────────────────────────────────────────────────
@keras.utils.register_keras_serializable(package="driftnet")
class L2Normalize(layers.Layer):
    def call(self, inputs):
        return tf.nn.l2_normalize(inputs, axis=1)

    def get_config(self):
        return super().get_config()


# ─────────────────────────────────────────────────────────────────
# Architecture: Contrastive Encoder  (163 → 512 → 256 → 128 L2)
# Updated to match new training notebook (bigger encoder)
# ─────────────────────────────────────────────────────────────────
def build_contrastive_encoder(input_dim=163):
    model = keras.Sequential(
        [
            layers.Input(shape=(input_dim,), name="input_layer"),
            layers.Dense(512, activation="relu",   name="dense"),
            layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="batch_normalization"),
            layers.Dropout(0.5,                    name="dropout"),
            layers.Dense(256, activation="relu",   name="dense_1"),
            layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="batch_normalization_1"),
            layers.Dropout(0.4,                    name="dropout_1"),
            layers.Dense(128, activation="linear", name="dense_2"),
            L2Normalize(                           name="l2_normalize"),
        ],
        name="Contrastive_Encoder",
    )
    return model


# ─────────────────────────────────────────────────────────────────
# Helper: load weights from a .keras archive into a fresh model
# ─────────────────────────────────────────────────────────────────
def load_weights_from_keras_archive(keras_path: str, fresh_model: keras.Model) -> keras.Model:
    """
    Extract model.weights.h5 from the .keras zip archive and load
    weights into the fresh model by name.
    """
    import tempfile
    import h5py

    with tempfile.TemporaryDirectory() as tmp:
        # .keras files are zip archives
        with zipfile.ZipFile(keras_path, "r") as zf:
            names = zf.namelist()
            print(f"  Archive contents: {names}")

            # Find the weights file
            weights_file = None
            for name in names:
                if "weights" in name and name.endswith(".h5"):
                    weights_file = name
                    break
            if weights_file is None:
                raise FileNotFoundError(
                    f"No weights .h5 file found in {keras_path}. "
                    f"Contents: {names}"
                )
            weights_path = os.path.join(tmp, "weights.h5")
            zf.extract(weights_file, tmp)
            # The extracted file may be in a subfolder
            extracted = os.path.join(tmp, weights_file)

        # Build the model so layers are created
        if isinstance(fresh_model.input_shape, list):
            dummy = [np.zeros((1, shape[1]), dtype=np.float32) for shape in fresh_model.input_shape]
        else:
            dummy = np.zeros((1, fresh_model.input_shape[1]), dtype=np.float32)
            
        fresh_model(dummy, training=False)

        # Load weights by name
        fresh_model.load_weights(extracted)
        print(f"  Loaded weights from: {weights_file}")

    return fresh_model


# ─────────────────────────────────────────────────────────────────
# Fix contrastive_encoder.keras
# ─────────────────────────────────────────────────────────────────
def get_contrastive_input_dim(keras_path):
    """Read input_dim from the saved keras archive config."""
    try:
        with zipfile.ZipFile(keras_path, "r") as zf:
            if "config.json" in zf.namelist():
                with zf.open("config.json") as f:
                    cfg = json.load(f)
                # Walk config to find input shape
                def find_input_dim(obj):
                    if isinstance(obj, dict):
                        if obj.get("class_name") in ("InputLayer", "Input"):
                            shape = obj.get("config", {}).get("batch_input_shape") or \
                                    obj.get("config", {}).get("shape")
                            if shape and len(shape) > 1:
                                return shape[-1]
                        for v in obj.values():
                            r = find_input_dim(v)
                            if r: return r
                    elif isinstance(obj, list):
                        for item in obj:
                            r = find_input_dim(item)
                            if r: return r
                    return None
                dim = find_input_dim(cfg)
                if dim:
                    print(f"  Detected input_dim from config: {dim}")
                    return int(dim)
    except Exception as e:
        print(f"  Could not read config ({e}), defaulting input_dim=163")
    return 163

def fix_contrastive_encoder():
    src  = os.path.join(ASSET_DIR, "contrastive_encoder.keras")
    dst  = os.path.join(ASSET_DIR, "contrastive_encoder_fixed.keras")
    dst2 = os.path.join(ASSET_DIR, "contrastive_encoder_clean.keras")

    print(f"\n[1/2] Rebuilding contrastive encoder from: {src}")
    input_dim = get_contrastive_input_dim(src)
    fresh = build_contrastive_encoder(input_dim=input_dim)

    fresh = load_weights_from_keras_archive(src, fresh)

    fresh.save(dst)
    fresh.save(dst2)
    print(f"  Saved -> {dst}")
    print(f"  Saved -> {dst2}")

    # Verify shapes
    dummy = np.zeros((2, input_dim), dtype=np.float32)
    out   = fresh(dummy, training=False)
    assert out.shape == (2, 128), f"Bad contrastive output shape: {out.shape}"
    print(f"  Verified: input (2,{input_dim}) -> output {tuple(out.shape)} OK")
    return fresh


# ─────────────────────────────────────────────────────────────────
# Discover DriftNet output size from archive config
# ─────────────────────────────────────────────────────────────────
def read_driftnet_num_classes(keras_path: str) -> int:
    """Read num output classes from archive config.json."""
    with zipfile.ZipFile(keras_path, "r") as zf:
        if "config.json" in zf.namelist():
            with zf.open("config.json") as f:
                cfg = json.load(f)
            # Walk the config tree looking for the last Dense units
            def find_units(obj):
                units = None
                if isinstance(obj, dict):
                    if obj.get("class_name") == "Dense":
                        u = obj.get("config", {}).get("units")
                        if u:
                            units = u
                    for v in obj.values():
                        sub = find_units(v)
                        if sub:
                            units = sub
                elif isinstance(obj, list):
                    for item in obj:
                        sub = find_units(item)
                        if sub:
                            units = sub
                return units
            n = find_units(cfg)
            if n:
                print(f"  Detected DriftNet output classes: {n}")
                return int(n)
    return 3  # default: Stage I / II / III


# ─────────────────────────────────────────────────────────────────
# Build DriftNet model (dual-input, functional API)
# ─────────────────────────────────────────────────────────────────
def build_driftnet(embedding_dim=128, clinical_dim=13, num_classes=3):
    # Branch 1: Contrastive Embedding
    inp_emb = layers.Input(shape=(embedding_dim,), name="embedding_input")
    x1 = layers.GaussianNoise(0.02)(inp_emb)
    x1 = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(0.005), name="emb_dense_1")(x1)
    x1 = layers.Dropout(0.4, name="emb_drop_1")(x1)

    # Branch 2: Clinical Features
    inp_clin = layers.Input(shape=(clinical_dim,), name="clinical_input")
    x2 = layers.Dense(32, activation="relu", kernel_regularizer=keras.regularizers.l2(0.005), name="clin_dense_1")(inp_clin)
    x2 = layers.Dropout(0.3, name="clin_drop_1")(x2)

    # Merge
    merged = layers.Concatenate(name="merge")([x1, x2])
    x = layers.Dense(64, activation="relu", kernel_regularizer=keras.regularizers.l2(0.005), name="merge_dense_1")(merged)
    x = layers.Dropout(0.4, name="merge_drop_1")(x)
    
    # Output
    out = layers.Dense(num_classes, activation="softmax", name="output")(x)

    model = keras.Model(inputs=[inp_emb, inp_clin], outputs=out, name="DriftNet")
    return model


def fix_driftnet():
    src = os.path.join(ASSET_DIR, "best_driftnet_final.keras")
    dst = os.path.join(ASSET_DIR, "best_driftnet_final_fixed.keras")

    print(f"\n[2/2] Rebuilding DriftNet from: {src}")

    num_classes = read_driftnet_num_classes(src)
    fresh = build_driftnet(embedding_dim=128, clinical_dim=13, num_classes=num_classes)

    fresh = load_weights_from_keras_archive(src, fresh)
    fresh.save(dst)
    print(f"  Saved -> {dst}")

    # Verify
    emb   = np.zeros((2, 128), dtype=np.float32)
    clin  = np.zeros((2, 13),  dtype=np.float32)
    out   = fresh([emb, clin], training=False)
    assert out.shape == (2, num_classes), f"Bad DriftNet output shape: {out.shape}"
    print(f"  Verified: [emb(2,128), clin(2,13)] -> {tuple(out.shape)} OK")
    return fresh


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
def convert_pth_to_fp16():
    """Convert full-precision .pth to fp16 for faster Windows inference."""
    import torch
    import torch.nn as nn

    src = os.path.join(ASSET_DIR, "best_encoder_150latent.pth")
    dst = os.path.join(ASSET_DIR, "best_encoder_150latent_fp16.pth")

    if not os.path.exists(src):
        print(f"\n[SKIP] {src} not found, skipping fp16 conversion.")
        return

    print(f"\n[0/2] Converting PyTorch encoder to fp16...")
    ckpt = torch.load(src, map_location="cpu")
    fp16_state = {k: v.half() if v.is_floating_point() else v
                  for k, v in ckpt["model_state_dict"].items()}
    ckpt["model_state_dict"] = fp16_state
    torch.save(ckpt, dst)
    print(f"  Saved fp16 model -> {dst}")
    size_mb = os.path.getsize(dst) / 1024 / 1024
    print(f"  File size: {size_mb:.1f} MB")


if __name__ == "__main__":
    print("=" * 60)
    print("DriftNet Model Fixer (Updated for new architecture)")
    print(f"ASSET_DIR: {ASSET_DIR}")
    print("=" * 60)

    # Step 0: Convert PyTorch encoder to fp16
    try:
        convert_pth_to_fp16()
    except Exception as e:
        print(f"\n[WARNING] fp16 conversion failed: {e}")
        print("You may need to install torch: pip install torch")

    # Step 1: Fix contrastive encoder
    try:
        fix_contrastive_encoder()
    except Exception as e:
        print(f"\n[ERROR] Contrastive encoder fix failed: {e}")
        print("Check that assets/contrastive_encoder.keras exists and")
        print("that its architecture matches build_contrastive_encoder().")
        sys.exit(1)

    # Step 2: Fix DriftNet
    try:
        fix_driftnet()
    except Exception as e:
        print(f"\n[ERROR] DriftNet fix failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("SUCCESS — All models fixed and ready!")
    print("  assets/best_encoder_150latent_fp16.pth")
    print("  assets/contrastive_encoder_fixed.keras")
    print("  assets/best_driftnet_final_fixed.keras")
    print("=" * 60)
