# Experiment 001 — API sanity

## Objective

Verify that this environment can authenticate to the direct TypeSafe API, send the smallest documented System One request, and parse a structured JSON response. This is a connectivity and schema check, not a study of decision quality.

## Hypothesis

**H001:** The TypeSafe HTTP API accepts authenticated requests using a Bearer `TYPESAFE_API_KEY` and returns a structured System One JSON body from `POST /v1/systemone`.

Related: **H002** (Noul field present), **H005** (response `model` is a versioned ID).

## Experimental setup

- Provider: TypeSafe direct API (`https://api.typesafe.ai`)
- Endpoint: `POST /v1/systemone`
- Auth: `Authorization: Bearer $TYPESAFE_API_KEY`
- Model requested: `jev-1.13.0` (pinned; not `jev-latest`)
- Decision type: single `noul`
- State: `"The sky is blue."`
- Question id: `is_sky_blue`
- Instructions: `"Is the sky described as blue?"`
- Runs: 1 (sanity). Repeatability is out of scope.
- Variables: none besides the live network
- Controls: request body matches the official HTTP example shape; no football content; no extra questions

## Expected result

HTTP 200, JSON body with `model`, `answers.is_sky_blue.type == "noul"`, numeric `noul`, and `usage` token fields.

## Falsification criteria

Reject H001 if, with a valid key and the documented request shape:

- the endpoint does not exist / returns 404
- authentication with a present key cannot produce a 2xx
- the body is not structured JSON with an `answers` map

A 401 caused by a missing local key is a local config failure, not a rejection of H001.

## Results

Artifacts: `results/001-api-sanity/run-001.json`, `run-002.json` (2026-09-21).

| run | HTTP | model returned | noul | input_tokens | output_tokens | latency_ms (client) | x-envoy-upstream-service-time | request_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-001 | 200 | jev-1.13.0 | 0.99 | 278 | 23 | 1088.1 | 124 | req_01a0c4d9222678d8a5fc2c073a380d9b |
| run-002 | 200 | jev-1.13.0 | 0.99 | 278 | 23 | 882.2 | 124 | req_01a0c4e33c7376648c03b94b45f88b2d |

Raw `answers.is_sky_blue` both times: `{"type": "noul", "noul": 0.99}`.

## Analysis

2/2 calls with the documented request shape returned HTTP 200 and the documented Noul JSON. Token counts were identical. The Noul value was identical. Client RTT varied (~0.88–1.09 s) while envoy upstream time did not (124 ms). Estimated list-price input cost is ~$1.17e-5 per call using documented $0.042/Mtok; this is not a billed figure.

This does not show calibration, robustness, or that 0.99 is a frequentist probability.

## Conclusion

H001: **SUPPORTED** under the conditions above.

H002: **SUPPORTED** as a schema/shape claim for this trivial item only.

H005: **SUPPORTED** for echoing a already-pinned `jev-1.13.0` ID. Alias resolution untested.

## Limitations

n=2. One tautological question. Valid key only. No Choice/Score. No error-path measurement. No OpenRouter comparison.

## Next experiment

002 — dedicated Noul characterization (repeated identical binary questions), still non-football.
