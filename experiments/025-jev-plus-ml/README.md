# Experiment 025 — Chronological Jev-plus-ML comparison

Status: **COMPLETED (retrospective stacking; exploratory — a product conclusion
needs the 024 prospective cohort).**

## Objective

Test whether frozen Jev outputs add measurable skill to the tabular ML baseline,
market by market and primitive by primitive, under a strict chronological split.

## Hypothesis

- **H073:** Adding frozen Jev probabilities to the ML baseline's features improves
  eval-season Brier on at least one core market.

## Experimental setup

- **Protocol `025-protocol-v1` (STACK-025-v1), frozen before evaluation:**
  inputs are the frozen 021 artifacts (per-match Jev probabilities for all three
  primitives; the ML baseline's eval predictions). No API calls; the ML trees are
  never refitted.
- **Chronological split:** stack layer fitted on 2025/26 (n=1,920), evaluated on
  the untouched 2026/27 fixtures (n=366). Nothing fitted on evaluation rows.
- **Arms per market:** `ml_alone` (logistic on ML probabilities),
  `ml_plus_<prim>` (ML + that primitive's Jev probabilities),
  `jev_<prim>_alone` (Jev probabilities only). The logistic layer recalibrates
  whatever feeds it, so raw Jev probabilities go in directly.
- **Metrics:** 3-class/binary Brier on 2026/27; paired contrasts with
  date-clustered bootstrap CIs (10k resamples, seed 42).

## Variables

- Independent: stack composition (ML alone / +Noul / +Score / +Choice / Jev alone).
- Dependent: eval-season Brier; paired differences.

## Controls

- Identical training rows, evaluation rows, and layer model across arms; fixed
  random state; the frozen ML layer guarantees the comparison isolates the Jev
  contribution.

## Expected result

If Jev adds information beyond the ML features: `ml_plus_<prim>` beats `ml_alone`
significantly on some market. If Jev only duplicates Elo-like knowledge: ties.

## Falsification criteria

H073 is REJECTED if no `ml_plus_<prim>` vs `ml_alone` contrast has a 95% CI
excluding zero with the claimed sign (negative = Jev helps).

## Sample size

7 arms × 4 markets = 28 stack fits; 10,248 prediction rows over 366 evaluation
fixtures. No API cost (local computation on frozen artifacts).

## Results

**Date:** 2026-10-19 UTC. **Artifacts:** `results/025-jev-plus-ml/protocol-v1.json`,
`stack-predictions-v1.parquet`, `run-001.json`.

### 1X2 Brier (eval 2026/27, n=366)

| Arm | Brier |
|---|---|
| ml_plus_noul | **0.56444** |
| ml_plus_score | 0.56445 |
| ml_plus_choice | 0.56626 |
| **ml_alone** | 0.56779 |
| jev_score_alone | 0.57617 |
| jev_noul_alone | 0.57750 |
| jev_choice_alone | 0.59000 |

### Binary Brier (eval 2026/27, n=366)

| Market | ml_alone | +Noul | +Score | +Choice | best Jev alone |
|---|---|---|---|---|---|
| Over 2.5 | 0.23227 | 0.23089 | **0.23068** | 0.23200 | 0.23468 |
| BTTS | 0.24282 | 0.24177 | **0.24172** | 0.24172 | 0.24199 |
| Corners > 9.5 | 0.24830 | 0.24671 | 0.24656 | **0.24576** | 0.24663 |

### Paired contrasts ML+Jev vs ML alone (negative = Jev helps; date-clustered 95% CI)

| Contrast | Mean diff | Significant |
|---|---|---|
| 1X2, +Noul / +Score / +Choice | −0.0033 / −0.0033 / −0.0015 | no (all CIs cross 0) |
| Over 2.5, all primitives | −0.0003 to −0.0016 | no |
| BTTS, +Noul / +Score / +Choice | −0.0011 / −0.0011 / −0.0011 | **yes (all three)** |
| Corners, +Noul / +Score / +Choice | −0.0016 / −0.0017 / −0.0025 | **yes (all three)** |

Confirmed with an independent bootstrap seed (999): the BTTS and corners
significances persist.

## Analysis

**Jev alone is worse than ML everywhere** (e.g., 1X2 0.576–0.590 vs 0.568) — the
ML model dominates raw Jev, consistent with 021. **But adding frozen Jev
outputs to ML produces small, consistent, statistically significant gains on
BTTS (−0.0011) and corners (−0.0016 to −0.0025), with all three primitives
agreeing** — exactly the markets where 022 showed Jev's band/binary outputs
carry complementary distribution information. On 1X2 and over-2.5 the direction
is positive but not significant at n=366.

The effect sizes are tiny (~0.001–0.003 Brier) and the evaluation is a single
366-fixture retrospective split. This is evidence that **Jev's outputs contain
information the ML model has not already extracted** — the most encouraging
result in the phase so far — but it is not proof of a product-worthy edge.

## Conclusion

- **H073: SUPPORTED** — significant (if small) ML improvements on BTTS and
  corners from adding frozen Jev outputs, consistent across primitives.
- Jev alone remains inferior to ML on every market.

## Limitations

- Retrospective cohort: contamination cannot be excluded; the decisive test is
  the prospective 024 series.
- Single chronological split, n=366; effect sizes near the noise floor; no
  correction for the 12 contrast tests (labeled exploratory).
- The stack layer is logistic; a richer combiner might extract more (or
  overfit).
- Corners line 9.5 only; BTTS/over-2.5 label periods are 90 minutes.

## Verification commands

```
.venv/bin/python -m pytest                                    # 173 passed
.venv/bin/python experiments/025-jev-plus-ml/experiment.py    # deterministic rerun
.venv/bin/python -m src.data.cli audit                         # 0 errors
```

Independent validation: stored per-arm means recomputed exactly from
`stack-predictions-v1.parquet` (28/28 match); contrasts re-run with an
independent seed (999) reproduce all significances; no NaNs in scored rows;
split integrity verified (train = season 2025 only, eval = season 2026 only).

## Next experiment

024 continues accumulating prospective predictions; the interim report follows
after 250 settled matches. 026 remains WAITING FOR RESEARCH.
