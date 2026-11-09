"""End-to-end service: production order -> forecast -> graded lots -> recycler matches.

Uses the exported JSON model (no scikit-learn needed at serving time), so the
same model runs here, in the agent's tools, and in the browser.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from .export import predict_json
from .garments import GARMENTS
from .grading import build_lots
from .matching import load_recyclers, match_lot
from .pipeline import CATEGORIES, PRE_MARKER

MODEL = Path(__file__).resolve().parents[2] / "models" / "pre_marker_model.json"


@lru_cache(maxsize=1)
def _model() -> dict:
    return json.loads(MODEL.read_text())


def _encode(order: Dict) -> List[float]:
    names = _model()["features"]
    row = {}
    for c in PRE_MARKER:
        if c in CATEGORIES:
            for v in CATEGORIES[c]:
                row[f"{c}={v}"] = 1.0 if order[c] == v else 0.0
        else:
            row[c] = float(order[c])
    return [row[n] for n in names]


def validate_order(order: Dict) -> None:
    for c in PRE_MARKER:
        if c not in order:
            raise ValueError(f"order is missing '{c}'")
    for c, allowed in CATEGORIES.items():
        if order[c] not in allowed:
            raise ValueError(f"{c} must be one of {allowed}, got {order[c]!r}")
    if not 1.2 <= float(order["fabric_width_m"]) <= 2.2:
        raise ValueError("fabric_width_m must be between 1.2 and 2.2")
    if not 60 <= float(order["gsm"]) <= 500:
        raise ValueError("gsm must be between 60 and 500")
    if not 500 <= float(order["fabric_metres"]) <= 60000:
        raise ValueError("fabric_metres must be between 500 and 60,000")


def forecast(order: Dict) -> Dict:
    """Forecast offcut kg (P10/P50/P90) for an order before any marker exists."""
    validate_order(order)
    x = _encode(order)
    ratio = {q: predict_json(_model(), x, q) for q in ("p10", "p50", "p90")}
    lo, mid, hi = sorted(ratio.values())   # guard against quantile crossing
    input_kg = float(order["fabric_metres"]) * float(order["fabric_width_m"]) * float(order["gsm"]) / 1000
    return {
        "input_kg": round(input_kg, 1),
        "offcut_ratio": {"p10": round(lo, 4), "p50": round(mid, 4), "p90": round(hi, 4)},
        "offcut_kg": {"p10": round(lo * input_kg, 1), "p50": round(mid * input_kg, 1),
                      "p90": round(hi * input_kg, 1)},
        "rule_of_thumb_kg": round(0.15 * input_kg, 1),
    }


def plan(order: Dict) -> Dict:
    """Forecast, grade and match in one call."""
    fc = forecast(order)
    colour = order.get("colour", "mixed")
    region = order.get("region", "South Asia")
    lots = build_lots(order.get("run_id", "RUN"), order["fibre"], colour,
                      GARMENTS[order["garment"]].knit, fc["offcut_kg"])
    recyclers = load_recyclers()
    return {
        "forecast": fc,
        "lots": [dict(l.as_dict(), matches=match_lot(l, region, recyclers)[:3]) for l in lots],
    }


if __name__ == "__main__":
    demo = {"run_id": "DEMO", "garment": "tee", "fibre": "cotton", "size_mix": "standard",
            "fabric_width_m": 1.8, "gsm": 180, "fabric_metres": 18000,
            "colour": "white", "region": "South Asia"}
    print(json.dumps(plan(demo), indent=2))
