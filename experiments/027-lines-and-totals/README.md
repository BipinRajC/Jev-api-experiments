# Experiment 027 — Lines and totals extension

Status: **ACTIVE — registered and live in the 024 prospective runner (protocol
revision 3, QSET-027-v1). Prospective confirmation pending.**

## Objective

Cover the user's preferred lines beyond the live over-2.5/9.5 arms: the goals
totals curve (1.5 and 3.5) and the corners line the user actually bets
(under 11.5). Under-side probabilities are scored as the complement of the same
over-record (one question prices both sides).

## Registered events (QSET-027-v1)

| Event | 90' proposition | Dev rate (2014/15–2024/25) |
|---|---|---|
| `total_goals_over_1_5` | ≥ 2 total goals | 0.7670 |
| `total_goals_over_3_5` | ≥ 4 total goals | 0.3060 |
| `corners_over_11_5` | > 11.5 total corners (user's under-11.5 = 0.7083) | 0.2917 |

Settlement: `market_labels` goals under the `label_valid_90` gate; conflict-free
`corner_total_90` for corners. Baselines: the frozen Dixon–Coles matrix tails
(goals) and the NB corner model (corners), per the research's structural
framework.

## Results

Pending (prospective accumulation from 2026-10-19). Note on the user's
under-11.5-corners belief: it is indeed high-probability (0.708), but that
tells us the *outcome frequency*, not whether the market price offers value —
bookmakers price ~1.30-1.35 for it, which the probability alone cannot beat.
Skill here means beating the DC/NB baseline's probability, not being above 50%.
