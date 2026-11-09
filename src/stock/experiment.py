"""Experimentation for Thread Futures.

Part A (real data): does a markdown actually clear stock?
    Stacked difference-in-differences: each SKU whose list price first dropped by 15%+ is
    compared with the 5 never-marked-down SKUs from its launch cohort whose sales were most
    similar beforehand, over the same calendar weeks (4 before, 4 after). Standard errors
    clustered by SKU. Observational, so it rests on parallel trends; a placebo test on the
    pre-period checks that.

Part B (pilot design, simulated): how many batches would a randomised routing pilot need?
    Power analysis for "routed through Thread Futures" vs "brand's usual liquidator", then
    one simulated pilot analysed with Welch's t-test and a bootstrap confidence interval.
    The simulation inputs are assumptions, stated below, until a pilot provides real data.

    python -m stock.experiment
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.power import TTestIndPower

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT = ROOT / "models" / "experiment_results.json"
WINDOW = 4
THRESHOLD = 0.15

K_CONTROLS = 5

PANEL_SQL = f"""
with first_md as (
    select stock_code, min(week_start) as md_week
    from fct_sku_weekly
    where markdown_pct >= {THRESHOLD} and weeks_since_launch >= {WINDOW}
    group by 1
),
ever_md as (select distinct stock_code from fct_sku_weekly where markdown_pct >= 0.05),
treated as (
    select f.stock_code, f.md_week, d.launch_cohort
    from first_md f join dim_sku d using (stock_code)
    where f.md_week between date '2010-03-01' and date '2011-10-01'
),
controls as (
    select d.stock_code, d.launch_cohort from dim_sku d
    where d.stock_code not in (select stock_code from ever_md)
),
-- One "stack" per marked-down SKU: the SKU itself plus every never-marked-down SKU from
-- its launch cohort, observed over the same calendar weeks.
units as (
    select t.stock_code as stack, t.stock_code, t.md_week, 1 as treated from treated t
    union all
    select t.stock_code, c.stock_code, t.md_week, 0 from treated t join controls c using (launch_cohort)
),
cal as (select u.*, unnest(range(-{WINDOW}, {WINDOW})) as rel_week from units u),
panel as (
    select c.stack, c.stock_code, c.treated, c.rel_week, ln(1 + coalesce(f.units_sold, 0)) as y,
           coalesce(f.units_sold, 0) as units
    from cal c left join fct_sku_weekly f
      on f.stock_code = c.stock_code and f.week_start = (c.md_week + to_weeks(c.rel_week))::date
),
unit_summary as (
    select stack, stock_code, treated,
           sum(units) filter (where rel_week < 0)                              as pre_units,
           avg(y) filter (where rel_week < 0)                                   as pre_y,
           avg(y) filter (where rel_week >= 0)                                  as post_y,
           avg(y) filter (where rel_week in (-2, -1)) - avg(y) filter (where rel_week in (-4, -3)) as placebo_diff
    from panel group by all
),
-- Keep the K controls whose pre-markdown sales are closest to the treated SKU's.
matched as (
    select u.*, row_number() over (partition by u.stack order by abs(u.pre_units - t.pre_units)) as rk
    from unit_summary u join unit_summary t on t.stack = u.stack and t.treated = 1
    where u.treated = 0 and u.pre_units > 0
)
select stack, stock_code, treated, pre_units, post_y - pre_y as diff, placebo_diff
from unit_summary where treated = 1 and pre_units > 0
union all
select stack, stock_code, treated, pre_units, post_y - pre_y, placebo_diff from matched where rk <= {K_CONTROLS}
"""


def _stacked(df: pd.DataFrame, outcome: str):
    # Unit fixed effects are differenced out (post minus pre); stack fixed effects hold
    # calendar weeks and launch cohort constant within each comparison.
    return smf.ols(f"{outcome} ~ treated + C(stack)", data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df.stock_code.astype("category").cat.codes})


def markdown_did(con) -> dict:
    df = con.execute(PANEL_SQL).df()
    df = df[df.groupby("stack").treated.transform("sum").eq(1) & df.groupby("stack").treated.transform("size").gt(1)]
    fit, plac = _stacked(df, "diff"), _stacked(df, "placebo_diff")
    b, se = fit.params["treated"], fit.bse["treated"]
    lo, hi = b - 1.96 * se, b + 1.96 * se
    return {
        "design": f"stacked difference-in-differences, {WINDOW} weeks either side, {K_CONTROLS} nearest-sales controls per SKU from the same launch cohort",
        "treated_skus": int(df.treated.sum()),
        "control_skus": int(df[df.treated == 0].stock_code.nunique()),
        "effect_log_units": round(float(b), 4),
        "effect_pct": round(float(np.expm1(b) * 100), 1),
        "ci95_pct": [round(float(np.expm1(lo) * 100), 1), round(float(np.expm1(hi) * 100), 1)],
        "p_value": float(f"{fit.pvalues['treated']:.3g}"),
        "placebo_pre_trend_effect": round(float(plac.params["treated"]), 4),
        "placebo_p_value": float(f"{plac.pvalues['treated']:.3g}"),
    }


# Pilot assumptions (to be replaced by real pilot data). Recovery = cash recovered per £ of
# original retail value. Liquidators commonly pay low single-digit to ~10p in the pound;
# these are planning assumptions, not measured results.
PILOT = {"liquidator_mean": 0.08, "routed_mean": 0.11, "sd": 0.06, "alpha": 0.05, "power": 0.8}


def pilot_design(seed: int = 3) -> dict:
    d = (PILOT["routed_mean"] - PILOT["liquidator_mean"]) / PILOT["sd"]
    n = TTestIndPower().solve_power(effect_size=d, alpha=PILOT["alpha"], power=PILOT["power"])
    n = int(np.ceil(n))
    curve = {int(k): round(float(TTestIndPower().power(d, k, PILOT["alpha"])), 3) for k in (10, 20, 30, 40, 60, 80)}
    rng = np.random.default_rng(seed)
    a = rng.normal(PILOT["liquidator_mean"], PILOT["sd"], n).clip(0)
    b = rng.normal(PILOT["routed_mean"], PILOT["sd"], n).clip(0)
    t = stats.ttest_ind(b, a, equal_var=False)
    boots = [rng.choice(b, n).mean() - rng.choice(a, n).mean() for _ in range(5000)]
    return {
        "assumptions": PILOT,
        "effect_size_d": round(float(d), 3),
        "batches_per_arm": n,
        "power_by_batches_per_arm": curve,
        "simulated_pilot": {
            "uplift_pence_per_pound": round(float((b.mean() - a.mean()) * 100), 2),
            "welch_p_value": float(f"{t.pvalue:.3g}"),
            "bootstrap_ci95_pence": [round(float(np.percentile(boots, 2.5) * 100), 2),
                                     round(float(np.percentile(boots, 97.5) * 100), 2)],
        },
    }


def main() -> dict:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    res = {"markdown_did": markdown_did(con), "pilot_design": pilot_design()}
    OUT.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    main()
