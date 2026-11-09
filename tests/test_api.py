import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)
ORDER = {"garment": "tee", "fibre": "cotton", "size_mix": "standard",
         "fabric_width_m": 1.8, "gsm": 180, "fabric_metres": 18000}
LINE = {"early_units_per_week": 40, "early_trend": 0.3, "early_zero_week_share": 0.25, "early_customers": 30,
        "early_orders": 45, "early_return_rate": 0.02, "early_max_markdown": 0.0, "launch_list_price": 2.95,
        "launch_month": 3, "is_seasonal_christmas": False}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_offcut_forecast_is_ordered_and_plausible():
    r = client.post("/v1/offcuts/forecast", json=ORDER).json()
    kg = r["offcut_kg"]
    assert kg["p10"] <= kg["p50"] <= kg["p90"]
    assert 0.05 * r["input_kg"] < kg["p50"] < 0.35 * r["input_kg"]


def test_offcut_rejects_bad_input():
    assert client.post("/v1/offcuts/forecast", json=ORDER | {"garment": "coat"}).status_code == 422
    assert client.post("/v1/offcuts/forecast", json=ORDER | {"gsm": 5}).status_code == 422


def test_stall_risk_returns_probability():
    r = client.post("/v1/stock/stall-risk", json=LINE).json()
    assert 0 <= r["stall_probability"] <= 1 and r["risk"] in {"low", "medium", "high"}


def test_stall_risk_rejects_bad_month():
    assert client.post("/v1/stock/stall-risk", json=LINE | {"launch_month": 13}).status_code == 422


def test_regulation_search_finds_the_ban():
    r = client.get("/v1/regulation/search", params={"q": "when does the destruction ban start"}).json()
    assert "Art 25(1)" in [x["id"] for x in r["results"]]
