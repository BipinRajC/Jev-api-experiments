# API notes

Every item is tagged:

- **VERIFIED FROM OFFICIAL DOCS** — stated at https://docs.typesafe.ai as of 2026-09-21
- **VERIFIED EXPERIMENTALLY** — observed in this repository
- **UNVERIFIED** — not yet confirmed here
- **INFERRED** — reasonable reading of docs, not a direct quote

Conflicts: official TypeSafe docs take precedence over blogs, OpenRouter, and community examples.

---

## Endpoint

- Evaluation: `POST https://api.typesafe.ai/v1/systemone` — VERIFIED FROM OFFICIAL DOCS ([API reference](https://docs.typesafe.ai/api))
- Models list: `GET https://api.typesafe.ai/v1/models` — VERIFIED FROM OFFICIAL DOCS ([Models](https://docs.typesafe.ai/models))
- Experimental confirmation of evaluation endpoint: VERIFIED EXPERIMENTALLY (001, 2/2 HTTP 200, 2026-09-21)

## Authentication

- Header: `Authorization: Bearer <API_KEY>` — VERIFIED FROM OFFICIAL DOCS
- Env var used by official Python SDK: `TYPESAFE_API_KEY` — VERIFIED FROM OFFICIAL DOCS ([SDK constants](https://docs.typesafe.ai/sdk/python/api/constants.md))
- Optional `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL` — VERIFIED FROM OFFICIAL DOCS (SDK); this repo uses `TYPESAFE_MODEL` for experiment pinning
- Missing/invalid key → HTTP 401 — VERIFIED FROM OFFICIAL DOCS; UNVERIFIED experimentally (001 used a valid key only)

## Headers

- `Content-Type: application/json` required — VERIFIED FROM OFFICIAL DOCS
- Other required headers: UNVERIFIED (none documented besides Authorization + Content-Type)
- Request-id response header: `x-typesafe-request-id` — VERIFIED EXPERIMENTALLY (001). Values like `req_01a0c4d9222678d8a5fc2c073a380d9b`. Also present: `server: istio-envoy`, `x-envoy-upstream-service-time` (124 on both 001 runs). `x-request-id` was not observed.

## Model identifier

- Current versioned ID: `jev-1.13.0` — VERIFIED FROM OFFICIAL DOCS
- Alias `jev-latest` currently points to `jev-1.13.0` — VERIFIED FROM OFFICIAL DOCS
- Alias `jev-preview` currently also points to `jev-1.13.0` — VERIFIED FROM OFFICIAL DOCS
- Experiments in this repo pin `jev-1.13.0` by default (not the moving alias) — INFERRED from reproducibility requirement
- Response `model` field reports the versioned ID that answered — VERIFIED FROM OFFICIAL DOCS; VERIFIED EXPERIMENTALLY for request `jev-1.13.0` → response `jev-1.13.0` (001). Alias `jev-latest` resolution: UNVERIFIED experimentally.
- `GET /v1/models` currently lists aliases; versioned IDs are still accepted — VERIFIED FROM OFFICIAL DOCS

## Request format

Top-level fields (all required per API reference):

- `state`: string | object | array
- `model`: string
- `questions`: map of named Question objects

Question types:

- `noul`: `type`, `instructions`; optional `criteria.{true,false}`
- `choice`: `type`, `instructions`, `criteria` map (max 255 options)
- `score`: `type`, `instructions`, `criteria` array (at least 2 levels, max 10)

`instructions` may be string, object, or array.

Source: VERIFIED FROM OFFICIAL DOCS.

SDK Python client may reshape answers into `.nouls` / `.choices`; the HTTP body uses a single `answers` map. Prefer the HTTP schema in this repo. INFERRED from comparing [API reference](https://docs.typesafe.ai/api) vs SDK snippets.

## Response format

- `model`: string
- `answers`: map keyed by question id
- `usage.input_tokens`, `usage.output_tokens`

Noul answer: `{ "type": "noul", "noul": <number 0–1> }` — no separate `confidence` field in official HTTP docs. VERIFIED EXPERIMENTALLY on 001 and 002 (values 0.99, 0.01, 0.05; no `confidence` key). Identical sequential repeats in 002 had range 0.00 (n=3 per case). An unmentioned-sky state returned 0.05, not ~0.5.

Choice answer: `choice`, `probabilities`, `confidence`. VERIFIED EXPERIMENTALLY on 003: 9/9 answers had all three fields; maps were one-hot with sum 1.0; `confidence` was 1.0; probability key order was not stable.

Score answer: `score`, `legend`, `probabilities`, `confidence`. VERIFIED EXPERIMENTALLY on 004: 9/9 answers had all four fields; scores were integers 2.0 / 1.0 / 0.0; maps one-hot with sum 1.0; `confidence` 1.0; `legend` echoed request criteria. Between-level scores UNVERIFIED.

Source: VERIFIED FROM OFFICIAL DOCS.

## Supported decision types

Noul, Choice, Score. VERIFIED FROM OFFICIAL DOCS.

## State representation

Text string, JSON object, or array of text values. No image/audio/video. VERIFIED FROM OFFICIAL DOCS.

## Question representation

Named map; keys are not sent to the underlying model. VERIFIED FROM OFFICIAL DOCS.

## Batching

Multiple questions in one request, evaluated in parallel against one `state`. VERIFIED FROM OFFICIAL DOCS. VERIFIED EXPERIMENTALLY (006): one request returned Noul+Choice+Score together. Input tokens 426 vs 954 for three separate calls (n=1, 3 questions, same state). Output 77 vs 84. Noul 0.99 vs 1.0 across batch vs separate; Choice/Score matched. Large fan-out (cookbook 13-question claims): UNVERIFIED here.

## Errors

| Status | Meaning | Source |
| --- | --- | --- |
| 401 | invalid API key (Bearer present but rejected) | VERIFIED FROM OFFICIAL DOCS; VERIFIED EXPERIMENTALLY (005) |
| 403 | missing Authorization header | VERIFIED EXPERIMENTALLY (005); official table said 401 for missing key |
| 400 | unknown model | VERIFIED EXPERIMENTALLY (005); not in official status table |
| 422 | validation failure (e.g. missing `questions`) | VERIFIED FROM OFFICIAL DOCS; VERIFIED EXPERIMENTALLY (005) |
| 429 | rate limit | VERIFIED FROM OFFICIAL DOCS; UNVERIFIED experimentally |
| 529 | overloaded | VERIFIED FROM OFFICIAL DOCS; UNVERIFIED experimentally |

Error JSON: `{"detail": ...}` — object with `error_type`/`message` for auth and unknown model; list of FastAPI validation errors for 422. VERIFIED EXPERIMENTALLY (005). Official docs did not specify this schema.

## Rate limits (Jev 1.13)

Documented: 250,000 tokens/sec and 1,200 requests/min. Limits can change without notice. VERIFIED FROM OFFICIAL DOCS. Account-specific actual limits: UNVERIFIED.

## Context limits (Jev 1.13)

- 64k tokens per request (state + all questions)
- 32k tokens for `state` plus the longest question

VERIFIED FROM OFFICIAL DOCS.

## Token accounting

`usage.input_tokens` and `usage.output_tokens` in the response. VERIFIED FROM OFFICIAL DOCS. VERIFIED EXPERIMENTALLY on 001: both runs `278` / `23`. Whether they match billed usage: UNVERIFIED.

## Pricing (Jev 1.13)

- $42 / Btok or $0.042 / Mtok input
- Output tokens free
- Charged per input token

VERIFIED FROM OFFICIAL DOCS. This account's remaining credit and billed amounts: UNVERIFIED in-repo (user reports $5 promo credit expiring 19 October).

## Latency

No official SLA found. VERIFIED EXPERIMENTALLY (001, n=2): client wall-clock 1088.1 ms and 882.2 ms; `x-envoy-upstream-service-time` 124 on both. Not a latency distribution.

## Versioning

Pin versioned IDs for reproducible experiments. Aliases move when releases ship. VERIFIED FROM OFFICIAL DOCS.

## OpenRouter vs direct API

Direct TypeSafe HTTP protocol is documented above. OpenRouter behavior for Jev: UNVERIFIED in this repo (planned later). Do not assume they are equivalent.

## Third-party sources (not treated as protocol truth)

- https://typesafe.ai/blog/introducing-system-one-models-and-jev — product announcement
- https://flaviocopes.com/jev/ — unofficial deep dive; may be stale
- https://github.com/rajivkuriakose/typesafe-jev-examples — community examples; may be stale
- OpenRouter listings — intermediary; protocol may differ

When these conflict with https://docs.typesafe.ai, use the official docs.
