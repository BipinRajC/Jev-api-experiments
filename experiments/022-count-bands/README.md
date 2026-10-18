# Experiment 022 — Native count-band arms vs direct threshold questions

Status: **COMPLETED (exploratory, n=48, retrospective cohort).**

## Objective

Test whether Score and Choice are more effective in their **native structured form** —
full distributions over goal/corner count bands — than as direct binary threshold
questions, by comparing (a) over/under probabilities derived from the band
distributions against direct Noul over/under questions at the same lines, and (b) the
band forecasts as count distributions via the ranked probability score (RPS).

## Hypothesis

- **H065:** Deriving the over/under probability from a full Score/Choice band
  distribution performs within 0.05 binary Brier of the direct Noul threshold question
  at the same line (2.5 goals; 9.5 corners).
- **H066:** Both band arms produce informative count distributions (mean RPS strictly
  better than a uniform distribution over the same bands).

## Experimental setup

- **Paired sample (predeclared):** the exact 48 fixtures and frozen `named_full`
  states of Experiment 020's protocol (`results/020-football-pilot/protocol-v1.json`);
  every state hash re-verified against the 020 freeze before any call.
- **Question set `QSET-022-v1`** (frozen before calls):
  - Goals — 8 bands (0, 1, 2, 3, 4, 5, 6, 7+), locked from 2014/15–2024/25
    development data; over 2.5 = bands g3..g7.
  - Corners — 10 bands (0–5, 6, 7, 8, 9, 10, 11, 12, 13, 14+); over 9.5 = c5..c9.
    Score's 10-level criteria limit is exactly met.
- **Arms (5 requests per fixture, 240 calls):** `noul_thresholds` (both threshold
  propositions batched; wordings identical to 020's), `score_goal_bands`,
  `score_corner_bands`, `choice_goal_bands`, `choice_corner_bands`.
- **Derivation `PROB-DERIVE-022-v1`:** a band answer is valid only with a full
  distribution over ALL bands, finite in [0,1]; normalized by its sum (recorded);
  over-probability = sum of bands above the line; missing levels / zero sums are
  rejected, never repaired. Score's level-indexed probabilities are mapped to bands by
  position (verified by test).
- Model `jev-1.13.0` pinned; same retry policy as 020.

## Variables

- Independent: representation form (direct threshold question vs band distribution ×
  primitive), market (goals, corners).
- Dependent: binary Brier of the over/under probability at each line, RPS of the band
  distribution, calibration of derived probabilities, one-hot incidence.

## Controls

- Identical fixtures, states, question-set discipline, and model across arms (paired).
- Direct Noul wordings byte-identical to 020's canonical propositions.
- Development-data band locking (no pilot data used to choose bands).

## Expected result

If native structure helps, band-derived over/under probabilities should match or beat
direct Noul questions, and RPS should show genuine count signal.

## Falsification criteria

- H065 REJECTED if a band arm's paired Brier is ≥ 0.05 worse than direct Noul with a
  bootstrap 95% CI excluding 0.
- H066 REJECTED if a band arm's mean RPS is not better than uniform
  (uniform RPS over K bands = (K-1)/(3(K-1)) ≈ 0.33 for K>1... computed explicitly per arm).

## Sample size

48 fixtures × 5 arms = 240 calls; measured 566,410 input tokens, **$0.0238** estimated
cost; mean 2,360 input tokens/call.

## Metrics computed

Binary Brier (over event), paired Brier contrasts with bootstrap 95% CIs (10k
resamples, seed 42), RPS of band distributions, mean predicted over-probability vs
outcome frequency, one-hot incidence, tokens/latency/failures.

## Results

**Date:** 2026-10-18/19 UTC. **Model returned:** `jev-1.13.0` on all 240 calls.
**Artifacts:** `results/022-count-bands/protocol-v1.json`, `states-001.json`,
`stream-001.jsonl`, `run-001.json`, `request-bodies-v1.json` (exact request payloads —
the scored trials omit per-trial `request_questions`; the payloads are deterministic
from QSET-022-v1 and identical for every fixture; runners from 023 onward embed them
per trial).

### Over/under Brier at the same line (paired, n=48)

| Market | Noul direct | Score bands (derived) | Choice bands (derived) |
|---|---|---|---|
| Over 2.5 goals | **0.2462** | 0.3255 | 0.2719 |
| Corners over 9.5 | **0.2669** | 0.3912 | 0.2851 |

(2025/26 season base-rate Brier: over 2.5 0.2482, corners 0.2498.)

### Paired contrasts (positive = Noul direct better)

| Contrast | Mean diff | 95% CI | Significant |
|---|---|---|---|
| Noul − Score bands, over 2.5 | +0.079 | [−0.003, +0.166] | no |
| Noul − Choice bands, over 2.5 | +0.026 | [−0.032, +0.086] | no |
| Noul − Score bands, corners 9.5 | **+0.124** | [+0.025, +0.225] | **yes** |
| Noul − Choice bands, corners 9.5 | +0.018 | [−0.046, +0.086] | no |

### Band distributions as count forecasts (RPS, n=48)

| Arm | Goals RPS | Corners RPS |
|---|---|---|
| Choice bands | **0.1447** | **0.1894** |
| Score bands | 0.1498 | 0.2232 |

Both band arms beat a uniform band distribution (uniform RPS 0.3125 for 8 goal bands,
0.3444 for 10 corner bands): H066's signal condition holds.

### Calibration of derived over-probabilities

Score goal bands put mean P(over 2.5) at 0.675 against a 0.396 outcome frequency —
badly miscalibrated (overconfident toward "over"). Choice bands: 0.542 vs 0.396. Noul
direct: 0.398 vs 0.396 — essentially perfectly calibrated on this sample.

## Analysis

Direct Noul threshold questions beat both band-derived derivations at both lines, and
the corners contrast against Score bands is significant (paired diff +0.124, CI
excludes 0). The mechanism is visible in the calibration table: the band
distributions pile probability on high-count bands, so the derived tail sum drifts
high. Choice's band distributions are the best count distributions (RPS), and — unlike
its 1X2 output in 020 — none of the band answers were one-hot (0/48), so the native
structured form does spread probability when options are granular. But as a source of
over/under probabilities, the band form is strictly worse than asking the threshold
directly.

## Conclusion

- **H065: REJECTED for Score bands** (corners contrast significant at ≥0.05 worse);
  over 2.5 contrasts are directionally the same but not significant at n=48.
- **H066: SUPPORTED** — both band arms carry genuine count signal (RPS well below
  uniform), with Choice slightly ahead of Score.

Practical reading: use **direct Noul threshold questions** for over/under probability
tasks; use **Choice/Score band distributions** if a count *distribution* is needed
(e.g., as features for a count model), not as a threshold-probability source.

## Limitations

- n=48, retrospective (contamination not excluded); no winner claim beyond these
  conditions.
- Only one band granularity tested; finer or coarser bands might calibrate better.
- No calibration map fitted (none admissible); the band miscalibration might partly
  shrink under calibration, but the direct-Noul comparison would need the same
  treatment to stay fair.
- Two earlier 240-call batches were lost before their run files were written (a
  post-loop analysis crash in the first, a second key mismatch fixed immediately
  after): ~$0.05 of calls wasted, no results retained from them. The third run added
  append-only streaming + resume and a pre-call label self-check, so its records were
  immune; the second crash's trials were recovered from the stream without new calls.

## Verification commands

```
.venv/bin/python -m pytest tests/test_exp022_bands.py        # 14 passed
.venv/bin/python -m pytest                                    # full suite
.venv/bin/python -m src.data.cli audit                        # 0 errors
```

An independent validation re-parsed all 240 raw responses (0 mismatches), recomputed
every over-probability from its distribution (exact match), recomputed all RPS values
(match), recomputed the paired contrasts (identical means), and checked totals,
duplicate keys, and the returned model ID: all clean.

## Next experiment

023 — state, wording, repeatability and model-version ablations on fixed paired
subsets.
