# Thread Futures part 05: Experimentation and causal analysis

**Status:** Built · **Label:** Real data (markdowns) + simulated pilot  

## In one line
Asks two questions: do markdowns actually sell more units, and how many batches a fair comparison would need to show that selling through Thread Futures returns more money to a brand than a liquidator?

## Why it matters
Brands will only pay if the recovery uplift is proven.

## Data
Markdowns: real weekly sales from part 2. Pilot: simulated, from stated planning assumptions.

## Method
Stacked difference-in-differences: 768 products whose list price first dropped 15% or more, each compared with the 5 never-marked-down products from the same launch cohort with the most similar pre-period sales, over the same calendar weeks (4 before, 4 after), with standard errors clustered by product. A placebo test on the pre-period checks parallel trends. Pilot: power analysis (Welch t-test), then one simulated pilot with a bootstrap confidence interval.

## Tools
statsmodels, SciPy, DuckDB, pandas, NumPy

## Result
The raw estimate is +125% units after a markdown, but the placebo test failed (marked-down lines were already gaining beforehand, p < 0.001), so it is reported as an upper bound, not a clean effect. Pilot: with 8p vs 11p recovered per £ of retail value (sd 6p), a randomised pilot needs 64 batches per arm for 80% power.

## Honest limits
Observational markdown data; price changes may partly reflect wholesale order mix. Pilot numbers are assumptions until a real pilot runs.

## Where it lives
src/stock/experiment.py, models/experiment_results.json
