# Experiment 004 — Score characterization

## Objective

Verify that Jev's Score primitive returns a numeric score, level legend, probability map, and confidence, and see how the score moves across polar vs unstated evidence.

## Hypothesis

**H004:** Jev's Score primitive can consistently represent a numerical judgment on a defined scale.

**H010 — Score tracks ordered evidence:** Under a three-level sky-blueness rubric (0 grey, 1 unstated, 2 blue), mean(clear_blue) > mean(ambiguous) > mean(clear_grey).

**H011 — Score probabilities sum to 1:** Each successful Score answer's `probabilities` values sum to approximately 1.

## Experimental setup

- Provider: TypeSafe direct API
- Model: `jev-1.13.0`
- Question: Score `sky_blueness` / `"How clearly is the sky described as blue?"`
- Criteria (ordered):
  0. grey/overcast, not blue
  1. sky color not stated
  2. described as blue
- Variable: `state` only (same three strings as 002/003)
- Repeats: 3 sequential calls per case (9 calls)

## Expected result

- All 9 answers have `type: score`, numeric `score`, `legend`, `probabilities`, `confidence`
- Polar blue near 2, polar grey near 0, unstated nearer 1 than the poles
- Probability maps sum to ~1

## Falsification criteria

- Reject H004 if HTTP 200 Score answers lack a numeric `score` or legend
- Reject H010 if the three case means are not ordered blue > unstated > grey
- Reject H011 if sums deviate substantially from 1

## Results

Artifact: `results/004-score/run-001.json` (2026-09-21). All 9 calls HTTP 200, model `jev-1.13.0`.

| case | score ×3 | mean | range | confidence | mass |
| --- | --- | --- | --- | --- | --- |
| clear_blue | 2.0, 2.0, 2.0 | 2.0 | 0 | 1.0 | level 2 = 1.0 |
| clear_grey | 0.0, 0.0, 0.0 | 0.0 | 0 | 1.0 | level 0 = 1.0 |
| ambiguous | 1.0, 1.0, 1.0 | 1.0 | 0 | 1.0 | level 1 = 1.0 |

Legend matched the request criteria. Probability sums 1.0 on 9/9.

## Analysis

H004: every answer had numeric `score`, `legend`, `probabilities`, `confidence`.

H010: means ordered 2.0 > 1.0 > 0.0.

H011: sums exactly 1.0 on these one-hot maps.

Scores sat on integer levels; this run did not produce between-level values (docs allow that). Confidence was constantly 1.0, so it is not characterized here.

## Conclusion

H004: **SUPPORTED** under these 9 calls.
H010: **SUPPORTED** under this rubric and these states.
H011: **SUPPORTED** under these 9 one-hot answers.

## Limitations

n=3. Toy English. One-hot integer scores only. Middle level is “unstated”, not a continuous blueness degree.

## Next experiment

005 — error handling (invalid key, malformed request), still non-football.
