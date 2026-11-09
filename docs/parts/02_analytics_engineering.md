# Thread Futures part 02: Analytics engineering (dbt + DuckDB)

**Status:** Built · **Label:** Real open retail data  

## In one line
Turns raw sales data into tested, documented tables that every other part reads from.

## Why it matters
Every number in the product, from dashboards to the EU disclosure table, needs one trusted definition. dbt is also the standard tool for this kind of work.

## Data
UCI Online Retail II: about 1.07m invoice lines from a UK online retailer, Dec 2009 to Dec 2011, CC BY 4.0. Not fashion and not a customer. 1.06m lines after cleaning.

## Method
Bronze: raw Excel landed as Parquet. Silver (staging): real products only, postage and fees removed, returns flagged. Intermediate: SKU by week. Gold (marts): dim_sku, fct_sku_weekly, mart_sku_health. Generic and singular tests, including a revenue reconciliation between silver and gold. Semantic layer: MetricFlow semantic models and metrics (units sold, revenue, return rate, average markdown).

## Tools
dbt Core 1.12, dbt-duckdb, DuckDB, SQL, Parquet, Python

## Result
22 dbt data tests passing. The tests caught a real issue: 23 returns logged before an item's first recorded sale (sold before the data starts), now handled explicitly.

## Honest limits
Runs locally on DuckDB; the cloud warehouse version is part 13.

## Where it lives
dbt/ (models/staging, intermediate, marts, _semantic.yml, tests), src/stock/ingest.py
