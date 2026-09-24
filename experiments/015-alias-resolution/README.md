# Experiment 015 — Alias Resolution (Add-on A)

## Objective

Determine what exact model version the `jev-latest` alias resolves to, and whether the response `model` field reports the versioned ID or the alias. The docs state `jev-latest` points to `jev-1.13.0`, but this has not been verified experimentally (noted as UNVERIFIED in api-notes.md). This establishes the alias behavior without mixing it into pinned experiments.

## Hypothesis

- H045: Sending `model: "jev-latest"` returns a response whose `model` field is a versioned ID (e.g., `jev-1.13.0`), confirming the alias resolves to a concrete version.
- H046: The alias `jev-latest` produces the same decision output as the pinned `jev-1.13.0` on an identical question (i.e., the alias currently points to 1.13.0).

## Experimental setup

One Noul question on a simple state, sent twice:
- Call 1: `model: "jev-latest"`
- Call 2: `model: "jev-1.13.0"` (control)

State: "A bag contains 70 red balls and 30 blue balls. One ball is selected randomly."
Question: "Will the selected ball be red?"

n=1 for each model to keep it cheap; the goal is the `model` field resolution, not a statistical comparison.

## Variables

- Independent variable: model identifier in the request (`jev-latest` vs `jev-1.13.0`)
- Dependent variables: response `model` field, Noul value, HTTP status
- Held constant: state, question, endpoint

## Controls

- Same state and question for both calls.
- The pinned `jev-1.13.0` call serves as the control.

## Expected result

- Response `model` = `jev-1.13.0` for the `jev-latest` request.
- Noul values close (within jitter) between the two.

## Falsification criteria

- H045 is SUPPORTED if `jev-latest` returns a versioned ID in the response `model`.
- H046 is SUPPORTED if the `jev-latest` Noul is within ~0.02 of the `jev-1.13.0` Noul.
- If `jev-latest` returns an error or a different model, both are REJECTED.

## Sample size

2 calls (1 alias + 1 control). Cost is trivial.

## Results

**Date:** 2026-09-23
**Model requested:** `jev-latest` (alias) and `jev-1.13.0` (pinned control)
**Calls:** 2/2 HTTP 200
**State:** 70/30 bag; Noul "Will the selected ball be red?"

| Label | Requested | Returned | Noul |
|-------|-----------|----------|------|
| alias | jev-latest | **jev-1.13.0** | 0.66 |
| pinned | jev-1.13.0 | **jev-1.13.0** | 0.67 |

Noul diff: 0.01 (within the 0.02 jitter baseline).

## Analysis

The `jev-latest` alias resolved to the versioned ID `jev-1.13.0` in the response `model` field. The alias and pinned models produced essentially identical Noul outputs (0.66 vs 0.67, diff 0.01), consistent with them being the same model. This verifies the documentation claim that `jev-latest` currently points to `jev-1.13.0`.

## Conclusion

- **H045 (jev-latest resolves to a versioned ID): SUPPORTED.** Response `model` = `jev-1.13.0`.
- **H046 (jev-latest == jev-1.13.0 output): SUPPORTED.** Noul diff 0.01 within jitter.

Alias resolution is verified as of the run date. This does NOT mean aliases are safe for reproducible experiments — they move when new versions ship, so pinned versioned IDs remain the correct choice for reproducible work.

## Limitations

- n=1 per model; the Noul comparison is indicative only.
- Snapshot as of 2026-09-23; alias target may change when a new version ships.
- Does not test `jev-preview`.
- The Noul diff (0.01) is within jitter but could mask a subtle version difference; a proper test would need repeatability across both models.

## Next experiment

Add-on D (large fan-out) or continue to add-ons.