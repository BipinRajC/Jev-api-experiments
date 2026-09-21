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
