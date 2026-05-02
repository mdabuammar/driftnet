import os
import json
import logging
import traceback
import uuid
import joblib
import numpy as np
import pandas as pd

# ── Stability settings for TF + PyTorch coexistence on Windows ──
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import torch
import torch.nn as nn
from pathlib import Path
from tensorflow import keras
from tensorflow.keras import layers
import tensorflow as tf  # Required for Lambda layers in saved models


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("driftnet.inference")


# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
ASSET_DIR = BASE_DIR / "assets"

ENCODER_PATH              = ASSET_DIR / "best_encoder_150latent.pth"
CONTRASTIVE_MODEL_PATH    = ASSET_DIR / "contrastive_encoder.keras"
DRIFTNET_MODEL_PATH       = ASSET_DIR / "best_driftnet_final.keras"

CLINICAL_ENCODERS_PATH    = ASSET_DIR / "clinical_label_encoders.pkl"
CLINICAL_MAPPINGS_PATH    = ASSET_DIR / "clinical_label_mappings.json"
CONTRASTIVE_SCALER_PATH   = ASSET_DIR / "contrastive_scaler.pkl"
DRIFTNET_SCALER_PATH      = ASSET_DIR / "driftnet_clinical_scaler.pkl"
PREPROCESS_META_PATH      = ASSET_DIR / "preprocessing_metadata.json"
GLOBAL_MIN_PATH           = ASSET_DIR / "global_min.npy"
GLOBAL_MAX_PATH           = ASSET_DIR / "global_max.npy"
# notebook saves as stage_encoder.pkl; also accept stage_label_encoder.pkl
_stage_enc_1              = ASSET_DIR / "stage_encoder.pkl"
_stage_enc_2              = ASSET_DIR / "stage_label_encoder.pkl"
STAGE_ENCODER_PATH        = _stage_enc_1 if _stage_enc_1.exists() else _stage_enc_2


# =========================
# CONSTANTS
# =========================
MAX_CPGS = 550_000

# Expected probe count range for TCGA sesame level3 betas files.
# EPIC array ≈ 866 K probes; 450 K array ≈ 485 K probes.
# Training was performed on EPIC arrays truncated to 550 K.
EXPECTED_CPG_MIN = 400_000
EXPECTED_CPG_MAX = 900_000

# Confidence level thresholds (3-class baseline random = 0.33)
CONFIDENCE_HIGH_THRESHOLD   = 0.70
CONFIDENCE_MEDIUM_THRESHOLD = 0.50
CONFIDENCE_WARNING_THRESHOLD = 0.60

MISSING_STRINGS = {"", "na", "n/a", "nan", "none", "null", "unknown", "--", "---"}

# Exact 13 clinical fields required by DriftNet, in order
EXPECTED_CLINICAL_COLS = [
    "demographic.gender",
    "demographic.vital_status",
    "samples.sample_type",
    "cases.disease_type",
    "samples.tissue_type",
    "diagnoses.primary_diagnosis",
    "diagnoses.tissue_or_organ_of_origin",
    "diagnoses.morphology",
    "diagnoses.age_at_diagnosis",
    "diagnoses.prior_treatment",
    "diagnoses.prior_malignancy",
    "demographic.race",
    "demographic.ethnicity",
]


# =========================
# PYTORCH ENCODER
# Architecture MUST match Autoencoder training notebook exactly:
#   Linear(input_dim,1024) → BN → ReLU → Dropout(0.2)
#   → Linear(1024,512)    → BN → ReLU → Dropout(0.2)
#   → Linear(512,256)     → BN → ReLU
#   → Linear(256,latent_dim)
# Only the encoder half is loaded (decoder keys are filtered out).
# =========================
class Encoder(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 150):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 1024), nn.BatchNorm1d(1024), nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(1024, 512),       nn.BatchNorm1d(512),  nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),        nn.BatchNorm1d(256),  nn.ReLU(),
            nn.Linear(256, latent_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)


# =========================
# CUSTOM KERAS LAYERS
# Registered so Keras can deserialize the models correctly.
# =========================
@keras.utils.register_keras_serializable(package="driftnet")
class L2Normalize(layers.Layer):
    def call(self, inputs):
        return tf.nn.l2_normalize(inputs, axis=1)

    def get_config(self):
        return super().get_config()


# =========================
# COMPATIBILITY PATCH
# Models saved on Colab (newer Keras) include 'quantization_config' in Dense
# layer configs. Deployment Keras doesn't recognise it and crashes on load.
# Monkey-patching Dense.__init__ and Dense.from_config fixes this globally
# without requiring a model re-export.
# =========================
_orig_dense_init = layers.Dense.__init__
def _compat_dense_init(self, *args, quantization_config=None, **kwargs):
    _orig_dense_init(self, *args, **kwargs)
layers.Dense.__init__ = _compat_dense_init

_orig_dense_from_config = layers.Dense.from_config.__func__
@classmethod
def _compat_dense_from_config(cls, config):
    config = dict(config)
    config.pop("quantization_config", None)
    return _orig_dense_from_config(cls, config)
layers.Dense.from_config = _compat_dense_from_config
# =========================
# MAIN INFERENCE CLASS
# =========================
class DriftNetInference:

    # ── helpers ──────────────────────────────────────────────────
    @staticmethod
    def _bind_tf_to_lambda_layers(model) -> None:
        """Ensure deserialized Lambda layers can resolve `tf` at call time."""
        for layer in model.layers:
            fn = getattr(layer, "function", None)
            if fn is not None and hasattr(fn, "__globals__"):
                fn.__globals__.setdefault("tf", tf)


    @staticmethod
    def _build_and_load_contrastive_encoder(
        path: Path, input_dim: int = 163, emb_dim: int = 128
    ) -> keras.Model:
        """
        Rebuild the Phase 3 contrastive encoder and load weights from .keras zip.

        The .keras format is a zip archive containing:
          model.weights.h5  ← weight tensors (what we need)
          config.json       ← architecture JSON (we skip this)
          metadata.json

        We rebuild the known architecture here (replacing the problematic
        Lambda layer with our L2Normalize custom layer) then inject the
        weights by name so the layer graph is correctly populated.
        """
        import zipfile, tempfile

        reg = keras.regularizers.l2(5e-5)
        model = keras.Sequential([
            layers.Input(shape=(input_dim,), name="inp"),
            layers.Dense(512, activation="relu", kernel_regularizer=reg, name="d1"),
            layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="bn1"),
            layers.Dropout(0.35, name="dr1"),
            layers.Dense(256, activation="relu", kernel_regularizer=reg, name="d2"),
            layers.BatchNormalization(momentum=0.99, epsilon=0.001, name="bn2"),
            layers.Dropout(0.25, name="dr2"),
            layers.Dense(emb_dim, activation=None, kernel_regularizer=reg, name="emb"),
            L2Normalize(name="l2"),
        ], name="Encoder")

        # Extract weights from the .keras zip and load them
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(str(path), "r") as zf:
                names = zf.namelist()
                # weights file is usually 'model.weights.h5'
                w_candidates = [n for n in names if n.endswith(".weights.h5") or n.endswith(".h5")]
                if not w_candidates:
                    raise RuntimeError(
                        f"No .h5 weights file found inside {path.name}. "
                        f"Archive contents: {names}"
                    )
                w_name = w_candidates[0]
                zf.extract(w_name, tmpdir)
                w_path = os.path.join(tmpdir, w_name)
                model.load_weights(w_path)
                logger.info(
                    "Contrastive encoder weights loaded from '%s' inside '%s'",
                    w_name, path.name,
                )

        return model


    @staticmethod
    def _confidence_level(confidence: float) -> str:
        if confidence >= CONFIDENCE_HIGH_THRESHOLD:
            return "high"
        if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
            return "medium"
        return "low"

    # ── initialization ───────────────────────────────────────────
    def __init__(self):
        logger.info("Initializing DriftNetInference")
        self.device = torch.device("cpu")
        torch.set_num_threads(1)
        tf.config.threading.set_intra_op_parallelism_threads(1)
        tf.config.threading.set_inter_op_parallelism_threads(1)

        # ── Validate assets ──────────────────────────────────────
        missing_assets = [
            p for p in [
                ENCODER_PATH, CONTRASTIVE_MODEL_PATH, DRIFTNET_MODEL_PATH,
                CLINICAL_ENCODERS_PATH, CLINICAL_MAPPINGS_PATH,
                CONTRASTIVE_SCALER_PATH, DRIFTNET_SCALER_PATH,
                GLOBAL_MIN_PATH, GLOBAL_MAX_PATH,
                PREPROCESS_META_PATH, STAGE_ENCODER_PATH,
            ]
            if not p.exists()
        ]
        if missing_assets:
            raise FileNotFoundError(
                f"Missing required assets: {[str(p) for p in missing_assets]}"
            )

        # ── Load metadata ────────────────────────────────────────
        with open(PREPROCESS_META_PATH, "r", encoding="utf-8") as f:
            self.meta = json.load(f)

        # ── Load preprocessing artifacts ─────────────────────────
        logger.info("Loading preprocessing artifacts")
        self.clinical_label_encoders  = joblib.load(CLINICAL_ENCODERS_PATH)
        self.contrastive_scaler       = joblib.load(CONTRASTIVE_SCALER_PATH)
        self.driftnet_clinical_scaler = joblib.load(DRIFTNET_SCALER_PATH)
        self.stage_label_encoder      = joblib.load(STAGE_ENCODER_PATH)

        # ── Load global min/max for autoencoder scaling ───────────
        # Training applied per-column MinMax: X_scaled = (X - global_min) / scale_range
        # This MUST be applied at inference to ensure the same scaling as training.
        self.global_min = np.load(str(GLOBAL_MIN_PATH)).astype(np.float32)
        self.global_max = np.load(str(GLOBAL_MAX_PATH)).astype(np.float32)
        self.scale_range = self.global_max - self.global_min
        self.scale_range[self.scale_range == 0] = 1.0   # prevent div-by-zero
        logger.info(
            "Global scaling loaded: min range=[%.4f, %.4f], max range=[%.4f, %.4f]",
            float(self.global_min.min()), float(self.global_min.max()),
            float(self.global_max.min()), float(self.global_max.max()),
        )

        with open(CLINICAL_MAPPINGS_PATH, "r", encoding="utf-8") as f:
            self.clinical_mappings = json.load(f)

        # ── Load PyTorch encoder ─────────────────────────────────
        logger.info("Loading PyTorch encoder: %s", ENCODER_PATH.name)

        # Training saves with: torch.save(model.state_dict(), path)
        # This is a FLAT dict of tensors (not a dict-of-dicts with 'encoder_state_dict' key).
        raw_checkpoint = torch.load(
            ENCODER_PATH, map_location=self.device, weights_only=False
        )

        # Detect whether it is a flat state dict or a wrapped checkpoint dict.
        # A flat state dict has tensor values; a wrapped dict has dict/str values at top.
        is_flat_state_dict = isinstance(raw_checkpoint, dict) and all(
            isinstance(v, torch.Tensor) for v in raw_checkpoint.values()
        )

        if is_flat_state_dict:
            # Training saved torch.save(model.state_dict(), path) directly.
            # Infer input_dim from the first Linear layer weight shape.
            first_key = next(k for k in raw_checkpoint if "encoder.0.weight" in k or (k.endswith(".weight") and "encoder" in k))
            input_dim  = raw_checkpoint[first_key].shape[1]
            latent_dim = 150
            logger.info("Flat state dict detected. Inferred input_dim=%d, latent_dim=%d", input_dim, latent_dim)
            checkpoint_weights = raw_checkpoint
        else:
            input_dim  = int(raw_checkpoint.get("input_dim",  MAX_CPGS))
            latent_dim = int(raw_checkpoint.get("latent_dim", 150))
            if "encoder_state_dict" in raw_checkpoint:
                checkpoint_weights = raw_checkpoint["encoder_state_dict"]
            elif "model_state_dict" in raw_checkpoint:
                checkpoint_weights = raw_checkpoint["model_state_dict"]
            else:
                checkpoint_weights = raw_checkpoint
            logger.info("Wrapped checkpoint. input_dim=%d, latent_dim=%d", input_dim, latent_dim)

        self.encoder = Encoder(input_dim=input_dim, latent_dim=latent_dim)

        # Filter decoder keys, normalise encoder key prefix, convert fp16→float32
        adjusted_weights: dict = {}
        fp16_converted = 0
        for k, v in checkpoint_weights.items():
            if k.startswith("decoder."):
                continue   # skip decoder weights — we only need the encoder half
            if not k.startswith("encoder."):
                k = f"encoder.{k}"
            if isinstance(v, torch.Tensor) and v.dtype == torch.float16:
                v = v.float()
                fp16_converted += 1
            adjusted_weights[k] = v

        if fp16_converted:
            logger.info("Converted %d fp16 weight tensors to float32", fp16_converted)

        self.encoder.load_state_dict(adjusted_weights)
        self.encoder.eval()
        logger.info("PyTorch encoder ready (input_dim=%d, latent_dim=%d)", input_dim, latent_dim)

        # ── Load Keras models ────────────────────────────────────
        logger.info("Loading Keras models")
        custom_objects = {
            "tf": tf,
            "L2Normalize": L2Normalize,
        }

        # ── Contrastive encoder: rebuild + load weights ───────────
        # Cannot use load_model() because the saved model used a Lambda layer
        # (lambda x: tf.nn.l2_normalize(x, axis=1)) which is serialized via
        # Python's marshal module — version-specific and breaks cross-version.
        # Fix: rebuild the architecture with our L2Normalize custom layer
        # (identical behaviour), then load only the weights from the .keras zip.
        logger.info("Loading contrastive encoder weights (compat mode)")
        self.contrastive_model = self._build_and_load_contrastive_encoder(
            CONTRASTIVE_MODEL_PATH, input_dim=163, emb_dim=128
        )

        self.driftnet_model = keras.models.load_model(
            DRIFTNET_MODEL_PATH,
            compile=False,
            safe_mode=False,
            custom_objects=custom_objects,
        )
        self._bind_tf_to_lambda_layers(self.driftnet_model)

        logger.info("DriftNetInference initialization complete ✓")

    # ─────────────────────────────────────────────────────────────
    # Step 1 — Parse methylation .txt file
    # ─────────────────────────────────────────────────────────────
    def parse_methylation_txt(self, file_path: str | Path) -> tuple[np.ndarray, int]:
        """
        Read a tab-separated methylation file and align it to the saved
        training probe order (assets/probe_list.txt) by CpG probe ID.

        This is a critical fix for cross-platform consistency:
        ─────────────────────────────────────────────────────────
        Previously, probes were read by row position (first N rows),
        which caused probe-position misalignment when the uploaded file
        had a different probe count or ordering than training files.

        Now:
          1. Load the canonical probe list saved from the training data.
          2. Read the uploaded file indexed by probe ID.
          3. Reindex to the canonical order — probes present in the file
             get their true beta value; probes absent get NaN (→ 0.5 after cleaning).

        This ensures the encoder always sees the same probe at each
        input position, regardless of which file platform you upload.

        File format
        ──────────
        Tab-separated, no header.
        Column 0: CpG probe ID (e.g. cg00000029)
        Column 1: beta value in [0, 1] or NA

        Returns
        ──────
        array          : np.ndarray, shape (1, len(probe_list))
        raw_cpg_count  : int — probes in the uploaded file
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Methylation file not found: {file_path}")

        # ── Load canonical probe list ─────────────────────────────
        probe_list_path = ASSET_DIR / "probe_list.txt"
        if probe_list_path.exists():
            with open(probe_list_path, "r") as f:
                training_probes = [line.strip() for line in f if line.strip()]
            logger.info(
                "Probe list loaded: %d canonical probes from %s",
                len(training_probes), probe_list_path.name,
            )
        else:
            # Fallback: no probe list saved — use positional truncate/pad
            logger.warning(
                "probe_list.txt not found in assets/. Falling back to "
                "positional truncation (less accurate). Run extract_probe_list.py to fix."
            )
            training_probes = None

        # ── Parse uploaded file ───────────────────────────────────
        df = pd.read_csv(file_path, sep="\t", index_col=0, header=None, dtype=str)

        if df.shape[1] < 1:
            raise ValueError(
                "Uploaded methylation file does not contain a beta-value column. "
                "Expected: tab-separated, no header, col0=probe_id, col1=beta_value."
            )

        raw_series = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        raw_series.index = raw_series.index.astype(str).str.strip()
        raw_cpg_count = len(raw_series)
        nan_count = int(raw_series.isna().sum())

        logger.info(
            "Methylation parse: %d probes read, %d NaN values (%.1f%%)",
            raw_cpg_count,
            nan_count,
            100.0 * nan_count / max(raw_cpg_count, 1),
        )

        # ── Alignment by probe ID (preferred) ────────────────────
        if training_probes is not None:
            # Reindex by probe ID to canonical training order
            aligned = raw_series.reindex(training_probes)

            matched   = int(aligned.notna().sum() - nan_count if nan_count < len(aligned) else aligned.notna().sum())
            # More accurate: count probes in file that also appear in training list
            common_probes = len(set(raw_series.index) & set(training_probes))
            coverage_pct  = 100.0 * common_probes / len(training_probes)

            logger.info(
                "Probe alignment: %d/%d training probes covered (%.1f%%) from uploaded file",
                common_probes, len(training_probes), coverage_pct,
            )

            if coverage_pct < 50.0:
                logger.warning(
                    "Low probe coverage (%.1f%%). The uploaded file may be from a very "
                    "different array platform or preprocessed differently from training data.",
                    coverage_pct,
                )

            arr = aligned.values.astype(np.float32)
            # arr length == len(training_probes); may not equal MAX_CPGS
            # Pad or truncate to MAX_CPGS to match encoder input_dim
            n = len(arr)
            if n > MAX_CPGS:
                arr = arr[:MAX_CPGS]
                logger.info("Truncating aligned array from %d to %d", n, MAX_CPGS)
            elif n < MAX_CPGS:
                arr = np.pad(arr, (0, MAX_CPGS - n), constant_values=np.nan)
                logger.info("Padding aligned array from %d to %d", n, MAX_CPGS)

        else:
            # ── Fallback: positional truncate/pad ─────────────────
            arr = raw_series.values.astype(np.float32)
            if len(arr) > MAX_CPGS:
                logger.info("Truncating from %d to %d probes (positional)", len(arr), MAX_CPGS)
                arr = arr[:MAX_CPGS]
            elif len(arr) < MAX_CPGS:
                logger.info("Padding from %d to %d probes with NaN (positional)", len(arr), MAX_CPGS)
                arr = np.pad(arr, (0, MAX_CPGS - len(arr)), constant_values=np.nan)

        assert arr.shape == (MAX_CPGS,), f"Unexpected methylation shape: {arr.shape}"
        return arr.reshape(1, -1), raw_cpg_count


    # ─────────────────────────────────────────────────────────────
    # Step 2 — Clean methylation array
    # ─────────────────────────────────────────────────────────────
    def clean_methylation_array(self, x: np.ndarray) -> np.ndarray:
        """
        Apply the same cleaning as training-time preprocessing:
          • NaN → 0.5   (neutral beta value for missing probes)
          • +inf → 1.0 / -inf → 0.0
          • clip to [0, 1]

        Note: No MinMaxScaler was applied during training methylation
        preprocessing beyond this standard beta-value cleaning.
        The VAE / autoencoder accepts raw [0,1] beta values directly.
        """
        x = x.astype(np.float32)
        nan_count = int(np.isnan(x).sum())
        x = np.nan_to_num(x, nan=0.5, posinf=1.0, neginf=0.0)
        x = np.clip(x, 0.0, 1.0)
        logger.debug("Methylation clean: %d NaNs replaced with 0.5", nan_count)
        return x.astype(np.float32)

    # ─────────────────────────────────────────────────────────────
    # Step 3 — PyTorch encoder → 150 latent features
    # ─────────────────────────────────────────────────────────────
    def get_latent_features(self, methylation_array: np.ndarray) -> np.ndarray:
        """
        Apply global MinMax scaling (matching training) then run PyTorch encoder.
        Training applied: X_scaled = (X - global_min) / scale_range, clipped to [0,1].
        """
        assert methylation_array.shape == (1, MAX_CPGS), (
            f"Expected methylation shape (1, {MAX_CPGS}), got {methylation_array.shape}"
        )

        # Apply the SAME per-column MinMax scaling used during autoencoder training
        x_scaled = (methylation_array - self.global_min) / self.scale_range
        x_scaled = np.clip(x_scaled, 0.0, 1.0).astype(np.float32)
        logger.debug("Global scaling applied — scaled range: [%.4f, %.4f]",
                     float(x_scaled.min()), float(x_scaled.max()))

        x_tensor = torch.tensor(x_scaled, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            latent = self.encoder(x_tensor).cpu().numpy().astype(np.float32)

        if latent.shape != (1, 150):
            raise ValueError(f"Expected latent shape (1, 150), got {latent.shape}")
        return latent

    # ─────────────────────────────────────────────────────────────
    # Step 4 — Encode 13 clinical features
    # ─────────────────────────────────────────────────────────────
    def encode_clinical_input(self, clinical_input: dict) -> np.ndarray:
        """
        Encode the 13 clinical fields using saved fitted LabelEncoders.
        - diagnoses.age_at_diagnosis is treated as raw numeric (days).
        - All other fields must exactly match training-time category strings.
        - Unknown categories raise a ValueError with allowed values listed.
        """
        missing = [col for col in EXPECTED_CLINICAL_COLS if col not in clinical_input]
        if missing:
            raise ValueError(
                f"Missing clinical input fields: {missing}. "
                f"All 13 fields are required."
            )

        encoded_values = []

        for col in EXPECTED_CLINICAL_COLS:
            value = clinical_input[col]

            if col == "diagnoses.age_at_diagnosis":
                try:
                    encoded_values.append(float(value))
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"'{col}' must be numeric (age in days). Got: {value!r}"
                    ) from e
            else:
                if value is None:
                    raise ValueError(f"Clinical field '{col}' is None.")

                value_str = str(value).strip()

                if col not in self.clinical_label_encoders:
                    raise ValueError(f"No saved LabelEncoder found for column '{col}'.")

                le = self.clinical_label_encoders[col]

                if value_str not in le.classes_:
                    allowed = list(le.classes_)
                    raise ValueError(
                        f"Unknown category for '{col}': {value_str!r}. "
                        f"Allowed values: {allowed}"
                    )

                encoded_values.append(float(le.transform([value_str])[0]))

        x_clinical = np.array(encoded_values, dtype=np.float32).reshape(1, -1)

        if x_clinical.shape != (1, 13):
            raise ValueError(f"Expected clinical shape (1, 13), got {x_clinical.shape}")

        logger.debug("Clinical encoding → shape=%s values=%s", x_clinical.shape, x_clinical)
        return x_clinical

    # ─────────────────────────────────────────────────────────────
    # Step 5 — Contrastive embedding → 128 features
    # ─────────────────────────────────────────────────────────────
    def get_contrastive_embedding(
        self,
        latent_150: np.ndarray,
        clinical_encoded_13: np.ndarray,
    ) -> np.ndarray:
        """
        Combine latent_150 + clinical_encoded_13 → (1, 163)
        Apply contrastive_scaler → run contrastive_encoder → (1, 128)

        Input order must match training exactly:
          [latent_1 … latent_150 | clinical_1 … clinical_13]
        """
        assert latent_150.shape == (1, 150), f"Expected (1,150), got {latent_150.shape}"
        assert clinical_encoded_13.shape == (1, 13), (
            f"Expected (1,13), got {clinical_encoded_13.shape}"
        )

        combined = np.hstack([latent_150, clinical_encoded_13]).astype(np.float32)
        assert combined.shape == (1, 163), (
            f"Expected combined shape (1, 163), got {combined.shape}"
        )

        scaled    = self.contrastive_scaler.transform(combined).astype(np.float32)
        embedding = self.contrastive_model.predict(scaled, verbose=0).astype(np.float32)

        if embedding.shape != (1, 128):
            raise ValueError(f"Expected contrastive embedding (1, 128), got {embedding.shape}")

        return embedding

    # ─────────────────────────────────────────────────────────────
    # Step 6 — DriftNet final stage prediction
    # ─────────────────────────────────────────────────────────────
    def predict_stage(
        self,
        embedding_128: np.ndarray,
        clinical_encoded_13: np.ndarray,
    ) -> dict:
        """
        Run DriftNet dual-branch classifier:
          Branch 1: embedding_128 (contrastive methylation representation)
          Branch 2: clinical_scaled_13 (independently scaled clinical features)
        Returns predicted stage, confidence, confidence_level, probabilities, warning.
        """
        assert embedding_128.shape == (1, 128), (
            f"Expected (1,128), got {embedding_128.shape}"
        )
        assert clinical_encoded_13.shape == (1, 13), (
            f"Expected (1,13), got {clinical_encoded_13.shape}"
        )

        clinical_scaled = self.driftnet_clinical_scaler.transform(
            clinical_encoded_13
        ).astype(np.float32)

        probs     = self.driftnet_model.predict([embedding_128, clinical_scaled], verbose=0)[0]
        pred_idx  = int(np.argmax(probs))
        pred_label = str(self.stage_label_encoder.inverse_transform([pred_idx])[0])
        confidence = float(np.max(probs))

        probability_map = {
            str(self.stage_label_encoder.inverse_transform([i])[0]): float(probs[i])
            for i in range(len(probs))
        }

        confidence_level = self._confidence_level(confidence)

        warning = None
        if confidence < CONFIDENCE_WARNING_THRESHOLD:
            warning = (
                "Low-confidence prediction. "
                "The model is uncertain between stages. "
                "Expert clinical review is strongly recommended."
            )

        logger.info(
            "Prediction → stage=%s | confidence=%.4f (%s) | probs=%s",
            pred_label,
            confidence,
            confidence_level,
            {k: f"{v:.3f}" for k, v in probability_map.items()},
        )

        return {
            "predicted_index":   pred_idx,
            "predicted_stage":   pred_label,
            "confidence":        confidence,
            "confidence_level":  confidence_level,
            "probabilities":     probability_map,
            "warning":           warning,
        }

    # ─────────────────────────────────────────────────────────────
    # Full pipeline (raises on error)
    # ─────────────────────────────────────────────────────────────
    def run_full_inference(
        self,
        methylation_txt_path: str | Path,
        clinical_input: dict,
    ) -> dict:
        request_id = str(uuid.uuid4())
        logger.info("[%s] ── Starting full inference ──", request_id)

        # Step 1
        try:
            methylation_raw, cpg_count = self.parse_methylation_txt(methylation_txt_path)
            logger.info(
                "[%s] Step 1 OK — methylation shape=%s, raw_cpg_count=%d",
                request_id, methylation_raw.shape, cpg_count,
            )
        except Exception as e:
            logger.exception("[%s] Step 1 FAILED — parse_methylation_txt", request_id)
            raise RuntimeError(f"[{request_id}] parse_methylation_txt: {e}") from e

        # Step 2
        try:
            methylation_clean = self.clean_methylation_array(methylation_raw)
            logger.info("[%s] Step 2 OK — methylation cleaned", request_id)
        except Exception as e:
            logger.exception("[%s] Step 2 FAILED — clean_methylation_array", request_id)
            raise RuntimeError(f"[{request_id}] clean_methylation_array: {e}") from e

        # Step 3
        try:
            latent_150 = self.get_latent_features(methylation_clean)
            logger.info("[%s] Step 3 OK — latent shape=%s", request_id, latent_150.shape)
        except Exception as e:
            logger.exception("[%s] Step 3 FAILED — get_latent_features", request_id)
            raise RuntimeError(f"[{request_id}] get_latent_features: {e}") from e

        # Step 4
        try:
            clinical_encoded_13 = self.encode_clinical_input(clinical_input)
            logger.info(
                "[%s] Step 4 OK — clinical encoded shape=%s",
                request_id, clinical_encoded_13.shape,
            )
        except Exception as e:
            logger.exception("[%s] Step 4 FAILED — encode_clinical_input", request_id)
            raise RuntimeError(f"[{request_id}] encode_clinical_input: {e}") from e

        # Step 5
        try:
            embedding_128 = self.get_contrastive_embedding(latent_150, clinical_encoded_13)
            logger.info(
                "[%s] Step 5 OK — contrastive embedding shape=%s",
                request_id, embedding_128.shape,
            )
        except Exception as e:
            logger.exception("[%s] Step 5 FAILED — get_contrastive_embedding", request_id)
            raise RuntimeError(f"[{request_id}] get_contrastive_embedding: {e}") from e

        # Step 6
        try:
            prediction = self.predict_stage(embedding_128, clinical_encoded_13)
            logger.info(
                "[%s] Step 6 OK — stage=%s confidence=%.4f (%s)",
                request_id,
                prediction["predicted_stage"],
                prediction["confidence"],
                prediction["confidence_level"],
            )
        except Exception as e:
            logger.exception("[%s] Step 6 FAILED — predict_stage", request_id)
            raise RuntimeError(f"[{request_id}] predict_stage: {e}") from e

        logger.info("[%s] ── Inference complete ──", request_id)
        return {
            "request_id":       request_id,
            "cpg_count":        cpg_count,
            "latent_shape":     list(latent_150.shape),
            "embedding_shape":  list(embedding_128.shape),
            **prediction,
        }

    # ─────────────────────────────────────────────────────────────
    # Safe wrapper — returns structured error dict, never raises
    # ─────────────────────────────────────────────────────────────
    def run_full_inference_safe(
        self,
        methylation_txt_path: str | Path,
        clinical_input: dict,
    ) -> dict:
        """Deployment-safe wrapper. Returns success/error dict instead of raising."""
        try:
            result = self.run_full_inference(methylation_txt_path, clinical_input)
            return {"success": True, **result}
        except Exception as e:
            request_id = str(uuid.uuid4())
            tb = traceback.format_exc()
            logger.error("[%s] Safe inference failed: %s", request_id, e)
            logger.debug("[%s] Traceback:\n%s", request_id, tb)
            return {
                "success":       False,
                "request_id":    request_id,
                "error_type":    type(e).__name__,
                "error_message": str(e),
                "hint": (
                    "If the process exits with -1073741819, "
                    "re-export contrastive_encoder.keras from the original training runtime. "
                    "If you see 'Unknown category', check clinical field values against "
                    "assets/clinical_label_mappings.json."
                ),
            }


# =========================
# Optional local test
# =========================
if __name__ == "__main__":
    try:
        predictor = DriftNetInference()

        sample_txt = BASE_DIR / "samples" / "sample_patient.methylation_array.sesame.level3betas.txt"

        sample_clinical_input = {
            "demographic.gender":                    "male",
            "demographic.vital_status":              "Alive",
            "samples.sample_type":                   "Primary Tumor",
            "cases.disease_type":                    "Adenomas and Adenocarcinomas",
            "samples.tissue_type":                   "Tumor",
            "diagnoses.primary_diagnosis":           "Cholangiocarcinoma",
            "diagnoses.tissue_or_organ_of_origin":   "Intrahepatic bile duct",
            "diagnoses.morphology":                  "8160/3",
            "diagnoses.age_at_diagnosis":            25069,
            "diagnoses.prior_treatment":             "No",
            "diagnoses.prior_malignancy":            "no",
            "demographic.race":                      "white",
            "demographic.ethnicity":                 "not hispanic or latino",
        }

        result = predictor.run_full_inference_safe(sample_txt, sample_clinical_input)
        print(json.dumps(result, indent=2))

    except Exception:
        logger.exception("Fatal error while initializing inference entrypoint")
        raise