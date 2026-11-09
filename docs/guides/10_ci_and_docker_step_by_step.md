# Part 10: CI and Docker build, step by step

**Status:** Built 9 Nov 2026 · **Data label:** n/a (infrastructure)
**Code:** `.github/workflows/ci.yml`, `Dockerfile`, `.dockerignore`, `requirements-api.txt`, `requirements.txt`, `Makefile`
**Numbers from:** the workflow and Dockerfile themselves, and the git history

---

## 1. The question this stage answers

Does the project run anywhere, not just on my laptop, and does every change get checked automatically?

A fashion brand (or anyone hiring me) cares because a model that only works on one machine can't be handed over, deployed or trusted. Continuous integration proves on every push that the tests pass, the service builds into a container, and the container actually answers a real request.

---

## 2. The pipeline, step by step

### Step 1. Pin the dependencies

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

### Step 2. Write the Dockerfile

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

### Step 3. Keep the build context small

**Where:** `.dockerignore`

It excludes raw and staged data, the DuckDB warehouse, the MLflow database, the dbt project, the website, docs, tests, `.git` and any `.env` files.

**Why:** smaller, faster builds, and secrets can never be copied into the image by accident.

### Step 4. The CI workflow: triggers

**Where:** `.github/workflows/ci.yml`

```yaml
name: ci
on:
  push: {branches: [main]}
  pull_request:
```

- Run on every push to `main` and on every pull request.

### Step 5. Job 1: run the tests

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

### Step 6. Job 2: build and smoke-test the container

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

### Step 7. Show the status

The README has a CI badge at the top, linked to the Actions page, so anyone can see whether the latest build passed.

---

## 3. Concepts, from scratch

### Continuous integration (CI)
**Definition:** automatically building and testing every change as soon as it's pushed.
**Analogy:** a smoke alarm. It doesn't stop fires, but it tells you immediately.
**Why it matters:** problems are found minutes after they're introduced, not weeks later.

### Continuous delivery / deployment (CD)
**Definition:** automatically preparing (delivery) or releasing (deployment) every change that passes CI.
**Here:** not yet. The image is built but not pushed to a registry or deployed (part 17).

### GitHub Actions: workflow, job, step, runner
- **Workflow:** a YAML file in `.github/workflows/` describing automation.
- **Trigger (`on`):** what starts it (push, pull request).
- **Job:** a group of steps that runs on one machine. Jobs run in parallel unless one `needs` another.
- **Step:** one command (`run`) or reusable action (`uses`).
- **Runner:** the machine, here `ubuntu-latest`.

### pytest in CI
Same tests as locally, run on a clean machine. If a test only passes on my laptop because of a file lying around, CI will catch it.

### Pinned dependencies
**Definition:** exact package versions.
**Why it matters:** "works on my machine" usually means "has different versions on my machine".

### Docker image vs container
- **Image:** a packaged, read-only template: an operating system layer, Python, packages, code and model files.
- **Container:** a running instance of an image.
**Analogy:** the image is a recipe card plus all the ingredients sealed in a box; the container is the dish being cooked.

### Dockerfile and layers
**Definition:** a Dockerfile is the instructions for building an image. Each instruction makes a layer, and unchanged layers are reused from cache.
**Why order matters:** dependencies first, code last, so code changes rebuild in seconds.

### Slim base image
A smaller Debian-based Python image with fewer system packages. Smaller download, smaller attack surface.

### Non-root user
Running as an unprivileged user limits damage if the app is compromised. A standard container security practice.

### HEALTHCHECK, EXPOSE, port mapping
- **HEALTHCHECK:** Docker's own liveness check.
- **EXPOSE:** documents the port the app uses.
- **`-p 8000:8000`:** connects a port on the host to a port in the container.

### `.dockerignore`
Like `.gitignore`, but for what gets sent to Docker when building. Keeps images small and secrets out.

### Smoke test
**Definition:** a quick end-to-end check that the system basically works ("does it turn on without smoke?"). Not a full test suite.

### Container registry
**Definition:** a store for images (GitHub Container Registry, Docker Hub, Azure Container Registry), so other machines can pull and run them. Not used yet.

### Secrets in CI
Keys belong in the CI platform's encrypted secrets, never in the workflow file. This workflow needs none, because nothing it tests calls an LLM API.

---

## 4. The real results, and how to read them

- **Per the summary and the commit history:** the first CI run passed on 9 Nov 2026: tests green, image built, API answered the forecast request. The commit after adding CI is titled "Docker build now verified in CI: update site and README" (`cbd22be`).
- **Two jobs:** `test` (pytest) then `docker` (build, run, poll `/health`, POST a forecast).
- **Tests run:** 22 at the time of the first CI run. The repo now has 23 (one more parity test was added in a later commit, `c2d6285`; see part 09). I haven't seen the CI log for the latest commit, so check the Actions page before quoting 23.
- **Image contents:** the API code, two model files, the regulation corpus and the sample recycler list. No raw data, warehouse, tests or secrets.

---

## 5. What went wrong or surprised me, and what it taught me

### Docker verified only via CI
I don't have Docker on my laptop, so I've never run the image locally. Instead, CI builds it and calls it on every push. That's honest and it works, but it has a cost: if the build breaks, I debug by pushing and reading logs, which is slow. I'd say that plainly rather than imply I run containers every day.

**What it taught me:** CI can be a substitute for local tooling, and it's arguably a better proof, because it runs on a clean machine every time.

### The pip install line in CI duplicates versions
The test job lists versions (like `scipy==1.18.1`) that also appear in `requirements.txt`. If one is updated and not the other, they drift. A cleaner option would be a `requirements-test.txt` used by both.

### A naming mismatch spotted while writing this guide
A test's skip message says "run `make train` first", but the Makefile target is `make offcuts`. Harmless, but it's the kind of small thing a reviewer notices.

---

## 6. Honest limits

- The image is built in CI but **not pushed to a registry** and **not deployed** (part 17, planned).
- Docker has only been verified in CI, not run locally.
- No security scanning of the image, no dependency update automation.
- CI doesn't run `dbt build` or retrain models, because those need the downloaded retail data. It tests the saved models and code.
- The smoke test checks one forecast request, not stall risk or search.
- No linting or type checking step.

---

## 7. How to run it yourself

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

## 8. Glossary

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
- **Smoke test:** quick end-to-end "does it work at all" check.
- **Container registry:** a store for images.
- **CI badge:** a status image showing the latest build result.
- **Secret:** a credential stored encrypted, never in code.
