# Experiment 024 — Prospective 2026/27 series

Status: **ACTIVE — setup and runner validated; prospective predictions accumulate.**
The first prospective interim report is due after 250 eligible completed matches
(descriptive only); the final report after the 2026/27 season ends. No Results are
claimed yet.

> **Protocol revision 2 (2026-10-19, 026-scoped):** three extension arms
> (`noul_ext`, `score_ext`, `choice_ext`) were added for the four registered
> 026 markets (team goals over 1.5 home/away, handicap home −1.5, first-half
> goals over 1.5; question set `QSET-026-v1`). Core arms and all earlier
> records are untouched; each record carries its own `question_set_version`.
> See `experiments/026-market-extension/README.md`.

## Objective

Predict every eligible 2026/27 fixture **before its recorded 60-minute information
cutoff** with all six core arms (Noul/Score/Choice × 1X2 and the three binary markets),
archive the predictions append-only, settle them later against 90-minute labels, and
compare the primitives and baselines on the first cohort that can support a claim about
real pre-match prediction.

## Hypothesis (to be evaluated only from settled prospective records)

- **H063:** At least one Jev primitive arm achieves better prospective skill than the
  as-of mathematical baselines on at least one core market, measured on paired
  completed fixtures after 250 eligible settled matches. (Interim: descriptive only.)
- **H064:** Predictions recorded before the cutoff do not systematically differ from
  retrospective predictions on the same markets (contamination check across cohorts).

Predeclared falsification criteria and metric definitions follow the phase-4 plan §6
and the 020 frozen protocol; they will be restated in the interim report before the
250-match analysis is run.

## Experimental setup (frozen)

- Question set `QSET-020-v1`, probability derivation `PROB-DERIVE-020-v1`, corner
  line 9.5, model `jev-1.13.0` — identical to the committed 020/021 protocol.
- Runner: `experiments/024-prospective-series/predict_due.py`, invoked by the
  `footyquant-predict.timer` every five minutes (see [ops/systemd/README.md](../../ops/systemd/README.md)).
- Due window: kickoff 62–80 minutes away. The state is the allowlisted as-of JSON
  built at call time from `upcoming_inputs.parquet`; the call must complete by the
  60-minute cutoff and each record stores `pre_cutoff` and minutes-before-kickoff.
- Idempotency: arm-level done keys; failed attempts go to `attempts.jsonl` and are
  retried on later ticks only while the fixture is still pre-cutoff. A window missed
  while the laptop sleeps is recorded as missing, never backfilled.
- Quotes: ESPN quotes captured within 15 minutes before the request and linked to the
  fixture by the conservative quote table are embedded per record. BTTS/corners quotes
  do not exist in the archive; those comparisons stay outcome-only. Displayed ESPN
  prices are not verified executable quotes (`price_semantics` is preserved).
- Settlement: `settle.py` appends label records per (match_id, arm) to
  `settlements.jsonl` from `market_labels.parquet` (90-minute labels; conflicting
  corner labels stay null). Predictions are never modified after the fact.

## Validation performed before activation

- `pytest tests/test_exp024_runner.py` (6 tests): due-window selection, idempotent
  skip of already-predicted fixtures, absence of result/odds fields in states,
  15-minute quote matching (including rejecting post-request captures and other
  fixtures), settlement append + idempotency, and no settlement for unfinished matches.
- `predict_due.py --dry-run` on the live 2026-10-19 data: 1,521 upcoming fixtures
  inspected; 3 already past cutoff correctly excluded; 1,518 correctly not due; 0 due
  at that moment; no API calls.

## Artifacts

- `predictions.jsonl` — one immutable record per (match_id, arm); grows over the season.
- `attempts.jsonl` — failed attempts (never deleted).
- `settlements.jsonl` — appended later per fixture, keyed to predictions.

## Sample size

All eligible 2026/27 fixtures (~1,500 remaining as of activation, growing with the
season). Expected cost ≈ 6 calls × ~2.3k tokens per fixture ≈ $0.0006/fixture — under
$1 for the whole season.

## Metrics computed

Per the phase-4 plan §6: three-class Brier (1X2), binary Brier, fixed-floor log loss,
calibration by bin, coverage/failure rate, tokens, latency, repeat comparison against
the 020 repeat-spread baseline, UCL reported separately from domestic leagues.

## Results

Pending. No prospective fixture had reached its cutoff at activation time
(2026-10-18T20:1xZ); the analysis is pending, and no post-match call will be used to
fill it.

## Limitations

- Requires the laptop to be awake and connected in every 62–80-minute pre-kickoff
  window; missed windows are permanent gaps recorded as missing.
- Same-cutoff market comparison is limited to 1X2/O/U 2.5 ESPN-displayed prices of
  unverified executability; BTTS/corners have no quotes.
- Early-season coverage flags (newly promoted teams, first UCL matchdays) reduce state
  completeness; the state marks omitted fields rather than fabricating them.

## Next experiment

025 (Jev plus ML chronological comparison) consumes these frozen predictions once
enough settled prospective records exist.
