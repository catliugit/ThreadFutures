"""Train and evaluate offcut forecasters.

Target: offcut ratio = weighed offcut kg / input fabric kg.

Compared on a held-out 20% of runs:

1. **Industry rule of thumb**: a flat 15% of fabric becomes offcut.
2. **Marker only**: 1 - planned marker efficiency (what CAD reports today).
3. **ML, pre-marker**: gradient boosting on order data only. This is the model the
   website runs in the browser, usable before any marker exists.
4. **ML, post-marker**: adds planned marker efficiency, and corrects the marker's
   blind spots (ends, roll remnants, spreading, defects).

Each ML model is trained as three quantile regressors (P10 / P50 / P90), so it
gives a planning range rather than a single number.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from .pipeline import DATA, POST_MARKER, PRE_MARKER, ROOT, TARGET, encode

QUANTILES = {"p10": 0.10, "p50": 0.50, "p90": 0.90}
PARAMS = dict(n_estimators=250, max_depth=3, learning_rate=0.06, subsample=0.8,
              min_samples_leaf=20, random_state=11)


def fit_quantiles(X: pd.DataFrame, y: pd.Series) -> dict:
    return {k: GradientBoostingRegressor(loss="quantile", alpha=a, **PARAMS).fit(X, y)
            for k, a in QUANTILES.items()}


def metrics(y_true: np.ndarray, p50: np.ndarray, input_kg: np.ndarray,
            p10: np.ndarray = None, p90: np.ndarray = None) -> dict:
    err_pp = np.abs(y_true - p50) * 100
    kg_err = np.abs(y_true - p50) * input_kg
    kg_true = y_true * input_kg
    out = {
        "mae_pp": round(float(err_pp.mean()), 3),          # percentage points of fabric
        "mape_kg": round(float((kg_err / kg_true).mean() * 100), 2),
        "within_15pct_kg": round(float((kg_err / kg_true <= 0.15).mean() * 100), 1),
        "bias_pp": round(float(((p50 - y_true) * 100).mean()), 3),
    }
    if p10 is not None:
        out["p10_p90_coverage"] = round(float(((y_true >= p10) & (y_true <= p90)).mean() * 100), 1)
    return out


def main() -> dict:
    df = pd.read_csv(DATA / "features" / "runs.csv")
    tr, te = df[df.split == "train"], df[df.split == "test"]
    y_tr, y_te, kg_te = tr[TARGET], te[TARGET].to_numpy(), te["input_kg"].to_numpy()

    results = {
        "n_train": len(tr), "n_test": len(te),
        "rule_of_thumb_15pct": metrics(y_te, np.full(len(te), 0.15), kg_te),
        "marker_only": metrics(y_te, (1 - te["marker_efficiency"]).to_numpy(), kg_te),
    }
    models = {}
    for name, cols in (("ml_pre_marker", PRE_MARKER), ("ml_post_marker", POST_MARKER)):
        q = fit_quantiles(encode(tr, cols), y_tr)
        Xte = encode(te, cols)
        p = {k: m.predict(Xte) for k, m in q.items()}
        results[name] = metrics(y_te, p["p50"], kg_te, p["p10"], p["p90"])
        models[name] = (q, list(Xte.columns))

    # Per-garment error for the browser model
    q, _ = models["ml_pre_marker"]
    te = te.assign(pred=q["p50"].predict(encode(te, PRE_MARKER)))
    results["ml_pre_marker_by_garment_mae_pp"] = (
        (te[TARGET] - te.pred).abs().mul(100).groupby(te.garment).mean().round(2).to_dict())

    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(results, indent=2))
    from .export import export_quantile_model
    export_quantile_model(*models["ml_pre_marker"], out / "pre_marker_model.json")
    _plot(results, te)
    return results


def _plot(results: dict, te: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = ROOT / "docs" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    labels = ["Rule of thumb\n(15%)", "Marker only\n(CAD today)", "ML\npre-marker", "ML\npost-marker"]
    keys = ["rule_of_thumb_15pct", "marker_only", "ml_pre_marker", "ml_post_marker"]
    vals = [results[k]["mape_kg"] for k in keys]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bars = ax.bar(labels, vals, color=["#B9C7C1", "#91A99A", "#197F70", "#11594F"])
    ax.bar_label(bars, fmt="%.1f%%", padding=3)
    ax.set_ylabel("Mean absolute % error (offcut kg)")
    ax.set_title("Forecast error on held-out runs (lower is better)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(figs / "error_by_method.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(te[TARGET] * 100, te.pred * 100, s=6, alpha=0.4, color="#197F70")
    lo, hi = te[TARGET].min() * 100, te[TARGET].max() * 100
    ax.plot([lo, hi], [lo, hi], color="#16211F", lw=1)
    ax.set_xlabel("Actual offcut (% of fabric)")
    ax.set_ylabel("Predicted P50 (% of fabric)")
    ax.set_title("Pre-marker model: predicted vs actual")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(figs / "pred_vs_actual.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
