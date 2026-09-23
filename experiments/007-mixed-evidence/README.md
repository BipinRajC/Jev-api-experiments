# Experiment 007 — Mixed / Non-Trivial Evidence

## Objective

Move beyond tautological examples and test whether Jev produces partial or non-one-hot outputs when the evidence is genuinely mixed (i.e., the correct answer is not obvious). Phase 1 used trivially clear states; this experiment probes whether Noul, Choice, and Score can express graded uncertainty beyond binary/one-hot extremes.

## Hypotheses

- H018: Noul produces values significantly different from 0/1 bin edges when given probabilistic evidence with a known ground-truth probability.
- H019: Choice produces non-one-hot probability distributions when multiple options are supported by evidence.
- H020: Score produces non-integer (interpolated) values when evidence falls between rubric levels.
- H021: Within a single batch request, Noul, Choice, and Score produce internally consistent answers (e.g., Noul on "red" correlates with Choice on "red").
- H022: Jev confidence values are not uniformly 1.0 on non-trivial evidence.

## Experimental setup

Three sub-experiments in one batch call (plus separate Noul calls for comparison):

### Sub-experiment A — Noul with known probabilities

Use synthetic coin-flip problems with known outcome probabilities. The state describes a biased coin with a stated probability. The question asks whether the next flip will land heads.

Cases:
- fair coin (50%)
- 70% heads
- 30% heads
- 90% heads
- 10% heads

Plus a control: tautological yes (100% implied) and tautological no (0% implied).

Each case uses one batch call with the Noul question alongside Choice and Score questions.

### Sub-experiment B — Choice with probabilistic urn

State describes an urn with a known composition. Choice has three color options. The question asks what color the drawn ball will be.

The composition is:
- 50% red, 30% blue, 20% green

This is designed to produce a non-one-hot distribution: red should have the highest probability, but blue and green should also have non-zero probability.

### Sub-experiment C — Score with graded evidence

Use a 5-point evidence-strength scale:
- Level 0: no evidence
- Level 1: very weak evidence
- Level 2: weak evidence
- Level 3: moderate evidence
- Level 4: strong evidence
- Level 5: overwhelming evidence

States describe scenarios that should map to intermediate levels without naming the target score:
- vague_hint: "Some preliminary data suggests the hypothesis might hold, but the sample size is tiny and contradictory data also exists."
- weak_study: "A single small study with n=30 and p=0.08 supports the hypothesis. No replication exists."
- moderate_evidence: "Two independent studies with moderate sample sizes find statistically significant results. One replication failed."
- strong_evidence: "Five large randomized controlled trials consistently support the hypothesis. Two meta-analyses confirm the effect."
- overwhelming: "Dozens of independent labs across multiple countries have replicated the finding. The effect is well-established scientific consensus."

The question is: "What level of evidence supports this hypothesis?"

## Variables

- Independent variable: state content (degree of probabilistic evidence / evidence strength)
- Dependent variables: Noul value, Choice probabilities and label, Score value, confidence values
- Held constant: model (jev-1.13.0), endpoint, question wording, rubric structure

## Controls

- tautological Noul cases (extreme probability values) serve as calibration anchors
- All Noul cases and the urn case use states where the ground-truth probability is explicitly stated
- All Score cases describe the evidence without using the rubric labels, so the model must infer the level

## Expected result

- H018: Noul values should track the stated probabilities (e.g., ~0.5 for fair coin, ~0.7 for 70% coin, ~0.3 for 30% coin). Not necessarily exact, but should be clearly distinguishable from 0.01/0.99.
- H019: Choice probabilities should show a non-one-hot distribution for the urn, with red > blue > green > 0.
- H020: Score should produce fractional or non-integer values for intermediate evidence cases.
- H021: Noul, Choice, and Score within the same batch should agree on direction (e.g., for 70% coin, Noul should be >0.5, Choice should select "heads").
- H022: Confidence should be < 1.0 for non-trivial cases.

## Falsification criteria

- H018 is REJECTED if all Noul values remain at 0.99/0.01 extremes despite explicit probabilistic states.
- H019 is REJECTED if Choice continues to be one-hot on the probabilistic urn with red only at 1.0.
- H020 is REJECTED if all Score outputs are exact integers despite graded evidence descriptions.
- H021 is REJECTED if Noul and Choice give contradictory direction for the same evidence.
- H022 is REJECTED if confidence remains 1.0 for every non-trivial case.

## Sample size

7 Noul cases × 1 repeat each = 7 Noul data points
1 Choice case = 1 Choice data point
5 Score cases = 5 Score data points

Limited intentionally due to credit budget. Repeats deferred to Experiment 008.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 13/13 HTTP 200
**Cost:** ~$0.000246 (5866 input tokens)

### Sub-experiment A — Noul with known probabilities

| Case | Ground truth | Noul | Abs error |
|------|-------------|------|-----------|
| 100% heads (taut yes) | 1.00 | 0.98 | 0.02 |
| 90% heads | 0.90 | 0.84 | 0.06 |
| 70% heads | 0.70 | 0.65 | 0.05 |
| 50% heads (fair) | 0.50 | 0.45 | 0.05 |
| 30% heads | 0.30 | 0.23 | 0.07 |
| 10% heads | 0.10 | 0.08 | 0.02 |
| 0% heads (taut no) | 0.00 | 0.01 | 0.01 |

- Mean absolute error (non-tautological, n=5): 0.050
- Pearson r (noul vs ground truth, n=7): 0.999
- No values observed at exactly 0.99/1.0 or 0.01/0.0 for non-tautological cases
- Fair coin (50%) produced 0.45, not ~0.5, but clearly distinct from Phase 1's 0.01/0.99 polarization

### Sub-experiment B — Choice with probabilistic urn

| Option | Composition | Jev probability |
|--------|------------|-----------------|
| red | 50% | 1.00 |
| blue | 30% | 0.00 |
| green | 20% | 0.00 |

- Selected: red
- Confidence: 0.99
- One-hot distribution (no partial probabilities despite non-trivial composition)

### Sub-experiment C — Score with graded evidence

| Case | Score | Confidence | Probability spread |
|------|-------|------------|-------------------|
| vague_hint | 1.06 | 0.96 | 94% on 1, 6% on 2 |
| weak_study | 1.01 | 0.88 | 81% on 1, 10% on 2, 9% on 0 |
| moderate | 2.92 | 0.94 | 91% on 3, 9% on 2 |
| strong | 4.68 | 0.79 | 69% on 5, 31% on 4 |
| overwhelming | 4.96 | 0.97 | 97% on 5, 3% on 4 |

All 5 Score outputs are non-integer.
All 5 Score confidence values are < 1.0.

### Confidence summary across all primitives

- 20 confidence observations total
- 4 at 1.0 (all on tautological/extreme cases)
- 16 below 1.0
- Range for non-1.0: 0.79 — 0.99

### Internal consistency (coin batch)

- Noul and Choice directions agree in 6/7 cases
- Fair coin (noul=0.45): noul says "slightly no", Choice says "heads". This is inconsistent with a strictly probabilistic interpretation but consistent with Choice picking the option with highest stated probability (even though the option barely edges out).

## Analysis

### H018 (Noul produces non-extreme values on probabilistic evidence): SUPPORTED

For the first time, Noul produced values well inside the (0, 1) interval. The fair coin case produced 0.45 (vs 0.05 in Experiment 002's ambiguous case where the sky color was simply unmentioned). This demonstrates that Jev can express graded uncertainty when the state explicitly quantifies that uncertainty.

The Noul values track ground-truth probabilities with high correlation (r=0.999) but with a slight conservative bias (values pulled away from 0.5 toward extremes by ~0.05 on average). This pattern may indicate a "certainty preference" — values tend to slightly understate uncertainty.

Crucially, the ambiguous case from Experiment 002 (0.05) is not the same as a stated-50% case (0.45). Jev distinguishes between "unmentioned" and "explicitly uncertain."

### H019 (Choice produces non-one-hot on probabilistic urn): REJECTED

Despite the urn having a clear probabilistic composition (50/30/20), Choice selected "red" with 100% probability. This continues the one-hot pattern from Phase 1.

Jev appears to treat Choice as answering "which is most likely?" rather than "what is the probability distribution?" — even when the state makes the distribution explicit. The probabilities field shows 1.0 on the modal option and 0.0 on all others.

This is a significant limitation: if you want a probability distribution from Jev, Choice may not deliver it.

### H020 (Score produces non-integer values): SUPPORTED

This is a major finding. After Phase 1 produced only exact integers (0.0, 1.0, 2.0), this experiment demonstrates Score DOES interpolate:
- 1.06 (vague_hint)
- 1.01 (weak_study)
- 2.92 (moderate)
- 4.68 (strong)
- 4.96 (overwhelming)

The interpolation is not just fractional — it produced values with two decimal places. This suggests Score is genuinely continuous in its output, contrary to Phase 1 observations.

### H021 (Noul/Choice/Score internal consistency): INCONCLUSIVE

Noul and Choice directions agreed in 6/7 batch calls. The sole disagreement was the fair coin case: noul=0.45 (slightly below 0.5) but Choice selected "heads." This could be due to:
1. Batch effects (see 006)
2. Noul jitter (the true value might be ~0.5, and 0.45 is within error range)
3. Choice being a "most likely" decision rather than a probabilistic one

n=1 per case prevents resolution. Needs Experiment 008 repeatability data.

### H022 (Confidence not uniformly 1.0): SUPPORTED

16/20 confidence values were below 1.0. The only 1.0 values were on extreme cases (100%/0% coins). This demonstrates that Jev's confidence field varies with evidential strength — a finding completely absent from Phase 1.

However, the range (0.79-0.99) is narrow. Even the weakest case (single small study, n=30, p=0.08) still had confidence 0.88. Jev seems reluctant to express low confidence.

## Conclusion

Experiment 007 established three important findings that contradict Phase 1 assumptions:

1. **Noul is capable of graded uncertainty** when the state explicitly quantifies probabilities. Values track ground truth with r=0.999 but with a slight conservative bias.

2. **Choice remains one-hot** even on explicitly probabilistic states. Jev appears to interpret Choice as "pick the best option" rather than "return a distribution."

3. **Score IS continuous** — it produces non-integer interpolated values. Phase 1's integer-only observations were an artifact of trivial states, not a limitation of Score.

4. **Confidence varies** with evidence strength, though the range is narrow (0.79-0.99).

## Limitations

- n=1 per case (no within-case repeats). Cannot distinguish signal from jitter.
- Coin and urn problems are synthetic with stated probabilities. Does not test whether Jev can infer probabilities from evidence; tests whether it can use explicitly stated probabilities.
- Score states are text descriptions with subjective mapping to rubric levels. The specific scores may vary with wording (Experiment 009).
- Batch effects could confound Noul-vs-Choice consistency checks (see findings from 006).
- The choice urn used "What color will the randomly drawn ball be?" which may be interpreted as picking the most likely. Different phrasings might produce partial distributions.
- The narrow confidence range (0.79-0.99) may overrepresent Jev's confidence. Truly high-uncertainty states were not tested.

## Next experiment

008 — Repeatability. The fair coin case showed an internal inconsistency (noul < 0.5 but Choice = heads). Repeating this case n >= 20 times will determine whether this is jitter or a genuine behavioral pattern. The Score interpolation finding also merits repeatability testing.