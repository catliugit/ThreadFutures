# Thread Futures part 06: Model monitoring

**Status:** Built · **Label:** Real open retail data  

## In one line
Checks whether the stall-risk model is still accurate and whether new data still looks like the training data.

## Why it matters
Models drift as seasons and ranges change. Forecast monitoring was a named requirement in the Relay application.

## Data
Later launch quarters the model never trained on (2010 Q4, 2011 Q1, 2011 Q2).

## Method
Per quarter: ROC AUC, PR AUC, predicted vs actual stall rate (calibration). Drift per feature: Population Stability Index and a Kolmogorov-Smirnov test. Alerts at PSI > 0.25, KS p < 0.01, AUC < 0.70. Static HTML report.

## Tools
SciPy, pandas, scikit-learn, HTML

## Result
Ranking stays good in two of three quarters (AUC 0.81, 0.65, 0.84), but calibration drifts: for 2011 Q2 launches the model predicted 14% would stall and only 1.7% did, because those lines sold into the Christmas peak. Strong drift flagged on several features.

## Honest limits
Small quarterly samples (70 to 178 SKUs).

## Where it lives
src/stock/monitor.py, models/monitoring.json, site/reports/monitoring.html (threadfutures.com/reports/monitoring.html)
