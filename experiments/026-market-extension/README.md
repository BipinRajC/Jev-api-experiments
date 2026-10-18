# Experiment 026 — Mathematical market extension

Status: **ACTIVE — research registered, markets audited and shortlisted, live
via the 024 runner protocol revision 2 (QSET-026-v1). Prospective confirmation
pending.**

## Research source (dated registration)

- **Document:** "Mathematical Foundations of Football Quantitative Analytics and
  Sports Betting: The FootyQuant v2 Scientific Framework" (Deliverables A–J:
  math foundations, annotated research library — Maher 1982, Dixon–Coles 1997,
  Karlis & Ntzoufras 2003/2009, footBayes, Shin 1991/93, Beta calibration
  (Kull et al. 2017), Goddard 2004 — methods matrix, evidence assessment,
  9-stage framework, walk-forward validation protocol, implementation spec).
- **Received:** 2026-10-19 (IST).
- **Stored copy:** `docs/footyquant-math-research-2026-10-18.pdf`,
  sha256 `b4419ccbe51c42e5a233ee33212bd5813580a1ff19f563f4cd3452242b6d091a`.

## What the research changes

The research's implementation spec (Deliverable J) grounds the candidate markets
in structural score-matrix mathematics: a Dixon–Coles (or bivariate-Poisson) score
matrix directly prices team goals, any over/under line, and Asian-handicap/margin
markets (with Skellam as the specialized margin form). It also prescribes Beta
calibration, Shin de-vigging, and fractional Kelly — those concern staking and
calibration infrastructure, not the Jev experiment set, and are noted as
product-stage guidance, not part of this repository's Jev protocol.

## Candidate-market audit (2026-10-19, development + current data)

| Candidate | Label source and coverage | Verdict |
|---|---|---|
| Team goals (home/away over a line) | `goals_home_90`/`goals_away_90` under the `label_valid_90` gate — 23,581 valid rows | **SHORTLISTED** |
| Handicap / goal margin (Skellam) | Same goal labels; margin = difference — 23,581 valid rows | **SHORTLISTED** |
| First-half goals | football-data `fd_stat_HTHG/HTAG`: 21,883/23,585 (93%); domestic only, no UCL half-time labels | **SHORTLISTED** (scored where labels exist; UCL coverage null) |
| Cards | FotMob team stats include extra time; provider card counts disagree across sources | **EXCLUDED** (90-minute scope unproven) |
| Shots on target | 99.9% coverage but extra-time scope unproven | **EXCLUDED** (same reason) |

## Registered markets and locked lines (QSET-026-v1)

Lines locked from 2014/15–2024/25 development data by the predeclared
nearest-to-balanced rule (measured rates):

| Event | Proposition (90') | Dev rate |
|---|---|---|
| `home_team_over_1_5` | The home team scores at least 2 goals | 0.4471 |
| `away_team_over_1_5` | The away team scores at least 2 goals | 0.3433 |
| `handicap_home_minus_1_5` | The home team wins by at least 2 goals | 0.2351 |
| `first_half_over_1_5` | At least 2 goals before half-time | 0.3496 |

Settlement rules are in the `QSET-026-v1` docstring and implemented in the 024
settler. No odds source exists for any extension market (ESPN carries none of
them) — outcome-only evaluation until a verified pre-cutoff price appears.

## Mathematical baselines (per the research, implemented)

- Team goals and handicap: marginals/tails of the frozen Dixon–Coles score
  matrix (`experiments/021-retrospective-locked/baselines.py`), which the
  research designates as the Tier-2 structural baseline; Skellam is the
  specialized margin form (same information as the matrix diagonal difference).
- First-half goals: constant development base rate (0.3496) — no structural
  half-time model yet (recorded as an open gap).

## Primitive mapping

Same three primitives and derivation rules as QSET-020-v1 (Noul direct binary,
Score nine-level rubric score/8, Choice yes/no via `probabilities["yes"]`),
batched into three new arms (`noul_ext`, `score_ext`, `choice_ext`) in the 024
prospective runner — protocol revision 2. The core six arms and their frozen
records are untouched.

## Evaluation plan (prospective only)

The extension markets enter scoring **only** through the 024 prospective
cohort: predictions accumulate from revision-2 activation (2026-10-19), settle
via the extended settler, and are reported descriptively after the 250-match
interim and conclusively after season end. No retrospective backtest of these
markets is run or used for ranking — per the phase-4 rule against outcome-only
market selection.

## Results

Pending (prospective accumulation started 2026-10-19).

## Limitations

- First-half labels are domestic-only; UCL first-half predictions are recorded
  but unscored.
- `handicap_home_minus_1_5` is skewed (dev rate 0.235) — chosen because the
  closer-to-balanced half-line duplicates the existing home-win event.
- No verified market prices for any extension market.
- The DC matrix prices full-time markets only; the first-half baseline is a
  constant until a half-time-conditional model exists.
