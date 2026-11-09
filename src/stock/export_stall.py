"""Export the stall-risk classifier so it runs in the browser (site/data/stall_model.js).

Gradient boosting for binary classification: raw score = init + learning_rate * sum(tree
leaf values), probability = sigmoid(raw). Thresholds are kept at full precision and the
browser compares float32 inputs, exactly like scikit-learn.

    python -m stock.export_stall
"""
from __future__ import annotations

import json
import math

import joblib
import numpy as np
import pandas as pd

from .features import FEATURES, ROOT


def export() -> dict:
    b = joblib.load(ROOT / "models" / "stall_model.joblib")
    m = b["model"]
    zero = pd.DataFrame(np.zeros((1, len(FEATURES))), columns=FEATURES)
    trees_sum = sum(est[0].predict(zero.to_numpy())[0] for est in m.estimators_)
    init = float(m.decision_function(zero)[0] - m.learning_rate * trees_sum)
    trees = []
    for est in m.estimators_:
        t = est[0].tree_
        trees.append({"f": t.feature.tolist(), "t": [float(x) for x in t.threshold],
                      "l": t.children_left.tolist(), "r": t.children_right.tolist(),
                      "v": [round(float(x), 7) for x in t.value[:, 0, 0]]})
    return {"features": FEATURES, "init": init, "lr": m.learning_rate, "trees": trees}


def predict(payload: dict, x: list[float]) -> float:
    """Reference implementation of the browser evaluator (used in tests)."""
    x = [float(np.float32(v)) for v in x]
    s = 0.0
    for t in payload["trees"]:
        n = 0
        while t["l"][n] != -1:
            n = t["l"][n] if x[t["f"][n]] <= t["t"][n] else t["r"][n]
        s += t["v"][n]
    return 1 / (1 + math.exp(-(payload["init"] + payload["lr"] * s)))


def main() -> None:
    payload = export()
    (ROOT / "models" / "stall_model.json").write_text(json.dumps(payload, separators=(",", ":")))
    (ROOT / "site" / "data" / "stall_model.js").write_text("window.STALL_MODEL=" + json.dumps(payload, separators=(",", ":")) + ";\n")
    print("exported", len(payload["trees"]), "trees")


if __name__ == "__main__":
    main()
