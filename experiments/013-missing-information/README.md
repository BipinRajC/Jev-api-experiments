# Experiment 013 — Missing Information

## Objective

Distinguish how Jev treats three related-but-different kinds of missing information:
1. **Explicitly unknown** — "The color is unknown."
2. **Unmentioned** — the state contains no color information at all.
3. **Explicitly insufficient** — "There is not enough information to determine the color."

This tests whether Jev treats "unknown," "unmentioned," and "explicitly insufficient" as equivalent or as distinct states. It directly builds on the Phase 1 finding: the unmentioned-sky state returned Noul=0.05 and Choice="unspecified."

## Hypothesis

- H038: Jev treats "unknown," "unmentioned," and "not enough information" as equivalent states (same Noul/Choice output).
- H039: Jev distinguishes at least some of these framings (materially different outputs across the three cases).
- H040: For a color question with missing color information, Jev's Noul is near 0 (not near 0.5), matching the Phase 1 unmentioned result.

These are complementary for H038/H039; exactly one will be supported.

## Experimental setup

Base question (Noul): "Is the color blue?"

Three cases differing only in how the missing color info is framed:

| Case | State |
|------|-------|
| A — unknown | "The color of the ball is unknown." |
| B — unmentioned | "There is a ball on the table." |
| C — insufficient | "There is not enough information to determine the color of the ball." |

Plus a positive control:

| Case | State |
|------|-------|
| D — control (blue) | "The ball is blue." |

For each case, three primitives in one batch:
- Noul: "Is the color blue?"
- Choice: options blue / not_blue / unknown — "What is the color of the ball?"
- Score: certainty rubric (0-4) — "How certain is the color being blue?"

Each case repeated n=3. 12 batch calls.

## Variables

- Independent variable: framing of the missing color information (unknown / unmentioned / insufficient), plus a positive control
- Dependent variables: Noul value, Choice label + confidence, Score value + confidence
- Held constant: question wording, model (jev-1.13.0), primitive definitions, color being asked about (blue)

## Controls

- All three missing-information cases describe a ball whose color is not specified, just worded differently.
- Positive control (blue ball) anchors the "known" endpoint.
- Model pinned to jev-1.13.0.

## Expected result

- If Jev treats all missing cases identically: A, B, C produce the same Noul/Choice.
- If Jev distinguishes: the three cases diverge.
- Phase 1 suggests unmentioned → Noul ≈ 0.05, Choice = unspecified/unknown.

## Falsification criteria

- H038 is SUPPORTED if A, B, C Noul means are within ~0.03 of each other (and Choice labels match).
- H039 is SUPPORTED if A, B, C diverge by more than ~0.03 in Noul, or Choice labels differ.
- H040 is SUPPORTED if missing-info Noul means are < 0.2 (near no), consistent with Phase 1.

## Sample size

4 cases × 3 repeats = 12 batch calls (3 questions each) = 36 answers. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 12/12 HTTP 200 (4 cases × 3 batch calls, 3 questions each = 36 answers)
**Cost:** ~$0.000246 (5,850 input tokens)

### Noul by case ("Is the color blue?")

| Case | Nouls | Mean |
|------|-------|------|
| unknown | 0.24, 0.22, 0.26 | **0.24** |
| unmentioned | 0.20, 0.20, 0.20 | **0.20** |
| insufficient | 0.29, 0.29, 0.29 | **0.29** |
| control (blue) | 0.90, 0.88, 0.88 | **0.887** |

### Choice by case

- unknown, unmentioned, insufficient → all **"unknown"** (confidence 1.0)
- control → **"blue"** (confidence 1.0)

### Score by case (certainty of blue, 0-4)

| Case | Score mean | Confidence |
|------|-----------|------------|
| unknown | 1.99 | 0.99 |
| unmentioned | 1.96 | 0.97 |
| insufficient | 1.99 | 0.99 |
| control | 3.98 | 0.98 |

## Analysis

### The three missing-info framings are NOT fully equivalent

- **Choice** treats them identically: all three → "unknown" (confidence 1.0).
- **Score** treats them nearly identically: 1.99, 1.96, 1.99 (all ≈ 2.0 = "unknown/even chance").
- **Noul** distinguishes them: 0.24 (unknown) vs 0.20 (unmentioned) vs 0.29 (insufficient). The range (0.09) exceeds the 0.02 jitter baseline and is reproducible (within-case jitter ≤ 0.04).

So whether Jev "distinguishes" the framings depends on the primitive. Choice and Score collapse them to "unknown," but Noul responds to the specific wording.

### Noul on missing info is NOT near 0 — contradicts Phase 1's 0.05

Phase 1 (Experiment 002) found an unmentioned-sky state returned Noul=0.05. This experiment found missing-color cases return Noul 0.20-0.29. These are NOT near 0.

This is a meaningful nuance: the Phase 1 value (0.05) may have been specific to the "The weather looks mixed today." phrasing (which implies negative/blurry evidence rather than neutral absence). Here, neutral missing-information phrasings ("unknown", "unmentioned", "not enough info") return values in the 0.20-0.29 band — low but clearly above 0, and clearly below 0.5.

Notably, Noul at 0.20-0.29 does NOT represent uncertainty as well as the Score, which landed at exactly ~2.0 (the rubric's "unknown / even chance" level). Score is the more semantically-appropriate uncertainty signal here.

### Score (~2.0) best represents "unknown"

The Score rubric mapped "unknown / even chance" to level 2, and all three missing cases landed at ~1.96-1.99. This is the most interpretable uncertainty representation. Noul (0.20-0.29) is ambiguous — is 0.25 "probably not blue" or "unknown"? — whereas Score's 2.0 unambiguously means "unknown / even chance."

## Conclusion

- **H038 (unknown/unmentioned/insufficient are equivalent): PARTIAL / REJECTED for Noul.** Choice and Score treat them identically, but Noul distinguishes them (0.20 vs 0.29, range 0.09 > jitter).
- **H039 (Jev distinguishes the framings): PARTIAL.** Noul distinguishes; Choice/Score do not. The answer is primitive-dependent.
- **H040 (missing info → Noul near 0): REJECTED.** Missing-color cases returned 0.20-0.29, not near 0. This differs from Phase 1's 0.05 (which likely reflected a "mixed/negative" phrasing, not neutral absence).

**Net:** Missing information is represented by Jev as low-but-not-zero Noul (0.20-0.29), a clear "unknown" Choice label, and a ~2.0 "even chance" Score. The Score rubric is the clearest uncertainty signal. Phase 1's near-zero Noul (0.05) does not generalize to neutral missing-information phrasings.

## Limitations

- Single question (color blue). Does not test other domains.
- Three missing framings + one control; other phrasings exist.
- n=3 per case.
- The Score rubric's "unknown / even chance" level (2) anchors the interpretation.
- Noul's 0.20-0.29 band is state-specific; the exact values may vary with wording (per 009).

## Next experiment

014 — Score interpolation. With missing-information behavior characterized, test whether Score produces fractional values on graded evidence, and whether the ~2.0 "unknown" reading generalizes.