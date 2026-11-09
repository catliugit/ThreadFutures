"""Marker building: lay graded pattern pieces onto a fabric width.

A production marker nests irregular polygons. We approximate each piece by an
area-equivalent rectangle (true area divided by the garment's nesting
compactness ``k``, same aspect ratio as its bounding box) and pack those with a
skyline bottom-left heuristic. Pieces keep their grain direction: no 90-degree
rotation, as in real cutting rooms.

Marker efficiency = true piece area / (usable width x marker length).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .garments import Garment, graded_pieces

# Highest marker efficiency reported for multi-size cut-and-sew markers (~92-93%).
MAX_EFFICIENCY = 0.93


@dataclass
class Marker:
    width_cm: float
    length_cm: float
    true_area_cm2: float
    n_pieces: int
    garments_per_marker: int

    @property
    def efficiency(self) -> float:
        return self.true_area_cm2 / (self.width_cm * self.length_cm)


def _skyline_pack(rects: List[Tuple[float, float]], width: float) -> float:
    """Pack (w, h) rectangles, in the given order, into a strip of ``width``.

    Skyline bottom-left: keep a list of (x, y, w) segments forming the top
    profile; place each rectangle where its top edge is lowest. Returns the
    used length.
    """
    sky: List[List[float]] = [[0.0, 0.0, width]]
    for w, h in rects:
        if w > width:
            raise ValueError(f"piece {w:.1f}cm wider than fabric {width:.1f}cm")
        best = None  # (top, x, start_idx, base_y)
        for i in range(len(sky)):
            x = sky[i][0]
            if x + w > width + 1e-9:
                break
            base, j, span = 0.0, i, 0.0
            while span < w - 1e-9:
                base = max(base, sky[j][1])
                span += sky[j][2]
                j += 1
            top = base + h
            if best is None or (top, x) < (best[0], best[1]):
                best = (top, x, i, base)
        top, x, i, base = best
        # Replace covered skyline with the new segment.
        new_seg = [x, top, w]
        right = x + w
        kept_left = sky[:i]
        rest = []
        for seg in sky[i:]:
            sx, sy, sw = seg
            if sx + sw <= right + 1e-9:
                continue
            if sx < right:
                rest.append([right, sy, sx + sw - right])
            else:
                rest.append(seg)
        sky = kept_left + [new_seg] + rest
        # Merge neighbours at equal height.
        merged: List[List[float]] = []
        for seg in sky:
            if merged and abs(merged[-1][1] - seg[1]) < 1e-9:
                merged[-1][2] += seg[2]
            else:
                merged.append(seg)
        sky = merged
    return max(s[1] for s in sky)


def build_marker(garment: Garment, width_m: float, size_ratio: Dict[str, int],
                 style_jitter: float = 1.0, seed: int = 0) -> Marker:
    """Build one marker for ``size_ratio`` garments on ``width_m`` of usable fabric."""
    width_cm = width_m * 100.0
    rects: List[Tuple[float, float]] = []
    true_area = 0.0
    n_garments = 0
    for size, count in size_ratio.items():
        n_garments += count
        for p in graded_pieces(garment, size, style_jitter):
            for _ in range(p.qty * count):
                area = p.area_cm2
                true_area += area
                eff_area = area / garment.nest_k
                aspect = p.w_cm / p.h_cm
                h = math.sqrt(eff_area / aspect)
                w = eff_area / h
                rects.append((w, h))
    length = min(_skyline_pack(order, width_cm) for order in _orderings(rects, seed))
    # The calibration factor can occasionally overshoot what any real marker achieves;
    # hold efficiency at the published upper bound for cut-and-sew garments.
    length = max(length, true_area / (width_cm * MAX_EFFICIENCY))
    return Marker(width_cm, length, true_area, len(rects), n_garments)


def _orderings(rects: List[Tuple[float, float]], seed: int, n_random: int = 6):
    """Candidate placement orders. Marker makers try many layouts and keep the
    shortest; we try four greedy sorts plus a few seeded shuffles."""
    yield sorted(rects, key=lambda r: (-r[1], -r[0]))      # tallest first
    yield sorted(rects, key=lambda r: -(r[0] * r[1]))      # largest area first
    yield sorted(rects, key=lambda r: (-r[0], -r[1]))      # widest first
    yield sorted(rects, key=lambda r: -max(r))             # longest side first
    rng = random.Random(seed)
    base = sorted(rects, key=lambda r: -(r[0] * r[1]))
    for _ in range(n_random):
        order = base[:]
        # Perturb the area ordering locally rather than fully shuffling.
        for i in range(len(order) - 1):
            if rng.random() < 0.3:
                order[i], order[i + 1] = order[i + 1], order[i]
        yield order
