# Experiment 023 — State-composition, model-version, and repeatability ablations

Status: **COMPLETED (exploratory, n=48, retrospective cohort).** Lineup and
pre-cutoff-price ablation arms were **not run**: no timestamp-proven historical
lineups and no verified executable quotes exist in this data layer (phase-4 plan
gates 6–7). Wording ablations are not retested — experiments 009 and 017 cover them.

## Objective

Measure which parts of the as-of state actually change Jev's 1X2 forecasts: compare
progressive state compositions (identity only → +Elo → +table/form/rest → full), the
anonymized control, and the pinned `jev-1.13.0` against `jev-1.14.0` on paired
subsets, with repeat-call spread per arm.

## Hypothesis

- **H067:** Adding as-of performance fields to the identity-only state improves Noul
  1X2 three-class Brier by ≥ 0.02 on paired fixtures.
- **H068:** `jev-1.14.0` produces 1X2 distributions matching `jev-1.13.0` within the
  repeat-jitter baseline on paired identical states.
- **H069:** Repeat-call spread (L1 distance of the 1X2 distribution) on every state
  variant stays ≤ 0.05 mean.

## Experimental setup

- **Paired sample:** the 020 pilot's 48 fixtures; every state variant rebuilt from the
  frozen named_full state by field-group filtering (`STATE-ABL-023-v1`) and verified
  against hash.
- **State variants:** `identity_only` (names/competition/dates), `identity_elo`
  (+ team Elo and Elo-diff/expected score), `identity_elo_form` (+ domestic table,
  form, rolling goals/shots/xG, rest/congestion, h2h), `full` (everything in 020's
  state, including xi_* rolling fields), `anonymized` (full but hidden identity).
- **Arms (Noul 1X2, three batched questions each):** `id_only_113`, `id_elo_113`,
  `id_elo_form_113`, `full_113`, `anon_full_113`, `id_only_114`, `full_114`;
  `id_elo_form_113` and `full_113` repeated once on all 48 fixtures.
- 48 fixtures × 7 arms + 96 repeats = **432 calls**; models returned: jev-1.13.0,
  jev-1.14.0 (as requested); measured **679,799 input tokens, $0.0286**.

## Variables

- Independent: state composition, model version, repeat index.
- Dependent: 1X2 three-class Brier, paired Brier differences vs `full_113`, repeat
  L1 spread, tokens, latency.

## Controls

- Identical fixtures, questions (byte-identical 020 Noul 1X2 wordings), parsing
  (020's `parse_call` reused), retry policy; state hash checks per call.
- Full-state 1.13 arm re-run in the same session as the reduced arms for same-day
  pairing (020's run was a separate session).

## Expected result

Monotonic improvement with richer states (identity worst, full best), 1.14 ≈ 1.13,
tight repeat spread.

## Falsification criteria

- H067 REJECTED if identity-only is within 0.02 Brier of the full state (or any
  reduced arm beats full with CI excluding 0).
- H068 REJECTED if a paired 1.13-vs-1.14 difference exceeds the repeat-jitter
  baseline (mean L1 ≈ 0.02–0.03) with CI excluding 0.
- H069 REJECTED if any arm's mean repeat L1 exceeds 0.05.

## Metrics computed

Three-class Brier per arm; paired contrasts with bootstrap 95% CIs (10k resamples,
seed 42); repeat L1 spread; tokens; latency; failure/rejection counts.

## Results

**Date:** 2026-10-19 UTC. **Artifacts:** `results/023-state-ablations/protocol-v1.json`,
`states-001.json`, `stream-001.jsonl`, `run-001.json`.

### 1X2 three-class Brier by arm (n=48 per arm; full/id_elo_form scored on 96 including repeats)

| Arm | State | Model | Brier | Mean tokens |
|---|---|---|---|---|
| id_elo_113 | identity + Elo | 1.13.0 | **0.5594** | 644 |
| id_only_114 | identity only | 1.14.0 | 0.5669 | 535 |
| id_elo_form_113 | + table/form/rest/xG | 1.13.0 | 0.5881 | 1,686 |
| anon_full_113 | full, anonymized | 1.13.0 | 0.5901 | 2,206 |
| full_113 | full | 1.13.0 | 0.5912 | 2,290 |
| id_only_113 | identity only | 1.13.0 | 0.5996 | 535 |
| full_114 | full | 1.14.0 | 0.6034 | 2,290 |

### Paired contrasts vs full_113 (negative = better than full state)

| Arm | Mean diff | 95% CI |
|---|---|---|
| id_elo_113 | −0.0344 | [−0.0770, +0.0049] |
| id_only_114 | −0.0270 | [−0.0984, +0.0412] |
| id_elo_form_113 | −0.0051 | [−0.0144, +0.0042] |
| anon_full_113 | −0.0037 | [−0.0204, +0.0108] |
| id_only_113 | +0.0058 | [−0.0738, +0.0817] |
| full_114 | +0.0096 | [−0.0047, +0.0247] |

**No contrast excludes zero.** The Elo-only state is nominally the *best* arm.

### Repeat spread (r1 vs r2, 48 pairs per arm)

`id_elo_form_113` mean L1 0.0246 (max 0.0610); `full_113` mean L1 0.0233 (max 0.0696).

## Analysis

The ablation ladder is **flat**: identity-only sits within noise of the full state
(paired diff +0.006, CI [−0.074, +0.082]), and adding Elo/table/form/xG fields does
not measurably improve 1X2 Brier at n=48 — H067 is not supported (INCONCLUSIVE:
the direction is inconsistent and every CI includes 0). The nominal best arm
(Elo-only, 0.559) suggests team identity plus a strength summary carries essentially
all the state's value; most of Jev's football signal appears to ride on team names
(pretraining knowledge), not on the rolling statistics. The anonymized control
matching the named full state (−0.004) is consistent with 020. Version-wise, 1.14.0
is statistically indistinguishable from 1.13.0 on paired full states (+0.010, CI
[−0.005, +0.025]) — H068 not rejected; the paired difference is within the repeat
jitter. Repeat spread (mean L1 0.023–0.025) satisfies H069 (≤ 0.05).

## Conclusion

- **H067: INCONCLUSIVE** — no measurable state-composition effect at n=48; the
  identity-only state is not distinguishable from the full state.
- **H068: SUPPORTED** — 1.14.0 matches 1.13.0 within jitter on paired states
  (no significant paired difference).
- **H069: SUPPORTED** — repeat L1 ≤ 0.025 mean on both repeated arms.

Exploratory only: n=48 cannot detect small ablation effects, and all calls are
post-match (retrospective cohort).

## Limitations

- Small n; CIs are wide; the ladder is underpowered for effects < ~0.05 Brier.
- Team-name-carried signal cannot be separated from contamination in this cohort.
- Lineup and pre-cutoff price arms omitted (no proven timestamped data — phase-4
  gate 7); xi_* fields remain in the full state only.
- One wording (020's canonical Noul form); wording sensitivity is documented in 009/017.

## Verification commands

```
.venv/bin/python -m pytest tests/test_exp023_ablations.py      # 7 passed
.venv/bin/python -m pytest                                      # full suite
.venv/bin/python -m src.data.cli audit                          # 0 errors
```

Independent validation: all 432 stream records re-parsed with 020's parser (0
mismatches), 0 duplicate keys, 0 state-hash mismatches vs the frozen protocol, 0
calls requested at/before cutoff, returned models exactly as requested.

## Next experiment

024 (prospective series) is ACTIVE and accumulating predictions; 025 (Jev plus ML)
consumes the frozen 021/024 outputs; 026 remains WAITING FOR RESEARCH.
