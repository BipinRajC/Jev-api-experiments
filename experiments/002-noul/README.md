# Experiment 002 — Noul characterization

## Objective

Measure how a single Noul question behaves across three evidence levels, and how stable the returned `noul` is when the same request is repeated.

## Hypothesis

**H002 (refined for this experiment):** For a fixed Noul question, Jev returns a numeric `noul` in `[0, 1]` on every successful call.

**H006 — Noul tracks evidence direction:** Under a fixed question, a clearly positive state yields a higher `noul` than a clearly negative state.

**H007 — Identical Noul repeats are stable:** Repeating the same request three times produces `noul` values whose range is small relative to the gap between clear-yes and clear-no.

Ambiguous-state behavior is recorded, not hypothesized as a specific number.

## Experimental setup

- Provider: TypeSafe direct API
- Model: `jev-1.13.0`
- Question (held constant): `is_sky_blue` / `"Is the sky described as blue?"` / type `noul`
- Variable: `state` only
- Cases:
  - `clear_yes`: `"The sky is blue."`
  - `clear_no`: `"The sky is overcast and grey."`
  - `ambiguous`: `"The weather looks mixed today."`
- Repeats: 3 sequential calls per case (9 calls total)
- Controls: same model, endpoint, question id, instructions, client

## Expected result

- All 9 responses are structured Noul answers
- mean(`clear_yes`) > mean(`clear_no`)
- within-case range is small compared with the yes–no gap

## Falsification criteria

- Reject H002 if any successful HTTP 200 body lacks a numeric `noul`
- Reject H006 if mean(`clear_yes`) ≤ mean(`clear_no`)
- Reject H007 if within-case range is large enough to overlap the yes and no groups

## Results

Artifact: `results/002-noul/run-001.json` (2026-09-21). All 9 calls HTTP 200, model `jev-1.13.0`.

| case | state | noul (3 repeats) | mean | range | input_tokens |
| --- | --- | --- | --- | --- | --- |
| clear_yes | The sky is blue. | 0.99, 0.99, 0.99 | 0.99 | 0.00 | 278 |
| clear_no | The sky is overcast and grey. | 0.01, 0.01, 0.01 | 0.01 | 0.00 | 280 |
| ambiguous | The weather looks mixed today. | 0.05, 0.05, 0.05 | 0.05 | 0.00 | 278 |

Yes–no gap: 0.98. Client latency after the first call was ~306–402 ms; first call 1291 ms.

## Analysis

H002: 9/9 bodies had `type: noul` and a numeric `noul` in `[0, 1]`.

H006: mean(clear_yes)=0.99 > mean(clear_no)=0.01. Ambiguous sat near no (0.05), not near 0.5. That is an observation, not a calibrated “unknown” signal.

H007: within-case range was 0.00 in every cell, much smaller than the 0.98 yes–no gap. n=3 cannot establish long-run stability.

## Conclusion

H002: **SUPPORTED** under these 9 calls.
H006: **SUPPORTED** under these two polar states.
H007: **SUPPORTED** under n=3 identical repeats per case. Do not treat as a general reliability claim.

## Limitations

Toy English sentences. Sequential, not concurrent. Ambiguous case is one wording. No known-true probability. Token counts differ slightly for `clear_no` (280 vs 278) because the state string is longer.

## Next experiment

003 — Choice primitive, still non-football.
