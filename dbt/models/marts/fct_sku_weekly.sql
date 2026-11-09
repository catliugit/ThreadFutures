-- Gold fact: SKU-week grain, with weeks since launch and markdown versus launch list price.
select
    w.stock_code,
    w.week_start,
    -- Returns can arrive before a SKU's first recorded sale (sold before the data starts).
    case when w.week_start >= d.first_sale_week
         then datediff('week', d.first_sale_week, w.week_start) end        as weeks_since_launch,
    w.units_sold,
    w.units_returned,
    w.revenue,
    w.orders,
    w.customers,
    w.list_price,
    d.launch_list_price,
    case when d.launch_list_price > 0 and w.list_price is not null
         then greatest(0, 1 - w.list_price / d.launch_list_price) end      as markdown_pct
from {{ ref('int_sku_weekly') }} w
join {{ ref('dim_sku') }} d using (stock_code)
