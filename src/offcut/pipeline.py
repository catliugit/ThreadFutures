"""Data pipeline: raw runs -> validated staging -> model features.

Layers, as in a lakehouse medallion layout:

* ``data/raw/runs.csv``        bronze: simulated cutting-room records, as produced
* ``data/staged/runs.csv``     silver: schema-checked, typed, with quality report
* ``data/features/*.csv``      gold: model-ready features and target

Each stage is idempotent and deterministic for a given seed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .garments import FIBRES, GARMENTS, SIZE_MIXES
from .simulate import simulate

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Data contract for the staged layer: column -> (dtype, min, max). None = unchecked.
CONTRACT: Dict[str, Tuple[str, float, float]] = {
    "fabric_width_m": ("float", 1.2, 2.2),
    "gsm": ("float", 60, 500),
    "fabric_metres": ("float", 500, 60_000),
    "marker_efficiency": ("float", 0.6, 0.95),
    "input_kg": ("float", 1, None),
    "offcut_kg_weighed": ("float", 0, None),
    "offcut_ratio": ("float", 0.05, 0.6),
}
CATEGORIES = {"garment": list(GARMENTS), "fibre": FIBRES, "size_mix": list(SIZE_MIXES)}

# Features available BEFORE a marker exists (order-level). Used by the browser model.
PRE_MARKER = ["garment", "fibre", "size_mix", "fabric_width_m", "gsm", "fabric_metres"]
# Adds the planned marker efficiency, available once the marker is made.
POST_MARKER = PRE_MARKER + ["marker_efficiency"]
TARGET = "offcut_ratio"


def extract(n: int = 8000, seed: int = 11) -> Path:
    out = DATA / "raw" / "runs.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(simulate(n, seed)).to_csv(out, index=False)
    return out


def validate(df: pd.DataFrame) -> List[str]:
    """Return a list of contract violations (empty = pass)."""
    problems = []
    for col, (_, lo, hi) in CONTRACT.items():
        if col not in df:
            problems.append(f"missing column {col}")
            continue
        if df[col].isna().any():
            problems.append(f"{col}: {int(df[col].isna().sum())} nulls")
        if lo is not None and (df[col] < lo).any():
            problems.append(f"{col}: {int((df[col] < lo).sum())} rows below {lo}")
        if hi is not None and (df[col] > hi).any():
            problems.append(f"{col}: {int((df[col] > hi).sum())} rows above {hi}")
    for col, allowed in CATEGORIES.items():
        bad = ~df[col].isin(allowed)
        if bad.any():
            problems.append(f"{col}: {int(bad.sum())} unknown values")
    if df["run_id"].duplicated().any():
        problems.append("duplicate run_id")
    # Mass balance: offcut can't exceed input.
    if (df["offcut_kg_true"] > df["input_kg"]).any():
        problems.append("mass balance violated")
    return problems


def stage() -> Path:
    df = pd.read_csv(DATA / "raw" / "runs.csv")
    problems = validate(df)
    report = {
        "rows": len(df),
        "violations": problems,
        "offcut_ratio": df[TARGET].describe().round(4).to_dict(),
        "by_garment": df.groupby("garment")[TARGET].mean().round(4).to_dict(),
    }
    out = DATA / "staged" / "runs.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    (DATA / "staged" / "quality_report.json").write_text(json.dumps(report, indent=2))
    if problems:
        raise ValueError(f"data contract failed: {problems}")
    df.to_csv(out, index=False)
    return out


def encode(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """One-hot encode categoricals with a fixed vocabulary, so the browser can match it."""
    X = pd.DataFrame(index=df.index)
    for c in cols:
        if c in CATEGORIES:
            for v in CATEGORIES[c]:
                X[f"{c}={v}"] = (df[c] == v).astype(float)
        else:
            X[c] = df[c].astype(float)
    return X


def features() -> Path:
    df = pd.read_csv(DATA / "staged" / "runs.csv")
    out = DATA / "features"
    out.mkdir(parents=True, exist_ok=True)
    # Deterministic split by run_id hash: 80% train, 20% test.
    is_test = df["run_id"].apply(lambda s: int(s.split("-")[1]) % 5 == 0)
    df.assign(split=is_test.map({True: "test", False: "train"})).to_csv(out / "runs.csv", index=False)
    return out / "runs.csv"


def run_all(n: int = 8000, seed: int = 11) -> None:
    extract(n, seed)
    stage()
    features()


if __name__ == "__main__":
    run_all()
    print((DATA / "staged" / "quality_report.json").read_text())
