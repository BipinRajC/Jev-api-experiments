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

Not yet run. After execution, see `results/001-api-sanity/run-*.json`.

## Analysis

Pending raw artifact.

## Conclusion

UNTESTED

## Limitations

A single successful call does not establish stability, calibration, latency distribution, or correctness of Noul as probability.

## Next experiment

002 — dedicated Noul characterization (repeated identical binary questions), still non-football.
