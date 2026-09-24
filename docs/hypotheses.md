# Hypotheses

Status values: SUPPORTED | REJECTED | INCONCLUSIVE | UNTESTED.

A SUPPORTED label means the named experiment(s) produced evidence consistent with the hypothesis **under the stated conditions**. It is not a universal proof.

---

## H001 — API connectivity

Hypothesis:

The TypeSafe HTTP API accepts authenticated requests using a Bearer `TYPESAFE_API_KEY` and returns a structured System One JSON body from `POST /v1/systemone`.

Status:

SUPPORTED (conditions: this account, 2026-09-21, model `jev-1.13.0`, one Noul question, two successful calls)

Experiment:

001

---

## H002 — Noul produces a yes-probability, not free-form text

Hypothesis:

Given a binary question with sufficiently clear evidence, Jev returns a structured `answers.<id>` object with `type: "noul"` and a numeric `noul` field in `[0, 1]`, rather than merely free-form text.

Status:

SUPPORTED (conditions: toy English sky-color states; 11 successful Noul calls across 001 and 002; values in {0.99, 0.01, 0.05})

Experiment:

001, 002 (schema/shape only; not a calibration study)

---

## H003 — Choice produces a distribution across mutually exclusive options

Hypothesis:

Jev's Choice primitive can produce a probability distribution across multiple mutually exclusive options.

Status:

SUPPORTED (conditions: 2026-09-21, `jev-1.13.0`, 3-way sky-color Choice, 9/9 answers had `choice` + `probabilities` + `confidence`)

Experiment:

003

---

## H008 — Choice tracks intended option on polar states

Hypothesis:

For a three-way sky-color Choice, a clearly blue state selects `blue` and a clearly grey state selects `grey`.

Status:

SUPPORTED (conditions: states `"The sky is blue."` and `"The sky is overcast and grey."`, n=3 each, labels 3/3 matching)

Experiment:

003

---

## H009 — Choice probabilities sum to 1

Hypothesis:

Each successful Choice answer's `probabilities` values sum to approximately 1.

Status:

SUPPORTED (conditions: 9 one-hot maps, sums exactly 1.0; does not test partial distributions)

Experiment:

003

---

## H004 — Score provides a usable numerical decision

Hypothesis:

Jev's Score primitive can consistently represent a numerical judgment on a defined scale.

Status:

SUPPORTED (conditions: 2026-09-21, `jev-1.13.0`, 3-level sky-blueness Score, 9/9 answers had numeric score + legend + probabilities + confidence)

Experiment:

004

---

## H010 — Score tracks ordered evidence

Hypothesis:

Under a three-level sky-blueness rubric (0 grey, 1 unstated, 2 blue), mean(clear_blue) > mean(ambiguous) > mean(clear_grey).

Status:

SUPPORTED (conditions: means 2.0 > 1.0 > 0.0, n=3 each, integer one-hot scores)

Experiment:

004

---

## H011 — Score probabilities sum to 1

Hypothesis:

Each successful Score answer's `probabilities` values sum to approximately 1.

Status:

SUPPORTED (conditions: 9 one-hot maps, sums exactly 1.0; between-level scores untested)

Experiment:

004

---

## H006 — Noul tracks evidence direction

Hypothesis:

For a fixed Noul question, a state with clear positive evidence yields a higher `noul` than a state with clear negative evidence.

Status:

SUPPORTED (conditions: 2026-09-21, `jev-1.13.0`, question `"Is the sky described as blue?"`, states `"The sky is blue."` vs `"The sky is overcast and grey."`, n=3 each; means 0.99 vs 0.01)

Experiment:

002

---

## H007 — Identical Noul repeats are stable

Hypothesis:

Repeating the same Noul request three times produces `noul` values whose within-case range is small relative to the gap between clear-yes and clear-no cases.

Status:

SUPPORTED (conditions: three sequential repeats per case, three toy states, within-case range 0.00 vs yes–no gap 0.98; n=3 is too small for a reliability claim)

Experiment:

002

---

## H005 — Response `model` field reports a versioned ID

Hypothesis:

When the request sends a pinned model ID, the response `model` field reports a versioned identifier such as `jev-1.13.0`.

Status:

SUPPORTED (conditions: request `model` was already `jev-1.13.0`; does not test alias resolution from `jev-latest`)

Experiment:

001

---

## H012 — Invalid bearer token returns 401

Hypothesis:

A System One request with `Authorization: Bearer` plus a non-real token returns HTTP 401.

Status:

SUPPORTED (conditions: 2026-09-21, placeholder token, HTTP 401, `detail.error_type=authentication_error`)

Experiment:

005

---

## H013 — Missing Authorization returns 401

Hypothesis:

A System One request with no `Authorization` header returns HTTP 401.

Status:

REJECTED (conditions: 2026-09-21, no Authorization header, observed HTTP **403**, `detail.error_type=authentication_error`)

Experiment:

005

---

## H014 — Missing `questions` returns 422

Hypothesis:

An otherwise documented body that omits `questions` returns HTTP 422.

Status:

SUPPORTED (conditions: valid key, body `{state, model}` only, HTTP 422, FastAPI-style `detail` list, loc `body.questions`)

Experiment:

005

---

## H015 — Mixed primitives batch

Hypothesis:

One System One request containing Noul, Choice, and Score returns a structured answer for each question id.

Status:

SUPPORTED (conditions: 2026-09-21, `jev-1.13.0`, one request with Noul+Choice+Score, HTTP 200, all three ids present)

Experiment:

006

---

## H016 — Batched answers match separate answers

Hypothesis:

For the trivial state `"The sky is blue."`, batched Noul/Choice/Score values equal the corresponding separate-call values.

Status:

REJECTED under strict equality (Noul 0.99 batched vs 1.0 separate; Choice and Score matched). Cause unseparated from Noul jitter.

Experiment:

006

---

## H017 — Batch uses fewer input tokens than the sum of separate calls

Hypothesis:

`usage.input_tokens` for one three-question request is less than the sum of three single-question requests on the same state.

Status:

SUPPORTED (conditions: batch 426 vs separate sum 954, ratio 2.24; n=1)

Experiment:

006

---

## H018 — Noul produces non-extreme values on probabilistic evidence

Hypothesis:

When the state describes a probabilistic scenario with a known numerical probability (e.g., biased coin), Noul produces values significantly different from the 0.01/0.99 extremes observed in Phase 1 toy states, and those values track the stated probability.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 5 non-tautological coin-flip cases, n=1 each; Noul range 0.08–0.84; mean abs error 0.05; Pearson r=0.999 vs ground truth; fair coin=0.45, not ~0.5)

Experiment:

007

---

## H019 — Choice produces non-one-hot distributions on probabilistic evidence

Hypothesis:

When the state describes a probabilistic urn with known non-deterministic composition, Choice produces a non-one-hot probability distribution across options.

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, urn 50/30/20, probabilities {red:1.0, blue:0.0, green:0.0}, confidence 0.99; one-hot only)

Experiment:

007

---

## H020 — Score produces non-integer (interpolated) values between rubric levels

Hypothesis:

When the state describes evidence whose strength falls between rubric levels, Score produces a fractional (non-integer) value rather than snapping to the nearest integer.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 5 graded evidence cases, n=1 each; all 5 scores non-integer: 1.06, 1.01, 2.92, 4.68, 4.96; Phase 1 integer-only observations were an artifact of trivial toy states)

Experiment:

007

---

## H021 — Noul/Choice/Score within a batch are internally consistent

Hypothesis:

For a given state in a single batch call, the direction indicated by Noul (>0.5 / <0.5) agrees with the Choice selection and Score direction.

Status:

INCONCLUSIVE (conditions: 2026-09-23, `jev-1.13.0`, 7 coin-flip batch calls; 6/7 consistent, 1/7 inconsistent: fair coin noul=0.45, slightly <0.5 but Choice selected "heads"; n=1 precludes distinguishing jitter from genuine inconsistency. Note: Experiment 008 established the fair-coin Noul central tendency is 0.46 — the 0.45 reading was a slightly-low draw — but the Noul-vs-Choice comparison still requires both primitives in the same batch, which was not tested in 008)

Experiment:

007

---

## H022 — Jev confidence values are not uniformly 1.0 on non-trivial evidence

Hypothesis:

On states with genuinely mixed or non-trivial evidence, Jev's Choice and Score confidence fields are below 1.0.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 20 confidence observations across Choice+Score; 16/20 <1.0, 4/20 =1.0 restricted to tautological cases; range 0.79–0.99; narrow range suggests Jev is reluctant to express low confidence)

Experiment:

007

---

## H023 — Repeated identical Noul requests are deterministic

Hypothesis:

Repeating the exact same Noul request produces identical Noul values.

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, fair-coin state, n=20 identical calls; observed 3 unique values {0.45, 0.46, 0.47}; range 0.02, stdev 0.003, mean 0.46; 0.46 appeared 18/20 times; jitter is real but tiny)

Experiment:

008

---

## H024 — Repeated identical Score requests are deterministic

Hypothesis:

Repeating the exact same Score request produces identical Score values.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, fair-coin state, n=20 identical calls; all 20 returned exactly 2.0, stdev 0.0; caveat: only tested at an obvious integer level, not graded evidence from 007)

Experiment:

008

---

## H025 — Confidence values are stable across identical repeats

Hypothesis:

Repeating the exact same request produces identical confidence values.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, fair-coin Score, n=20; confidence exactly 0.99 in all 20, stdev 0.0; Noul has no confidence field)

Experiment:

008

---

## H026 — Noul jitter is small relative to meaningful output differences

Hypothesis:

The run-to-run Noul jitter (output noise) is an order of magnitude smaller than the differences between meaningful evidence states (e.g., 30% vs 70% vs fair).

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, n=20; Noul jitter range 0.02 vs signal differences of 0.19+ between adjacent probability levels in 007; jitter is ~20x smaller than the fair-coin distinction from extreme cases)

Experiment:

008

---

## H027 — Semantically equivalent Noul wordings produce materially different values

Hypothesis:

Different phrasings of the same underlying question produce Noul values that differ by more than the ±0.02 jitter baseline.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 70/30 bag state, 4 wordings × 3 repeats; range across wording means = 0.207, ~10x the 0.02 jitter baseline; within-wording jitter ≤ 0.03. Literal/phrased-probability wordings returned 0.66–0.71 near ground truth 0.70; judgment-framed wordings "likely"/"evidence support" returned 0.84–0.87, inflated by ~0.14–0.17)

Experiment:

009

---

## H028 — Noul is wording-insensitive within the jitter baseline

Hypothesis:

Semantically equivalent wordings produce Noul values within the ±0.02 run-to-run jitter baseline.

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, 70/30 bag state, 4 wordings × 3 repeats; cross-wording spread 0.207 vastly exceeds the 0.02 jitter baseline)

Experiment:

009

---

## H029 — Appending irrelevant information changes the Noul value

Hypothesis:

Adding semantically-irrelevant context to a state shifts the Noul value beyond the ±0.02 jitter baseline.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 70/30 bag state, 0/1/5/20 irrelevant facts × 2 repeats; max drift 0.045, dose-dependent and monotonic; baseline 0.665 → plus_1 0.675 → plus_5 0.70 → plus_20 0.71. Caveat: drift moved toward ground truth 0.70, not away; modest magnitude vs 009's wording effect of 0.207)

Experiment:

010

---

## H030 — Appending irrelevant information does NOT change the Noul value

Hypothesis:

Adding semantically-irrelevant context leaves the Noul value within the ±0.02 jitter baseline.

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, 70/30 bag state, 0/1/5/20 irrelevant facts × 2 repeats; max drift 0.045 exceeds the 0.02 jitter baseline; drift monotonic with fact count)

Experiment:

010

---

## H031 — State representation format materially changes outputs

Hypothesis:

Representing identical facts as prose, JSON, or compact structured text produces materially different Jev outputs.

Status:

INCONCLUSIVE (conditions: 2026-09-23, `jev-1.13.0`, facts 7 red/3 blue, 3 formats × 3 batch calls; compact consistently lower (Noul 0.68 vs prose/json 0.70; Score 2.97 vs 3.00) but range ≤ 0.033, marginal vs the 0.02 jitter baseline; prose vs JSON essentially equivalent; Choice fully insensitive; magnitude far below 009's wording effect of 0.207)

Experiment:

011

---

## H032 — State representation format does not change outputs

Hypothesis:

Representing identical facts as prose, JSON, or compact structured text leaves outputs within the ±0.02 jitter baseline.

Status:

REJECTED under strict interpretation (conditions: 2026-09-23, `jev-1.13.0`, facts 7 red/3 blue, 3 formats × 3 batch calls; Noul range 0.023 and Score range 0.033 both marginally exceed the 0.02 baseline, driven by the compact form being consistently lower; deviation is small)

Experiment:

011

---

## H033 — JSON / structured representation uses fewer input tokens than prose

Hypothesis:

A structured (JSON or compact) state representation consumes fewer input tokens than the equivalent prose representation.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, facts 7 red/3 blue; prose 464 tokens, JSON 462, compact 458; savings ~1.3%; n=3 each, token counts fully deterministic)

Experiment:

011

---

## H034 — Noul moves toward 0.5 on contradictory state

Hypothesis:

Given internally contradictory state (two mutual exclusives), Jev's Noul value falls in an uncertain band near 0.5 rather than confidently picking a side.

Status:

INCONCLUSIVE (conditions: 2026-09-23, `jev-1.13.0`, 3 contradictory pairs × 3 repeats; coin 0.49 (uncertain) but sky 0.69 and direction 0.40 did NOT collapse to 0.5; Noul can lean toward or away from the stated side depending on the pair; Noul is not a reliable uncertainty signal on contradiction)

Experiment:

012

---

## H035 — Choice selects an explicit "uncertain" option on contradictory state

Hypothesis:

Given contradictory state, Jev's Choice selects an explicit "uncertain/conflicting" option when one is available.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 3 contradictory pairs × 3 repeats; "uncertain" selected in 9/9 calls, confidence 0.95–0.99; Jev reliably detects the contradiction when an "uncertain" option exists)

Experiment:

012

---

## H036 — Confidence is low on contradictory state

Hypothesis:

Given contradictory state, Jev's confidence is well below 1.0.

Status:

INCONCLUSIVE / PARTIAL (conditions: 2026-09-23, `jev-1.13.0`, 3 contradictory pairs × 3 repeats; Choice confidence HIGH 0.95–0.99 because Jev is confident it detected the contradiction, but Score confidence LOW 0.59–0.85; the blanket "low confidence on contradiction" prediction is too simple — confidence depends on the primitive and what it is confident about)

Experiment:

012

---

## H037 — Contradiction handling is consistent across repeats

Hypothesis:

Jev's response to the same contradictory state is stable across repeated calls.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 3 contradictory pairs × 3 repeats; Choice "uncertain" 3/3 in every case; Noul and Score very stable, e.g. direction Score exactly 3.82 × 3)

Experiment:

012

---

## H038 — "Unknown", "unmentioned", and "not enough information" are treated as equivalent

Hypothesis:

Jev returns the same output for explicitly-unknown, unmentioned, and explicitly-insufficient information states.

Status:

REJECTED for Noul / PARTIAL overall (conditions: 2026-09-23, `jev-1.13.0`, color question, 3 missing framings × 3 repeats; Choice and Score treat them identically — all "unknown", Score ~2.0 — but Noul distinguishes them: unknown 0.24, unmentioned 0.20, insufficient 0.29; Noul range 0.09 exceeds jitter)

Experiment:

013

---

## H039 — Jev distinguishes the missing-information framings

Hypothesis:

Jev returns materially different outputs for explicitly-unknown vs unmentioned vs explicitly-insufficient information.

Status:

PARTIAL / primitive-dependent (conditions: 2026-09-23, `jev-1.13.0`, color question, 3 missing framings × 3 repeats; Noul distinguishes them 0.20–0.29 (range 0.09 > jitter), but Choice (all "unknown") and Score (~2.0) do not)

Experiment:

013

---

## H040 — Missing information produces Noul near 0

Hypothesis:

A color question with missing color information produces a Noul value near 0, consistent with Phase 1's unmentioned case (0.05).

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, color question, 3 missing framings × 3 repeats; Noul means 0.20 (unmentioned), 0.24 (unknown), 0.29 (insufficient) — low but clearly above 0 and below 0.5; Phase 1's 0.05 likely reflected a "mixed/negative" phrasing rather than neutral absence; Score at ~2.0 "even chance" is the clearer uncertainty signal)

Experiment:

013

---

## H041 — Score produces non-integer (interpolated) values between rubric levels

Hypothesis:

When evidence falls between rubric levels, Jev's Score produces a fractional value rather than snapping to an integer.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 0-5 evidence-strength rubric, 6 graded cases × 3 repeats; 14/18 scores non-integer; values span a continuous range 0.00–4.87; decisively confirms Score interpolation, overturning the Phase 1 implication that Score is discrete)

Experiment:

014

---

## H042 — Score covers the full rubric scale

Hypothesis:

Score produces values across all rubric levels (0 through 5), not a subset.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 0-5 evidence-strength rubric, 6 graded cases × 3 repeats; scores span 0.00 to 4.87, monotonic across intended levels)

Experiment:

014

---

## H043 — Score ordering matches intended evidence strength

Hypothesis:

Score means increase monotonically with the intended evidence strength.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 0-5 evidence-strength rubric, 6 graded cases × 3 repeats; means strictly increase 0.003 → 0.79 → 1.00 → 1.99 → 4.11 → 4.87 with intended level)

Experiment:

014

---

## H044 — Fractional Score values are stable across repeats

Hypothesis:

Repeated identical Score calls on graded evidence produce materially similar fractional values.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, 0-5 evidence-strength rubric, 6 graded cases × 3 repeats; max within-case range 0.03 across all cases; fractional scores are reproducible, extending 008's determinism finding to graded cases)

Experiment:

014

---

## H045 — `jev-latest` resolves to a versioned model ID

Hypothesis:

Sending `model: "jev-latest"` returns a response whose `model` field is a concrete versioned ID, not the alias.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`; request `jev-latest` → response `model` = `jev-1.13.0`; HTTP 200; n=1)

Experiment:

015

---

## H046 — `jev-latest` produces the same output as the pinned `jev-1.13.0`

Hypothesis:

On an identical question, `jev-latest` and the pinned `jev-1.13.0` produce the same Noul output (within jitter).

Status:

SUPPORTED (conditions: 2026-09-23, 70/30 bag state, Noul "Will the selected ball be red?"; alias 0.66 vs pinned 0.67, diff 0.01 within the 0.02 jitter baseline; n=1 indicative)

Experiment:

015

---

## H047 — A single request can contain many questions and return all answers

Hypothesis:

A single System One request with up to 20 questions returns all answers with HTTP 200.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, urn state, batches of 3/5/10/20 Noul questions; all HTTP 200 with exact answer counts 3/3, 5/5, 10/10, 20/20)

Experiment:

016

---

## H048 — Input tokens scale sublinearly with question count

Hypothesis:

Batching many questions amortizes the shared state, so input tokens grow more slowly than question count.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, urn state; tokens/question fell 109 (3q) → 73 (5q) → 43.5 (10q) → 31 (20q); going 10→20 questions added only ~185 input tokens)

Experiment:

016

---

## H049 — Latency increases with question count

Hypothesis:

A batch with more questions takes longer than one with fewer.

Status:

REJECTED (conditions: 2026-09-23, `jev-1.13.0`, urn state; after a slow first call (833ms warmup), latency was flat ~317ms for 5, 10, AND 20 questions; consistent with the documented parallel evaluation of questions; latency confounded by network jitter per 008)

Experiment:

016

---

## H050 — All questions in a large batch are answered consistently

Hypothesis:

No questions are dropped or left unanswered in a large batch.

Status:

SUPPORTED (conditions: 2026-09-23, `jev-1.13.0`, urn state; every batch returned exactly the number of answers requested, up to 20/20)

Experiment:

016
