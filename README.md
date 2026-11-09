# Thread Futures

[![ci](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml/badge.svg)](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml)

**Software for fashion teams: forecast fabric offcuts before cutting, spot lines likely to go unsold, and keep a clearer record of what happens to stock.**

Website: [threadfutures.com](https://threadfutures.com) · Founder: Cathy Liu ([LinkedIn](https://www.linkedin.com/in/cathyqliu))

> **Honest scope.** This is an early-stage independent project, not a live product. The offcut forecast is trained on **simulated** cutting runs. The unsold-stock analytics run on **real open retail data** ([UCI Online Retail II](https://doi.org/10.24432/C5CG6D), a UK online retailer, CC BY 4.0), which is not fashion data and not a customer's. Routing and evidence workflows are planned, not built.

## Why

Two kinds of textile waste are decided at different times:

- **Offcuts at production.** Cutting plans report planned efficiency, but cutting rooms lose more fabric than the plan shows. Knowing the likely weight before the run makes it easier to plan a buyer for it.
- **Unsold stock after the season.** From 19 July 2026, large companies may no longer destroy unsold clothing and footwear in the EU, outside limited exceptions, and must disclose what they discard ([Regulation (EU) 2024/1781](https://eur-lex.europa.eu/eli/reg/2024/1781/oj), Articles 24–25). Spotting lines that are about to stop selling gives a brand time to act.

## What's in the repository

| # | Part | What it does | Tools | Result |
|---|---|---|---|---|
| 1 | [Offcut forecasting](src/offcut) | P10/P50/P90 offcut forecast per cutting run; runs in the browser | Python, scikit-learn, pandas, JavaScript | **8.8%** mean error vs 20.3% for the 15% rule of thumb, 1,600 held-out *simulated* runs |
| 2 | [Analytics engineering](dbt) | Bronze (Parquet) → silver → gold models of 1.06m sales lines | dbt Core, DuckDB, SQL | **28** dbt data tests passing, including revenue reconciliation between layers |
| 3 | [Merchandising analytics](dbt/models/marts/mart_sku_health.sql) | Selling / slowing / stopped status, ABC/XYZ, velocity, markdown depth, return rate | SQL, dbt | **4,707** SKUs classified |
| 4 | [Stall-risk model](src/stock/train_stall.py) | From a line's first 12 weeks, predicts whether sales collapse in weeks 12–25 | scikit-learn, MLflow | ROC AUC **0.81** vs 0.52 for a "sales halved" rule on 423 later launches; top-20% precision 34% vs an 11% base rate |
| 5 | [Experimentation](src/stock/experiment.py) | Do markdowns clear stock? How big must a routing pilot be? | statsmodels, SciPy | Stacked difference-in-differences (768 marked-down SKUs, 5 matched controls each). A placebo test found a pre-trend, so the +125% estimate is an upper bound. Pilot power analysis: **64** batches per arm |
| 6 | [Model monitoring](src/stock/monitor.py) | Accuracy, calibration and data drift per launch quarter | SciPy, pandas | Flagged over-prediction on 2011 launches (14% predicted vs 1.7% actual) and PSI drift. [Report](site/reports/monitoring.html) |
| 7 | [Regulation search](src/regsearch/search.py) | Finds the article of EU law that answers a question; checks citations | BM25, TF-IDF (scikit-learn), LLM API | Right article in the top 3 for **21 of 22** test questions (hit@1 73%, MRR 0.83) |
| 8 | [Purchase-order agent](src/offcut/agent.py) | Reads a messy order note, states assumptions, calls tested tools | LLM API with tool use | The model never does the arithmetic |
| 9 | [API](src/api/main.py) | Offcut forecast, stall risk and regulation search endpoints | FastAPI, Pydantic, Docker | **22** pytest tests; GitHub Actions runs them, builds the Docker image and calls the API on every push |

Every number above is produced by the code in this repo and saved under [`models/`](models).

### Things the checks caught

- **dbt tests** found 23 returns logged before an item's first recorded sale (stock sold before the data starts). The model now leaves weeks-since-launch empty for those rows.
- **The browser export** of the offcut model rounded split thresholds, but scikit-learn compares inputs as 32-bit floats. For edge inputs (e.g. a 1.57 m roll) the browser took a different branch. Thresholds are now exported at full precision and inputs cast with `Math.fround`, and a test checks the export matches scikit-learn.
- **The placebo test** showed marked-down lines were already gaining before the markdown, so the difference-in-differences estimate is reported as an upper bound, not a clean effect.
- **Monitoring** showed the stall model is well ranked but over-confident for spring launches heading into the Christmas season, which a seasonal feature or recalibration would need to fix.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make offcuts      # simulate 8,000 cutting runs, train, evaluate
make stock        # download retail data, dbt build, stall model, experiment, monitoring, regulation search
make test         # 22 tests
make site         # copy the browser model into site/
make api          # http://127.0.0.1:8000/docs
make mlflow-ui    # browse tracked runs
```

Docker (API only):

```bash
docker build -t threadfutures-api . && docker run -p 8000:8000 threadfutures-api
```

The purchase-order agent and generated regulation answers are optional and need an LLM API key: copy `.env.example` to `.env`, then `pip install -r requirements-llm.txt`.

## Layout

```
site/            static website (Netlify publishes this folder)
src/offcut/      offcut simulation, pipeline, quantile model, browser export, agent
src/stock/       retail ingest, stall-risk model, experiment, monitoring, site export
src/regsearch/   regulation retrieval, evaluation, cited answers
src/api/         FastAPI service
dbt/             dbt project (staging, intermediate, marts, semantic layer, tests)
data/            regulation text, evaluation questions, sample recyclers (raw data is downloaded)
models/          trained models and saved metrics
tests/           pytest suite
```

## Data and licences

- Retail data: Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D (CC BY 4.0). Downloaded by `make retail`, not stored in the repo.
- Regulation text: Regulation (EU) 2024/1781, © European Union, https://eur-lex.europa.eu, reused under Commission Decision 2011/833/EU. General information, not legal advice.
- Offcut data is simulated from first principles and calibrated to published industry ranges.
