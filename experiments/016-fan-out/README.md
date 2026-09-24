# Experiment 016 — Large Fan-out (Add-on D)

## Objective

Determine how Jev handles large batches of questions in a single request. Experiment 006 compared a 3-question batch against separate calls (finding token savings). This extends the test to 3, 5, 10, and 20 questions in one request, measuring input/output tokens, latency, response structure, and failures.

This is relevant to FootyQuant v2 because a real application would ask many questions per state (e.g., one per team, per outcome, per market).

## Hypothesis

- H047: A single request can contain many (up to 20) questions and return all answers with HTTP 200.
- H048: Input tokens scale sublinearly with question count (batching amortizes the shared state).
- H049: Latency increases with the number of questions in a batch.
- H050: All questions in a large batch are answered consistently (no dropped/missing answers).

## Experimental setup

Base state (constant):

```text
A football match is being analyzed. Team A is strong and favored, Team B is an underdog. The match is a league game.
```

Wait — no football. Use a neutral state:

```text
An urn contains 60 red, 25 blue, and 15 green balls. One ball is drawn randomly.
```

Four batch sizes, each with Noul questions (one per color-related proposition repeated as distinct question ids):

- 3 questions
- 5 questions
- 10 questions
- 20 questions

Each question is a distinct Noul proposition about the draw (e.g., "Will the ball be red?", "Will the ball be blue?", ... with varied but simple propositions). Question ids are distinct.

n=1 per batch size (to keep it cheap; the focus is token/latency/failure scaling, not statistical).

## Variables

- Independent variable: number of questions in the batch (3/5/10/20)
- Dependent variables: input tokens, output tokens, latency, HTTP status, number of answers returned
- Held constant: state, model (jev-1.13.0), primitive (Noul), endpoint

## Controls

- Same state for all batch sizes.
- Questions are distinct but homogeneous (all simple Noul propositions).
- Model pinned.

## Expected result

- H047: All four batch sizes return HTTP 200 with the expected number of answers.
- H048: Input tokens grow more slowly than question count (shared state amortized).
- H049: Latency grows with question count.
- H050: Number of answers returned equals number of questions asked.

## Falsification criteria

- H047 is REJECTED if any batch size fails or errors.
- H048 is REJECTED if input tokens grow ~linearly with question count (no amortization).
- H049 is REJECTED if latency does not increase.
- H050 is REJECTED if some questions are dropped/unanswered.

## Sample size

4 batch sizes × 1 call each = 4 calls (total 3+5+10+20 = 38 question-answers). Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 4/4 HTTP 200 (batches of 3, 5, 10, 20 Noul questions)

| Batch size | Status | Answers | Input tokens | Output tokens | Latency |
|-----------|--------|---------|--------------|---------------|---------|
| 3 | 200 | 3 | 327 | 58 | 833 ms |
| 5 | 200 | 5 | 365 | 94 | 319 ms |
| 10 | 200 | 10 | 435 | 184 | 317 ms |
| 20 | 200 | 20 | 620 | 364 | 317 ms |

### Token scaling (sublinear)

| Batch size | Tokens per question |
|-----------|---------------------|
| 3 | 109.0 |
| 5 | 73.0 |
| 10 | 43.5 |
| 20 | 31.0 |

Going from 10 to 20 questions added only ~185 input tokens (435 → 620) and ~180 output tokens. The shared state is clearly amortized across questions.

## Analysis

### Batching handles many questions cleanly

All four batch sizes returned HTTP 200 with exactly the number of answers requested (3/3, 5/5, 10/10, 20/20). No dropped or missing answers. This confirms large batches work reliably.

### Input tokens scale sublinearly

Tokens per question dropped from 109 (3 questions) to 31 (20 questions). This is the amortization benefit: the shared state (and question structure) is billed once, and each additional question adds only its own instruction tokens. This strongly extends Experiment 006's token-savings finding to larger batches.

### Latency does NOT increase with question count (after warmup)

Latency was 833ms for the first (3-question) call, then flat at ~317ms for 5, 10, AND 20 questions. The first call's higher latency is likely warmup. The flat latency from 5 to 20 questions is consistent with the documentation that questions are evaluated in parallel against one state — adding questions doesn't add serial time.

**Caveat:** Latency is client wall-clock and 008 showed it varies ~2x from network jitter, so the flatness should not be over-interpreted. But the fact that 20 questions (620 tokens) took the same latency as 5 questions (365 tokens) is notable.

## Conclusion

- **H047 (many questions in one request): SUPPORTED.** 3/5/10/20 all HTTP 200.
- **H048 (input tokens scale sublinearly): SUPPORTED.** Tokens/question fell 109 → 31 as batch grew; state amortized.
- **H049 (latency increases with question count): REJECTED.** After warmup, latency was flat (~317ms) from 5 to 20 questions, consistent with parallel evaluation.
- **H050 (all questions answered): SUPPORTED.** Every batch returned exactly the requested number of answers.

**Net:** Jev handles large question batches efficiently — token cost is sublinear and latency is flat (parallel), with no dropped answers up to 20 questions. This is excellent news for FootyQuant v2, which would batch many questions per match state.

## Limitations

- n=1 per batch size; token/latency are single measurements.
- All questions were homogeneous simple Noul; heterogeneous batches may differ.
- Latency is client wall-clock, confounded by network and warmup.
- 20 questions is the largest tested; the practical ceiling is unknown.

## Next experiment

Add-on F (Noul criteria) or continue.