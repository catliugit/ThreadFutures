"""Export real model output for the website (site/data/stock.js).

Takes later launches the model never trained on and shows, for a few real lines, the
stall risk it predicted after 12 weeks next to what actually happened in weeks 12-25.

    python -m stock.export_site
"""
from __future__ import annotations

import json

import duckdb
import joblib

from .features import FEATURES, ROOT, WAREHOUSE, load


def main() -> None:
    b = joblib.load(ROOT / "models" / "stall_model.joblib")
    df = load()
    te = df[df.split == "test"].copy()
    te["p"] = b["model"].predict_proba(te[FEATURES])[:, 1]
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    names = con.execute("select stock_code, description from dim_sku").df().set_index("stock_code").description
    health = con.execute("select abc_class || xyz_class as abcxyz, stock_code from mart_sku_health").df().set_index("stock_code").abcxyz
    # Readable examples: lines with steady early sales, excluding one-off bulk orders.
    te = te[(te.early_units_per_week >= 5) & (te.early_units_per_week < 1000)]
    pick = (te.nlargest(5, "p").to_dict("records") + te.nsmallest(3, "p").to_dict("records"))
    rows = [{
        "sku": r["stock_code"], "name": str(names.get(r["stock_code"], "")).title(),
        "launched": r["first_sale_week"].strftime("%b %Y"),
        "early_units_wk": round(r["early_units_per_week"], 1),
        "trend": round(r["early_trend"], 2),
        "risk": round(float(r["p"]), 2),
        "late_units_wk": round(r["late_units_per_week"], 1),
        "stalled": bool(r["stalled"]), "abcxyz": health.get(r["stock_code"], ""),
        "x": [round(float(r[f]), 4) for f in FEATURES],
    } for r in pick]
    metrics = json.loads((ROOT / "models" / "stall_metrics.json").read_text())
    payload = {"rows": rows, "test_skus": metrics["test_skus"], "auc": metrics["model"]["roc_auc"],
               "rule_auc": metrics["rule_trend_halved"]["roc_auc"]}
    (ROOT / "site" / "data" / "stock.js").write_text("window.TF_STOCK=" + json.dumps(payload) + ";\n")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
