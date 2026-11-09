# Part 08: Purchase-order agent, step by step

**Status:** Built · **Data label:** Prototype. The forecast it calls is trained on SIMULATED cutting runs (part 01). Recycler profiles are fictional samples.
**Code:** `src/offcut/agent.py`, `src/offcut/service.py`, `src/offcut/grading.py`, `src/offcut/matching.py`, `data/recyclers_sample.json`
**Tests:** `tests/test_offcut.py` (TestModelExport::test_service_plan, test_service_rejects_bad_order, TestGradingMatching)

---

## 1. The question this stage answers

Production orders arrive as messy emails and chat messages, not tidy forms. Can a language model read one, work out the order, say what it had to assume, and produce an offcut plan where every number comes from tested code?

A fashion brand (or its factory) cares because the useful information is locked in free text: "PO 4471: 22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka". Retyping it into a form is the step people skip, so the forecast never gets used. The agent removes that step without letting the model make up numbers.

---

## 2. The pipeline, step by step

### Step 1. A deterministic "plan" service

**Where:** `src/offcut/service.py`, `forecast()` and `plan()`

```python
def plan(order: Dict) -> Dict:
    """Forecast, grade and match in one call."""
    fc = forecast(order)
    colour = order.get("colour", "mixed")
    region = order.get("region", "South Asia")
    lots = build_lots(order.get("run_id", "RUN"), order["fibre"], colour,
                      GARMENTS[order["garment"]].knit, fc["offcut_kg"])
    recyclers = load_recyclers()
    return {
        "forecast": fc,
        "lots": [dict(l.as_dict(), matches=match_lot(l, region, recyclers)[:3]) for l in lots],
    }
```

- `forecast(order)`: validates the order, encodes it, and runs the exported part 01 model (the JSON trees, via `predict_json`) for P10, P50 and P90. It also returns the 15% rule-of-thumb kg for comparison.
- Defaults: colour "mixed", region "South Asia" if not given.
- `build_lots`: splits the forecast into lots by physical form.
- `match_lot`: ranks sample recyclers for each lot; keep the top 3.

**Why:** this function is plain Python, tested, and gives the same answer every time for the same order. It's what the API, the agent and the tests all call.

### Step 2. Validate the order strictly

```python
def validate_order(order: Dict) -> None:
    for c in PRE_MARKER:
        if c not in order:
            raise ValueError(f"order is missing '{c}'")
    for c, allowed in CATEGORIES.items():
        if order[c] not in allowed:
            raise ValueError(f"{c} must be one of {allowed}, got {order[c]!r}")
    if not 1.2 <= float(order["fabric_width_m"]) <= 2.2:
        raise ValueError("fabric_width_m must be between 1.2 and 2.2")
```

- Every required field must be present, categories must be known, and numbers must be within the ranges the model was trained on (also 60 to 500 gsm and 500 to 60,000 metres).
- The error messages are written to be read by a person or a model: they say what's allowed.

**Why:** the model only knows the ranges it saw. Refusing out-of-range orders is safer than extrapolating silently.

### Step 3. Turn the forecast into graded lots

**Where:** `src/offcut/grading.py`

```python
FORM_SHARE = {"knit": {"strips": 0.0, "remnant": 0.20, "cutting": 0.80},
              "woven": {"strips": 0.07, "remnant": 0.18, "cutting": 0.75}}
```

- Offcuts are split by form, because form drives recyclability: strips (selvedge trim, only on wovens), remnants (roll ends, often reusable) and cutting waste (small irregular pieces, most of the volume).
- Grade code = fibre class + colour class, e.g. `C1-W` for 100% cotton, white.
- Notes are added automatically, for example "Elastane content limits mechanical recycling; confirm % before offer."

A test checks the lots add back up to the forecast (`test_lots_sum_to_forecast`).

### Step 4. Match lots to recyclers: filter, then score

**Where:** `src/offcut/matching.py`, `match_lot()`

```python
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
```

- First, hard constraints (earlier in the function): the recycler must accept the grade, the form, and serve the region. If not, skip it.
- Then the size score uses the **forecast range**: if even the pessimistic P10 clears the recycler's minimum lot, that's the safest match. This is where quantile forecasting pays off.
- Final score: 60% size, 25% how well the recycler's process suits the fibre, 15% lead time (faster is better, capped at 60 days).
- Every match carries a plain-English "why".

The five recycler profiles in `data/recyclers_sample.json` are fictional, each labelled "(sample)".

### Step 5. Expose the plan as a tool for the language model

**Where:** `src/offcut/agent.py`, `plan_offcuts()`

```python
@beta_tool
def plan_offcuts(garment: str, fibre: str, size_mix: str, fabric_width_m: float,
                 gsm: float, fabric_metres: float, colour: str = "mixed",
                 region: str = "South Asia", run_id: str = "RUN") -> str:
    """Forecast pre-cut offcuts for a production run, split them into graded lots,
    and rank sample recyclers for each lot.
    ...
    try:
        return json.dumps(service.plan(order))
    except (ValueError, KeyError) as e:
        # Returned to the model as a tool error so it can correct the order.
        return json.dumps({"error": str(e)})
```

- The decorator from the LLM provider's SDK turns the function's typed signature and docstring into a tool definition the model can see: name, parameters, types, and the allowed values listed in the docstring.
- The function just calls `service.plan`.
- If validation fails, the error goes back to the model as the tool's result instead of crashing. The model can read "gsm must be between 60 and 500" and fix the order.

### Step 6. Instruct the model with a system prompt

```python
SYSTEM = """You help garment factories plan what happens to their cutting-room offcuts \
before a production run is cut.
...
2. If a required field is missing or ambiguous, state your assumption explicitly \
(e.g. "denim assumed 1.55 m wide") rather than inventing precision.
3. Call plan_offcuts with the order. Never compute forecast numbers yourself.
4. Reply with: the order you used (with assumptions flagged), the forecast range \
(P10-P90 kg) next to the 15% rule of thumb, each lot with its best recycler match and why, \
and a 4-6 sentence lot offer the factory could send. Note that recycler profiles are samples."""
```

- Step 1 of the prompt (not shown) lists the allowed values for every field.
- Step 2: flag assumptions instead of guessing silently.
- Step 3: the key rule. The model never does the maths.
- Step 4: a fixed reply structure, including the rule-of-thumb comparison and a draft offer to a recycler.

### Step 7. Run the tool-use loop

```python
def run(note: str) -> str:
    if not MODEL:
        raise SystemExit("Set LLM_MODEL and LLM_API_KEY (see .env.example).")
    ...
    final = runner.until_done()
    if final.stop_reason == "refusal":
        return "The request was declined."
    return "".join(b.text for b in final.content if b.type == "text")
```

- The model name and API key come from environment variables (`LLM_MODEL`, `LLM_API_KEY`), set in a local `.env` file that is never committed. `.env.example` shows the variable names with empty values.
- The SDK's tool runner handles the loop: send the note, the model asks to call `plan_offcuts`, the code runs it, the result goes back, and so on until the model writes its final reply.
- If the model declines, the function says so rather than returning nothing.
- The final reply is the text blocks joined together.

---

## 3. Concepts, from scratch

### Large language model (LLM)
**Definition:** a model trained on large amounts of text that predicts likely next words. Good at reading messy language and writing; unreliable at precise arithmetic and facts it hasn't been given.

### Tool use (function calling)
**Definition:** the model is given descriptions of functions it may call. Instead of answering directly, it can output "call this function with these arguments"; your code runs it and returns the result.
**Analogy:** a sharp assistant with a calculator and a filing system. They decide what to look up; the calculator does the sums.
**Why it matters here:** the model does extraction and drafting; tested code does every number.

### Agent and the agent loop
**Definition:** an LLM that can take several steps, calling tools and reading results, until a task is done.
**Here:** a small agent with one tool. Read note, call tool, maybe correct and call again, then write the reply.

### System prompt
**Definition:** instructions given to the model before the user's message, setting its role and rules.

### Structured extraction
**Definition:** turning free text into fields with defined types and allowed values.
**Worked example:** "22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka" becomes garment `tee`, fibre `cotton`, colour `white`, fabric_metres 22,000, gsm 180, fabric_width_m 1.8, size_mix `standard` (XS to XXL is closest), region `South Asia`. The size mix is a judgement the model should flag as an assumption, since "S-XXL" isn't exactly any template.

### Deterministic vs probabilistic components
**Definition:** deterministic code gives the same output for the same input. An LLM may phrase things differently each time.
**Design principle:** put anything that must be reproducible or auditable (forecasts, lot sizes, scores) in deterministic code.

### Stating assumptions
**Definition:** when information is missing, say what was assumed, so a person can correct it.
**Why it matters:** a confident wrong width gives a confident wrong forecast. A flagged assumption invites a check.

### Tool errors as feedback
**Definition:** return validation errors to the model as tool results instead of raising them.
**Why it matters:** the model can correct itself (for example, convert "180 g" or change an unknown fibre to the nearest allowed one and say so).

### Input validation and allowed ranges
**Definition:** reject inputs outside what the system supports. Here, the same ranges as the training data contract in part 01.

### Hard constraints then scoring
**Definition:** first remove options that can't work (wrong grade, wrong region), then rank the rest by a weighted score.
**Why it matters:** it keeps the ranking explainable: every match has a reason.

### Environment variables and secrets
**Definition:** configuration passed in from outside the code. API keys belong here, never in the source.
**Here:** `.env` (ignored by git) holds the real key; `.env.example` documents what's needed.

---

## 4. The real results, and how to read them

There's no metrics file for the agent, and I won't invent one. What is true and checkable:

- Every figure in the reply comes from `service.plan`, which is covered by tests: `test_service_plan` checks P10 <= P50 <= P90 and that lots are produced for a jeans order; `test_service_rejects_bad_order` checks a "sock" garment is rejected; `test_lots_sum_to_forecast` and `test_matching_respects_constraints` check the lot split and the recycler filter.
- The forecast inside it carries the part 01 accuracy: 8.8% mean error on 1,600 held-out **simulated** runs, P10 to P90 coverage 76.8%.
- The agent itself has **not been evaluated** on a set of real order notes. That's the obvious next step: 30 to 50 real or realistic notes with the correct extracted order, measuring field-level accuracy and how often assumptions are flagged.

To see it work on the deterministic side without any API key:

```bash
PYTHONPATH=src python -m offcut.service
```

That prints the forecast, lots and top recycler matches for a demo tee order.

---

## 5. What went wrong or surprised me, and what it taught me

- **The temptation to let the model do the maths.** It would have been quicker to ask the model "how much offcut will this produce?". It would also have been unreproducible and unauditable. Making the model call a tool for every number was the key design decision.
- **Error messages are part of the interface.** Once tool errors go back to the model, the wording of `ValueError` messages matters. "gsm must be between 60 and 500" lets the model fix the problem; a stack trace wouldn't.
- **Assumptions are a feature.** Real notes leave things out (width is often missing for denim). The prompt makes the model say "denim assumed 1.55 m wide", which turns a hidden risk into something a planner can correct.
- **Inherited from part 01:** the float32 export fix matters here too, because the agent's tool uses the same exported JSON model.

---

## 6. Honest limits

- **Prototype.** Needs an LLM API key, and isn't evaluated on a large set of real orders.
- The underlying forecast is trained on **simulated** runs.
- Recycler profiles are **fictional samples**; the form shares in `grading.py` come from the simulator, and the grade standard is a v0 written for illustration, not agreed with recyclers.
- One tool only. A real version would need tools for looking up the factory's fabric library, checking recycler capacity, and so on.
- Language models can still mis-extract a field confidently. Flagged assumptions and human review are the safeguards, not a guarantee.
- Not used by a customer.

---

## 7. How to run it yourself

Deterministic part (no key needed):

```bash
make offcuts                        # trains and exports the forecast model
PYTHONPATH=src python -m offcut.service
make test
```

Agent (needs an LLM API key):

```bash
cp .env.example .env                # then fill in LLM_API_KEY and LLM_MODEL
pip install -r requirements-llm.txt
PYTHONPATH=src python -m offcut.agent "PO 4471: 22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka"
```

Make sure the variables in `.env` are loaded into your shell (for example `set -a; source .env; set +a`) before running.

---

## 8. Glossary

- **LLM:** large language model.
- **Tool use / function calling:** the model asks your code to run a function and reads the result.
- **Agent:** an LLM that takes several tool-using steps towards a goal.
- **Agent loop / tool runner:** the code that passes tool calls and results back and forth.
- **System prompt:** standing instructions for the model.
- **Structured extraction:** turning free text into typed fields.
- **Deterministic:** same input, same output.
- **Assumption flagging:** stating what was guessed when information was missing.
- **Tool error:** a validation message returned to the model so it can correct itself.
- **Input validation:** rejecting inputs outside the supported range.
- **Graded lot:** a batch of offcuts with a fibre and colour grade and a physical form.
- **Grade code:** fibre class plus colour class, such as C1-W.
- **Hard constraint:** a rule that must be met for an option to be considered.
- **Weighted score:** a ranking combining several factors with fixed weights.
- **Minimum lot:** the smallest batch a recycler will accept.
- **Environment variable:** configuration supplied from outside the code.
- **`.env` / `.env.example`:** local secrets file (never committed) / template showing required variables.
- **PO:** purchase order.
