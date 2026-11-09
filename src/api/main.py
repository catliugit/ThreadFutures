"""Thread Futures API: offcut forecasts, stall risk for unsold stock, and regulation search.

    uvicorn api.main:app --app-dir src --reload
    # docs at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from offcut import service
from regsearch.search import search

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="Thread Futures API", version="0.1.0",
              description="Prototype. Offcut forecasts are trained on simulated cutting runs; "
                          "stall risk is trained on open retail data (UCI Online Retail II).")


class OffcutOrder(BaseModel):
    garment: Literal["tee", "hoodie", "shirt", "jeans", "dress"]
    fibre: Literal["cotton", "polyester", "cotton_poly", "cotton_elastane"]
    size_mix: Literal["narrow", "standard", "extended"]
    fabric_width_m: float = Field(ge=1.2, le=2.2, description="Fabric width in metres")
    gsm: float = Field(ge=60, le=500, description="Fabric weight, grams per square metre")
    fabric_metres: float = Field(ge=500, le=60000, description="Planned fabric length in metres")


class EarlySales(BaseModel):
    """A line's first 12 weeks on sale."""
    early_units_per_week: float = Field(ge=0)
    early_trend: float = Field(gt=0, description="(avg units wk 8-11 + 1) / (avg units wk 0-3 + 1)")
    early_zero_week_share: float = Field(ge=0, le=1)
    early_customers: float = Field(ge=0)
    early_orders: float = Field(ge=0)
    early_return_rate: float = Field(ge=0, le=1)
    early_max_markdown: float = Field(ge=0, le=1)
    launch_list_price: float = Field(ge=0)
    launch_month: int = Field(ge=1, le=12)
    is_seasonal_christmas: bool = False


@lru_cache
def _stall_model() -> dict:
    return joblib.load(ROOT / "models" / "stall_model.joblib")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/offcuts/forecast")
def offcut_forecast(order: OffcutOrder) -> dict:
    try:
        return service.forecast(order.model_dump()) | {"data": "simulated cutting runs"}
    except ValueError as e:  # pragma: no cover - pydantic catches ranges first
        raise HTTPException(422, str(e))


@app.post("/v1/stock/stall-risk")
def stall_risk(line: EarlySales) -> dict:
    b = _stall_model()
    x = pd.DataFrame([line.model_dump()])[b["features"]].astype(float)
    p = float(b["model"].predict_proba(x)[0, 1])
    band = "high" if p >= 0.4 else "medium" if p >= 0.15 else "low"
    return {"stall_probability": round(p, 3), "risk": band,
            "meaning": "Chance that weekly sales in weeks 12-25 fall below 20% of the first 12 weeks."}


@app.get("/v1/regulation/search")
def regulation_search(q: str = Query(min_length=3, max_length=300), k: int = Query(3, ge=1, le=10)) -> dict:
    hits = search(q, k)
    return {"query": q, "results": [{"id": h["id"], "title": h["title"], "text": h["text"], "score": h["score"]} for h in hits],
            "note": "General information from Regulation (EU) 2024/1781, not legal advice."}
