# Experiment 017 — Noul Criteria Behavior (Add-on F)

## Objective

Determine whether the optional `criteria.{true,false}` fields on a Noul question materially affect the output. The API supports optional `criteria` for Noul (per api-notes.md). This tests whether providing explicit true/false criteria changes the Noul value versus an instruction-only formulation.

This matters because a production application might want to add criteria to sharpen Noul questions — but only if it actually changes behavior in a predictable way.

## Hypothesis

- H051: Adding explicit `criteria.{true,false}` changes the Noul value compared to an instruction-only formulation.
- H052: Adding `criteria.{true,false}` does NOT change the Noul value (within the ±0.02 jitter baseline).

These are complementary; exactly one will be supported.

## Experimental setup

State (constant): an ambiguous-but-quantified case to give room for the criteria to matter.

```text
A bag contains 55 red balls and 45 blue balls. One ball is selected randomly.
```

Question intent: "Is the ball red?" (ground truth ~0.55, genuinely ambiguous so criteria could shift it).

Three Noul formulations, same underlying question:

| ID | Formulation |
|----|-------------|
| instruction_only | `{"type": "noul", "instructions": "Is the ball red?"}` |
| criteria_true | `{"type": "noul", "instructions": "Is the ball red?", "criteria": {"true": "The ball is red.", "false": "The ball is not red."}}` |
| criteria_reworded | `{"type": "noul", "instructions": "Decide whether the ball is red.", "criteria": {"true": "Return a high probability if the ball is red.", "false": "Return a low probability if the ball is not red."}}` |

Each formulation repeated n=3. 9 calls.

## Variables

- Independent variable: whether/how `criteria` is specified (none / plain true-false / reworded)
- Dependent variables: Noul value
- Held constant: state, underlying question intent, model (jev-1.13.0), primitive

## Controls

- Same state and question intent across formulations.
- Model pinned.
- n=3 per formulation to control jitter.

## Expected result

- If criteria are inert: all three formulations produce Noul within ~0.03 of each other.
- If criteria matter: they diverge.

## Falsification criteria

- H051 is SUPPORTED if the range across formulation means exceeds ~0.03.
- H052 is SUPPORTED if the range stays within ~0.03.

## Sample size

3 formulations × 3 repeats = 9 Noul calls. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 9/9 HTTP 200 (3 formulations × 3 repeats)
**State:** 55 red / 45 blue bag (ground truth ~0.55)

### Noul by formulation

| Formulation | Nouls | Mean |
|-------------|-------|------|
| instruction_only | 0.55, 0.55, 0.56 | **0.553** |
| criteria_plain (true/false restatement) | 0.58, 0.57, 0.57 | **0.573** |
| criteria_reworded (probability language) | 0.63, 0.62, 0.63 | **0.627** |

Range across formulation means: 0.073 (well above the 0.03 threshold).

## Analysis

### Criteria DO affect Noul, but the effect depends on how the criteria are worded

- **Plain criteria** (restating "The ball is red." / "The ball is not red.") had only a small effect: 0.553 → 0.573 (+0.02, ~at the jitter boundary).
- **Reworded criteria** (using probability language: "Return a high probability if red" / "low probability if not red") had a larger effect: 0.553 → 0.627 (+0.07).

The overall range (0.073) exceeds the 0.03 threshold, so criteria do matter. But the plain criteria barely moved the needle while the reworded criteria added ~0.07.

This is fully consistent with Experiment 009 (wording sensitivity): adding any wording shifts Noul, and the magnitude depends on the specific words. The reworded criteria essentially inject additional instruction language ("return a high probability") that nudges the value up.

### Which is "correct"?

The instruction-only value (0.553) and plain-criteria value (0.573) are both close to the 55% ground truth. The reworded criteria (0.627) overshoots — the "high probability" phrasing appears to inflate the answer. This mirrors 009's finding that judgment-framed wording inflates Noul.

## Conclusion

- **H051 (Criteria change the Noul value): SUPPORTED.** Range across formulations 0.073 > 0.03 threshold.
- **H052 (Criteria do not change the value): REJECTED.**

**Nuance:** Criteria matter, but plain true/false criteria (restating the proposition) have a marginal effect (~0.02), while reworded criteria with probability meta-language have a larger effect (~0.07). The effect is consistent with wording sensitivity (009) rather than criteria-specific behavior.

## Limitations

- Single state and question.
- Three criteria formulations; other wordings exist.
- n=3 per formulation.
- The reworded criteria confound "criteria" with "extra wording" — the effect may be mostly the extra language, not the criteria per se.

## Next experiment

Add-on B (HTTP 429) or continue.