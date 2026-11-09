"""Model monitoring: is the stall-risk model still accurate, and has the data drifted?

Scores each later launch quarter the model never trained on and reports, per quarter:
  - accuracy: ROC AUC, PR AUC, predicted vs actual stall rate (calibration)
  - drift: Population Stability Index (PSI) and a Kolmogorov-Smirnov test per feature,
    comparing that quarter's inputs with the training data
Alerts fire on PSI > 0.25 (major shift), KS p < 0.01, or AUC below 0.70.
Writes models/monitoring.json and a static HTML report to site/reports/monitoring.html.

    python -m stock.monitor
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, roc_auc_score

from .features import FEATURES, ROOT, load

PSI_ALERT, KS_ALERT, AUC_ALERT = 0.25, 0.01, 0.70


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index using quantile bins of the training distribution."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def run() -> dict:
    bundle = joblib.load(ROOT / "models" / "stall_model.joblib")
    model = bundle["model"]
    df = load()
    tr, te = df[df.split == "train"], df[df.split == "test"].copy()
    te["p"] = model.predict_proba(te[FEATURES])[:, 1]
    te["quarter"] = te.first_sale_week.dt.to_period("Q").astype(str)
    out = {"thresholds": {"psi": PSI_ALERT, "ks_p": KS_ALERT, "auc": AUC_ALERT}, "periods": []}
    for q, g in te.groupby("quarter"):
        drift = {}
        for f in FEATURES:
            ks = stats.ks_2samp(tr[f], g[f])
            drift[f] = {"psi": round(psi(tr[f].to_numpy(), g[f].to_numpy()), 3), "ks_p": float(f"{ks.pvalue:.3g}")}
        auc = roc_auc_score(g.stalled, g.p) if g.stalled.nunique() > 1 else None
        alerts = [f"{f}: PSI {d['psi']}" for f, d in drift.items() if d["psi"] > PSI_ALERT]
        alerts += [f"{f}: KS p={d['ks_p']}" for f, d in drift.items() if d["ks_p"] < KS_ALERT and d["psi"] <= PSI_ALERT]
        if auc is not None and auc < AUC_ALERT:
            alerts.append(f"AUC {auc:.2f} below {AUC_ALERT}")
        out["periods"].append({
            "launch_quarter": q, "skus": int(len(g)),
            "roc_auc": None if auc is None else round(float(auc), 3),
            "pr_auc": None if auc is None else round(float(average_precision_score(g.stalled, g.p)), 3),
            "predicted_stall_rate": round(float(g.p.mean()), 3),
            "actual_stall_rate": round(float(g.stalled.mean()), 3),
            "drift": drift, "alerts": alerts,
        })
    offcut = json.loads((ROOT / "models" / "metrics.json").read_text())
    out["offcut_model"] = {
        "note": "Simulated cutting runs. Error by garment on the 1,600-run hold-out.",
        "mae_pp_by_garment": offcut["ml_pre_marker_by_garment_mae_pp"],
        "p10_p90_coverage": offcut["ml_pre_marker"]["p10_p90_coverage"],
        "coverage_target": 80.0,
    }
    (ROOT / "models" / "monitoring.json").write_text(json.dumps(out, indent=2))
    (ROOT / "site" / "reports" / "monitoring.html").write_text(render(out))
    return out


def render(m: dict) -> str:
    rows = []
    for p in m["periods"]:
        alert = "<br>".join(html.escape(a) for a in p["alerts"]) or "None"
        cls = "warn" if p["alerts"] else "ok"
        rows.append(f"<tr><td>{p['launch_quarter']}</td><td>{p['skus']}</td><td>{p['roc_auc']}</td><td>{p['pr_auc']}</td>"
                    f"<td>{p['predicted_stall_rate']:.1%}</td><td>{p['actual_stall_rate']:.1%}</td><td class='{cls}'>{alert}</td></tr>")
    psi_rows = []
    for f in FEATURES:
        cells = "".join(
            f"<td class='{'warn' if p['drift'][f]['psi'] > m['thresholds']['psi'] else ''}'>{p['drift'][f]['psi']}</td>"
            for p in m["periods"])
        psi_rows.append(f"<tr><td>{f}</td>{cells}</tr>")
    heads = "".join(f"<th>{p['launch_quarter']}</th>" for p in m["periods"])
    oc = m["offcut_model"]
    garm = "".join(f"<tr><td>{g}</td><td>{v} pp</td></tr>" for g, v in oc["mae_pp_by_garment"].items())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Model monitoring</title>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root{{--forest:#173D35;--lime:#D7EF91;--ivory:#F7F7F1;--char:#242A28;--sage:#B5D9C8;--line:#DCDCD2}}
body{{margin:0;background:var(--ivory);color:var(--char);font:15px/1.55 Manrope,system-ui,sans-serif;padding:40px 16px}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:1.9rem;margin:.2em 0}} h2{{font-size:1.05rem;margin-top:2.2em}}
.eyebrow{{font-size:.72rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--forest)}}
.label{{display:inline-block;background:var(--lime);color:var(--forest);font-weight:800;font-size:.72rem;padding:3px 8px;border-radius:4px}}
.scroll{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:.88rem;background:#fff}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}} th{{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em}}
td.warn{{background:#FBE9D0}} td.ok{{color:var(--forest)}} p.small{{font-size:.85rem;color:#5b625f}}
a{{color:var(--forest)}}
</style></head><body><main>
<div class="eyebrow">Thread Futures · model monitoring</div>
<h1>Stall-risk model, scored on later launches</h1>
<p><span class="label">Real retail data · UCI Online Retail II</span> Trained on SKUs launched before Oct 2010, then scored quarter by quarter on launches it never saw. Generated by <code>python -m stock.monitor</code>.</p>
<h2>Accuracy and calibration by launch quarter</h2>
<div class="scroll"><table><tr><th>Launch quarter</th><th>SKUs</th><th>ROC AUC</th><th>PR AUC</th><th>Predicted stall rate</th><th>Actual stall rate</th><th>Alerts</th></tr>{''.join(rows)}</table></div>
<h2>Data drift: PSI per feature versus training data</h2>
<p class="small">PSI above {m['thresholds']['psi']} is highlighted (major shift). KS-test p-values are in models/monitoring.json.</p>
<div class="scroll"><table><tr><th>Feature</th>{heads}</tr>{''.join(psi_rows)}</table></div>
<h2>Offcut forecast: error by garment</h2>
<p class="small">{html.escape(oc['note'])} P10–P90 range covers {oc['p10_p90_coverage']}% of outcomes (target {oc['coverage_target']}%).</p>
<div class="scroll"><table><tr><th>Garment</th><th>Mean abs. error</th></tr>{garm}</table></div>
<p class="small"><a href="../index.html">Back to Thread Futures</a></p>
</main></body></html>"""


if __name__ == "__main__":
    res = run()
    for p in res["periods"]:
        print(p["launch_quarter"], p["skus"], p["roc_auc"], p["predicted_stall_rate"], p["actual_stall_rate"], p["alerts"])
