# Thread Futures part 01: Offcut forecasting

**Status:** Built · **Label:** Simulated data  

## In one line
Forecasts how many kilograms of fabric offcuts a planned cutting run will produce, as a low, likely and high range, before any fabric is cut.

## Why it matters
Cutting plans (markers) report planned efficiency, but cutting rooms lose more fabric than the plan shows: selvedge trim, ply ends, roll remnants, splices, defects. Knowing the likely weight early lets a factory plan a buyer for the offcuts.

## Data
8,000 simulated production runs from a simulator that nests graded pattern pieces into markers and adds real-world losses. Calibrated to published industry ranges (simulated waste averages about 19% of fabric, inside the 10 to 20% range). Not factory data.

## Method
Gradient-boosted quantile regression (P10, P50, P90) on order data only. Compared with two real baselines: the marker alone and a flat 15% rule of thumb. Interval coverage checked. Trees exported to JSON and evaluated in plain JavaScript in the browser.

## Tools
Python, scikit-learn (GradientBoostingRegressor, quantile loss), pandas, NumPy, Matplotlib, JavaScript

## Result
On 1,600 held-out simulated runs: 8.8% mean error on offcut kg vs 20.3% for the 15% rule and 23.3% for the marker alone; 82.4% of runs within ±15%; P10 to P90 range covers 76.8% of outcomes (target 80%). With the planned marker as an input: 4.9% error. A float32 split-threshold bug in the browser export was found and fixed: scikit-learn compares inputs as 32-bit floats, and rounded thresholds made edge inputs (e.g. a 1.57 m roll) take a different branch. A test now proves the export matches scikit-learn.

## Honest limits
Trained on simulated runs. The first pilot goal is ±15% on real weighed output. Coverage is slightly under the 80% target.

## Where it lives
src/offcut/ (simulate.py, nesting.py, train.py, export.py), site/forecast.js, models/metrics.json
