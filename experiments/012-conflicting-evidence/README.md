# Experiment 012 — Conflicting Evidence

## Objective

Determine how Jev handles internally contradictory state. The state explicitly asserts two mutually exclusive facts. This tests whether Jev:
- picks one side
- distributes probability / expresses uncertainty
- recognizes the contradiction
- becomes highly confident despite the contradiction

This is a critical behavioral probe: if Jev becomes confidently wrong on contradictory input, that limits where its outputs can be trusted.

## Hypothesis

- H034: Given internally contradictory state, Jev's Noul value moves toward an intermediate/uncertain value (near 0.5) rather than confidently picking a side.
- H035: Given contradictory state, Jev's Choice selects an explicit "uncertain/conflicting" option when one is available.
- H036: Given contradictory state, Jev's confidence is low (well below 1.0).
- H037: Jev's handling of contradictory state is consistent across repeats.

## Experimental setup

### Scenario — contradictory sky observations

State:

```text
Statement 1: The sky is blue.
Statement 2: The sky is grey.
Statement 3: The observation was made during the same time period.
```

Three primitives in one batch:

- Noul: "Is the sky blue?" — expectation if uncertainty-aware: near 0.5
- Choice: options blue / grey / uncertain — expectation if uncertainty-aware: "uncertain"
- Score: uncertainty/evidence rubric (0-4) — expectation: intermediate

Three contradictory scenarios tested:

| Case | State | Ground truth of contradiction |
|------|-------|-------------------------------|
| sky | blue vs grey (above) | maximal contradiction |
| coin | "The coin shows heads." + "The coin shows tails." | maximal contradiction |
| direction | "The car is moving north." + "The car is moving south." | maximal contradiction |

Each case repeated n=3 to check consistency. 9 batch calls.

### Score rubric (shared across cases)

```text
0 = completely clear, one side
1 = mostly clear, one side dominant
2 = mixed, balanced
3 = mostly contradictory, little clarity
4 = fully contradictory, no way to decide
```

## Variables

- Independent variable: the content of the contradictory pair
- Dependent variables: Noul value, Choice label + confidence, Score value + confidence
- Held constant: contradiction structure (two mutual exclusives), primitive definitions, model (jev-1.13.0)

## Controls

- All scenarios use exactly two mutually-exclusive statements plus a "same time period" tie-breaker.
- Question wording and rubric held constant across cases.
- Model pinned to jev-1.13.0.

## Expected result

- If uncertainty-aware: Noul near 0.5, Choice = "uncertain", Score mid-range, confidence < 1.0.
- If confidently-biased: Noul near 0 or 1, Choice picks a side, Score at an extreme, confidence 1.0.

## Falsification criteria

- H034 is SUPPORTED if Noul means fall in [0.35, 0.65] (uncertain) rather than near 0/1.
- H035 is SUPPORTED if Choice selects "uncertain" in the majority of calls.
- H036 is SUPPORTED if confidence means < 0.9 (clearly below 1.0).
- H037 is SUPPORTED if Choice label is stable across the 3 repeats.

## Sample size

3 cases × 3 repeats = 9 batch calls (3 questions each) = 27 answers. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 9/9 HTTP 200 (3 cases × 3 batch calls, 3 questions each = 27 answers)

### Noul by case (contradictory pairs)

| Case | Nouls | Mean | Interpretation |
|------|-------|------|----------------|
| sky (blue vs grey) | 0.68, 0.70, 0.69 | **0.69** | leans toward "blue" (first statement) |
| coin (heads vs tails) | 0.49, 0.48, 0.49 | **0.49** | near 0.5 (uncertain) |
| direction (north vs south) | 0.39, 0.40, 0.41 | **0.40** | leans away from "north" |

### Choice by case

All 9 calls selected **"uncertain"** (confidence 0.95–0.99). Perfectly consistent.

### Score (contradiction level, 0–4) by case

| Case | Scores | Mean | Confidence |
|------|--------|------|------------|
| sky | 3.51, 3.61, 3.55 | 3.56 | 0.59–0.68 |
| coin | 3.68, 3.63, 3.69 | 3.67 | 0.69–0.75 |
| direction | 3.82, 3.82, 3.82 | 3.82 | 0.85 |

All scores high (recognizes strong contradiction). Score confidence (0.59–0.85) is notably lower than Choice confidence (0.95–0.99).

## Analysis

### Jev clearly recognizes contradiction — but expresses it differently across primitives

The most striking result: **Choice selected "uncertain" in all 9 calls.** When an explicit "uncertain/conflicting" option is available, Jev reliably uses it. This is strong evidence that Jev detects the contradiction rather than blindly picking a side.

The **Score** also reflects the contradiction — all cases scored 3.5+ on a 0-4 "how contradictory" scale, correctly indicating a high contradiction level. Score confidence (0.59-0.85) is the lowest observed so far in this project, suggesting Jev is genuinely uncertain about how contradictory to call it.

### Noul does NOT collapse to 0.5 symmetrically

This is the nuanced and important finding. Noul on the contradictory pair was:
- **0.69 for "Is the sky blue?"** — leans toward blue (the first-stated alternative)
- **0.49 for "Does the coin show heads?"** — properly uncertain
- **0.40 for "Is the car moving north?"** — leans away from north

So Noul does not reliably return 0.5 on contradiction. It depends on which side is being asked about, and can lean toward or away from it. Only the coin case hit near 0.5.

This is consistent with Experiment 009 (wording sensitivity): Noul is not a symmetric, frame-independent measure. On contradictory input, it does not reliably signal "uncertain" — the Choice primitive with an explicit "uncertain" option is far more reliable for that.

### Confidence is nuanced

- **Choice confidence is HIGH (0.95-0.99)** — but it's confident about the *category* "uncertain," which is correct.
- **Score confidence is LOWER (0.59-0.85)** — Jev is less sure how contradictory to score it.

So "confidence" is not a single thing: Jev can be confident about detecting a contradiction (Choice) while being less confident about rating its degree (Score).

### Consistency across repeats

Choice was perfectly stable (uncertain 3/3 in every case). Noul and Score were also very stable (e.g., direction Score exactly 3.82 × 3). Contradiction handling is consistent, not jittery.

## Conclusion

- **H034 (Noul → intermediate/0.5 on contradiction): PARTIALLY / INCONCLUSIVE.** Coin hit 0.49, but sky (0.69) and direction (0.40) did not. Noul does not reliably collapse to 0.5 on contradiction; it can lean toward or away from the stated side.
- **H035 (Choice → "uncertain" when available): STRONGLY SUPPORTED.** 9/9 selected "uncertain."
- **H036 (confidence well below 1.0): PARTIAL.** Choice confidence is high (0.95-0.99) because Jev is confident it detected the contradiction; Score confidence is low (0.59-0.85). The blanket prediction "low confidence on contradiction" is too simple.
- **H037 (consistent across repeats): SUPPORTED.** Choice stable 3/3, Noul/Score very stable.

**Net takeaway:** Jev reliably *detects* contradiction (Choice → "uncertain", Score → high contradiction rating) but Noul is not a reliable uncertainty signal on contradictory input. To handle conflict, prefer Choice with an explicit "uncertain/conflicting" option over Noul.

## Limitations

- Contradiction is explicit and maximal (direct mutual exclusives). Does not test subtle or partial conflicts.
- Three scenarios; the specific content varies but the structure is constant.
- n=3 per case.
- The "same time period" tie-breaker frames it as genuine simultaneous contradiction.
- The Noul lean (toward/away) may depend on statement order or the specific pair content.

## Next experiment

013 — Missing information. Since Choice reliably signals "uncertain," test how Jev distinguishes explicit "unknown" vs unmentioned vs "not enough information" states (Experiment 013's three cases).