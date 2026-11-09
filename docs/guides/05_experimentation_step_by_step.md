# Part 05: Experimentation and causal analysis, step by step

**Status:** Built · **Data label:** Part A uses REAL OPEN RETAIL DATA (markdowns in UCI Online Retail II). Part B is a SIMULATED pilot from stated planning assumptions.
**Code:** `src/stock/experiment.py`
**Numbers from:** `models/experiment_results.json`

---

## 1. The question this stage answers

Two questions. A: do markdowns actually clear stock, or would those products have sold anyway? B: if Thread Futures runs a pilot routing unsold stock to better buyers, how many batches would it need to prove it recovers more money than the brand's usual liquidator?

A fashion brand cares because markdowns cost margin, and it only makes sense to pay for a routing service if the uplift is proven, not just claimed. Both questions are about telling cause from coincidence.

---

## 2. The pipeline, step by step

### Part A: markdown effect (real data, observational)

#### Step 1. Find each product's first real markdown

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

#### Step 2. Find possible controls

```sql
ever_md as (select distinct stock_code from fct_sku_weekly where markdown_pct >= 0.05),
...
controls as (
    select d.stock_code, d.launch_cohort from dim_sku d
    where d.stock_code not in (select stock_code from ever_md)
),
```

- A control is a product that was never marked down by even 5%. Using a stricter "never touched" rule keeps controls clean.

#### Step 3. Build one "stack" per marked-down product

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

#### Step 4. Log outcome and pre/post summaries

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

#### Step 5. Match: keep the 5 most similar controls

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

#### Step 6. Estimate with a stacked regression and clustered standard errors

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

### Part B: pilot design (simulated)

#### Step 7. Power analysis

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

#### Step 8. Simulate one pilot and analyse it two ways

```python
    a = rng.normal(PILOT["liquidator_mean"], PILOT["sd"], n).clip(0)
    b = rng.normal(PILOT["routed_mean"], PILOT["sd"], n).clip(0)
    t = stats.ttest_ind(b, a, equal_var=False)
    boots = [rng.choice(b, n).mean() - rng.choice(a, n).mean() for _ in range(5000)]
```

- Draw 64 liquidator batches and 64 routed batches from the assumed distributions (no negative recovery).
- Welch's t-test: compares the means without assuming equal variances.
- Bootstrap: resample each arm with replacement 5,000 times, record the difference in means, and take the 2.5th and 97.5th percentiles as a 95% confidence interval.

**Why simulate:** to check the analysis plan works end to end before any real pilot, and to show a buyer what the result would look like.

---

## 3. Concepts, from scratch

### Correlation vs causation
Marked-down products might sell more because of the markdown, or because retailers mark down products that were about to pick up anyway. The data alone can't tell; the design has to.

### Randomised experiment (A/B test)
**Definition:** randomly assign units to treatment or control, so the only systematic difference between the groups is the treatment.
**Here:** Part B designs one. Part A can't, because markdowns already happened, so it's observational.

### Difference-in-differences (DiD)
**Definition:** compare the before-to-after change in the treated group with the before-to-after change in a control group. The control's change estimates what would have happened anyway.
**Worked example:** treated product goes from 10 to 18 units a week (+8). Similar controls go from 10 to 12 (+2). DiD estimate = 8 - 2 = +6 units caused by the markdown.
**Why it matters:** it removes fixed differences between products and common shocks over time.

### Stacked DiD
**Definition:** build a separate small DiD for each treated unit with its own time window and controls, then estimate them together with a fixed effect per stack.
**Why:** markdowns happen at different times. Classic two-way fixed-effects DiD with staggered timing can compare already-treated units with newly treated ones and give biased answers. Stacking avoids that.

### Parallel trends
**Definition:** the key assumption of DiD: without treatment, treated and control groups would have followed the same trend.
**Analogy:** two runners at different speeds are fine to compare, as long as neither was already accelerating before the starting gun.

### Placebo test (pre-trend test)
**Definition:** apply the same method to a period where no treatment happened. If you find an "effect", the parallel trends assumption is in doubt.
**Here:** compare the change from weeks -4/-3 to -2/-1, all before the markdown.

### Matched controls
**Definition:** pick controls that look like the treated unit before treatment.
**Here:** 5 nearest by pre-period units, within the same launch cohort.

### Fixed effects
**Definition:** a separate intercept for each group, which absorbs anything constant within that group.
**Here:** `C(stack)` absorbs everything shared within a stack (calendar weeks, cohort).

### Log outcome and percentage effects
**Definition:** model ln(1 + units). A coefficient b means units are multiplied by e^b.
**Worked example:** b = 0.8105 gives e^0.8105 - 1 ≈ 1.249, so +124.9%.

### Clustered standard errors
**Definition:** standard errors that allow rows within a cluster (here, a product) to be correlated.
**Why it matters:** the same control can appear in many stacks. Treating those rows as independent would make the estimate look more precise than it is.

### Confidence interval and p-value
- **95% confidence interval:** a range built so that, across repeated studies, 95% of such ranges would contain the true effect.
- **p-value:** if there were truly no effect, the probability of seeing a result at least this extreme. Small p-values say "unlikely to be chance" but say nothing about bias in the design.

### Power analysis
**Definition:** working out the sample size needed to detect an effect of a given size with a given probability (power), at a given significance level (alpha).
**Why it matters:** an underpowered pilot is likely to "fail" even if the product works, which wastes everyone's time.

### Effect size (Cohen's d)
**Definition:** difference in means divided by the standard deviation. 0.2 small, 0.5 medium, 0.8 large (common rules of thumb).
**Here:** 3p difference / 6p SD = 0.5.

### Alpha and power
- **Alpha (0.05):** the false-positive rate you accept.
- **Power (0.8):** the chance of detecting a real effect of the assumed size.

### Welch's t-test
**Definition:** a t-test comparing two means that doesn't assume equal variances. Safer default than Student's t-test.

### Bootstrap confidence interval
**Definition:** resample your data with replacement many times, recompute the statistic each time, and use the spread of those results as the interval.
**Analogy:** if you can't run the pilot 5,000 times, pretend your sample is the population and resample from it.
**Why it matters:** no assumption that the difference is normally distributed.

---

## 4. The real results, and how to read them

From `models/experiment_results.json`.

### Part A: markdowns (real data)

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

### Part B: pilot design (simulated)

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

## 5. What went wrong or surprised me, and what it taught me

### The failed placebo test
My first estimate said markdowns more than double sales, which felt too good. The placebo test showed marked-down products were already picking up before the price cut. Likely reasons: the retailer marks down products when it sees demand rising (to push volume), or price changes partly reflect a shift towards wholesale orders at lower unit prices. Either way, it breaks the assumption.

**What I did:** reported +125% as an upper bound and said why. I didn't hunt for a specification that made the placebo pass.

**What it taught me:** always run the falsification test, and let it change your headline. A huge, very significant effect is a reason for suspicion, not celebration.

**What I'd try next:** an event-study plot (effect week by week, -4 to +3) to see the shape of the pre-trend; matching on pre-period *trend* as well as level; or a synthetic control.

### Assumptions drive the pilot size
The 64 batches come straight from three numbers I chose. If the true SD were larger, or the uplift smaller, the pilot would need far more batches. I say "with these assumptions" every time.

---

## 6. Honest limits

- **Part A is observational, real open data, not fashion and not a customer.** Markdown timing isn't random.
- Price changes may partly reflect wholesale order mix (list price is the mode of small-order prices, but wholesale share can still shift).
- Only one markdown threshold (15%) and one window (4 weeks) tested.
- Matching is on pre-period level only, not trend.
- **Part B is simulated.** The 8p, 11p and 6p are planning assumptions. A real pilot replaces them.
- The simulated pilot is one draw; another seed gives a different uplift and interval.

---

## 7. How to run it yourself

```bash
make retail       # if not already there
make dbt          # builds fct_sku_weekly and dim_sku
make experiment   # python -m stock.experiment -> models/experiment_results.json
```

---

## 8. Glossary

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
