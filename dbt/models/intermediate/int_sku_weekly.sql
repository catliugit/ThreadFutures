-- One row per SKU per week with sales. List price = most common price on small orders,
-- because this retailer also sells wholesale with quantity price breaks.
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
