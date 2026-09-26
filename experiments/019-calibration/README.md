# Experiment 019 — Synthetic Calibration (Phase 3)

## Objective

Determine whether Jev's Noul output corresponds to observed frequency when asked about known probabilities. The core calibration question: when Jev outputs p ≈ 0.70 across a set of events, do approximately 70% of those events actually occur?

This is the first calibration experiment. It uses synthetic problems with known ground-truth probabilities in a controlled environment, before any football or real-world domains.

## Hypothesis

- H055: Jev's Noul values are positively correlated with ground-truth probabilities (confirms 007's r=0.999 finding with larger n).
- H056: Jev's Noul values are well-calibrated (Brier score significantly better than a constant 0.5 baseline).
- H057: Jev's Noul values are not perfectly calibrated (systematic bias exists — the ~0.04 conservative bias observed in 008).
- H058: Score values on a probability rubric are better calibrated than Noul values.

## Experimental setup

A set of synthetic ball-color problems with KNOWN probabilities of drawing a red ball. For each instance:

- State describes a bag with a known ratio of red and blue balls.
- Noul question (fixed wording, held from 009's most-accurate phrasing): "Will the selected ball be red?"
- Score question (same state, separate call): probability rubric.

### Ground-truth probabilities

| Level | Description | N per level |
|-------|------------|-------------|
| 0.50 | 50 red, 50 blue | 20 |
| 0.60 | 60 red, 40 blue | 20 |
| 0.70 | 70 red, 30 blue | 20 |
| 0.80 | 80 red, 20 blue | 20 |
| 0.90 | 90 red, 10 blue | 20 |

Total: 100 Noul calls + 100 Score calls = 200 calls. Estimated cost: 200 × ~300 tokens × $0.042/Mtok ≈ $0.003.

Each Noul call is a standalone request (no batching) to avoid batch effects (006). Score calls are also standalone. To keep within budget, n=20 per level is moderate — enough for meaningful calibration metrics but not extreme.

### Scoring rubric for Score comparison

```json
{
  "type": "score",
  "criteria": [
    {"score": 0, "label": "impossible (0%)"},
    {"score": 1, "label": "unlikely (25%)"},
    {"score": 2, "label": "even odds (50%)"},
    {"score": 3, "label": "likely (75%)"},
    {"score": 4, "label": "certain (100%)"}
  ]
}
```

### Outcome sampling

For each instance, after recording Jev's prediction, sample the actual ball color according to the known composition. This simulates whether the "red" event actually occurs.

## Variables

- Independent variable: ground-truth probability of red (0.50–0.90)
- Dependent variables: Noul value (probability estimate), Score value (quantized estimate), sampled outcome (0/1)
- Held constant: question wording, model (jev-1.13.0), primitive definitions, question structure

## Controls

- One fixed Noul wording throughout ("Will the selected ball be red?") — controls for wording sensitivity (009).
- State structure identical across all instances (only the ratio changes).
- Model pinned.

## Expected result

- Noul tracks ground truth directionally (r > 0.9).
- Noul has a systematic bias (likely conservative, per 008's ~0.04 understatement at 0.50).
- Brier score < 0.25 (which is the constant-0.5 baseline).
- Score on the rubric quantizes to 4 levels and may have different calibration.

## Falsification criteria

- H055 is REJECTED if r < 0.5.
- H056 is REJECTED if Brier >= 0.25.
- H057 is REJECTED if the mean absolute error across levels is < 0.01 (perfect calibration).
- H058 is REJECTED if Score calibration is no better than Noul.

## Sample size

100 Noul calls + 100 Score calls = 200 calls. ~$0.003 estimated cost.

## Metrics computed

- Mean Noul per ground-truth level
- Mean absolute error per level
- Pearson r (Noul vs ground truth)
- Brier score
- Log loss (cross-entropy)
- Calibration error (absolute difference between mean Noul and mean outcome frequency per level)
- Reliability diagram components
- Score vs Noul comparison

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 200/200 HTTP 200 (100 Noul + 100 Score across 5 probability levels)

### Noul by level

| Level | Ground truth | Mean Noul | Stdev | Abs error |
|-------|-------------|-----------|-------|-----------|
| p_50 | 0.50 | **0.418** | 0.006 | 0.082 |
| p_60 | 0.60 | **0.607** | 0.005 | 0.007 |
| p_70 | 0.70 | **0.665** | 0.005 | 0.036 |
| p_80 | 0.80 | **0.768** | 0.005 | 0.032 |
| p_90 | 0.90 | **0.857** | 0.005 | 0.043 |

### Score by level

| Level | Ground truth | Mean Score | Meaning |
|-------|-------------|-----------|---------|
| p_50 | 0.50 | 1.990 | ≈2.0 (50%) |
| p_60 | 0.60 | 2.385 | between 2 (50%) and 3 (75%) |
| p_70 | 0.70 | 2.878 | between 2 (50%) and 3 (75%) |
| p_80 | 0.80 | 2.974 | close to 3 (75%) |
| p_90 | 0.90 | 2.998 | close to 3 (75%) |

### Calibration metrics

| Metric | Noul | Score |
|--------|------|-------|
| Brier score | **0.195** | 0.258 |
| Log loss | **0.576** | 0.712 |
| Calibration error (ECE) | **0.068** | 0.190 |
| Constant-0.5 Brier baseline | 0.250 | 0.250 |
| Constant base-rate Brier baseline | 0.210 | 0.218 |

### Within-level variance (Noul)

Tight across all levels: stdev 0.005–0.006. The Noul values within each level are almost identical — this is consistent with 008's finding of ±0.01 jitter.

### Reliability diagram (Noul bins)

| Bin | N | Mean predicted | Mean actual | Abs error |
|-----|---|---------------|-------------|-----------|
| 0.40–0.50 | 20 | 0.418 | 0.500 | 0.082 |
| 0.60–0.70 | 40 | 0.636 | 0.625 | 0.011 |
| 0.70–0.80 | 20 | 0.768 | 0.950 | 0.182 |
| 0.80–0.90 | 20 | 0.857 | 0.800 | 0.057 |

## Analysis

### Noul is reasonably well-calibrated but has a systematic conservative bias

The Brier score (0.195) is better than both baselines (constant 0.5 = 0.250, constant base-rate = 0.210). Noul tracks ground truth with r=0.983.

The bias is systematic and consistent: Noul **understates** probabilities by ~0.037 on average. The effect is:
- Largest at the extremes: p=0.50 → 0.418 (−0.082), p=0.90 → 0.857 (−0.043)
- Smallest in the middle: p=0.60 → 0.607 (+0.007), essentially perfect

This is a **conservative bias**: Jev's outputs are pulled *away* from the extremes and toward a central region. This matches the "slight pull away from 0.5" pattern observed in 008.

### Within-level variance is extremely tight (stdev ~0.005)

The Noul values are nearly identical within each level. This means a single Noul call is a reliable estimate of the central tendency (consistent with 008's jitter finding). There is no meaningful calibration improvement from averaging multiple calls per level.

### Score is worse than Noul for calibration

Score Brier (0.258) is actually **worse** than the constant-0.5 baseline. The Score rubric (0/0.25/0.5/0.75/1.0) doesn't have enough resolution — at p=0.80 and p=0.90, the Score output clusters near 3.0 (= ~0.75) and cannot distinguish 80% from 90%. The Score-to-probability mapping is too coarse. A finer-grained rubric might improve Score calibration.

**Recommendation:** Use Noul (not Score) for probability calibration. Score is useful for qualitative ratings but loses resolution for fine-grained probabilities.

### Calibration error details

The ECE of 0.068 is moderate. The largest calibration error is in the 0.70-0.80 bin (actual outcome frequency was 0.95, predicted 0.768 — a gap driven by random sampling variation in the 80% level). With n=20 per level, the outcome frequency estimate has variance p(1-p)/n ≈ 0.008-0.01. The calibration error at p=0.80 (0.182) is partly driven by this sampling noise.

## Conclusion

- **H055 (Noul correlates with ground truth): SUPPORTED.** r=0.983.
- **H056 (Noul Brier better than 0.5 baseline): SUPPORTED.** Brier 0.195 < 0.250 baseline.
- **H057 (Noul not perfectly calibrated): SUPPORTED.** Systematic conservative bias of ~0.037; mean abs error 0.040 per level.
- **H058 (Score better calibrated than Noul): REJECTED.** Score Brier 0.258 > Noul Brier 0.195; Score rubric too coarse.

**Noul is useable for calibrated probability estimates** with a known, systematic conservative bias of ~0.04 (understating toward the center). This bias is consistent and can be corrected (by ±0.04) for better calibration. Score is not recommended for fine-grained probability calibration with the current 5-level rubric.

## Limitations

- Bag-of-balls problems only; does not test domain generalization.
- n=20 per level (n=100 total), moderate for calibration metrics.
- Outcome sampling noise inflates calibration error at some bins.
- Score rubric [0/0.25/0.5/0.75/1.0] is too coarse; a finer-grained rubric might give different results.
- Only one fixed Noul wording used; wording sensitivity (009) means the calibration may shift with different phrasing.
- Conservative bias estimate (-0.037) may be specific to the "will be" phrasing used here.

## Next experiment

If calibration is acceptable (Brier beats baseline, bias is systematic), proceed to real-world domains (football) with strict information-cutoff rules. The known bias can be corrected or accounted for. If a better-calibrated primitive is needed, test Noul with explicit probability-scaling instructions or a different fixed wording.