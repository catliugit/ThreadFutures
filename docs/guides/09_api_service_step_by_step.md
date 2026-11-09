# Part 09: API service, step by step

**Status:** Built · **Data label:** Prototype. Offcut forecast trained on SIMULATED runs; stall risk trained on REAL OPEN RETAIL DATA; regulation search over real EU law text.
**Code:** `src/api/main.py`; tests in `tests/test_api.py` (plus `tests/test_offcut.py`, `tests/test_stock.py`)
**Numbers from:** the test files and `.pytest_cache/v/cache/nodeids` (see section 4 on the test count)

---

## 1. The question this stage answers

How do I turn three separate models (offcut forecast, stall risk, regulation search) into one service that any other system, website or colleague can call, safely?

A fashion brand cares because a model in a notebook helps nobody. A planning tool, an ERP or a dashboard needs to send a request and get a reliable answer back, and a bad request needs to fail clearly instead of returning a plausible wrong number.

---

## 2. The pipeline, step by step

### Step 1. Create the app

```python
app = FastAPI(title="Thread Futures API", version="0.1.0",
              description="Prototype. Offcut forecasts are trained on simulated cutting runs; "
                          "stall risk is trained on open retail data (UCI Online Retail II).")
```

- One FastAPI application. The description carries the data labels, so anyone reading the auto-generated docs at `/docs` sees what the models are trained on.

### Step 2. Define the inputs as Pydantic models

```python
class OffcutOrder(BaseModel):
    garment: Literal["tee", "hoodie", "shirt", "jeans", "dress"]
    fibre: Literal["cotton", "polyester", "cotton_poly", "cotton_elastane"]
    size_mix: Literal["narrow", "standard", "extended"]
    fabric_width_m: float = Field(ge=1.2, le=2.2, description="Fabric width in metres")
    gsm: float = Field(ge=60, le=500, description="Fabric weight, grams per square metre")
    fabric_metres: float = Field(ge=500, le=60000, description="Planned fabric length in metres")
```

- `Literal[...]`: only these exact strings are allowed. "coat" is rejected.
- `Field(ge=..., le=...)`: greater-or-equal and less-or-equal bounds. These match the data contract from part 01, so the API only accepts inputs inside the range the model was trained on.
- `description`: appears in the generated docs.

The stall-risk input, `EarlySales`, does the same for the ten features from part 04, for example:

```python
    early_trend: float = Field(gt=0, description="(avg units wk 8-11 + 1) / (avg units wk 0-3 + 1)")
    early_zero_week_share: float = Field(ge=0, le=1)
    launch_month: int = Field(ge=1, le=12)
    is_seasonal_christmas: bool = False
```

- `gt=0`: the trend is a ratio of two positive numbers, so it can't be 0 or negative.
- Shares are between 0 and 1; months between 1 and 12.

**Why:** validation happens before any of my code runs. FastAPI returns HTTP 422 with a message saying which field failed and why.

### Step 3. Health check

```python
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- The simplest possible endpoint. Docker's `HEALTHCHECK` and the CI smoke test (part 10) call it to know the service is up.

### Step 4. Offcut forecast endpoint

```python
@app.post("/v1/offcuts/forecast")
def offcut_forecast(order: OffcutOrder) -> dict:
    try:
        return service.forecast(order.model_dump()) | {"data": "simulated cutting runs"}
    except ValueError as e:  # pragma: no cover - pydantic catches ranges first
        raise HTTPException(422, str(e))
```

- POST, because the client sends a body (the order).
- `order.model_dump()` turns the validated Pydantic object into a plain dict for `service.forecast` (part 08), which runs the exported JSON trees.
- `| {"data": "simulated cutting runs"}`: every response is labelled with its data source.
- The `try/except` is a second safety net. Pydantic already enforces the same ranges, so in practice it never fires (hence the `pragma: no cover` note for coverage tools).

### Step 5. Stall-risk endpoint

```python
@lru_cache
def _stall_model() -> dict:
    return joblib.load(ROOT / "models" / "stall_model.joblib")

@app.post("/v1/stock/stall-risk")
def stall_risk(line: EarlySales) -> dict:
    b = _stall_model()
    x = pd.DataFrame([line.model_dump()])[b["features"]].astype(float)
    p = float(b["model"].predict_proba(x)[0, 1])
    band = "high" if p >= 0.4 else "medium" if p >= 0.15 else "low"
    return {"stall_probability": round(p, 3), "risk": band,
            "meaning": "Chance that weekly sales in weeks 12-25 fall below 20% of the first 12 weeks."}
```

- `@lru_cache`: load the model from disk once, on the first request, then reuse it.
- Build a one-row DataFrame in exactly the feature order saved with the model (`b["features"]`). Column order matters for scikit-learn.
- Return the probability, a band (high at 0.4 or above, medium at 0.15 or above, low below) and a plain-English meaning.

**Why the bands:** a merchandiser wants "high / medium / low", not 0.287. The thresholds are judgement calls, and given the calibration findings in part 06, the probability itself should be read as a ranking signal.

### Step 6. Regulation search endpoint

```python
@app.get("/v1/regulation/search")
def regulation_search(q: str = Query(min_length=3, max_length=300), k: int = Query(3, ge=1, le=10)) -> dict:
    hits = search(q, k)
    return {"query": q, "results": [{"id": h["id"], "title": h["title"], "text": h["text"], "score": h["score"]} for h in hits],
            "note": "General information from Regulation (EU) 2024/1781, not legal advice."}
```

- GET, because it's a read-only lookup with query parameters (`?q=...&k=3`).
- `Query(min_length=3, max_length=300)`: no empty or giant queries.
- `k` between 1 and 10.
- Uses the BM25 search from part 07, and every response carries the "not legal advice" note.

### Step 7. Test it with TestClient

**Where:** `tests/test_api.py`

```python
client = TestClient(app)
...
def test_offcut_forecast_is_ordered_and_plausible():
    r = client.post("/v1/offcuts/forecast", json=ORDER).json()
    kg = r["offcut_kg"]
    assert kg["p10"] <= kg["p50"] <= kg["p90"]
    assert 0.05 * r["input_kg"] < kg["p50"] < 0.35 * r["input_kg"]

def test_offcut_rejects_bad_input():
    assert client.post("/v1/offcuts/forecast", json=ORDER | {"garment": "coat"}).status_code == 422
    assert client.post("/v1/offcuts/forecast", json=ORDER | {"gsm": 5}).status_code == 422
```

- `TestClient` calls the app in-process, without starting a server.
- Test 1: the quantiles come back in order, and the median is a plausible share of input fabric (5% to 35%).
- Test 2: an unknown garment and an impossible gsm both return 422.

The six API tests cover health, a plausible ordered forecast, bad offcut input, a valid stall probability and band, a bad launch month (13 returns 422), and that searching "when does the destruction ban start" returns `Art 25(1)` in the results.

---

## 3. Concepts, from scratch

### API
**Definition:** application programming interface. A defined way for one program to ask another for something.

### REST and HTTP methods
**Definition:** a style of web API where resources have URLs and you act on them with HTTP methods.
- **GET:** read, no side effects, parameters in the URL. Used for search.
- **POST:** send a body to be processed. Used for forecasts.
**Analogy:** GET is looking something up in a catalogue; POST is handing over a form.

### HTTP status codes
- **200:** OK.
- **422:** Unprocessable Entity: the request was well-formed but the data is invalid.
- **404, 500:** not found, server error.
**Why it matters:** clients can react to the code without parsing text.

### JSON
**Definition:** the text format for structured data used in requests and responses: `{"gsm": 180}`.

### FastAPI
**Definition:** a Python web framework that uses type hints to validate inputs, convert data and generate interactive documentation automatically (`/docs`).

### Pydantic validation
**Definition:** a library that checks data against a typed model. Wrong type, missing field, out of range or not in the allowed list: rejected with a clear message.
**Why it matters:** the model never sees an input it wasn't trained for.

### `Literal` and `Field` constraints
`Literal["a", "b"]` allows only those values. `Field(ge=, le=, gt=)` sets numeric bounds.

### Versioned endpoints (`/v1/`)
**Definition:** putting a version in the URL so you can change the API later (`/v2/`) without breaking existing clients.

### Health check
**Definition:** an endpoint that just says "I'm alive", used by containers, load balancers and CI.

### Caching a model in memory
**Definition:** load once, reuse for every request. `functools.lru_cache` does it in one line.

### Serialised models (joblib vs JSON trees)
The offcut model is served from exported JSON trees (no scikit-learn needed to predict). The stall model is served from a joblib file, which needs the same scikit-learn version that saved it. That's one reason the Docker image pins versions (part 10).

### ASGI and uvicorn
**Definition:** uvicorn is the web server that runs a FastAPI app. ASGI is the interface between them.

### pytest and TestClient
- **pytest:** Python's most common test runner. Any function named `test_*` with `assert` statements is a test.
- **TestClient:** sends requests to the app in memory, so tests are fast and need no running server.

### Unit vs integration tests
- **Unit:** one function on its own (BM25 scores, PSI, grade codes).
- **Integration:** several parts together (an HTTP request through validation, the service and the model).
The API tests are integration tests; most of `test_offcut.py` and `test_stock.py` are unit tests.

---

## 4. The real results, and how to read them

- **Endpoints:** `/health`, `/v1/offcuts/forecast`, `/v1/stock/stall-risk`, `/v1/regulation/search`.
- **Bad inputs return 422**, tested for an unknown garment, a gsm of 5 and a launch month of 13.

**The test count.** The README and summaries say **22** tests. The test files in the repo today contain **23**: 6 in `test_api.py`, 12 in `test_offcut.py`, 5 in `test_stock.py`. pytest's cache lists the same 23 node IDs, and `pytest --collect-only` collects 23. The git history explains it: `test_browser_stall_model_matches_sklearn` was added in commit `c2d6285` ("Interactive stall-risk tool", 23:24 on 9 Nov 2026), after the CI commits (`1bc9206`, `cbd22be`, 22:40). So 22 was right for the first CI run, and 23 is right now. I haven't seen the CI log for the later commit, so check the Actions page shows it green, then report "23 automated tests".

---

## 5. What went wrong or surprised me, and what it taught me

- **Validation in two places, on purpose.** Pydantic enforces ranges at the edge; `service.validate_order` enforces the same ranges inside, because the agent (part 08) calls the service directly without going through the API. Defence in depth, with one shared set of numbers from the part 01 contract.
- **The float32 lesson still applies.** The forecast endpoint runs the exported JSON trees, so the parity tests from part 01 protect the API's answers too.
- **Labels in responses.** Adding `"data": "simulated cutting runs"` and the "not legal advice" note to responses felt small, but it means the honesty travels with the number wherever it ends up.
- **Calibration and bands.** Part 06 showed the stall probabilities run high on later launches. The bands are a reasonable interface, but I'd revisit the 0.15 and 0.4 cut-offs after recalibration (part 15).

---

## 6. Honest limits

- **Prototype, not deployed to a public cloud** (Azure deploy is part 17, planned). It runs locally and inside Docker in CI.
- No authentication, rate limiting or request logging.
- The stall endpoint expects the caller to compute the ten early-life features; there's no endpoint that takes raw weekly sales.
- No batch endpoint; one order or line per request.
- Models are loaded from files baked into the image, so updating a model means rebuilding.
- Data labels as before: offcut model simulated, stall model real open retail data (not fashion, not a customer).

---

## 7. How to run it yourself

```bash
make offcuts && make stall     # the API needs models/pre_marker_model.json and models/stall_model.joblib
make api                       # uvicorn api.main:app --app-dir src --reload
# open http://127.0.0.1:8000/docs
make test                      # python -m pytest -q tests
```

Try a request:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/offcuts/forecast -H 'Content-Type: application/json' \
  -d '{"garment":"tee","fibre":"cotton","size_mix":"standard","fabric_width_m":1.8,"gsm":180,"fabric_metres":18000}'
curl -s "http://127.0.0.1:8000/v1/regulation/search?q=when%20does%20the%20destruction%20ban%20start"
```

---

## 8. Glossary

- **API:** a defined interface for programs to request things from each other.
- **REST:** web API style using URLs and HTTP methods.
- **Endpoint:** one URL plus method, such as POST /v1/offcuts/forecast.
- **GET / POST:** read with parameters / send a body.
- **HTTP 422:** request understood but data invalid.
- **JSON:** text format for structured data.
- **FastAPI:** Python web framework built on type hints.
- **Pydantic:** library for typed data validation.
- **`Literal`:** a type allowing only listed values.
- **`Field` bounds:** numeric limits (ge, le, gt).
- **Health check:** an "I'm alive" endpoint.
- **Versioned endpoint:** `/v1/` in the path for future changes.
- **`lru_cache`:** caches a function's result in memory.
- **joblib:** saves Python objects such as scikit-learn models.
- **uvicorn:** the server that runs the FastAPI app.
- **ASGI:** the interface between Python web servers and apps.
- **pytest:** Python test runner.
- **TestClient:** in-process HTTP client for testing FastAPI apps.
- **Unit test / integration test:** one function / several parts together.
- **Defence in depth:** the same safety check in more than one layer.
