"""
DriftNet preprocessing utilities.

Methylation array parsing and cleaning helpers, extracted here so they
can be imported by both inference.py and any future preprocessing scripts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("driftnet.preprocess")

MAX_CPGS = 550_000
EXPECTED_CPG_MIN = 400_000
EXPECTED_CPG_MAX = 900_000


def parse_methylation_txt(file_path: str | Path) -> Tuple[np.ndarray, int]:
    """
    Parse a TCGA sesame level3 beta-value text file into a fixed-length vector.

    File format
    -----------
    - Tab-separated, no header
    - Column 0: CpG probe ID (e.g. cg00000029)
    - Column 1: beta value in [0, 1] or NA

    Returns
    -------
    array : np.ndarray, shape (1, MAX_CPGS=550000)
        Raw float32 array with NaN where probes are missing or NA.
    raw_cpg_count : int
        Number of CpG probe rows in the file before truncation/padding.

    Notes
    -----
    CpG probe ordering assumption
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Training was performed on TCGA sesame level3 betas files from the EPIC
    array platform (~866 K probes per file, truncated to 550 000).
    Files from the same platform have probes in the same row order, so
    feature positions align correctly with those seen during training.

    Uploading a file from a DIFFERENT platform (e.g. Illumina 450 K, ~485 K
    probes) will result in feature–position misalignment and unreliable
    predictions.  A robust fix requires saving the training probe list and
    aligning both training and inference files to the same canonical order.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Methylation file not found: {file_path}")

    df = pd.read_csv(file_path, sep="\t", index_col=0, header=None, dtype=str)

    if df.shape[1] < 1:
        raise ValueError(
            "Methylation file must have at least two columns: "
            "col0 = CpG probe ID, col1 = beta value. "
            "File appears to have only one column or wrong separator."
        )

    raw_series = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    raw_cpg_count = len(raw_series)
    nan_count = int(raw_series.isna().sum())

    logger.info(
        "Methylation parse: %d probes, %d NaN (%.1f%%)",
        raw_cpg_count,
        nan_count,
        100.0 * nan_count / max(raw_cpg_count, 1),
    )

    if not (EXPECTED_CPG_MIN <= raw_cpg_count <= EXPECTED_CPG_MAX):
        logger.warning(
            "Probe count %d outside expected range [%d, %d]. "
            "This may indicate a different array platform from training data. "
            "Predictions may be unreliable.",
            raw_cpg_count, EXPECTED_CPG_MIN, EXPECTED_CPG_MAX,
        )

    arr = raw_series.values.astype(np.float32)

    # Truncate or pad to MAX_CPGS (matches training chunk-builder behavior)
    if len(arr) > MAX_CPGS:
        arr = arr[:MAX_CPGS]
    elif len(arr) < MAX_CPGS:
        arr = np.pad(arr, (0, MAX_CPGS - len(arr)), constant_values=np.nan)

    return arr.reshape(1, -1), raw_cpg_count


def clean_methylation_array(x: np.ndarray) -> np.ndarray:
    """
    Apply training-matching methylation array cleaning.

    Transformations (in order)
    --------------------------
    1. Cast to float32
    2. NaN → 0.5   (neutral beta value; matches training NaN fill strategy)
    3. +inf → 1.0  / -inf → 0.0
    4. Clip to [0, 1]

    Note: No MinMaxScaler was applied in training beyond this standard
    beta-value cleaning.  The VAE/autoencoder encoder accepts raw [0,1]
    beta values directly.
    """
    x = x.astype(np.float32)
    x = np.nan_to_num(x, nan=0.5, posinf=1.0, neginf=0.0)
    x = np.clip(x, 0.0, 1.0)
    return x.astype(np.float32)
