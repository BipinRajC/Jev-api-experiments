# Experiment 008 — Repeatability

## Objective

Measure whether Jev produces deterministic outputs when the exact same request is repeated many times. Phase 1 (Experiment 002) used only n=3 per case and found range 0.00 (all identical). Experiment 006 showed a 0.01 discrepancy (0.99 vs 1.0). Experiment 007 found Noul values tracking probabilities but with potential jitter. This experiment measures the actual output distribution under repeated identical input.

## Hypothesis

- H023: Repeated identical Noul requests produce identical (deterministic) Noul values.
- H024: Repeated identical Score requests produce identical (deterministic) Score values.
- H025: Confidence values are stable across identical repeats.
- H026: Noul jitter (if present) is small relative to the within-question signal.

## Experimental setup

Use the fair-coin state from Experiment 007:

```text
A biased coin lands heads 50% of the time and tails 50% of the time. The coin is flipped once.
```

This is the most interesting case because:
- Experiment 007 produced noul=0.45 (not exactly 0.5)
- It is the most ambiguous case, so if Jev has output jitter, this is where it should appear
- It tests whether 0.45 is a stable value or an artifact of a single draw

Two question sets:

### Noul repeatability
```json
{
  "heads_noul": {
    "type": "noul",
    "instructions": "Will the next flip land heads?"
  }
}
```

### Score repeatability
```json
{
  "coin_score": {
    "type": "score",
    "instructions": "How likely is it that the coin lands heads?",
    "criteria": [
      {"score": 0, "label": "impossible"},
      {"score": 1, "label": "unlikely"},
      {"score": 2, "label": "even odds"},
      {"score": 3, "label": "likely"},
      {"score": 4, "label": "certain"}
    ]
  }
}
```

Each repeated n=20 times. Interleave Noul and Score calls to avoid order/path effects.

## Variables

- Independent variable: repetition index (1..20)
- Dependent variables: Noul value, Score value, Score confidence, latency, token usage
- Held constant: state, question wording, model (jev-1.13.0), endpoint

## Controls

- Identical state and question wording across all repeats
- Model pinned to jev-1.13.0
- Interleaved ordering (Noul, Score, Noul, Score, ...) to avoid serial bias

## Expected result

- If deterministic: all 20 Noul values identical, all 20 Score values identical.
- If jittery: a distribution of values around some central tendency.

## Falsification criteria

- H023 is REJECTED if Noul values differ across repeats.
- H024 is REJECTED if Score values differ across repeats.
- H025 is REJECTED if confidence varies across identical repeats.
- H026 is REJECTED if the Noul spread exceeds ~0.1 (i.e., jitter is large relative to the 0.5-vs-0.45 signal).

## Sample size

20 Noul calls + 20 Score calls = 40 calls total. Cost is trivial (< $0.001).

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 40/40 HTTP 200 (20 Noul + 20 Score)
**Cost:** ~$0.000592 (14,100 input tokens)

### Noul repeatability (fair coin, n=20)

| Statistic | Value |
|-----------|-------|
| min | 0.45 |
| max | 0.47 |
| mean | 0.46 |
| median | 0.46 |
| stdev | 0.0032 |
| range | 0.02 |
| unique values | 3 ({0.45, 0.46, 0.47}) |

Frequency: 0.45 → 1, **0.46 → 18**, 0.47 → 1

### Score repeatability (n=20)

| Statistic | Value |
|-----------|-------|
| min / max / mean / median | all 2.0 |
| stdev | 0.0 |
| range | 0.0 |
| unique values | 1 ({2.0}) |

Score confidence: constant 0.99 across all 20 (stdev 0.0).

### Latency (highly variable)

| Metric | Noul | Score |
|--------|------|-------|
| min | 400.6 ms | 422.6 ms |
| max | 875.7 ms | 779.3 ms |
| mean | 493.4 ms | 505.1 ms |
| median | 451.9 ms | 466.1 ms |
| stdev | 114.4 ms | 91.3 ms |
| range | 475.1 ms | 356.7 ms |

Latency varied ~2x around the median (400–876 ms). This is large relative to the Noul jitter magnitude.

### Token usage (deterministic)

- Noul: constant 301 input tokens across all 20 (stdev 0.0)
- Score: constant 404 input tokens across all 20

## Analysis

### Noul is NOT deterministic, but jitter is tiny

Across 20 identical requests, Noul returned 3 distinct values: 0.45, 0.46, 0.47. The dominant value (0.46) appeared 18/20 times. The jitter is ±0.01 around the mean 0.46.

This confirms the Experiment 006 observation (0.99 vs 1.0) is real: Noul has output jitter. But the magnitude here is very small (range 0.02, stdev 0.003).

**Important calibration correction:** Experiment 007 reported fair-coin noul=0.45 in a single draw. This experiment shows the central tendency is 0.46, and 0.45 was a slightly-low single sample. The true value is ~0.46, not exactly 0.5 — Jev understates uncertainty at 50% by ~0.04.

### Score IS deterministic (at least at integer levels)

All 20 Score calls returned exactly 2.0 with confidence exactly 0.99. Score output was fully deterministic on this state.

**Caveat:** This test used the fair-coin state, where the "correct" answer (2 = even odds) is unambiguous. Experiment 007's fractional scores (2.92, 4.68) involved genuinely graded evidence; those may or may not be equally deterministic. The integer result here does not prove Score is always deterministic — only that it is stable when the answer is an obvious integer.

### Confidence is stable for Score

Score confidence was exactly 0.99 in all 20 calls (stdev 0.0). So the confidence field is deterministic here, matching the deterministic Score.

### Latency jitter dominates the experiment

Latency ranged 400–876 ms (Noul) — a ~2x spread. This is far larger than the Noul output jitter. For any production use, latency variability (not output variability) is the more significant practical concern.

### Token usage is fully deterministic

Input tokens were constant (301 Noul, 404 Score) across all repeats. Token accounting has no jitter.

## Conclusion

- **H023 (Noul deterministic): REJECTED.** Noul jitters, but only by ±0.01 around a stable central value. Mean 0.46, stdev 0.003, range 0.02 across n=20.
- **H024 (Score deterministic): SUPPORTED** for this state. All 20 identical (2.0, confidence 0.99). Does not generalize to graded evidence.
- **H025 (Confidence stable): SUPPORTED** for Score on this state (0.99 constant).
- **H026 (Noul jitter small relative to signal): SUPPORTED.** Jitter range (0.02) is ~20x smaller than the fair-coin "signal" that distinguishes 0.46 from the extreme cases (0.01/0.98 in Phase 1, or 0.23/0.65 in 007's 30%/70% cases).

**Net takeaway:** Jev Noul is effectively deterministic for practical purposes on this state — the jitter (range 0.02) is an order of magnitude smaller than meaningful output differences. A single Noul call is a reliable estimate of the central tendency. However, the ±0.01 jitter is real and must be acknowledged in any claim of exact reproducibility.

## Limitations

- Single state (fair coin). Does not test whether repeatability varies with evidence strength.
- Sequential calls may share server-side caching or have correlated sampling.
- 20 repeats is moderate for a determinism claim but does not prove determinism in general.
- Score determinism tested only at an obvious integer level, not graded evidence (007's fractional scores).
- Latency measured as client wall-clock, which includes network overhead, not pure model inference time (see 001's `x-envoy-upstream-service-time`).

## Next experiment

009 — Wording sensitivity. With Noul jitter established as tiny (±0.01), any output variation from semantically-equivalent wording changes is attributable to wording, not noise. This makes 009's wording-vs-jitter comparison clean.