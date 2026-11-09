# Part 03: Merchandising analytics, step by step

**Status:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II). Not fashion, not a customer.
**Code:** `dbt/models/marts/mart_sku_health.sql`, tests in `dbt/models/marts/_marts.yml`
**Numbers from:** README, subproject summary, and read-only queries of `data/warehouse.duckdb` (labelled)

---

## 1. The question this stage answers

At a given date, which product lines are selling, which are slowing, and which have stopped, and how important is each one to the business?

A fashion brand cares because unsold stock starts as a merchandising problem: lines that slow down and don't get acted on become end-of-season surplus. Since July 2026 large companies in the EU can't simply destroy unsold clothing (Regulation (EU) 2024/1781, Article 25), so knowing early which lines are stalling matters more than it used to.

---

## 2. The pipeline, step by step

Everything in this part is one dbt model, `mart_sku_health.sql`, built on top of the part 02 tables (`dim_sku`, `fct_sku_weekly`). It's written as a chain of CTEs (common table expressions), each doing one job.

### Step 1. Fix the "as of" date

```sql
{% set as_of = "date '2011-12-05'" %}
```

- A Jinja variable. Every "recent" calculation is relative to the week starting Monday 5 December 2011, the last week in the data (the data ends on Friday 9 December). The comment at the top of the file says "9 Dec 2011", the end of that week; the YAML description says "at 5 Dec 2011", the week start. Both refer to the same final week.

**Why:** a health view is always "as of" a date. Fixing it makes the output reproducible.

### Step 2. Build a dense calendar (including zero weeks)

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

### Step 3. Rolling 8-week average (for velocity)

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

### Step 4. Per-SKU summaries

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

### Step 5. Money, returns, markdown and ABC ranking

```sql
ranked as (
    select m.*, sum(revenue) over (order by revenue desc rows unbounded preceding)
                / sum(revenue) over () as cum_share
    from money m
)
```

- Sort all SKUs by revenue, highest first.
- Running total of revenue divided by total revenue gives each SKU's cumulative share. The top seller might have `cum_share` 0.01; the SKU at which 80% of revenue has been reached has 0.80.

### Step 6. Classify

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

### Step 7. Test the output

From `_marts.yml`: `stock_code` unique and not null; `abc_class` in A/B/C; `xyz_class` in X/Y/Z; `stock_status` in selling/slowing/stopped; `velocity_ratio` between 0 and 1. These run on every `dbt build`.

**Why the tests matter here:** a velocity ratio above 1 would mean the last 8 weeks beat the best 8 weeks, which is impossible by construction. If it ever happened, something upstream would be broken.

---

## 3. Concepts, from scratch

### SKU
**Definition:** stock-keeping unit, one product code. In fashion, often one style in one colour (and sometimes one size).

### ABC classification
**Definition:** rank products by contribution (here, revenue) and split by cumulative share. It's the Pareto idea: a small share of products makes most of the money.
**Worked example:** five products with revenue 50, 30, 10, 6, 4 (total 100). Cumulative shares: 0.50, 0.80, 0.90, 0.96, 1.00. So the first two are A, the third is B (up to 0.95), and the last two are C.
**Why it matters:** a stalling A line is an urgent revenue problem; a stalling C line may just need clearing.

### XYZ classification
**Definition:** classify products by how predictable their demand is.
**Why it matters:** X lines are easy to forecast and replenish; Z lines are lumpy and risky to over-buy.

### Coefficient of variation (CV)
**Definition:** standard deviation divided by mean. A unit-free measure of how spread out something is relative to its size.
**Worked example:** weekly units 10, 10, 10, 10: SD 0, CV 0 (perfectly steady). Weekly units 0, 0, 40, 0: mean 10, population SD about 17.3, CV about 1.7 (erratic).
**Why it matters here:** including zero weeks is what makes CV honest. Without them, the second example would look like "40 every week" and CV 0.

### Population vs sample standard deviation
`stddev_pop` divides by n; `stddev_samp` divides by n - 1. With many weeks per SKU it barely matters; I used population because I'm describing the full history, not estimating from a sample.

### Sales velocity and velocity ratio
**Definition:** velocity is the rate of sale (units per week). The velocity ratio compares recent velocity with the product's own peak.
**Worked example:** best 8-week run averaged 40 units a week; the last 8 weeks averaged 8. Ratio 0.2, which is under 0.25, so "slowing".
**Why it matters:** comparing a product with its own peak is fairer than comparing it with other products of very different sizes.

### Sell-through and weeks of cover (and why I didn't use them)
**Definition:** sell-through = units sold / units received (or available). Weeks of cover = stock on hand / weekly sales.
**Why not here:** this dataset has no inventory figures. Calling velocity "sell-through" would be wrong, so I don't.

### Markdown depth
**Definition:** how far the price has dropped from the launch price: 1 - current / launch.
**Here:** `max_markdown_pct` is the deepest markdown a SKU ever had, from `fct_sku_weekly`.

### Return rate
**Definition:** units returned / units sold.
**Why it matters:** in fashion, returns feed straight back into unsold stock.

### Launch cohort
**Definition:** group products by when they launched (here, year and quarter). Compare a product with others launched at the same time, so seasonality doesn't mislead you.

### Window functions
**Definition:** SQL functions that calculate across a set of rows related to the current row, without collapsing them like `group by` does. `avg(...) over (partition by ... order by ... rows between ...)` is a rolling average.
**Why it matters:** rolling averages and running totals (for ABC) are both window functions here.

### Dense vs sparse time series
**Definition:** a sparse series only has rows where something happened; a dense one has a row for every period, with zeros where nothing happened.
**Why it matters:** averages, CV and velocity are all wrong on sparse data.

### CTE (common table expression)
**Definition:** a named sub-query in a `with` clause. Lets you write a long query as readable steps.

### Jinja in dbt
**Definition:** a templating language. `{% set as_of = ... %}` and `{{ as_of }}` let me define the date once and reuse it.

---

## 4. The real results, and how to read them

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

## 5. What went wrong or surprised me, and what it taught me

- **Zero weeks change everything.** My first instinct was to compute averages from the fact table. Building the dense calendar was the moment I understood why stopped lines can look fine in sparse data.
- **XYZ didn't discriminate.** I expected a spread across X, Y and Z. Almost everything being Z taught me that textbook thresholds come from steady replenishment businesses, and need adjusting for seasonal or wholesale-heavy ones.
- **Not calling it sell-through.** The temptation is to use the familiar term. Saying "the data has no stock figures, so this is velocity" is more honest than over-claiming.
- **Inherited from part 02:** the dbt test that caught 23 pre-launch returns (part 02) protects this mart, because dbt skips downstream models when an upstream test fails.

---

## 6. Honest limits

- **Real open data, not fashion and not a customer.**
- **No inventory**, so no sell-through, weeks of cover or stock value at risk.
- **Rule-based thresholds** (12 weeks without a sale, 25% of peak, 80/95 for ABC, 0.5/1.0 for XYZ). They're standard starting points, not tuned to a business.
- **The last week is partial:** the data ends on Friday 9 December, so the final week has five days of sales at most, which slightly understates the last 8-week average.
- Status is a snapshot at one date. For a live tool it would be recalculated weekly.
- Revenue-based ABC favours expensive items. Margin-based ABC would be better if cost data existed.

---

## 7. How to run it yourself

```bash
make retail     # bronze Parquet (if not already there)
make dbt        # builds all models, including mart_sku_health, and runs the tests
```

Or just this model and its upstream dependencies:

```bash
cd dbt && DBT_PROFILES_DIR=. dbt build --select +mart_sku_health
```

---

## 8. Glossary

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
