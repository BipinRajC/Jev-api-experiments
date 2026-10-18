# Experiment 020 — Football infrastructure and contamination pilot (Phase 4)

Status: **COMPLETED (exploratory pilot only).** This experiment validates the football
pipeline and question sets. It does **not** establish predictive skill, a winner, or any
market edge.

## Objective

Run the first real-football Jev calls end to end and verify, on a small stratified
sample, that (a) every primitive arm returns parseable, valid probability outputs for
the four core markets, (b) token cost, latency, and failure rates are measured rather
than estimated, (c) repeat-call spread on football states is near the synthetic jitter
baseline, and (d) the names/date-only control shows no suspicious contamination signal.
This freezes the core protocol for the locked retrospective comparison (021).

## Hypothesis

- **H059:** All three primitives return parseable, in-range probability outputs for
  1X2, over/under 2.5, BTTS, and corners-over-9.5 on real as-of states; invalid rate
  < 5% per arm.
- **H060:** Choice's native three-way 1X2 distribution performs within 0.05 three-class
  Brier of Noul and Score on the same fixtures.
- **H061:** Repeat-call spread on football states stays near the ±0.02 synthetic jitter
  baseline (mean absolute repeat difference ≤ 0.04 per event).
- **H062:** A names/date-only control state is clearly worse than the full state (no
  memorized-match contamination signal).

## Experimental setup

- **Cohort:** `retrospective_2025_26` — all calls happened after the matches finished.
  Request times are recorded per call; no call is labelled prospective.
- **Fixtures:** 48 completed 2025/26 fixtures, 8 per competition (EPL, La Liga,
  Bundesliga, Serie A, Ligue 1, UCL), selected with seed 20261020 by abs(Elo-diff)
  terciles within competition (allocation 3/3/2) from **1,920 eligible** of 1,941
  season fixtures. Eligibility: `label_valid_90`, non-null conflict-free
  `corner_total_90`, `kickoff_disagreement` false, `details_pending` false.
  **21 excluded** (19 corner conflicts, 2 kickoff disagreements — overlapping groups
  counted once). Selection is deterministic and covered by tests.
- **Model:** `jev-1.13.0` pinned (continuity with 001–019); verified answering
  (HTTP 200) before the freeze.
- **State:** the allowlisted as-of JSON from `src/features/state.py` (`schema_version` 1),
  built from `model_inputs.parquet` at the stored kickoff−60 min cutoff. No odds, no
  outcomes, no current-match stats, no lineups. Sent as a JSON object.
- **Question set:** `QSET-020-v1` (frozen in `results/020-football-pilot/protocol-v1.json`
  at 2026-10-18T19:49:12Z, before the first scored call). Canonical 90-minute propositions
  from the phase-4 plan §4, e.g. "The home team wins after 90 minutes plus stoppage time,
  excluding extra time and penalties." Noul instructions: "Is the following proposition
  true? {proposition}". Score: nine labelled levels, 0–8 in 12.5-point steps,
  probability = score/8. Choice: one three-way 1X2 question; yes/no binary questions;
  event probability = `probabilities["yes"]`. `confidence` is never used as a probability.
- **Corner line:** 9.5, selected from development data (2014/15–2024/25,
  n=20,863 corner labels; over rate 0.5139 — closest half-line to balanced).
- **Arms (8 per fixture):** `noul_1x2`, `noul_binary`, `score_1x2`, `score_binary`,
  `choice_1x2`, `choice_binary` (1X2 = 3 batched questions; binary = 3 batched
  questions; Choice 1X2 = 1 question), plus controls `ctrl_namesdate_noul_1x2`
  (fixture block only) and `ctrl_anon_noul_1x2` (anonymized full state).
- **Repeats:** all 6 core arms repeated once (repeat_index=2) on a seeded 8-fixture
  subset (48 extra calls).
- **Request order:** per fixture, a seeded shuffle of the 8 arms (`RandomState(seed+2)`).
- **Retries:** up to 2 with 2 s/5 s backoff on timeout/429/5xx/network; auth,
  validation, and malformed-response errors fail fast.

## Variables

- Independent: primitive (Noul/Score/Choice), market (1X2, O/U 2.5, BTTS,
  corners over 9.5), state variant (named full / names-date-only / anonymized),
  repeat index.
- Dependent: raw and derived event probabilities, 1X2 distributions, Brier/log loss
  vs 90-minute labels, tokens, latency, failures.
- Held constant: state schema, question set, model, 90-minute settlement rule,
  corner line, scoring rule.

## Controls

- Names/date-only state and anonymized state for Noul 1X2 (contamination probe).
- Repeat subset for run-to-run spread.
- Season base-rate Brier baselines computed from all 1,941 valid 2025/26 labels.
- No bookmaker prices anywhere in the state or scoring (none are admissible here).
- Protocol freeze file verified against a recomputed selection on every invocation;
  runs are append-only (`next_run_path`).

## Expected result

If the pipeline is sound: ~432 calls with ≈0 HTTP failures, ≈0 parse rejections,
Noul/Score distributions roughly plausible vs base rates, repeat spread ≈ 0.01–0.04,
and total input tokens under ~1.2M (≈$0.05).

## Falsification criteria

- H059 REJECTED if any arm exceeds a 5% invalid/failed rate.
- H060 REJECTED if Choice's paired 1X2 Brier is ≥ 0.05 worse than Noul or Score.
- H061 REJECTED if mean absolute repeat difference exceeds 0.04 on any core event.
- H062 REJECTED (contamination signal) if the names/date-only control is as accurate
  as or more accurate than the full state.

## Sample size

48 fixtures × 8 arms = 384 calls + 48 repeats = **432 attempted calls**
(192 1X2-arm calls, 192 binary-arm calls, 48 control calls). Pre-pilot cost estimate
~$0.02–0.10 at $0.042/Mtok; measured **$0.0414** (986,690 input tokens, mean 2,284/call).

## Metrics computed

Three-class Brier for 1X2, `mean(sum_k (p_k−y_k)^2)`; binary Brier `(p−y)^2` for the
three binary markets; fixed-floor log loss (floor 0.01); mean predicted vs outcome
frequency; repeat absolute differences; input/output tokens, estimated cost, latency,
retry and failure counts; per-competition breakdowns. 1X2 and binary Brier scales are
reported separately and never compared to each other.

## Results

**Date:** 2026-10-18/19 UTC. **Model returned:** `jev-1.13.0` on all 432 calls.
**Artifacts:** `results/020-football-pilot/protocol-v1.json` (frozen before calls),
`preflight-20261019.json`, `run-001.json`, `analysis-run001-v2.json`.

### Reliability and cost

| Metric | Value |
|---|---|
| Attempted / successful calls | 432 / 432 (0 HTTP failures, 0 retries) |
| Parse rejections | 0 (all probabilities finite in [0,1]; all 1X2 sums = 1) |
| Input tokens | 986,690 total; mean 2,284; min 503 (date-only control); max 3,585 |
| Estimated cost (list price) | $0.0414 |
| Latency | mean 289 ms, median 281 ms, max 629 ms |

### Primitive comparison (repeat-1 only, n = 48)

1X2 three-class Brier (2025/26 season base-rate baseline: **0.6460**):

| Arm | Brier | Fixed-floor log loss |
|---|---|---|
| score_1x2 | **0.5788** | 0.9734 |
| noul_1x2 | 0.5913 | 0.9934 |
| ctrl_anon_noul_1x2 | 0.5919 | 0.9940 |
| ctrl_namesdate_noul_1x2 | 0.6086 | 1.0131 |
| choice_1x2 | **0.7883** | 1.7714 |

Binary Brier (season base rates: O/U 2.5 **0.2482**, BTTS **0.2483**, corners 0.2498):

| Arm | O/U 2.5 | BTTS | Corners > 9.5 |
|---|---|---|---|
| noul_binary | **0.2478** | **0.2421** | 0.2625 |
| score_binary | 0.2726 | 0.2642 | **0.2449** |
| choice_binary | 0.2598 | 0.2830 | 0.2686 |

### Predeclared paired contrasts (bootstrap 95% CI, 10k resamples, n=48)

| Contrast | Mean diff (positive = first arm worse) | 95% CI |
|---|---|---|
| Noul − Score, 1X2 | +0.0125 | [−0.0057, +0.0329] |
| Noul − Choice, 1X2 | **−0.1970** | [−0.3311, −0.0646] |
| Noul − Score, O/U 2.5 | −0.0248 | [−0.0799, +0.0305] |
| Noul − Choice, O/U 2.5 | −0.0119 | [−0.0450, +0.0205] |
| Noul − Score, BTTS | −0.0221 | [−0.0479, +0.0044] |
| Noul − Choice, BTTS | **−0.0409** | [−0.0804, −0.0012] |
| Noul − Score, corners | +0.0177 | [−0.0381, +0.0732] |
| Noul − Choice, corners | −0.0061 | [−0.0393, +0.0253] |

### Choice overconfidence

16/48 Choice 1X2 distributions placed ≥ 0.99 on one class; 0/48 for Noul and 0/48 for
Score. This replicates the one-hot Choice behavior of H019 on real football states and
explains Choice's 1X2 log loss (1.77).

### Repeat spread (8 fixtures × 6 core arms, 24 paired event sets)

Mean absolute repeat difference per event: over 2.5 0.0139, BTTS 0.0156, corners 0.0166,
1X2 components 0.0056–0.0083 (max single-event 0.07; max 1X2 L1 distance 0.0731).

### Controls (Noul 1X2, paired, n=48)

Named full 0.5913; names/date-only 0.6086; anonymized 0.5919. The date-only control is
*worse* than the full state (no contamination signal); the gaps are within n=48 noise.

### Per-competition Noul 1X2 Brier (n=8 each)

Serie A 0.487, Bundesliga 0.578, EPL 0.584, UCL 0.591, Ligue 1 0.645, La Liga 0.664.
UCL (n=8) is reported separately in later experiments, where n permits.

## Analysis

The pipeline works end to end with zero failures and zero rejections, and the measured
cost ($0.0414) is inside the pre-pilot estimate. Score's nine-level rubric produced the
best 1X2 Brier, nominally better than Noul, but the paired Noul−Score CI includes zero —
no winner claim is possible at n=48. Both Noul and Score beat the season base-rate 1X2
Brier (0.646) directionally. Binary-market results hover at the base-rate baselines
with mixed ordering across markets — no binary skill signal is detectable at this n.
Choice's native three-way distribution is markedly overconfident (H060 REJECTED): it
collapses toward one-hot, consistent with H019, and should not be used as the primary
1X2 probability source. Repeat spread (mean 0.006–0.017) is somewhat above the toy
±0.02 single-call jitter but far below any plausible market effect.

The names/date-only control being *less* accurate than the full state is the expected
direction under no-contamination; at n=48 this probe has low power (H062 INCONCLUSIVE).
The contamination question stays open until the prospective cohort, where no result
exists to know.

Note on artifacts: `run-001.json`'s embedded summary undercounted `repeat_pairs` (an
analysis-loop ordering bug that built the repeat-1 index after the repeat-2 diff loop).
The trials were never touched; the corrected analysis is
`analysis-run001-v2.json`, all README numbers come from it or from an independent
recompute, and a regression test now covers the ordering.

## Conclusion

- **H059: SUPPORTED** — 0 failures, 0 rejections across 432 calls.
- **H060: REJECTED** — Choice's native 1X2 distribution is ≥ 0.05 Brier worse than
  Noul and Score (paired diff −0.197 vs Noul, CI excludes 0).
- **H061: SUPPORTED** — mean repeat differences 0.006–0.017 per event (max 0.07).
- **H062: INCONCLUSIVE** — no contamination signal, but n=48 has low power.

Protocol frozen (`020-protocol-v1`, question set `QSET-020-v1`, derivation
`PROB-DERIVE-020-v1`). All results are **exploratory**.

## Limitations

- n=48 fixtures (8 per competition): every ranking is noise-limited; CIs are wide.
- Retrospective cohort: Jev may have prior knowledge of these results; the
  contamination probe could not rule memorization in or out.
- Raw scores only — no calibration map was fitted because no earlier out-of-sample
  football Jev predictions exist (calibration stays pending per the phase-4 plan).
- No same-cutoff market comparison: no verified pre-cutoff executable quotes exist.
- Binary and 1X2 Brier scales are not comparable; base rates differ by market.
- The corner line (9.5) and all thresholds were locked from development data; corner
  labels for 19 season fixtures remain conflicting and were excluded.
- Choice's near-one-hot 1X2 outputs make its three-way distribution unusable as a
  calibrated forecast; a per-class one-vs-rest Choice arm remains untested here.

## Verification commands

```
.venv/bin/python -m pytest tests/test_exp020_pilot.py        # 20 passed
.venv/bin/python -m pytest                                    # full suite
.venv/bin/python -m src.data.cli audit                        # 0 errors
.venv/bin/python experiments/020-football-pilot/experiment.py --freeze-only
```

An independent validation pass re-parsed all 432 raw responses (0 mismatches),
re-derived all labels from 90-minute goals/corners, re-scored every arm, and checked
totals reconciliation, key uniqueness, probability ranges, distribution sums, cutoff
ordering, and the returned model ID: all clean.

## Next experiment

021 — locked retrospective primitive comparison on all eligible 2025/26 and
already-completed 2026/27 fixtures (raw scores only; calibration pending). In
parallel, set up 024's prospective cutoff-time runner and append-only prediction
archive now that the protocol is validated.

## Cost/budget note for 021+

Measured pilot usage: 2,284 input tokens/call mean. The 021 batch (~1,941 + ~358
fixtures × 6 calls) projects to ~32M input tokens ≈ **$1.34** at $0.042/Mtok, plus
022/023 subsets. No balance endpoint is documented; the account's $5 promo credit is
reported to expire 19 October 2026 — confirm account credit with the user before
starting the full 021 batch.
