# Football data layer: files, cutoffs, and direct use

This repository keeps source responses in `data/raw/` and builds local Parquet tables in `data/derived/`. Both directories are ignored by Git. The data layer covers finished matches from the five largest domestic leagues and UCL in detail, plus feeder-league/UEL/UECL results for cross-league Elo. It prepares historical and upcoming match inputs; it does not call Jev or train a model.

## Refresh and verify

```bash
.venv/bin/python -m src.data.cli daily
.venv/bin/python -m src.data.cli audit
.venv/bin/python -m src.data.cli status
```

`daily` refreshes the current season, downloads FotMob details for fixtures whose kickoff was at least four hours earlier, takes forward snapshots, rebuilds tables and features, and runs the audit. A failed source fetch or audit makes the command return a nonzero exit code. Newly finished fixtures can appear in `matches.parquet` with `details_pending=True`; they remain visible and are fetched by a later daily run. `audit` treats them as overdue after 28 hours (the four-hour settle rule plus a daily refresh interval), and also fails if IDs are duplicated, model inputs contain outcome columns, cutoffs move too close to kickoff, input schemas diverge, or a quote was captured after kickoff.

To rebuild entirely from the cached source files without network access:

```bash
.venv/bin/python -m src.data.cli build-tables
.venv/bin/python -m src.data.cli build-features
.venv/bin/python -m src.data.cli audit
```

## Derived file contract

| File | Grain | Use |
|---|---|---|
| `matches.parquet` | One finished fixture across all collected competitions | FotMob identity, UTC kickoff, final and 90-minute result, source timing, conflict flags, and `has_match_details` / `details_pending`. Current-match scores are labels, never prediction inputs. |
| `team_stats.parquet`, `players.parquet`, `shots.parquet` | Two team rows, many player rows, or many shot rows per detailed fixture | Post-match observations. Only prior fixtures may contribute rolling inputs. `corners_90` is the reconstructed regulation count where possible; 120-minute `corners` remains a separate raw statistic. |
| `odds.parquet` | One joined football-data row per domestic fixture | Historical prices and current-match statistics. `fd_stat_HxG/AxG` are post-match xG, not odds. Opening/closing CSV columns lack per-row capture times and are not default Jev state fields. |
| `understat_match.parquet`, `understat_team_match.parquet` | One source match or one team history row | Domestic xG and related metrics. `us_source_datetime_text` and `us_date_gap_days` expose stale or postponed source dates. One Understat match has no FotMob fixture link; its team rows remain unjoined. |
| `market_labels.parquet` | One finished fixture | Reliable 90-minute 1X2, total goals, O/U 2.5, BTTS, and conservative total-corner labels. Conflicting corner totals are null with `corner_conflict=True`; awarded/disputed results have null goal labels. |
| `model_inputs.parquet` | One finished target fixture | **Label-free** historical as-of features; use this for ML inputs or state construction. |
| `upcoming.parquet`, `upcoming_inputs.parquet` | One future target fixture | Future fixture identity and the same label-free feature schema. No result event is applied for a fixture being queried. The files refresh when tables/features are rebuilt. |
| `forward_quotes.parquet` | One displayed bookmaker side/line per saved ESPN event and capture | `captured_at_utc`, provider, market, side, line, decimal price, source file, optional FotMob `match_id`, `available_at_cutoff`, and `near_cutoff_15m`. Unmatched events retain null `match_id`. ESPN calls the field `close` even on pre-event pages; its quote time and executability are unverified, so `price_semantics` is explicit. |
| `features.parquet` | One finished target fixture | Legacy combined features **and labels**. Prefer `model_inputs.parquet` plus an explicit `match_id` join to `market_labels.parquet` for ML. |

The historical feature cutoff is the earlier of the FotMob and football-data recorded kickoff times, minus 60 minutes. Both times, the difference, and `cutoff_source` are retained in `matches.parquet`. Match results enter Elo/form only after the nominal completion delay. Season membership is seeded from the fixture list so clubs have a zero-game domestic table before their first result; rank/points are reconstructed and do not reproduce every official deduction or tie-breaker. Current-match starting XI is omitted by default because the finished-match record has no pre-cutoff release timestamp. The feature API accepts separately captured, confirmed, timestamped lineups when available.

## Use the data directly

For a historical model, start from `model_inputs.parquet`, then join only the intended label from `market_labels.parquet` by `match_id`. Filter `label_valid_90` for goal markets, require non-null `corner_total_90` for a corner line, and inspect timing/source quality flags in `matches.parquet` before fitting. Keep a chronological train/validation split.

```python
import pandas as pd

inputs = pd.read_parquet("data/derived/model_inputs.parquet")
labels = pd.read_parquet("data/derived/market_labels.parquet")
training = inputs.merge(labels[["match_id", "label_valid_90", "result_90"]], on="match_id", validate="one_to_one")
training = training[training["label_valid_90"]]
```

For Jev, the CLI prints a structured JSON state from an allowlist of as-of feature fields. It excludes odds, outcomes, match ratings from the current game, and missing numbers. The upcoming command refuses matches whose information cutoff has passed:

```bash
.venv/bin/python -m src.data.cli state --match-id MATCH_ID
.venv/bin/python -m src.data.cli state --match-id MATCH_ID --upcoming
.venv/bin/python -m src.data.cli state --match-id MATCH_ID --upcoming --anonymized
```

The `capture-due` command reads `upcoming.parquet` and archives ESPN scoreboard pages for competitions with a fixture cutoff in the next 15 minutes. It also refreshes `forward_quotes.parquet` without rebuilding all historical tables. The [systemd user timer](../ops/systemd/README.md) is enabled on the research laptop and calls it every five minutes while the laptop is awake. Matching odds to fixtures requires both normalized team names, the competition, and kickoff within 30 minutes; a small observed alias list is explicit in `src/data/quotes.py`. No price is silently assigned to an uncertain fixture.

## Known limits to preserve in downstream work

- Four cross-source match-score conflicts are flagged; one old Spezia–Verona playoff conflict was caused by a duplicate-pair join and has been repaired. The source rows now match the March league fixture, leaving the June playoff result intact.
- FotMob and football-data kickoff times differ by more than 15 minutes on 16 joined matches. The earlier time defines the historical information cutoff; `kickoff_disagreement` remains visible for sensitivity checks.
- FotMob and football-data corner totals disagree on some matches. The canonical corner label is null when both sources exist and disagree. Extra-time fixtures use first- and second-half corner totals when available; otherwise their 90-minute corner label is null.
- The forward quote archive has no verified BTTS or corners market, and an ESPN price displayed before kickoff does not establish that it was executable. Use `near_cutoff_15m` and a matching line for any exploratory market comparison. No historical UCL odds are joined.
- Domestic cup results, confirmed historical lineup-publication times, reliable historical injury lists, and live bookmaker quote timestamps are not present. These should stay missing in a strict pre-match state.
