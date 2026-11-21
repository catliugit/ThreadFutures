# 1. Data engineering

Getting real open retail data into a tested warehouse and turning it into merchandising measures: the dbt and DuckDB pipeline (Part 02) and the stock health mart built on it (Part 03).

Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. The code described here is earlier, exploratory technical work, not the product. Nothing new is built during customer discovery (to early 2027), and any early pilot runs by hand (spreadsheet and email). See [ARCHITECTURE.md](ARCHITECTURE.md) for how the parts fit together.

Each part starts with a header block (discipline, methodology, tools, status), then the short part note, then the full step-by-step guide.

## Contents

- [Part 02: Analytics engineering (dbt + DuckDB)](#part-02-analytics-engineering-dbt--duckdb)
  - [Part 02 step by step](#part-02-step-by-step)
- [Part 03: Merchandising analytics](#part-03-merchandising-analytics)
  - [Part 03 step by step](#part-03-step-by-step)

---

## Part 02: Analytics engineering (dbt + DuckDB)

**Discipline:** Data Engineering / Data Analytics (primary / secondary)  
**Methodology:** `src/stock/ingest.py` downloads UCI Online Retail II and lands it as Parquet (bronze). dbt on DuckDB builds `stg_transactions` (silver), `int_sku_weekly` (one row per SKU per week) and the gold marts `dim_sku`, `fct_sku_weekly` and `mart_sku_health`, with generic tests, two custom test macros, a revenue-reconciliation singular test and a MetricFlow semantic layer.  
**Tools:** dbt Core, DuckDB, SQL, Jinja, Parquet, MetricFlow, Python  
**Status:** Maybe later: 22 data tests pass, but the pipeline is not run in CI. It could be reused for brands' stock files after pilots.

**Build state:** Built · **Data label:** Real open retail data  

### In one line
Turns raw sales data into tested, documented tables that every other part reads from.

### Why it matters
Every number needs one trusted definition. This part is proof of build, not the product; the same habits (layers, tests, reconciled totals) are what the planned batch report would rely on. dbt is also the standard tool for this kind of work.

### Data
UCI Online Retail II: about 1.07m invoice lines from a UK online retailer, Dec 2009 to Dec 2011, CC BY 4.0. Not fashion and not a customer. 1.06m lines after cleaning.

### Method
Bronze: raw Excel landed as Parquet. Silver (staging): real products only, postage and fees removed, returns flagged. Intermediate: SKU by week. Gold (marts): dim_sku, fct_sku_weekly, mart_sku_health. Generic and singular tests, including a revenue reconciliation between silver and gold. Semantic layer: MetricFlow semantic models and metrics (units sold, revenue, return rate, average markdown).

### Tools
dbt Core 1.12, dbt-duckdb, DuckDB, SQL, Parquet, Python

### Result
22 dbt data tests passing. The tests caught a real issue: 23 returns logged before an item's first recorded sale (sold before the data starts), now handled explicitly.

### Honest limits
Runs locally on DuckDB; the cloud warehouse version is part 13.

### Where it lives
dbt/ (models/staging, intermediate, marts, _semantic.yml, tests), src/stock/ingest.py

### Part 02 step by step

**Build state:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II, a UK online retailer, CC BY 4.0). Not fashion, not a customer.
**Code:** `src/stock/ingest.py`, `dbt/` (dbt_project.yml, profiles.yml, models/staging, models/intermediate, models/marts, tests, macros)
**Numbers from:** `dbt/target/run_results.json`, `dbt/logs/dbt.log`, and read-only queries of `data/warehouse.duckdb` (labelled where used)

---

#### 1. The question this stage answers

How do I turn a raw spreadsheet of 1.07 million invoice lines into trusted, tested tables that every other part of the project reads from?

A fashion brand cares because every number it reports, from "units sold this week" to a record of where unsold stock went, needs one agreed definition. If the dashboard, the model and the compliance report each calculate revenue slightly differently, nobody trusts any of them.

---

#### 2. The pipeline, step by step

##### Step 1. Bronze: download the raw data and land it as Parquet

**What happens:** download the UCI zip, read both Excel sheets (2009-10 and 2010-11), rename columns, and write one Parquet file. Nothing is cleaned here on purpose.

**Where:** `src/stock/ingest.py`, `download()`, `land()`

**In:** `online_retail_II.xlsx`. **Out:** `data/raw/retail/transactions.parquet`

```python
sheets = pd.read_excel(xlsx, sheet_name=None, dtype={"Invoice": str, "StockCode": str, "Customer ID": "Int64"})
df = pd.concat(sheets.values(), ignore_index=True)
df.columns = ["invoice", "stock_code", "description", "quantity", "invoice_ts", "unit_price", "customer_id", "country"]
con = duckdb.connect()
con.register("df", df)
con.execute(f"COPY df TO '{out.as_posix()}' (FORMAT PARQUET)")
```

- Line 1: `sheet_name=None` reads every sheet. Invoice and StockCode are forced to text, because some codes start with letters (returns start with "C") and leading zeros matter. Customer ID uses pandas' nullable integer so missing IDs stay missing instead of becoming floats.
- Line 2: stack both years into one table.
- Line 3: clean, consistent snake_case column names.
- Lines 4 to 6: hand the DataFrame to DuckDB and write Parquet.

**Why this way:** Excel is slow and fragile to re-read. Parquet is columnar, compressed and typed, so every downstream query is fast. Keeping bronze untouched means I can always rebuild silver and gold if I change a rule. A read-only check of the Parquet file returns 1,067,371 rows.

##### Step 2. Silver (staging): keep real products, flag returns

**Where:** `dbt/models/staging/stg_transactions.sql` (materialised as a view)

**In:** the bronze Parquet, via `read_parquet('{{ var("raw_transactions") }}')`. **Out:** one row per invoice line for real products.

```sql
    invoice like 'C%'                                     as is_return,
    customer_id,
    country,
    invoice_ts,
    cast(date_trunc('week', invoice_ts) as date)          as week_start
from src
where regexp_matches(upper(trim(stock_code)), '^[0-9]{5}[A-Z]{0,2}$')
  and unit_price > 0
  and quantity <> 0
```

- `is_return`: in this dataset, cancelled invoices start with "C". I flag them rather than delete them, because return rate is a metric I need later.
- `week_start`: every line gets the Monday of its week, which is the grain of everything downstream.
- The `where` clause keeps only real product codes: five digits plus up to two letters (like `85123A`). That drops postage (`POST`), fees, manual adjustments (`M`), bank charges and test codes.
- `unit_price > 0` and `quantity <> 0` remove free adjustments and zero lines.

The model also builds a `line_id` by hashing several columns plus a row number, so every line has a unique key that a test can check.

**Why this way:** analysis needs product sales, not shipping charges. A read-only count of the view gives 1,055,162 lines (the "1.06m" figure), of which 18,285 are flagged as returns.

##### Step 3. Intermediate: one row per SKU per week

**Where:** `dbt/models/intermediate/int_sku_weekly.sql` (materialised as a table)

```sql
select
    stock_code,
    week_start,
    sum(case when not is_return then quantity else 0 end)              as units_sold,
    -sum(case when is_return then quantity else 0 end)                 as units_returned,
    sum(case when not is_return then line_revenue else 0 end)          as revenue,
    count(distinct case when not is_return then invoice end)           as orders,
    count(distinct case when not is_return then customer_id end)       as customers,
    mode(case when not is_return and quantity between 1 and 12 then unit_price end) as list_price
from {{ ref('stg_transactions') }}
group by 1, 2
```

- `units_sold` and `units_returned` are kept separate. Returns have negative quantities, so the minus sign makes returned units positive.
- `revenue` counts sales only.
- `orders` and `customers` are distinct counts per week.
- `list_price`: the most common price on small orders (1 to 12 units). This retailer also sells wholesale with quantity price breaks, so a big order at a lower unit price is not a markdown. Using the mode on small orders gives a fair "shelf price".
- `{{ ref('stg_transactions') }}` tells dbt this model depends on the staging model, so dbt builds them in the right order.

**Why this way:** SKU-week is the natural grain for retail: weekly sales are what merchandisers look at, and it's what the stall model needs. A read-only count gives 197,517 SKU-week rows.

##### Step 4. Gold: dimension, fact and mart

**Where:** `dbt/models/marts/dim_sku.sql`, `fct_sku_weekly.sql`, `mart_sku_health.sql`

**`dim_sku`** (one row per SKU): first and last sale week, launch cohort (year and quarter of first sale), launch list price (most common list price in the first 8 weeks), a Christmas flag from the description, and `launch_observed`.

```sql
    b.first_sale_week >= date '2010-01-01'                                  as launch_observed,
    strftime(b.first_sale_week, '%Y') || '-Q' || cast(quarter(b.first_sale_week) as varchar) as launch_cohort,
    lp.launch_list_price,
    regexp_matches(upper(n.description), 'CHRISTMAS|XMAS|ADVENT|SANTA|REINDEER') as is_seasonal_christmas
```

- `launch_observed`: the data starts in December 2009, so a SKU first seen then was probably on sale before. Its true launch is unknown (left-censored). Only SKUs first seen from January 2010 count as observed launches.
- `launch_cohort`: like "2010-Q3", used to compare like with like in part 05.
- `is_seasonal_christmas`: a simple keyword flag.

**`fct_sku_weekly`** (SKU-week fact): weeks since launch and markdown versus launch price.

```sql
    -- Returns can arrive before a SKU's first recorded sale (sold before the data starts).
    case when w.week_start >= d.first_sale_week
         then datediff('week', d.first_sale_week, w.week_start) end        as weeks_since_launch,
    ...
    case when d.launch_list_price > 0 and w.list_price is not null
         then greatest(0, 1 - w.list_price / d.launch_list_price) end      as markdown_pct
```

- `weeks_since_launch` is left empty (NULL) when the week is before the first sale. This is the fix for the 23 rows the test caught (section 5).
- `markdown_pct`: 1 minus current price over launch price, floored at 0. Launch price £2.00, this week £1.50: markdown 25%. A price rise counts as 0, not negative.

**`mart_sku_health`**: the merchandising view per SKU (explained in part 03).

**Why a dimension and a fact:** this is a star schema. The dimension holds things that describe a SKU once; the fact holds things that happen every week. Joins are simple and every dashboard can slice the fact by any attribute of the dimension.

##### Step 5. Tests on every layer

**Where:** `_staging.yml`, `_intermediate.yml`, `_marts.yml`, `dbt/macros/test_between.sql`, `dbt/macros/test_unique_combination.sql`, `dbt/tests/assert_revenue_reconciles.sql`

Generic tests are declared in YAML next to the model:

```yaml
  - name: fct_sku_weekly
    columns:
      - name: stock_code
        tests: [not_null, {relationships: {arguments: {to: ref('dim_sku'), field: stock_code}}}]
      - name: weeks_since_launch
        tests: [{between: {arguments: {min_value: 0, max_value: 120}}}]
      - name: markdown_pct
        tests: [{between: {arguments: {min_value: 0, max_value: 1}}}]
```

- `not_null`: every fact row has a SKU.
- `relationships`: every SKU in the fact exists in the dimension (no orphan rows).
- `between`: a custom test I wrote as a macro. Weeks since launch must be 0 to 120; markdown 0 to 1.

The custom `between` test is just SQL that returns the bad rows:

```sql
{% test between(model, column_name, min_value, max_value) %}
select * from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}
```

A dbt test passes when the query returns zero rows. Note `is not null`: NULLs are allowed, which is why leaving `weeks_since_launch` empty for pre-launch returns makes the test pass honestly.

The singular test checks nothing is lost between layers:

```sql
-- Gold revenue must equal silver revenue (no rows lost or double-counted between layers).
with silver as (select sum(line_revenue) as r from {{ ref('stg_transactions') }} where not is_return),
gold as (select sum(revenue) as r from {{ ref('fct_sku_weekly') }})
select * from silver, gold where abs(silver.r - gold.r) > 0.01
```

If silver and gold revenue differ by more than a penny, the test returns a row and fails.

##### Step 6. The semantic layer (MetricFlow)

**Where:** `dbt/models/marts/_semantic.yml`, `metricflow_time_spine.sql`

```yaml
metrics:
  - name: return_rate
    label: Return rate
    description: Units returned as a share of units sold.
    type: ratio
    type_params: {numerator: units_returned, denominator: units_sold}
```

- Semantic models declare entities (`sku`, `sku_week`), dimensions (`week_start`, `launch_cohort`, `is_seasonal_christmas`) and measures (`units_sold`, `units_returned`, `revenue`, `avg_markdown_pct`).
- Metrics are defined once: units sold, units returned, revenue, return rate (a ratio of sums, not an average of weekly ratios) and average markdown.
- The time spine is a table of every day from 30 Nov 2009 to 31 Dec 2011, which MetricFlow needs to aggregate over time correctly.

**Why this way:** a ratio like return rate is easy to get wrong (averaging weekly percentages gives a different answer from total returns over total sales). Defining it once means every dashboard asks for `return_rate` and gets the same answer.

##### Step 7. Build everything with one command

`make dbt` runs `cd dbt && DBT_PROFILES_DIR=. dbt build`. `dbt build` runs models and tests in dependency order, and if a test fails, everything downstream of it is skipped.

`profiles.yml` points dbt at a local DuckDB file (`../data/warehouse.duckdb`, overridable with the `TF_WAREHOUSE` environment variable). Staging is a view; intermediate and marts are tables (`dbt_project.yml`).

---

#### 3. Concepts, from scratch

##### Analytics engineering
**Definition:** applying software engineering habits (version control, tests, documentation, modular code) to the SQL that turns raw data into analysis tables.
**Why it matters:** it's the difference between "a query on my laptop" and "a table the business can rely on".

##### Medallion layout: bronze, silver, gold
**Definition:** bronze = raw data as received; silver = cleaned, typed, filtered; gold = business-ready tables.
**Analogy:** a kitchen. Bronze is the delivery as it arrives, silver is washed and chopped, gold is the plated dish.
**Here:** bronze is the Parquet file, silver is `stg_transactions`, intermediate is `int_sku_weekly`, gold is `dim_sku`, `fct_sku_weekly`, `mart_sku_health`.

##### dbt model
**Definition:** a `.sql` file containing one `select`. dbt wraps it in `create view` or `create table` for you.
**Why it matters:** each step is small, readable and versioned in git.

##### Materialisation (view vs table)
**Definition:** a view stores the query and runs it every time; a table stores the result.
**Here:** staging is a view (cheap, always fresh from bronze); intermediate and marts are tables (fast to query repeatedly).

##### `ref()` and the DAG
**Definition:** `{{ ref('stg_transactions') }}` refers to another model. dbt reads all refs and builds a dependency graph (a DAG: directed acyclic graph), then runs models in order.
**Why it matters:** no hard-coded table names and no manual run order.

##### Sources and `var()`
**Definition:** a source is raw data dbt doesn't build. dbt has a formal `sources:` block for declaring them.
**Here:** I didn't declare a formal source. The raw Parquet path is a project variable (`vars: raw_transactions` in `dbt_project.yml`) read with `read_parquet('{{ var("raw_transactions") }}')`. A formal source block with freshness checks would be a sensible next step, especially on a cloud warehouse (part 13).

##### dbt tests: generic vs singular
- **Generic:** reusable, declared in YAML on a column: `unique`, `not_null`, `accepted_values`, `relationships`, plus my custom `between` and `unique_combination` macros.
- **Singular:** a one-off SQL file in `tests/`, like `assert_revenue_reconciles.sql`.
- **Rule for both:** the test query returns the bad rows. Zero rows = pass.

##### Grain
**Definition:** what one row represents. `stg_transactions` = one invoice line; `int_sku_weekly` = one SKU in one week; `dim_sku` = one SKU.
**Why it matters:** most analytics bugs are grain bugs (joining two tables at different grains and double-counting). The `unique_combination` test on `(stock_code, week_start)` proves the grain.

##### Star schema: dimension and fact tables
**Definition:** facts are events or measurements (weekly sales); dimensions describe the things involved (the SKU).
**Why it matters:** BI tools and semantic layers expect this shape.

##### Left-censoring
**Definition:** you can see something exists but not when it started, because your data starts after it did.
**Here:** SKUs already selling in December 2009 have an unknown launch date, so `launch_observed` is false for them.

##### Reconciliation test
**Definition:** check that a total is the same in two layers.
**Why it matters:** it catches silently dropped or duplicated rows from a bad join, which no column-level test would catch.

##### Semantic layer and MetricFlow
**Definition:** a layer that defines business metrics (measures, dimensions, entities) once, so any tool can query "revenue by launch cohort" and get the same answer. MetricFlow is dbt's semantic layer engine.
**Key words:** *entity* (a join key, like `sku`), *dimension* (something to group by), *measure* (an aggregation, like `sum(revenue)`), *metric* (what users ask for, built from measures), *time spine* (a calendar table).

##### DuckDB
**Definition:** an in-process analytical database. It runs inside Python or the dbt process, no server, and is very fast on columnar data.
**Analogy:** SQLite for analytics.
**Why it matters here:** free, local and fast enough for 1 million rows. The same dbt models can move to BigQuery or Snowflake later (part 13).

##### Parquet
**Definition:** a columnar file format. Data is stored column by column, compressed, with types.
**Why it matters:** a query that needs three columns only reads those three. Much faster and smaller than CSV or Excel.

##### Mode
**Definition:** the most common value.
**Here:** list price = mode of unit price on small orders, so one wholesale deal doesn't look like a markdown.

##### Data contracts (link to part 01)
dbt tests are the warehouse version of the data contract in part 01: rules about valid data, enforced automatically on every build.

---

#### 4. The real results, and how to read them

| What | Number | Source |
|---|---|---|
| Bronze rows | 1,067,371 | read-only count of `transactions.parquet` |
| Silver rows (real products) | 1,055,162 ("1.06m") | read-only count of `stg_transactions` |
| Of which returns | 18,285 | same |
| SKU-week rows (intermediate) | 197,517 | read-only count |
| SKUs in `dim_sku` | 4,707 | read-only count |
| SKUs with an observed launch | 1,706 | read-only count |
| Rows with `weeks_since_launch` left empty | 23 | read-only count of `fct_sku_weekly` |
| dbt build nodes | 28 = 6 models + 22 data tests, all passing | `dbt/target/run_results.json` |
| Date range | 1 Dec 2009 to 9 Dec 2011 | min/max `invoice_ts` |

**How to read it:**

- About 12,000 bronze lines (1,067,371 minus 1,055,162) are postage, fees, adjustments, zero-price or zero-quantity lines. Dropping them is correct for product analysis.
- **An important correction on "28 tests".** The README and the summaries say "28 dbt data tests". The last `dbt build` reports `PASS=28 ... TOTAL=28`, but `run_results.json` shows those 28 nodes are 6 models plus 22 data tests. The accurate phrasing is "22 data tests, and all 28 build steps pass".

The 22 data tests are: 5 on staging (line_id unique and not null, stock_code not null, unit_price between, week_start not null), 3 on intermediate (unique SKU-week combination, units_sold not null and between), 3 on `dim_sku`, 4 on `fct_sku_weekly`, 6 on `mart_sku_health`, and 1 singular revenue reconciliation.

---

#### 5. What went wrong or surprised me, and what it taught me

##### The test that caught 23 pre-launch returns
**What happened:** the first full `dbt build` failed. The log shows `19 of 28 FAIL 23 between_fct_sku_weekly_weeks_since_launch__120__0` and `Done. PASS=20 WARN=0 ERROR=1 SKIP=7`. The `between 0 and 120` test on weeks since launch found 23 rows with negative values.

**Why:** "launch" is defined as the first week with a sale. But some SKUs had returns before their first recorded sale. The customer bought before the data starts (December 2009), then returned it during the data window. So the return week is before the "launch" week, and weeks since launch comes out negative.

**The fix:** `fct_sku_weekly` now leaves `weeks_since_launch` NULL when the week is before the first sale, with a comment explaining why. The `between` test ignores NULLs, so it passes honestly: I didn't widen the range to make it pass.

**Also notice:** because the test failed, dbt skipped 7 downstream nodes. That's the point. A broken fact table never reached the mart or the model.

**What it taught me:** tests on assumptions ("weeks since launch can't be negative") find real-world quirks you'd never think to look for. And the right fix is to model the quirk explicitly, not to loosen the test.

##### Wholesale price breaks
This retailer sells to both consumers and wholesalers, so the same SKU appears at different unit prices in the same week. If I'd used average price, every bulk order would look like a markdown. Using the mode of small-order prices was a domain decision, not a technical one.

##### A small detail worth knowing
The intermediate table has 197,517 SKU-weeks and the fact table 197,497 (read-only counts). The 20-row difference comes from SKUs that only ever appear as returns, with no sale in the data: they never get a `dim_sku` row (which is built from weeks with sales), so the inner join drops them. They carry no sales revenue, which is why the reconciliation test still passes. It's a deliberate consequence of defining a SKU by its sales.

---

#### 6. Honest limits

- **Real open data, not fashion and not a customer.** It's a UK online gift and homeware retailer. I use it to build methods on real sales behaviour (launches, decay, markdowns, returns, seasonality).
- **No inventory data**, so true sell-through can't be computed (see part 03).
- Runs locally on DuckDB. The cloud warehouse version is part 13, planned.
- The raw path is a `var`, not a formally declared dbt source with freshness checks.
- The Christmas flag is a keyword match on descriptions, so it will miss some seasonal lines and catch the odd false positive.
- I haven't run the MetricFlow CLI queries as part of CI; the semantic layer is defined and parsed by dbt.

---

#### 7. How to run it yourself

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make retail     # python -m stock.ingest: download UCI data, land Parquet (bronze)
make dbt        # cd dbt && DBT_PROFILES_DIR=. dbt build  (models + tests)
```

`make stock` runs retail, dbt and every later stock step in one go. `python -m stock.ingest --force` rebuilds the Parquet file if it already exists. To look around:

```bash
cd dbt && DBT_PROFILES_DIR=. dbt ls          # list models and tests
cd dbt && DBT_PROFILES_DIR=. dbt test        # rerun tests only
```

---

#### 8. Glossary

- **Analytics engineering:** software habits applied to SQL data preparation.
- **Bronze / silver / gold:** raw / cleaned / business-ready layers.
- **dbt model:** one SQL select that dbt turns into a view or table.
- **Materialisation:** how a model is stored (view or table).
- **`ref()`:** a reference to another model that builds the dependency graph.
- **DAG:** directed acyclic graph, the order models run in.
- **`var()`:** a project variable, here the raw data path.
- **Source:** raw data declared to dbt but not built by it.
- **Generic test:** reusable column test declared in YAML.
- **Singular test:** one-off SQL test file.
- **Macro:** reusable Jinja/SQL function, such as the custom `between` test.
- **Grain:** what one row represents.
- **Star schema:** facts plus dimensions.
- **Dimension table:** describes entities (one row per SKU).
- **Fact table:** records events or measures (one row per SKU-week).
- **Left-censoring:** the start of something is before your data begins.
- **Reconciliation:** checking totals agree across layers.
- **Semantic layer:** one shared definition of each metric.
- **MetricFlow:** dbt's semantic layer engine.
- **Entity / dimension / measure / metric:** join key / group-by field / aggregation / user-facing number.
- **Time spine:** a calendar table used for time aggregation.
- **DuckDB:** in-process analytical database.
- **Parquet:** compressed, typed, columnar file format.
- **Mode:** most common value.
- **SKU:** stock-keeping unit, one product code.
- **Markdown:** a price reduction from the launch price.

---

## Part 03: Merchandising analytics

**Discipline:** Data Analytics / Data Engineering (primary / secondary)  
**Methodology:** `dbt/models/marts/mart_sku_health.sql` builds a dense weekly calendar per SKU (zero weeks included), an 8-week rolling average with window functions, and per-SKU ABC (cumulative revenue share at 80% and 95%), XYZ (coefficient of variation below 0.5 or 1.0), velocity ratio and a selling / slowing / stopped status as of 5 Dec 2011.  
**Tools:** SQL, dbt, Jinja, DuckDB  
**Status:** Maybe later: part of the dbt pipeline (Part 02).

**Build state:** Built · **Data label:** Real open retail data  

### In one line
Shows which lines are selling, slowing or stopped, with the classic merchandising views.

### Why it matters
Unsold stock is a merchandising problem first: slowing and stopped lines are the stock a brand will later need a home for. Proof of build, not the product.

### Data
dbt marts built in part 2.

### Method
ABC classification by revenue share (A top 80%, B next 15%, C rest); XYZ by demand variability (coefficient of variation of weekly units including zero weeks); sales velocity (last 8 weeks vs best 8-week run); markdown depth vs launch list price; return rate; launch cohorts by quarter; status selling / slowing / stopped.

### Tools
SQL, dbt, DuckDB

### Result
4,707 SKUs classified (e.g. 1,573 stopped, 1,333 slowing, 1,801 selling at 5 Dec 2011).

### Honest limits
The data has no inventory, so true sell-through and weeks of cover can't be computed honestly; velocity is used instead.

### Where it lives
dbt/models/marts/mart_sku_health.sql

### Part 03 step by step

**Build state:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II). Not fashion, not a customer.
**Code:** `dbt/models/marts/mart_sku_health.sql`, tests in `dbt/models/marts/_marts.yml`
**Numbers from:** README, subproject summary, and read-only queries of `data/warehouse.duckdb` (labelled)

---

#### 1. The question this stage answers

At a given date, which product lines are selling, which are slowing, and which have stopped, and how important is each one to the business?

A fashion brand cares because unsold stock starts as a merchandising problem: lines that slow down and don't get acted on become end-of-season surplus. Since July 2026 large companies in the EU can't simply destroy unsold clothing (Regulation (EU) 2024/1781, Article 25), so knowing early which lines are stalling matters more than it used to.

---

#### 2. The pipeline, step by step

Everything in this part is one dbt model, `mart_sku_health.sql`, built on top of the part 02 tables (`dim_sku`, `fct_sku_weekly`). It's written as a chain of CTEs (common table expressions), each doing one job.

##### Step 1. Fix the "as of" date

```sql
{% set as_of = "date '2011-12-05'" %}
```

- A Jinja variable. Every "recent" calculation is relative to the week starting Monday 5 December 2011, the last week in the data (the data ends on Friday 9 December). The comment at the top of the file says "9 Dec 2011", the end of that week; the YAML description says "at 5 Dec 2011", the week start. Both refer to the same final week.

**Why:** a health view is always "as of" a date. Fixing it makes the output reproducible.

##### Step 2. Build a dense calendar (including zero weeks)

```sql
calendar as (
    select stock_code, unnest(generate_series(first_sale_week, {{ as_of }}, interval 1 week))::date as week_start
    from d
),
dense as (
    select c.stock_code, c.week_start, coalesce(f.units_sold, 0) as units
    from calendar c left join f using (stock_code, week_start)
),
```

- `calendar`: for each SKU, one row for every week from its first sale to the as-of date.
- `dense`: left join the actual sales onto that calendar, and fill missing weeks with 0.

**In:** `dim_sku` (first sale week) and `fct_sku_weekly` (weeks with activity). **Out:** a complete SKU by week grid.

**Why this way:** the fact table only has rows for weeks with activity. If you calculate an average or a variability from it directly, you silently ignore all the weeks where nothing sold, which makes a stopped product look healthy. This is the single most important step in the model.

##### Step 3. Rolling 8-week average (for velocity)

```sql
rolling as (
    select stock_code, week_start,
           avg(units) over (partition by stock_code order by week_start rows between 7 preceding and current row) as avg8
    from dense
),
```

- A window function: for each SKU and week, average the units of this week and the 7 before it.
- `partition by stock_code`: restart for each product.
- `rows between 7 preceding and current row`: an 8-row window.

##### Step 4. Per-SKU summaries

```sql
per_sku as (
    select
        stock_code,
        sum(units)                                         as units_total,
        count(*)                                           as weeks_live,
        avg(units)                                         as units_per_week,
        stddev_pop(units) / nullif(avg(units), 0)          as demand_cv
    from dense group by 1
),
velocity as (
    select stock_code,
           max(avg8)                                                        as peak_avg8,
           max(case when week_start = {{ as_of }} then avg8 end)            as last_avg8
    from rolling group by 1
),
```

- `demand_cv`: coefficient of variation (standard deviation over mean) of weekly units, including the zero weeks. `nullif(..., 0)` avoids dividing by zero.
- `peak_avg8`: the best 8-week run the product ever had.
- `last_avg8`: the last 8 weeks up to the as-of date.

##### Step 5. Money, returns, markdown and ABC ranking

```sql
ranked as (
    select m.*, sum(revenue) over (order by revenue desc rows unbounded preceding)
                / sum(revenue) over () as cum_share
    from money m
)
```

- Sort all SKUs by revenue, highest first.
- Running total of revenue divided by total revenue gives each SKU's cumulative share. The top seller might have `cum_share` 0.01; the SKU at which 80% of revenue has been reached has 0.80.

##### Step 6. Classify

```sql
    case when r.cum_share <= 0.80 then 'A' when r.cum_share <= 0.95 then 'B' else 'C' end as abc_class,
    case when p.demand_cv < 0.5 then 'X' when p.demand_cv < 1.0 then 'Y' else 'Z' end  as xyz_class,
    case
        when datediff('week', d.last_sale_week, {{ as_of }}) >= 12 then 'stopped'
        when coalesce(v.last_avg8 / nullif(v.peak_avg8, 0), 0) < 0.25 then 'slowing'
        else 'selling'
    end                                                                     as stock_status
```

- **ABC:** A = SKUs making up the top 80% of revenue, B = the next 15%, C = the rest.
- **XYZ:** X = steady demand (CV under 0.5), Y = variable (0.5 to 1), Z = erratic (1 or more).
- **Status:** stopped = no sale for 12 weeks or more; slowing = last 8 weeks below 25% of the best 8 weeks; otherwise selling.

The output also includes `return_rate` (units returned over units sold), `max_markdown_pct` (deepest markdown vs launch price) and `velocity_ratio` (last 8 weeks over peak, 1 = at peak, 0 = stopped).

##### Step 7. Test the output

From `_marts.yml`: `stock_code` unique and not null; `abc_class` in A/B/C; `xyz_class` in X/Y/Z; `stock_status` in selling/slowing/stopped; `velocity_ratio` between 0 and 1. These run on every `dbt build`.

**Why the tests matter here:** a velocity ratio above 1 would mean the last 8 weeks beat the best 8 weeks, which is impossible by construction. If it ever happened, something upstream would be broken.

---

#### 3. Concepts, from scratch

##### SKU
**Definition:** stock-keeping unit, one product code. In fashion, often one style in one colour (and sometimes one size).

##### ABC classification
**Definition:** rank products by contribution (here, revenue) and split by cumulative share. It's the Pareto idea: a small share of products makes most of the money.
**Worked example:** five products with revenue 50, 30, 10, 6, 4 (total 100). Cumulative shares: 0.50, 0.80, 0.90, 0.96, 1.00. So the first two are A, the third is B (up to 0.95), and the last two are C.
**Why it matters:** a stalling A line is an urgent revenue problem; a stalling C line may just need a markdown or a sale elsewhere.

##### XYZ classification
**Definition:** classify products by how predictable their demand is.
**Why it matters:** X lines are easy to forecast and replenish; Z lines are lumpy and risky to over-buy.

##### Coefficient of variation (CV)
**Definition:** standard deviation divided by mean. A unit-free measure of how spread out something is relative to its size.
**Worked example:** weekly units 10, 10, 10, 10: SD 0, CV 0 (perfectly steady). Weekly units 0, 0, 40, 0: mean 10, population SD about 17.3, CV about 1.7 (erratic).
**Why it matters here:** including zero weeks is what makes CV honest. Without them, the second example would look like "40 every week" and CV 0.

##### Population vs sample standard deviation
`stddev_pop` divides by n; `stddev_samp` divides by n - 1. With many weeks per SKU it barely matters; I used population because I'm describing the full history, not estimating from a sample.

##### Sales velocity and velocity ratio
**Definition:** velocity is the rate of sale (units per week). The velocity ratio compares recent velocity with the product's own peak.
**Worked example:** best 8-week run averaged 40 units a week; the last 8 weeks averaged 8. Ratio 0.2, which is under 0.25, so "slowing".
**Why it matters:** comparing a product with its own peak is fairer than comparing it with other products of very different sizes.

##### Sell-through and weeks of cover (and why I didn't use them)
**Definition:** sell-through = units sold / units received (or available). Weeks of cover = stock on hand / weekly sales.
**Why not here:** this dataset has no inventory figures. Calling velocity "sell-through" would be wrong, so I don't.

##### Markdown depth
**Definition:** how far the price has dropped from the launch price: 1 - current / launch.
**Here:** `max_markdown_pct` is the deepest markdown a SKU ever had, from `fct_sku_weekly`.

##### Return rate
**Definition:** units returned / units sold.
**Why it matters:** in fashion, returns feed straight back into unsold stock.

##### Launch cohort
**Definition:** group products by when they launched (here, year and quarter). Compare a product with others launched at the same time, so seasonality doesn't mislead you.

##### Window functions
**Definition:** SQL functions that calculate across a set of rows related to the current row, without collapsing them like `group by` does. `avg(...) over (partition by ... order by ... rows between ...)` is a rolling average.
**Why it matters:** rolling averages and running totals (for ABC) are both window functions here.

##### Dense vs sparse time series
**Definition:** a sparse series only has rows where something happened; a dense one has a row for every period, with zeros where nothing happened.
**Why it matters:** averages, CV and velocity are all wrong on sparse data.

##### CTE (common table expression)
**Definition:** a named sub-query in a `with` clause. Lets you write a long query as readable steps.

##### Jinja in dbt
**Definition:** a templating language. `{% set as_of = ... %}` and `{{ as_of }}` let me define the date once and reuse it.

---

#### 4. The real results, and how to read them

**4,707 SKUs classified** (README; confirmed by read-only query).

| Status (as of week of 5 Dec 2011) | SKUs |
|---|---|
| Selling | 1,801 |
| Slowing | 1,333 |
| Stopped | 1,573 |

Read-only queries of `mart_sku_health` also give:

| ABC class | SKUs | | XYZ class | SKUs |
|---|---|---|---|---|
| A (top 80% of revenue) | 1,024 | | X (CV < 0.5) | 43 |
| B (next 15%) | 1,260 | | Y (0.5 to 1) | 616 |
| C (last 5%) | 2,423 | | Z (1 or more) | 4,048 |

ABC by status (read-only query):

| | Selling | Slowing | Stopped |
|---|---|---|---|
| A | 612 | 329 | 83 |
| B | 556 | 425 | 279 |
| C | 633 | 579 | 1,211 |

**How to read it:**

- About a third of SKUs have stopped (1,573 of 4,707). That's typical of a gift retailer with many seasonal and one-off lines.
- **ABC:** about 22% of SKUs (1,024) make 80% of revenue. Classic Pareto.
- **XYZ is almost all Z.** 4,048 of 4,707 SKUs have erratic weekly demand. That's partly real (seasonal gifts, wholesale orders) and partly a consequence of including zero weeks, which is deliberate. It tells me XYZ with these cut-offs doesn't separate products much in this data; for fashion data I'd recalibrate the thresholds or compute CV over the selling season only.
- **The actionable cell:** 329 A lines are slowing. Those are the high-revenue lines worth looking at first. Most stopped lines (1,211) are C, which is reassuring.

---

#### 5. What went wrong or surprised me, and what it taught me

- **Zero weeks change everything.** My first instinct was to compute averages from the fact table. Building the dense calendar was the moment I understood why stopped lines can look fine in sparse data.
- **XYZ didn't discriminate.** I expected a spread across X, Y and Z. Almost everything being Z taught me that textbook thresholds come from steady replenishment businesses, and need adjusting for seasonal or wholesale-heavy ones.
- **Not calling it sell-through.** The temptation is to use the familiar term. Saying "the data has no stock figures, so this is velocity" is more honest than over-claiming.
- **Inherited from part 02:** the dbt test that caught 23 pre-launch returns (part 02) protects this mart, because dbt skips downstream models when an upstream test fails.

---

#### 6. Honest limits

- **Real open data, not fashion and not a customer.**
- **No inventory**, so no sell-through, weeks of cover or stock value at risk.
- **Rule-based thresholds** (12 weeks without a sale, 25% of peak, 80/95 for ABC, 0.5/1.0 for XYZ). They're standard starting points, not tuned to a business.
- **The last week is partial:** the data ends on Friday 9 December, so the final week has five days of sales at most, which slightly understates the last 8-week average.
- Status is a snapshot at one date. For a live tool it would be recalculated weekly.
- Revenue-based ABC favours expensive items. Margin-based ABC would be better if cost data existed.

---

#### 7. How to run it yourself

```bash
make retail     # bronze Parquet (if not already there)
make dbt        # builds all models, including mart_sku_health, and runs the tests
```

Or just this model and its upstream dependencies:

```bash
cd dbt && DBT_PROFILES_DIR=. dbt build --select +mart_sku_health
```

---

#### 8. Glossary

- **SKU:** one product code.
- **ABC classification:** ranking by share of revenue (80% / 15% / 5%).
- **XYZ classification:** ranking by demand variability.
- **Coefficient of variation:** standard deviation divided by mean.
- **Velocity:** units sold per week.
- **Velocity ratio:** recent velocity divided by peak velocity.
- **Sell-through:** units sold divided by units available (needs inventory).
- **Weeks of cover:** stock on hand divided by weekly sales (needs inventory).
- **Markdown depth:** fall in price from launch price.
- **Return rate:** units returned divided by units sold.
- **Launch cohort:** products grouped by launch quarter.
- **Dense time series:** one row per period, zeros included.
- **Window function:** a calculation over related rows, such as a rolling average.
- **CTE:** a named step in a `with` query.
- **Jinja:** the templating language dbt uses.
- **As-of date:** the date a snapshot describes.
- **Pareto principle:** a small share of items accounts for most of the value.
