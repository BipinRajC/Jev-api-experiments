# Experiment 010 — Irrelevant Information

## Objective

Test whether adding irrelevant state information changes Jev's decision. The relevant facts (a 70/30 bag) remain identical; only semantically-irrelevant context is appended. This tests whether context pollution ("distractor" information) shifts the output.

Experiment 009 established that Noul jitter is ±0.02 and that wording is the dominant source of variation. To isolate the effect of added context, the question wording is held constant across all conditions.

## Hypothesis

- H029: Appending irrelevant information to the state changes the Noul value.
- H030: Appending irrelevant information does NOT change the Noul value (within the ±0.02 jitter baseline).

These are complementary; exactly one will be supported. A gradient (more irrelevant facts → larger drift) would be evidence for dose-dependent context pollution.

## Experimental setup

Base state (constant):

```text
A box contains 70 red balls and 30 blue balls.
One ball is selected randomly.
```

Noul question (constant, held from 009's most-accurate phrasing):

```text
Will the selected ball be red?
```

Ground truth: 70% red.

Four levels of appended irrelevant context:

| Level | Added context |
|-------|---------------|
| baseline | none |
| +1 fact | "The experiment is being conducted on a Tuesday." |
| +5 facts | 5 irrelevant sentences (day, observer's shirt, room temperature, table, lighting) |
| +20 facts | 20 irrelevant sentences (varied sensory/environmental details) |

Each level repeated n=2 to average the ±0.02 jitter. 8 total calls.

## Variables

- Independent variable: amount of appended irrelevant context (0/1/5/20 facts)
- Dependent variables: Noul value
- Held constant: relevant state, question wording, model (jev-1.13.0), primitive, question id

## Controls

- The relevant facts (70 red / 30 blue) are byte-identical across all levels.
- The question wording is byte-identical across all levels.
- The irrelevant facts are topically unrelated to color (no red/blue references).

## Expected result

- If context-robust: all Noul values within ~0.02 of the baseline.
- If context-sensitive: appended context shifts Noul away from baseline, possibly dose-dependently.

## Falsification criteria

- H029 is SUPPORTED if any level's mean drifts from baseline by more than ~0.03 (jitter + margin).
- H030 is SUPPORTED if all levels' means stay within ~0.03 of baseline.
- A monotonic gradient (drift increasing with fact count) is strong evidence for dose-dependent context pollution.

## Sample size

4 levels × 2 repeats = 8 Noul calls. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 8/8 HTTP 200 (4 levels × 2 repeats)
**Ground truth:** 70% red

### Noul by context level

| Level | Facts | Mean Noul | Repeats | Within-range | Drift from baseline |
|-------|-------|-----------|---------|--------------|---------------------|
| baseline | 0 | **0.665** | 0.66, 0.67 | 0.01 | — |
| plus_1 | 1 | **0.675** | 0.68, 0.67 | 0.01 | +0.010 |
| plus_5 | 5 | **0.700** | 0.70, 0.70 | 0.00 | +0.035 |
| plus_20 | 20 | **0.710** | 0.71, 0.71 | 0.00 | +0.045 |

### Summary

- Max absolute drift from baseline: **0.045** (plus_20)
- Jitter baseline: 0.02
- Drift is **monotonic** — increases smoothly with fact count (0.010 → 0.035 → 0.045)
- Within-level jitter: all ≤ 0.01 (3 of 4 levels had range ≤ 0.01)

## Analysis

### Context does shift Noul, but in a dose-dependent and counterintuitively "helpful" direction

The monotonic increase (0.665 → 0.675 → 0.70 → 0.71) is real and dose-dependent — all within-level jitter is tiny (≤ 0.01), so the trend is not noise. The max drift (0.045) modestly exceeds the 0.02 jitter baseline.

**However, the direction matters.** The baseline (0.665) was a slight *underestimate* of the 0.70 ground truth. Adding irrelevant context moved the answer *toward* the correct value (0.70-0.71), not away from it. The "pollution" actually improved calibration on this state.

This is the opposite of what naive "context pollution" would predict (which would be that added noise degrades accuracy). Here, the extra context appears to anchor or reinforce the relevant information rather than distract from it.

### Not classic distraction

The drift magnitude is modest (0.045 max) relative to the wording-sensitivity effect from Experiment 009 (0.207). Context is a much weaker influence than wording. Also, since the drift is monotonic and toward ground truth, there is no evidence of the classic "distractor" failure mode where irrelevant details overwhelm the relevant signal.

### Possible explanations (untested here)

1. The added context may reinforce the "scenario" framing, making the 70/30 composition more salient.
2. The drift may be coincidental on this single state — only one composition was tested.
3. The irrelevant facts used here are neutral. Facts that conflict with or contradict the relevant info might behave very differently (this is Experiment 012's domain).

## Conclusion

- **H029 (Appending irrelevant information changes the Noul value): SUPPORTED** — but weakly. Max drift 0.045 exceeds the 0.02 jitter baseline, and the drift is dose-dependent (monotonic in fact count).
- **H030 (Irrelevant information does NOT change the Noul value): REJECTED** under strict interpretation.

**Nuanced conclusion:** Irrelevant context does shift Noul (monotonically with amount added), but the effect is modest (≤ 0.045) and in this case moved the answer *toward* ground truth rather than away. There is no evidence of catastrophic context pollution on this state. The effect is far weaker than the wording sensitivity found in 009.

## Limitations

- Single state (70/30 bag). Only one composition tested.
- The irrelevant facts were neutral/environmental. Conflicting or contradictory context was not tested (Experiment 012).
- The 20-fact condition adds many sentences; cannot distinguish "more context" from "particular context."
- n=2 per level.
- Noul only; Choice and Score context-sensitivity not tested here.

## Next experiment

011 — Structured vs unstructured state. Since context modestly shifts Noul, it is worth testing whether representing the identical facts as JSON (structured) rather than prose (unstructured) changes the answer or reduces context sensitivity.