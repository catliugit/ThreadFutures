"""Offcut planning agent built on an LLM with tool use.

Give it a messy production-order note (an email, a WhatsApp message, a PO
excerpt). It extracts the order, calls the forecasting, grading and matching
tools, and drafts a short lot offer a factory could send to a recycler.

The model does the language work (extraction, judgement, drafting). All numbers
come from the deterministic tools, so forecasts are reproducible and auditable.

Requires ``pip install -r requirements-llm.txt`` and LLM_API_KEY / LLM_MODEL set in
the environment (see .env.example).

    python -m offcut.agent "PO 4471: 22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka"
"""
from __future__ import annotations

import json
import os
import sys

import anthropic
from anthropic import beta_tool

from . import service

MODEL = os.environ.get("LLM_MODEL", "")

SYSTEM = """You help garment factories plan what happens to their cutting-room offcuts \
before a production run is cut.

Work in this order:
1. Read the production note and extract one order. Allowed values:
   garment: tee | hoodie | shirt | jeans | dress
   fibre: cotton | polyester | cotton_poly | cotton_elastane
   size_mix: narrow (2-4 core sizes) | standard (XS-XXL, peaked at M/L) | extended (flat across sizes, incl. plus)
   colour: white | light | dark | mixed;  region: UK | EU | Turkey | South Asia
   You need fabric_width_m (metres), gsm (g/m2) and fabric_metres.
2. If a required field is missing or ambiguous, state your assumption explicitly \
(e.g. "denim assumed 1.55 m wide") rather than inventing precision.
3. Call plan_offcuts with the order. Never compute forecast numbers yourself.
4. Reply with: the order you used (with assumptions flagged), the forecast range \
(P10-P90 kg) next to the 15% rule of thumb, each lot with its best recycler match and why, \
and a 4-6 sentence lot offer the factory could send. Note that recycler profiles are samples."""


@beta_tool
def plan_offcuts(garment: str, fibre: str, size_mix: str, fabric_width_m: float,
                 gsm: float, fabric_metres: float, colour: str = "mixed",
                 region: str = "South Asia", run_id: str = "RUN") -> str:
    """Forecast pre-cut offcuts for a production run, split them into graded lots,
    and rank sample recyclers for each lot.

    Args:
        garment: One of tee, hoodie, shirt, jeans, dress.
        fibre: One of cotton, polyester, cotton_poly, cotton_elastane.
        size_mix: One of narrow, standard, extended.
        fabric_width_m: Fabric roll width in metres (1.2-2.2).
        gsm: Fabric weight in grams per square metre (60-500).
        fabric_metres: Total fabric length planned for the run (500-60000).
        colour: One of white, light, dark, mixed.
        region: One of UK, EU, Turkey, South Asia.
        run_id: The factory's run or PO reference.
    """
    order = dict(garment=garment, fibre=fibre, size_mix=size_mix,
                 fabric_width_m=fabric_width_m, gsm=gsm, fabric_metres=fabric_metres,
                 colour=colour, region=region, run_id=run_id)
    try:
        return json.dumps(service.plan(order))
    except (ValueError, KeyError) as e:
        # Returned to the model as a tool error so it can correct the order.
        return json.dumps({"error": str(e)})


def run(note: str) -> str:
    if not MODEL:
        raise SystemExit("Set LLM_MODEL and LLM_API_KEY (see .env.example).")
    client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"])
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        tools=[plan_offcuts],
        output_config={"effort": "medium"},
        # Server-side fallback on a policy refusal (routes by refusal category).
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": note}],
    )
    final = runner.until_done()
    if final.stop_reason == "refusal":
        return "The request was declined."
    return "".join(b.text for b in final.content if b.type == "text")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('usage: python -m offcut.agent "<production order note>"')
    print(run(" ".join(sys.argv[1:])))
