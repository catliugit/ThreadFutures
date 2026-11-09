"""Train and evaluate the stall-risk model, tracking the run in MLflow.

    python -m stock.train_stall

Compares gradient boosting against the rule a merchandiser might use ("sales in weeks
8-11 have halved versus weeks 0-3"), on later launches the model never saw.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import mlflow
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .features import FEATURES, ROOT, load

MODELS = ROOT / "models"
TRACKING = f"sqlite:///{(ROOT / 'data' / 'mlflow.db').as_posix()}"
PARAMS = dict(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, random_state=7)


def precision_at(y, score, frac=0.2):
    k = max(1, int(len(y) * frac))
    top = np.argsort(-score)[:k]
    return float(np.mean(np.asarray(y)[top]))


def evaluate(y, score) -> dict:
    return {
        "roc_auc": round(float(roc_auc_score(y, score)), 4),
        "pr_auc": round(float(average_precision_score(y, score)), 4),
        "precision_top20pct": round(precision_at(y, score), 4),
    }


def main() -> dict:
    df = load()
    tr, te = df[df.split == "train"], df[df.split == "test"]
    mlflow.set_tracking_uri(TRACKING)
    mlflow.set_experiment("stall-risk")
    with mlflow.start_run(run_name="gbm-early-12wk") as run:
        model = GradientBoostingClassifier(**PARAMS).fit(tr[FEATURES], tr.stalled)
        p = model.predict_proba(te[FEATURES])[:, 1]
        rule = (te.early_trend < 0.5).astype(float).to_numpy()
        res = {
            "train_skus": int(len(tr)), "test_skus": int(len(te)),
            "test_stall_rate": round(float(te.stalled.mean()), 4),
            "model": {**evaluate(te.stalled, p), "brier": round(float(brier_score_loss(te.stalled, p)), 4)},
            # Rule: flag lines whose sales halved; within each group, a bigger fall ranks as riskier.
            "rule_trend_halved": evaluate(te.stalled, rule + 1e-9 * (-te.early_trend).rank().to_numpy()),
            "feature_importance": dict(sorted(
                ((f, round(float(v), 4)) for f, v in zip(FEATURES, model.feature_importances_)),
                key=lambda kv: -kv[1])),
        }
        mlflow.log_params(PARAMS | {"features": len(FEATURES), "train_before": "2010-10-01"})
        mlflow.log_metrics({f"test_{k}": v for k, v in res["model"].items()})
        mlflow.log_metrics({f"rule_{k}": v for k, v in res["rule_trend_halved"].items()})
        mlflow.sklearn.log_model(model, name="model", registered_model_name="stall-risk",
                                 input_example=te[FEATURES].head(3),
                                 # We trained this model ourselves in this run, so its tree nodes are trusted.
                                 skops_trusted_types=["sklearn.tree._tree.Tree"])
        res["mlflow_run_id"] = run.info.run_id
    MODELS.mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES}, MODELS / "stall_model.joblib")
    (MODELS / "stall_metrics.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    main()
