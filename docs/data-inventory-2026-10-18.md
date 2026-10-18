# Football data inventory — 2026-10-18

Snapshot audited after the FotMob 2014–2019 backfill finished at 20:18 IST and `build-tables` / `build-features` completed at about 21:49 IST. Counts are for files and **finished fixtures present in the local cache**, not a promise that matches played later on 18 October have already been refreshed. The latest finished fixture in the rebuilt tables kicked off on **2026-10-17 19:00 UTC**. The current 2026/27 season remains in progress.

## At a glance

| Layer | Verified inventory | What it contains |
|---|---:|---|
| Football-data.co.uk | 65 CSVs; 21,886 joined domestic match rows | Results, half-time scores, shots, shots on target, corners, fouls, cards, and many bookmaker prices. CSV rows are joined to FotMob IDs, subject to the join caveat below. |
| Understat | 65 league JSON files; 21,911 result rows, **21,910 joined** | Match and team xG, xGA, non-penalty xG, PPDA, deep entries, xPts for the five domestic leagues. No UCL. No individual Understat shot-detail files were fetched. |
| FotMob fixture lists | 254 league-season JSON files; **63,833 unique finished matches** | Five target domestic leagues, UCL, twelve other domestic leagues, UEL, and UECL; shared team IDs, kickoff UTC, final result, round and competition. |
| FotMob match details | **23,570 / 23,570 expected target files present and parsed** | Every finished top-five/UCL match in the cached seasons. Detailed team stats, lineups, player performances and shot maps when the provider includes them. The other 40,263 matches intentionally have fixture results only. |
| 538 SPI archive | 68,913 CSV rows | Historical forecasts/ratings archive. Stored raw; not joined into the derived tables or feature engine. |
| Forward snapshots | 99 raw bodies: 90 ESPN, 3 football-data fixtures, 3 FPL, 3 ClubElo | Timestamped captures. They have not been parsed into match-level historical price or availability tables. The CLI's `status` currently misreports **9** because its snapshot counter excludes filenames containing `@`. |
| Rebuilt derived tables | 9 base Parquet tables plus the features file, about 28 MiB total; raw cache about 4.4 GiB | Joined matches, team stats, players, shots, odds, Understat, team identity and partial unavailable-player records. |
| As-of features | **23,570 matches × 135 columns** | Historical target-match features calculated at kickoff minus 60 minutes, plus separately named outcome columns in the same file. No upcoming-fixture prediction path yet. |

`data/raw/` and `data/derived/` are ignored by Git. The raw backfill log ended `done=11563/11563 ... failed=0`; an independent fixture-to-file check found **0 missing** FotMob match-detail files across all 13 target seasons. The 71 repository tests pass against the rebuilt data.

The main entry points on disk are `data/derived/matches.parquet` (fixture and result identity), `team_stats.parquet`, `players.parquet`, `shots.parquet`, `odds.parquet`, `understat_match.parquet`, `understat_team_match.parquet`, `teams.parquet`, and `features.parquet`. The immutable source bodies and fetch metadata remain under `data/raw/`.

## Competition coverage

`Details` and the FotMob stats below refer to the saved per-match payload. `FD` and `US` count rows joined to the same FotMob match ID. `FM xG` means both teams have a match xG value; `FM corners` means both have a corner count. The five disputed target matches are excluded from `valid 90'` labels.

| Competition | Finished matches | Valid 90' result | Details | FD rows | US xG rows | FM xG, both | FM corners, both |
|---|---:|---:|---:|---:|---:|---:|---:|
| Premier League | 4,625 | 4,625 | 4,625 | 4,620 | 4,625 | 2,350 | 4,625 |
| La Liga | 4,643 | 4,643 | 4,643 | 4,638 | 4,643 | 2,364 | 4,625 |
| Bundesliga | 3,724 | 3,723 | 3,724 | 3,717 | 3,724 | 1,894 | 3,724 |
| Serie A | 4,625 | 4,622 | 4,625 | 4,620 | 4,624 | 2,346 | 4,625 |
| Ligue 1 | 4,295 | 4,294 | 4,295 | 4,291 | 4,294 | 2,122 | 4,295 |
| Champions League | 1,658 | 1,658 | 1,658 | 0 | 0 | 914 | 1,658 |
| **Target total** | **23,570** | **23,565** | **23,570** | **21,886** | **21,910** | **11,990** | **23,552** |

The rating-only competitions contain **40,263** additional finished results. They feed cross-league Elo through FotMob team IDs but have no saved `matchDetails` files or derived player/shot rows.

| Results-only competition | Finished matches | Results-only competition | Finished matches |
|---|---:|---|---:|
| Turkey | 4,074 | Belgium | 3,829 |
| Portugal | 3,743 | Netherlands | 3,728 |
| Czech Republic | 3,279 | Norway | 3,059 |
| Greece | 3,017 | Scotland | 2,740 |
| Denmark | 2,607 | Ukraine | 2,483 |
| Switzerland | 2,364 | Austria | 2,331 |
| Europa League | 2,262 | Conference League | 747 |

## Depth by season for the six target competitions

| Season | Finished matches | Valid 90' result | FotMob xG, both teams | FotMob shot map | FD domestic rows | Understat domestic rows |
|---|---:|---:|---:|---:|---:|---:|
| 2014/15 | 1,951 | 1,951 | 0 | 0 | 1,826 | 1,826 |
| 2015/16 | 1,951 | 1,951 | 0 | 0 | 1,826 | 1,826 |
| 2016/17 | 1,951 | 1,949 | 0 | 0 | 1,826 | 1,826 |
| 2017/18 | 1,951 | 1,951 | 0 | 0 | 1,826 | 1,826 |
| 2018/19 | 1,951 | 1,951 | 4 | 4 | 1,826 | 1,826 |
| 2019/20 | 1,844 | 1,844 | 18 | 18 | 1,725 | 1,725 |
| 2020/21 | 1,951 | 1,950 | 1,949 | 1,950 | 1,826 | 1,826 |
| 2021/22 | 1,951 | 1,951 | 1,951 | 1,951 | 1,826 | 1,826 |
| 2022/23 | 1,952 | 1,951 | 1,952 | 1,952 | 1,826 | 1,826 |
| 2023/24 | 1,877 | 1,877 | 1,876 | 1,876 | 1,752 | 1,752 |
| 2024/25 | 1,941 | 1,940 | 1,941 | 1,941 | 1,752 | 1,752 |
| **2025/26** | **1,941** | **1,941** | **1,941** | **1,941** | **1,752** | **1,752** |
| **2026/27 to date** | **358** | **358** | **358** | **358** | **297** | **321** |

The five domestic leagues account for 1,752 of the 1,941 matches in 2025/26; UCL accounts for 189. The current 2026/27 cache has 322 domestic results and 36 UCL results. FotMob xG and shot maps are systematic from 2020/21; the 22 earlier xG matches are isolated exceptions. Understat covers domestic xG from 2014/15 onward.

## Fields and their measured completeness

All `team_stats` coverage counts mean **both teams have a value in the same match**, out of 23,570 target matches. Other row counts are explicitly labelled. These are post-match observations; they become pre-match evidence only when rolled over *earlier* completed fixtures.

| Data group | Fields stored in the derived tables | Coverage / status |
|---|---|---|
| Identity and result | Match ID, competition, season, round, UTC kickoff, FotMob home/away IDs and names, final score, reconstructed 90' score, extra-time/penalty reason, conflict flag | 63,833 fixture rows; 23,565/23,570 target 90' outcomes accepted as labels; 5 target conflicts flagged. |
| Venue and officials | Referee, stadium, attendance | Referee and stadium on 23,570/23,570 target matches; attendance on 21,572. Historical publication time is not recorded. |
| Core team match stats | Possession, shots, shots on target, corners | **23,552/23,570** matches from FotMob for both teams. Football-data supplies corner counts for the 18 FotMob gaps, giving a source-field corner count for all 23,570 target matches. |
| xG family, FotMob | xG, open-play xG, non-penalty xG | **11,990** matches with both teams; set-play xG 11,955; xG on target 11,881. Mostly 2020/21 onward. |
| Attacking detail | Shots off target, blocked, inside/outside box, woodwork, big chances and misses | **19,807** matches with both teams. Touches in the opposition box: 10,962. |
| Passing and build-up | Passes, accurate passes, long balls, crosses, throw-ins, offsides | **19,807** matches with both teams. Accurate-pass percentage: 19,806; opposition-half passes: 19,772; own-half passes: 18,371. |
| Defensive and discipline | Tackles, interceptions, shot blocks, clearances, goalkeeper saves, duels, aerial/ground duels, dribbles, fouls, yellow/red cards | **19,807** matches with both teams for the main counts; several success percentages have 19,800–19,806. Provider definitions differ from football-data for some shots/cards. |
| Lineup, formation, coaching | Formation, coach ID/name, starting XI, substitutes, player positions, substitutions, player ratings, lineup rating | 47,140 team rows (exactly two per target match); formation is populated on all, coach name is blank on one team row; lineup rating on **19,773** matches with both teams. **943,582** player-match rows, including 518,540 starter rows and 540,656 rated rows. Actual XI availability at the 60-minute cutoff is unproven. |
| Shot events | Shot ID, team/player, minute, coordinates, event/shot type, situation, period, blocked/on-target/own-goal flags, xG, xGOT | **302,850** shots from 11,991 target matches; 301,898 rows have shot xG and 175,046 have xGOT. Primarily 2020/21 onward. |
| Understat match/team metrics | Match xG home/away; team xG/xGA, non-penalty xG/xGA, PPDA attack/defence, deep/deep allowed, xPts | 21,911 match rows (21,910 joined); 43,822 team rows (43,814 joined), domestic leagues only. Understat and FotMob xG are different provider models; do not treat them as identical values. |
| Football-data match stats | Half-time goals, shots, shots on target, fouls, corners, yellow/red cards | 21,886 domestic rows; both corner sides populated on **21,884**. These fields describe the current match and are labels, or prior-match inputs only. |
| Bookmaker odds | 173 parsed numeric `odds_*` columns including 1X2, O/U 2.5, and Asian handicap families | 21,886 domestic rows; Pinnacle closing 1X2 triplet on 20,733 (898/1,752 in 2025/26, **0/297** joined rows in 2026/27); average closing 1X2 and O/U 2.5 pairs on 12,756; Betfair Exchange closing 1X2 and O/U 2.5 on 3,690. No joined historical UCL, BTTS, or corners prices. Opening/closing CSV odds lack per-row capture times. |
| Unavailable players | Player ID/name, injury/absence type, expected return | 49,415 records over 11,388 matches in `unavailable_partial`; prior audit found this feed too incomplete for historical injury features. |

### Per-field FotMob team-stat coverage

| Complete both-team matches | Fields |
|---:|---|
| 23,570 / 23,569 | Formation / nonblank coach name (lineup/match facts rather than numeric match stats). |
| 23,552 | Possession, shots, shots on target, corners. |
| 19,807 | Shots off target, blocked shots, woodwork, shots inside/outside box, big chances and misses, passes, accurate passes, long balls, crosses, throw-ins, offsides, tackles, interceptions, shot blocks, clearances, keeper saves, duels won, ground/aerial duels won, dribbles succeeded, fouls, yellow/red cards. |
| 19,806–19,800 | Accurate-pass, long-ball, cross, duel and dribble success percentages; individual values differ slightly. |
| 19,773 | Lineup rating. |
| 19,772 / 18,371 | Opposition-half / own-half passes. |
| 11,990 | xG, open-play xG, non-penalty xG. |
| 11,955 / 11,881 | Set-play xG / xG on target. |
| 10,962 | Touches in opposition box. |

## As-of feature coverage

The engine uses all 63,833 results as chronological input for cross-league Elo, but writes features only for the 23,570 target matches. The 135-column file includes **labels in the same Parquet file**, so training and Jev state construction must explicitly select permitted feature columns. Coverage below requires the field on **both** home and away sides.

| Historical feature pair | All target matches | 2025/26 | 2026/27 cached to date |
|---|---:|---:|---:|
| Elo | 23,570 / 23,570 | 1,941 / 1,941 | 358 / 358 |
| Domestic table position | 22,626 / 23,570 | 1,868 / 1,941 | 304 / 358 |
| Recent five-match form | 23,437 / 23,570 | 1,938 / 1,941 | 353 / 358 |
| Understat rolling xG | 22,446 / 23,570 | 1,827 / 1,941 | 329 / 358 |
| FotMob rolling xG | 11,784 / 23,570 | 1,924 / 1,941 | 338 / 358 |
| Rolling shots and possession | 23,279 / 23,570 | 1,926 / 1,941 | 342 / 358 |
| Prior ratings of the **actual** starters | 20,201 / 23,570 | 1,941 / 1,941 | 358 / 358 |
| Rest days from covered matches | 23,437 / 23,570 | 1,938 / 1,941 | 353 / 358 |

Head-to-head history exists for 20,542/23,570 target fixtures. The engine also provides rolling goals for/against, shots against, corners, cards, pass accuracy, big chances, lineup continuity, congestion over 14/30 days, domestic points/GD/PPG, and Elo difference/expected score. The first matches of a season or newly observed teams naturally lack some form/table/history fields. Its table is reconstructed from results, not a guaranteed exact official table with every points deduction or league-specific tie-breaker.

## Market outcomes this dataset can support

| Market | Outcome label source | Historical price source currently joined | Readiness |
|---|---|---|---|
| 1X2, 90 minutes | `matches.goals_90_home/away` | Domestic 1X2 odds | 23,565 accepted target labels; UCL has no joined historical price. |
| Over/under 2.5 goals | Sum of accepted 90-minute goals | Domestic O/U 2.5 odds | Same accepted goal labels; 12,756 rows have average closing O/U 2.5 prices. |
| Both teams to score | Each accepted 90-minute goal count is at least 1 | None in current joined odds | Outcome evaluation possible; price/edge evaluation needs a pre-cutoff BTTS quote. |
| Total corners over/under a specified line | Home + away corner counts from football-data or FotMob | None in current joined odds | Source field on all 23,570 target matches, but a canonical 90-minute label, extra-time handling, source adjudication, and matching price line still need implementation. |
| Cards, shots on target, first-half or team goals, handicap | Provider-specific stats or scores | Some handicap odds; others not joined | Candidate markets for a separately specified label/settlement audit. |

## Quality and timing limitations before Jev or ML

1. **One known incorrect source join remains.** Serie A's regular Spezia–Verona match on 2023-03-05 and playoff on 2023-06-11 share the same home/away team IDs. The regular match's football-data odds and Understat match row were attached to the playoff, causing one of the five `score_conflict` flags and blanking that playoff's 90-minute label. Thus `21,886/21,886 joined` describes coverage, not perfect correctness. Fix the join and rerun the conflict audit before training/scoring.
2. **A source field is not automatically a pre-match input.** Current-match goals, xG, shots, corners, cards, player ratings, and attendance are post-match outcomes. Rolling versions from earlier completed games may be used at the cutoff. The actual XI and formation came from completed-match payloads without a release timestamp, so lineup-dependent historical features are not yet certified as known 60 minutes before kickoff. FotMob market values are fetch-time values and should not enter an as-of state. The football-data parser also put 297 post-match `HxG` and `AxG` values under `odds_HxG` and `odds_AxG`; those columns are **not prices** and must be reclassified before any broad `odds_*` selection.
3. **Cross-source definitions differ.** On the 21,866 matches with both football-data and FotMob home/away corners, 21,454 have the same total; 20 differ by more than two. Shots and yellow cards disagree more often, so retain provider identity and audit each market label before mixing values. For UCL matches with extra time, confirm whether FotMob `Periods.All` corners/cards include the extra period before calling them 90-minute labels.
4. **Kickoff and odds cutoffs need adjudication.** A prior comparison found 17 football-data/FotMob kickoff differences over 15 minutes among 12,756 rows with both times; the Spezia misjoin is one cause. Historical CSV opening/closing odds have no per-match capture timestamp. Closing odds and the current match's stats cannot be placed in a historical pre-cutoff Jev state.
5. **Forward predictions are not wired yet.** `features.parquet` covers already finished matches only. The ESPN/FPL/ClubElo snapshots are raw archives, not a parsed, joined, timestamp-validated pre-match feature/odds table. Historical injury lists are incomplete. A fixture query and immutable prospective record are required before evaluating real-time advice.
6. **Do not infer missing data from a null-free parser row.** For example, formation and coach fields are populated on all target records, but the release time of the lineup is unknown; referee/stadium are from finished-match payloads; and bookmaker odds are evaluation-only until their timing is established. The current 2026/27 cache is a partial season, not a final-season total.

The [Jev football experiment plan](phase4-jev-football-experiment-plan.md) defines the next data gates, Noul/Score/Choice comparisons, and prospective tests across 1X2, goals, BTTS, and corners.
