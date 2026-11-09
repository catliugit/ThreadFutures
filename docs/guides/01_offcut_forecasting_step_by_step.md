# Part 01: Offcut forecasting, step by step

**Status:** Built · **Data label:** SIMULATED cutting runs (not factory data)
**Code:** `src/offcut/` (simulate.py, garments.py, nesting.py, pipeline.py, train.py, export.py), `site/forecast.js`
**Numbers from:** `models/metrics.json`, `data/staged/quality_report.json`

---

## 1. The question this stage answers

Before a factory cuts a production run, how many kilograms of fabric offcuts will it end up weighing, as a low, likely and high range?

A fashion brand cares because offcuts are fabric it has already paid for. If the factory knows the likely weight and fibre before cutting, it can line up a recycler and sell the offcuts as a planned lot instead of sweeping them into a skip. The cutting plan software (the marker) reports a planned waste figure, but real cutting rooms lose more than that, so planning on the marker figure leaves you short every time.

---

## 2. The pipeline, step by step

### Step 1. Describe the garments as pattern pieces

**What happens:** each of five garments (tee, hoodie, shirt, jeans, dress) is written down as a list of pattern pieces at size M: width across the fabric, length along it, how much of its bounding box the real piece fills, and how many are cut per garment.

**Where:** `src/offcut/garments.py`, `GARMENTS`, `SIZE_SCALE`, `SIZE_MIXES`, `graded_pieces()`

**In:** hand-written piece dimensions. **Out:** a library of garments that can be scaled to any size.

```python
SIZE_SCALE = {"XS": 0.92, "S": 0.96, "M": 1.00, "L": 1.04, "XL": 1.08, "XXL": 1.12}

SIZE_MIXES: Dict[str, Dict[str, int]] = {
    "narrow":   {"S": 1, "M": 2, "L": 2, "XL": 1},
    "standard": {"XS": 1, "S": 2, "M": 3, "L": 3, "XL": 2, "XXL": 1},
    "extended": {"XS": 1, "S": 1, "M": 2, "L": 2, "XL": 2, "XXL": 2},
}
```

- `SIZE_SCALE`: linear grading. An XL piece is 8% bigger in each direction than an M piece.
- `SIZE_MIXES`: how many garments of each size are cut together in one marker. "standard" cuts 12 garments per marker, peaked at M and L.

**Why this way:** there is no public dataset of factory cutting runs. Building from first principles means every number in the simulation has a physical meaning I can explain.

### Step 2. Build a marker (the cutting plan) for each run

**What happens:** the pieces for one size mix are packed onto the fabric width with a "skyline bottom-left" packing heuristic. Several orderings are tried and the shortest marker is kept, as a marker maker would.

**Where:** `src/offcut/nesting.py`, `build_marker()`, `_skyline_pack()`, `_orderings()`

**In:** a garment, usable fabric width, size mix. **Out:** a `Marker` with length, true piece area and efficiency.

```python
length = min(_skyline_pack(order, width_cm) for order in _orderings(rects, seed))
# The calibration factor can occasionally overshoot what any real marker achieves;
# hold efficiency at the published upper bound for cut-and-sew garments.
length = max(length, true_area / (width_cm * MAX_EFFICIENCY))
return Marker(width_cm, length, true_area, len(rects), n_garments)
```

- Line 1: pack the pieces in each candidate order and keep the shortest marker.
- Line 4: never let efficiency go above 93% (`MAX_EFFICIENCY = 0.93`), the top of published ranges.
- Line 5: return the marker. Efficiency = true piece area / (width x length).

**Why this way:** real nesting software handles irregular shapes. I approximate each piece by a rectangle of equal area, adjusted by a per-garment calibration factor `nest_k`, so simulated efficiencies land in published ranges. Pieces are never rotated 90 degrees, because grain direction matters in real cutting.

### Step 3. Simulate the real-world losses the marker does not see

**What happens:** for each of 8,000 runs, the simulator picks garment, fibre, size mix, width, fabric weight (gsm) and fabric length, then adds the losses that happen on the cutting-room floor.

**Where:** `src/offcut/simulate.py`, `simulate_run()`, `simulate()`

**In:** random but seeded choices. **Out:** one row per run, including the weighed offcut kg.

```python
ply_len = (m_len + 2 * end_allow / 100) * (1 + spread)
roll_m = rng.uniform(20, 30) * 1000 / (gsm * width) if g.knit else rng.uniform(60, 120)
plies_per_roll = int(roll_m // ply_len)
...
remnant_m = n_rolls * (roll_m - plies_per_roll * ply_len)
...
weighed = offcut_true * recovery * (1 + rng.gauss(0, 0.01))
```

- `ply_len`: each layer of fabric is laid a little longer than the marker at each end (end allowance), plus spreading loss (tension, slippage, splices).
- `roll_m`: knit rolls are sold by weight (20 to 30 kg), so heavier or wider knit means a shorter roll; woven rolls are 60 to 120 m.
- `plies_per_roll`: a roll rarely divides into whole plies.
- `remnant_m`: the leftover at the end of each roll. Part is reused, the rest is waste.
- `weighed`: some lint and sweepings are never weighed (`recovery`), plus 1% weighing noise.

Selvedge trim (1 to 2 cm per edge on wovens) and defects are also simulated. Everything is seeded (`seed=11`), so the same 8,000 runs come out every time.

**Why this way:** this is exactly the gap between the marker and reality that a model has to learn. A test (`tests/test_offcut.py::test_mass_balance_and_gap`) checks that real waste always exceeds what the marker alone predicts.

### Step 4. Land, check and split the data (bronze, silver, gold)

**What happens:** raw runs are written to CSV (bronze), checked against a data contract and written to a staged CSV with a quality report (silver), then tagged train or test (gold).

**Where:** `src/offcut/pipeline.py`, `extract()`, `validate()`, `stage()`, `features()`

```python
CONTRACT: Dict[str, Tuple[str, float, float]] = {
    "fabric_width_m": ("float", 1.2, 2.2),
    "gsm": ("float", 60, 500),
    "fabric_metres": ("float", 500, 60_000),
    "marker_efficiency": ("float", 0.6, 0.95),
    "input_kg": ("float", 1, None),
    "offcut_kg_weighed": ("float", 0, None),
    "offcut_ratio": ("float", 0.05, 0.6),
}
```

- Each line says: this column must exist, have no nulls, and sit inside this range.
- `validate()` also checks categories are known, `run_id` is unique, and mass balance holds (offcut can't weigh more than the fabric that went in).
- `stage()` writes `quality_report.json` and raises an error if anything fails, so bad data never reaches training.

The split:

```python
is_test = df["run_id"].apply(lambda s: int(s.split("-")[1]) % 5 == 0)
```

Every fifth run (run number divisible by 5) goes to test. That gives 6,400 train and 1,600 test.

**Why this way:** the split is deterministic, so results are reproducible. A random split is fine here because simulated runs are independent of each other and have no time order. (The code comment calls it a "hash" split; it is actually a simple modulo on the run number.)

### Step 5. Define the target and the features

**Target:** `offcut_ratio = offcut_kg_weighed / input_kg`. Predicting a ratio rather than kg means the model learns the waste behaviour, and kg comes back by multiplying by input kg.

**Features** (`pipeline.py`):

- `PRE_MARKER = ["garment", "fibre", "size_mix", "fabric_width_m", "gsm", "fabric_metres"]`: known from the order alone, before any marker exists. This is the model the website runs.
- `POST_MARKER = PRE_MARKER + ["marker_efficiency"]`: once the marker is made, its efficiency is added.

Categoricals are one-hot encoded with a fixed vocabulary (`encode()`), so the browser can rebuild exactly the same columns.

### Step 6. Train three quantile models (P10, P50, P90)

**Where:** `src/offcut/train.py`, `fit_quantiles()`

```python
QUANTILES = {"p10": 0.10, "p50": 0.50, "p90": 0.90}
PARAMS = dict(n_estimators=250, max_depth=3, learning_rate=0.06, subsample=0.8,
              min_samples_leaf=20, random_state=11)

def fit_quantiles(X: pd.DataFrame, y: pd.Series) -> dict:
    return {k: GradientBoostingRegressor(loss="quantile", alpha=a, **PARAMS).fit(X, y)
            for k, a in QUANTILES.items()}
```

- Three separate gradient-boosted models, one per quantile. `loss="quantile"` with `alpha=0.1` trains the P10 model, and so on.
- 250 shallow trees (depth 3), each nudging the prediction by 6% of its suggestion (`learning_rate=0.06`), each trained on a random 80% of rows (`subsample=0.8`), with at least 20 runs per leaf.

**Why this way:** a planner needs a range, not one number. A recycler contract can be written against the P10 ("we're confident at least this much will come").

### Step 7. Compare against real baselines

**Where:** `train.py`, `main()` and `metrics()`

- **Rule of thumb:** a flat 15% of fabric becomes offcut.
- **Marker only:** `1 - marker_efficiency`, which is what CAD reports today.
- **ML pre-marker** and **ML post-marker**.

```python
err_pp = np.abs(y_true - p50) * 100
kg_err = np.abs(y_true - p50) * input_kg
kg_true = y_true * input_kg
"mape_kg": round(float((kg_err / kg_true).mean() * 100), 2),
"within_15pct_kg": round(float((kg_err / kg_true <= 0.15).mean() * 100), 1),
"bias_pp": round(float(((p50 - y_true) * 100).mean()), 3),
```

- `err_pp`: error in percentage points of fabric.
- `mape_kg`: mean absolute percentage error on offcut kg. (Input kg cancels out, so this equals the percentage error on the ratio.)
- `within_15pct_kg`: share of runs where the forecast is within 15% of the true kg.
- `bias_pp`: average signed error. Negative means under-forecasting.
- Coverage: share of runs where the truth falls between P10 and P90.

### Step 8. Export the model so it runs in a browser

**Where:** `src/offcut/export.py`, `export_quantile_model()`, `predict_json()`; `site/forecast.js`

Each tree is saved as parallel arrays: feature index `f`, threshold `t`, left child `l`, right child `r`, value `v`. A prediction is `init + learning_rate * sum(leaf values)`.

```javascript
function walk(tree, x) {
  let n = 0;
  while (tree.l[n] !== -1) n = Math.fround(x[tree.f[n]]) <= tree.t[n] ? tree.l[n] : tree.r[n];  // float32, as scikit-learn
  return tree.v[n];
}
```

- Start at the root (node 0). While the node has children, compare the input feature with the threshold and go left or right.
- `Math.fround` converts the input to a 32-bit float before comparing, as scikit-learn does. This is the bug fix (see section 5).
- Return the leaf value.

`forecast.js` also sorts the three quantiles before returning them, as a guard against quantile crossing.

**Why this way:** the website forecast needs no server and no Python. The same JSON is used by the API and the agent (via `service.py`), so there is one model everywhere.

---

## 3. Concepts, from scratch

### Simulation from first principles
**Definition:** generating data from a model of how the process works, rather than collecting it.
**Example:** a roll is 90 m, each ply is 5.8 m, so 15 plies fit and 3 m is left over as a remnant.
**Why it matters here:** no public factory cutting data exists. The simulation proves the method and pipeline; it does not prove real-world accuracy.

### Marker and marker efficiency
**Definition:** the marker is the cutting layout. Efficiency = area of pattern pieces / (usable width x marker length).
**Example:** pieces total 9.0 m², fabric is 1.8 m wide, marker is 5.75 m long, so 10.35 m² is laid. Efficiency 87%, planned waste 13%.
**Why it matters:** it's what the industry uses today, so it's one of my baselines.

### Quantile regression
**Definition:** instead of predicting the average outcome, predict a chosen percentile of it.
**Analogy:** a commute. "Usually 30 minutes (P50), but 1 in 10 days it's over 45 (P90)." You plan a meeting on the P90, not the average.
**Why it matters:** offcut planning needs a range. The P10 tells a recycler the minimum they can count on.

### Pinball loss (quantile loss)
**Definition:** the loss function that makes a model learn a quantile. For quantile q, under-predicting costs q per unit of error and over-predicting costs (1 - q).
**Worked example:** P90 model, truth 20 kg. Predict 18 (under by 2): loss 0.9 x 2 = 1.8. Predict 22 (over by 2): loss 0.1 x 2 = 0.2. Under-predicting is nine times more expensive, so the model learns to sit high, at the point where only 10% of outcomes are above it.
**Why it matters:** `loss="quantile", alpha=0.9` is exactly this.

### P10, P50, P90 and interval coverage
**Definition:** P10 = 10% of outcomes should fall below it; P50 = median; P90 = 90% should fall below. So P10 to P90 should contain 80% of outcomes. Coverage is the share that actually does.
**Example:** across 100 runs, if 77 land between P10 and P90, coverage is 77%: a bit narrow, because the target is 80%.
**Why it matters:** a range is only useful if it's honest. Coverage is the check.

### Quantile crossing
**Definition:** because the three quantile models are trained separately, occasionally the "P10" comes out above the "P50".
**Fix used:** sort the three values (`sorted(ratio.values())` in `service.py`, `.sort()` in `forecast.js`).

### Gradient boosting
**Definition:** build many small decision trees in sequence; each new tree tries to fix the errors the previous ones left. The final prediction is the starting value plus a small step (learning rate) times the sum of all the trees.
**Analogy:** a golfer. First shot gets near the green, each putt corrects what's left, and small careful putts (low learning rate) beat one big swing.
**Why it matters:** it handles interactions (say, jeans plus narrow fabric) and non-linear effects without me hand-crafting them, and it works well on tabular data.

### Decision tree, split, threshold, leaf
**Definition:** a tree asks yes/no questions ("is fabric width <= 1.745?") and ends in a leaf with a number.
**Why it matters:** the export saves exactly these questions and leaf values.

### Hyperparameters
`n_estimators` (number of trees), `max_depth` (how many questions per tree), `learning_rate` (step size), `subsample` (fraction of rows per tree, adds randomness and reduces overfitting), `min_samples_leaf` (stops leaves built on tiny groups).

### One-hot encoding
**Definition:** turn a category into 0/1 columns. `garment=tee` becomes `[1,0,0,0,0]` across tee, hoodie, shirt, jeans, dress.
**Why it matters:** the browser rebuilds the same columns from the feature names in the JSON, so the order and vocabulary must be fixed.

### Train/test split
**Definition:** train on one set of rows, measure on rows the model never saw.
**Here:** 6,400 train, 1,600 test, deterministic by run number. A random-style split is fine because simulated runs have no time order. (Contrast with part 04, where a time-based split is essential.)

### Data leakage
**Definition:** the model sees information at training time that it won't have at prediction time, so test results look better than reality.
**Here:** the pre-marker model deliberately excludes marker efficiency, because it isn't known yet when the order arrives. Hidden process parameters like `selvedge_cm` or `defect_rate` are in the data but are never features: a factory doesn't know them in advance.

### Baselines
**Definition:** the simple methods you have to beat for a model to be worth anything.
**Here:** the 15% rule of thumb and the marker figure, both used in industry today. Beating a straw man proves nothing; beating what planners actually use does.

### Error metrics: MAE in percentage points, MAPE, within ±15%, bias
- **MAE (pp):** average absolute error in percentage points of fabric. Truth 19%, forecast 17%: error 2 pp.
- **MAPE:** average absolute error as a percentage of the true value. Truth 1,000 kg, forecast 920 kg: 8% error.
- **Within ±15%:** share of runs close enough to plan on. Easy to explain to a factory.
- **Bias:** average signed error. The marker has bias of about -4.4 pp, so it always under-forecasts.

### Medallion layout (bronze, silver, gold)
**Definition:** keep raw data untouched (bronze), a cleaned and checked version (silver), and analysis-ready tables (gold).
**Why it matters:** if something goes wrong you can always rebuild from bronze. Covered in more depth in part 02.

### Data contract
**Definition:** a written rule for what valid data looks like: columns, types, allowed ranges, allowed categories. Data that breaks the contract is stopped, not silently passed on.
**Here:** `CONTRACT` and `validate()` in `pipeline.py`; a unit test feeds in a "sock" garment and a 0.9 offcut ratio and checks both are caught.

### Float32 vs float64
**Definition:** computers store decimals with limited precision. float64 has about 16 significant digits; float32 about 7. The number 1.57 isn't exactly representable in either, and its float32 version is slightly different from its float64 version.
**Why it matters:** see section 5.

### Mass balance
**Definition:** what goes in must equal what comes out. Fabric in = cut panels + offcut.
**Here:** a contract check and a unit test.

---

## 4. The real results (simulated data), and how to read them

From `models/metrics.json`, 1,600 held-out simulated runs (6,400 used for training):

| Method | Mean % error on offcut kg | Within ±15% | MAE (pp) | Bias (pp) | P10 to P90 coverage |
|---|---|---|---|---|---|
| Rule of thumb (15%) | 20.25% | 39.2% | 4.305 | -3.998 | n/a |
| Marker only | 23.29% | 11.1% | 4.366 | -4.366 | n/a |
| ML pre-marker (website model) | **8.8%** | **82.4%** | 1.62 | -0.001 | 76.8% |
| ML post-marker | 4.87% | 96.7% | 0.906 | -0.148 | 78.0% |

Pre-marker MAE by garment (pp): dress 2.16, shirt 1.86, hoodie 1.6, jeans 1.23, tee 1.22.

From `data/staged/quality_report.json`: 8,000 rows, no contract violations, mean offcut ratio 0.1896 (about 19%), from 0.0882 to 0.3405. By garment: dress 0.2456, jeans 0.197, shirt 0.178, hoodie 0.1707, tee 0.1583.

**How to read it:**

- The headline: 8.8% error vs 20.3% for the rule of thumb, which is roughly 57% lower error, on simulated runs.
- The marker is the worst baseline on percentage error and has a strong negative bias: it under-forecasts by about 4.4 pp of fabric because it can't see ply ends, roll remnants, spreading loss and defects.
- The rule of thumb's bias is also negative (-4.0 pp) because the simulated average is about 19%, not 15%.
- The ML model's bias is essentially zero.
- Coverage of 76.8% is a little below the 80% target, so the range is slightly too narrow. I report that rather than hide it.
- Adding the marker (post-marker) halves the error again, so the marker is useful information; it just isn't enough on its own.
- Dresses are hardest: curved pieces and lower, more variable efficiency.

---

## 5. What went wrong or surprised me, and what it taught me

### The float32 browser export bug
**What happened:** the first browser export rounded the split thresholds when writing them to JSON. scikit-learn's trees compare each input as a 32-bit float against a threshold that sits between neighbouring 32-bit values. Once the thresholds were rounded, an input right at the edge (the README's example is a 1.57 m roll width) could go left in scikit-learn and right in the browser, giving a different forecast.

**The fix:** `export.py` writes thresholds at full precision (`"t": [float(x) for x in tr.threshold]`), and both the Python reference evaluator (`predict_json`) and `forecast.js` cast inputs to float32 (`np.float32` / `Math.fround`) before comparing. A test, `tests/test_offcut.py::test_json_matches_sklearn`, trains on 400 runs, exports, and checks the JSON predictions match scikit-learn to 3 decimal places for all three quantiles.

**What it taught me:** when you move a model between languages, "nearly the same" is not the same. You need a parity test that proves the exported model gives the same answers as the original, especially at boundaries.

### The marker gap was bigger than I expected
The marker misses about a quarter of the weighed volume in simulation (bias -4.4 pp on an average of about 19%). That's the case for the product: planning on the marker figure leaves a recycler short.

### Coverage slightly under target
The P10 to P90 range covers 76.8%, not 80%. It's a small miss but a real one. A fix would be conformal calibration of the interval or slightly widening it, checked on held-out data.

---

## 6. Honest limits

- **Simulated, not factory data.** The simulator is calibrated to published ranges (marker efficiency, roll lengths, selvedge widths), but it's still my model of reality. The first pilot goal is ±15% on real weighed offcuts.
- **Not a customer.** No factory has used this yet.
- The nesting is a rectangle approximation with a calibration factor, not commercial nesting software.
- Five garment types and four fibres. A real factory has many more styles.
- Coverage is 76.8% against an 80% target.
- Grading lots and recycler profiles (`grading.py`, `data/recyclers_sample.json`) are illustrative; the 5 recycler profiles are fictional.

---

## 7. How to run it yourself

From the repo root (`ThreadFutures/`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make offcuts    # python -m offcut.pipeline then python -m offcut.train
make site       # copies models/pre_marker_model.json into site/model.js
make test       # runs the pytest suite, including the export parity test
```

Try one forecast end to end (forecast, graded lots, recycler matches):

```bash
PYTHONPATH=src python -m offcut.service
```

Outputs: `data/raw/runs.csv`, `data/staged/runs.csv`, `data/staged/quality_report.json`, `data/features/runs.csv`, `models/metrics.json`, `models/pre_marker_model.json`, `docs/figures/error_by_method.png`, `docs/figures/pred_vs_actual.png`.

---

## 8. Glossary

- **Offcut:** fabric left after garment pieces are cut.
- **Marker:** the cutting layout of pattern pieces on the fabric.
- **Marker efficiency:** piece area divided by laid fabric area.
- **Ply / spread:** one layer of fabric / the stack of layers cut together.
- **Selvedge:** the finished edge of woven fabric, trimmed off.
- **gsm:** grams per square metre, the fabric's weight.
- **Grading:** scaling pattern pieces between sizes.
- **Size mix:** how many of each size are cut in one marker.
- **Offcut ratio:** weighed offcut kg divided by input fabric kg (the target).
- **Quantile regression:** predicting a percentile instead of the mean.
- **Pinball loss:** the asymmetric loss used for quantile regression.
- **P10 / P50 / P90:** the 10th, 50th and 90th percentile forecasts.
- **Coverage:** share of outcomes falling inside the P10 to P90 range.
- **Quantile crossing:** separately trained quantiles coming out in the wrong order.
- **Gradient boosting:** many small trees added in sequence, each fixing the last one's errors.
- **Learning rate:** how much each tree's correction is scaled down.
- **One-hot encoding:** turning a category into 0/1 columns.
- **Baseline:** the simple method a model has to beat.
- **MAPE:** mean absolute percentage error.
- **Bias:** average signed error.
- **Data leakage:** using information at training time that isn't available at prediction time.
- **Data contract:** written rules for valid data, enforced in code.
- **Medallion layout:** bronze (raw), silver (clean), gold (ready to analyse).
- **float32:** 32-bit floating point, about 7 significant digits.
- **Parity test:** a test that checks two implementations give the same answer.
- **`Math.fround`:** JavaScript function that rounds a number to float32.
