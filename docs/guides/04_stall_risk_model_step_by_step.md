# Part 04: Stall-risk model, step by step

**Status:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II). Not fashion, not a customer.
**Code:** `src/stock/features.py`, `src/stock/train_stall.py`, `src/stock/export_stall.py`, `src/stock/export_site.py`
**Numbers from:** `models/stall_metrics.json` (plus a few read-only checks, labelled)

---

## 1. The question this stage answers

From a product's first 12 weeks on sale, can I predict whether its sales are about to collapse in weeks 12 to 25?

A fashion brand cares because a line that stalls mid-season is the line most likely to end up as unsold stock. Twelve weeks in, there's still time to act: reorder less, move stock between channels, mark down earlier, or plan a resale or donation route.

---

## 2. The pipeline, step by step

### Step 1. Choose which products are eligible

**Where:** `src/stock/features.py`, the `skus` CTE in `SQL`

```python
EARLY_WEEKS = 12
LATE_WEEKS = 14          # weeks 12-25
STALL_RATIO = 0.20
LAST_LAUNCH = "2011-06-06"   # 26 weeks before the data ends, so every outcome is observed
TRAIN_BEFORE = "2010-10-01"  # time-based split: train on earlier launches, test on later
```

```sql
    from dim_sku
    where launch_observed and first_sale_week <= date '{LAST_LAUNCH}'
```

- Only SKUs whose launch is actually observed (first sale from January 2010, see part 02).
- Only launches up to 6 June 2011, so all 26 weeks (12 early + 14 late) fall inside the data. Otherwise a product launched in November 2011 would look "stalled" just because the data ran out.

**Out:** 1,319 SKUs (896 train + 423 test).

### Step 2. Build a 26-week grid per SKU and fill zeros

```sql
grid as (
    select s.*, unnest(range(0, {EARLY_WEEKS + LATE_WEEKS})) as wk from skus s
),
weekly as (
    select g.stock_code, g.wk,
           coalesce(f.units_sold, 0) as units, ...
    from grid g
    left join fct_sku_weekly f
      on f.stock_code = g.stock_code and f.weeks_since_launch = g.wk
)
```

- `range(0, 26)` gives weeks 0 to 25 for every SKU.
- Left join the weekly fact on `weeks_since_launch` and fill missing weeks with 0.

**Why:** same lesson as part 03. Weeks with no sales must count as zero, or a dying product looks healthy.

### Step 3. Compute ten early-life features and the outcome

```sql
    avg(units) filter (where wk < {EARLY_WEEKS})                                  as early_units_per_week,
    (avg(units) filter (where wk between 8 and 11) + 1)
      / (avg(units) filter (where wk between 0 and 3) + 1)                        as early_trend,
    avg((units = 0)::int) filter (where wk < {EARLY_WEEKS})                       as early_zero_week_share,
    ...
    avg(units) filter (where wk >= {EARLY_WEEKS})                                 as late_units_per_week
```

- `early_units_per_week`: average weekly units in weeks 0 to 11.
- `early_trend`: weeks 8 to 11 vs weeks 0 to 3. Below 1 means sales are falling. The `+ 1` on both sides stops division by zero and damps noise for tiny sellers.
- `early_zero_week_share`: share of the first 12 weeks with no sale.
- Also: early customers, early orders, early return rate, deepest early markdown, launch list price, launch month and a Christmas flag.
- `late_units_per_week`: weeks 12 to 25. This is used only for the label, never as a feature.

`FILTER (WHERE ...)` is a neat SQL feature: an aggregate over only the rows that meet the condition, so I can compute early and late measures in one pass.

### Step 4. Define the label and the time-based split

```python
df["early_return_rate"] = df["early_return_rate"].fillna(0).clip(0, 1)
df[FEATURES] = df[FEATURES].astype(float)
df["stalled"] = (df["late_units_per_week"] < STALL_RATIO * df["early_units_per_week"]).astype(int)
df["split"] = (df["first_sale_week"] < pd.Timestamp(TRAIN_BEFORE)).map({True: "train", False: "test"})
```

- Line 1: no sales means a NULL return rate, so fill with 0 and keep it between 0 and 1.
- Line 3: **stalled** = late weekly sales below 20% of early weekly sales. Sold 50 a week early, then under 10 a week: stalled.
- Line 4: train on launches before 1 October 2010, test on later launches.

**Why time-based:** in real life you train on the past and predict the future. A random split would let the model learn from products launched after the ones it's tested on, which flatters it.

### Step 5. Train gradient boosting and a simple rule, tracked in MLflow

**Where:** `src/stock/train_stall.py`, `main()`

```python
PARAMS = dict(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, random_state=7)
...
    mlflow.set_tracking_uri(TRACKING)
    mlflow.set_experiment("stall-risk")
    with mlflow.start_run(run_name="gbm-early-12wk") as run:
        model = GradientBoostingClassifier(**PARAMS).fit(tr[FEATURES], tr.stalled)
        p = model.predict_proba(te[FEATURES])[:, 1]
        rule = (te.early_trend < 0.5).astype(float).to_numpy()
```

- `TRACKING` is a SQLite file, `data/mlflow.db`.
- Every run is recorded under the experiment "stall-risk".
- The model: 300 shallow trees, learning rate 0.05.
- `predict_proba(...)[:, 1]`: the probability of the "stalled" class.
- **The baseline rule:** flag a product if sales in weeks 8 to 11 have halved versus weeks 0 to 3 (`early_trend < 0.5`). That's what a merchandiser might do by eye.

Then it logs parameters, test metrics and rule metrics, and registers the model:

```python
        mlflow.log_params(PARAMS | {"features": len(FEATURES), "train_before": "2010-10-01"})
        mlflow.log_metrics({f"test_{k}": v for k, v in res["model"].items()})
        mlflow.sklearn.log_model(model, name="model", registered_model_name="stall-risk",
                                 input_example=te[FEATURES].head(3),
                                 skops_trusted_types=["sklearn.tree._tree.Tree"])
```

- `registered_model_name="stall-risk"` adds a new version to the model registry each time.
- `input_example`: three real rows saved with the model, so anyone loading it sees the expected input shape.
- The model is saved in the skops format (`mlruns/.../model.skops`), a safer alternative to pickle; the trusted-types argument says the tree objects are ones I trained myself.

The model is also saved with joblib to `models/stall_model.joblib` for the API, and the metrics to `models/stall_metrics.json`.

### Step 6. Evaluate on later launches

```python
def precision_at(y, score, frac=0.2):
    k = max(1, int(len(y) * frac))
    top = np.argsort(-score)[:k]
    return float(np.mean(np.asarray(y)[top]))
```

- Sort products by predicted risk, take the top 20%, and measure what share actually stalled.

Plus ROC AUC, PR AUC (`average_precision_score`) and the Brier score.

### Step 7. Export for the browser and the website

- `src/stock/export_stall.py` writes the trees to `models/stall_model.json` and `site/data/stall_model.js`, with full-precision thresholds and float32 input comparison (lesson from part 01). Probability = sigmoid(init + learning_rate x sum of leaf values). The test `test_browser_stall_model_matches_sklearn` checks the export matches scikit-learn to within 0.000001.
- `src/stock/export_site.py` picks a few real test-set lines (5 highest risk, 3 lowest, among steady sellers) and writes `site/data/stock.js` for the website table.

---

## 3. Concepts, from scratch

### Binary classification and predicted probability
**Definition:** predict one of two outcomes (stalled or not) and, usually, a probability.
**Why it matters:** a probability lets you rank products and choose your own threshold.

### Target definition
**Definition:** the exact rule that says what counts as a positive.
**Here:** late weekly units < 20% of early weekly units. Change the 20% and you change the problem, so it's stated precisely.

### Time-based split vs random train/test split
**Definition:** random = shuffle rows into train and test. Time-based = everything before a date is train, after is test.
**Analogy:** you can't use next month's weather to "forecast" this month's.
**Here:** train on 896 launches before October 2010, test on 423 launches from October 2010 to June 2011.

### Data leakage
**Definition:** information at training time that won't exist at prediction time.
**Checks here:** features only use weeks 0 to 11; the label only uses weeks 12 to 25; launch price uses the first 8 weeks; launches without a complete outcome window are excluded; the split is by time.

### Base rate
**Definition:** the share of positives in the data.
**Here:** 10.64% of test products stalled. Any "precision" number must be compared with this.

### Baseline
**Definition:** the simple method you need to beat. Here, the "sales halved" rule.

### Gradient boosting classifier
Same idea as part 01 (many small trees in sequence, each correcting the last), but each tree adds to a log-odds score, and a sigmoid turns the total into a probability.
**Sigmoid:** p = 1 / (1 + e^(-score)). A score of 0 gives 50%; -2 gives about 12%.

### ROC AUC
**Definition:** the probability that a randomly chosen stalled product gets a higher risk score than a randomly chosen non-stalled one. 0.5 = coin toss, 1.0 = perfect ranking.
**Worked example:** with 3 stalled and 3 healthy products there are 9 stalled-vs-healthy pairs. If the model ranks the stalled one higher in 7, AUC = 7/9 = 0.78.
**Why it matters:** it measures ranking, regardless of threshold.

### PR AUC (average precision)
**Definition:** the area under the precision-recall curve. Precision = of those flagged, how many really stalled; recall = of those that stalled, how many were flagged.
**Why use it alongside ROC AUC:** when positives are rare (11%), ROC AUC can look good while precision is poor. PR AUC focuses on the positives. Its "random" level is the base rate, not 0.5.

### Precision at top k
**Definition:** flag the top k% riskiest and see what share are true positives.
**Why it matters:** this is how it would be used. A merchandiser can review 20% of lines, not all of them.

### Calibration
**Definition:** a model is calibrated if, among products given 30% risk, about 30% actually stall.
**Why it matters:** ranking (AUC) can be good while probabilities are off. Part 06 shows exactly that.

### Brier score
**Definition:** the mean squared difference between predicted probability and outcome (0 or 1). Lower is better.
**Worked example:** predict 0.8 and it stalls: (0.8 - 1)² = 0.04. Predict 0.8 and it doesn't: 0.64.
**Benchmark:** always predicting the base rate p gives Brier = p(1 - p). With p = 0.1064 that's about 0.095. The model's 0.0874 is better, but only modestly, which is a calibration warning sign (see section 5).

### Feature importance
**Definition:** for tree models, how much each feature reduced the loss across all splits, normalised to sum to 1.
**Caveat:** it says what the model used, not what causes stalling. Correlated features share importance.

### MLflow tracking and model registry
**Definition:** tracking records every training run's parameters, metrics and artefacts. The registry keeps named, versioned models ("stall-risk" version 1, 2, ...).
**Analogy:** a lab notebook plus a labelled shelf of finished samples.
**Why it matters:** when I change features in part 15, I can compare the new run with this one honestly.

### joblib and skops
joblib saves Python objects to disk (fast, but pickle-based, so only load files you trust). skops is a format for scikit-learn models designed to be safer to load.

### Float32 thresholds (export parity)
Same lesson as part 01: export thresholds at full precision and compare inputs as float32, then test the export against scikit-learn.

---

## 4. The real results, and how to read them

From `models/stall_metrics.json`. Train 896 SKUs, test 423 later launches, test stall rate 10.64%.

| Metric (test set) | Gradient boosting | "Sales halved" rule | Random |
|---|---|---|---|
| ROC AUC | **0.8118** | 0.5994 | 0.5 |
| PR AUC | **0.5312** | 0.3138 | about 0.106 (base rate) |
| Precision in top 20% | **34.5%** | 8.3% | 10.6% |
| Brier score | 0.0874 | n/a | about 0.095 if always predicting the base rate |

Feature importance: early_trend 0.1959, early_customers 0.1634, launch_list_price 0.154, early_units_per_week 0.1386, launch_month 0.107, early_zero_week_share 0.0753, early_orders 0.0598, early_return_rate 0.041, is_seasonal_christmas 0.0367, early_max_markdown 0.0282.

MLflow run ID: `5dd66097c6e54d829c5e8004c37580fa`.

**How to read it:**

- AUC 0.81: pick a stalled and a healthy product at random, and 81% of the time the model ranks the stalled one higher.
- Top 20%: if a merchandiser reviews the 20% of lines the model flags, about 1 in 3 really will stall, versus about 1 in 9 at random. That's about three times the base rate.
- PR AUC 0.51 vs a base rate of 0.11: strong given how rare stalls are.
- Trend matters most, which makes sense, but it isn't enough alone: customers, price and launch month add a lot.
- `launch_month` being important is a warning: seasonality is in play, which part 06 confirms.

---

## 5. What went wrong or surprised me, and what it taught me

### The model ranks well but over-predicts later
Monitoring (part 06) found that for 2011 Q2 launches the model predicted a 14% stall rate (13.9%) and only 1.7% actually stalled, because those lines sold into the Christmas peak. Ranking was still good (AUC 0.79), but the probabilities were too high. That's a calibration problem, and the fix is planned as part 15.

A read-only check while writing this guide shows why: the stall rate in the training set is 27.6% versus 10.6% in the test set. The model learned from a period where stalling was much more common. That also explains why the Brier score is only modestly better than predicting the base rate.

### A check worth running on the baseline (found while writing this guide)
In `train_stall.py` the rule is scored as `rule + 1e-9 * te.early_trend.rank()`. The tiny tie-breaker is meant to order products within the rule's two groups, but it ranks products with a *higher* trend as riskier, which is the opposite of the rule's logic. Read-only recalculation on the same test set:

| Rule scoring | ROC AUC |
|---|---|
| As first coded (tie-break in the wrong direction) | 0.516 (since fixed) |
| Pure 0/1 rule, no tie-break | 0.558 |
| Tie-break in the right direction (equivalent to ranking by lower trend) | 0.599 |

So the model's advantage is real (0.81 vs about 0.60) but smaller than "0.81 vs 0.52" suggests. **Fixed on 9 Nov 2026:** the sign was changed, the model was retrained, and the rule now scores 0.5994. Original recommendation, for the record: change the sign to `- 1e-9 * ...`, rerun `make stall`, and update the README with the new rule numbers.

### Getting the eligibility window right
Without `LAST_LAUNCH`, products launched late in 2011 would look stalled simply because the data ends. That's a form of label leakage through censoring, and it's easy to miss.

---

## 6. Honest limits

- **Real open data, not fashion and not a customer.** Gift and homeware retail has different seasons and life cycles from fashion.
- Small test set (423 SKUs, about 45 stalls), so the metrics have real uncertainty. I haven't reported confidence intervals on the AUC; bootstrapping the test set would give them.
- Over-predicts for spring launches heading into Christmas (part 06). Seasonality fix and calibration planned (part 15).
- The baseline comparison needs rerunning with the corrected tie-break (section 5).
- The 20% stall threshold and 12-week window are choices, not tuned to a business decision.
- No hyperparameter search or cross-validation; one sensible configuration.
- Feature importance is not causation.

---

## 7. How to run it yourself

```bash
make retail       # bronze data, if not already there
make dbt          # builds dim_sku and fct_sku_weekly
make stall        # python -m stock.train_stall: trains, logs to MLflow, writes models/stall_metrics.json
make mlflow-ui    # mlflow ui --backend-store-uri sqlite:///data/mlflow.db
```

Browser and website exports (not in the Makefile):

```bash
PYTHONPATH=src python -m stock.export_stall   # site/data/stall_model.js
PYTHONPATH=src python -m stock.export_site    # site/data/stock.js
```

---

## 8. Glossary

- **Stall:** weeks 12 to 25 weekly sales below 20% of weeks 0 to 11.
- **Early trend:** (weeks 8 to 11 average + 1) / (weeks 0 to 3 average + 1).
- **Binary classification:** predicting one of two outcomes.
- **Base rate:** share of positives.
- **Time-based split:** train on earlier data, test on later.
- **Data leakage:** training on information not available at prediction time.
- **Censoring:** outcome not fully observed because the data ends.
- **Sigmoid:** function turning a score into a probability.
- **ROC AUC:** probability a random positive ranks above a random negative.
- **Precision / recall:** share of flagged that are right / share of positives flagged.
- **PR AUC (average precision):** area under the precision-recall curve.
- **Precision at top k:** precision among the k% highest-risk items.
- **Calibration:** whether predicted probabilities match observed rates.
- **Brier score:** mean squared error of probabilities.
- **Feature importance:** how much a model relied on each feature.
- **MLflow tracking:** a record of runs, parameters and metrics.
- **Model registry:** named, versioned models.
- **joblib:** Python object serialisation.
- **skops:** a safer serialisation format for scikit-learn models.
- **Tie-break:** a tiny adjustment to order items with equal scores.
- **`FILTER (WHERE ...)`:** SQL aggregate over a subset of rows.
