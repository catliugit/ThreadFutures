import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from regsearch.search import BM25, check_citations  # noqa: E402
from stock.monitor import psi  # noqa: E402


def test_psi_zero_for_same_distribution_and_large_for_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 5000)) < 0.02
    assert psi(a, rng.normal(1.5, 1, 5000)) > 0.25


def test_bm25_prefers_matching_document():
    docs = ["destruction of unsold apparel is prohibited", "disclosure of discarded products each year"]
    s = BM25(docs).scores("apparel destruction")
    assert s[0] > s[1]


def test_citation_check_flags_unretrieved_articles():
    retrieved = [{"id": "Art 25(1)"}, {"id": "Annex VII"}]
    assert check_citations("Banned from 2026 [Art 25(1)] for clothing [Annex VII].", retrieved) == []
    assert check_citations("Exceptions exist [Art 25(5)].", retrieved) == ["Art 25(5)"]


def test_saved_results_are_consistent():
    m = json.loads((ROOT / "models" / "stall_metrics.json").read_text())
    assert m["model"]["roc_auc"] > m["rule_trend_halved"]["roc_auc"]
    e = json.loads((ROOT / "models" / "regsearch_eval.json").read_text())
    assert e["bm25"]["hit@3"] >= 0.9
