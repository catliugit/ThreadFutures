"""Simulate production runs from order to weighed offcuts.

The marker gives the *planned* waste. Real cutting rooms lose more fabric than
the marker shows, and that gap is what a forecasting model has to learn:

* **Selvedge trim**: woven fabrics lose 1-2 cm at each edge; usable width < roll width.
* **Ply-end allowance**: every ply is laid a few cm longer than the marker at each end.
* **Roll ends**: a roll rarely divides into whole plies. Part of each remnant is
  spliced or recut for small parts; the rest is waste. Knit rolls are sold by
  weight (~20-30 kg), so heavier or wider knits mean shorter rolls; woven rolls
  run roughly 60-120 m.
* **Spreading loss**: splices, tension and slippage, higher for slippery polyester.
* **Defects**: flawed areas cut out and re-cut.
* **Recovery**: some sweepings and lint are never weighed as offcut.

Everything is seeded and reproducible. All quantities are synthetic.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Dict, List

from .garments import FIBRES, GARMENTS, SIZE_MIXES
from .nesting import build_marker

SPREAD_LOSS = {  # (low, high) fraction of laid length
    "cotton": (0.004, 0.015), "cotton_poly": (0.006, 0.018),
    "polyester": (0.010, 0.028), "cotton_elastane": (0.010, 0.025),
}


@dataclass
class Run:
    run_id: str
    garment: str
    fibre: str
    size_mix: str
    fabric_width_m: float
    gsm: float
    fabric_metres: float
    # planning-side (known before cutting, from the marker)
    marker_length_m: float
    marker_efficiency: float
    garments_per_marker: int
    # hidden process parameters (not features)
    selvedge_cm: float
    end_allowance_cm: float
    roll_m: float
    remnant_reuse: float
    spread_loss: float
    defect_rate: float
    recovery: float
    # outcomes
    plies: int
    garments_cut: int
    input_kg: float
    cut_panels_kg: float
    offcut_kg_true: float
    offcut_kg_weighed: float
    edge_strip_kg: float
    roll_end_kg: float
    marker_waste_kg: float

    @property
    def offcut_ratio(self) -> float:
        return self.offcut_kg_weighed / self.input_kg


def _pick(rng: random.Random, weights: Dict[str, float]) -> str:
    r, acc = rng.random() * sum(weights.values()), 0.0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return k


def simulate_run(rng: random.Random, run_id: str, garment_key: str = None) -> Run:
    g = GARMENTS[garment_key or rng.choice(list(GARMENTS))]
    fibre = _pick(rng, g.fibres)
    size_mix = rng.choice(list(SIZE_MIXES))
    width = round(rng.uniform(*g.width_range), 2)
    gsm = round(rng.uniform(*g.gsm_range))
    metres = round(rng.uniform(2_000, 40_000), -1)
    style = rng.uniform(0.96, 1.04)

    selvedge = 0.0 if g.knit else rng.uniform(1.0, 2.0)
    usable_w = width - 2 * selvedge / 100
    marker = build_marker(g, usable_w, SIZE_MIXES[size_mix], style, seed=rng.randrange(1 << 30))
    m_len = marker.length_cm / 100

    end_allow = rng.uniform(2.0, 3.0)                 # cm at each ply end (4-6 cm per ply)
    spread = rng.uniform(*SPREAD_LOSS[fibre])
    defect = rng.uniform(0.002, 0.015)
    recovery = rng.uniform(0.975, 0.995)
    remnant_reuse = rng.uniform(0.6, 0.9)

    ply_len = (m_len + 2 * end_allow / 100) * (1 + spread)
    roll_m = rng.uniform(20, 30) * 1000 / (gsm * width) if g.knit else rng.uniform(60, 120)
    plies_per_roll = int(roll_m // ply_len)
    if plies_per_roll < 1:
        plies_per_roll, ply_len = 1, roll_m
    n_rolls = metres / roll_m
    plies = int(n_rolls * plies_per_roll)
    good_plies = int(plies * (1 - defect))
    remnant_m = n_rolls * (roll_m - plies_per_roll * ply_len)
    # Reused remnant fabric yields extra panels (small parts), recovering part of the loss.
    reused_area_m2 = remnant_m * usable_w * remnant_reuse * marker.efficiency

    kg_per_m = gsm * width / 1000
    input_kg = metres * kg_per_m
    panels_kg = (good_plies * marker.true_area_cm2 / 1e4 + reused_area_m2) * gsm / 1000
    offcut_true = input_kg - panels_kg

    # Composition (approximate attribution for grading)
    edge_kg = plies * m_len * (2 * selvedge / 100) * gsm / 1000
    roll_end_kg = remnant_m * (1 - remnant_reuse * marker.efficiency) * kg_per_m
    marker_waste_kg = good_plies * (usable_w * m_len - marker.true_area_cm2 / 1e4) * gsm / 1000

    weighed = offcut_true * recovery * (1 + rng.gauss(0, 0.01))

    return Run(
        run_id, g.key, fibre, size_mix, width, gsm, metres,
        round(m_len, 3), round(marker.efficiency, 4), marker.garments_per_marker,
        round(selvedge, 2), round(end_allow, 2), round(roll_m, 1), round(remnant_reuse, 3), round(spread, 4),
        round(defect, 4), round(recovery, 4),
        plies, good_plies * marker.garments_per_marker,
        round(input_kg, 2), round(panels_kg, 2), round(offcut_true, 2), round(weighed, 2),
        round(edge_kg, 2), round(roll_end_kg, 2), round(marker_waste_kg, 2),
    )


def simulate(n: int, seed: int = 11) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        r = simulate_run(rng, f"SF-{i:06d}")
        d = asdict(r)
        d["offcut_ratio"] = round(r.offcut_ratio, 5)
        rows.append(d)
    return rows


assert set(SPREAD_LOSS) == set(FIBRES)
