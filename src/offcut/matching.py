"""Match graded lots to recycler acceptance specs.

Hard constraints filter (grade accepted, form accepted, region served); a score
ranks what's left (lot size vs. minimum, process fit, lead time). Recycler
profiles in ``data/recyclers_sample.json`` are fictional and illustrative.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .grading import Lot

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "recyclers_sample.json"


def load_recyclers(path: Path = SAMPLE) -> List[dict]:
    return json.loads(path.read_text())["recyclers"]


def match_lot(lot: Lot, region: str, recyclers: List[dict]) -> List[Dict]:
    matches = []
    for r in recyclers:
        if lot.grade not in r["accepts_grades"] or lot.form not in r["accepts_forms"]:
            continue
        if region not in r["regions"]:
            continue
        # Score: can the forecast range meet the minimum lot? Prefer P10 clearing it.
        if lot.kg_p10 >= r["min_lot_kg"]:
            size_score, size_note = 1.0, "P10 clears minimum lot"
        elif lot.kg_p50 >= r["min_lot_kg"]:
            size_score, size_note = 0.6, "P50 clears minimum; consolidate to be safe"
        elif lot.kg_p90 >= r["min_lot_kg"]:
            size_score, size_note = 0.3, "Only P90 clears minimum; consolidate with other runs"
        else:
            size_score, size_note = 0.0, "Below minimum; consolidate across runs"
        score = round(0.6 * size_score + 0.25 * r["process_fit"].get(lot.fibre, 0.5)
                      + 0.15 * (1 - min(r["lead_time_days"], 60) / 60), 3)
        matches.append({"recycler": r["name"], "process": r["process"], "score": score,
                        "min_lot_kg": r["min_lot_kg"], "why": size_note})
    return sorted(matches, key=lambda m: -m["score"])
