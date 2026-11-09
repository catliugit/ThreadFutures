# Thread Futures part 03: Merchandising analytics

**Status:** Built · **Label:** Real open retail data  

## In one line
Shows which lines are selling, slowing or stopped, with the classic merchandising views.

## Why it matters
Unsold stock is a merchandising problem first. This is also the domain gap flagged by merchandising analyst roles (e.g. Aqilea).

## Data
dbt marts built in part 2.

## Method
ABC classification by revenue share (A top 80%, B next 15%, C rest); XYZ by demand variability (coefficient of variation of weekly units including zero weeks); sales velocity (last 8 weeks vs best 8-week run); markdown depth vs launch list price; return rate; launch cohorts by quarter; status selling / slowing / stopped.

## Tools
SQL, dbt, DuckDB

## Result
4,707 SKUs classified (e.g. 1,573 stopped, 1,333 slowing, 1,801 selling at 5 Dec 2011).

## Honest limits
The data has no inventory, so true sell-through and weeks of cover can't be computed honestly; velocity is used instead.

## Where it lives
dbt/models/marts/mart_sku_health.sql
