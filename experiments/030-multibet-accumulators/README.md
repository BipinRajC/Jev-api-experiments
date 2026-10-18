# Experiment 030 — Multibet (1X2 accumulator) probability quality

Status: **REGISTERED — retrospective analysis runnable from frozen artifacts;
prospective legs accumulate via 024. Interim retrospective results pending.**

## Objective

The user bets multi-leg 1X2 accumulators. The relevant question is NOT whether
each leg wins often, but whether the **joint probability** implied by
multiplying the per-leg probabilities is calibrated — i.e., does a 3-leg
"80%-per-leg" accumulator actually win ~51% (= 0.8³) of the time?

The user's research (Deliverable B section 7, "Portfolio Theory and Correlated
Football Bets") prescribes the framework: multi-leg joint outcomes need the
return-covariance correction; ignoring correlation over-exposes capital.
Between matches, goal outcomes are plausibly near-independent (the research's
"common-factor risk across fixtures" is the caveat to test).

## Design (no new Jev calls needed)

1. **Retrospective calibration of accumulators:** from the frozen 021
   predictions (and later 024 prospective records), group matches into same-day
   date clusters (the natural multibet card). For every k-leg combination drawn
   from the same day (k = 2, 3), compute the product of the per-leg implied
   probabilities under each arm (ml_alone, score_1x2, noul_1x2, choice_1x2),
   then bucket accumulators by predicted joint probability and compare predicted
   vs realized win rates (calibration curve), plus log loss on the joint event.
2. **Correlation check:** compare the observed joint win rate of same-day legs
   with the independence prediction; a systematic gap indicates common-factor
   risk (e.g., weather/date effects) that the Kelly-covariance correction
   (f* = Σ⁻¹e) would need.
3. **Prospective accumulation:** 024's per-match 1X2 records feed the same
   analysis as they settle; nothing here changes the frozen runner.

## Evaluation

Joint Brier/log loss on accumulators; calibration-by-bucket table; observed vs
independence-implied same-day correlation; all by arm. A multibet is only
"supported" if the per-leg probabilities are calibrated AND the independence
assumption holds in the data.

## Results

Pending (retrospective analysis to run from the frozen 021 artifacts; the
prospective version accumulates with 024).
