"""Pattern-piece library and size grading.

Each garment is a list of pattern pieces at base size M. A piece is described by
its bounding box (width across the fabric, length along it, in cm), how much of
that box the real piece fills (``fill``), and how many are cut per garment.

``nest_k`` is a per-garment calibration factor. It combines how tightly the
garment's irregular shapes interlock and the gap between our simple skyline
packer and commercial nesting software. It is set so simulated marker
efficiencies land in published ranges (see README, "Calibration"). Values just
above 1 mean commercial nesting beats our rectangle packer for that garment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Piece:
    name: str
    w_cm: float   # across the fabric width
    h_cm: float   # along the fabric length (grain direction)
    fill: float   # true piece area / bounding-box area
    qty: int = 1

    @property
    def area_cm2(self) -> float:
        return self.w_cm * self.h_cm * self.fill


@dataclass(frozen=True)
class Garment:
    key: str
    label: str
    pieces: List[Piece]
    nest_k: float          # nesting compactness, 0..1
    knit: bool             # knits have no selvedge trim
    gsm_range: tuple       # typical fabric weight, g/m2
    width_range: tuple     # typical usable fabric width, m
    fibres: Dict[str, float]  # fibre -> probability


GARMENTS: Dict[str, Garment] = {
    "tee": Garment(
        "tee", "T-shirt (jersey knit)",
        [Piece("front", 52, 72, 0.86), Piece("back", 52, 72, 0.88),
         Piece("sleeve", 46, 24, 0.72, 2), Piece("neck_rib", 45, 4, 1.0)],
        nest_k=1.014, knit=True, gsm_range=(130, 220), width_range=(1.65, 1.95),
        fibres={"cotton": 0.55, "cotton_poly": 0.25, "polyester": 0.20},
    ),
    "hoodie": Garment(
        "hoodie", "Hoodie (fleece knit)",
        [Piece("front", 56, 70, 0.87), Piece("back", 56, 70, 0.88),
         Piece("sleeve", 50, 65, 0.72, 2), Piece("hood", 34, 38, 0.82, 2),
         Piece("pocket", 40, 22, 0.85), Piece("cuff", 20, 10, 1.0, 2),
         Piece("waistband", 90, 12, 1.0)],
        nest_k=1.01, knit=True, gsm_range=(250, 380), width_range=(1.65, 1.95),
        fibres={"cotton": 0.35, "cotton_poly": 0.50, "polyester": 0.15},
    ),
    "shirt": Garment(
        "shirt", "Shirt (woven)",
        [Piece("front", 34, 80, 0.85, 2), Piece("back", 60, 80, 0.87),
         Piece("sleeve", 60, 64, 0.68, 2), Piece("collar", 45, 10, 0.80, 2),
         Piece("cuff", 25, 8, 0.95, 4), Piece("yoke", 50, 14, 0.85, 2),
         Piece("pocket", 15, 17, 0.90)],
        nest_k=1.016, knit=False, gsm_range=(100, 150), width_range=(1.40, 1.65),
        fibres={"cotton": 0.60, "cotton_poly": 0.35, "polyester": 0.05},
    ),
    "jeans": Garment(
        "jeans", "Jeans (denim)",
        [Piece("front", 32, 108, 0.74, 2), Piece("back", 36, 110, 0.74, 2),
         Piece("waistband", 50, 8, 0.98, 2), Piece("back_yoke", 22, 12, 0.70, 2),
         Piece("pocket", 18, 22, 0.85, 4), Piece("coin_pocket", 10, 10, 0.90)],
        nest_k=0.955, knit=False, gsm_range=(270, 420), width_range=(1.50, 1.70),
        fibres={"cotton": 0.45, "cotton_elastane": 0.50, "cotton_poly": 0.05},
    ),
    "dress": Garment(
        "dress", "Dress (woven)",
        [Piece("front", 52, 105, 0.78), Piece("back", 52, 105, 0.80),
         Piece("sleeve", 40, 20, 0.70, 2), Piece("facing", 30, 10, 0.60, 2)],
        nest_k=0.945, knit=False, gsm_range=(90, 200), width_range=(1.40, 1.60),
        fibres={"polyester": 0.45, "cotton": 0.35, "cotton_poly": 0.20},
    ),
}

FIBRES = ["cotton", "polyester", "cotton_poly", "cotton_elastane"]

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
# Linear grading factor relative to M.
SIZE_SCALE = {"XS": 0.92, "S": 0.96, "M": 1.00, "L": 1.04, "XL": 1.08, "XXL": 1.12}

# Size-ratio templates: garments of each size cut in one marker.
SIZE_MIXES: Dict[str, Dict[str, int]] = {
    "narrow":   {"S": 1, "M": 2, "L": 2, "XL": 1},
    "standard": {"XS": 1, "S": 2, "M": 3, "L": 3, "XL": 2, "XXL": 1},
    "extended": {"XS": 1, "S": 1, "M": 2, "L": 2, "XL": 2, "XXL": 2},
}


def graded_pieces(garment: Garment, size: str, style_jitter: float = 1.0) -> List[Piece]:
    """Return the garment's pieces scaled for ``size`` (and a style variant)."""
    s = SIZE_SCALE[size] * style_jitter
    return [Piece(p.name, p.w_cm * s, p.h_cm * s, p.fill, p.qty) for p in garment.pieces]
