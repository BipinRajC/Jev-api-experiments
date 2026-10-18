# Jev API Experiments — Research Handoff / Phase 2+

You are taking over an ongoing empirical research project investigating TypeSafe's Jev System One model.

Your role is **research engineer + experimentalist**, not product/demo generator.

Repository:

`/home/bipin/jev-api-experiments`

GitHub:

`https://github.com/BipinRajC/Jev-api-experiments`

Branch:

`main`

The eventual goal is to determine whether learnings from Jev can inform a future FootyQuant v2 system for football analysis and betting-market research.

**Do NOT build FootyQuant v2 now.**

This repository exists specifically to understand Jev before making architectural assumptions.

---

# 1. CORE RESEARCH PHILOSOPHY

The central principle is:

> **We don't build around assumptions. We build experiments that kill assumptions.**

Our research loop is:

```text
Hypothesis
    ↓
Experimental design
    ↓
Controlled test
    ↓
Raw observations
    ↓
Quantitative analysis
    ↓
Conclusion
    ↓
Next hypothesis
```

Use only these hypothesis statuses:

* `SUPPORTED`
* `REJECTED`
* `INCONCLUSIVE`
* `UNTESTED`

Never claim a hypothesis has been universally "proven".

Every conclusion must specify:

* what was tested
* under what conditions
* sample size
* observed result
* limitations

A finding that holds on a toy example should NOT automatically be generalized to Jev as a whole.

---

# 2. VERY IMPORTANT: RESEARCH BEFORE IMPLEMENTATION

Before doing anything:

1. Inspect the current repository.
2. Read:

   * `README.md`
   * `docs/hypotheses.md`
   * `docs/findings.md`
   * `docs/api-notes.md`
3. Inspect all experiment READMEs from 001 onward.
4. Inspect the raw results under `results/`.
5. Inspect the existing test suite.
6. Understand the existing client/parsers before modifying them.
7. Do NOT rerun completed experiments unless:

   * raw evidence is missing
   * the implementation was demonstrably broken
   * a later result directly contradicts an earlier finding and requires replication

Do not destroy or rewrite previous experimental evidence.

Previous results are part of the research record.

---

# 3. SECURITY

The TypeSafe API key exists locally in:

```text
.env
```

under:

```text
TYPESAFE_API_KEY
```

NEVER:

* print the API key
* read it into chat output
* hardcode it
* commit it
* put it in a result artifact
* put it in a README
* include it in a Git diff
* ask the user to paste it

Use the existing environment-loading mechanism.

`.gitignore` must continue to ignore:

```text
.env
*.env
.venv/
__pycache__/
*.pyc
```

Before every commit:

1. inspect `git diff`
2. inspect `git status`
3. scan for secrets
4. ensure `.env` is not tracked

Do NOT push to GitHub unless explicitly instructed by the user.

---

# 4. CURRENT API CONFIGURATION

The current direct TypeSafe API configuration is:

Endpoint:

```text
POST https://api.typesafe.ai/v1/systemone
```

Authentication:

```text
Authorization: Bearer $TYPESAFE_API_KEY
```

Header:

```text
Content-Type: application/json
```

Pinned model:

```text
jev-1.13.0
```

Do NOT silently replace this with:

```text
jev-latest
```

unless an experiment is specifically testing alias resolution.

Request structure:

```json
{
  "state": "...",
  "model": "jev-1.13.0",
  "questions": {
    "...": {}
  }
}
```

Supported decision primitives currently being investigated:

* Noul
* Choice
* Score

Current documented pricing:

```text
$0.042 / 1M input tokens
output free
```

Current user credit:

```text
$5 promotional monthly credit
expires October 19
```

Treat this as a limited research budget.

Context/rate-limit information recorded from the previous phase:

```text
Context: 64k per request
State + longest question: 32k
Documented rate limit: 250k tokens/s
Documented rate limit: 1200 rpm
```

These may change. If an experiment depends on them, verify current official documentation first.

Prefer:

```text
https://docs.typesafe.ai/
```

over blog posts for API behavior.

---

# 5. EXISTING CODEBASE

Current relevant structure:

```text
src/
    jev_client.py
    schemas.py
    noul.py
    choice.py
    score.py
    utils.py

experiments/
    001-*/
    002-*/
    ...

results/
    001-*/
    002-*/
    ...

docs/
    hypotheses.md
    findings.md
    api-notes.md

tests/
```

The existing client uses:

* `httpx`
* `pydantic`
* `python-dotenv`
* `pytest`

Keep dependencies minimal.

Do not introduce a large framework.

---

# 6. EXPERIMENT ARTIFACT STANDARD

Every experiment must contain:

```text
experiments/XXX-name/
    README.md
    experiment.py
```

The README must contain:

```text
# Experiment XXX — Name

## Objective

## Hypothesis

## Experimental setup

## Variables

## Controls

## Expected result

## Falsification criteria

## Results

## Analysis

## Conclusion

## Limitations

## Next experiment
```

Every experiment must save raw evidence under:

```text
results/XXX-name/
```

Each run should preserve, where available:

* timestamp
* experiment ID
* model requested
* model returned
* request ID
* HTTP status
* latency
* input tokens
* output tokens
* estimated cost
* redacted headers
* raw API JSON
* experiment parameters

Never store credentials.

---

# 7. PHASE 1: COMPLETED

Experiments 001–006 are complete.

Do not redo them unnecessarily.

Date:

`2026-09-21`

Model:

`jev-1.13.0`

Provider:

Direct TypeSafe API.

---

## Experiment 001 — API sanity

Observed:

* 2/2 HTTP 200
* trivial Noul returned `0.99`
* TypeSafe request ID header is:

```text
x-typesafe-request-id
```

* client RTT approximately 0.88–1.09 seconds
* upstream service time approximately 124 ms
* token usage approximately 278 input / 23 output

Important implication:

There appears to be a meaningful difference between client-observed latency and upstream service time.

Do not assume all latency is Jev inference latency.

---

## Experiment 002 — Noul

Three states × three repeats.

Observed:

```text
clear_yes:
0.99 ×3

clear_no:
0.01 ×3

ambiguous:
0.05 ×3
```

Important:

The ambiguous case did NOT produce approximately 0.5.

It produced approximately 0.05.

This is important evidence.

Do not reinterpret it as "Jev is calibrated" or "Jev is uncalibrated" from this alone.

---

## Experiment 003 — Choice

Three-way Choice:

```text
blue
grey
unspecified
```

Observed:

* 9/9 one-hot
* confidence 1.0
* probabilities sum to 1
* ambiguous case consistently selected `unspecified`

Also:

**JSON probability key order is not stable.**

Do not rely on key order.

---

## Experiment 004 — Score

Three-level score:

```text
0 = grey
1 = unstated
2 = blue
```

Observed:

* 9/9 integer one-hot
* confidence 1.0

Observed:

```text
clear_blue → 2
ambiguous → 1
clear_grey → 0
```

Important:

**No non-integer/between-level scores were observed.**

Do not claim that Score interpolates merely because documentation might suggest it can.

We need an experiment specifically designed to test this.

---

## Experiment 005 — Error handling

Observed:

```text
invalid Bearer token → 401
missing Authorization → 403
missing questions → 422
unknown model → 400
```

Important:

Official error documentation should not automatically be treated as identical to actual observed behavior.

---

## Experiment 006 — Batch vs separate

Compared:

```text
one request:
Noul + Choice + Score
```

against:

```text
three separate requests
```

Observed:

```text
Batch:
426 input tokens
77 output tokens
894 ms latency

Separate:
954 input tokens
84 output tokens
956 ms total latency
```

Decision outputs:

```text
Batch Noul = 0.99
Separate Noul = 1.0

Choice = same
Score = same
```

Therefore the strict hypothesis:

> Batch answers are exactly identical to separate answers

was rejected.

However:

**This does NOT establish that batching causes different decisions.**

There is insufficient evidence to separate batching effects from ordinary variability/jitter.

What IS supported:

> Batching can reduce repeated input-token overhead in the tested case.

---

# 8. CURRENT HYPOTHESIS LEDGER

The existing ledger contains:

```text
H001 Direct API + Bearer key returns System One JSON
SUPPORTED

H002 Noul is structured noul in [0,1], not prose
SUPPORTED

H003 Choice returns a distribution
SUPPORTED
(one-hot only so far)

H004 Score returns numeric judgment on rubric
SUPPORTED
(integer outputs only so far)

H005 Response model is versioned ID
SUPPORTED

H006 Noul higher on clear-yes than clear-no
SUPPORTED

H007 3 identical Noul repeats stable
SUPPORTED
(n=3)

H008 Choice polar labels match
SUPPORTED

H009 Choice probabilities sum to 1
SUPPORTED
(one-hot cases)

H010 Score ordered blue > unstated > grey
SUPPORTED

H011 Score probabilities sum to 1
SUPPORTED
(one-hot cases)

H012 Invalid token → 401
SUPPORTED

H013 Missing Authorization → 401
REJECTED
(actual response was 403)

H014 Missing questions → 422
SUPPORTED

H015 Mixed primitives in one request
SUPPORTED

H016 Batch answers == separate answers
REJECTED

H017 Batch input tokens < sum of separate
SUPPORTED
(n=1 comparison)
```

Preserve these findings.

Do not retroactively alter them unless new evidence genuinely requires replication or revision.

---

# 9. WHY PHASE 2 EXISTS

Phase 1 was intentionally simple.

It established:

* API connectivity
* schema
* primitive types
* basic error handling
* basic batching behavior

But it used extremely easy / tautological examples.

The most important limitation discovered was:

> Jev often produced highly confident one-hot answers on simple toy problems.

That means we have NOT yet demonstrated that:

* Choice produces useful probability distributions
* Score produces continuous values
* confidence is meaningful
* probabilities respond smoothly to evidence
* outputs are calibrated
* outputs are robust to wording
* irrelevant information is ignored
* structured state is interpreted consistently
* conflicting evidence is handled sensibly

Phase 2 exists specifically to attack these assumptions.

---

# 10. PHASE 2 RESEARCH PROGRAM

Phase 2 should investigate Jev's decision behavior without football.

The planned sequence is:

```text
007 — Non-trivial / mixed evidence
008 — Repeatability
009 — Wording sensitivity
010 — Irrelevant information
011 — Structured vs unstructured state
012 — Conflicting evidence
013 — Missing information
014 — Score interpolation / scale behavior
```

Do these in sequence unless a previous experiment gives a strong reason to change the design.

If you believe an experiment should be modified, explain why in its README.

Do not silently change the research question.

---

# 11. EXPERIMENT 007 — MIXED / NON-TRIVIAL EVIDENCE

This is the immediate next experiment.

## Objective

Move beyond tautological examples and test whether Jev produces partial distributions or non-one-hot outputs when the evidence is genuinely mixed.

We need examples where the correct answer is not obvious.

Do NOT use football.

Good candidates:

### Noul

Use synthetic probability descriptions where the answer has a known probability.

For example:

```text
A fair coin is flipped once.
Will it land heads?
```

Expected conceptual probability:

0.5

But be careful:

The goal is not to assume Jev must return exactly 0.5.

The goal is to observe what it does.

Then use:

```text
A biased coin lands heads 70% of the time.
Will the next flip be heads?
```

and perhaps:

```text
A biased coin lands heads 30% of the time.
Will the next flip be heads?
```

These are useful because the underlying probabilities are known.

### Choice

Create a three-way synthetic scenario where evidence supports multiple alternatives.

For example, a probabilistic urn:

```text
An urn contains:
50% red
30% blue
20% green

One ball is drawn at random.

What color is most likely?
```

But distinguish between:

1. probability implied by the state
2. which option is most likely

If Choice only returns one-hot probability distributions, that itself is a finding.

### Score

Create a genuinely graded question.

Do not simply label:

```text
0 = low
1 = medium
2 = high
```

and then state "medium" explicitly.

Instead provide evidence that should reasonably correspond to an intermediate judgment.

For example, define a scale:

```text
0 = no evidence
1 = weak evidence
2 = moderate evidence
3 = strong evidence
4 = overwhelming evidence
```

Then give a state containing genuinely moderate evidence.

The question should require the model to infer the score.

Do NOT tell it the answer.

## Important

Do not create a giant experiment.

Keep the number of calls modest because credits are limited.

But include enough repeated cases to identify obvious patterns.

---

# 12. EXPERIMENT 008 — REPEATABILITY

Phase 1 only used n=3 for repeated Noul calls.

Experiment 006 also showed a small discrepancy:

```text batch Noul = 0.99
separate Noul = 1.0
```

We therefore need a better measurement.

Use the **exact same request** repeatedly.

Target:

```text n >= 20
```

if cost is trivial.

Prefer one representative Noul case initially.

Measure:

* min
* max
* mean
* median
* standard deviation
* range
* unique output values
* frequency of each output
* confidence values if present
* latency distribution
* token usage

Then answer:

> Does repeated identical input produce deterministic outputs?

Do not simply say "yes" because all outputs are close.

Report the actual distribution.

If the answer is always 0.99, that's useful.

If it alternates between 0.99 and 1.0, that's also useful.

If there are larger variations, that's even more interesting.

---

# 13. EXPERIMENT 009 — WORDING SENSITIVITY

Objective:

Determine whether semantically equivalent questions produce materially different outputs.

Hold everything constant except the question wording.

Example:

State:

```text
A bag contains 70 red balls and 30 blue balls.
One ball is selected randomly.
```

Questions:

```text
Will the selected ball be red?

Is the selected ball likely to be red?

What is the chance that the selected ball is red?

Does the evidence support the ball being red?
```

Important:

Do NOT change the state.

Do NOT change the model.

Do NOT change the primitive.

Do NOT change the options/rubric.

Only wording changes.

Measure:

* probability
* confidence
* selected option
* score
* drift between formulations

If outputs differ, quantify the difference.

Do not automatically label variation as bad.

The question is:

> How sensitive is Jev to semantically equivalent wording?

---

# 14. EXPERIMENT 010 — IRRELEVANT INFORMATION

Objective:

Test whether irrelevant state information changes the decision.

Base state:

```text
A box contains 70 red balls and 30 blue balls.
One ball is selected randomly.
```

Question:

```text
Will the selected ball be red?
```

Then append irrelevant information:

```text
The experiment is being conducted on a Tuesday.
The observer is wearing a blue shirt.
The room temperature is 22°C.
The box is sitting on a wooden table.
```

The actual relevant evidence remains unchanged.

Create increasing levels:

```text
baseline
+ 1 irrelevant fact
+ 5 irrelevant facts
+ 20 irrelevant facts
```

Keep the relevant information identical.

Measure output drift.

This tests whether context pollution occurs.

Do not assume more context is harmful or harmless.

Measure it.

---

# 15. EXPERIMENT 011 — STRUCTURED VS UNSTRUCTURED STATE

Objective:

Determine whether Jev behaves differently when identical information is represented as:

### Format A — prose

```text
Arun has 7 red balls and 3 blue balls.
```

### Format B — JSON

```json
{
  "red": 7,
  "blue": 3
}
```

### Format C — perhaps a compact structured representation

Only if supported by the API and sensible.

The actual facts must remain identical.

Hold constant:

* question
* model
* primitive
* request structure

Measure:

* decision
* probability
* confidence
* latency
* token usage

Do not conclude that JSON is "better" simply because it uses fewer tokens.

This experiment is about behavioral equivalence and sensitivity.

---

# 16. EXPERIMENT 012 — CONFLICTING EVIDENCE

Objective:

Determine how Jev handles internally contradictory state.

Example:

```text
Statement 1:
The sky is blue.

Statement 2:
The sky is grey.

Statement 3:
The observation was made during the same time period.
```

Ask:

### Noul

```text
Is the sky blue?
```

### Choice

```text
blue
grey
uncertain
```

### Score

Use a predefined uncertainty/evidence rubric.

The important thing is not to tell Jev what it should conclude.

Measure:

* probability distribution
* confidence
* selected option
* score
* consistency across repeated runs

This experiment may reveal whether Jev:

* picks one side
* distributes probability
* recognizes uncertainty
* becomes highly confident despite contradiction

Any of those results are informative.

---

# 17. EXPERIMENT 013 — MISSING INFORMATION

Objective:

Distinguish:

```text
explicit uncertainty
```

from:

```text
absence of information
```

Test cases such as:

### Case A

State explicitly says:

```text
The color is unknown.
```

### Case B

State contains no color information.

### Case C

State says:

```text
There is not enough information to determine the color.
```

Ask the same Noul/Choice question.

This should be compared against the Phase 1 observation:

```text
Noul ambiguous case = 0.05
Choice = unspecified
```

The purpose is to understand whether Jev treats:

* unknown
* unmentioned
* explicitly uncertain

as equivalent or different states.

Do not assume they should be equivalent.

---

# 18. EXPERIMENT 014 — SCORE INTERPOLATION

Phase 1 produced:

```text
0
1
2
```

as exact integer outputs.

We need to test whether Score can actually produce intermediate values.

Do NOT simply rerun the same experiment.

Construct a scale such as:

```text
0 = no evidence
1 = very weak evidence
2 = weak evidence
3 = moderate evidence
4 = strong evidence
5 = overwhelming evidence
```

Then construct several states representing:

* very weak
* weak
* moderate
* strong
* overwhelming

without explicitly naming the target score.

Measure whether outputs are:

```text
integer only
```

or:

```text
fractional / interpolated
```

If fractional scores never appear, report that accurately.

Do NOT infer from documentation that interpolation must occur.

---

# 19. OPTIONAL PHASE 2 ADD-ONS

After 007–014, consider these additional experiments.

Do not automatically run all of them.

Prioritize based on what Phase 2 reveals.

### A. `jev-latest` alias resolution

Determine what exact model version `jev-latest` resolves to.

Do not mix this with the pinned experiments.

### B. HTTP 429

Determine actual rate-limit behavior safely.

Do NOT intentionally hammer the API.

Use a controlled method if possible.

### C. HTTP 529

Investigate only if safely reproducible or documented.

Do not manufacture an outage.

### D. Large fan-out

Compare:

```text
3 questions
5 questions
10 questions
20 questions
```

in one request.

Measure:

* input tokens
* output tokens
* latency
* response structure
* failures
* consistency

This extends Experiment 006.

### E. Cost verification

Compare:

```text usage.input_tokens × published price
```

against actual account usage if the console exposes sufficient data.

Do not assume the console accounting mechanism.

### F. Noul criteria behavior

Compare:

```text criteria.true / criteria.false
```

against instruction-only formulations.

Determine whether criteria materially affect outputs.

---

# 20. PHASE 3 — CALIBRATION

Do NOT start Phase 3 until Phase 2 is sufficiently understood.

Phase 3 is where the research becomes much more quantitative.

The core question:

> When Jev outputs a probability, does that probability correspond to observed frequency?

For example:

If Jev repeatedly outputs approximately 0.70 across a set of events, do approximately 70% of those events actually occur?

This requires many independent examples.

Do NOT attempt to answer calibration using:

```text n=3
n=9
```

toy examples.

We need a meaningful sample.

---

# 21. SYNTHETIC CALIBRATION FIRST

Before football, create synthetic problems with known probabilities.

Examples:

```text
50%
60%
70%
80%
90%
```

Use randomized instances where possible.

For each prediction:

* generate the known probability
* ask Jev
* record Jev probability
* sample the actual outcome according to the known probability
* repeat many times

Then calculate:

* Brier score
* log loss
* reliability
* calibration error
* confidence vs accuracy

This gives us a controlled environment.

---

# 22. THEN REAL-WORLD DECISION CALIBRATION

Only after synthetic calibration should we consider real-world domains.

And eventually:

```text
football
```

But football requires strict prevention of data leakage.

---

# 23. PHASE 4 — FOOTBALL

Do NOT enter Phase 4 automatically.

It is a separate research phase.

The eventual question is not:

> "Can Jev tell me who will win?"

It is:

> "Does Jev provide useful probabilistic information for football outcomes beyond reasonable baselines?"

The eventual architecture may look like:

```text
Historical football data
        ↓
Feature engineering
        ↓
Baseline statistical models
        ↓
Jev structured decisions
        ↓
Probability comparison
        ↓
Calibration
        ↓
Market comparison
        ↓
Evaluation
```

But this architecture is NOT assumed to be correct.

We test it.

---

# 24. FOOTBALL DATA-LEAKAGE RULES

When we eventually reach football, every prediction must have:

```text
prediction_timestamp
information_cutoff
match_date
data_sources
model_version
jev_version
market_timestamp
```

Only information available at the defined information cutoff may be used.

Never accidentally include:

* post-match information
* future injuries
* later lineup announcements
* closing odds when evaluating an earlier timestamp
* post-match statistics

The historical experiment must reproduce what could actually have been known at prediction time.

---

# 25. EVENTUAL BASELINES

When football research starts, compare Jev against reasonable baselines.

Potential baselines:

* bookmaker implied probability
* Elo
* Poisson
* xG-based model
* logistic regression
* tree-based model
* other appropriate statistical models

Do not assume Jev beats any of them.

Evaluate objectively.

Useful metrics may include:

### Classification

* accuracy
* precision/recall where appropriate

### Probabilistic

* Brier score
* log loss
* calibration error
* reliability diagrams

### Market-related

* closing-line value
* expected value
* ROI

But ROI should be treated carefully because it is highly sensitive to staking rules, sample size, odds, and variance.

---

# 26. VERY IMPORTANT: DO NOT CONFLATE THESE CONCEPTS

Throughout the research keep these separate:

```text
Probability
Confidence
Accuracy
Calibration
Expected value
Market implied probability
Profitability
```

They are not interchangeable.

For example:

```text
Jev confidence = 0.95
```

does NOT automatically mean:

```text
95% probability of being correct
```

And:

```text
Jev probability = 0.70
```

does NOT automatically imply:

```text
profitable bet
```

A betting opportunity requires comparison against market price and appropriate evaluation.

---

# 27. RESEARCH QUALITY REQUIREMENTS

For every experiment ask:

### What is the independent variable?

### What is the dependent variable?

### What is held constant?

### What is the control?

### What would falsify the hypothesis?

### Is the sample size adequate?

### Is there a confounder?

### Are we accidentally testing multiple things?

### Could the observed result be ordinary variance?

### Can the result be reproduced?

If an experiment is poorly designed, stop and redesign it rather than generating misleading data.

---

# 28. STATISTICAL DISCIPLINE

Do not overinterpret tiny samples.

For n=3:

Say:

> "Observed across 3 repetitions."

Do not say:

> "Jev is deterministic."

For n=20:

Say:

> "Observed variation across 20 repetitions."

Do not claim universal determinism.

For larger experiments, use appropriate statistical summaries.

Where useful calculate:

* mean
* median
* standard deviation
* min/max
* range
* quantiles
* confidence intervals

Do not add statistical machinery merely for appearance.

---

# 29. RAW DATA > NARRATIVE

Never throw away raw results.

If a result is surprising:

1. preserve raw JSON
2. preserve exact input
3. preserve experiment parameters
4. reproduce
5. analyze
6. update findings only afterward

The repository should make it possible for someone else to inspect how a conclusion was reached.

---

# 30. DOCUMENTATION DISCIPLINE

After each experiment:

1. Update the experiment README.
2. Update `docs/hypotheses.md`.
3. Update `docs/findings.md` only with supported observations.
4. Update `docs/api-notes.md` only if the experiment establishes API behavior.
5. Run the test suite.
6. Review git diff.
7. Check for secrets.
8. Make a small logical commit.

Suggested commit pattern:

```text
feat: add experiment 007 mixed evidence
docs: record experiment 007 findings
```

Do not combine many unrelated experiments into one huge commit.

---

# 31. WHEN TO STOP

Do not blindly execute the entire roadmap if evidence shows that an experiment is no longer meaningful.

For example:

If Experiment 007 reveals a major unexpected behavior, stop and investigate it before proceeding to 008.

The experiment sequence is a guide, not a script.

The goal is **knowledge**, not reaching Experiment 014 as quickly as possible.

However, avoid getting stuck endlessly polishing one experiment.

Prefer:

```text
small experiment
→ clear result
→ document
→ next experiment
```

---

# 32. SPEED VS QUALITY

I want these experiments done efficiently.

Do not spend 20 minutes building an elaborate abstraction for a 10-line experiment.

Do not repeatedly research the same documentation.

Do not over-engineer the experiment runner.

Use the existing client and helpers where appropriate.

But do NOT sacrifice:

* raw evidence
* reproducibility
* hypothesis clarity
* security
* correct statistical interpretation

The goal is:

> **fast, clean, reproducible experimentation.**

---

# 33. CURRENT IMMEDIATE TASK

Start by inspecting the repository.

Then:

### Step 1

Understand Experiments 001–006 and existing code.

### Step 2

Confirm the current TypeSafe API behavior from official documentation where necessary.

### Step 3

Design Experiment 007.

Before writing code, create:

```text
experiments/007-mixed-evidence/README.md
```

with:

* objective
* hypothesis
* experimental design
* controls
* expected results
* falsification criteria
* sample size
* variables

### Step 4

Implement the smallest clean experiment.

### Step 5

Run it using the existing local API credentials.

Do not expose the key.

### Step 6

Save raw JSON results.

### Step 7

Perform quantitative analysis.

### Step 8

Determine:

```text
SUPPORTED
REJECTED
INCONCLUSIVE
```

### Step 9

Update the hypothesis ledger and findings.

### Step 10

Run:

```text
.venv/bin/python -m pytest
```

### Step 11

Inspect:

```text
git diff
git status
```

### Step 12

Make a small logical commit.

### Step 13

STOP.

Do not automatically implement Experiment 008 in the same run unless explicitly instructed.

---

# 34. FINAL GUIDING PRINCIPLE

The eventual goal is not to prove that Jev is amazing.

The goal is not to prove that Jev is useless.

The goal is to determine:

> **Where does Jev actually work, where does it fail, and under what conditions can its outputs be trusted or usefully combined with other methods?**

If Jev turns out to be excellent for football, the experiments should demonstrate that.

If Jev turns out to be poor for football, the experiments should demonstrate that too.

If the answer is mixed, preserve the nuance.

The future FootyQuant v2 architecture should emerge from these findings, rather than the research being designed to justify a predetermined FootyQuant architecture.

**Research first. Product later. Evidence over assumptions.**
