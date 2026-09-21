# Experiment 006 — Batch vs separate questions

## Objective

Measure whether one System One request with three questions (Noul, Choice, Score) returns all answers, and how tokens/latency compare with three separate single-question requests on the same state.

## Hypothesis

**H015 — Mixed primitives batch:** One request containing Noul, Choice, and Score returns a structured answer for each question id.

**H016 — Batched answers match separate answers:** For this trivial state, batched Noul/Choice/Score values equal the corresponding separate-call values.

**H017 — Batch uses fewer input tokens than the sum of separate calls:** `usage.input_tokens` for the batch is less than the sum of the three separate calls.

Latency is recorded, not hypothesized (first-call warmup already observed).

## Experimental setup

- Provider: TypeSafe direct API
- Model: `jev-1.13.0`
- State (held constant): `"The sky is blue."`
- Questions: same wording as 002/003/004 (`is_sky_blue`, `sky_color`, `sky_blueness`)
- Condition A: one request with all three questions
- Condition B: three sequential requests, one question each
- Order: batch first, then Noul, Choice, Score
- n=1 per condition (cost control)

## Expected result

- Batch HTTP 200 with three answers
- Answer values match separate calls
- Batch input tokens < sum of separate input tokens

## Falsification criteria

- Reject H015 if the batch is missing any of the three answers
- Reject H016 if a batched value differs from the matching separate call
- Reject H017 if batch input tokens ≥ sum of separate input tokens

## Results

Artifact: `results/006-batch/run-001.json` (2026-09-21). All 4 calls HTTP 200, model `jev-1.13.0`.

| call | input_tokens | output_tokens | latency_ms | parsed |
| --- | --- | --- | --- | --- |
| batch (3 questions) | 426 | 77 | 894 | noul 0.99; choice blue 1.0; score 2.0 |
| separate_noul | 278 | 23 | 312 | noul **1.0** |
| separate_choice | 348 | 41 | 315 | choice blue 1.0 |
| separate_score | 328 | 20 | 329 | score 2.0 |

Separate input sum: 954 (2.24× batch). Separate latency sum: 956 ms vs batch 894 ms.

## Analysis

H015: batch returned all three answer ids with the documented shapes.

H016: Choice and Score matched. Noul did not: 0.99 (batch) vs 1.0 (separate). Strict equality is false. This may be ordinary Noul jitter (002 had 0.99×3 on the same item; this separate call is the first 1.0) rather than a batching effect. Cause is not identified.

H017: 426 < 954. Output tokens 77 vs 84 (not hypothesized). Wall-clock of one batch ≈ sum of three already-warm separate RTTs; batch still uses one round trip.

## Conclusion

H015: **SUPPORTED**
H016: **REJECTED** under strict equality (Noul 0.99 vs 1.0). Choice/Score matched.
H017: **SUPPORTED** for input tokens on this 3-vs-3 comparison.

## Limitations

n=1 per condition. Toy state. Cannot separate batching from Noul jitter. Latency comparison is confounded by call order/warmup.

## Next experiment

Phase 1 complete. Next logical item is Phase 2 / 007 (non-trivial items or known distributions), not football.
