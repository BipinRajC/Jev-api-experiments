# Experiment 005 — Error handling

## Objective

Record the live HTTP status codes and JSON error bodies for invalid authentication and invalid request shapes, and compare them to the official docs (401, 422, 429, 529).

## Hypothesis

**H012 — Invalid bearer token returns 401:** A request with `Authorization: Bearer` plus a non-real token returns HTTP 401.

**H013 — Missing Authorization returns 401:** A request with no `Authorization` header returns HTTP 401.

**H014 — Missing `questions` returns 422:** An otherwise documented body that omits `questions` returns HTTP 422.

Unknown-model status is recorded, not hypothesized (docs do not specify it).

## Experimental setup

- Endpoint: `POST /v1/systemone`
- Cases (one call each):
  1. invalid bearer token (placeholder string, not the real key)
  2. no Authorization header
  3. valid key, body missing `questions`
  4. valid key, `model` = `jev-does-not-exist-0.0.0`
- Controls: same endpoint; real key never written to results
- Not tested: 429, 529 (would require inducing overload)

## Expected result

Cases 1–2: 401. Case 3: 422. Case 4: documented if observed.

## Falsification criteria

- Reject H012/H013 if those calls return 2xx or a status other than 401
- Reject H014 if missing `questions` is accepted (2xx) or returns a non-422 error

## Results

Artifact: `results/005-error-handling/run-001.json` (2026-09-21). One call per case.

| case | expected | observed | body (summary) |
| --- | --- | --- | --- |
| invalid_bearer_token | 401 | **401** | `authentication_error` / check API key |
| missing_authorization_header | 401 | **403** | `authentication_error` / must supply an API key |
| missing_questions | 422 | **422** | FastAPI-style `Field required` at `body.questions` |
| unknown_model | unspecified | **400** | `api_usage_error` / Unknown model: `jev-does-not-exist-0.0.0` |

Official docs listed 401, 422, 429, 529. They did not list 403 or 400.

## Analysis

H012: invalid bearer token returned 401 as documented.

H013: missing Authorization returned **403**, not 401. Same `error_type` (`authentication_error`) but a different status. Hypothesis rejected under this condition.

H014: omitting `questions` returned 422 with a validation `detail` list.

Unknown model returned 400, which is undocumented in the status table we recorded.

Error JSON used a `detail` wrapper (object or list), not a top-level `error` string.

## Conclusion

H012: **SUPPORTED**
H013: **REJECTED** (observed 403)
H014: **SUPPORTED**

## Limitations

n=1 per case. 429/529 untested. Placeholder token only.

## Next experiment

006 — batch / multiple decisions in one request.
