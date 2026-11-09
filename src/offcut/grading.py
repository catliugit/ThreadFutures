"""Turn a forecast into graded lots that recyclers can contract against.

Grade code = fibre class + colour class, e.g. ``C1-W`` (100% cotton, white).
Lots are also split by physical form, because form drives recyclability:

* ``strips``  selvedge and edge trim: long, uniform, easiest to process
* ``remnant`` roll-end pieces: large, often reusable before recycling
* ``cutting`` inter-piece marker waste: small, irregular, the bulk of volume

This is a v0 standard written for illustration; a real one would be
co-defined with recyclers against their acceptance specs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

FIBRE_CLASS = {
    "cotton": ("C", "100% cotton"),
    "polyester": ("P", "100% polyester"),
    "cotton_poly": ("B", "Cotton/polyester blend"),
    "cotton_elastane": ("E", "Cotton with elastane"),
}
COLOUR_CLASS = {"white": "W", "light": "L", "dark": "D", "mixed": "M"}

# Typical share of offcut mass by form (from the simulator's attribution).
FORM_SHARE = {"knit": {"strips": 0.0, "remnant": 0.20, "cutting": 0.80},
              "woven": {"strips": 0.07, "remnant": 0.18, "cutting": 0.75}}


@dataclass
class Lot:
    lot_id: str
    grade: str
    fibre: str
    colour: str
    form: str
    kg_p50: float
    kg_p10: float
    kg_p90: float
    notes: str

    def as_dict(self) -> dict:
        return asdict(self)


def grade_code(fibre: str, colour: str) -> str:
    return f"{FIBRE_CLASS[fibre][0]}1-{COLOUR_CLASS[colour]}"


def build_lots(run_id: str, fibre: str, colour: str, knit: bool,
               kg: Dict[str, float]) -> List[Lot]:
    """Split a forecast (``kg`` with p10/p50/p90) into lots by form."""
    shares = FORM_SHARE["knit" if knit else "woven"]
    code = grade_code(fibre, colour)
    lots = []
    for form, share in shares.items():
        if share == 0:
            continue
        notes = []
        if fibre == "cotton_elastane":
            notes.append("Elastane content limits mechanical recycling; confirm % before offer.")
        if colour == "mixed":
            notes.append("Mixed colours: sort or route to recyclers that accept mixed shades.")
        if form == "cutting":
            notes.append("Small irregular pieces; bale tightly to cut freight cost.")
        lots.append(Lot(f"{run_id}-{form[:3].upper()}", code, fibre, colour, form,
                        round(kg["p50"] * share, 1), round(kg["p10"] * share, 1),
                        round(kg["p90"] * share, 1), " ".join(notes)))
    return lots
