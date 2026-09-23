# Experiment 009 — Wording Sensitivity

## Objective

Determine whether semantically equivalent questions produce materially different outputs. Hold everything constant (state, model, primitive, options) and vary only the question wording. This tests whether Jev's answers are robust to how a question is phrased, or whether phrasing itself is a significant source of output variation.

Experiment 008 established that Noul jitter on identical input is only ±0.01 (mean 0.46, range 0.02). This provides a baseline: any output variation larger than ~0.02 across wordings is attributable to the wording change, not output noise.

## Hypothesis

- H027: Semantically equivalent Noul wordings produce materially different Noul values.
- H028: Semantically equivalent Noul wordings produce stable (non-wording-sensitive) outputs within jitter baseline (±0.02).

These are complementary framings of the same question; exactly one will be supported.

## Experimental setup

State (constant):

```text
A bag contains 70 red balls and 30 blue balls.
One ball is selected randomly.
```

Model: jev-1.13.0 (constant).

Noul question, four semantically equivalent formulations:

| ID | Wording |
|----|---------|
| will_be_red | "Will the selected ball be red?" |
| likely_red | "Is the selected ball likely to be red?" |
| chance_red | "What is the chance that the selected ball is red?" |
| evidence_red | "Does the evidence support the ball being red?" |

Ground truth: the ball has a 70% chance of being red.

Each wording repeated n=3 to average out the ±0.01 jitter established in Experiment 008. 12 total calls.

## Variables

- Independent variable: question wording (4 variants)
- Dependent variables: Noul value
- Held constant: state, model, primitive, options, question id structure

## Controls

- The state is identical across all 4 wordings.
- The model is pinned (jev-1.13.0).
- Noul primitive used throughout.
- n=3 per wording to control for the ±0.01 jitter baseline.

## Expected result

- If wording-insensitive: all 4 wordings produce Noul values within ~0.02 of each other.
- If wording-sensitive: some wordings drift by more than 0.02.

## Falsification criteria

- H027 is SUPPORTED if the range across wording means exceeds ~0.02 (the jitter baseline).
- H028 is SUPPORTED if the range across wording means is within ~0.02.

A range between 0.02 and 0.05 is borderline and will be reported as such rather than forced into a binary.

## Sample size

4 wordings × 3 repeats = 12 Noul calls. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 12/12 HTTP 200 (4 wordings × 3 repeats)
**Ground truth:** 70% red

### Noul by wording

| Wording | Mean Noul | Repeats | Within-range | vs ground truth |
|---------|-----------|---------|--------------|-----------------|
| "Will the selected ball be red?" | **0.66** | 0.66, 0.66, 0.67 | 0.01 | −0.04 |
| "What is the chance that the selected ball is red?" | **0.71** | 0.71, 0.71, 0.71 | 0.00 | +0.01 |
| "Is the selected ball likely to be red?" | **0.87** | 0.87, 0.87, 0.87 | 0.00 | +0.17 |
| "Does the evidence support the ball being red?" | **0.84** | 0.86, 0.84, 0.83 | 0.03 | +0.14 |

### Summary statistics

- Global mean across all 12 calls: 0.772
- Range across all 12 repeats: 0.21
- **Range across wording means: 0.207**
- Stdev across wording means: 0.101
- Jitter baseline (from 008): 0.02

## Analysis

### Wording sensitivity is LARGE — an order of magnitude beyond the jitter baseline

The range across wording means is **0.207**, which is ~10x the jitter baseline (0.02) established in Experiment 008. The four wordings split cleanly into two clusters:

- **Literal/phrased probabilities:** "Will be red?" (0.66) and "What is the chance?" (0.71) → near ground truth (0.70)
- **Judgment-eliciting phrasings:** "Is it likely?" (0.87) and "Does the evidence support?" (0.84) → inflated by ~0.14–0.17

This is not output noise. Within each wording, jitter was tiny (all within-ranges ≤ 0.03, and 2 of 4 wordings had range 0.00). The variation is entirely attributable to the wording change.

### The inflation pattern is systematic

The two phrasings that frame the question as a **judgment** ("likely", "evidence support") produce higher Noul values than the two that frame it as a **literal outcome probability** ("will be", "chance"). The state is identical. This suggests Jev is sensitive to the pragmatic framing of the question, not just the underlying facts.

This is a significant concern for calibration: the same underlying probability (70%) yields answers ranging 0.66–0.87 depending on phrasing. The "likely" phrasing asks "is it likely?" — and Jev may be interpreting this as asking whether the event is on the "likely" side of a threshold (which 70% clearly is), rather than asking for the exact probability.

### Wording matters more than jitter

With within-wording jitter ≤ 0.03 and cross-wording spread of 0.207, **wording choice is the dominant source of Noul variation** — not model noise. For any application, standardizing question phrasing is more important than repeating calls to reduce noise.

## Conclusion

- **H027 (Semantically equivalent wordings produce materially different Noul values): SUPPORTED.** Range across wording means = 0.207, ~10x the jitter baseline.
- **H028 (Wording-insensitive within jitter baseline): REJECTED.**

Noul is substantially wording-sensitive. The variation is systematic (judgment-framed phrasings inflate the probability) and dwarfs the run-to-run jitter. This means:
1. Noul values cannot be treated as frame-independent measurements of a single underlying probability.
2. Any claims about Noul "calibration" must be tied to a specific, fixed question phrasing.
3. The 0.66–0.71 values from literal phrasings are closest to the 0.70 ground truth; the inflated values come from judgment-framed phrasings.

## Limitations

- Single state (70/30 bag). Does not test whether wording sensitivity varies with evidence strength.
- Only 4 wordings sampled; the space of equivalent phrasings is much larger.
- n=3 per wording; wording means have ~0.01 uncertainty (jitter / sqrt(3)), negligible vs the 0.207 spread.
- Noul only; Choice and Score wording sensitivity not tested here.
- The specific magnitude (0.66–0.87) may be specific to this state and these particular phrasings.

## Next experiment

010 — Irrelevant information. Given that wording sensitivity is large and systematic, it is important to control phrasing tightly in 010 so that any drift is attributable to the added (irrelevant) context, not to phrasing differences.