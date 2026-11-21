# 5. Platform

How the models are served and checked: the FastAPI service (Part 09) and the CI and Docker build that tests it on every push to main and every pull request (Part 10).

Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. The code described here is earlier, exploratory technical work, not the product. Nothing new is built during customer discovery (to early 2027), and any early pilot runs by hand (spreadsheet and email). See [ARCHITECTURE.md](ARCHITECTURE.md) for how the parts fit together.

Each part starts with a header block (discipline, methodology, tools, status), then the short part note, then the full step-by-step guide.

## Contents

- [Part 09: API service](#part-09-api-service)
  - [Part 09 step by step](#part-09-step-by-step)
- [Part 10: CI and Docker build](#part-10-ci-and-docker-build)
  - [Part 10 step by step](#part-10-step-by-step)

---

## Part 09: API service

**Discipline:** AI Engineering / Machine Learning (primary / secondary)  
**Methodology:** `src/api/main.py` is a FastAPI app with `/health` and three versioned endpoints (offcut forecast, stall risk, regulation search). Pydantic models with `Literal` and `Field` bounds return 422 on bad input, and models load once through `lru_cache`. `tests/test_api.py` exercises it with `TestClient`.  
**Tools:** FastAPI, Pydantic, uvicorn, joblib, pytest  
**Status:** Live: maintenance only.

**Build state:** Built · **Data label:** Prototype  

### In one line
Puts the offcut forecast, stall risk and regulation search behind one web service.

### Why it matters
Turns notebooks into something other systems can call. Part of the earlier, exploratory technical work, not the product; if the batch report prototype (part 18) is ever built, it would use the same FastAPI, validation and testing approach.

### Data
Models saved by parts 1 and 4; regulation text from part 7.

### Method
FastAPI with Pydantic input validation. Endpoints: /health, /v1/offcuts/forecast, /v1/stock/stall-risk, /v1/regulation/search. Automated tests with pytest and TestClient.

### Tools
FastAPI, Pydantic, uvicorn, pytest, httpx

### Result
23 pytest tests (6 API, 12 offcut, 5 stock analytics) passing, confirmed in the CI run of 17 Nov 2026; bad inputs return 422.

### Honest limits
Not deployed to a public cloud yet (part 17).

### Where it lives
src/api/main.py, tests/

### Part 09 step by step

**Build state:** Built · **Data label:** Prototype. Offcut forecast trained on SIMULATED runs; stall risk trained on REAL OPEN RETAIL DATA; regulation search over real EU law text.
**Code:** `src/api/main.py`; tests in `tests/test_api.py` (plus `tests/test_offcut.py`, `tests/test_stock.py`)
**Numbers from:** the test files and `.pytest_cache/v/cache/nodeids` (see section 4 on the test count)

---

#### 1. The question this stage answers

How do I turn three separate models (offcut forecast, stall risk, regulation search) into one service that any other system, website or colleague can call, safely?

A fashion brand cares because a model in a notebook helps nobody. A planning tool, an ERP or a dashboard needs to send a request and get a reliable answer back, and a bad request needs to fail clearly instead of returning a plausible wrong number.

---

#### 2. The pipeline, step by step

##### Step 1. Create the app

```python
app = FastAPI(title="Thread Futures API", version="0.1.0",
              description="Prototype. Offcut forecasts are trained on simulated cutting runs; "
                          "stall risk is trained on open retail data (UCI Online Retail II).")
```

- One FastAPI application. The description carries the data labels, so anyone reading the auto-generated docs at `/docs` sees what the models are trained on.

##### Step 2. Define the inputs as Pydantic models

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

##### Step 3. Health check

```python
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- The simplest possible endpoint. Docker's `HEALTHCHECK` and the CI smoke test (part 10) call it to know the service is up.

##### Step 4. Offcut forecast endpoint

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

##### Step 5. Stall-risk endpoint

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

##### Step 6. Regulation search endpoint

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

##### Step 7. Test it with TestClient

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

#### 3. Concepts, from scratch

##### API
**Definition:** application programming interface. A defined way for one program to ask another for something.

##### REST and HTTP methods
**Definition:** a style of web API where resources have URLs and you act on them with HTTP methods.
- **GET:** read, no side effects, parameters in the URL. Used for search.
- **POST:** send a body to be processed. Used for forecasts.
**Analogy:** GET is looking something up in a catalogue; POST is handing over a form.

##### HTTP status codes
- **200:** OK.
- **422:** Unprocessable Entity: the request was well-formed but the data is invalid.
- **404, 500:** not found, server error.
**Why it matters:** clients can react to the code without parsing text.

##### JSON
**Definition:** the text format for structured data used in requests and responses: `{"gsm": 180}`.

##### FastAPI
**Definition:** a Python web framework that uses type hints to validate inputs, convert data and generate interactive documentation automatically (`/docs`).

##### Pydantic validation
**Definition:** a library that checks data against a typed model. Wrong type, missing field, out of range or not in the allowed list: rejected with a clear message.
**Why it matters:** the model never sees an input it wasn't trained for.

##### `Literal` and `Field` constraints
`Literal["a", "b"]` allows only those values. `Field(ge=, le=, gt=)` sets numeric bounds.

##### Versioned endpoints (`/v1/`)
**Definition:** putting a version in the URL so you can change the API later (`/v2/`) without breaking existing clients.

##### Health check
**Definition:** an endpoint that just says "I'm alive", used by containers, load balancers and CI.

##### Caching a model in memory
**Definition:** load once, reuse for every request. `functools.lru_cache` does it in one line.

##### Serialised models (joblib vs JSON trees)
The offcut model is served from exported JSON trees (no scikit-learn needed to predict). The stall model is served from a joblib file, which needs the same scikit-learn version that saved it. That's one reason the Docker image pins versions (part 10).

##### ASGI and uvicorn
**Definition:** uvicorn is the web server that runs a FastAPI app. ASGI is the interface between them.

##### pytest and TestClient
- **pytest:** Python's most common test runner. Any function named `test_*` with `assert` statements is a test.
- **TestClient:** sends requests to the app in memory, so tests are fast and need no running server.

##### Unit vs integration tests
- **Unit:** one function on its own (BM25 scores, PSI, grade codes).
- **Integration:** several parts together (an HTTP request through validation, the service and the model).
The API tests are integration tests; most of `test_offcut.py` and `test_stock.py` are unit tests.

---

#### 4. The real results, and how to read them

- **Endpoints:** `/health`, `/v1/offcuts/forecast`, `/v1/stock/stall-risk`, `/v1/regulation/search`.
- **Bad inputs return 422**, tested for an unknown garment, a gsm of 5 and a launch month of 13.

**The test count.** The README and summaries once said **22** tests (now corrected to 23). The test files in the repo today contain **23**: 6 in `test_api.py`, 12 in `test_offcut.py`, 5 in `test_stock.py`. pytest's cache lists the same 23 node IDs, and `pytest --collect-only` collects 23. The git history explains it: `test_browser_stall_model_matches_sklearn` was added in commit `c2d6285` ("Interactive stall-risk tool", 23:24 on 9 Nov 2026), after the CI commits (`1bc9206`, `cbd22be`, 22:40). So 22 was right for the first CI run, and 23 is right now. Checked on 17 Nov 2026: the CI log of the latest run on main reports "23 passed, 1 warning in 4.00s", so report "23 automated tests".

---

#### 5. What went wrong or surprised me, and what it taught me

- **Validation in two places, on purpose.** Pydantic enforces ranges at the edge; `service.validate_order` enforces the same ranges inside, because the agent (part 08) calls the service directly without going through the API. Defence in depth, with one shared set of numbers from the part 01 contract.
- **The float32 lesson still applies.** The forecast endpoint runs the exported JSON trees, so the parity tests from part 01 protect the API's answers too.
- **Labels in responses.** Adding `"data": "simulated cutting runs"` and the "not legal advice" note to responses felt small, but it means the honesty travels with the number wherever it ends up.
- **Calibration and bands.** Part 06 showed the stall probabilities run high on later launches. The bands are a reasonable interface, but I'd revisit the 0.15 and 0.4 cut-offs after recalibration (part 15).

---

#### 6. Honest limits

- **Prototype, not deployed to a public cloud** (Azure deploy is part 17, planned). It runs locally and inside Docker in CI.
- No authentication, rate limiting or request logging.
- The stall endpoint expects the caller to compute the ten early-life features; there's no endpoint that takes raw weekly sales.
- No batch endpoint; one order or line per request.
- Models are loaded from files baked into the image, so updating a model means rebuilding.
- Data labels as before: offcut model simulated, stall model real open retail data (not fashion, not a customer).

---

#### 7. How to run it yourself

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

#### 8. Glossary

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

---

## Part 10: CI and Docker build

**Discipline:** AI Engineering / Data Engineering (primary / secondary)  
**Methodology:** `.github/workflows/ci.yml` runs a test job (Python 3.12, pinned dependencies, pytest) and then a Docker job (`needs: test`) that builds the image, starts it, polls `/health` and calls the forecast endpoint as a smoke test. The `Dockerfile` uses `python:3.12-slim`, copies only `src/` and the models and data it needs, and runs as a non-root user with a `HEALTHCHECK`.  
**Tools:** GitHub Actions, Docker, pytest, Make  
**Status:** Live: maintenance only.

**Build state:** Built · **Data label:** Built 9 Nov 2026  

### In one line
On every push to main and every pull request, GitHub Actions runs the tests, builds the Docker image and calls the running API.

### Why it matters
Shows the work runs anywhere, not just on one laptop. Part of the earlier, exploratory technical work, not the product; if the batch report prototype (part 18) is ever built, it would be tested and built the same way.

### Data
n/a

### Method
Two jobs: test (install pinned dependencies, run pytest) and docker (docker build, docker run, poll /health, POST a real forecast request). Badge on the README.

### Tools
GitHub Actions, Docker, pytest, curl

### Result
First run passed on 9 Nov 2026: tests green, image built, API answered a forecast request. Latest check, 17 Nov 2026: the five most recent runs are green; the log shows 23 tests passed and the container answered the forecast request.

### Honest limits
Image is built in CI but not yet pushed to a registry.

### Where it lives
.github/workflows/ci.yml, Dockerfile

### Part 10 step by step

**Build state:** Built 9 Nov 2026 · **Data label:** n/a (infrastructure)
**Code:** `.github/workflows/ci.yml`, `Dockerfile`, `.dockerignore`, `requirements-api.txt`, `requirements.txt`, `Makefile`
**Numbers from:** the workflow and Dockerfile themselves, and the git history

---

#### 1. The question this stage answers

Does the project run anywhere, not just on my laptop, and does every change get checked automatically?

A fashion brand, a programme or an investor's technical adviser cares because a model that only works on one machine can't be handed over, deployed or trusted. Continuous integration proves on every push to main and every pull request that the tests pass, the service builds into a container, and the container actually answers a real request.

---

#### 2. The pipeline, step by step

##### Step 1. Pin the dependencies

**Where:** `requirements-api.txt` (serving only) and `requirements.txt` (everything)

```text
# Serving only (Docker image)
numpy==2.5.4
pandas==3.1.1
scikit-learn==1.9.1
joblib==1.6.0
fastapi==0.162.2
uvicorn==0.54.0
pydantic==2.14.3
```

- Every package has an exact version (`==`).
- `requirements.txt` starts with `-r requirements-api.txt` and adds the analysis tools (SciPy, DuckDB, dbt, statsmodels, MLflow, pytest and so on).

**Why:** the stall model is a joblib file, which needs the same scikit-learn version that saved it. Pinned versions mean CI, Docker and my laptop all run the same code. Splitting serving from analysis keeps the image small: the API doesn't need dbt or MLflow.

##### Step 2. Write the Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/ src/
COPY models/pre_marker_model.json models/stall_model.joblib models/
COPY data/regulation/ data/regulation/
COPY data/recyclers_sample.json data/
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Line by line:

- `FROM python:3.12-slim`: start from an official, small Python 3.12 image.
- `WORKDIR /app`: all following paths are inside `/app`.
- `ENV ...`: don't write `.pyc` files, don't buffer logs (so they appear immediately), and put `src/` on the Python path so `import api.main` works.
- `COPY requirements-api.txt .` then `RUN pip install ...`: install dependencies **before** copying the code. Docker caches each step as a layer, so changing code doesn't reinstall packages.
- `COPY src/ ...`, `COPY models/...`, `COPY data/...`: only what the API needs: the code, the two model files, the regulation text and the sample recyclers.
- `useradd` and `USER app`: run as a normal user, not root. If something goes wrong, the process has fewer permissions.
- `EXPOSE 8000`: documents the port.
- `HEALTHCHECK`: Docker periodically calls `/health` from inside the container and marks it unhealthy if it fails. It uses Python's standard library, so no extra tools like curl are needed in the image.
- `CMD`: start uvicorn listening on all interfaces (`0.0.0.0`), so traffic from outside the container reaches it.

##### Step 3. Keep the build context small

**Where:** `.dockerignore`

It excludes raw and staged data, the DuckDB warehouse, the MLflow database, the dbt project, the website, docs, tests, `.git` and any `.env` files.

**Why:** smaller, faster builds, and secrets can never be copied into the image by accident.

##### Step 4. The CI workflow: triggers

**Where:** `.github/workflows/ci.yml`

```yaml
name: ci
on:
  push: {branches: [main]}
  pull_request:
```

- Run on every push to `main` and on every pull request.

##### Step 5. Job 1: run the tests

```yaml
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12", cache: pip}
      - run: pip install -r requirements-api.txt scipy==1.18.1 statsmodels==0.15.0 duckdb==2.0.0 httpx==0.28.1 pytest==9.2.0 matplotlib==3.11.2
      - run: PYTHONPATH=src python -m pytest -q tests
```

- A fresh Ubuntu virtual machine from GitHub.
- Check out the code, install Python 3.12 with a pip cache (faster repeat runs).
- Install the serving packages plus a few extras: SciPy and DuckDB (the monitoring and feature modules that tests import need them), httpx (for TestClient) and pytest. statsmodels and Matplotlib are installed too, although no test imports them directly, so they could probably be dropped. Not dbt or MLflow, which no test needs.
- Run the whole suite.

**Why a subset:** quicker CI, and it proves the tests don't secretly depend on heavy tools.

##### Step 6. Job 2: build and smoke-test the container

```yaml
  docker:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t threadfutures-api .
      - run: |
          docker run -d -p 8000:8000 --name api threadfutures-api
          for i in $(seq 1 20); do curl -fs http://127.0.0.1:8000/health && break; sleep 1; done
          curl -fs -X POST http://127.0.0.1:8000/v1/offcuts/forecast -H 'Content-Type: application/json' \
            -d '{"garment":"tee","fibre":"cotton","size_mix":"standard","fabric_width_m":1.8,"gsm":180,"fabric_metres":18000}'
```

- `needs: test`: only runs if the tests passed. No point building a broken app.
- `docker build`: build the image from the Dockerfile.
- `docker run -d -p 8000:8000`: start it in the background, mapping port 8000.
- The `for` loop: try `/health` up to 20 times, one second apart, and stop as soon as it answers. The app takes a moment to start.
- Final `curl -fs -X POST ...`: send a real forecast request. `-f` makes curl fail on an HTTP error (like 422 or 500), and a failing command fails the step.

**Why:** a container that builds isn't the same as a container that works. This proves the image starts, loads its models and returns a forecast.

**A subtle point worth knowing:** if `/health` never answers, the loop itself doesn't fail; it just finishes. The step still fails, because the final POST would fail. If I wanted a clearer error message, I'd add an explicit check after the loop.

##### Step 7. Show the status

The README has a CI badge at the top, linked to the Actions page, so anyone can see whether the latest build passed.

---

#### 3. Concepts, from scratch

##### Continuous integration (CI)
**Definition:** automatically building and testing every change as soon as it's pushed.
**Analogy:** a smoke alarm. It doesn't stop fires, but it tells you immediately.
**Why it matters:** problems are found minutes after they're introduced, not weeks later.

##### Continuous delivery / deployment (CD)
**Definition:** automatically preparing (delivery) or releasing (deployment) every change that passes CI.
**Here:** not yet. The image is built but not pushed to a registry or deployed (part 17).

##### GitHub Actions: workflow, job, step, runner
- **Workflow:** a YAML file in `.github/workflows/` describing automation.
- **Trigger (`on`):** what starts it (push, pull request).
- **Job:** a group of steps that runs on one machine. Jobs run in parallel unless one `needs` another.
- **Step:** one command (`run`) or reusable action (`uses`).
- **Runner:** the machine, here `ubuntu-latest`.

##### pytest in CI
Same tests as locally, run on a clean machine. If a test only passes on my laptop because of a file lying around, CI will catch it.

##### Pinned dependencies
**Definition:** exact package versions.
**Why it matters:** "works on my machine" usually means "has different versions on my machine".

##### Docker image vs container
- **Image:** a packaged, read-only template: an operating system layer, Python, packages, code and model files.
- **Container:** a running instance of an image.
**Analogy:** the image is a recipe card plus all the ingredients sealed in a box; the container is the dish being cooked.

##### Dockerfile and layers
**Definition:** a Dockerfile is the instructions for building an image. Each instruction makes a layer, and unchanged layers are reused from cache.
**Why order matters:** dependencies first, code last, so code changes rebuild in seconds.

##### Slim base image
A smaller Debian-based Python image with fewer system packages. Smaller download, smaller attack surface.

##### Non-root user
Running as an unprivileged user limits damage if the app is compromised. A standard container security practice.

##### HEALTHCHECK, EXPOSE, port mapping
- **HEALTHCHECK:** Docker's own liveness check.
- **EXPOSE:** documents the port the app uses.
- **`-p 8000:8000`:** connects a port on the host to a port in the container.

##### `.dockerignore`
Like `.gitignore`, but for what gets sent to Docker when building. Keeps images small and secrets out.

##### Smoke test
**Definition:** a quick whole-system check that the system basically works ("does it turn on without smoke?"). Not a full test suite.

##### Container registry
**Definition:** a store for images (GitHub Container Registry, Docker Hub, Azure Container Registry), so other machines can pull and run them. Not used yet.

##### Secrets in CI
Keys belong in the CI platform's encrypted secrets, never in the workflow file. This workflow needs none, because nothing it tests calls an LLM API.

---

#### 4. The real results, and how to read them

- **Per the summary and the commit history:** the first CI run passed on 9 Nov 2026: tests green, image built, API answered the forecast request. The commit after adding CI is titled "Docker build now verified in CI: update site and README" (`cbd22be`).
- **Two jobs:** `test` (pytest) then `docker` (build, run, poll `/health`, POST a forecast).
- **Tests run:** 22 at the time of the first CI run. The repo now has 23 (one more parity test was added in a later commit, `c2d6285`; see part 09). Checked on 17 Nov 2026: the latest run on main reports "23 passed", and the smoke test returned `{"status":"ok"}` and a forecast with P50 960.7 kg (simulated data).
- **Image contents:** the API code, two model files, the regulation corpus and the sample recycler list. No raw data, warehouse, tests or secrets.

---

#### 5. What went wrong or surprised me, and what it taught me

##### Docker verified only via CI
I don't have Docker on my laptop, so I've never run the image locally. Instead, CI builds it and calls it on every push to main and every pull request. That's honest and it works, but it has a cost: if the build breaks, I debug by pushing and reading logs, which is slow. I'd say that plainly rather than imply I run containers every day.

**What it taught me:** CI can be a substitute for local tooling, and it's arguably a better proof, because it runs on a clean machine every time.

##### The pip install line in CI duplicates versions
The test job lists versions (like `scipy==1.18.1`) that also appear in `requirements.txt`. If one is updated and not the other, they drift. A cleaner option would be a `requirements-test.txt` used by both.

##### A naming mismatch spotted while writing this guide
A test's skip message says "run `make train` first", but the Makefile target is `make offcuts`. Harmless, but it's the kind of small thing a reviewer notices.

---

#### 6. Honest limits

- The image is built in CI but **not pushed to a registry** and **not deployed** (part 17, planned).
- Docker has only been verified in CI, not run locally.
- No security scanning of the image, no dependency update automation.
- CI doesn't run `dbt build` or retrain models, because those need the downloaded retail data. It tests the saved models and code.
- The smoke test checks one forecast request, not stall risk or search.
- No linting or type checking step.

---

#### 7. How to run it yourself

CI runs automatically on push. To run the same test step locally:

```bash
pip install -r requirements.txt
make test                       # PYTHONPATH=src python -m pytest -q tests
```

If you have Docker:

```bash
docker build -t threadfutures-api . && docker run -p 8000:8000 threadfutures-api
curl -fs http://127.0.0.1:8000/health
```

View CI runs at github.com/catliugit/ThreadFutures/actions (the badge at the top of the README links there).

---

#### 8. Glossary

- **CI:** continuous integration, automatic build and test on every change.
- **CD:** continuous delivery or deployment.
- **GitHub Actions:** GitHub's automation service.
- **Workflow:** a YAML automation file.
- **Trigger:** event that starts a workflow.
- **Job:** steps run on one machine.
- **Step:** one command or action.
- **Runner:** the machine running a job.
- **`needs`:** makes one job wait for another.
- **Pinned dependency:** an exact package version.
- **Docker image:** packaged template of an app and its environment.
- **Container:** a running image.
- **Dockerfile:** instructions to build an image.
- **Layer cache:** reusing unchanged build steps.
- **Slim image:** a smaller base image.
- **Non-root user:** an unprivileged account inside the container.
- **HEALTHCHECK:** Docker's liveness probe.
- **EXPOSE / port mapping:** declared port / host-to-container port link.
- **`.dockerignore`:** files excluded from the build.
- **Smoke test:** quick whole-system "does it work at all" check.
- **Container registry:** a store for images.
- **CI badge:** a status image showing the latest build result.
- **Secret:** a credential stored encrypted, never in code.
