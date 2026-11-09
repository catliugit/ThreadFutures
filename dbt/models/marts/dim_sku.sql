-- Gold: one row per SKU. Launch = first week with a sale. Launches before Jan 2010
-- are treated as unknown (left-censored), because the data starts in Dec 2009.
with weekly as (select * from {{ ref('int_sku_weekly') }} where units_sold > 0),
names as (
    select stock_code, mode(description) as description
    from {{ ref('stg_transactions') }} group by 1
),
bounds as (
    select stock_code, min(week_start) as first_sale_week, max(week_start) as last_sale_week
    from weekly group by 1
),
launch_price as (
    select w.stock_code, mode(w.list_price) as launch_list_price
    from weekly w join bounds b using (stock_code)
    where w.week_start < b.first_sale_week + interval 8 week
    group by 1
)
select
    b.stock_code,
    n.description,
    b.first_sale_week,
    b.last_sale_week,
    b.first_sale_week >= date '2010-01-01'                                  as launch_observed,
    strftime(b.first_sale_week, '%Y') || '-Q' || cast(quarter(b.first_sale_week) as varchar) as launch_cohort,
    lp.launch_list_price,
    regexp_matches(upper(n.description), 'CHRISTMAS|XMAS|ADVENT|SANTA|REINDEER') as is_seasonal_christmas
from bounds b
left join names n using (stock_code)
left join launch_price lp using (stock_code)
