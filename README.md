# Thread Futures

[![ci](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml/badge.svg)](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml)

**Thread Futures: every unit a second life, and the proof.** Thread Futures is the trusted second-life desk for the stock nobody else will take: returns, damaged, broken size runs, old seasons and logo-heavy lines from brands selling into the EU. We give every unit a second life through vetted buyers and EU charities we fund to say yes, and hand the brand a file proving where all of it went.

**Status (12 Nov 2026):** the desk is planned and not operating; there are no customers yet. Validation interviews with brands, buyers and EU social-economy organisations start on 16 Nov 2026.

**What this repository is:** the founder's technical proof (Parts 1 to 10: models, data pipelines, regulation search, an API and CI), plus the upcoming **batch and destination file prototype** ([Part 18](docs/parts/18_batch_and_destination_file_prototype.md), planned for 16 to 19 Nov 2026). The built models are not the product and not a reason to buy; the product is the desk and the destination file.

- **How the desk works, per batch: Grade · Place · Prove.** *Grade:* real size breakdown, condition codes and fibre composition from the brand's tech packs. *Place,* in waste-hierarchy order: contracted buyers (brand anonymous; no destruction, no export as waste, channel limits, onward-destination reporting), then curated donation to vetted **EU** social-economy entities with transport paid, then a licensed waste operator only as a last resort. *Prove:* a destination file per batch, every unit and every step, kept 5 years, producible within 30 days, with rows ready for the Article 24 disclosure table. *Status:* **planned, not built**.
- **Stall-risk model (built, Part 4).** Scores a line from its first 12 weeks of sales; a possible optional intake ("flag the tail early so it's placed while it still has value"). Runs on **real open retail data, not fashion**.
- **Offcut Forecast (built, Part 1, parked).** An earlier idea: estimates the kg of fabric a cutting run will leave over. Trained on **simulated** cutting runs; parked as a possible later module, not part of the pitch.

**Why not just use ChatGPT?** Much of the software in this repo (Parts 3, 4 and 7 especially) could be reproduced by a brand analyst with ChatGPT, Claude or Copilot, which is why software isn't what we sell. A chatbot can draft a template; it can't contract buyers, grade goods, fund a charity's logistics, or create a charity's acceptance or a waste operator's statement after the fact. **Why not just call TK Maxx?** For clean stock, brands should; we handle the tail off-price won't take.

Website: [threadfutures.com](https://threadfutures.com) · Founder: Cathy Liu ([LinkedIn](https://www.linkedin.com/in/cathyqliu))

> **Honest scope.** This is an early-stage independent project, not a live product. The offcut forecast is trained on **simulated** cutting runs. The unsold-stock analytics run on **real open retail data** ([UCI Online Retail II](https://doi.org/10.24432/C5CG6D), a UK online retailer, CC BY 4.0), which is not fashion data and not a customer's. The desk, the destination file and the buyer and charity networks are planned, not built. General information, not legal advice.

## Why

Since 19 July 2026, large companies may not destroy unsold clothing and footwear in the EU, and "destruction" includes recycling and energy recovery unless one of the exceptions in Delegated Regulation (EU) 2026/296 applies ([Regulation (EU) 2024/1781](https://eur-lex.europa.eu/eli/reg/2024/1781/oj), Articles 24–25). Medium-sized companies follow from July 2030. The donation exception needs goods offered for at least 8 weeks to at least three suitable social-economy entities in the EU (or on the brand's own website) and not accepted; UK charities don't count. Evidence must be kept 5 years and provided within 30 days of a request. The disclosure duty already applies to large firms; the mandatory standard format (Implementing Regulation (EU) 2026/2) applies to financial years starting on or after 2 March 2027. Germany's fines (up to €100,000 per destruction breach) apply from 1 Nov 2026.

The easy stock already sells: off-price chains buy it directly. The tail (returns, damaged goods, odd sizes, old seasons) used to go to the shredder. Jobbers take it cheaply and can't say where it ends up; charities refuse 15–20% of what's offered because they can't pay to move or store it.

## What's in the repository

| # | Part | What it does | Tools | Result |
|---|---|---|---|---|
| 1 | [Offcut forecasting](src/offcut) | P10/P50/P90 offcut forecast per cutting run; runs in the browser | Python, scikit-learn, pandas, JavaScript | **8.8%** mean error vs 20.3% for the 15% rule of thumb, 1,600 held-out *simulated* runs |
| 2 | [Analytics engineering](dbt) | Bronze (Parquet) → silver → gold models of 1.06m sales lines | dbt Core, DuckDB, SQL | **22** dbt data tests passing, including revenue reconciliation between layers |
| 3 | [Merchandising analytics](dbt/models/marts/mart_sku_health.sql) | Selling / slowing / stopped status, ABC/XYZ, velocity, markdown depth, return rate | SQL, dbt | **4,707** SKUs classified |
| 4 | [Stall-risk model](src/stock/train_stall.py) | From a line's first 12 weeks, predicts whether sales collapse in weeks 12–25 | scikit-learn, MLflow | ROC AUC **0.81** vs 0.60 for a "sales halved" rule on 423 later launches; top-20% precision 32% vs an 11% base rate |
| 5 | [Experimentation](src/stock/experiment.py) | Do markdowns clear stock? How big must a routing pilot be? | statsmodels, SciPy | Stacked difference-in-differences (768 marked-down SKUs, 5 matched controls each). A placebo test found a pre-trend, so the +125% estimate is an upper bound. Pilot power analysis: **64** batches per arm |
| 6 | [Model monitoring](src/stock/monitor.py) | Accuracy, calibration and data drift per launch quarter | SciPy, pandas | Flagged over-prediction on 2011 launches (13.6% predicted vs 1.7% actual) and PSI drift. [Report](site/reports/monitoring.html) |
| 7 | [Regulation search](src/regsearch/search.py) | Finds the article of EU law that answers a question; checks citations | BM25, TF-IDF (scikit-learn), LLM API | Right article in the top 3 for **21 of 22** test questions (hit@1 73%, MRR 0.83) |
| 8 | [Purchase-order agent](src/offcut/agent.py) | Reads a messy order note, states assumptions, calls tested tools | LLM API with tool use | The model never does the arithmetic |
| 9 | [API](src/api/main.py) | Offcut forecast, stall risk and regulation search endpoints | FastAPI, Pydantic, Docker | **23** pytest tests; GitHub Actions runs them, builds the Docker image and calls the API on every push |
| 18 | [Batch and destination file prototype](docs/parts/18_batch_and_destination_file_prototype.md) (**planned, not built**) | Batch intake with grading fields, offer/refusal log for donation entities, buyer contract terms per placement, waste-operator statements, hash-chained append-only log, export of disclosure rows | SQL (SQLite/Postgres), FastAPI, pytest | Planned, Mon 16 – Thu 19 Nov 2026. Done when a demo season's batches produce a reproducible destination file and disclosure rows, with tests |

Every number above (Parts 1 to 9) is produced by the code in this repo and saved under [`models/`](models).

### Things the checks caught

- **dbt tests** found 23 returns logged before an item's first recorded sale (stock sold before the data starts). The model now leaves weeks-since-launch empty for those rows.
- **The browser export** of the offcut model rounded split thresholds, but scikit-learn compares inputs as 32-bit floats. For edge inputs (e.g. a 1.57 m roll) the browser took a different branch. Thresholds are now exported at full precision and inputs cast with `Math.fround`, and a test checks the export matches scikit-learn.
- **The placebo test** showed marked-down lines were already gaining before the markdown, so the difference-in-differences estimate is reported as an upper bound, not a clean effect.
- **Monitoring** showed the stall model is well ranked but over-confident for spring launches heading into the Christmas season, which a seasonal feature or recalibration would need to fix.

## Documentation

- [Part notes](docs/parts/00_index.md): one page per part (01 to 10 built, 11 to 18 planned; Part 18 is next).
- [Step-by-step guides](docs/guides/README.md): each built part explained from the ground up, with the code, every concept from scratch, results, what went wrong and how to run it.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make offcuts      # simulate 8,000 cutting runs, train, evaluate
make stock        # download retail data, dbt build, stall model, experiment, monitoring, regulation search
make test         # 23 tests
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
