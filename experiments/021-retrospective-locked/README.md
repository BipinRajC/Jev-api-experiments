# Experiment 021 — Locked retrospective primitive comparison

Status: **COMPLETED (locked retrospective cohort; exploratory interpretation —
Jev may know these results).**

## Objective

Run all six core arms (Noul/Score/Choice × 1X2 and the three binary markets) on
every eligible 2025/26 and already-played 2026/27 fixture with the frozen 020
question set, and compare them against each other and against frozen
mathematical and ML baselines on paired fixtures. Raw scores are primary;
a legitimate out-of-fold calibration (fit 2025/26 → evaluate 2026/27) is a
secondary result. No market edge or winner claim is made from this cohort.

## Hypothesis

- **H070:** Score and Noul differ on 1X2 three-class Brier (direction unspecified
  a priori); Choice is not worse than Noul.
- **H071:** At least one Jev arm beats the Elo baseline on 1X2.
- **H072:** Post-hoc calibration (fitted on 2025/26 only) does not materially
  change 2026/27 Brier for Noul/Score binary arms.

## Experimental setup

- **Cohorts:** `retrospective_2025_26` (1,920 fixtures) and
  `retrospective_2026_27_played` (366 fixtures), all called post-match with
  recorded times. 2,286 fixtures total; 450 season fixtures excluded (corner
  conflicts, kickoff disagreements, details pending, invalid labels).
- **Protocol:** `021-protocol-v1` frozen 2026-10-18T20:05:08Z before any call —
  fixture list with label snapshot and per-fixture state SHA-256, all 2,286
  states stored in `states-001.json` (hash-verified at call time), question set
  `QSET-020-v1` (hash of 020's `questions.py` recorded), derivation
  `PROB-DERIVE-020-v1` (020's parser reused verbatim), model `jev-1.13.0`
  pinned, arm order rotated per fixture (seeded).
- **Execution:** append-only stream (`stream-001.jsonl`), resumable; final
  summary in `run-003.json` (run-001 = main batch; run-002 = a no-op resume
  before the resume-supersession fix; run-003 = after completing choice_1x2).
- **Baselines (fitted on 2014/15–2024/25 only, `BASELINE-021-v1`):** prior-season
  frequencies; multinomial-logit Elo-difference mapping; Dixon–Coles joint-goals
  model (215 teams, home advantage 1.372, ρ −0.045, time-decay weighted); NB
  corner model (dispersion 1.18); tabular ML (gradient boosting, 112 as-of
  features, size chosen on the 2024/25 split; features selected from the raw
  label-free inputs table only, with an explicit label-leakage guard).

## Variables

- Independent: primitive arm, market, baseline model.
- Dependent: three-class Brier (1X2), binary Brier, Brier skill vs the prior
  baseline, calibration effect, tokens/latency.

## Controls

- Identical fixtures and states across all arms (paired); per-call state hash
  checks against the frozen protocol; date-clustered bootstrap CIs for all
  contrasts; competition and season breakdowns; UCL reported separately.

## Expected result

Jev arms roughly in the 0.58–0.62 1X2 Brier range, better than the season base
rate (0.645), in the neighborhood of the Elo baseline; Choice uncertain.

## Falsification criteria

- H070 REJECTED if Choice is significantly worse than Noul, or if Score/Noul
  order contradicts the direction (either way, the test decides).
- H071 REJECTED if every Jev arm's paired CI vs Elo excludes zero on the wrong
  side.
- H072 REJECTED if calibration shifts any binary arm's 2026/27 Brier by more
  than 0.01.

## Sample size

2,286 fixtures × 6 arms = 13,716 valid calls (+2,286 superseded attempts).
Measured: 34,765,950 input tokens, **$1.4602** estimated cost, 0 transport
failures, mean latency ~0.3 s/call.

## Results

**Dates:** 2026-10-19 UTC. **Artifacts:** `results/021-retrospective-locked/`
(`protocol-v1.json`, `states-001.json`, `stream-001.jsonl`, `run-003.json`,
`baseline-predictions-v1.parquet`, `ml-predictions-v1.parquet`,
`analysis-v1.json`, `calibration-v1.json`).

### 1X2 three-class Brier (n = 2,286 paired; baselines n = 2,288/2,099)

| Arm | Brier | Skill vs prior | By season 2025/26 → 2026/27 |
|---|---|---|---|
| **Score 1X2** | **0.59191** | +0.0534 | 0.59541 → 0.57354 |
| Elo baseline | 0.58997 | +0.0553 | 0.59326 → 0.57268 |
| Dixon–Coles | 0.59116 | +0.0540 | 0.59435 → 0.57357 |
| ML baseline | 0.59530 | +0.0553 (vs own prior n) | 0.59989 → 0.57122 |
| **Noul 1X2** | 0.59820 | +0.0471 | 0.60217 → 0.57741 |
| Choice 1X2 | 0.79382 | −0.1485 | 0.80478 → 0.73633 |
| Prior (base rate) | 0.64530 | — | — |

UCL (n=225, reported separately): Score 0.5434, Elo 0.5433, Noul 0.5514, ML 0.5801.

### Binary Brier (n = 2,286 paired)

| Market | Noul | Score | Choice | Prior | DC | ML |
|---|---|---|---|---|---|---|
| Over 2.5 | 0.26415 | **0.24204** | 0.24795 | 0.24778 | 0.24797 | 0.24172 |
| BTTS | 0.25957 | 0.24949 | 0.26219 | 0.24795 | 0.25250 | **0.24631** |
| Corners > 9.5 | 0.25497 | 0.26558 | 0.26923 | 0.25014 | — | 0.25011 |

### Key paired contrasts (date-clustered 95% CIs, n=2,286)

| Contrast | Mean diff (positive = first arm worse) | Significant |
|---|---|---|
| Noul − Score, 1X2 | +0.0063 [0.0036, 0.0091] | **yes** (Score better) |
| Noul − Choice, 1X2 | −0.1956 [−0.2147, −0.1766] | **yes** (Choice far worse) |
| Noul − Elo, 1X2 | +0.0086 [0.0032, 0.0138] | **yes** (Elo better than Noul) |
| Score − Elo, 1X2 | +0.0023 [−0.0011, +0.0056] | no (tie) |
| Score − ML, 1X2 | −0.0031 [−0.0102, +0.0039] | no (tie) |
| Noul − Score, over 2.5 | +0.0221 [0.0142, 0.0300] | **yes** (Score better) |
| Noul − Score, corners | −0.0106 [−0.0182, −0.0032] | **yes** (Noul better) |
| Noul − Choice, BTTS | −0.0026 [−0.0083, +0.0029] | no |

### Calibration (fit 2025/26 → evaluate 2026/27, n=366; `CALIB-021-v1`)

| Arm / market | Raw 26/27 | Calibrated 26/27 | Change |
|---|---|---|---|
| noul_binary / over 2.5 | 0.26911 | **0.23442** (logistic) | −0.035 |
| noul_binary / BTTS | 0.25724 | **0.24161** | −0.016 |
| noul_binary / corners | 0.25033 | **0.24716** | −0.003 |
| choice_1x2 | 0.73633 | **0.58615** | −0.150 |
| score_1x2 | 0.57354 | 0.57370 | +0.000 (already calibrated) |
| score_binary / over 2.5 | 0.22999 | 0.23273 | +0.003 |

The mechanism behind Noul's binary miscalibration: mean P(over 2.5) = 0.404 vs a
0.554 outcome frequency (gap −0.149) — a much larger conservative bias on
football than the −0.037 measured on synthetic data in 019. Score's binary gaps
are smaller (+0.035 over, +0.127 corners, −0.021 BTTS).

## Analysis

**Within Jev:** Score is the best 1X2 primitive (significantly better than Noul
by a small 0.006 margin), and its 1X2 output is natively calibrated (calibration
moves it by ~0.000). Choice's native 1X2 distribution is again catastrophically
overconfident (consistent with 020/022) but collapses to Elo-level quality
(0.586) after calibration — the *ordering* information is there; the *numbers*
are not. For binary markets, Score wins over 2.5 raw, Noul wins corners raw,
and the arms flip in places under calibration.

**Versus baselines:** no Jev arm significantly beats the Elo baseline on 1X2
(Score ties it; Noul is significantly worse). Score's raw over-2.5 Brier is the
single best number in the study but statistically ties the ML baseline. On BTTS
and corners the ML/prior baselines lead. In short, **this retrospective cohort
shows no measurable Jev skill beyond a simple Elo rating** — consistent with
023's finding that Jev's football signal rides on team identity (pretraining
knowledge), which an Elo model already summarizes.

**Caveat that matters:** these matches are in Jev's past. The contamination
probe (020/023) found no strong contamination signal, but a large-retrospective
tie with Elo is exactly what "knowledge without calibration" would look like.
The prospective 024 series is the only decisive test.

## Conclusion

- **H070: PARTIALLY SUPPORTED** — Score significantly beats Noul (small margin);
  Choice is far worse than Noul (rejected for Choice).
- **H071: REJECTED** — no Jev arm significantly beats Elo on 1X2.
- **H072: REJECTED for Noul** — calibration moves Noul's binary Brier by up to
  −0.035 (over 2.5), far beyond 0.01; SUPPORTED for Score (moves ≤ 0.003).

Protocol maintained throughout: no calibration fitted on scored fixtures (the
2025/26→2026/27 split is strictly chronological), no post-hoc cohort moves.

## Limitations

- Retrospective cohort: Jev may know these results; no edge claim is possible.
- choice_1x2 incident: the first pass sent the wrong question payload (score
  rubric instead of the three-way Choice) due to a runner routing bug — 2,286
  superseded attempts remain in the stream; the arm was re-run with the correct
  questions and a regression test locks the routing (`tests/test_exp021_arms.py`).
  run-002.json is a no-op resume artifact from the same incident (the resume
  key counted rejected records as done; fixed and tested).
- No verified pre-cutoff market prices → no odds comparison (outcome-only).
- UCL breakdown has n=225; subgroup results are exploratory.
- The calibration evaluation (n=366, one chronological split) is itself
  exploratory and will be re-estimated on the prospective cohort.
- Binary Brier scales are not comparable with the 1X2 scale or with each other
  across markets.

## Verification commands

```
.venv/bin/python -m pytest                                     # 173 passed
.venv/bin/python -m src.data.cli audit                          # 0 errors
.venv/bin/python experiments/021-retrospective-locked/analysis.py
.venv/bin/python experiments/021-retrospective-locked/calibrate.py
```

Independent validation: all 16,002 stream records re-parsed with 020's parser
(0 mismatches), totals reconcile (attempted = 13,716 valid + 2,286 superseded),
no duplicate valid keys, every state hash verified against the frozen protocol,
all calls post-cutoff, returned model always `jev-1.13.0`, baseline and ML
predictions joined one-to-one by match_id.

## Next experiment

025 — Jev plus ML: combine the frozen Score/Noul outputs with the ML baseline's
features under a chronological split, separately by market and primitive; the
prospective conclusion waits for 024's settled records.
