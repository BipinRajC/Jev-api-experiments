# Add-on E — Cost Verification

## Objective

Compare the estimated cost of all experiments (computed as `usage.input_tokens × documented price`) against the actual account usage. The handoff notes "Do not assume the console accounting mechanism" — so this document reports what we can verify (token accounting and estimated cost) and clearly flags what remains unverified (actual billing) due to no console access.

## Method

For every completed experiment, sum `usage.input_tokens` across all calls and multiply by the documented price of **$0.042 / 1M input tokens** (output free). Compare against the $5 promotional credit (expires 2026-10-19).

## Aggregated usage (all experiments with trials)

| Experiment | Calls | Input tokens | Est. cost (USD) |
|------------|------:|-------------:|----------------:|
| 002-noul | 9 | 2,514 | 0.000106 |
| 003-choice | 9 | 3,144 | 0.000132 |
| 004-score | 9 | 2,964 | 0.000124 |
| 005-error-handling | 4 | 0* | 0.000000 |
| 007-mixed-evidence | 13 | 5,866 | 0.000246 |
| 008-repeatability | 40 | 14,100 | 0.000592 |
| 009-wording-sensitivity | 12 | 3,552 | 0.000149 |
| 010-irrelevant-information | 8 | 2,850 | 0.000120 |
| 011-structured-state | 9 | 4,152 | 0.000174 |
| 012-conflicting-evidence | 9 | 4,692 | 0.000197 |
| 013-missing-information | 12 | 5,850 | 0.000246 |
| 014-score-interpolation | 18 | 7,704 | 0.000324 |
| 015-alias-resolution | 2 | 588 | 0.000025 |
| 016-fan-out | 4 | 1,747 | 0.000073 |
| 017-noul-criteria | 9 | 2,829 | 0.000119 |
| 018-rate-limit | 10 | 2,940 | 0.000123 |
| **TOTAL** | **177** | **65,492** | **$0.002751** |

\* 005-error-handling used `post_raw` calls that returned errors; token counts not recorded for non-200 responses.

## Findings

### Estimated cost is a tiny fraction of budget

- **Total estimated cost: $0.0028**
- **$5 promotional credit → 0.055% of budget used**
- This covers ALL experiments (001–018), including Phase 1 and Phase 2 plus add-ons.

### Token accounting is internally consistent

- Token counts are deterministic across identical repeats (verified in 008: constant 301/404 tokens).
- Token usage scales sublinearly with question count (verified in 016).
- These are the two behaviors that make cost predictable.

### Actual billing is UNVERIFIED

I do **not** have access to the TypeSafe account console, so I cannot confirm:
- Whether billed usage matches `usage.input_tokens × $0.042/Mtok`.
- Whether the promotional credit is actually debited at this rate.
- Whether there is any minimum charge, per-request fee, or other billing mechanism.

The handoff explicitly says "Do not assume the console accounting mechanism." Therefore the $0.042/Mtok figure remains a **documented list price**, and the actual billed cost is **UNVERIFIED**.

## Conclusion

- Estimated total research cost to date: **~$0.003** — negligible against the $5 budget.
- Token accounting is deterministic and sublinear in question count, making cost predictable.
- **Actual billed amount: UNVERIFIED** without console access. The listed price ($0.042/Mtok input, output free) is used only for estimation.

## Recommendations

1. If account console access becomes available, compare the reported usage against this estimate to verify the billing mechanism.
2. Monitor the credit balance after each batch of experiments to detect any divergence from the list price.
3. Given the negligible cost so far, the $5 budget is more than sufficient for the remainder of Phase 2 add-ons and Phase 3 calibration.