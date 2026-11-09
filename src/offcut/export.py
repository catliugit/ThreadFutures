"""Export scikit-learn gradient-boosted trees to compact JSON for the browser.

A GradientBoostingRegressor prediction is ``init + learning_rate * sum(tree(x))``.
Each tree is stored as parallel arrays (feature, threshold, left, right, value),
which ``web/forecast.js`` walks without any dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor


def _tree(t) -> dict:
    tr = t.tree_
    return {
        "f": tr.feature.tolist(),
        # Full precision: scikit-learn splits on float32(x) <= threshold, and thresholds sit
        # between neighbouring float32 values, so rounding them can flip a split.
        "t": [float(x) for x in tr.threshold],
        "l": tr.children_left.tolist(),
        "r": tr.children_right.tolist(),
        "v": [round(float(x), 6) for x in tr.value[:, 0, 0]],
    }


def _init_value(m: GradientBoostingRegressor, feature_names: List[str]) -> float:
    """Recover the constant initial prediction from the fitted model."""
    x = pd.DataFrame(np.zeros((1, len(feature_names))), columns=feature_names)
    trees = sum(est[0].predict(x.to_numpy())[0] for est in m.estimators_)
    return float(m.predict(x)[0] - m.learning_rate * trees)


def export_quantile_model(models: Dict[str, GradientBoostingRegressor],
                          feature_names: List[str], path: Path) -> None:
    payload = {"features": feature_names, "target": "offcut_ratio", "quantiles": {}}
    for q, m in models.items():
        payload["quantiles"][q] = {
            "init": round(_init_value(m, feature_names), 6),
            "lr": m.learning_rate,
            "trees": [_tree(est[0]) for est in m.estimators_],
        }
    path.write_text(json.dumps(payload, separators=(",", ":")))


def predict_json(payload: dict, x: List[float], q: str = "p50") -> float:
    """Reference implementation of the JS evaluator, used in tests."""
    m = payload["quantiles"][q]
    x = [float(np.float32(v)) for v in x]   # match scikit-learn's float32 comparison
    total = 0.0
    for t in m["trees"]:
        node = 0
        while t["l"][node] != -1:
            node = t["l"][node] if x[t["f"][node]] <= t["t"][node] else t["r"][node]
        total += t["v"][node]
    return m["init"] + m["lr"] * total
