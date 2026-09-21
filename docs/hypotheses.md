# Hypotheses

Status values: SUPPORTED | REJECTED | INCONCLUSIVE | UNTESTED.

A SUPPORTED label means the named experiment(s) produced evidence consistent with the hypothesis **under the stated conditions**. It is not a universal proof.

---

## H001 — API connectivity

Hypothesis:

The TypeSafe HTTP API accepts authenticated requests using a Bearer `TYPESAFE_API_KEY` and returns a structured System One JSON body from `POST /v1/systemone`.

Status:

UNTESTED

Experiment:

001

---

## H002 — Noul produces a yes-probability, not free-form text

Hypothesis:

Given a binary question with sufficiently clear evidence, Jev returns a structured `answers.<id>` object with `type: "noul"` and a numeric `noul` field in `[0, 1]`, rather than merely free-form text.

Status:

UNTESTED

Experiment:

001 (minimal single-question check; not a calibration study)

---

## H003 — Choice produces a distribution across mutually exclusive options

Hypothesis:

Jev's Choice primitive can produce a probability distribution across multiple mutually exclusive options.

Status:

UNTESTED

Experiment:

002 (planned)

---

## H004 — Score provides a usable numerical decision

Hypothesis:

Jev's Score primitive can consistently represent a numerical judgment on a defined scale.

Status:

UNTESTED

Experiment:

003 (planned)

---

## H005 — Response `model` field reports a versioned ID

Hypothesis:

When the request sends a pinned model ID or the `jev-latest` alias, the response `model` field reports a versioned identifier such as `jev-1.13.0`.

Status:

UNTESTED

Experiment:

001
