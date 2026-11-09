# Part 06: Model monitoring, step by step

**Status:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II). Not fashion, not a customer.
**Code:** `src/stock/monitor.py`; test in `tests/test_stock.py::test_psi_zero_for_same_distribution_and_large_for_shift`
**Output:** `models/monitoring.json`, `site/reports/monitoring.html`
**Numbers from:** `models/monitoring.json`

---

## 1. The question this stage answers

Is the stall-risk model from part 04 still accurate on newer launches, and does the new data still look like the data it was trained on?

A fashion brand cares because ranges, seasons and customers change. A model that was right last year can quietly go wrong, and the merchandiser acting on its risk scores won't know unless someone checks. Monitoring is that check.

---

## 2. The pipeline, step by step

### Step 1. Load the model and the same features

```python
bundle = joblib.load(ROOT / "models" / "stall_model.joblib")
model = bundle["model"]
df = load()
tr, te = df[df.split == "train"], df[df.split == "test"].copy()
te["p"] = model.predict_proba(te[FEATURES])[:, 1]
te["quarter"] = te.first_sale_week.dt.to_period("Q").astype(str)
```

- Load the saved model (part 04) and rebuild the feature table with the same `load()` function, so features are computed identically.
- Score every test-period launch.
- Tag each launch with its quarter: 2010Q4, 2011Q1, 2011Q2.

**Why per quarter:** a single test-set AUC hides change over time. Splitting into periods simulates what you'd see if the model had been in production and checked each quarter.

### Step 2. Accuracy per quarter

```python
for q, g in te.groupby("quarter"):
    ...
    auc = roc_auc_score(g.stalled, g.p) if g.stalled.nunique() > 1 else None
    ...
        "predicted_stall_rate": round(float(g.p.mean()), 3),
        "actual_stall_rate": round(float(g.stalled.mean()), 3),
```

- ROC AUC and PR AUC: is the ranking still good? Skipped if a quarter has only one class (AUC is undefined then).
- Predicted stall rate = average predicted probability. Actual stall rate = share that really stalled. If they differ a lot, the model is mis-calibrated for that period.

### Step 3. Drift per feature: PSI

```python
def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index using quantile bins of the training distribution."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))
```

- Line 3: cut the training distribution into 10 equal-count bins (deciles). `np.unique` merges duplicate edges, which happens when many values are identical.
- Lines 4 and 5: if there are fewer than 3 distinct edges (fewer than 2 bins), return 0. More on this in section 5.
- Line 6: open the outer bins so new values outside the training range still land somewhere.
- Lines 7 and 8: share of training rows (expected) and new rows (actual) in each bin.
- Line 9: avoid log of zero.
- Line 10: PSI formula: sum over bins of (actual - expected) x ln(actual / expected).

### Step 4. Drift per feature: KS test

```python
ks = stats.ks_2samp(tr[f], g[f])
drift[f] = {"psi": round(psi(tr[f].to_numpy(), g[f].to_numpy()), 3), "ks_p": float(f"{ks.pvalue:.3g}")}
```

- Two-sample Kolmogorov-Smirnov test: are these two samples from the same distribution?

### Step 5. Alerts

```python
PSI_ALERT, KS_ALERT, AUC_ALERT = 0.25, 0.01, 0.70
...
alerts = [f"{f}: PSI {d['psi']}" for f, d in drift.items() if d["psi"] > PSI_ALERT]
alerts += [f"{f}: KS p={d['ks_p']}" for f, d in drift.items() if d["ks_p"] < KS_ALERT and d["psi"] <= PSI_ALERT]
if auc is not None and auc < AUC_ALERT:
    alerts.append(f"AUC {auc:.2f} below {AUC_ALERT}")
```

- PSI above 0.25: major shift.
- KS p below 0.01, but only reported when PSI didn't already alert, to avoid double-counting the same feature.
- AUC below 0.70: ranking has degraded.

### Step 6. Write JSON and a static HTML report

`run()` writes `models/monitoring.json`, then `render()` builds `site/reports/monitoring.html`: an accuracy and calibration table per quarter, a PSI table per feature (cells above 0.25 highlighted), and the offcut model's error by garment and P10 to P90 coverage (from part 01). Every value goes through `html.escape` where it's text.

**Why static HTML:** no server, no dashboard tool, nothing to break. It's published on the website at `site/reports/monitoring.html`.

### Step 7. Test the drift metric itself

```python
def test_psi_zero_for_same_distribution_and_large_for_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 5000)) < 0.02
    assert psi(a, rng.normal(1.5, 1, 5000)) > 0.25
```

- Same distribution: PSI should be near zero. Shifted by 1.5 standard deviations: PSI should be clearly above the alert threshold.

---

## 3. Concepts, from scratch

### Model monitoring
**Definition:** checking a deployed model's inputs and outputs over time.
**Two kinds:** *performance monitoring* (is it still right?) needs the true outcomes, which arrive late. *Drift monitoring* (do inputs look different?) works immediately.

### Data drift vs concept drift
- **Data drift (covariate shift):** the inputs change. New launches sell more units per week than training launches did.
- **Concept drift:** the relationship between inputs and outcome changes. The same early sales pattern now means something different, for example because of Christmas.
**Here:** both appear. Inputs shifted (high PSI) and the stall rate for a given input pattern fell.

### Population Stability Index (PSI)
**Definition:** a number summarising how much a distribution has shifted between two samples, using bins.
**Worked example:** two bins. Training: 50% / 50%. New: 70% / 30%.
(0.7 - 0.5) x ln(0.7/0.5) + (0.3 - 0.5) x ln(0.3/0.5) = 0.2 x 0.336 + (-0.2) x (-0.511) = 0.067 + 0.102 = 0.17.
**Common rules of thumb:** under 0.1 stable, 0.1 to 0.25 moderate shift, over 0.25 major shift.

### Kolmogorov-Smirnov (KS) test
**Definition:** compares two cumulative distributions and finds the largest gap between them. The p-value says how surprising that gap would be if both samples came from the same distribution.
**Caveat:** with large samples tiny differences become "significant", and with discrete features (like month) the test is approximate.

### Calibration (by period)
**Definition:** do predicted probabilities match observed rates? Here, at the level of a whole quarter: mean predicted probability vs actual stall rate.

### ROC AUC and PR AUC (recap)
ROC AUC: ranking quality, 0.5 is random. PR AUC: focuses on the rare positive class; random equals the base rate. See part 04 for detail.

### Ranking vs calibration
A model can order products correctly (good AUC) while its probabilities are all too high. Ranking is what you need for "review the riskiest 20%"; calibration is what you need for "how many lines will stall this quarter?"

### Alert thresholds
**Definition:** fixed rules that turn a metric into "look at this". Simple and explainable; the risk is alert fatigue if they fire too often.

### Quantile bins
**Definition:** bins with equal numbers of training rows, rather than equal widths. Robust to skewed features like units per week.

### Static report
**Definition:** an HTML file generated by code. Reproducible, versioned and viewable anywhere.

---

## 4. The real results, and how to read them

From `models/monitoring.json`. Thresholds: PSI 0.25, KS p 0.01, AUC 0.70.

| Launch quarter | SKUs | ROC AUC | PR AUC | Predicted stall rate | Actual stall rate |
|---|---|---|---|---|---|
| 2010Q4 | 175 | 0.806 | 0.663 | 27.2% | 21.1% |
| 2011Q1 | 70 | **0.649** (alert) | 0.326 | 20.0% | 7.1% |
| 2011Q2 | 178 | 0.836 | 0.312 | **13.6%** | **1.7%** |

PSI by feature (alerts above 0.25 in bold):

| Feature | 2010Q4 | 2011Q1 | 2011Q2 |
|---|---|---|---|
| early_units_per_week | **0.316** | **1.616** | **1.311** |
| early_trend | 0.163 | **0.328** | 0.238 |
| early_zero_week_share | **2.634** | **0.559** | **0.899** |
| early_customers | **0.279** | **1.212** | **1.119** |
| early_orders | **0.397** | **0.881** | **1.182** |
| early_return_rate | **0.261** | **0.413** | 0.07 |
| early_max_markdown | 0.0 | 0.0 | 0.0 |
| launch_list_price | **0.377** | **1.513** | **0.413** |
| launch_month | **8.883** | **3.347** | **5.24** |
| is_seasonal_christmas | 0.0 | 0.0 | 0.0 |

KS-only alerts (PSI under 0.25 but KS p under 0.01): early_trend in 2010Q4 (p = 1.5e-05) and 2011Q2 (p = 0.00182); early_return_rate in 2011Q2 (p = 1.3e-05).

The 175 + 70 + 178 SKUs add up to the 423 test SKUs in part 04.

**How to read it:**

- **Ranking holds in two of three quarters** (0.81 and 0.79). 2011Q1 drops to 0.62, but it has only 70 SKUs (about 5 stalls at 7.1%), so that AUC is very noisy.
- **Calibration drifts badly.** The model over-predicts in every quarter, and the gap widens: 28% vs 21%, then 21% vs 7%, then 14% vs 1.7%. For 2011 Q2 launches, the model expected about 1 in 7 to stall and only about 1 in 60 did. Those spring lines' weeks 12 to 25 ran into the Christmas season (from late summer onwards), when sales rise instead of collapsing.
- **Inputs shifted a lot.** Later launches sold more per week, to more customers, with fewer zero weeks than the training launches.
- **launch_month PSI is huge by construction.** Each test quarter contains only three months, while training covers many months, so this "drift" is expected. It's still useful: it tells you the model is being asked about months it saw less of.

---

## 5. What went wrong or surprised me, and what it taught me

### Over-prediction for 2011 Q2: 14% predicted vs 1.7% actual
This was the big finding. The model still ranked well, so a simple AUC check would have said "fine". Only the calibration check showed it was over-confident about stalling for lines selling into Christmas. A read-only check while writing this guide adds context: 27.6% of training launches stalled versus 10.6% of test launches, so the model learned in a higher-stall world.

**What it taught me:** monitor calibration, not just ranking. And monitoring is useful because it tells you exactly what to fix next: a seasonal feature (weeks to Christmas) and recalibration on recent data. That's planned as part 15.

### PSI of 0.0 doesn't always mean "no drift"
`early_max_markdown` and `is_seasonal_christmas` show PSI 0.0 in every quarter. That's an artefact of my implementation: both features are mostly zero, so the decile edges collapse to fewer than three distinct values and the function returns 0. For binary or mostly-zero features, PSI should compare category shares directly. The KS p-values for them (0.08 to 1.0) don't suggest a big shift, but the 0.0 is not evidence by itself. That's a fix I'd make.

### Many alerts at once
Nearly every feature alerts in every quarter. That's partly real (the business grew) and partly because these are small samples against a fixed training snapshot. In production I'd want alert priorities, so a merchandiser sees "calibration off by 12 points" before "launch_month PSI 5.24".

---

## 6. Honest limits

- **Real open data, not fashion and not a customer.**
- **Small quarterly samples** (70 to 178 SKUs), so AUC and stall rates per quarter are noisy. No confidence intervals reported.
- Retrospective: this simulates monitoring on historical quarters, it isn't a live system.
- Performance metrics need outcomes, which arrive 26 weeks after launch. In live use, drift alerts come first and accuracy later.
- PSI returns 0 for low-cardinality features (section 5).
- Fixed thresholds (0.25, 0.01, 0.70) are common conventions, not tuned.
- Calibration is checked at quarter level only, not with a reliability curve across probability bands.

---

## 7. How to run it yourself

```bash
make retail && make dbt && make stall   # monitoring needs the warehouse and the trained model
make offcuts                            # the report also reads models/metrics.json
make monitor                            # python -m stock.monitor -> models/monitoring.json, site/reports/monitoring.html
```

Then open `site/reports/monitoring.html` in a browser. It's also published at threadfutures.com/reports/monitoring.html.

---

## 8. Glossary

- **Model monitoring:** checking a model's inputs and performance over time.
- **Data drift / covariate shift:** input distributions change.
- **Concept drift:** the input-to-outcome relationship changes.
- **PSI:** Population Stability Index, a binned measure of distribution shift.
- **KS test:** Kolmogorov-Smirnov test comparing two distributions.
- **Quantile bins / deciles:** bins with equal counts of training rows.
- **Calibration:** predicted probabilities matching observed rates.
- **Over-prediction:** predicted rate higher than actual rate.
- **Ranking vs calibration:** ordering items correctly vs getting probability levels right.
- **Alert threshold:** a fixed rule that flags a metric for attention.
- **Alert fatigue:** so many alerts that people stop reading them.
- **Launch quarter:** the calendar quarter of a product's first sale.
- **Static report:** an HTML file generated from code.
- **Reliability curve:** predicted probability bands against observed rates.
- **Isotonic / Platt calibration:** methods to re-map scores to better probabilities.
