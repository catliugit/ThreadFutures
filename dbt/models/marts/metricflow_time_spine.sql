{{ config(materialized='table') }}
select cast(d as date) as date_day
from generate_series(date '2009-11-30', date '2011-12-31', interval 1 day) t(d)
