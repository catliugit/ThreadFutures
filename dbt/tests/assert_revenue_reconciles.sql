-- Gold revenue must equal silver revenue (no rows lost or double-counted between layers).
with silver as (select sum(line_revenue) as r from {{ ref('stg_transactions') }} where not is_return),
gold as (select sum(revenue) as r from {{ ref('fct_sku_weekly') }})
select * from silver, gold where abs(silver.r - gold.r) > 0.01
