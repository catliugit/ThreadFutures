# Thread Futures

[![ci](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml/badge.svg)](https://github.com/catliugit/ThreadFutures/actions/workflows/ci.yml)

**We find new homes for the clothes fashion brands can't sell.** Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. We sell to off-price retailers, resale platforms and stock buyers; donation and recycling are a last resort only. Since July 2026, large fashion brands selling into the EU, including UK brands, can no longer destroy unsold clothing (shredding for recycling counts). Current stock sells via off-price; returns, damaged items, broken size runs and older seasons go to liquidators with no visibility, and charities turn much of it down because they can't fund transport. Brands get four things: **money back** (we aim to return more than a liquidator pays; to be tested in pilots), **brand protection** (anonymous lots, limits on where stock is resold, de-labelling where needed), **compliance handled** (donation, legal recycling and a complete record for EU reporting) and, over time, **insight** into what didn't sell and why, so they produce less.

**Status (21 Nov 2026):** pre-revenue and not incorporated, with no customers, pilots or signed partners. Started in November 2026. The stage is customer discovery, not building: contacting brands, warehouses (3PLs), buyers and charities, with the first interviews booking now. The go / pivot / stop decision is due on Fri 26 Feb 2027; nothing new is built before then, and any early pilot runs by hand (spreadsheet and email). Listed in the Barclays Eagle Labs Demo Directory, with NatWest Digital Boost mentoring calls booked, and on YC Co-Founder Matching. Building solo; recruiting a commercial co-founder. **Go-to-market:** mid-size warehouses (3PLs) first, as partners and the source of brand introductions; the brand (its operations or merchandising lead) is the paying customer. Direct brand outreach runs in parallel. The clickable prototype is a mock-up with example data.

**What this repository is:** earlier, exploratory technical work (Parts 1 to 10: models, data pipelines, regulation search, an API and CI). The built models are not the product and not a reason to buy. The offcut forecast (Part 1) and the purchase-order agent (Part 8) are **earlier exploratory work for a previous idea (garment factories), not the product**; the product is the service itself (selling brands' unsold stock, with donation or recycling only as a last resort) and the report it produces. The **batch record prototype** ([Part 18](docs/6_planned.md#part-18-batch-report-prototype)) is planned, not built, and is not being built before the 26 Feb 2027 decision; it would be built only if a hand-run pilot shows it is needed.

- **How it works, per batch.** 1) The brand sends us a list of what it can't sell: returns, damaged items, old seasons. 2) A partner warehouse checks every item: condition and size (fibre from the brand's tech packs). 3) We sell what we can to off-price stores, resale sites and stock buyers; the brand's name stays hidden, and buyers sign no-destroy, resale-limit and onward-reporting terms. 4) What doesn't sell goes to EU charities that need it; we pay the transport. 5) Damaged items go to a licensed recycler under the correct legal exception. 6) The brand gets its money (minus our share) and a report of where every item went: every unit and every handover, kept 5 years, producible within 30 days, with rows ready for the Article 24 disclosure table. We coordinate and keep the record; partners do the physical work; the brand keeps ownership of the stock until it is sold. Pricing is a hypothesis to test: the first pilot batch is free to the brand (no set-up fee, no commission; logistics passed through at cost) in return for a written case study, a testimonial, real before/after numbers and two introductions; after a successful pilot, a season subscription plus commission. *Status:* **planned, not built**; any early pilot would run by hand.
- **Stall-risk model (built, Part 4).** Scores a line from its first 12 weeks of sales; an optional later idea (it could flag the tail early, while the stock still has value), not being developed before 26 Feb 2027. Runs on **real open retail data, not fashion**.
- **Offcut Forecast (built, Part 1, parked).** Earlier exploratory work for a previous idea (garment factories), not the product: estimates the kg of fabric a cutting run will leave over. Trained on **simulated** cutting runs; parked as a possible later module, not part of the pitch.

**Why not just use ChatGPT?** Much of the software in this repo (Parts 3, 4 and 7 especially) could be reproduced by a brand analyst with ChatGPT, Claude or Copilot, which is why software isn't what we sell. A chatbot can draft a template; it can't contract buyers, check goods, fund a charity's logistics, or create a charity's acceptance or a waste operator's statement after the fact. **Why not just call TK Maxx?** For clean stock, brands should; we handle the tail off-price won't take.

Website: [threadfutures.com](https://threadfutures.com) · Building Thread Futures: Cathy Liu ([LinkedIn](https://www.linkedin.com/in/cathyqliu))

> **Honest scope.** This is an early-stage independent project, not a live product. The offcut forecast is trained on **simulated** cutting runs. The unsold-stock analytics run on **real open retail data** ([UCI Online Retail II](https://doi.org/10.24432/C5CG6D), a UK online retailer, CC BY 4.0), which is not fashion data and not a customer's. The service, the batch report and the buyer and charity networks are planned, not built. General information, not legal advice.

## Why

Since 19 July 2026, large companies may not destroy unsold clothing and footwear in the EU, and "destruction" includes recycling and energy recovery unless one of the exceptions in Delegated Regulation (EU) 2026/296 applies ([Regulation (EU) 2024/1781](https://eur-lex.europa.eu/eli/reg/2024/1781/oj), Articles 24–25). Medium-sized companies follow from July 2030. The donation exception needs goods offered for at least 8 weeks to at least three suitable social-economy entities in the EU (or on the brand's own website) and not accepted; UK charities don't count. Evidence must be kept 5 years and provided within 30 days of a request. The disclosure duty already applies to large firms; the mandatory standard format (Implementing Regulation (EU) 2026/2) applies to financial years starting on or after 2 March 2027. Germany's fines (up to €100,000 per destruction breach) apply from 1 Nov 2026.

The easy stock already sells: off-price chains buy it directly. The tail (returns, damaged goods, odd sizes, old seasons) used to go to the shredder. Jobbers take it cheaply and can't say where it ends up; charities refuse 15–20% of what's offered because they can't pay to move or store it.

## What's in the repository

| # | Part | What it does | Tools | Result |
|---|---|---|---|---|
| 1 | [Offcut forecasting](src/offcut) (*earlier work for a previous idea, not the product*) | P10/P50/P90 offcut forecast per cutting run; runs in the browser | Python, scikit-learn, pandas, JavaScript | **8.8%** mean error vs 20.3% for the 15% rule of thumb, 1,600 held-out *simulated* runs |
| 2 | [Analytics engineering](dbt) | Bronze (Parquet) → silver → gold models of 1.06m sales lines | dbt Core, DuckDB, SQL | **22** dbt data tests passing, including revenue reconciliation between layers |
| 3 | [Merchandising analytics](dbt/models/marts/mart_sku_health.sql) | Selling / slowing / stopped status, ABC/XYZ, velocity, markdown depth, return rate | SQL, dbt | **4,707** SKUs classified |
| 4 | [Stall-risk model](src/stock/train_stall.py) | From a line's first 12 weeks, predicts whether sales collapse in weeks 12–25 | scikit-learn, MLflow | ROC AUC **0.81** vs 0.60 for a "sales halved" rule on 423 later launches; top-20% precision 32% vs an 11% base rate |
| 5 | [Experimentation](src/stock/experiment.py) | Do markdowns help stock sell? How big must a routing pilot be? | statsmodels, SciPy | Stacked difference-in-differences (768 marked-down SKUs, 5 matched controls each). A placebo test found a pre-trend, so the +125% estimate is an upper bound. Pilot power analysis: **64** batches per arm |
| 6 | [Model monitoring](src/stock/monitor.py) | Accuracy, calibration and data drift per launch quarter | SciPy, pandas | Flagged over-prediction on 2011 Q2 launches (13.6% predicted vs 1.7% actual), an AUC alert for 2011 Q1 (0.65) and PSI drift. [Report](site/reports/monitoring.html) |
| 7 | [Regulation search](src/regsearch/search.py) | Finds the article of EU law that answers a question; checks citations | BM25, TF-IDF (scikit-learn), LLM API | Right article in the top 3 for **21 of 22** test questions (hit@1 73%, MRR 0.83) |
| 8 | [Purchase-order agent](src/offcut/agent.py) (*earlier work for a previous idea, not the product*) | Reads a messy order note, states assumptions, calls tested tools | LLM API with tool use | The model never does the arithmetic |
| 9 | [API](src/api/main.py) | Offcut forecast, stall risk and regulation search endpoints | FastAPI, Pydantic, Docker | **23** pytest tests; GitHub Actions runs them, builds the Docker image and calls the API on every push |
| 18 | [Batch record prototype](docs/6_planned.md#part-18-batch-report-prototype) (**planned, not built**) | Batch intake with check fields, offer/refusal log for donation entities, buyer contract terms per placement, waste-operator statements, hash-chained append-only log, export of disclosure rows | SQL (SQLite/Postgres), FastAPI, pytest | Not scheduled: nothing new is built before the Fri 26 Feb 2027 go / pivot / stop decision, and any early pilot runs by hand (spreadsheet and email). Built only if the pilot shows it is needed. Done when a demo season's batches produce a reproducible batch record and disclosure rows, with tests |

Every number above (Parts 1 to 9) is produced by the code in this repo and saved under [`models/`](models).

### Things the checks caught

- **dbt tests** found 23 returns logged before an item's first recorded sale (stock sold before the data starts). The model now leaves weeks-since-launch empty for those rows.
- **The browser export** of the offcut model rounded split thresholds, but scikit-learn compares inputs as 32-bit floats. For edge inputs (e.g. a 1.57 m roll) the browser took a different branch. Thresholds are now exported at full precision and inputs cast with `Math.fround`, and a test checks the export matches scikit-learn.
- **The placebo test** showed marked-down lines were already gaining before the markdown, so the difference-in-differences estimate is reported as an upper bound, not a clean effect.
- **Monitoring** showed the stall model is well ranked but over-confident for spring launches heading into the Christmas season, which a seasonal feature or recalibration would need to fix.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): how the parts fit together, and which are live, maybe later, parked or planned.
- Themed docs, one per group of parts. For each part: discipline, methodology, tools and status, the short part note, then the step-by-step guide (the code, every concept from scratch, results, what went wrong and how to run it). Parts 01 to 10 are built; 11 to 18 are planned, and none of 11 to 18 is scheduled before the 26 Feb 2027 decision.
  - [1. Data engineering](docs/1_data_engineering.md): Part 02 analytics engineering (dbt + DuckDB), Part 03 merchandising analytics
  - [2. Machine learning models](docs/2_ml_models.md): Part 01 offcut forecasting (earlier work for a previous idea, not the product), Part 04 stall-risk model
  - [3. Experiments and monitoring](docs/3_experiments_monitoring.md): Part 05 experimentation and causal analysis, Part 06 model monitoring
  - [4. AI tools](docs/4_ai_tools.md): Part 07 regulation search, Part 08 purchase-order agent (earlier work for a previous idea, not the product)
  - [5. Platform](docs/5_platform.md): Part 09 API service, Part 10 CI and Docker build
  - [6. Planned parts](docs/6_planned.md): Parts 11 to 18, including the Part 18 batch report prototype
- [Discipline and methodology by part](docs/ARCHITECTURE.md#discipline-and-methodology-by-part) and a [concept index](docs/ARCHITECTURE.md#concept-index).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make offcuts      # simulate 8,000 cutting runs, train, evaluate
make stock        # download retail data, dbt build, stall model, experiment, monitoring, regulation search
                  # (the monitoring step rewrites site/reports/monitoring.html)
make test         # 23 tests
make site-export  # on purpose only: refresh site/model.js and site/data/*.js for the live website
make site-diff    # see what changed in site/ before committing
make api          # http://127.0.0.1:8000/docs
make mlflow-ui    # browse tracked runs
```

> **Note:** `site/` is published by Netlify whenever `main` changes. Only `make monitor` (part of `make stock`), `make site` and `make site-export` write into it; run `make site-diff` and review `git diff site/` before committing.

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
