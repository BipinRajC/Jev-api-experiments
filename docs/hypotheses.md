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

INCONCLUSIVE (conditions: 2026-09-23, `jev-1.13.0`, 7 coin-flip batch calls; 6/7 consistent, 1/7 inconsistent: fair coin noul=0.45, slightly <0.5 but Choice selected "heads"; n=1 precludes distinguishing jitter from genuine inconsistency)

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
