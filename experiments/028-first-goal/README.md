# Experiment 028 — First goal by which team

Status: **ACTIVE — registered and live in the 024 prospective runner (protocol
revision 4, QSET-028-v1). Prospective confirmation pending.**

## Objective

Price the three-way first-goal market (home scores first / away scores first /
no goal) with all three primitives, and evaluate against structural baselines.

## Label construction (verified by test)

From the parsed FotMob shot maps (`shots.parquet`, systematic 2020/21 onward —
all eval-season fixtures are covered):

- first goal = earliest Goal event by (half order, minute, stoppage);
- own goals count **for the benefiting team** (the non-shooting side);
- only FirstHalf/SecondHalf events (extra time and shootouts excluded);
- a shot map with no Goal event settles as `no_goal`;
- a match with no shot map at all stays null — never guessed.

Development rates (2020/21–2024/25 shot-map seasons) and the frozen
Dixon–Coles P(0-0) provide the `no_goal` baseline; the home/away first rates
provide the two remaining constant baselines.

## Registered arms (QSET-028-v1)

- `choice_first`: one three-way Choice (home/away/no_goal), parsed by the
  dedicated `parse_first_goal_choice` (missing keys, zero sums and out-of-range
  values are rejected, never repaired).
- `noul_first`: two binary Noul propositions (home first; away first).
- `score_first`: two nine-level Score rubrics on the same propositions.

## Results

Pending (prospective accumulation from 2026-10-19).
