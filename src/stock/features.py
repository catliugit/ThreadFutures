"""Early-life features for 'will this line stop selling?'.

For every SKU whose launch we observe, look only at its first 12 weeks on sale and ask
whether demand collapses in weeks 12-25 (average weekly units below 20% of the first 12
weeks). A line that stalls like that is the line most likely to end the season as
unsold stock, so this is the signal Thread Futures needs before stock goes unsold.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
EARLY_WEEKS = 12
LATE_WEEKS = 14          # weeks 12-25
STALL_RATIO = 0.20
LAST_LAUNCH = "2011-06-06"   # 26 weeks before the data ends, so every outcome is observed
TRAIN_BEFORE = "2010-10-01"  # time-based split: train on earlier launches, test on later

FEATURES = [
    "early_units_per_week", "early_trend", "early_zero_week_share", "early_customers",
    "early_orders", "early_return_rate", "early_max_markdown", "launch_list_price",
    "launch_month", "is_seasonal_christmas",
]

SQL = f"""
with skus as (
    select stock_code, first_sale_week, launch_cohort, launch_list_price, is_seasonal_christmas
    from dim_sku
    where launch_observed and first_sale_week <= date '{LAST_LAUNCH}'
),
grid as (
    select s.*, unnest(range(0, {EARLY_WEEKS + LATE_WEEKS})) as wk from skus s
),
weekly as (
    select g.stock_code, g.wk,
           coalesce(f.units_sold, 0) as units, coalesce(f.units_returned, 0) as returned,
           coalesce(f.customers, 0) as customers, coalesce(f.orders, 0) as orders,
           coalesce(f.markdown_pct, 0) as markdown
    from grid g
    left join fct_sku_weekly f
      on f.stock_code = g.stock_code and f.weeks_since_launch = g.wk
)
select
    s.stock_code, s.first_sale_week, s.launch_cohort,
    avg(units) filter (where wk < {EARLY_WEEKS})                                  as early_units_per_week,
    (avg(units) filter (where wk between 8 and 11) + 1)
      / (avg(units) filter (where wk between 0 and 3) + 1)                        as early_trend,
    avg((units = 0)::int) filter (where wk < {EARLY_WEEKS})                       as early_zero_week_share,
    sum(customers) filter (where wk < {EARLY_WEEKS})                              as early_customers,
    sum(orders) filter (where wk < {EARLY_WEEKS})                                 as early_orders,
    sum(returned) filter (where wk < {EARLY_WEEKS})
      / nullif(sum(units) filter (where wk < {EARLY_WEEKS}), 0)                   as early_return_rate,
    max(markdown) filter (where wk < {EARLY_WEEKS})                               as early_max_markdown,
    coalesce(s.launch_list_price, 0)                                              as launch_list_price,
    month(s.first_sale_week)                                                      as launch_month,
    s.is_seasonal_christmas::int                                                  as is_seasonal_christmas,
    avg(units) filter (where wk >= {EARLY_WEEKS})                                 as late_units_per_week
from weekly w join skus s using (stock_code)
group by all
"""


def load(warehouse: Path = WAREHOUSE) -> pd.DataFrame:
    con = duckdb.connect(str(warehouse), read_only=True)
    df = con.execute(SQL).df()
    con.close()
    df["early_return_rate"] = df["early_return_rate"].fillna(0).clip(0, 1)
    df[FEATURES] = df[FEATURES].astype(float)
    df["stalled"] = (df["late_units_per_week"] < STALL_RATIO * df["early_units_per_week"]).astype(int)
    df["split"] = (df["first_sale_week"] < pd.Timestamp(TRAIN_BEFORE)).map({True: "train", False: "test"})
    return df
