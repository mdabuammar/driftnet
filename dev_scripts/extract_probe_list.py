"""
extract_probe_list.py
=====================
Run this ONCE to extract the canonical probe order from the sample
methylation file and save it as assets/probe_list.txt.

This probe order must match the order used during model training.
The training pipeline read TCGA sesame level3 betas files from the
EPIC array in row order and truncated to 550,000 probes.

Usage:
    python extract_probe_list.py

Output:
    assets/probe_list.txt   (550,000 lines, one probe ID per line)
"""
from pathlib import Path
import pandas as pd

BASE_DIR   = Path(__file__).resolve().parent
ASSET_DIR  = BASE_DIR / "assets"
SAMPLE_TXT = BASE_DIR / "samples" / "sample_patient.methylation_array.sesame.level3betas.txt"
OUT_PATH   = ASSET_DIR / "probe_list.txt"
MAX_CPGS   = 550_000

print(f"Reading sample file: {SAMPLE_TXT.name}")
df = pd.read_csv(SAMPLE_TXT, sep="\t", index_col=0, header=None, dtype=str)
probe_ids = df.index.tolist()
print(f"Total probes in file: {len(probe_ids)}")

# Truncate or take all (matches training behavior)
probe_ids = probe_ids[:MAX_CPGS]
print(f"Saving {len(probe_ids)} probe IDs to {OUT_PATH}")

with open(OUT_PATH, "w") as f:
    f.write("\n".join(probe_ids))

print("Done. probe_list.txt saved.")
print()
print("IMPORTANT: This probe list was extracted from the SAMPLE file.")
print("If your training used EPIC array files (~866K probes) with a")
print("different probe ordering, you must re-extract from a training")
print("EPIC array file instead. Replace the sample file in samples/")
print("with one of your EPIC training files and re-run this script.")
