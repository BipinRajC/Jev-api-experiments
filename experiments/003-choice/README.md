# Experiment 003 — Choice characterization

## Objective

Verify that Jev's Choice primitive returns a label, a full probability distribution, and a confidence value, and see how those fields move with polar vs unstated evidence.

## Hypothesis

**H003:** Jev's Choice primitive can produce a probability distribution across multiple mutually exclusive options.

**H008 — Choice tracks intended option on polar states:** For this three-way sky-color Choice, `clear_blue` selects `blue` and `clear_grey` selects `grey`.

**H009 — Choice probabilities sum to 1:** Each successful Choice answer's `probabilities` values sum to approximately 1.

Ambiguous-state label is recorded, not required to be `unspecified`.

## Experimental setup

- Provider: TypeSafe direct API
- Model: `jev-1.13.0`
- Question (held constant): Choice `sky_color` / `"What color is the sky described as?"`
- Criteria: `blue`, `grey`, `unspecified`
- Variable: `state` only
- Cases: same three strings as Experiment 002
- Repeats: 3 sequential calls per case (9 calls)

## Expected result

- All 9 answers have `type: choice`, `choice`, `probabilities`, `confidence`
- Polar cases map to the matching option
- Probability maps cover all three keys and sum to ~1

## Falsification criteria

- Reject H003 if HTTP 200 Choice answers lack a probability map
- Reject H008 if polar cases do not select the matching option on a majority of repeats
- Reject H009 if sums deviate substantially from 1 (beyond ordinary float noise)

## Results

Artifact: `results/003-choice/run-001.json` (2026-09-21). All 9 calls HTTP 200, model `jev-1.13.0`.

| case | choice ×3 | confidence | mean probabilities |
| --- | --- | --- | --- |
| clear_blue | blue, blue, blue | 1.0 | blue 1.0, others 0.0 |
| clear_grey | grey, grey, grey | 1.0 | grey 1.0, others 0.0 |
| ambiguous | unspecified, unspecified, unspecified | 1.0 | unspecified 1.0, others 0.0 |

Probability sums were 1.0 on 9/9. Probability key order in JSON varied; keys were complete.

## Analysis

H003: every answer included `choice`, a three-key `probabilities` map, and `confidence`.

H008: polar states selected the matching option 3/3 each.

H009: sums were exactly 1.0 on these 9 one-hot maps.

Contrast with 002: the same ambiguous state scored Noul 0.05 (near no) but Choice `unspecified` at confidence 1.0. Choice used the extra option; Noul had no “unmentioned” outcome.

These items were trivial. Confidence 1.0 here does not imply Choice is always certain.

## Conclusion

H003: **SUPPORTED** under these 9 calls.
H008: **SUPPORTED** under these polar states.
H009: **SUPPORTED** under these 9 one-hot answers.

## Limitations

n=3 per cell. Toy English. One-hot maps do not test partial distributions. Confidence was constantly 1.0, so this experiment cannot characterize confidence as a second axis.

## Next experiment

004 — Score primitive, still non-football.
