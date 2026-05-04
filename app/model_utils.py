"""
DriftNet model loading utilities.

Centralised helpers for loading and verifying all deployment assets.
Import these in inference.py or any validation/testing script.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import torch
import torch.nn as nn
from tensorflow import keras
import tensorflow as tf

logger = logging.getLogger("driftnet.model_utils")

# ─────────────────────────────────────────────────────────────────
# Required asset filenames
# ─────────────────────────────────────────────────────────────────
REQUIRED_ASSETS = [
    "best_encoder_150latent.pth",
    "global_min.npy",
    "global_max.npy",
    "contrastive_encoder.keras",
    "best_driftnet_final.keras",
    "clinical_label_encoders.pkl",
    "clinical_label_mappings.json",
    "contrastive_scaler.pkl",
    "driftnet_clinical_scaler.pkl",
    "stage_encoder.pkl",
    "preprocessing_metadata.json",
]


def verify_assets(asset_dir: str | Path) -> None:
    """
    Raise FileNotFoundError listing all missing assets.
    Call this at startup before attempting to load any model.
    """
    import shutil
    asset_dir = Path(asset_dir)

    # ── Auto-download the 4.2GB model from Hugging Face if missing ──
    large_model_name = "best_encoder_150latent.pth"
    large_model_path = asset_dir / large_model_name
    
    if not large_model_path.exists():
        logger.warning(
            "Large model '%s' not found locally. Downloading from Hugging Face "
            "(mdabuammar/driftnet-model). This may take several minutes...", 
            large_model_name
        )
        try:
            from huggingface_hub import hf_hub_download
            cached_path = hf_hub_download(
                repo_id="mdabuammar/driftnet-model", 
                filename=large_model_name
            )
            # Copy from huggingface cache into our assets folder
            shutil.copy2(cached_path, large_model_path)
            logger.info("Successfully downloaded and placed '%s'", large_model_name)
        except ImportError:
            logger.error("huggingface_hub is not installed. Run: pip install huggingface_hub")
        except Exception as e:
            logger.error("Failed to download model from Hugging Face: %s", e)

    missing = [f for f in REQUIRED_ASSETS if not (asset_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required asset files in '{asset_dir}':\n"
            + "\n".join(f"  ✗ {f}" for f in missing)
        )
    logger.info("All %d required assets verified in '%s'", len(REQUIRED_ASSETS), asset_dir)


def load_joblib(path: str | Path, label: str = "") -> object:
    """
    Load a joblib-serialised artifact (LabelEncoder, StandardScaler, etc.)
    with descriptive error context.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Joblib asset not found: {path}")
    try:
        obj = joblib.load(path)
        logger.info("Loaded joblib artifact: %s%s", path.name, f" ({label})" if label else "")
        return obj
    except Exception as exc:
        raise RuntimeError(f"Failed to load joblib artifact '{path.name}': {exc}") from exc


def load_json(path: str | Path) -> dict:
    """Load and return a JSON file as a dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON asset not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded JSON: %s", path.name)
    return data


def load_keras_model(
    path: str | Path,
    custom_objects: dict | None = None,
) -> keras.Model:
    """
    Load a Keras `.keras` model with safe_mode=False (required for Lambda layers).

    Parameters
    ----------
    path : path to the .keras file
    custom_objects : optional dict of custom classes/functions (e.g. L2Normalize)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Keras model not found: {path}")
    try:
        model = keras.models.load_model(
            path,
            compile=False,
            safe_mode=False,
            custom_objects=custom_objects or {},
        )
        logger.info("Loaded Keras model: %s", path.name)
        return model
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load Keras model '{path.name}': {exc}"
        ) from exc


def load_pytorch_encoder(
    path: str | Path,
    encoder_cls: type[nn.Module],
    device: torch.device | None = None,
) -> nn.Module:
    """
    Load a PyTorch encoder checkpoint and return an eval-mode model.

    Handles:
    - torch.save(model.state_dict(), path)  → flat state dict (training notebook format)
    - torch.save({'encoder_state_dict': ..., ...}, path)  → wrapped dict
    - fp16 → float32 weight conversion for CPU stability
    - Decoder key filtering (Autoencoder saves both encoder + decoder)
    - Automatic key prefix normalisation (prepend "encoder." if missing)
    """
    path = Path(path)
    device = device or torch.device("cpu")

    if not path.exists():
        raise FileNotFoundError(f"PyTorch checkpoint not found: {path}")

    raw_checkpoint = torch.load(path, map_location=device, weights_only=False)

    # Detect flat vs wrapped checkpoint
    is_flat = isinstance(raw_checkpoint, dict) and all(
        isinstance(v, torch.Tensor) for v in raw_checkpoint.values()
    )

    if is_flat:
        # torch.save(model.state_dict(), path) — infer input_dim from first Linear weight
        first_key = next(
            k for k in raw_checkpoint
            if "encoder.0.weight" in k or (k.endswith(".weight") and "encoder" in k)
        )
        input_dim  = raw_checkpoint[first_key].shape[1]
        latent_dim = 150
        logger.info("Flat state dict: input_dim=%d, latent_dim=%d", input_dim, latent_dim)
        state_dict = raw_checkpoint
    else:
        input_dim  = int(raw_checkpoint.get("input_dim",  550_000))
        latent_dim = int(raw_checkpoint.get("latent_dim", 150))
        if "encoder_state_dict" in raw_checkpoint:
            state_dict = raw_checkpoint["encoder_state_dict"]
        elif "model_state_dict" in raw_checkpoint:
            state_dict = raw_checkpoint["model_state_dict"]
        else:
            state_dict = raw_checkpoint
        logger.info("Wrapped checkpoint: input_dim=%d, latent_dim=%d", input_dim, latent_dim)

    model = encoder_cls(input_dim=input_dim, latent_dim=latent_dim)

    # Filter decoder keys, normalise prefix, convert fp16→float32
    adjusted: dict = {}
    fp16_count = 0
    for k, v in state_dict.items():
        if k.startswith("decoder."):
            continue   # skip decoder — only encoder weights needed
        if not k.startswith("encoder."):
            k = f"encoder.{k}"
        if isinstance(v, torch.Tensor) and v.dtype == torch.float16:
            v = v.float()
            fp16_count += 1
        adjusted[k] = v

    if fp16_count:
        logger.info("Converted %d fp16 tensors to float32", fp16_count)

    model.load_state_dict(adjusted)
    model.eval()
    logger.info("PyTorch encoder loaded and ready (device=%s)", device)
    return model
