import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from offcut.export import predict_json  # noqa: E402
from offcut.garments import GARMENTS, SIZE_MIXES  # noqa: E402
from offcut.grading import build_lots, grade_code  # noqa: E402
from offcut.matching import load_recyclers, match_lot  # noqa: E402
from offcut.nesting import _skyline_pack, build_marker  # noqa: E402
from offcut.pipeline import validate  # noqa: E402
from offcut.simulate import simulate, simulate_run  # noqa: E402

MODEL = ROOT / "models" / "pre_marker_model.json"


class TestNesting(unittest.TestCase):
    def test_exact_fit(self):
        # Four 50x50 squares in a 100-wide strip need exactly 100 of length.
        self.assertAlmostEqual(_skyline_pack([(50, 50)] * 4, 100), 100)

    def test_efficiency_in_realistic_range(self):
        for g in GARMENTS.values():
            m = build_marker(g, sum(g.width_range) / 2, SIZE_MIXES["standard"])
            self.assertTrue(0.70 < m.efficiency < 0.92, (g.key, m.efficiency))

    def test_piece_wider_than_fabric_raises(self):
        with self.assertRaises(ValueError):
            _skyline_pack([(120, 10)], 100)


class TestSimulation(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(simulate(5, seed=3), simulate(5, seed=3))

    def test_mass_balance_and_gap(self):
        rng = random.Random(1)
        for i in range(50):
            r = simulate_run(rng, f"T-{i}")
            self.assertLess(r.cut_panels_kg, r.input_kg)
            # Real waste always exceeds what the marker alone predicts.
            self.assertGreater(r.offcut_ratio, (1 - r.marker_efficiency) * 0.95)


class TestContract(unittest.TestCase):
    def test_catches_bad_rows(self):
        df = pd.DataFrame(simulate(20, seed=2))
        self.assertEqual(validate(df), [])
        bad = df.copy()
        bad.loc[0, "garment"] = "sock"
        bad.loc[1, "offcut_ratio"] = 0.9
        problems = " ".join(validate(bad))
        self.assertIn("garment", problems)
        self.assertIn("offcut_ratio", problems)


@unittest.skipUnless(MODEL.exists(), "run `make train` first")
class TestModelExport(unittest.TestCase):
    def test_json_matches_sklearn(self):
        """The exported JSON trees must reproduce scikit-learn's predictions."""
        from offcut.pipeline import PRE_MARKER, encode
        from offcut.train import fit_quantiles
        df = pd.DataFrame(simulate(400, seed=5))
        X, y = encode(df, PRE_MARKER), df["offcut_ratio"]
        models = fit_quantiles(X, y)
        from offcut.export import export_quantile_model
        tmp = ROOT / "models" / "_test_export.json"
        try:
            export_quantile_model(models, list(X.columns), tmp)
            payload = json.loads(tmp.read_text())
            for q, m in models.items():
                sk = m.predict(X.iloc[:25])
                js = [predict_json(payload, row, q) for row in X.iloc[:25].to_numpy().tolist()]
                for a, b in zip(sk, js):
                    self.assertAlmostEqual(a, b, places=3)
        finally:
            tmp.unlink(missing_ok=True)

    def test_service_plan(self):
        from offcut import service
        out = service.plan({"garment": "jeans", "fibre": "cotton", "size_mix": "standard",
                            "fabric_width_m": 1.55, "gsm": 380, "fabric_metres": 12000,
                            "colour": "dark", "region": "EU"})
        fc = out["forecast"]["offcut_kg"]
        self.assertLessEqual(fc["p10"], fc["p50"])
        self.assertLessEqual(fc["p50"], fc["p90"])
        self.assertGreater(len(out["lots"]), 0)

    def test_service_rejects_bad_order(self):
        from offcut import service
        with self.assertRaises(ValueError):
            service.forecast({"garment": "sock", "fibre": "cotton", "size_mix": "standard",
                              "fabric_width_m": 1.5, "gsm": 200, "fabric_metres": 5000})


class TestGradingMatching(unittest.TestCase):
    def test_grade_codes(self):
        self.assertEqual(grade_code("cotton", "white"), "C1-W")
        self.assertEqual(grade_code("cotton_elastane", "dark"), "E1-D")

    def test_lots_sum_to_forecast(self):
        kg = {"p10": 800, "p50": 1000, "p90": 1200}
        lots = build_lots("R", "cotton", "white", knit=False, kg=kg)
        self.assertAlmostEqual(sum(l.kg_p50 for l in lots), 1000, delta=1)
        self.assertEqual({l.form for l in lots}, {"strips", "remnant", "cutting"})

    def test_matching_respects_constraints(self):
        recyclers = load_recyclers()
        lot = build_lots("R", "polyester", "dark", knit=True,
                         kg={"p10": 900, "p50": 1000, "p90": 1100})[1]
        matches = match_lot(lot, "EU", recyclers)
        self.assertTrue(matches)
        for m in matches:
            r = next(x for x in recyclers if x["name"] == m["recycler"])
            self.assertIn(lot.grade, r["accepts_grades"])
            self.assertIn("EU", r["regions"])


if __name__ == "__main__":
    unittest.main()
