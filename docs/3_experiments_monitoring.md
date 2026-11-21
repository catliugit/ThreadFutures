# 3. Experiments and monitoring

Checking whether an effect is real and whether a model still holds: the markdown difference-in-differences and pilot power analysis (Part 05) and the stall-risk model's monitoring report (Part 06).

Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. The code described here is earlier, exploratory technical work, not the product. Nothing new is built before the go / pivot / stop decision on Fri 26 Feb 2027, and any early pilot runs by hand (spreadsheet and email). See [ARCHITECTURE.md](ARCHITECTURE.md) for how the parts fit together.

Each part starts with a header block (discipline, methodology, tools, status), then the short part note, then the full step-by-step guide.

## Contents

- [Part 05: Experimentation and causal analysis](#part-05-experimentation-and-causal-analysis)
  - [Part 05 step by step](#part-05-step-by-step)
- [Part 06: Model monitoring](#part-06-model-monitoring)
  - [Part 06 step by step](#part-06-step-by-step)

---

## Part 05: Experimentation and causal analysis

**Discipline:** Data Science / Data Analytics (primary / secondary)  
**Methodology:** `src/stock/experiment.py` estimates each line's first markdown with a stacked difference-in-differences: statsmodels OLS with stack fixed effects and SKU-clustered standard errors, 4 weeks either side, 5 nearest-sales controls from the same launch cohort, plus a placebo pre-trend test. It then sizes a pilot with `TTestIndPower` and analyses one simulated pilot with Welch's t-test and a bootstrap confidence interval.  
**Tools:** statsmodels, SciPy, DuckDB, pandas, NumPy  
**Status:** Maybe later: grouped with the stall-risk model.

**Build state:** Built · **Data label:** Real data (markdowns) + simulated pilot  

### In one line
Asks two questions: do markdowns actually sell more units, and how many batches a fair comparison would need to show that selling through Thread Futures returns more money to a brand than a liquidator?

### Why it matters
We believe brands will only pay if the recovery uplift is shown (to test).

### Data
Markdowns: real weekly sales from part 2. Pilot: simulated, from stated planning assumptions.

### Method
Stacked difference-in-differences: 768 products whose list price first dropped 15% or more, each compared with the 5 never-marked-down products from the same launch cohort with the most similar pre-period sales, over the same calendar weeks (4 before, 4 after), with standard errors clustered by product. A placebo test on the pre-period checks parallel trends. Pilot: power analysis (pooled-variance two-sample t-test, statsmodels `TTestIndPower`), then one simulated pilot analysed with Welch's t-test and a bootstrap confidence interval.

### Tools
statsmodels, SciPy, DuckDB, pandas, NumPy

### Result
The raw estimate is +125% units after a markdown, but the placebo test failed (marked-down lines were already gaining beforehand, p < 0.001), so it is reported as an upper bound, not a clean effect. Pilot: with 8p vs 11p recovered per £ of retail value (sd 6p), a randomised pilot needs 64 batches per arm for 80% power.

### Honest limits
Observational markdown data; price changes may partly reflect wholesale order mix. Pilot numbers are assumptions until a real pilot runs.

### Where it lives
src/stock/experiment.py, models/experiment_results.json

### Part 05 step by step

**Build state:** Built · **Data label:** Part A uses REAL OPEN RETAIL DATA (markdowns in UCI Online Retail II). Part B is a SIMULATED pilot from stated planning assumptions.
**Code:** `src/stock/experiment.py`
**Numbers from:** `models/experiment_results.json`

---

#### 1. The question this stage answers

Two questions. A: do markdowns actually sell more units, or would those products have sold anyway? B: if Thread Futures sells some of a brand's unsold batches to vetted buyers and the brand's usual liquidator takes the others, how many batches would it take to show we return more money?

A fashion brand cares because markdowns cost margin, and it only makes sense to pay for a resale service if the extra money back is shown, not just claimed. Both questions are about telling cause from coincidence.

---

#### 2. The pipeline, step by step

##### Part A: markdown effect (real data, observational)

###### Step 1. Find each product's first real markdown

```sql
with first_md as (
    select stock_code, min(week_start) as md_week
    from fct_sku_weekly
    where markdown_pct >= {THRESHOLD} and weeks_since_launch >= {WINDOW}
    group by 1
),
```

- `THRESHOLD = 0.15`, `WINDOW = 4`. The first week a product's list price was at least 15% below its launch price, and at least 4 weeks after launch (so there are 4 "before" weeks to compare).
- Only markdowns between 1 March 2010 and 1 October 2011 are kept, so the 4 weeks before and after fall inside the data.

###### Step 2. Find possible controls

```sql
ever_md as (select distinct stock_code from fct_sku_weekly where markdown_pct >= 0.05),
...
controls as (
    select d.stock_code, d.launch_cohort from dim_sku d
    where d.stock_code not in (select stock_code from ever_md)
),
```

- A control is a product that was never marked down by even 5%. Using a stricter "never touched" rule keeps controls clean.

###### Step 3. Build one "stack" per marked-down product

```sql
units as (
    select t.stock_code as stack, t.stock_code, t.md_week, 1 as treated from treated t
    union all
    select t.stock_code, c.stock_code, t.md_week, 0 from treated t join controls c using (launch_cohort)
),
cal as (select u.*, unnest(range(-{WINDOW}, {WINDOW})) as rel_week from units u),
```

- Each stack is one treated product plus every never-marked-down product from the **same launch cohort**, all observed over the **same calendar weeks** (relative weeks -4 to +3 around the markdown week).
- That's what "stacked" means: many small experiments, each with its own calendar window, stacked into one regression.

**Why:** comparing in the same weeks removes seasonality and shocks common to everyone (Christmas, a site outage). Comparing within a launch cohort removes life-cycle differences.

###### Step 4. Log outcome and pre/post summaries

```sql
    ln(1 + coalesce(f.units_sold, 0)) as y,
...
           avg(y) filter (where rel_week < 0)                                   as pre_y,
           avg(y) filter (where rel_week >= 0)                                  as post_y,
           avg(y) filter (where rel_week in (-2, -1)) - avg(y) filter (where rel_week in (-4, -3)) as placebo_diff
```

- `y = ln(1 + units)`: log units, with +1 so zero-sale weeks work. Effects on a log scale read as percentage changes.
- `pre_y`, `post_y`: average log units before and after.
- `placebo_diff`: the change *within* the before period (weeks -2, -1 versus -4, -3). Used to test parallel trends.

###### Step 5. Match: keep the 5 most similar controls

```sql
matched as (
    select u.*, row_number() over (partition by u.stack order by abs(u.pre_units - t.pre_units)) as rk
    from unit_summary u join unit_summary t on t.stack = u.stack and t.treated = 1
    where u.treated = 0 and u.pre_units > 0
)
...
select stack, stock_code, treated, pre_units, post_y - pre_y, placebo_diff from matched where rk <= {K_CONTROLS}
```

- For each stack, rank controls by how close their total pre-period units are to the treated product's, and keep the closest 5 (`K_CONTROLS = 5`).
- `diff = post_y - pre_y`: each product's own before-to-after change.

###### Step 6. Estimate with a stacked regression and clustered standard errors

```python
def _stacked(df: pd.DataFrame, outcome: str):
    # Unit fixed effects are differenced out (post minus pre); stack fixed effects hold
    # calendar weeks and launch cohort constant within each comparison.
    return smf.ols(f"{outcome} ~ treated + C(stack)", data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df.stock_code.astype("category").cat.codes})
```

- Outcome = each product's before-to-after change. Taking the difference already removes each product's own baseline level (that's the first "difference").
- `treated`: 1 for the marked-down product, 0 for controls. Its coefficient is how much more the treated product changed than its matched controls (the second "difference"). That's the DiD estimate.
- `C(stack)`: a separate intercept for each stack, so every comparison is within its own weeks and cohort.
- `cov_type="cluster"` by product: a control can appear in several stacks, so its rows aren't independent. Clustering widens the standard errors to account for that.

Then the effect is converted from log units to a percentage with `np.expm1(b) * 100`, and the same regression is run on `placebo_diff`.

##### Part B: pilot design (simulated)

###### Step 7. Power analysis

```python
PILOT = {"liquidator_mean": 0.08, "routed_mean": 0.11, "sd": 0.06, "alpha": 0.05, "power": 0.8}

def pilot_design(seed: int = 3) -> dict:
    d = (PILOT["routed_mean"] - PILOT["liquidator_mean"]) / PILOT["sd"]
    n = TTestIndPower().solve_power(effect_size=d, alpha=PILOT["alpha"], power=PILOT["power"])
    n = int(np.ceil(n))
```

- Assumptions: a liquidator recovers 8p per £ of original retail value; routing through Thread Futures recovers 11p; batch-to-batch standard deviation 6p. These are planning assumptions, stated in the code, not measurements.
- `d = (0.11 - 0.08) / 0.06 = 0.5`: Cohen's d, the effect in standard deviations.
- `solve_power`: how many batches per arm for an 80% chance of detecting that effect at a 5% significance level. Rounded up.

###### Step 8. Simulate one pilot and analyse it two ways

```python
    a = rng.normal(PILOT["liquidator_mean"], PILOT["sd"], n).clip(0)
    b = rng.normal(PILOT["routed_mean"], PILOT["sd"], n).clip(0)
    t = stats.ttest_ind(b, a, equal_var=False)
    boots = [rng.choice(b, n).mean() - rng.choice(a, n).mean() for _ in range(5000)]
```

- Draw 64 liquidator batches and 64 routed batches from the assumed distributions (no negative recovery).
- Welch's t-test: compares the means without assuming equal variances.
- Bootstrap: resample each arm with replacement 5,000 times, record the difference in means, and take the 2.5th and 97.5th percentiles as a 95% confidence interval.

**Why simulate:** to check the analysis plan works from start to finish before any real batches, and to show a buyer what the result would look like.

---

#### 3. Concepts, from scratch

##### Correlation vs causation
Marked-down products might sell more because of the markdown, or because retailers mark down products that were about to pick up anyway. The data alone can't tell; the design has to.

##### Randomised experiment (A/B test)
**Definition:** randomly assign units to treatment or control, so the only systematic difference between the groups is the treatment.
**Here:** Part B designs one. Part A can't, because markdowns already happened, so it's observational.

##### Difference-in-differences (DiD)
**Definition:** compare the before-to-after change in the treated group with the before-to-after change in a control group. The control's change estimates what would have happened anyway.
**Worked example:** treated product goes from 10 to 18 units a week (+8). Similar controls go from 10 to 12 (+2). DiD estimate = 8 - 2 = +6 units caused by the markdown.
**Why it matters:** it removes fixed differences between products and common shocks over time.

##### Stacked DiD
**Definition:** build a separate small DiD for each treated unit with its own time window and controls, then estimate them together with a fixed effect per stack.
**Why:** markdowns happen at different times. Classic two-way fixed-effects DiD with staggered timing can compare already-treated units with newly treated ones and give biased answers. Stacking avoids that.

##### Parallel trends
**Definition:** the key assumption of DiD: without treatment, treated and control groups would have followed the same trend.
**Analogy:** two runners at different speeds are fine to compare, as long as neither was already accelerating before the starting gun.

##### Placebo test (pre-trend test)
**Definition:** apply the same method to a period where no treatment happened. If you find an "effect", the parallel trends assumption is in doubt.
**Here:** compare the change from weeks -4/-3 to -2/-1, all before the markdown.

##### Matched controls
**Definition:** pick controls that look like the treated unit before treatment.
**Here:** 5 nearest by pre-period units, within the same launch cohort.

##### Fixed effects
**Definition:** a separate intercept for each group, which absorbs anything constant within that group.
**Here:** `C(stack)` absorbs everything shared within a stack (calendar weeks, cohort).

##### Log outcome and percentage effects
**Definition:** model ln(1 + units). A coefficient b means units are multiplied by e^b.
**Worked example:** b = 0.8105 gives e^0.8105 - 1 ≈ 1.249, so +124.9%.

##### Clustered standard errors
**Definition:** standard errors that allow rows within a cluster (here, a product) to be correlated.
**Why it matters:** the same control can appear in many stacks. Treating those rows as independent would make the estimate look more precise than it is.

##### Confidence interval and p-value
- **95% confidence interval:** a range built so that, across repeated studies, 95% of such ranges would contain the true effect.
- **p-value:** if there were truly no effect, the probability of seeing a result at least this extreme. Small p-values say "unlikely to be chance" but say nothing about bias in the design.

##### Power analysis
**Definition:** working out the sample size needed to detect an effect of a given size with a given probability (power), at a given significance level (alpha).
**Why it matters:** an underpowered pilot is likely to "fail" even if the product works, which wastes everyone's time.

##### Effect size (Cohen's d)
**Definition:** difference in means divided by the standard deviation. 0.2 small, 0.5 medium, 0.8 large (common rules of thumb).
**Here:** 3p difference / 6p SD = 0.5.

##### Alpha and power
- **Alpha (0.05):** the false-positive rate you accept.
- **Power (0.8):** the chance of detecting a real effect of the assumed size.

##### Welch's t-test
**Definition:** a t-test comparing two means that doesn't assume equal variances. Safer default than Student's t-test.

##### Bootstrap confidence interval
**Definition:** resample your data with replacement many times, recompute the statistic each time, and use the spread of those results as the interval.
**Analogy:** if you can't run the pilot 5,000 times, pretend your sample is the population and resample from it.
**Why it matters:** no assumption that the difference is normally distributed.

---

#### 4. The real results, and how to read them

From `models/experiment_results.json`.

##### Part A: markdowns (real data)

| Item | Value |
|---|---|
| Design | Stacked DiD, 4 weeks either side, 5 nearest-sales controls per SKU from the same launch cohort |
| Marked-down (treated) SKUs | 768 |
| Distinct control SKUs | 1,580 |
| Effect on log units | 0.8105 |
| Effect as % | **+124.9%** |
| 95% CI | +106.4% to +145.0% |
| p-value | 1.27e-76 |
| Placebo pre-trend effect | 0.1607 (log units) |
| Placebo p-value | 0.000517 |

**How to read it:** taken at face value, a markdown of 15% or more is followed by about 2.25 times the weekly units compared with matched controls. But the placebo test finds a significant "effect" before any markdown happened: marked-down products were already gaining relative to controls (about 0.16 log units, p ≈ 0.0005). Parallel trends doesn't hold, so the +125% is reported as an **upper bound**, not a clean causal effect. The tiny main p-value doesn't rescue it: it measures noise, not bias.

##### Part B: pilot design (simulated)

| Item | Value |
|---|---|
| Assumptions | Liquidator 8p, routed 11p per £ retail value, SD 6p, alpha 0.05, power 0.8 |
| Effect size d | 0.5 |
| **Batches per arm** | **64** |
| Power with 10 / 20 / 30 / 40 / 60 / 80 batches per arm | 0.185 / 0.338 / 0.478 / 0.598 / 0.775 / 0.882 |
| Simulated uplift | 2.9p per £ |
| Welch p-value | 0.00665 |
| Bootstrap 95% CI | 0.85p to 4.93p |

**How to read it:** with these assumptions, 64 batches in each arm (128 in total) give an 80% chance of detecting a 3p difference. With only 20 per arm, you'd detect it about a third of the time. In the simulated pilot, the measured uplift was 2.9p (close to the assumed 3p) and the interval excludes zero.

---

#### 5. What went wrong or surprised me, and what it taught me

##### The failed placebo test
My first estimate said markdowns more than double sales, which felt too good. The placebo test showed marked-down products were already picking up before the price cut. Likely reasons: the retailer marks down products when it sees demand rising (to push volume), or price changes partly reflect a shift towards wholesale orders at lower unit prices. Either way, it breaks the assumption.

**What I did:** reported +125% as an upper bound and said why. I didn't hunt for a specification that made the placebo pass.

**What it taught me:** always run the falsification test, and let it change your headline. A huge, very significant effect is a reason for suspicion, not celebration.

**What I'd try next:** an event-study plot (effect week by week, -4 to +3) to see the shape of the pre-trend; matching on pre-period *trend* as well as level; or a synthetic control.

##### Assumptions drive the pilot size
The 64 batches come straight from three numbers I chose. If the true SD were larger, or the uplift smaller, the pilot would need far more batches. I say "with these assumptions" every time.

---

#### 6. Honest limits

- **Part A is observational, real open data, not fashion and not a customer.** Markdown timing isn't random.
- Price changes may partly reflect wholesale order mix (list price is the mode of small-order prices, but wholesale share can still shift).
- Only one markdown threshold (15%) and one window (4 weeks) tested.
- Matching is on pre-period level only, not trend.
- **Part B is simulated.** The 8p, 11p and 6p are planning assumptions. Real batches would replace them; no stock has been sold yet.
- The simulated pilot is one draw; another seed gives a different uplift and interval.

---

#### 7. How to run it yourself

```bash
make retail       # if not already there
make dbt          # builds fct_sku_weekly and dim_sku
make experiment   # python -m stock.experiment -> models/experiment_results.json
```

---

#### 8. Glossary

- **Causal effect:** the change caused by a treatment, compared with what would have happened otherwise.
- **Observational data:** treatment not assigned by the researcher.
- **Randomised experiment / A/B test:** treatment assigned at random.
- **Difference-in-differences:** treated change minus control change.
- **Stacked DiD:** one small DiD per treated unit, estimated together.
- **Parallel trends:** without treatment, both groups would have moved together.
- **Placebo test:** running the method where no effect should exist.
- **Pre-trend:** treated and control already diverging before treatment.
- **Upper bound:** the true effect is likely no larger than this.
- **Matched controls:** controls chosen to resemble treated units beforehand.
- **Launch cohort:** products launched in the same quarter.
- **Fixed effect:** a group-specific intercept.
- **Clustered standard errors:** errors allowing correlation within clusters.
- **Log outcome:** ln(1 + units), effects read as percentages.
- **Confidence interval:** range expected to contain the true value at a stated rate.
- **p-value:** chance of a result this extreme if there were no effect.
- **Power:** chance of detecting a real effect.
- **Alpha:** accepted false-positive rate.
- **Effect size (Cohen's d):** difference divided by standard deviation.
- **Welch's t-test:** two-sample t-test without equal-variance assumption.
- **Bootstrap:** resampling with replacement to estimate uncertainty.
- **Event study:** effect estimated separately for each week around treatment.
- **Synthetic control:** a weighted mix of controls built to match the treated unit's history.

---

## Part 06: Model monitoring

**Discipline:** Machine Learning / Data Science (primary / secondary)  
**Methodology:** `src/stock/monitor.py` reloads the stall-risk model, scores each launch quarter (ROC AUC, PR AUC, predicted vs actual stall rate), measures feature drift with a hand-written PSI over 10 quantile bins and SciPy's KS test, raises alerts at PSI > 0.25, KS p < 0.01 or AUC < 0.70, and writes `models/monitoring.json` and a static HTML report.  
**Tools:** SciPy, scikit-learn, pandas, joblib, HTML  
**Status:** Maybe later: grouped with the stall-risk model.

**Build state:** Built · **Data label:** Real open retail data  

### In one line
Checks whether the stall-risk model is still accurate and whether new data still looks like the training data.

### Why it matters
Models drift as seasons and ranges change. Proof of build, not the product: it shows how any model behind the service would be kept honest.

### Data
Later launch quarters the model never trained on (2010 Q4, 2011 Q1, 2011 Q2).

### Method
Per quarter: ROC AUC, PR AUC, predicted vs actual stall rate (calibration). Drift per feature: Population Stability Index and a Kolmogorov-Smirnov test. Alerts at PSI > 0.25, KS p < 0.01, AUC < 0.70. Static HTML report.

### Tools
SciPy, pandas, scikit-learn, HTML

### Result
Ranking stays good in two of three quarters (AUC 0.81, 0.65, 0.84), but calibration drifts: for 2011 Q2 launches the model predicted 13.6% would stall and only 1.7% did, because those lines sold into the Christmas peak. Strong drift flagged on several features.

### Honest limits
Small quarterly samples (70 to 178 SKUs).

### Where it lives
src/stock/monitor.py, models/monitoring.json, site/reports/monitoring.html (threadfutures.com/reports/monitoring.html)

### Part 06 step by step

**Build state:** Built · **Data label:** REAL OPEN RETAIL DATA (UCI Online Retail II). Not fashion, not a customer.
**Code:** `src/stock/monitor.py`; test in `tests/test_stock.py::test_psi_zero_for_same_distribution_and_large_for_shift`
**Output:** `models/monitoring.json`, `site/reports/monitoring.html`
**Numbers from:** `models/monitoring.json`

---

#### 1. The question this stage answers

Is the stall-risk model from part 04 still accurate on newer launches, and does the new data still look like the data it was trained on?

A fashion brand cares because ranges, seasons and customers change. A model that was right last year can quietly go wrong, and the merchandiser acting on its risk scores won't know unless someone checks. Monitoring is that check.

---

#### 2. The pipeline, step by step

##### Step 1. Load the model and the same features

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

##### Step 2. Accuracy per quarter

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

##### Step 3. Drift per feature: PSI

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

##### Step 4. Drift per feature: KS test

```python
ks = stats.ks_2samp(tr[f], g[f])
drift[f] = {"psi": round(psi(tr[f].to_numpy(), g[f].to_numpy()), 3), "ks_p": float(f"{ks.pvalue:.3g}")}
```

- Two-sample Kolmogorov-Smirnov test: are these two samples from the same distribution?

##### Step 5. Alerts

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

##### Step 6. Write JSON and a static HTML report

`run()` writes `models/monitoring.json`, then `render()` builds `site/reports/monitoring.html`: an accuracy and calibration table per quarter, a PSI table per feature (cells above 0.25 highlighted), and the offcut model's error by garment and P10 to P90 coverage (from part 01). Every value goes through `html.escape` where it's text.

**Why static HTML:** no server, no dashboard tool, nothing to break. It's published on the website at `site/reports/monitoring.html`.

##### Step 7. Test the drift metric itself

```python
def test_psi_zero_for_same_distribution_and_large_for_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    assert psi(a, rng.normal(0, 1, 5000)) < 0.02
    assert psi(a, rng.normal(1.5, 1, 5000)) > 0.25
```

- Same distribution: PSI should be near zero. Shifted by 1.5 standard deviations: PSI should be clearly above the alert threshold.

---

#### 3. Concepts, from scratch

##### Model monitoring
**Definition:** checking a deployed model's inputs and outputs over time.
**Two kinds:** *performance monitoring* (is it still right?) needs the true outcomes, which arrive late. *Drift monitoring* (do inputs look different?) works immediately.

##### Data drift vs concept drift
- **Data drift (covariate shift):** the inputs change. New launches sell more units per week than training launches did.
- **Concept drift:** the relationship between inputs and outcome changes. The same early sales pattern now means something different, for example because of Christmas.
**Here:** both appear. Inputs shifted (high PSI) and the stall rate for a given input pattern fell.

##### Population Stability Index (PSI)
**Definition:** a number summarising how much a distribution has shifted between two samples, using bins.
**Worked example:** two bins. Training: 50% / 50%. New: 70% / 30%.
(0.7 - 0.5) x ln(0.7/0.5) + (0.3 - 0.5) x ln(0.3/0.5) = 0.2 x 0.336 + (-0.2) x (-0.511) = 0.067 + 0.102 = 0.17.
**Common rules of thumb:** under 0.1 stable, 0.1 to 0.25 moderate shift, over 0.25 major shift.

##### Kolmogorov-Smirnov (KS) test
**Definition:** compares two cumulative distributions and finds the largest gap between them. The p-value says how surprising that gap would be if both samples came from the same distribution.
**Caveat:** with large samples tiny differences become "significant", and with discrete features (like month) the test is approximate.

##### Calibration (by period)
**Definition:** do predicted probabilities match observed rates? Here, at the level of a whole quarter: mean predicted probability vs actual stall rate.

##### ROC AUC and PR AUC (recap)
ROC AUC: ranking quality, 0.5 is random. PR AUC: focuses on the rare positive class; random equals the base rate. See part 04 for detail.

##### Ranking vs calibration
A model can order products correctly (good AUC) while its probabilities are all too high. Ranking is what you need for "review the riskiest 20%"; calibration is what you need for "how many lines will stall this quarter?"

##### Alert thresholds
**Definition:** fixed rules that turn a metric into "look at this". Simple and explainable; the risk is alert fatigue if they fire too often.

##### Quantile bins
**Definition:** bins with equal numbers of training rows, rather than equal widths. Robust to skewed features like units per week.

##### Static report
**Definition:** an HTML file generated by code. Reproducible, versioned and viewable anywhere.

---

#### 4. The real results, and how to read them

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

- **Ranking holds in 2010Q4** (0.81). 2011Q1 drops to 0.65, but it has only 70 SKUs (about 5 stalls at 7.1%), so that AUC is very noisy. The 0.84 in 2011Q2 rests on only about 3 stalls among 178 lines (1.7%), so AUC is not reliable for that quarter either.
- **Calibration drifts badly.** The model over-predicts in every quarter, and the gap widens: 27% vs 21%, then 20% vs 7%, then 14% vs 1.7%. For 2011 Q2 launches, the model expected about 1 in 7 to stall and only about 1 in 60 did. Those spring lines' weeks 12 to 25 ran into the Christmas season (from late summer onwards), when sales rise instead of collapsing.
- **Inputs shifted a lot.** Later launches sold more per week, to more customers, with fewer zero weeks than the training launches.
- **launch_month PSI is huge by construction.** Each test quarter contains only three months, while training covers many months, so this "drift" is expected. It's still useful: training launches run only from January to September 2010, so in 2010Q4 the model is being asked about launch months (Oct–Dec) it never saw in training.

---

#### 5. What went wrong or surprised me, and what it taught me

##### Over-prediction for 2011 Q2: 13.6% predicted vs 1.7% actual
This was the big finding. The model still ranked well, so a simple AUC check would have said "fine". Only the calibration check showed it was over-confident about stalling for lines selling into Christmas. A read-only check while writing this guide adds context: 27.6% of training launches stalled versus 10.6% of test launches, so the model learned in a higher-stall world.

**What it taught me:** monitor calibration, not just ranking. And monitoring is useful because it tells you exactly what to fix next: a seasonal feature (weeks to Christmas) and recalibration on recent data. That's planned as part 15.

##### PSI of 0.0 doesn't always mean "no drift"
`early_max_markdown` and `is_seasonal_christmas` show PSI 0.0 in every quarter. That's an artefact of my implementation: both features are mostly zero, so the decile edges collapse to fewer than three distinct values and the function returns 0. For binary or mostly-zero features, PSI should compare category shares directly. The KS p-values for them (0.08 to 1.0) don't suggest a big shift, but the 0.0 is not evidence by itself. That's a fix I'd make.

##### Many alerts at once
Nearly every feature alerts in every quarter. That's partly real (the business grew) and partly because these are small samples against a fixed training snapshot. In production I'd want alert priorities, so a merchandiser sees "calibration off by 12 points" before "launch_month PSI 5.24".

---

#### 6. Honest limits

- **Real open data, not fashion and not a customer.**
- **Small quarterly samples** (70 to 178 SKUs), so AUC and stall rates per quarter are noisy. No confidence intervals reported.
- Retrospective: this simulates monitoring on historical quarters, it isn't a live system.
- Performance metrics need outcomes, which arrive 26 weeks after launch. In live use, drift alerts come first and accuracy later.
- PSI returns 0 for low-cardinality features (section 5).
- Fixed thresholds (0.25, 0.01, 0.70) are common conventions, not tuned.
- Calibration is checked at quarter level only, not with a reliability curve across probability bands.

---

#### 7. How to run it yourself

```bash
make retail && make dbt && make stall   # monitoring needs the warehouse and the trained model
make offcuts                            # the report also reads models/metrics.json
make monitor                            # python -m stock.monitor -> models/monitoring.json, site/reports/monitoring.html
```

Then open `site/reports/monitoring.html` in a browser. It's also published at threadfutures.com/reports/monitoring.html.

---

#### 8. Glossary

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
