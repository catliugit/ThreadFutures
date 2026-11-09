# Thread Futures part 13: Cloud warehouse

**Status:** Planned · **Label:** Planned  

## In one line
Run the same dbt project on BigQuery (free sandbox) or Snowflake (trial).

## Skills it adds
BigQuery, Snowflake, dbt

## Plan
Add a cloud profile, load the Parquet bronze layer, run dbt build on the cloud target, compare row counts with DuckDB.

## Done when
dbt build passes on the cloud target.

## Effort
2 to 3 days
