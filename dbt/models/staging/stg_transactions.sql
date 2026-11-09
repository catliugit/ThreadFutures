-- Silver: one row per invoice line for real products only.
-- Drops postage, fees, manual adjustments and test codes; flags cancellations (returns).
with src as (
    select * from read_parquet('{{ var("raw_transactions") }}')
)
select
    md5(concat_ws('|', invoice, stock_code, cast(invoice_ts as varchar), cast(quantity as varchar),
                  cast(unit_price as varchar), cast(row_number() over () as varchar))) as line_id,
    invoice,
    upper(trim(stock_code))                               as stock_code,
    trim(description)                                     as description,
    quantity,
    unit_price,
    quantity * unit_price                                 as line_revenue,
    invoice like 'C%'                                     as is_return,
    customer_id,
    country,
    invoice_ts,
    cast(date_trunc('week', invoice_ts) as date)          as week_start
from src
where regexp_matches(upper(trim(stock_code)), '^[0-9]{5}[A-Z]{0,2}$')
  and unit_price > 0
  and quantity <> 0
