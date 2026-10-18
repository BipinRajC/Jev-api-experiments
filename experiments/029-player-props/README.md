# Experiment 029 — Player props (to score / to assist / shots on target)

Status: **REGISTERED — data audit done; activation pending the player-selection
rule freeze and the assist re-parse. Not yet live.**

## Objective

Price player-level props with the three primitives and evaluate them against
player-level baselines (trailing-rate and Poisson count models), per the
research's count-model guidance.

## Data audit (2026-10-19)

| Prop | Data | Status |
|---|---|---|
| Player to score | `shots.parquet` Goal events with `player_id` (303k shots; systematic 2020/21+) — 34,181 goals; player-match history in `players.parquet` (944k rows) | **FEASIBLE** |
| Player shots on target (over a line) | `shots.parquet` `is_on_target` per player per match | **FEASIBLE** |
| Player to assist | Assist ids are NOT in the parsed `players.parquet`, but ARE in the raw FotMob payloads (`header.events.{home,away}TeamGoals[].assistPlayerId/assistStr`) — needs a targeted re-parse (47k cached files, header section only) | **FEASIBLE AFTER RE-PARSE** |

## Design constraints to freeze before activation

1. **Player-selection rule (predeclared, no hindsight):** for each fixture, the
   registered players are each side's top scorer by trailing-365-day goals
   (fallback: trailing shots; fallback: any player with ≥900 trailing minutes).
   The rule must be computed as-of the fixture cutoff from prior matches only.
2. **Markets per registered player:** to score yes/no; 1+ shots on target
   yes/no (assist added after the re-parse).
3. **Baselines:** trailing per-90 goals/SOT rates with a Poisson/NB count model
   (research: NB when overdispersed); shrinkage toward position mean for small
   samples (research: regression-to-the-mean and L2 shrinking).
4. **Settlement:** goal credited with own-goal handling; SOT from `is_on_target`
   on 90-minute events only; assists from the re-parsed assist ids.
5. **Exclusions:** matches without shot maps (pre-2020/21 — irrelevant
   prospectively); players absent from the state (injury/omission) — the prop
   voids (market convention), recorded as excluded rather than as a loss.

## Why not live yet

The player-selection rule and its as-of history table do not exist yet; building
them without care would either leak future information (using post-cutoff form)
or hand-pick players with hindsight. Activation follows the same
register → freeze → activate path as 026/027/028.

## Results

Pending activation.
