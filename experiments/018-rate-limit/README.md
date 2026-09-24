# Experiment 018 — Rate-Limit Behavior (Add-on B)

## Objective

Observe whether Jev returns HTTP 429 rate-limit errors under a moderate, controlled burst of requests, and document any rate-limit response headers. The documented limits are 250k tokens/s and 1,200 requests/min.

**Safety constraint (per handoff):** This must NOT intentionally hammer the API. I will send a short burst of rapid requests that stays within documented limits (well under 1,200 rpm and 250k tokens/s). The goal is to observe natural rate-limit behavior, not to trigger an artificial outage.

## Hypothesis

- H053: A moderate burst of requests (well within documented limits) completes without HTTP 429.
- H054: If a 429 occurs, the response includes a meaningful error body and/or retry-after information.

H054 is conditional; it is only assessed if a 429 is observed.

## Experimental setup

A short burst of Noul requests on a simple state, sent back-to-back with no delay (the highest request rate this account has used in one experiment), to probe for rate limiting.

- State: "A bag contains 70 red balls and 30 blue balls. One ball is selected randomly."
- Question: "Will the selected ball be red?"
- 10 requests sent back-to-back (no sleep between calls).

This is well under the 1,200 rpm documented limit and the token limit, so it should NOT trigger a 429 under normal operation. If it does, that reveals the effective limit is lower than documented.

## Variables

- Independent variable: rapid-fire request sequence
- Dependent variables: HTTP status per request, latency, any rate-limit headers
- Held constant: state, question, model (jev-1.13.0)

## Controls

- Same request for all 10 calls.
- Model pinned.
- Back-to-back with no delay (deliberately fast, but within limits).

## Expected result

- All 10 requests return HTTP 200 (no 429), since we stay within documented limits.
- If a 429 occurs, capture its body and headers.

## Falsification criteria

- H053 is SUPPORTED if all requests return 200.
- H053 is REJECTED if any request returns 429.
- H054 is only evaluated if a 429 is observed.

## Sample size

10 rapid requests. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 10/10 HTTP 200 (back-to-back, no delay)
**Documented limits:** 1,200 rpm / 250k tokens/s

| Metric | Value |
|--------|-------|
| 200 responses | 10/10 |
| 429 responses | 0 |
| Retry-after headers | none observed |
| Mean latency | 344 ms |

## Analysis

All 10 rapid back-to-back requests returned HTTP 200 with no 429 and no rate-limit headers. This is consistent with the documented limits: 10 requests in ~3 seconds is ~200 rpm, far below the 1,200 rpm ceiling, and ~10 × 300 tokens = ~3k tokens over 3s = ~1k tokens/s, far below 250k tokens/s.

The 429 path (and any retry-after behavior) was NOT observed because we deliberately did not exceed the documented limits. This experiment establishes that normal, even rapid, operation does not trigger rate limiting — but it does NOT test the actual ceiling.

## Conclusion

- **H053 (moderate burst completes without 429): SUPPORTED.** 10/10 returned 200.
- **H054 (429 response structure): NOT ASSESSED** (no 429 observed).

Normal operation, including rapid back-to-back calls, does not rate-limit. The exact rate-limit ceiling remains untested by design (the handoff prohibits intentionally hammering the API).

## Limitations

- Does not exceed documented limits, so the ceiling is unverified.
- Single burst; rate limits may be time-window based.
- Token-based limits untested (each request is small).

## Next experiment

Add-on E (cost verification) or begin Phase 3.