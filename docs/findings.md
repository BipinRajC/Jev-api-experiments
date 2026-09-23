# Findings

Only findings measured in this repository.

---

## F001 — Direct TypeSafe System One endpoint accepted this account's key

- **Related hypothesis:** H001
- **Experiment(s):** 001 (`results/001-api-sanity/run-001.json`, `run-002.json`)
- **Conditions:** 2026-09-21 UTC; `POST https://api.typesafe.ai/v1/systemone`; Bearer `TYPESAFE_API_KEY`; `model=jev-1.13.0`; state `"The sky is blue."`; one Noul question `is_sky_blue`
- **Evidence:** HTTP 200 on 2/2 calls. Bodies were JSON objects with `model`, `answers`, `usage`. Request IDs in `x-typesafe-request-id`: `req_01a0c4d9222678d8a5fc2c073a380d9b`, `req_01a0c4e33c7376648c03b94b45f88b2d`.
- **Interpretation:** Under these conditions the documented evaluation endpoint is reachable and authenticates this key.
- **Limitations:** n=2. Does not test invalid keys, other endpoints, or other models.
- **Confidence in the finding:** High for this account/endpoint/date; not generalizable beyond that.
- **Implications:** Proceed to primitive-specific experiments. Do not treat connectivity as evidence of decision quality.

---

## F002 — Noul answer shape matched official HTTP docs on a trivial item

- **Related hypothesis:** H002
- **Experiment(s):** 001
- **Conditions:** same as F001
- **Evidence:** Both runs returned `answers.is_sky_blue = {"type": "noul", "noul": 0.99}`. No `confidence` field on the Noul answer. No free-form text field.
- **Interpretation:** For this tautological binary question, Jev returned a structured yes-probability rather than prose. The value 0.99 is consistent with a strong yes; it is not a calibration measurement.
- **Limitations:** One question, one state, two repeats. Does not show that `noul` is a calibrated probability or that Noul works for ambiguous items.
- **Confidence in the finding:** High for schema presence on this item; low for any probabilistic interpretation.
- **Implications:** Experiment 002 should repeat Noul on identical and varied items and record value stability.

---

## F003 — Response model echoed the pinned versioned ID

- **Related hypothesis:** H005
- **Experiment(s):** 001
- **Conditions:** request `model` was `jev-1.13.0` (not `jev-latest`)
- **Evidence:** Both responses had `"model": "jev-1.13.0"`.
- **Interpretation:** Pinning `jev-1.13.0` produced a matching `model` field in the body.
- **Limitations:** Does not test whether `jev-latest` resolves to `jev-1.13.0` in the response.
- **Confidence in the finding:** High for echo of an already-versioned ID.
- **Implications:** If alias behavior matters, add a dedicated run that sends `jev-latest`.

---

## F004 — Token usage and latency were reported for this request

- **Related hypothesis:** none numbered
- **Experiment(s):** 001
- **Conditions:** same as F001
- **Evidence:** Both runs `usage.input_tokens=278`, `output_tokens=23`. Wall-clock latency 1088.1 ms (run-001) and 882.2 ms (run-002). Response header `x-envoy-upstream-service-time: 124` (ms) on both. Estimated input cost at documented $0.042/Mtok: ~$1.17e-5 per call. Output tokens present in `usage` even though docs say output is free.
- **Interpretation:** Token accounting fields exist and were stable across these two identical requests. Client-measured RTT is ~0.9–1.1 s and is much larger than the envoy upstream time of 124 ms. Cost estimate uses documented list price, not a bill.
- **Limitations:** n=2. Pricing vs billed credit is UNVERIFIED. Latency includes local client overhead and network, not only model time.
- **Confidence in the finding:** High for the two recorded numbers; low as a latency or cost characterization.
- **Implications:** Later experiments should keep recording `usage`, wall-clock, and `x-envoy-upstream-service-time` separately.

---

## F005 — Noul values separated polar evidence and were identical across 3 repeats

- **Related hypothesis:** H002, H006, H007
- **Experiment(s):** 002 (`results/002-noul/run-001.json`)
- **Conditions:** 2026-09-21 UTC; `jev-1.13.0`; question held constant (`is_sky_blue` / `"Is the sky described as blue?"`); only `state` varied; 3 sequential repeats per case
- **Evidence:** 9/9 HTTP 200. `clear_yes` noul 0.99×3; `clear_no` 0.01×3; `ambiguous` 0.05×3. Within-case range 0.00. Yes–no gap 0.98. All answers `{type: noul, noul: <float>}` with no `confidence` field.
- **Interpretation:** Under these toy states, Noul moved with evidence direction and did not jitter across three immediate repeats. The ambiguous wording produced 0.05 (near no), not ~0.5, so a mid-range value should not be assumed to mean “unknown”.
- **Limitations:** n=3 per cell. English one-liners. Immediate sequential repeats may share server-side caching; this was not tested. Not a calibration study.
- **Confidence in the finding:** High for these 9 calls; low as a general stability or uncertainty-representation claim.
- **Implications:** Treat Noul as a structured yes-weight on clear items. Do not interpret values near 0 as uniquely “no” versus “unmentioned” without a dedicated missing-information experiment. Next: Choice (003).

---

## F006 — Choice returned one-hot distributions that matched polar and unstated states

- **Related hypothesis:** H003, H008, H009
- **Experiment(s):** 003 (`results/003-choice/run-001.json`)
- **Conditions:** 2026-09-21 UTC; `jev-1.13.0`; Choice `sky_color` with options `blue`/`grey`/`unspecified`; same three states as 002; 3 sequential repeats each
- **Evidence:** 9/9 HTTP 200. Labels: blue×3, grey×3, unspecified×3. Each map one-hot (winning option 1.0, others 0.0), sum 1.0, confidence 1.0. JSON key order of `probabilities` varied.
- **Interpretation:** Under these trivial items, Choice returned the documented schema and selected the intended option, including `unspecified` when color was unmentioned. That differs from Noul 002, where the same unmentioned state scored 0.05 rather than a dedicated unknown outcome. Confidence was constantly 1.0, so this run does not characterize confidence.
- **Limitations:** n=3. Toy sentences. No partial (non-one-hot) distributions observed. Key order is not semantically meaningful.
- **Confidence in the finding:** High for schema and polar labeling on these 9 calls; low for confidence behavior or non-trivial classification.
- **Implications:** Prefer Choice when “unmentioned” is a real option. Next: Score (004).

---

## F007 — Score landed on integer levels matching the rubric

- **Related hypothesis:** H004, H010, H011
- **Experiment(s):** 004 (`results/004-score/run-001.json`)
- **Conditions:** 2026-09-21 UTC; `jev-1.13.0`; Score `sky_blueness` with three ordered criteria (grey / unstated / blue); same three states as 002/003; 3 sequential repeats each
- **Evidence:** 9/9 HTTP 200. Scores: clear_blue 2.0×3, ambiguous 1.0×3, clear_grey 0.0×3. Confidence 1.0. Probability mass 1.0 on the matching level. Legend echoed the request criteria. Sums 1.0.
- **Interpretation:** Under these trivial items, Score returned the documented schema and ordered the three states as intended. Between-level (non-integer) scores were not observed. Confidence was constantly 1.0.
- **Limitations:** n=3. Toy sentences. Does not show Score interpolates. Does not characterize confidence.
- **Confidence in the finding:** High for schema and ordering on these 9 calls; low for Score as a continuous scale.
- **Implications:** Score is usable as an ordered-level output on clear items. Next: error handling (005).

---

## F008 — Documented 401/422 statuses are incomplete: missing auth is 403, unknown model is 400

- **Related hypothesis:** H012, H013, H014
- **Experiment(s):** 005 (`results/005-error-handling/run-001.json`)
- **Conditions:** 2026-09-21 UTC; `POST /v1/systemone`; one call per case; placeholder invalid token (not the real key); real key used only for missing-questions and unknown-model cases; secrets not stored
- **Evidence:**
  - invalid bearer → HTTP 401, `detail.error_type=authentication_error`
  - missing Authorization → HTTP **403**, same error_type, message “Must supply an API key!”
  - missing `questions` → HTTP 422, `detail` list with `type=missing`, `loc=['body','questions']`
  - unknown model `jev-does-not-exist-0.0.0` → HTTP **400**, `detail.error_type=api_usage_error`
- **Interpretation:** Official status table (401, 422, 429, 529) understates the live surface. Missing credentials and invalid credentials are not the same status. Unknown model is a 400 usage error, not 422. Error bodies use a `detail` wrapper.
- **Limitations:** n=1 per case. 429/529 untested. Behavior may change.
- **Confidence in the finding:** High for these four calls on this date; treat as snapshot, not a contract.
- **Implications:** Client should handle 400 and 403, not only the documented four codes. Next: batch questions (006).

---

## F009 — One request can return mixed Noul/Choice/Score; input tokens were 2.24× lower than three separate calls

- **Related hypothesis:** H015, H016, H017
- **Experiment(s):** 006 (`results/006-batch/run-001.json`)
- **Conditions:** 2026-09-21 UTC; `jev-1.13.0`; state `"The sky is blue."`; questions copied from 002/003/004; batch first, then three separate calls; n=1
- **Evidence:** Batch HTTP 200 with answers for `is_sky_blue` (noul 0.99), `sky_color` (blue, conf 1.0), `sky_blueness` (score 2.0). Separate: noul **1.0**, choice blue, score 2.0. Input tokens 426 vs 278+348+328=954. Output 77 vs 84. Client latency 894 ms vs 312+315+329=956 ms.
- **Interpretation:** Mixed primitives work in one request. Input-token savings vs three calls were real on this item (state is not billed three times). Strict answer equality failed on Noul (0.99 vs 1.0); that is a 0.01 difference also consistent with jitter (002 recorded 0.99, this separate call recorded 1.0). Do not claim batching changes decisions.
- **Limitations:** n=1. Toy state. Latency confounded by order/warmup. No test of many questions (cookbook-scale fan-out).
- **Confidence in the finding:** High for batch schema and token inequality on this run; low for answer-identity and latency.
- **Implications:** Prefer batching independent questions for cost. Do not assume identical Noul floats across batched vs separate. Phase 1 complete.

---

## F010 — Noul tracks explicit probabilities with high correlation but shows a slight conservative bias

- **Related hypothesis:** H018
- **Experiment(s):** 007 (`results/007-mixed-evidence/run-001.json`)
- **Conditions:** 2026-09-23 UTC; `jev-1.13.0`; 7 coin-flip states with stated probabilities (0%, 10%, 30%, 50%, 70%, 90%, 100%); n=1 each; batch calls with Noul+Choice+Score
- **Evidence:** Noul values: {0.01, 0.08, 0.23, 0.45, 0.65, 0.84, 0.98}. Pearson r=0.999 vs ground truth. Mean abs error=0.05 (n=5 non-tautological). Fair coin (50%) produced 0.45, clearly distinguishable from Phase 1's ambiguous-unmentioned result (0.05). Conservative bias: values pulled slightly away from 0.5 toward extremes.
- **Interpretation:** Jev can express graded Noul uncertainty when the state explicitly quantifies probabilities. Phase 1's extreme-polarization finding was an artifact of trivially clear toy states, not an inherent Noul limitation. The ~0.05 conservative bias (slight pull away from 0.5) is consistent and may reflect a calibration characteristic.
- **Limitations:** n=1 per probability level. Batch calls may confound Noul values vs separate calls (see F009). Does not test whether Jev can infer probabilities — the state explicitly stated them.
- **Confidence in the finding:** High for Noul's ability to track explicit probabilities; lower for the magnitude of the conservative bias (needs repeats).
- **Implications:** Noul is usable for quantitative uncertainty when the state provides explicit probability information. The slight conservative bias should be characterized in Experiment 008 (repeatability).

---

## F011 — Choice remains one-hot even on explicitly probabilistic alternatives

- **Related hypothesis:** H019
- **Experiment(s):** 007 (`results/007-mixed-evidence/run-001.json`)
- **Conditions:** 2026-09-23 UTC; `jev-1.13.0`; urn with known composition 50% red / 30% blue / 20% green; question "What color will the randomly drawn ball be?"; n=1
- **Evidence:** Choice selected "red" with probabilities {red: 1.0, blue: 0.0, green: 0.0}, confidence 0.99. Despite the state explicitly providing a non-trivial distribution, Jev treated Choice as "pick the most likely" and returned a one-hot distribution.
- **Interpretation:** Jev's Choice primitive appears to answer "which option is most likely?" rather than "what is the probability distribution?" This is consistent with all Phase 1 Choice results (all one-hot). The confidence of 0.99 is notable — not 1.0 despite being clearly the correct modal answer, possibly reflecting the genuine uncertainty.
- **Limitations:** n=1. Single wording of the question. Does not test whether different phrasing ("What is the probability distribution...") would produce partial distributions.
- **Confidence in the finding:** Moderate — the one-hot pattern is consistent across Phase 1 and Phase 2, but n is still small and only one question wording was tested.
- **Implications:** Do not use Choice when a probability distribution is required. Noul or Score may be better suited for distributions. Experiment 009 (wording sensitivity) should test whether phrasing affects Choice distribution behavior.

---

## F012 — Score IS continuous: non-integer values observed for genuinely graded evidence

- **Related hypothesis:** H020
- **Experiment(s):** 007 (`results/007-mixed-evidence/run-001.json`)
- **Conditions:** 2026-09-23 UTC; `jev-1.13.0`; 5-point evidence-strength rubric (0–5); 5 cases with graded evidence descriptions (vague hint through overwhelming consensus); n=1 each
- **Evidence:** All 5 scores were non-integer: 1.06 (vague hint), 1.01 (weak study), 2.92 (moderate), 4.68 (strong), 4.96 (overwhelming). Phase 1's integer-only scores (0.0, 1.0, 2.0) were an artifact of trivially-clear toy states where the answer was obvious. Score interpolates between rubric levels.
- **Interpretation:** Score is a continuous-scale primitive that can return fractional values between rubric levels. It is not limited to snapping to integer levels. The two-decimal-place precision suggests the model produces a computed value, not merely a category selection.
- **Limitations:** n=1 per case. Subjective mapping between text descriptions and rubric levels. Different wording might shift scores (Experiment 009). The specific numeric values should not be treated as precisely calibrated without further testing.
- **Confidence in the finding:** High that Score interpolates; lower on the specific numeric precision (needs repeatability testing).
- **Implications:** Score is the most promising primitive for graded quantitative judgments. Future calibration experiments should use Score for continuous-valued predictions. Experiment 008 should test repeatability of fractional Score values.

---

## F013 — Jev confidence varies with evidence strength but stays in a narrow range

- **Related hypothesis:** H022
- **Experiment(s):** 007 (`results/007-mixed-evidence/run-001.json`)
- **Conditions:** 2026-09-23 UTC; `jev-1.13.0`; 20 confidence observations across 13 trial calls (Choice and Score primitives)
- **Evidence:** 16/20 confidence values < 1.0; 4/20 = 1.0 (all on tautological 100%/0% coin cases). Non-1.0 range: 0.79 (strong evidence, Score) to 0.99 (several cases). Phase 1's uniform 1.0 confidence was an artifact of trivial toy states. Confidence now varies but in a narrow band — even the weakest evidence case (single small study, p=0.08) got confidence 0.88.
- **Interpretation:** Jev does produce variable confidence, overturning the Phase 1 assumption that confidence is always 1.0. However, the narrow range (0.79–0.99) suggests reluctance to express low confidence. No observation below 0.79, even for explicitly weak evidence.
- **Limitations:** n=1 per case. Only tested moderate-to-strong evidence strengths; no truly ambiguous or contradictory states were used (that's Experiment 012/013). Does not test whether confidence correlates with accuracy.
- **Confidence in the finding:** High that confidence varies; moderate on the range (broader evidence types might produce lower confidence).
- **Implications:** Confidence is more informative than Phase 1 suggested but may be poorly calibrated at the low end. Experiment 012 (conflicting evidence) and 013 (missing information) should attempt to elicit lower confidence values. Do not interpret confidence as a calibrated probability without calibration experiments (Phase 3).
