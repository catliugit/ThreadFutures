-- Gold: merchandising health per SKU at the end of the data (9 Dec 2011).
--   ABC: share of revenue (A = top 80%, B = next 15%, C = rest)
--   XYZ: demand variability, coefficient of variation of weekly units (incl. zero weeks)
--   velocity_ratio: last 8 weeks' units per week / best 8-week run (1 = at peak, 0 = stopped)
{% set as_of = "date '2011-12-05'" %}
with d as (select * from {{ ref('dim_sku') }}),
f as (select * from {{ ref('fct_sku_weekly') }}),
calendar as (
    select stock_code, unnest(generate_series(first_sale_week, {{ as_of }}, interval 1 week))::date as week_start
    from d
),
dense as (
    select c.stock_code, c.week_start, coalesce(f.units_sold, 0) as units
    from calendar c left join f using (stock_code, week_start)
),
rolling as (
    select stock_code, week_start,
           avg(units) over (partition by stock_code order by week_start rows between 7 preceding and current row) as avg8
    from dense
),
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
money as (
    select stock_code, sum(revenue) as revenue, sum(units_returned) as units_returned,
           max(markdown_pct) as max_markdown_pct
    from f group by 1
),
ranked as (
    select m.*, sum(revenue) over (order by revenue desc rows unbounded preceding)
                / sum(revenue) over () as cum_share
    from money m
)
select
    d.stock_code,
    d.description,
    d.launch_cohort,
    d.launch_observed,
    p.weeks_live,
    p.units_total,
    round(p.units_per_week, 3)                                              as units_per_week,
    r.revenue,
    round(r.units_returned / nullif(p.units_total, 0), 4)                   as return_rate,
    round(coalesce(r.max_markdown_pct, 0), 4)                               as max_markdown_pct,
    round(coalesce(v.last_avg8 / nullif(v.peak_avg8, 0), 0), 4)             as velocity_ratio,
    datediff('week', d.last_sale_week, {{ as_of }})                         as weeks_since_last_sale,
    case when r.cum_share <= 0.80 then 'A' when r.cum_share <= 0.95 then 'B' else 'C' end as abc_class,
    case when p.demand_cv < 0.5 then 'X' when p.demand_cv < 1.0 then 'Y' else 'Z' end  as xyz_class,
    case
        when datediff('week', d.last_sale_week, {{ as_of }}) >= 12 then 'stopped'
        when coalesce(v.last_avg8 / nullif(v.peak_avg8, 0), 0) < 0.25 then 'slowing'
        else 'selling'
    end                                                                     as stock_status
from d
join per_sku p using (stock_code)
join ranked r using (stock_code)
left join velocity v using (stock_code)
