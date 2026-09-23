# Experiment 011 — Structured vs Unstructured State

## Objective

Determine whether Jev behaves differently when identical information is represented as prose, JSON, or a compact structured form. The underlying facts are identical; only the representation changes. This tests representation sensitivity — whether the format of the state, not its content, changes Jev's answer.

The handoff notes that a JSON state uses fewer tokens, but this experiment is about behavioral equivalence and sensitivity, not token savings.

## Hypothesis

- H031: Representing identical facts as prose vs JSON vs compact structured text produces materially different Jev outputs.
- H032: The representation format does not change Jev outputs (within the ±0.02 jitter baseline).
- H033: JSON / structured representation uses fewer input tokens than prose.

These are complementary for H031/H032 (exactly one will be supported). H033 is a token-accounting check.

## Experimental setup

Identical facts: **7 red balls and 3 blue balls**.

Three representation formats:

| Format | State value |
|--------|-------------|
| A — prose | "Arun has 7 red balls and 3 blue balls." |
| B — JSON | `{"red": 7, "blue": 3}` |
| C — compact structured | "red=7, blue=3" |

For each format, three primitives in one batch:

- Noul: "Will a randomly selected ball be red?" (ground truth 0.70)
- Choice: options red / blue — "What color will a randomly selected ball be?"
- Score: 0-4 rubric (impossible .. certain) — "How likely is it that a randomly selected ball is red?"

Each format repeated n=3 to average the ±0.02 jitter. 9 total batch calls (each with 3 questions).

## Variables

- Independent variable: state representation format (prose / JSON / compact)
- Dependent variables: Noul value, Choice label + probabilities + confidence, Score value + confidence, input tokens, latency
- Held constant: underlying facts, question wording, model (jev-1.13.0), primitive definitions

## Controls

- The underlying facts (7 red, 3 blue) are identical across all formats.
- The question wording is byte-identical across all formats.
- Model pinned to jev-1.13.0.

## Expected result

- If representation-insensitive: all three formats produce Noul within ~0.02 of each other, matching Choice and Score.
- If representation-sensitive: some format produces materially different outputs.

## Falsification criteria

- H031 is SUPPORTED if the range across format means for Noul (or a materially different Choice/Score) exceeds ~0.03.
- H032 is SUPPORTED if all format outputs stay within ~0.03 of each other.
- H033 is SUPPORTED if JSON/compact input tokens < prose input tokens.

## Sample size

3 formats × 3 repeats = 9 batch calls (3 questions each) = 27 answers. Cost is trivial.

## Results

**Date:** 2026-09-23
**Model:** jev-1.13.0
**Calls:** 9/9 HTTP 200 (3 formats × 3 batch calls, 3 questions each = 27 answers)
**Cost:** ~$0.000174 (4,152 input tokens)
**Ground truth:** 70% red

### Noul by format

| Format | Mean Noul | Repeats | Range |
|--------|-----------|---------|-------|
| prose | **0.700** | 0.70, 0.70, 0.70 | 0.00 |
| json | **0.703** | 0.70, 0.70, 0.71 | 0.01 |
| compact | **0.680** | 0.68, 0.68, 0.68 | 0.00 |

Noul range across format means: 0.023

### Score by format

| Format | Mean Score | Repeats | Range |
|--------|-----------|---------|-------|
| prose | **3.00** | 3.00, 3.00, 3.00 | 0.00 |
| json | **2.99** | 2.99, 2.99, 2.99 | 0.00 |
| compact | **2.97** | 2.97, 2.97, 2.96 | 0.01 |

Score range across format means: 0.033

### Choice by format

All 9 calls selected "red" (confidence 0.99–1.0). No difference across formats.

### Tokens and latency

| Format | Input tokens | Latency (mean) |
|--------|-------------|----------------|
| prose | 464 | 538.7 ms |
| json | 462 | 475.6 ms |
| compact | 458 | 430.9 ms |

Compact uses 6 fewer input tokens than prose (~1.3%). JSON uses 2 fewer. Latency decreases with compactness (538.7 → 475.6 → 430.9 ms).

## Analysis

### Representation format has a small but consistent effect

The compact form consistently produced slightly lower values than prose (Noul 0.68 vs 0.70, Score 2.97 vs 3.00) across all 3 repeats. This is a real, consistent pattern — not a single outlier. The Noul range (0.023) and Score range (0.033) both marginally exceed the ±0.02 jitter baseline.

**However, the magnitude is small.** The largest effect (Score: prose 3.00 vs compact 2.97) is 0.033 — tiny on a 0-4 scale, and far smaller than the wording-sensitivity effect from Experiment 009 (0.207). Prose and JSON were essentially indistinguishable on Noul (0.70 vs 0.703).

### Choice is fully representation-insensitive

All representations produced "red" with high confidence. Choice is the most robust primitive to representation changes.

### Token and latency differences are minor

Compact saves only ~1.3% input tokens vs prose. The latency ordering (prose > json > compact) is interesting but n=3 and confounded by network jitter (008 showed latency varies ~2x).

## Conclusion

- **H031 (Representation format materially changes outputs): INCONCLUSIVE / weakly SUPPORTED.** There is a small consistent effect (compact is slightly lower), but the magnitude (≤ 0.033) is marginal and far below the wording effect. The compact form is a modest outlier; prose vs JSON are essentially equivalent.
- **H032 (Representation format does not change outputs): REJECTED** under strict interpretation, but the deviation is small.
- **H033 (JSON/structured uses fewer input tokens): SUPPORTED.** Compact (458) < JSON (462) < prose (464), though the savings are only ~1.3%.

**Net:** Representation format matters far less than question wording (009). Prose and JSON are behaviorally equivalent on this state. The compact form is slightly lower but still within a small margin. For practical purposes, prose and JSON are interchangeable for decision output; the choice between them is a token/latency tradeoff, not a decision-quality one.

## Limitations

- Single fact set (7/3). Does not test whether representation effects grow with complexity.
- Three formats only; "compact" syntax is one specific form.
- n=3 per format.
- Latency confounded by network jitter (008).
- Primitive definitions identical; only state representation varied.

## Next experiment

012 — Conflicting evidence. Representation has a small effect; prose and JSON are equivalent. Proceed to test how Jev handles internally contradictory state.