# 6. Planned parts

Parts that are planned and not built. Parts 11 to 17 would extend the earlier technical work; Part 18, the batch report prototype, would be the first piece of product software and would be built only after hand-run pilots show it is needed.

Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. The code described here is earlier, exploratory technical work, not the product. Nothing new is built before the go / pivot / stop decision on Fri 26 Feb 2027, and any early pilot runs by hand (spreadsheet and email). See [ARCHITECTURE.md](ARCHITECTURE.md) for how the parts fit together.

Each part starts with a header block (discipline, methodology, tools, status), then the short part note, then the full step-by-step guide.

## Contents

- [Overview of Parts 11 to 17](#overview-of-parts-11-to-17)
- [Part 11: Stock health dashboard](#part-11-stock-health-dashboard)
  - [Part 11 step by step (PLANNED)](#part-11-step-by-step-planned)
- [Part 12: Customer analytics](#part-12-customer-analytics)
  - [Part 12 step by step (PLANNED)](#part-12-step-by-step-planned)
- [Part 13: Cloud warehouse](#part-13-cloud-warehouse)
  - [Part 13 step by step (PLANNED)](#part-13-step-by-step-planned)
- [Part 14: Spark at scale](#part-14-spark-at-scale)
  - [Part 14 step by step (PLANNED)](#part-14-step-by-step-planned)
- [Part 15: Seasonality fix](#part-15-seasonality-fix)
  - [Part 15 step by step (PLANNED)](#part-15-step-by-step-planned)
- [Part 16: Markdown pricing (Bayesian)](#part-16-markdown-pricing-bayesian)
  - [Part 16 step by step (PLANNED, optional)](#part-16-step-by-step-planned-optional)
- [Part 17: Azure deploy](#part-17-azure-deploy)
  - [Part 17 step by step (PLANNED, optional)](#part-17-step-by-step-planned-optional)
- [Part 18: Batch report prototype](#part-18-batch-report-prototype)
- [Glossary for the planned parts](#glossary-for-the-planned-parts)

---

## Overview of Parts 11 to 17

> **PLANNED, NOT BUILT.** Nothing in Parts 11 to 17 exists in the repo yet. None of it is claimed on the website until it's built, in the repo and its numbers are saved under `models/`.

Parts are ordered by priority. Effort estimates come from the subproject summaries.

Parts 11 to 17 extend the earlier, exploratory technical work; they are not the product and none is scheduled. Part 18, the batch report prototype ([below](#part-18-batch-report-prototype)), would come before these, but it is planned, not built: nothing new is built before the Fri 26 Feb 2027 go / pivot / stop decision, and any early pilot runs by hand (spreadsheet and email).

| # | Part | Skills it adds | Effort | Done when |
|---|---|---|---|---|
| 11 | Stock health dashboard | Power BI, Looker, semantic layer, DAX | 1 day | Published dashboard link and a screenshot on the site |
| 12 | Customer analytics | Cohorts, LTV, churn, segmentation, SQL | 3 to 4 days | Cohort chart and LTV table in the repo |
| 13 | Cloud warehouse | BigQuery, Snowflake, dbt | 2 to 3 days | dbt build passes on the cloud target |
| 14 | Spark at scale | Databricks, PySpark, Delta Lake | 2 to 3 days | Same feature table as DuckDB; row counts and a sample of values match |
| 15 | Seasonality fix | Feature engineering, calibration, monitoring | 1 to 2 days | The 2011 Q2 gap between predicted (14%) and actual (1.7%) stall rate shrinks |
| 16 | Markdown pricing (Bayesian) | PyMC, pricing, elasticity | 3 to 5 days | Elasticity by category with credible intervals (optional) |
| 17 | Azure deploy | Azure, containers, cloud deployment | 2 to 3 days | Live API URL on Azure (optional) |

---

## Part 11: Stock health dashboard

**Discipline:** Data Analytics / Data Engineering (primary / secondary)  
**Methodology:** Planned: export `mart_sku_health` and `fct_sku_weekly` from DuckDB, relate them one-to-many on `stock_code` in Power BI (or Looker Studio), and write DAX measures that match the dbt and MetricFlow definitions, with one page per audience.  
**Tools:** Power BI, Looker Studio, DAX  
**Status:** Planned: not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Power BI (or Looker Studio) dashboard on the dbt marts: selling, slowing and stopped lines, ABC/XYZ, markdown depth.

### Skills it adds
Power BI, Looker, semantic layer, DAX

### Plan
Connect to mart_sku_health and fct_sku_weekly (export to CSV/Parquet or BigQuery after part 13). One page for the merchandiser, one for the sustainability lead.

### Done when
Published dashboard link and a screenshot on the site.

### Effort
1 day

### Part 11 step by step (PLANNED)

**Goal:** a Power BI (or Looker Studio) dashboard on the dbt marts: selling, slowing and stopped lines, ABC/XYZ, markdown depth. One page for the merchandiser, one for the sustainability lead.

#### Concepts to learn first

- **BI tool data model:** a BI tool imports or connects to tables and relates them. `fct_sku_weekly` (many rows per SKU) relates to `dim_sku` (one row per SKU) on `stock_code`, a one-to-many relationship. This is the star schema from part 02.
- **Import vs live/DirectQuery connection:** import copies data into the BI file (fast, needs refreshing); a live connection queries the warehouse each time (always fresh, depends on the warehouse). With DuckDB locally, import from CSV or Parquet is the practical route; after part 13, a live BigQuery connection.
- **DAX measures:** Power BI's formula language. A measure is calculated at query time in the current filter context. Example: `Return Rate = DIVIDE(SUM(fct[units_returned]), SUM(fct[units_sold]))`. `DIVIDE` handles division by zero. This is a ratio of sums, matching the MetricFlow `return_rate` in part 02.
- **Filter context:** the slicers, rows and columns currently applied. The same measure gives a different number per launch cohort because the context changes. Understanding this is most of DAX.
- **Calculated column vs measure:** a column is computed per row at refresh and stored; a measure is computed on the fly over many rows. Ratios should be measures.
- **Semantic layer consistency:** the dashboard's definitions should match dbt's. Either reuse the dbt metrics or document that the DAX measures are copies of them.
- **Audience-led design:** a merchandiser needs "what do I act on this week" (A lines slowing, deepest markdowns); a sustainability lead needs "how much stock is at risk of becoming surplus".

#### Step-by-step build plan

1. Export `mart_sku_health` and `fct_sku_weekly` from DuckDB to Parquet or CSV (or connect to BigQuery after part 13).
2. Load into Power BI Desktop; set the relationship `dim_sku[stock_code]` to `fct_sku_weekly[stock_code]`, one to many.
3. Write measures: units sold, revenue, return rate, average markdown, count of SKUs by status.
4. Page 1 (merchandiser): status by ABC class matrix, list of A lines that are slowing, velocity ratio, markdown depth.
5. Page 2 (sustainability lead): stopped and slowing lines, weekly sales trend, return rate by cohort.
6. Label every page "Real open retail data (UCI Online Retail II), not fashion, not a customer".
7. Check three numbers against the dbt mart by SQL (for example SKUs by status) before publishing.
8. Publish (Power BI service or Looker Studio), take a screenshot, add both to the site.

#### Done when
Published dashboard link and a screenshot on the site.

---

## Part 12: Customer analytics

**Discipline:** Data Science / Data Analytics (primary / secondary)  
**Methodology:** Planned: monthly acquisition cohorts and retention curves in SQL over the customer IDs already in the staging data, RFM scores with k-means segments, and a simple LTV (optionally BG/NBD).  
**Tools:** SQL, dbt, Python, scikit-learn  
**Status:** Planned: not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Cohort retention, RFM segmentation and customer lifetime value using Online Retail II's customer IDs.

### Skills it adds
Cohorts, LTV, churn, segmentation, SQL

### Plan
Monthly acquisition cohorts and retention curves in SQL; RFM scores and k-means segments; simple LTV (and optionally BG/NBD).

### Done when
Cohort chart and LTV table in the repo.

### Effort
3 to 4 days

### Part 12 step by step (PLANNED)

**Goal:** cohort retention, RFM segmentation and customer lifetime value using Online Retail II's customer IDs.

#### Concepts to learn first

- **Acquisition cohort:** customers grouped by the month of their first purchase.
- **Retention curve:** for each cohort, the share of customers who buy again in month 1, 2, 3 after their first purchase. Shown as a triangle-shaped table or a set of lines.
  *Example:* 100 customers first bought in January; 30 bought again in February. Month-1 retention is 30%.
- **Churn:** a customer who has stopped buying. In non-subscription retail there's no cancel button, so churn has to be defined, for example "no purchase in 6 months".
- **RFM:** Recency (days since last purchase), Frequency (number of orders), Monetary (total spend). Score each 1 to 5 by quintile and combine. "555" is a best customer; "155" is a big spender who hasn't been back lately.
- **k-means clustering:** split customers into k groups so each customer is close to its group's centre. Needs scaled features (RFM values are on very different scales) and a choice of k (elbow plot or silhouette score).
- **Customer lifetime value (LTV):** expected future value of a customer. Simple version: average order value x purchase frequency x expected lifespan. Historical LTV just sums past spend.
- **BG/NBD model (optional):** a probabilistic model that estimates, for each customer, how likely they are still "alive" and how many purchases to expect, from their recency, frequency and age. Often paired with Gamma-Gamma for spend.
- **Data quirks to handle:** missing customer IDs (guest or wholesale orders), returns (negative quantities), and wholesale customers who distort averages.

#### Step-by-step build plan

1. New dbt models: `int_customer_orders` (one row per customer per invoice, excluding missing IDs and returns), `mart_customer_cohorts` (cohort month x months since first purchase, with retention share).
2. SQL for RFM per customer as of the last data date; quintile scores with `ntile(5)`.
3. Add dbt tests: customer ID not null in the mart, retention between 0 and 1, cohort sizes reconcile with distinct customers.
4. In Python: scale RFM, run k-means for a few values of k, choose one, describe each segment in plain English.
5. Simple LTV table by segment; optionally fit BG/NBD and compare.
6. Plot the cohort retention chart; save the LTV table and any metrics to `models/`.
7. Write the honest-limits note: UK online gift retailer with wholesale customers, not fashion, not a customer.

#### Done when
Cohort chart and LTV table in the repo.

---

## Part 13: Cloud warehouse

**Discipline:** Data Engineering / Data Analytics (primary / secondary)  
**Methodology:** Planned: add a cloud target to `dbt/profiles.yml`, load the Parquet bronze layer into BigQuery or Snowflake, run the same `dbt build` there and compare row counts with DuckDB.  
**Tools:** BigQuery, Snowflake, dbt  
**Status:** Planned: not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Run the same dbt project on BigQuery (free sandbox) or Snowflake (trial).

### Skills it adds
BigQuery, Snowflake, dbt

### Plan
Add a cloud profile, load the Parquet bronze layer, run dbt build on the cloud target, compare row counts with DuckDB.

### Done when
dbt build passes on the cloud target.

### Effort
2 to 3 days

### Part 13 step by step (PLANNED)

**Goal:** run the same dbt project on BigQuery (free sandbox) or Snowflake (trial).

#### Concepts to learn first

- **Cloud data warehouse:** a managed, columnar database that separates storage from compute and scales on demand. BigQuery bills mainly by data scanned; Snowflake by warehouse compute time.
- **dbt profiles and targets:** `profiles.yml` can hold several outputs (for example `dev` on DuckDB, `bq` on BigQuery). `dbt build --target bq` runs the same models against the other warehouse.
- **Adapters:** dbt-duckdb, dbt-bigquery, dbt-snowflake translate dbt's work into each warehouse's SQL. Installing one is a new dependency, so discuss it first.
- **SQL dialect differences:** functions in the current models that may need changing: `read_parquet`, `regexp_matches`, `datediff('week', ...)`, `generate_series`, `unnest(range(...))`, `mode()`, `md5(concat_ws(...))`. dbt's cross-database macros (like `dbt.datediff`) help.
- **dbt sources:** declare the raw table formally in a `sources:` block instead of a file path variable, with freshness checks.
- **Loading data:** upload the bronze Parquet to cloud storage and load it into a raw table (BigQuery load job, or Snowflake stage plus `COPY INTO`).
- **Authentication:** service account key files or OAuth. Keys never go in git; they go in environment variables or a local file listed in `.gitignore`.
- **Cost control:** partitioning and clustering, selecting only needed columns, and checking the free-tier limits.

#### Step-by-step build plan

1. Create a BigQuery sandbox project (or Snowflake trial) and a dataset for raw data.
2. Load `data/raw/retail/transactions.parquet` into a raw table.
3. Add a `sources:` block for it and switch `stg_transactions` to `{{ source(...) }}` (keeping DuckDB working, for example with a target-based macro).
4. Add a cloud output to `profiles.yml`, with credentials from environment variables.
5. Fix dialect differences one model at a time, using dbt cross-database macros where possible.
6. `dbt build --target <cloud>`; fix failing tests.
7. Compare row counts per model and key totals (revenue, SKUs by status) with DuckDB, and record them.

#### Done when
dbt build passes on the cloud target.

---

## Part 14: Spark at scale

**Discipline:** Data Engineering / Machine Learning (primary / secondary)  
**Methodology:** Planned: rebuild the `src/stock/features.py` feature table in PySpark on Databricks from the Parquet bronze layer, using Spark window functions, write Delta tables and check that row counts and sampled values match DuckDB.  
**Tools:** Databricks, PySpark, Delta Lake  
**Status:** Planned: not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Rebuild the stall-risk feature table in PySpark on Databricks Free Edition.

### Skills it adds
Databricks, PySpark, Delta Lake

### Plan
Read the Parquet bronze layer, rebuild weekly SKU features with Spark window functions, write Delta tables.

### Done when
Same feature table as DuckDB; row counts and a sample of values match.

### Effort
2 to 3 days

### Part 14 step by step (PLANNED)

**Goal:** rebuild the stall-risk feature table in PySpark on Databricks Free Edition.

#### Concepts to learn first

- **Apache Spark:** a distributed engine that splits data into partitions and processes them in parallel across machines.
- **PySpark DataFrame API:** a pandas-like API whose operations build a plan rather than running immediately.
- **Lazy evaluation:** operations such as `filter`, `groupBy` and `join` are planned; nothing runs until an action (`count`, `write`, `show`). Spark optimises the whole plan first.
- **Partitions and shuffles:** a `groupBy` or `join` often moves data between machines (a shuffle), which is the expensive part. Knowing when a shuffle happens is the key performance skill.
- **Spark window functions:** `Window.partitionBy("stock_code").orderBy("week_start").rowsBetween(-7, 0)` is the Spark equivalent of the rolling 8-week average in part 03.
- **Delta Lake:** a table format on top of Parquet that adds transactions (ACID), schema enforcement and time travel (querying earlier versions).
- **Medallion on Databricks:** the same bronze, silver, gold idea, as Delta tables.
- **Honest scale framing:** 1.07m rows is small for Spark. The point is to show the same logic works on a distributed engine, not that it's needed here.

#### Step-by-step build plan

1. Upload the bronze Parquet to Databricks Free Edition; read it as a DataFrame.
2. Rebuild staging filters (product code regex, price and quantity rules, return flag) as a silver Delta table.
3. Rebuild SKU-week aggregation and `dim_sku` launch logic.
4. Rebuild the 26-week grid per SKU (a cross join with a 0 to 25 range) and the ten early-life features from `src/stock/features.py`.
5. Write the feature table as Delta.
6. Export it and compare with the DuckDB feature table: row count (1,319 eligible SKUs in DuckDB), and a sample of values per feature to a tolerance.
7. Note any differences and why (for example `mode()` tie-breaking).

#### Done when
Same feature table as DuckDB; row counts and a sample of values match.

---

## Part 15: Seasonality fix

**Discipline:** Machine Learning / Data Science (primary / secondary)  
**Methodology:** Planned: add weeks-to-Christmas and launch-season features to the stall-risk model, calibrate probabilities with Platt scaling or isotonic regression, and re-run `src/stock/monitor.py` to see whether the 2011 Q2 over-prediction shrinks.  
**Tools:** scikit-learn, pandas, SciPy  
**Status:** Planned: not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Add seasonal features and calibrate probabilities to fix the over-prediction monitoring found.

### Skills it adds
Feature engineering, calibration, monitoring

### Plan
Add weeks-to-Christmas and launch-season features; isotonic or Platt calibration; re-run part 6.

### Done when
The 2011 Q2 gap between predicted (14%) and actual (1.7%) stall rate shrinks.

### Effort
1 to 2 days

### Part 15 step by step (PLANNED)

**Goal:** add seasonal features and calibrate probabilities to fix the over-prediction monitoring found (part 06).

#### Concepts to learn first

- **Seasonality:** regular calendar patterns in demand. Here, sales rise towards Christmas, so a spring launch's weeks 12 to 25 fall in a rising market.
- **Seasonal features:** for example, weeks from launch to Christmas, or the share of the outcome window that falls in October to December. Better than launch month alone, because they describe the outcome window the model is predicting.
- **Cyclical encoding (optional):** month as sine and cosine so December and January are close.
- **Calibration:** predicted probabilities should match observed rates (part 04).
- **Platt scaling:** fit a logistic regression on the model's scores to map them to better probabilities. Simple, assumes an S-shaped correction.
- **Isotonic regression:** fit a step-shaped, always-increasing mapping. More flexible, needs more data, can overfit small sets.
- **Calibration set:** the mapping must be fitted on data not used to train the model, ideally a recent period, to avoid leakage.
- **Reliability diagram:** bin predictions (0 to 10%, 10 to 20%, and so on) and plot mean predicted against actual rate. A calibrated model sits on the diagonal.
- **Base-rate shift:** a read-only check while writing the part 04 guide found the training stall rate was about 28% and the test rate about 11%. Calibration on recent data directly addresses that.
- **Evaluation:** Brier score and the predicted vs actual gap per quarter, alongside AUC (ranking shouldn't get worse).

#### Step-by-step build plan

1. Fix the rule baseline tie-break sign in `train_stall.py` first (see part 04 guide), so comparisons are fair.
2. Add seasonal features to `features.py` (weeks to Christmas from launch, share of the outcome window in Q4).
3. Retrain; log as a new MLflow run so it can be compared with run `588d9d4399eb4ce0be3deed3809a0b84` (the current stall-risk run, version 2).
4. Hold out the most recent training launches as a calibration set; fit Platt and isotonic; compare Brier scores.
5. Rerun `make monitor`; compare predicted vs actual stall rate per quarter with the current 27.2% vs 21.1%, 20.0% vs 7.1% and 13.6% vs 1.7% (from `models/monitoring.json`).
6. Fix the PSI function for low-cardinality features while there (part 06 guide).
7. Update `models/stall_metrics.json`, `models/monitoring.json`, the API bands if needed, and the README.

#### Done when
The 2011 Q2 gap between predicted (14%) and actual (1.7%) stall rate shrinks.

---

## Part 16: Markdown pricing (Bayesian)

**Discipline:** Data Science / Machine Learning (primary / secondary)  
**Methodology:** Planned: a hierarchical model of log units on log price by category with partial pooling, fitted with MCMC, building on the markdown data used in `src/stock/experiment.py`.  
**Tools:** PyMC, ArviZ, pandas  
**Status:** Planned (optional): not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Estimate how much markdowns move sales by category, with honest uncertainty.

### Skills it adds
Bayesian methods (PyMC), pricing, elasticity

### Plan
Hierarchical model of log units on log price by category, with partial pooling.

### Done when
Elasticity by category with credible intervals. Optional.

### Effort
3 to 5 days

### Part 16 step by step (PLANNED, optional)

**Goal:** estimate how much markdowns move sales by category, with honest uncertainty.

#### Concepts to learn first

- **Price elasticity of demand:** the percentage change in units for a 1% change in price. Elasticity of -2 means a 10% price cut gives about 20% more units.
- **Log-log model:** regress log units on log price; the slope is the elasticity.
- **Bayesian inference:** start with a prior belief about a parameter, update it with data, get a posterior distribution.
- **Prior / likelihood / posterior:** what you believed before / how likely the data is under each parameter value / what you believe after.
- **Credible interval:** a range containing the parameter with a stated probability (for example 90%), given the model and data. Different from a confidence interval's interpretation.
- **Hierarchical model and partial pooling:** each category gets its own elasticity, but they're drawn from a shared distribution. Small categories borrow strength from the rest, so their estimates are less noisy. Between "one elasticity for everything" (complete pooling) and "separate for each" (no pooling).
- **MCMC (Markov chain Monte Carlo):** the sampling method that draws from the posterior. PyMC uses the NUTS sampler.
- **Diagnostics:** R-hat close to 1 (chains agree), effective sample size, no divergences, posterior predictive checks.
- **Endogeneity caveat:** price isn't set randomly. Part 05's failed placebo test showed markdowns follow demand changes, so these elasticities are still observational and should be framed with care.
- **Categories:** the data has no category field, so they'd need defining (for example from description keywords). That's a judgement to document.

#### Step-by-step build plan

1. Define categories from descriptions; check counts per category.
2. Build a SKU-week dataset with log units and log price relative to launch price.
3. Write the PyMC model: category-level elasticities drawn from a shared normal, SKU intercepts, week effects.
4. Prior predictive check: do priors produce plausible sales?
5. Sample; check R-hat, effective sample size and divergences.
6. Posterior predictive check against held-out weeks.
7. Report elasticity by category with credible intervals; compare with the part 05 upper bound.
8. Discuss PyMC as a new dependency before installing it.

#### Done when
Elasticity by category with credible intervals. Optional.

---

## Part 17: Azure deploy

**Discipline:** AI Engineering / Data Engineering (primary / secondary)  
**Methodology:** Planned: push the image that CI already builds from the `Dockerfile` to a container registry and deploy it to Azure Container Apps, then add the URL to the README.  
**Tools:** Azure Container Apps, Azure Container Registry, Docker  
**Status:** Planned (optional): not scheduled; nothing new is built before the 26 Feb 2027 decision.

**Build state:** Planned · **Data label:** Planned  

### In one line
Deploy the API container to Azure Container Apps.

### Skills it adds
Azure, containers, cloud deployment

### Plan
Push the CI-built image to a registry, deploy, add the URL to the README; DP-900 learning path alongside.

### Done when
Live API URL on Azure. Optional.

### Effort
2 to 3 days

### Part 17 step by step (PLANNED, optional)

**Goal:** deploy the API container to Azure Container Apps.

#### Concepts to learn first

- **Container registry:** a store for images. Azure Container Registry (ACR) or GitHub Container Registry. CI pushes the image; the cloud service pulls it.
- **Image tags:** label images with the commit hash (and optionally `latest`) so you always know what's running.
- **Azure Container Apps:** a managed service that runs containers with HTTPS, scaling and revisions, without managing servers or Kubernetes directly.
- **Ingress and HTTPS:** external ingress gives the app a public URL with a certificate.
- **Scale to zero:** no traffic means no running instances (lower cost), with a cold start on the next request.
- **Revisions:** each deployment is a revision; you can roll back.
- **Health probes:** the platform calls `/health` (already built) to decide whether an instance is ready.
- **Secrets and identity:** registry credentials and any API keys as Container Apps secrets or managed identity, plus GitHub Actions secrets for the deploy step. Never in the workflow file.
- **Continuous deployment:** extend `.github/workflows/ci.yml` with a job that runs after `docker` on `main`, pushes the image and updates the container app. Changing the workflow is a CI/CD change, so show the diff before applying it.
- **Cost and limits:** free credits and quotas; switch off or scale to zero when not demoing.
- **DP-900:** Microsoft's Azure Data Fundamentals learning path, done alongside, covering core data concepts and Azure data services.

#### Step-by-step build plan

1. Create a resource group, a container registry and a Container Apps environment.
2. Add a CI job (diff reviewed first) that logs in to the registry with secrets, tags the image with the commit hash and pushes it.
3. Create the container app from the image, port 8000, external ingress, health probe on `/health`.
4. Smoke-test the live URL with the same curl requests used in CI.
5. Add a deploy step to update the app on each green build of `main`.
6. Add the live URL to the README with the same data labels as the API description.

#### Done when
Live API URL on Azure. Optional.

---

## Part 18: Batch report prototype

**Discipline:** Data Engineering / AI Engineering (primary / secondary)  
**Methodology:** Planned: a SQL data model for batches, units and handovers, a hash-chained append-only event log, and FastAPI endpoints (reusing the patterns in `src/api/main.py`) to record events and export the batch report and Article 24 disclosure rows.  
**Tools:** SQL (SQLite/Postgres), FastAPI, pytest  
**Status:** Planned: only after hand-run pilots (spreadsheet and email) show it is needed, and not before the 26 Feb 2027 decision.

**Build state:** Planned, not built · **Data label:** Planned (not before the 26 Feb 2027 decision)  

### In one line
Planned product software: one batch report per batch of a brand's unsold stock, recording every unit and every step (check, sell or donate or recycle, report), with an export of the EU Article 24 disclosure rows.

### Why it matters
Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves. The brand keeps ownership of the stock until it is sold, gets the money from each sale and gets a report of where every item went. Parts 1 to 10 are earlier, exploratory technical work; this part would be product software.

### Skills it adds
Data modelling, SQL (SQLite/Postgres), FastAPI, audit logging, pytest

### Plan
- **Batch intake with check fields:** batch ID, SKUs, quantity, real size breakdown, condition codes, fibre composition (from the brand's product specs), reason unsold.
- **Placement records, in waste-hierarchy order:**
  - contracted buyers, with the contract terms per placement (no destruction, no export as waste, channel/marketplace limits, de-labelling where required, onward-destination reporting) and the buyer's report of onward destinations;
  - an offer/refusal log for donation to EU social-economy entities (who was offered what, when, and their decision), so the donation derogation (offered to at least three suitable EU entities for at least 8 weeks) can be evidenced;
  - waste-operator statements for last-resort recycling: the derogation statement handed over and the operator's receipt/treatment statement collected.
- **Hash-chained, append-only log:** every event is appended and chained to the previous one, so any later edit is visible. Records are created at the moment of each handover, not rebuilt afterwards.
- **Export:** a batch report per batch (kept 5 years, producible within 30 days of a request) and rows ready for the Article 24 disclosure table.
- FastAPI endpoints to record events and export the batch report and disclosure rows.

This is why the product isn't something a chatbot can reproduce: a chat can draft a template, but it can't create a charity's acceptance or a waste operator's statement after the fact.

### Done when
A demo season's batches produce a reproducible batch report and disclosure rows, with tests.

### Effort
About 4 days (an estimate). Not scheduled: nothing new is built before the Fri 26 Feb 2027 go / pivot / stop decision, and any early pilot runs by hand (spreadsheet and email). This part would be built only if the pilot shows it is needed.

### Note on the file name
This part was first written up in its own file under `docs/parts/`, whose name used an earlier working name for the batch report. It now lives in this doc.

---

## Glossary for the planned parts

- **DAX:** Power BI's formula language.
- **Measure (BI):** a calculation evaluated in the current filter context.
- **Filter context:** the filters currently applied to a visual.
- **Cohort retention:** share of a cohort still buying after n periods.
- **Churn:** customers who have stopped buying, by a chosen definition.
- **RFM:** recency, frequency, monetary scoring.
- **k-means:** clustering into k groups around centres.
- **LTV:** customer lifetime value.
- **BG/NBD:** probabilistic model of repeat purchasing and drop-out.
- **dbt target / adapter:** a named connection / warehouse-specific plug-in.
- **dbt source:** formally declared raw table.
- **SQL dialect:** a warehouse's flavour of SQL.
- **Spark:** distributed data processing engine.
- **Lazy evaluation:** operations planned, run only on an action.
- **Shuffle:** moving data between machines for a group or join.
- **Delta Lake:** Parquet-based table format with transactions and time travel.
- **Seasonal feature:** an input describing calendar effects.
- **Platt scaling / isotonic regression:** calibration methods.
- **Reliability diagram:** predicted against observed rates by bin.
- **Elasticity:** percentage change in units per percentage change in price.
- **Prior / posterior:** belief before / after seeing data.
- **Credible interval:** Bayesian uncertainty range.
- **Partial pooling:** group estimates that share information.
- **MCMC / NUTS:** sampling methods for Bayesian models.
- **R-hat:** convergence diagnostic, should be close to 1.
- **Container registry:** store for container images.
- **Azure Container Apps:** managed container hosting.
- **Ingress:** how outside traffic reaches the app.
- **Scale to zero:** no instances running when idle.
- **Revision:** a versioned deployment.
- **DP-900:** Azure Data Fundamentals certification path.
