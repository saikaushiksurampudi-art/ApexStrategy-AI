# The podium model

## What it predicts

Two binary classifiers, trained on the same feature matrix:

| Target | Definition | Base rate (2021–2025) |
|---|---|---|
| `podium` | Finishing position ≤ 3 | ~15% |
| `points` | Finishing position ≤ 10 | ~50% |

These were chosen deliberately over "predict the finishing order of all 20
drivers". Ordering a full grid is a much harder problem, and a model that
claimed to do it would be selling a precision it does not have. Podium and
points probabilities are useful, checkable, and honest about their uncertainty.

Two derived numbers are also shown, and both are labelled in the UI as
derived rather than separately modelled:

- **Win probability** — podium scores rescaled so the field sums to 1, since
  there is exactly one winner.
- **Expected position** — a rank over a blended score, giving the dashboard an
  ordering. It is not a calibrated position forecast.

---

## Architecture

Each target is scored as:

```
P = w · logistic_regression(features) + (1 − w) · grid_conversion_rate[grid_slot]
```

### Why the grid term is explicit

Starting position dominates Formula 1 results. A lookup table of "how often does
P4 finish on the podium", built from history alone, is a strong predictor — and
in the first iteration of this project it **beat** a gradient-boosted model on
every metric.

Two options followed: quietly drop the baseline comparison, or change the model.
The model changed. The grid conversion rate is now an explicit component, so the
model starts from baseline-level information and spends its capacity learning
*adjustments* — form, reliability, circuit history, qualifying pace — rather than
rediscovering the shape of the grid curve from scratch. The same rates are also
supplied as features (`grid_prior_podium`, `grid_prior_points`).

### Why logistic regression

Gradient boosting was tried (`HistGradientBoostingClassifier`, tuned, with
isotonic and sigmoid calibration) and rejected. With ~1,800 training rows it
overfits and scores worse on held-out seasons:

| Estimator | Podium log loss (2025) | Points log loss (2025) |
|---|---|---|
| Gradient boosting, calibrated | 0.2040 | 0.5132 |
| Gradient boosting, small | 0.1976 | 0.5107 |
| **Logistic regression (C=0.1)** | **0.1934** | **0.4896** |
| Logistic regression + grid blend | **0.1922** | **0.4859** |

Regularised linear models are a better fit for this data volume, and they carry
a second advantage: the occlusion explanations are more stable, because the
response surface has no sharp steps for a single feature change to fall off.

### How the blend weight is chosen

On a **validation season carved out of the training range** — never on the test
seasons. With 2021–2024 as training data, the weight is selected on 2024 after
fitting on 2021–2023, then the final model is refit on all four seasons using
that weight. Tuning the weight on the test set would have produced a better
number and a meaningless one.

Current selected weights: `podium = 0.60`, `points = 0.90`.

### Calibration

Probabilities are shown directly to users, so a miscalibrated 70% is worse than
no number. Platt (sigmoid) calibration is applied via `CalibratedClassifierCV`.
The fold count adapts to the rarest class — podiums are a ~15% class, and a
small or early-season dataset can hold fewer positives than folds. If there are
too few examples to calibrate at all, the bare pipeline is used and a warning is
logged: the product degrades in calibration quality rather than failing.

A useful sanity check surfaced on the dashboard: **podium probabilities across
the field sum to ≈3.0** (3.14 on the current model), which is what a calibrated
set of estimates should do when three drivers reach the podium.

#### Reliability on the held-out season

Summing to 3 is necessary but not sufficient. The direct test is a reliability
table: group the 479 held-out 2025 entries by the probability the model gave
them, then compare the average prediction with what actually happened. Each
observed rate carries a 95% Wilson interval, because a bin of 15 drivers proves
very little. Training prints this table, and the Model page shows it.

**Podium** (expected calibration error 3.6%)

| Model said | Drivers | Avg predicted | Actual | 95% range |
|---|---|---|---|---|
| 0–5% | 301 | 1.6% | 0.7% | 0–2% |
| 5–10% | 35 | 7.1% | 5.7% | 2–19% |
| 10–20% | 28 | 14.4% | 7.1% | 2–23% |
| 20–30% | 26 | 24.9% | 15.4% | 6–34% |
| 30–40% | 15 | 35.5% | 53.3% | 30–75% |
| 40–50% | 17 | 45.2% | 41.2% | 22–64% |
| 50–60% | 5 | 55.9% | 80.0% | 38–96% |
| 60–70% | 18 | 64.4% | 77.8% | 55–91% |
| 70–80% | 22 | 75.1% | 86.4% | 67–95% |
| 80–90% | 12 | 82.1% | 83.3% | 55–95% |

**Points** (expected calibration error 3.2%): every bin is within about 7 points of
its prediction, and 5 of the 11 are within 3.

What this shows, stated plainly:

- Every podium bin's prediction falls inside the 95% range of its observed
  rate, so no single bin is demonstrably miscalibrated on one season of data.
- But the misses lean one way. The model is **too generous to midfield
  drivers** (it said ~25% for the 20–30% bin; 15% made it) and **too cautious
  about front-runners** (it said ~75%; 86% made it). That is the signature of a
  model pulled toward the middle, plausibly by the strong regularisation
  (C=0.1) and the grid-rate blend.
- One held-out season is too little to correct this safely. Re-fitting the
  calibration on 2025 would leak the test set. The plan is to re-check the
  pattern as the 2026 season comes in. If it holds, calibrate on a validation
  season the same way the blend weight is chosen.

---

## Features

All 24 features are computable **before the race starts**. This is enforced
structurally, not by convention: every rolling statistic is shifted by one race
within its group, so a race can never contribute to its own prediction.

| Group | Features |
|---|---|
| Grid | `grid`, `grid_prior_podium`, `grid_prior_points` |
| Qualifying | `quali_position`, `quali_gap_to_pole_s`, `reached_q3` |
| Driver form (last 5) | `driver_form_avg_finish`, `driver_form_avg_points`, `driver_form_finish_rate`, `driver_form_podium_rate` |
| Championship | `driver_season_points`, `driver_season_rank`, `constructor_season_points`, `constructor_season_rank` |
| Team form | `constructor_form_avg_points`, `constructor_form_finish_rate`, `constructor_reliability` (last 10) |
| Circuit history | `driver_circuit_starts`, `driver_circuit_avg_finish`, `driver_circuit_podium_rate` |
| Track character | `overtaking_difficulty`, `tyre_degradation`, `circuit_type`, `weather` |

Notes:

- **Retirements count against form.** A DNF has no finishing position, so it is
  treated as a notional P20 in rolling form. Ignoring it would quietly reward
  unreliability.
- **Missing values are preserved as NaN.** A rookie genuinely has no circuit
  history, and imputing a zero would assert something false. Median imputation
  happens inside the model pipeline, fitted on training data only.
- **Weather is a coarse, partly editorial category.** Ergast carries no weather
  field; a curated list of known wet/mixed races supplies it. This is the
  weakest feature in the set and is flagged as such.

### Leakage guarantees, and the test that enforces them

`tests/test_ml.py::test_rolling_features_exclude_the_current_race` is the most
important test in the repository. Using a fixture where a driver finishes P1
then P2, it asserts that the form attached to race 2 is `1.0` (race 1 alone) and
not `1.5` (the mean of both). Companion tests cover circuit history, championship
points and the grid prior.

A model that fails these tests can still score beautifully offline and be
worthless in production.

---

## Evaluation

The split is **chronological**: train on earlier seasons, test on later ones. A
random split would let the model learn from races that happen after the ones it
is tested on.

### Baselines

Every run scores three, and reports the strongest:

| Baseline | What it does |
|---|---|
| `grid_base_rate` | Historical conversion rate for each grid slot, learned on training data only |
| `grid_rule` | A hard rule: top 3 on the grid get the podium, top 10 get points |
| `class_prior` | Always predict the overall base rate |

### Results (train 2021–2024 → test 2025)

**Podium** — actual rate in test set: 15.0%

| Approach | Log loss | Brier | ROC AUC | Accuracy | Precision | Recall |
|---|---|---|---|---|---|---|
| **Model** | **0.1922** | **0.0559** | **0.9503** | **0.9269** | 0.8246 | 0.6528 |
| grid_base_rate | 0.2002 | 0.0582 | 0.9386 | 0.9165 | 0.8333 | 0.5556 |
| grid_rule | 0.2726 | 0.0701 | 0.8529 | 0.9249 | 0.7500 | 0.7500 |
| class_prior | 0.4233 | 0.1277 | 0.5000 | 0.8497 | 0.0000 | 0.0000 |

**Points** — actual rate in test set: 50.1%

| Approach | Log loss | Brier | ROC AUC | Accuracy | Precision | Recall |
|---|---|---|---|---|---|---|
| **Model** | **0.4859** | **0.1579** | **0.8453** | 0.7704 | 0.7851 | 0.7458 |
| grid_base_rate | 0.5023 | 0.1636 | 0.8332 | 0.7787 | 0.7792 | 0.7792 |
| grid_rule | 0.7029 | 0.2017 | 0.7787 | 0.7787 | 0.7792 | 0.7792 |
| class_prior | 0.6931 | 0.2500 | 0.5000 | 0.5010 | 0.5010 | 1.0000 |

The model wins on the probability-quality metrics (log loss, Brier) and on
ranking (ROC AUC), which are the ones that matter for a product that displays
probabilities. It is roughly level on threshold accuracy — unsurprising, since
at a 0.5 cut-off most of the decision is simply "is this driver near the front".

---

## Explanations

The factor breakdown shown next to each probability is produced by
**occlusion**: each feature in turn is replaced with its training median and the
whole model — including the grid component — is re-scored. The change in
probability is that feature's contribution.

This is honest in a specific way: every number displayed comes from actually
re-running the model, not from a narrative layered on afterwards. Its limitation
is equally specific, and is stated in the UI: features are perturbed one at a
time, so interactions between them are not separated out. Contributions will not
sum exactly to the prediction.

---

## Known limitations

1. **Five seasons is a small dataset.** ~2,300 rows, ~1,800 for training.
2. **Regulation changes break comparability.** The 2022 ground-effect rules
   reset the competitive order; the model has no notion of an era boundary.
3. **Circuit samples are tiny.** Some circuits appear 3–4 times. The UI shows
   the sample size next to every circuit statistic for this reason.
4. **No live session data.** No practice pace, tyre allocations, fuel loads,
   upgrades or grid penalties.
5. **Weather is coarse and partly editorial.** Three categories, curated by hand.
6. **No in-race modelling.** Safety cars, red flags and first-lap incidents are
   major sources of variance and are not represented at all.
7. **Predicting an upcoming race projects the grid** from recent qualifying
   form, which adds error the historical evaluation does not capture. The UI
   labels a projected grid whenever one is used.

---

## Retraining

```bash
make ingest   # refresh historical data (cached; safe to re-run)
make train    # retrain, re-evaluate, write artifacts/
```

Training writes `artifacts/podium_model.joblib`, a `.meta.json` sidecar and
`evaluation_report.json`. `--upload-s3` pushes the artifact to the configured
bucket. The API caches the model in memory at start-up, so a deployment restart
picks up a new artifact.
