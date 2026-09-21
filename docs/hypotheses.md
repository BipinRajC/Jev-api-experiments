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

UNTESTED

Experiment:

003 (planned)

---

## H004 — Score provides a usable numerical decision

Hypothesis:

Jev's Score primitive can consistently represent a numerical judgment on a defined scale.

Status:

UNTESTED

Experiment:

004 (planned)

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
