# Architecture

How the parts of this repository fit together, and the status of each one as of 21 Nov 2026.

Thread Futures is a service, not software: the product is selling brands' unsold stock and reporting where every item went. Until the go / pivot / stop decision on Fri 26 Feb 2027, nothing new is built and any early pilot runs by hand (spreadsheet and email). The code here is earlier, exploratory work.

```mermaid
flowchart LR
    subgraph data["Data"]
        UCI["UCI Online Retail II<br/>(real open retail data, not fashion)"]
        SIM["Simulated cutting runs"]
        REG["EU regulation text<br/>(Reg. 2024/1781)"]
    end

    subgraph dbtp["dbt + DuckDB"]
        BR["bronze: Parquet"] --> SV["silver: staging / intermediate"] --> GD["gold: marts<br/>(22 data tests)"]
    end

    subgraph models["Models (src/)"]
        STALL["Stall-risk model<br/>src/stock"]
        EXP["Experiment + monitoring<br/>src/stock"]
        OFF["Offcut forecast + PO agent<br/>src/offcut"]
    end

    RS["Regulation search<br/>src/regsearch"]
    API["FastAPI<br/>src/api (3 endpoints)"]
    SITE["Website<br/>site/ (Netlify, auto-deploys main)"]
    BATCH["Batch-record tool<br/>(planned, not built)"]

    UCI --> BR
    GD --> STALL --> EXP
    SIM --> OFF
    REG --> RS
    STALL --> API
    OFF --> API
    RS --> API
    STALL -. "make site-export" .-> SITE
    EXP -. "make monitor" .-> SITE
    OFF -. "make site" .-> SITE
    BATCH -.-> SITE

    classDef live fill:#D7EF91,stroke:#173D35,color:#173D35
    classDef later fill:#E3F2EE,stroke:#173D35,color:#173D35
    classDef parked fill:#EEEEEA,stroke:#8A948F,color:#46564F
    classDef planned fill:#FFFFFF,stroke:#173D35,stroke-dasharray:5 5,color:#173D35
    class RS,API,SITE live
    class BR,SV,GD,STALL,EXP later
    class OFF,SIM parked
    class BATCH planned
```

Dotted arrows into `site/` are manual export steps. `site/` is the live website, so only run them on purpose and check `make site-diff` before committing.

## Status of each part

| Part | Where | Status | What that means |
|---|---|---|---|
| Website | `site/` | **Live** | Static HTML, published by Netlify when `main` changes. No build step. |
| Regulation search | `src/regsearch/` | **Live** (internal research aid) | Finds the article of EU law that answers a question. Rebuilds its index on each call, which is fine at this size. |
| API, CI and tests | `src/api/`, `tests/`, `.github/workflows/` | **Live** (maintenance only) | FastAPI with offcut, stall-risk and regulation-search endpoints; CI runs pytest, builds the Docker image and calls the API. |
| dbt pipeline | `dbt/` | **Maybe later** | Bronze → silver → gold on real open retail data, 22 data tests. Not run in CI. Could be reused for brands' stock files after pilots. |
| Stall-risk model, experiment, monitoring | `src/stock/` | **Maybe later** | ROC AUC 0.81 vs 0.60 for a simple rule, on retail data that is not fashion. A possible input to prevention ("make less"), a later stage. |
| Offcut forecast and purchase-order agent | `src/offcut/` | **Parked** | Earlier exploratory work for a previous idea (garment factories), not the product. Trained on simulated data. Kept as proof of build. |
| Batch-record tool | `docs/parts/18_batch_and_destination_file_prototype.md` | **Planned, not built** | The first piece of product software, if pilots show it is needed. Not before 26 Feb 2027; until then pilots run by hand. |

## Files that write into `site/`

| Command | Writes | Part of |
|---|---|---|
| `make monitor` | `site/reports/monitoring.html` | `make stock` |
| `make site` | `site/model.js` (offcut model) | `make all`, `make site-export` |
| `make site-export` | `site/model.js`, `site/data/stall_model.js`, `site/data/stock.js` | run on purpose only |

## Known gaps

- Locally, only the offcut tests run without the full environment (`fastapi` and `duckdb` are needed for the rest); CI has the full set.
- Several tests check saved artefacts in `models/` rather than re-running the code that made them.
- No tests yet for feature building, the experiment, training, monitoring, the site exports, ingest, the agent or generated regulation answers.
