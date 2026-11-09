# Thread Futures part 04: Stall-risk model

**Status:** Built · **Label:** Real open retail data  

## In one line
From a line's first 12 weeks on sale, predicts whether its sales are about to collapse, which is the line most likely to end up as unsold stock.

## Why it matters
Brands need to act while there is still time. This is the early-warning signal for the unsold-stock workflow.

## Data
1,319 SKUs whose launch is observed and whose outcome window is complete. Target: average weekly units in weeks 12 to 25 below 20% of the first 12 weeks.

## Method
Ten early-life features (velocity, trend, zero-sale weeks, customers, orders, returns, markdown, launch price, month, Christmas flag). Time-based split: train on launches before Oct 2010, test on later launches. Gradient boosting vs a rule a merchandiser might use (sales halved). Every run tracked in MLflow with the model registered.

## Tools
scikit-learn, pandas, DuckDB, MLflow (tracking + model registry), joblib

## Result
On 423 later launches: ROC AUC 0.81 vs 0.60 for the rule; PR AUC 0.53 vs a base rate of 0.11; the top 20% flagged were stall cases 32% of the time (20% for the rule) vs 11% at random.

## Honest limits
Retail data, not fashion. Over-predicts for spring launches heading into Christmas (see part 6). Seasonality is fixed in part 15.

## Where it lives
src/stock/features.py, src/stock/train_stall.py, models/stall_metrics.json, site/data/stock.js
