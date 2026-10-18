# Phase 4 — Data Source Findings

Research date: 2026-10-13 (live checks 2026-10-12 → 2026-10-13 UTC). Scope: Premier League only.
Current season is **2026-27** (50 of 380 matches played as of 2026-09-20 in the data); **2025-26 is complete**.

## 0. Summary, verification legend, and decisions needed

### Bottom line

1. **Backbone (free, keyless, verified): football-data.co.uk `E0.csv`.** One CSV per season gives results, kickoff time, referee, shots / SoT / corners / fouls / cards, and many bookmakers' odds including **Pinnacle 1X2 and Over/Under 2.5, pre-closing and closing**. Everything in Tier 1 (table, form, head-to-head, rest days) is **computed as-of from these results**; no free API gives as-of tables.
2. **Pinnacle is only usable for 2019-20 → 2024-25** (2,280 matches with Pinnacle open + close 1X2, verified). The site itself says Pinnacle's feed became unreliable on 2025-07-23; our files confirm Pinnacle coverage drops to 55% in 2025-26 (last row 2026-01-08) and is absent in 2026-27. Fallback benchmarks for later seasons are Betfair Exchange closing and market-average closing (both populated).
3. **There is no free BTTS odds source** (not in any football-data file; none found anywhere else). Drop BTTS from the market comparison unless we pay.
4. **Free per-match xG exists, but no source explicitly permits our use.** Understat (best quality, one call returns all 380 matches) has `robots.txt: Disallow: /` and no ToS; FotMob's robots.txt disallows `/api/*` and its footer bans systematic automated use; FBref **no longer has xG at all** (Opta data removed January 2026). This is a legal-risk decision for you (Decision 1 below). The clean stack works without it.
5. **Firecrawl is not needed** for the recommended stack. Every useful source is plain-curl JSON/CSV. Spent 18 credits total across the research (1,432 of 1,450 free credits remain, measured via `/v1/team/credit-usage`; the paid 10k is not activated).
6. **Jev's training cutoff is not documented** (verified: docs.typesafe.ai/models states none). Backtesting on seasons the model may have seen risks memorization. See §8.

### Verification legend

| Tag | Meaning |
|---|---|
| **[LIVE]** | I (the main session) called it or computed it this session. |
| **[LIVE-A]** | A research sub-agent called it live and reported exact URLs/status/shapes. Raw evidence is in `/tmp/phase4-research/` (ephemeral). I spot-checked several of these against the saved files. |
| **[DOCS]** | Quoted from an official docs / pricing / terms page (URL given). |
| **[3P]** | Third-party or vendor claim. |
| **[UNVERIFIED]** | Not confirmed. Never relied on for a recommendation. |

> **Update 2026-10-18:** scope expanded from the Premier League to the top-5 leagues + UEFA Champions League, with cross-league inference. See **§10**. Decisions 1 and 2 below were settled by the user (legal/ToS risk accepted for personal research use, Understat/FotMob scraping approved); the clean-stack-first recommendation was not adopted.

### Decisions needed from you

| # | Decision | Recommendation |
|---|---|---|
| 1 | **xG sourcing / legal-risk appetite.** Understat and FotMob work technically but are not contractually permitted (robots.txt / ToS). | Run Experiment 020 on the **clean stack** (no scraped xG) first; add xG afterwards as a separately flagged **ablation** ("state with xG vs without"). If you approve Understat: one-time backfill of 1 + 380 requests per season at ≤1 req/s, cached raw, personal research only. |
| 2 | **football-data.co.uk terms.** Notice: "use is intended for private individuals only, NOT commerical or data training products using automated bots/scrapers/AI". We feed it to a predictor as input (not training), but the wording is broad. | Email the author (https://football-data.co.uk/contact.php) describing the use. Download a handful of CSVs, never crawl. |
| 3 | **Optional free signups** (I can't create accounts): The Odds API (forward Pinnacle snapshots), API-Football (injuries / as-of team stats; test season window), football-data.org token. | The Odds API is the highest value (see §6). |
| 4 | **Contamination control** (Jev cutoff unknown). | Run a no-state memorization probe before Experiment 020; reserve a post-2025 holdout. See §8.12. |
| 5 | **Paid odds for a true-opening / Pinnacle backfill?** | Not now. Document only (§6). |

---

## 1. Recommended Primary Source: football-data.co.uk (+ as-of computed features)

### 1.1 What it is and why

`https://football-data.co.uk` publishes free CSVs per league-season. For the Premier League (`E0`) it is the only free source I found that combines **per-match results, kickoff time, referee, shot/corner/card stats, and multi-bookmaker odds (open + close, incl. Pinnacle)** in one machine-readable file, back to 1993. It meets all six decision criteria in the research plan except the ToS wording noted in Decision 2.

### 1.2 Access (all [LIVE] unless noted)

```bash
# Note: www. redirects (302) to the apex domain. Use the apex host or curl -L.
curl -sL -o E0_2425.csv https://football-data.co.uk/mmz4281/2425/E0.csv   # season code = YYZZ
curl -sL -o fixtures.csv https://football-data.co.uk/fixtures.csv         # upcoming fixtures, all leagues (E0 = 10 rows)
```

| Property | Value |
|---|---|
| Auth | none |
| Format | CSV, UTF-8 **with BOM** (`encoding='utf-8-sig'`), dates `dd/mm/yyyy` |
| Rate limit | none documented; response header `x-ws-ratelimit-limit: 1000` [LIVE-A]. We need ~1 request per season file. |
| robots.txt | `User-agent: *` allowed; **blocks ClaudeBot, Claude-Web, Anthropic-AI, GPTBot, CCBot, Google-Extended, PerplexityBot, etc.** [LIVE] |
| Update cadence | "at least updated twice weekly (Sunday nights and Wednesday nights)" [LIVE data.php]; observed lag after final matchday 0–1 day, and the 10–11 Oct 2026 results were not yet in the file on 2026-10-12 evening [LIVE-A] |
| Revisions | Back-seasons are occasionally re-published (2021-22 file modified 2026-02-16) [LIVE-A]; **hash and version every download** |
| Season coverage | 380 rows each for 2019-20 → 2025-26; 50 rows for 2026-27 [LIVE] |

### 1.3 Season coverage table [LIVE for my own downloads]

| Season | Rows | `Time` | Pinnacle 1X2 open / close | Pinnacle O/U 2.5 open / close | Bet365, Avg, Max closing | Betfair Exchange closing |
|---|---|---|---|---|---|---|
| 2019-20 | 380 | 380 | 380 / 380 | 380 / 380 | 100% | n/a (agent: from 2024-25) |
| 2020-21 | 380 | 380 | 380 / 380 | 380 / 380 | 100% | n/a |
| 2021-22 | 380 | 380 | 380 / 380 | 380 / 380 | 100% | n/a |
| 2022-23 | 380 | 380 | 380 / 380 | 379 / 379 | 100% | n/a |
| 2023-24 | 380 | 380 | 380 / 380 | 372 / 373 | 100% | n/a |
| 2024-25 | 380 | 380 | 380 / 380 | 377 / 377 | 100% | 100% |
| **2025-26** | 380 | 380 | **210 / 210 (55.3%)**, last 2026-01-08 | ≈55% (210 rows, **[LIVE-A]**) | 100% | 94.2% |
| **2026-27** | 50 | 50 | **absent** | **absent** | 100% | 100% |

Matches with Pinnacle open **and** close 1X2: **2,280** (2019-20 → 2024-25). Pinnacle caveat quoted from data.php [LIVE]: *"Since 23/07/2025 Pinnacle's public API for odds delivery has become unreliable meaning their odds are systematically out of date relative to odds for other bookmakers, including both the pre-closing and closing odds. Consequently they should be used with caution… and are no longer being included for the calculation of market average and maximum odds."* → treat even the 2025-26 Pinnacle rows (Aug 2025 → Jan 2026) as degraded.

### 1.4 Columns we use (dictionary: https://football-data.co.uk/notes.txt [DOCS])

| Group | Columns |
|---|---|
| Identity / time | `Date`, `Time` (**UK local**, convert with `Europe/London` → UTC), `HomeTeam`, `AwayTeam`, `Referee` |
| Result (**labels, post-match**) | `FTHG`, `FTAG`, `FTR`, `HTHG`, `HTAG`, `HTR` |
| Match stats (post-match; usable only for **earlier** matches) | `HS`, `AS`, `HST`, `AST`, `HF`, `AF`, `HC`, `AC`, `HY`, `AY`, `HR`, `AR` (100% populated in all seasons) |
| Opening odds (no suffix) | Pinnacle `PSH/PSD/PSA`, `P>2.5/P<2.5`; Bet365 `B365H/D/A`; `MaxH/D/A`, `AvgH/D/A`; Asian handicap `AHh`; Betfair Exchange `BFEH/D/A` |
| Closing odds (`C` infix) | `PSCH/PSCD/PSCA`, `PC>2.5/PC<2.5`, `B365CH…`, `MaxCH…`, `AvgCH…`, `BFECH…`, `AHCh` |
| **Not present in any E0 file** | BTTS odds, possession, pass completion, player ratings, attendance, **xG** (except undocumented `HxG/AxG` in the 2026-27 file only, 50/50 rows, source unknown) |

### 1.5 Timing of the "opening" odds (critical for the information cutoff)

[DOCS notes.txt / matches.php]: *"Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games"*, "Fridays afternoons generally not later than 17:00 British Standard Time … midweek fixtures are collected Tuesdays not later than 13:00." The CSV has **no per-row capture timestamp**, and these are **not true market-opening prices**. For a strict cutoff assume the snapshot is no later than Fri 17:00 UK (Fri-evening / Sat / Sun / Mon kickoffs) or Tue 13:00 UK (Tue–Thu kickoffs). Exceptions (postponed games, bank holidays) are [UNVERIFIED]. The closing-odds capture time is also [UNVERIFIED] (presumably near kickoff). Opening ≠ closing in practice: Pinnacle open equals close in 0 of 380 rows in 2024-25 [LIVE-A].

### 1.6 Cost analysis

| Item | Cost |
|---|---|
| football-data.co.uk CSVs | $0 |
| openfootball (CC0), FPL API, dcaribou datasets | $0 |
| Understat / FotMob (if approved) | $0 (curl), 0 Firecrawl credits |
| Firecrawl | **$0 for the recommended stack**; 18 credits used in this research |
| The Odds API free tier (forward Pinnacle snapshots) | $0, 500 credits/month [DOCS] |
| Jev inference for one season | ≈ **$0.02** upper bound: 380 matches × ≈1,130 input tokens (≈500-token state, **[INFERRED]** at 4 chars/token, + 20 questions × ≈31 tokens, from F024) × $0.042/Mtok |
| *Paid, only if needed* | The Odds API historical: **paid-only** [DOCS]; "10 × markets × regions" credits per request [DOCS]; one paid month ≈ $30 (**[UNVERIFIED]** agent estimate). Sportmonks 14-day trial / €29+ plans; TheStatsAPI $50/mo [3P]. All exceed the <$5/month rule, so documented not recommended. |

---

## 2. API Details

### 2.1 Endpoints we would use

| Purpose | Endpoint | Auth | Status |
|---|---|---|---|
| Results, stats, odds per season | `GET https://football-data.co.uk/mmz4281/{YYZZ}/E0.csv` | none | **[LIVE]** 200, `text/csv` |
| Upcoming fixtures + opening odds + referee | `GET https://football-data.co.uk/fixtures.csv` (overwritten each time; **no history**; **no Pinnacle columns**; closing cols empty) | none | **[LIVE]** 200, 94 cols, E0 = 10 rows (one matchweek) |
| Cross-check fixtures / kickoff (CC0) | `https://raw.githubusercontent.com/openfootball/football.json/master/2024-25/en.1.json`; repo `openfootball/england` has 2025-26 full text with starters/subs/referee for 380/380 | none | **[LIVE-A]**; openfootball vs football-data kickoff (Europe/London → UTC): 378/380 identical, scores 380/380 |
| Injury / availability flags, **current only** | `GET https://fantasy.premierleague.com/api/bootstrap-static/` (`status`, `news`, `news_added`, `chance_of_playing_next_round`; 195/667 players had `news` per **[LIVE-A]**) | none | HTTP 200, 1.78 MB **[LIVE]**; fields **[LIVE-A]** |
| Forward odds (Pinnacle) | `GET https://api.the-odds-api.com/v4/sports/soccer_epl/odds?regions=eu&bookmakers=pinnacle&markets=h2h,totals&oddsFormat=decimal&apiKey=…` (≈2 credits/call) | key (free) | **[UNVERIFIED]** with a key; unauthenticated call returns 401 [LIVE-A]. Docs say totals are "mainly available for US sports and bookmakers" [DOCS], so Pinnacle EPL totals are unproven |
| *(Gated)* team xG per match | `GET https://understat.com/getLeagueData/EPL/{year}` with header `X-Requested-With: XMLHttpRequest` (404 without it), `--compressed`; one call = 380 matches + 20 team histories | none | **[LIVE-A]**; saved response re-parsed by me: 380 matches with xG, history has `xG, xGA, npxG, npxGA, ppda, deep, xpts` |
| *(Gated)* shot-level xG | `GET https://understat.com/getMatchData/{match_id}` (match ids 2024: 26602–26981) | none | **[LIVE-A]**; 14 + 10 shots for 26602 verified in saved file |
| *(Gated)* possession, pass %, corners, cards, ratings, lineups | `GET https://www.fotmob.com/api/data/leagues?id=47&ccode3=GBR&season=2024%2F2025` and `…/api/data/matchDetails?matchId={id}` | none today (no `x-mas` token needed in 4 tests) | **[LIVE-A]**; values re-read by me from saved JSON (xG 2.43/0.44, possession 55/45) |
| *(Optional, needs signup)* injuries, as-of team stats, h2h | API-Football `v3.football.api-sports.io`: `/injuries?fixture=`, `/teams/statistics?…&date=`, `/fixtures/headtohead`, `/fixtures?ids=a-b-c` (≤20) | `x-apisports-key` | Docs via Firecrawl [DOCS]; unauthenticated 403 [LIVE-A]; **no live keyed calls** |

### 2.2 Rate limits summary

| Source | Limit | Meets ≥100 req/day? |
|---|---|---|
| football-data.co.uk | none documented (header says 1000) | Yes (we need ~2 req/day) |
| Understat / FotMob | none observed at ≤1 req/s | Yes, but **not contractually granted** |
| FPL API | none stated | Yes |
| The Odds API (free) | 500 credits/month ≈ 250 calls/month ≈ 8/day | **No for polling**; fine for ~daily forward snapshots |
| API-Football (free) | 100 requests/day [DOCS] | Exactly at the threshold |
| football-data.org (free) | 10 calls/min [DOCS]; anonymous `/matches` and `/standings` return **403** [LIVE] | Yes, but free historical depth is unknown |

---

## 3. Data Schema

The record separates **what may enter Jev's `state`** from **evaluation-only** and **label** blocks, so leakage is structurally hard. Every `home_team` / `away_team` value is computed **as-of `information_cutoff_utc`**.

### 3.1 Cutoff and as-of rules (design decisions, tested in §9)

| Rule | Value | Rationale |
|---|---|---|
| `information_cutoff_utc` | `kickoff_utc − 60 min` | Lineups become public ~1h before kickoff; nothing later is allowed |
| "Finished match" | `kickoff_utc + 150 min ≤ cutoff` | A 12:30 game must not count for a 14:00 cutoff even if it kicked off earlier |
| Kickoff time source | football-data `Date`+`Time` → `Europe/London` → UTC | Understat `datetime` is **not reliable** (see §8.2) |
| Table ordering | points, goal difference, goals for, then name | Close enough to PL rules except head-to-head tie-breaks at season end |
| Odds in `state` | **excluded by default** | Odds in the state anchor Jev to the market, destroying the comparison; run a "with-market" arm as a separate ablation |

### 3.2 Field map

| Path | Tier | Source | As-of rule | Availability |
|---|---|---|---|---|
| `match_id`, `competition`, `season` | 1 | derived | – | all |
| `kickoff_utc`, `kickoff_local_uk` | 1 | football-data `Date`,`Time` | known pre-match | 100% (2019-20 →) |
| `information_cutoff_utc`, `cutoff_rule` | 1 | derived | – | all |
| `referee` | 4 | football-data `Referee` | appointment known days before; historical file is the post-match record | 100% |
| `venue` | 4 | static club→stadium map (not in football-data) | static | **to build** |
| `team.league_position, matches_played, points, wins/draws/losses, goals_for/against, goal_difference` | 1 | computed from results | finished matches only | all seasons |
| `team.form_last5`, `home_form_last5` / `away_form_last5`, `last5/last10 goals_for/against_per_game` | 1 | computed | finished matches only | all |
| `head_to_head.last_meetings`, `meetings_found`, record, home-at-venue | 1 | computed from E0 history (football-data goes back to 1993; sample searched 2019-20 → 2024-25) | finished matches only | all |
| `team.shots_per_game`, `shots_on_target_per_game`, `shots_against_per_game`, `corners_per_game`, `yellow_cards_per_game`, `red_cards_total` | 2 | computed from `HS/AS/HST/AST/HC/AC/HY/AY/HR/AR` | earlier matches only | 100% |
| `team.season_xg_for/against`, `season_npxg_for`, `last5_xg_for/against` (+ `ppda`, `deep`, `xpts` available) | 2 | **Understat `teams[id].history`** (gated, Decision 1) | filter on football-data kickoff, never on Understat `date` | 2014/15 → now |
| `team.possession_percent`, `pass_completion_percent` | 2 | **FotMob** `matchDetails` (gated); no free ungated source | earlier matches only | optional; `null` in the sample |
| `team.avg_player_rating` | 2 | FotMob per-player ratings (heavy: 22 players × matches) | earlier matches only | **not recommended initially**; `null` |
| `team.days_since_last_league_match`, `last_league_match_utc` | 4 | computed | – | **league only; cups/Europe missing** |
| `team.key_injuries`, `team.manager` | 4 | injuries: no free as-of history (forward FPL snapshots only). Managers: dcaribou `games.*_manager_name` (2012-2025, frozen 2026-07-06) | – | `null` in the sample |
| `odds.pre_cutoff_opening` | 3 | football-data open columns | Fri/Tue snapshot (§1.5); `snapshot_not_later_than_utc` carried in record | Pinnacle: 2019-20 → 2024-25; fallback Bet365/Avg/Max/BFE |
| `odds.closing_EVALUATION_ONLY_after_cutoff` | 3 | football-data `C` columns | **post-cutoff; never in state** | as above |
| `odds.*.btts` | 3 | **none free** | – | always `null` |
| `labels_post_match_NEVER_IN_STATE` | – | `FTHG/FTAG/FTR`, Understat match xG | – | all |
| weather | 4 | none verified (Open-Meteo is a candidate, **[UNVERIFIED]**, not tested) | – | not in schema v0.1 |

Odds fields use decimal odds; devigged probabilities are proportional normalisation (Shin / power methods are alternatives to test). The full concrete record is in §9.

---

## 4. Alternative Sources

| Source | What | Free-tier facts | Verdict | Status |
|---|---|---|---|---|
| **openfootball** (GitHub, CC0) | fixtures, results, kickoff, 2025-26 lineups/referee/attendance | static files | **Supplement** (cross-check kickoff; 2025-26 lineups) | [LIVE-A] |
| **dcaribou/transfermarkt-datasets** (CC0 repo) | PL games 2012-2025 (380/season), manager names, referee, formation, attendance, dated player valuations, lineups | **updates paused; data ends 2026-07-06**; upstream Transfermarkt ToS bans bots/AI | **Supplement** for managers / valuations; **never use `home/away_club_position`** | [LIVE-A] downloads; position leak reproduced by the sub-agent (310/310 post-round), not re-run by me |
| **vaastav/Fantasy-Premier-League** | per-player GW xG/xA (2022-23 →), kickoff UTC, price | 2026-27 has GW1 only; `xP` column is look-ahead; `players_raw`/`teams.csv` are end-of-season snapshots (leaky) | **Backup xG proxy** (sum player xG per team; correlation with goals 0.50, **unvalidated** vs Understat) | [LIVE-A] |
| **FPL API** | live injury flags, fixtures | no limit stated; PL terms bar building a database from downloaded material without approval | **Use for forward injury snapshots only (grey)** | HTTP 200 [LIVE]; field details [LIVE-A] |
| **API-Football** (api-sports.io) | lineups, injuries (from Apr 2021), h2h, as-of `teams/statistics?date=`, player ratings; **no xG** | 100 req/day; free plan "limited in terms of available seasons" [DOCS]; one 3P report (2026-09-18) of "try from 2022 to 2024" | **Optional** (needs signup + season-window test); odds only 1–14 days pre-kickoff, 7-day history | [DOCS], unauthenticated 403 [LIVE-A] |
| **football-data.org v4** | fixtures, tables | 10/min; lineups need €29; odds add-on €15; anonymous 403 | **Weak**; free history depth unknown | [LIVE] 403; [DOCS] |
| **Sportmonks** | broad incl. xG | free plan = Danish Superliga + Scottish Premiership only; PL is 403 on free | **Paid only** | [DOCS], unauth 401 |
| **TheSportsDB** | basic | free key `3` returns **5 rows per query** | **Unusable free** | [LIVE-A] |
| **OpenLigaDB** | German-focused | PL data patchy (2023: 68 rows with epoch dates; 2024: none) | **Avoid** for PL | [LIVE] 200 for Bundesliga; PL [LIVE-A] |
| **ESPN hidden API** | box scores, lineups, odds | keyless but Disney ToS prohibits scraping / compiling data sets; scoreboard `form`/`records` look post-match | **Avoid** | [LIVE-A] |
| **Highlightly / TheStatsAPI / Goalserve / SportsDataIO** | commercial feeds | Highlightly 100 req/day, no free odds; TheStatsAPI $50/mo (7-day trial); Goalserve $150–550/mo; SportsDataIO trial scrambled | **Paid / skip** | [DOCS]/[3P] |
| **Kaggle** (all datasets above) | repackaged scrapes | Public page metadata readable without login; downloads need login (UNVERIFIED) | Prefer primary sources; the useful ones are `armin2080/premier-league-matches-dataset-2021-to-2025` (FBref xG, possession, 2021-2025 only, MIT label), `adamgbor/club-football-match-data-2000-2025` (ClubElo ratings; Bet365/Max odds only; **no Pinnacle**) | [LIVE-A] page JSON-LD |
| **StatsBomb open data** | event data | PL only 2003/04 and 2015/16 | **Irrelevant** for 2020-26 | [LIVE-A] |
| `jalapic/engsoccerdata`, `footballcsv/england`, Kaggle football-data mirrors | old results | stale; engsoccerdata is **missing PL 2022-23** | **Avoid** | [LIVE-A] |

---

## 5. Scraping Assessment

All tests were a handful of requests ≥1 s apart. Firecrawl was only needed to *test* the sites that block curl; none of the recommended sources need it.

| Site | Plain curl | Firecrawl | Data | As-of? | ToS / robots | Verdict |
|---|---|---|---|---|---|---|
| **Understat** | **Yes**, header `X-Requested-With: XMLHttpRequest` + `--compressed` | not needed | Per-match xG for all 380 matches (1 call); team histories (xG, xGA, npxG, PPDA, deep, xpts); shot-level xG per match; 2014/15 → now | Yes | `robots.txt` = `User-agent: *` / `Disallow: /` **[LIVE]**; no ToS page (404s) | **Primary xG candidate, gated on Decision 1** |
| **FotMob** | **Yes** via `/api/data/…` (old `/api/leagues` path 404s) | not needed | xG (open play / set play / xGOT), shots, SoT, possession, passes + accuracy, corners, cards, big chances, shotmap, lineups, ratings, unavailable list, referee | Yes (per-match pulls) | `robots.txt`: `Disallow: /api/*` for `*` **[LIVE-A, re-read by me from saved file]**; footer bans "systematic or regular use" | **Secondary / richer stats, gated** |
| **FBref** | **No**, 403 Cloudflare interactive challenge (even robots.txt) | 1 credit/page works | Schedule, scores, referee, basic team stats. **No xG, no pass accuracy** (verified on 2024-25 and 2021-22 schedule tables and a match page) | basic only | 10 req/min "jail"; data-use page bans AI/ML use and "supporting machine learning methods used to predict, classify, label, or score" | **Avoid** |
| **WhoScored** | No (403 Cloudflare) | 1 credit/page; full Opta `matchCentreData` (1,538 events) | events, ratings, team stats; **no xG field** | yes | ToS bans copying statistics; ratings need licence for betting/fantasy use | **Avoid** |
| **Sofascore** | No (403, even via Firecrawl for the API) | www HTML only | not reachable | n/a | ToS bans scraping | **Avoid** |
| **Transfermarkt** (direct) | `.de` / `.co.uk` yes; `.com` timed out from this network | not needed | squad values, **current** injuries, lineups, managers | injuries: snapshot only | ToS 11.1 bans bots/AI use | **Avoid direct; use dcaribou** |
| **Crawlee / Parsebot** | – | – | Crawlee's own tip #1: "check for an official API or hidden JSON endpoint… try a plain HTTP client before a browser". Its anti-blocking tooling (fingerprints, session pools, tiered proxies) would only matter for the Cloudflare-challenged sites, which are either xG-less (FBref, WhoScored) or ToS-forbidden (Sofascore). **Parsebot** most likely = parse.bot (YC F25), an AI agent that reverse-engineers a site's network calls into a REST endpoint (~$30/mo [3P]); it doesn't solve the legal question. | **Not useful here** |

**The FBref / Opta situation.** Sports Reference announced on 2026-01-20 that its data provider terminated access and required deletion; xG, xA, PSxG, progressive actions and shot-creating actions were removed. I could not fetch the primary post (403); sourced from Awful Announcing (2026-01-23), a Substack (2026-01-22) and a data guide [3P]. **Verified live by the scraping agent**: no xG columns on the FBref 2024-25 or 2021-22 schedule tables and none on a match page.

**Firecrawl cost model.** Measured ≈ 1 credit per page. FBref or WhoScored for a season ≈ 380–420 credits, affordable under the 10k plan but pointless (no xG, forbidden/ToS-blocked). Understat, FotMob, FPL, football-data.co.uk and dcaribou cost **0** credits.

**Recommended scraping stack (if Decision 1 approves xG):** a polite sequential script (`curl`/`httpx`, ≤1 req/s, retries with backoff, UA identifying the research project), every response cached raw to disk and never re-fetched, each match fetched once after full time. Expect ~7 minutes per season for Understat (1 + 380 requests).

---

## 6. Odds Sources

| Source | Free historical? | Opening / closing | Pinnacle | Markets | Verdict |
|---|---|---|---|---|---|
| **football-data.co.uk** | **Yes**, 1993 → now (Pinnacle from 2012/13) | Fri/Tue snapshot + closing | Yes **2019-20 → 2024-25**; degraded 2025-26; absent 2026-27 | 1X2, O/U 2.5, Asian handicap; **no BTTS** | **Primary for historical** [LIVE] |
| **The Odds API** | **No** ("only available on paid usage plans", from 2020-06-06, 10-min snapshots, `10 × markets × regions` credits) [DOCS, fetched by me] | derivable if paid | `pinnacle` listed under `eu` per sub-agent [DOCS]; "Odds are from public website which may incur a delay" | `h2h`, `spreads`, `totals`, `outrights`; **BTTS not mentioned** in the guide pages I read | **Forward snapshots on free tier** (500 credits/mo). Terms (updated 2026-08-31) explicitly permit "research papers", "Storing our data and retaining it indefinitely" and "train statistical and machine learning models" **[DOCS, fetched by me]**; only reselling as a standalone feed is banned. **Clearest ToS in the batch.** |
| **API-Football** | No (1–14 days pre-kickoff, 7-day history) | no | listed (id 4) | 1X2, O/U, BTTS | Forward only; requires signup |
| **OddsPapi** | claimed rolling ~8-month window, free limit sources conflict (250/mo vs 5,000/mo), docs say B2B | price timeline | `pinnacle` slug | 1X2, totals, AH; no BTTS listed | **Unconfirmed**; optional free-account test |
| **Betfair Historic Data** | free "Basic" 1-min last-traded price, ~2016 → [3P] | exchange | no (exchange) | soccer covered; markets unverified | **Unreachable from this machine**; needs login |
| **Pinnacle direct** | – | – | – | – | Public API closed 2025-07-23 per sub-agent reading of Pinnacle's page (**not independently verified by me**: the page fetch failed; corroborated by football-data's notice). Sub-agent also reports the page invites academic / pregame-handicapping requests to api@pinnacle.com: worth one email. |
| **OddsPortal** | – | – | – | – | **Do not scrape** (ToS bars aggregating/scraping/automated requests) |
| **Odds-API.io** | – | – | paid plans only | – | free keys "paused indefinitely"; paid ≥ $65/mo |

**Answer: where do we get Pinnacle-grade pre-match odds?**

- **Historical 1X2 + O/U 2.5:** football-data.co.uk Pinnacle columns, **2019-20 → 2024-25** (verified). Not true opening; no BTTS.
- **Historical true opening + closing:** only a paid The Odds API month (≈$30, unverified), or the Pinnacle academic route.
- **Forward (2026-27 →):** The Odds API free key polled daily with `bookmakers=pinnacle` (needs your signup; whether Pinnacle returns EPL totals is untested), plus our own **timestamped archiving of `fixtures.csv` every Friday and Tuesday**, the only way to get a dated opening line for free.
- **Sharp-ish fallback for 2025-26 and 2026-27** (no usable Pinnacle): **Betfair Exchange closing** (`BFECH/D/A`, 94.2% in 2025-26) and **market average closing** (`AvgCH/D/A`, 100%; note Avg stopped including Pinnacle after 2025-07-23, so cross-season Avg isn't like-for-like).
- **BTTS:** no free source; skip BTTS in the market comparison.

---

## 7. Integration Plan

**Step 0. Decisions** (§0): xG appetite, football-data author email, optional signups, contamination plan.

**Step 1. Raw layer (immutable).** `data/raw/football-data/E0_{season}_{fetchUTC}.csv` + `.sha256`; `data/raw/football-data/fixtures_{fetchUTC}.csv` archived **every Friday and Tuesday** (gives dated opening snapshots going forward); daily `data/raw/fpl/bootstrap-static_{fetchUTC}.json` (injury flags exist only as snapshots). If Decision 1 approves: `data/raw/understat/getLeagueData_EPL_{year}_{fetchUTC}.json` and per-match files. Version everything; football-data re-publishes back-seasons.

**Step 2. Normalise.** Canonical team names (football-data's naming) with a mapping table. Mapping for the 2024-25 clubs from Understat was built and verified (380/380 fixtures paired): Manchester United→Man United, Manchester City→Man City, Newcastle United→Newcastle, Nottingham Forest→Nott'm Forest, Wolverhampton Wanderers→Wolves, others identical. Other sources differ again (openfootball: "Manchester United FC", "Brighton & Hove Albion FC"; FPL: "Man Utd", "Spurs"; Transfermarkt: "Fulham FC"). The 30 distinct football-data names across 2019-20 → 2026-27 add Burnley, Coventry, Hull, Leeds, Luton, Norwich, Sheffield United, Sunderland, Watford, West Brom [LIVE-A]. Convert `Date`+`Time` with `zoneinfo("Europe/London")` → UTC.

**Step 3. As-of feature builder.** Implement exactly the rules in §3.1. Required tests (the prototype in §9 passes the first two):
1. *Table reconstruction*: a full-season as-of table equals the final table (done: all 20 teams' 2024-25 points identical to Understat's independent per-match `pts`, and the as-of table at the sample cutoff matches Understat for 20/20 teams on points and games played).
2. *Kickoff agreement* across sources (done: Understat vs football-data 370/380, see §8.2).
3. *Leakage test*: replace all results after the cutoff with garbage and assert the state is byte-identical.
4. *Early-season behaviour*: matchweeks 1–5 have short form windows; decide a minimum matchweek (recommend ≥ 6) or add prior-season carry-over.

**Step 4. Odds layer.** Attach `odds.pre_cutoff_opening` (with `snapshot_not_later_than_utc`) and `odds.closing_EVALUATION_ONLY_after_cutoff`. Devig (proportional first; try Shin). Use Pinnacle where `PSH` is present (2019-20 → 2024-25), otherwise `BFE`/`Avg`. **Report results separately for Pinnacle-era and later seasons.**

**Step 5. State constructor.** JSON state (F019: JSON and prose are behaviorally equivalent, so JSON is safe), fixed key order, **no odds, no labels**, **omit fields that are unavailable rather than passing `null`** (F021: Jev treats missing info as an ambiguous low-but-nonzero Noul, so don't make it guess what a `null` means), consistent across matches. The derived state for the §9 sample is 2,024 compact characters, **≈500 tokens (INFERRED at 4 chars/token; Jev's tokenizer wasn't measured)**; the 32k state+question limit is nowhere near. Include a one-line `note` stating that table/form/xG are league-only (the cup/European gap in §8.6 is known to the model, not hidden).

**Step 6. Questions (proposal, for Experiment 020 design).** Fixed literal wording (F017: literal phrasings tracked ground truth, "likely/evidence" phrasings inflated; F025: avoid meta-language in criteria), e.g. `Will the home team win this match?`, `Will this match end in a draw?`, `Will the away team win this match?`, `Will this match have more than 2.5 total goals?`. Batch them in one request (F024: ≤20 per request, sublinear tokens). Remember F027's ~0.04 conservative bias was measured on balls-in-a-bag, so it needs its own football calibration, not a blind +0.04 shift. Noul answers for home/draw/away are independent questions, so they will not necessarily sum to 1 (expected, **untested**); renormalise and report both raw and renormalised scores.

**Step 7. Evaluation.** Brier and log-loss vs (a) devigged Pinnacle **opening** (information roughly comparable, earlier) and (b) devigged Pinnacle **closing** (the stronger benchmark; incorporates information up to kickoff), plus constant, Elo and Poisson baselines; calibration curve; ROI only as a secondary diagnostic.

**Step 8. Request budget.** Backfill of 6 football-data seasons = 6 requests. Forward operation: `fixtures.csv` ×2/week, FPL daily, The Odds API ≤ 8 calls/day. All inside every limit in §2.2.

**Where this goes in the repo (from the research plan):** `docs/data-sources.md` (condensed from this file), `src/data/` (fetch + normalise + as-of builder), Experiment 020.

---

## 8. Limitations & Caveats

1. **Pinnacle gap.** Reliable only 2019-20 → 2024-25. 2025-26: 210/380 rows, and degraded even where present. 2026-27: none. [LIVE]
2. **Understat kickoff times are unreliable.** `datetime` is UTC for 370/380 of 2024-25 matches, but **9 midweek matches on 1–2 Apr 2025 store UK local time as if UTC (+60 min)** and **Aston Villa v Liverpool (19 Feb 2025) shows a stale 15:00 placeholder vs the real 19:30** [LIVE: my comparison of saved Understat data vs football-data]. Always take kickoff from football-data and join Understat by team pair / calendar date.
3. **xG provider choice changes the numbers**: for the 2024-25 opener Understat has 2.04 / 0.42 and FotMob 2.43 / 0.44 [LIVE-A]. Pick one provider for all matches. Whether Understat retroactively revises past xG is [UNVERIFIED]; fetched values are "as of fetch time", not "as displayed before the next match".
4. **Understat page format changed twice in Nov–Dec 2025**; FotMob can add `x-mas` token requirements at any time; dcaribou is paused (data ends 2026-07-06); vaastav 2026-27 has only GW1. Build the pipeline to cache raw responses and to fail loudly.
5. **Leakage traps (verified or reported):** Understat `dates[].forecast` (post-match simulation) and season aggregates in `players` / `statistics`; FotMob `h2h.matches` (includes future fixtures) and `marketValue` (as-of unclear); Transfermarkt/dcaribou `home/away_club_position` (reproduced as the table **after** the round, 310/310 from matchday 8; matches the pre-match table only 84/310); vaastav `xP` column, `players_raw.csv`, `teams.csv` (end-of-season snapshots); ESPN `form`/`records`; football-data match stats and **closing odds** (post-match / post-cutoff by definition).
6. **League-only context.** Form, xG, `days_since_last_league_match` and fatigue ignore cup and European fixtures. A "7.0 days rest" for a team that played in the Champions League 3 days ago is wrong. dcaribou `games` may include other competitions (UNVERIFIED); FotMob team pages might. Flag in the state `note`.
7. **No historical injuries / lineups with as-of dates.** FPL `news`/`chance_of_playing` are current-only (start archiving now). Lineups are public only ~1 h pre-kickoff: sources are post-match records (dcaribou `game_lineups` for 2020-25; openfootball full file for 2025-26). API-Football `/injuries` (from Apr 2021) as-of semantics are [UNVERIFIED].
8. **Opening odds are a Fri/Tue snapshot, not market open.** Also not timestamped per row (§1.5).
9. **No BTTS odds** free; Pinnacle BTTS not found anywhere.
10. **Possession, pass completion, player ratings** have no free ungated source; FotMob only (gated). Ratings are post-match and heavy: not recommended initially.
11. **Legal posture per source** (none explicit for our use except The Odds API and CC0 repos):

| Source | Posture |
|---|---|
| The Odds API | Research and ML training explicitly permitted [DOCS] |
| openfootball | CC0 |
| dcaribou | CC0 repo over Transfermarkt-derived data; upstream ToS bans bots/AI |
| football-data.co.uk | "private individuals only"; robots block AI crawlers; contact author |
| FPL API | PL terms bar creating databases from downloaded material without approval (grey) |
| Understat | robots.txt `Disallow: /`, no ToS |
| FotMob | robots.txt `Disallow: /api/*`, footer bans automated systematic use |
| FBref, Transfermarkt, WhoScored, Sofascore, ESPN, OddsPortal | Explicit bans: avoid |

12. **Possible memorization / contamination.** Jev's docs state no training cutoff (verified: docs.typesafe.ai/models says only "Jev is not trained on customer requests or responses" and "English is the primary training language"). Match results for 2019-2025 may be in its training data, and the state contains real team names and dates. Mitigations to design into Experiment 020: (a) a no-state probe ("Who won Liverpool v Man United on 2025-01-05?") to detect memorization; (b) anonymised-teams arm (Team A / Team B, relative dates); (c) holdout on 2025-26 / 2026-27, **but** those seasons lack Pinnacle, so use Betfair Exchange closing / Avg closing as the benchmark there, and carry the Pinnacle-era results as a separate, possibly contaminated, arm.
13. **Season-boundary / early-season effects**: no promoted-club priors, no prior-season carry-over in the prototype; short form windows in matchweeks 1–5.
14. **Odd kickoff times** (e.g. 14:05, 15:15) exist in 2025-26 and agree between sources; two games differed by 10–15 min between football-data and openfootball [LIVE-A].
15. **Weather, manager head-to-head, travel distance, referee card rates** not sourced in this research; referee card rates are computable from the E0 history (`HY/AY/HR/AR` by `Referee`).

---

## 9. Sample Match Record

Real match: **Liverpool 2–2 Manchester United, 2025-01-05 16:30 UTC**, built by a prototype script (kept in `/tmp`, not in the repo) from football-data E0 files 2019-20 → 2024-25 (downloaded 2026-10-13) and the Understat `getLeagueData/EPL/2024` response saved 2026-10-12.

**Prototype self-checks (all passed):**
- As-of table reconstruction: final 2024-25 table points match Understat's independent per-match `pts` for 20/20 teams; the as-of table at this cutoff matches for 20/20 teams on points **and** games played.
- Odds fields equal the raw football-data row (Pinnacle open 1.29/6.14/9.37; close 1.36/5.55/8.55; O/U 2.5 open 1.43/2.88; close 1.53/2.62).
- Liverpool 18 games vs Man United 19 matches Understat's independent per-match count, so it is not a builder bug (presumably the postponed Merseyside derby; not checked).
- xG windows use football-data kickoff times for the as-of gate (see §8.2).

```json
{
  "schema_version": "0.1-research",
  "match_id": "epl|2024-25|20250105|Liverpool|Man_United",
  "source_refs": {
    "football_data": "E0/2024-25 csv line 199",
    "understat_match_id": "26797"
  },
  "competition": "Premier League",
  "season": "2024-25",
  "kickoff_utc": "2025-01-05T16:30:00Z",
  "kickoff_local_uk": "2025-01-05 16:30 GMT",
  "information_cutoff_utc": "2025-01-05T15:30:00Z",
  "cutoff_rule": "kickoff - 60 min; a match is 'finished' only if kickoff + 150 min <= cutoff",
  "referee": "M Oliver",
  "venue": "Liverpool home ground (stadium name not in football-data)",
  "home_team": {
    "name": "Liverpool",
    "understat_team_id": "87",
    "league_position": 1,
    "matches_played": 18,
    "points": 45,
    "wins": 14,
    "draws": 3,
    "losses": 1,
    "goals_for": 45,
    "goals_against": 17,
    "goal_difference": 28,
    "form_last5": "DDWWW",
    "last5_goals_for_per_game": 3.8,
    "last5_goals_against_per_game": 1.8,
    "last10_goals_for_per_game": 3.0,
    "last10_goals_against_per_game": 1.4,
    "home_form_last5": "WWWDW",
    "season_xg_for": 46.23,
    "season_xg_against": 17.86,
    "season_npxg_for": 43.19,
    "last5_xg_for": 14.72,
    "last5_xg_against": 4.75,
    "last5_matches_xg_window": ["2024-12-04", "2024-12-14", "2024-12-22", "2024-12-26", "2024-12-29"],
    "shots_per_game": 16.5,
    "shots_on_target_per_game": 6.94,
    "shots_against_per_game": 9.67,
    "corners_per_game": 6.56,
    "yellow_cards_per_game": 2.17,
    "red_cards_total": 1,
    "possession_percent": null,
    "pass_completion_percent": null,
    "avg_player_rating": null,
    "days_since_last_league_match": 7.0,
    "last_league_match_utc": "2024-12-29T17:15:00Z",
    "key_injuries": null,
    "manager": null
  },
  "away_team": {
    "name": "Man United",
    "understat_team_id": "89",
    "league_position": 14,
    "matches_played": 19,
    "points": 22,
    "wins": 6,
    "draws": 4,
    "losses": 9,
    "goals_for": 21,
    "goals_against": 26,
    "goal_difference": -5,
    "form_last5": "LWLLL",
    "last5_goals_for_per_game": 0.8,
    "last5_goals_against_per_game": 2.2,
    "last10_goals_for_per_game": 1.3,
    "last10_goals_against_per_game": 1.5,
    "away_form_last5": "LDLWL",
    "season_xg_for": 29.49,
    "season_xg_against": 31.05,
    "season_npxg_for": 27.97,
    "last5_xg_for": 7.16,
    "last5_xg_against": 6.19,
    "last5_matches_xg_window": ["2024-12-07", "2024-12-15", "2024-12-22", "2024-12-26", "2024-12-30"],
    "shots_per_game": 13.26,
    "shots_on_target_per_game": 4.68,
    "shots_against_per_game": 10.84,
    "corners_per_game": 4.84,
    "yellow_cards_per_game": 2.21,
    "red_cards_total": 2,
    "possession_percent": null,
    "pass_completion_percent": null,
    "avg_player_rating": null,
    "days_since_last_league_match": 5.9,
    "last_league_match_utc": "2024-12-30T20:00:00Z",
    "key_injuries": null,
    "manager": null
  },
  "head_to_head": {
    "seasons_searched": ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"],
    "last_meetings": [
      {"date": "2024-09-01", "home": "Man United", "away": "Liverpool", "score": "0-3"},
      {"date": "2024-04-07", "home": "Man United", "away": "Liverpool", "score": "2-2"},
      {"date": "2023-12-17", "home": "Liverpool", "away": "Man United", "score": "0-0"},
      {"date": "2023-03-05", "home": "Liverpool", "away": "Man United", "score": "7-0"},
      {"date": "2022-08-22", "home": "Man United", "away": "Liverpool", "score": "2-1"}
    ],
    "meetings_found": 11,
    "this_team_orientation_record_last5": {"Liverpool_wins": 2, "draws": 2, "Man United_wins": 1},
    "home_team_home_meetings_last5_at_this_venue": ["0-0", "7-0", "4-0", "0-0", "2-0"]
  },
  "odds": {
    "pre_cutoff_opening": {
      "snapshot_rule": "Friday<=17:00 UK",
      "snapshot_not_later_than_utc": "2025-01-03T17:00:00Z",
      "pinnacle_1x2": {"home": 1.29, "draw": 6.14, "away": 9.37},
      "pinnacle_1x2_implied_devigged": {"home": 0.742, "draw": 0.1559, "away": 0.1021, "overround": 1.0448},
      "pinnacle_over_under_2_5": {"over": 1.43, "under": 2.88},
      "bet365_1x2": {"home": 1.29, "draw": 6.25, "away": 8.0},
      "market_avg_1x2": {"home": 1.29, "draw": 6.05, "away": 9.49},
      "asian_handicap_line_home": -1.75,
      "btts": null
    },
    "closing_EVALUATION_ONLY_after_cutoff": {
      "pinnacle_1x2": {"home": 1.36, "draw": 5.55, "away": 8.55},
      "pinnacle_1x2_implied_devigged": {"home": 0.7122, "draw": 0.1745, "away": 0.1133, "overround": 1.0324},
      "pinnacle_over_under_2_5": {"over": 1.53, "under": 2.62},
      "asian_handicap_line_home": -1.5,
      "btts": null
    }
  },
  "labels_post_match_NEVER_IN_STATE": {
    "ft_home_goals": 2,
    "ft_away_goals": 2,
    "ftr": "D",
    "ht": "0-0",
    "shots": "19-13",
    "understat_xg": {"h": "2.862", "a": "1.67469"}
  }
}
```

**Derived Jev `state`** (odds, labels, source refs, internal ids, null fields removed; 2,024 characters compact, ≈500 tokens **[INFERRED]**). The `xg` fields are present only on the "with-xG" arm; delete the five `*_xg_*` keys per team for the clean-stack arm.

```json
{
  "match": {
    "competition": "Premier League", "season": "2024-25",
    "kickoff_utc": "2025-01-05T16:30:00Z", "information_cutoff_utc": "2025-01-05T15:30:00Z",
    "referee": "M Oliver",
    "note": "league table, form, goals and xG are league-only and computed from matches finished before the information cutoff"
  },
  "home_team": {
    "name": "Liverpool", "league_position": 1, "matches_played": 18, "points": 45,
    "wins": 14, "draws": 3, "losses": 1, "goals_for": 45, "goals_against": 17, "goal_difference": 28,
    "form_last5": "DDWWW", "last5_goals_for_per_game": 3.8, "last5_goals_against_per_game": 1.8,
    "last10_goals_for_per_game": 3.0, "last10_goals_against_per_game": 1.4, "home_form_last5": "WWWDW",
    "season_xg_for": 46.23, "season_xg_against": 17.86, "season_npxg_for": 43.19,
    "last5_xg_for": 14.72, "last5_xg_against": 4.75,
    "shots_per_game": 16.5, "shots_on_target_per_game": 6.94, "shots_against_per_game": 9.67,
    "corners_per_game": 6.56, "yellow_cards_per_game": 2.17, "red_cards_total": 1,
    "days_since_last_league_match": 7.0
  },
  "away_team": {
    "name": "Man United", "league_position": 14, "matches_played": 19, "points": 22,
    "wins": 6, "draws": 4, "losses": 9, "goals_for": 21, "goals_against": 26, "goal_difference": -5,
    "form_last5": "LWLLL", "last5_goals_for_per_game": 0.8, "last5_goals_against_per_game": 2.2,
    "last10_goals_for_per_game": 1.3, "last10_goals_against_per_game": 1.5, "away_form_last5": "LDLWL",
    "season_xg_for": 29.49, "season_xg_against": 31.05, "season_npxg_for": 27.97,
    "last5_xg_for": 7.16, "last5_xg_against": 6.19,
    "shots_per_game": 13.26, "shots_on_target_per_game": 4.68, "shots_against_per_game": 10.84,
    "corners_per_game": 4.84, "yellow_cards_per_game": 2.21, "red_cards_total": 2,
    "days_since_last_league_match": 5.9
  },
  "head_to_head": {
    "last_meetings": [
      {"date": "2024-09-01", "home": "Man United", "away": "Liverpool", "score": "0-3"},
      {"date": "2024-04-07", "home": "Man United", "away": "Liverpool", "score": "2-2"},
      {"date": "2023-12-17", "home": "Liverpool", "away": "Man United", "score": "0-0"},
      {"date": "2023-03-05", "home": "Liverpool", "away": "Man United", "score": "7-0"},
      {"date": "2022-08-22", "home": "Man United", "away": "Liverpool", "score": "2-1"}
    ]
  }
}
```

---

## 10. Expansion: top-5 leagues + UCL (added 2026-10-18)

Scope: EPL, La Liga, Bundesliga, Serie A, Ligue 1 and the Champions League, so that a club's UCL match can be read through its domestic strength. Tags as in §0. The UCL/cross-league sub-agent evidence is **[LIVE-A]** (scratch in `/tmp/phase4-research/ucl/`).

### 10.1 Collection layer and what is on disk

Code is in `src/data/` (cached, rate-limited, resumable; stops on 403/429): `http.py`, `footballdata.py`, `understat.py`, `fotmob.py`, `teams.py`, `snapshots.py`, `cli.py`. Raw responses live in gitignored `data/raw/`, each with a `.meta.json` (url, fetched_at, sha256); a refetch that changes content archives the old copy as `<file>@<fetched_at>`. 43 tests pass. Commands: `python -m src.data.cli {footballdata|understat-leagues|understat-matches|fotmob-leagues|fotmob-matches|snapshot|status}`.

| Layer | Coverage | State (2026-10-18) |
|---|---|---|
| football-data.co.uk CSVs | 5 leagues × 2014-15 → 2026-27 (65 files) | done **[LIVE]** |
| Understat league files (match xG, team histories) | same 65 league-seasons | done **[LIVE]** |
| FotMob fixture lists | 5 leagues + UCL × 2014/15 → 2026/27 (78 files, 23,570 finished matches) | done **[LIVE]** |
| FotMob fixture lists, rating-only competitions | Süper Lig, Liga Portugal, Eredivisie, Scottish Premiership, Belgium, Greece, Austria, Norway, Czech, Ukraine, Switzerland, Denmark, UEL, UECL (IDs verified by name **[LIVE]**) | done: 175 files, 40,442 finished matches across the 12 feeder leagues + UEL/UECL (13 seasons each; UECL 6, Norway 14 calendar-year seasons) **[LIVE]** |
| FotMob `matchDetails` | 11,971 finished matches from 2020/21 (xG era) | **done** 2026-10-18: 0 missing, 0 corrupt, 0 id mismatches; xG in 11,968, shot map in 11,969, ratings in 11,969, possession and referee 100% **[LIVE]**, 3.2 GB |
| FotMob `matchDetails` 2014-2019 | ~9k matches: possession/passes/ratings, **no xG** | running (log: `logs/chain-refresh-and-2014-2019.log`) |
| Understat shot-level (`getMatchData`) | optional; FotMob has shot-level xG from 2020 | not started |
| 538 SPI archive | 68,913 rows, `data/raw/spi/spi_matches_wayback_20250306.csv` | done **[LIVE]** |
| Forward snapshots | ESPN odds, football-data `fixtures.csv`, FPL injury feed, ClubElo current ratings | first snapshot taken **[LIVE]** |

### 10.2 football-data.co.uk across the five leagues [LIVE, parsed by `src/data/footballdata.py`]

- Pinnacle open **and** close 1X2 present for **20,712 matches** in total. Closing is 100% in every league through 2024-25; 2025-26 is ~46–55% by league (the 2025-07-23 Pinnacle feed problem is not Premier League-specific); 2026-27 has none.
- **`Time` is UK local time in every league** (not league-local): converting as `Europe/London` matched FotMob UTC kickoffs in 379/380 (La Liga), 305/306 (Bundesliga), 378/380 (Serie A), 306/306 (Ligue 1) in 2024-25; the league-local hypothesis matched none.
- **No kickoff time before 2019-20** and no Pinnacle O/U columns under the `P>2.5` names before then (older bookmaker columns have different names). Kickoff for 2014-2018 must come from FotMob fixture lists.
- **`Referee` exists only in the English files.** Other leagues need FotMob (`matchFacts.infoBox.Referee`, all seasons **[LIVE-A]**).
- Ligue 1 2019-20 has 279 rows (COVID curtailment); Bundesliga and Ligue 1 have 306 matches per season (18 teams), Ligue 1 380 before 2023-24.

### 10.3 FotMob depth per competition [LIVE, one match per season and competition; 2016-2020 re-sampled by sub-agent]

| Data | Earliest season |
|---|---|
| Possession, shots, lineups, referee | 2014/15 (lineups/ratings 2016/17) |
| Pass accuracy, player ratings | 2016/17 |
| **xG, xGOT, shot map** | **2020/21 in all six competitions** (Ligue 1 2018/19 has it only as a stray) |
| Bookmaker odds | never present (`oddspoll` is a fan poll) |

Payloads are 130–300 KB for 2016+ matches. **`content.h2h` leaks the future** (computed at fetch time, includes later seasons and unstarted fixtures **[LIVE-A]**); `table` is final/current only, not as-of. Filter fixtures with `status.reason.shortKey` and `cancelled`, not `finished` alone (EPL 2023/24 lists an abandoned Bournemouth v Luton match and its replay).

### 10.4 Cross-league linkage

- **Canonical key = FotMob team id.** It is shared across domestic leagues, UCL, UEL, UECL (Galatasaray is 8637 in both Süper Lig and UCL **[LIVE-A]**).
- `src/data/teams.py` links football-data names and Understat titles to FotMob ids by joining matches on (date, score) and voting; ambiguous keys are skipped. **[LIVE]**: every football-data name in all five leagues over 13 seasons is mapped; Understat is fully mapped too, with one real quirk (Understat renamed "Parma" to "Parma Calcio 1913", kept as aliases).
- UCL clubs outside the top five (Galatasaray, Benfica, PSV, Celtic, etc.) are covered by their domestic leagues in the rating-only list above. Of 2026/27's 36 UCL league-phase clubs, 28 are covered by the first 10 leagues probed; the extra leagues close most of the rest (Greece, Austria, Norway, Czech, Ukraine, Switzerland, Denmark) **[LIVE-A]**, not recomputed.
- Hard name cases from the sub-agent (e.g. Inter vs "Internazionale", "Ath Madrid", "FC Koln", "Paris SG", Understat "RasenBallsport Leipzig") are handled by the match-join, not by fuzzy name matching.
- Calendar-year leagues (e.g. Norway) use season labels like `2016`, not `2016/2017`; handle that when parsing.

### 10.5 Cross-league strength: what is and is not available

| Source | Verdict |
|---|---|
| **ClubElo CSV API** | **Dead.** `api.clubelo.com` returns 502/timeouts since ~2026-09-01 and is reported moved behind authentication (soccerdata#977); the site was redesigned and recalibrated **[LIVE-A]**; I also saw 502 **[LIVE]**. The site shows **current** ratings only (`/Ranking`, ~498 clubs) and per-club charts from ~2022-10 whose pre/post-match semantics are unverified. Archive `/Ranking` daily via `snapshot`. |
| **538 SPI archive** (Wayback `spi_matches.csv`) | **Best as-of cross-league source for 2016 → 2023-06**: per-match `spi1/spi2`, win probabilities, projected scores, and `xg/nsxg` for UCL 2016-2022 (868 of 869 matches). Frozen; no later data. **[LIVE]** downloaded. Sanity check: 3-class Brier of its pre-match probabilities is 0.56–0.59 per league vs ≈0.64 for a constant-frequency baseline, consistent with genuine pre-match forecasts (plausibility, not proof). **Caveat:** UCL knockout rows show `probtie = 0`, so those probabilities probably describe advancement, not 90-minute results. Team names need mapping to FotMob ids. |
| **Self-computed rating** (recommended) | Elo / Bayesian rating from FotMob results across 17+ domestic leagues and UCL/UEL/UECL, linked by team id, strictly as-of. Warm-start or benchmark against SPI (2016-2023); use UEFA country coefficients (kassiesa.net) as a league-strength prior. |
| Opta Power Rankings, footballdatabase.eu | Not usable as-of (client-rendered / unexplored) |

### 10.6 UCL specifics [LIVE-A unless noted]

- FotMob UCL fixture list: 125 matches per old-format season (119 in 2019/20), 189 in 2024/25 and 2025/26 (144 league phase + 16 playoff + 16 + 8 + 4 + 1); 2026/27 currently 144 (36 finished) **[LIVE]**. Qualifying rounds are not included.
- `scoreStr` is the 90/120-minute score. Penalties and aggregates are only in `matchDetails.header.status` (`reason.penalties`, `aggregatedStr`, `whoLostOnPenalties`); two-legged ties via `matchFacts.infoBox.legInfo`. `reason.shortKey` distinguishes `fulltime_short`, `afterextratime_short`, `penalties_short`.
- openfootball/champions-league (CC0): `cl.txt` for 2011-12 → 2025-26 (no 2026-27), plain text, CET/CEST wall-clock kickoffs with no UTC offset; use FotMob `utcTime` for kickoff.
- football-data.co.uk has **no UCL or Europe page**, but does cover Netherlands, Belgium, Portugal, Turkey, Greece and Scotland domestic leagues with odds (feeder leagues for cross-league work).

### 10.7 Odds for the expanded scope

- **Historical Pinnacle:** 2019-20 → 2024-25 for the five leagues via football-data (§1.3). No free historical UCL odds found anywhere. The Odds API historical is paid (from 2020-06-06; ~$30/month plan; ~3,000 credits estimated for six seasons of UCL closing snapshots; Pinnacle coverage for UCL history **unverified**). OddsPapi claims free timestamped Pinnacle history (UCL tournamentId 7) **[DOCS only]**; depth and limits untested, needs a key.
- **Forward (the only free dated odds history we can build):** `snapshot` archives ESPN scoreboard JSON (DraftKings 1X2, totals, spread, open and close; **not Pinnacle**) for UCL and all five leagues. First snapshot: 63 upcoming matches, all with odds **[LIVE]**. ESPN has no odds for completed events and takes one date per request. The Odds API sport keys (all six confirmed in its docs): `soccer_epl`, `soccer_spain_la_liga`, `soccer_germany_bundesliga`, `soccer_italy_serie_a`, `soccer_france_ligue_one`, `soccer_uefa_champs_league`; `/v4/sports` and `/events` are free of quota **[DOCS]**; 500 credits/month free; whether the free tier returns Pinnacle is unverified.
- **Schedule the snapshots**, e.g. `0 */6 * * * cd /home/bipin/jev-api-experiments && .venv/bin/python -m src.data.cli snapshot >> logs/snapshot.log 2>&1` (not installed; add it to crontab if wanted). Each run is ~33 requests.

### 10.8 Remaining work and unverified items

- Not yet fetched: FotMob 2014-2019 `matchDetails`; Understat shot-level; the Odds API / OddsPapi (need keys).
- Not built yet: feature builder across leagues, the self-computed rating, SPI-to-FotMob name mapping, parsers for FotMob `matchDetails` and ESPN odds.
- Unverified: whether SPI's ratings are strictly pre-match (only the Brier sanity check), whether FotMob xG coverage is complete within 2020/21 and 2021/22 (spot-checked), ClubElo per-club chart semantics, OddsPapi depth, The Odds API free-tier Pinnacle coverage.

---

## 11. Derived tables and as-of features (added 2026-10-18)

Code: `src/data/tables.py` (raw → parquet tables), `src/features/asof.py` (as-of feature engine), `src/features/build.py`. Commands: `python -m src.data.cli build-tables` then `build-features`; the daily job runs both after fetching. Outputs go to `data/derived/` (git-ignored, rebuildable). 71 tests pass.

### 11.1 Tables (`data/derived/*.parquet`) [LIVE, built from the raw cache]

| Table | Rows (2026-10-18) | Content |
|---|---|---|
| `matches` | 63,833 | every finished match of all 20 collected competitions, FotMob id as key, kickoff UTC, final and 90-minute goals, `decided_by`, referee/attendance/stadium where details exist |
| `team_stats` | ~30k (2 per match with details) | 36 FotMob stats per team-match (xG family, shots, possession, passes, duels, cards, ...), formation, coach, lineup rating |
| `players` | ~617k | per-match squad: starter flag, position, rating, sub minutes |
| `shots` | ~303k | shot-level xG, xGOT, coordinates, situation (2020/21 onward) |
| `odds` | 21,886 | football-data odds/stats joined to FotMob ids, **100% joined**; flag `fd_score_agrees` |
| `understat_match` / `understat_team_match` | 21,911 / 43,822 | Understat match xG and per-team npxG, PPDA, deep, xPts; 21,910 and 43,814 joined |
| `teams` | 171 | FotMob id ↔ football-data name ↔ Understat titles |
| `unavailable_partial` | ~43k | FotMob "unavailable" lists, **not reliable** (see below) |
| `features` | 23,570 × 135 | one row per top-5 / UCL match, as-of the cutoff, plus labels |

### 11.2 Data-quality findings from building the tables

- **90-minute result:** FotMob `scoreStr` is the score after extra time for AET matches, so the 90-minute label is rebuilt from goal events with `time <= 90` (stoppage time is stored as 90 + overload). Verified on Inter 4-3 Barcelona (3-3 at 90'). Goal-event counts equal the final score in 11,969 of 11,971 matches.
- **Awarded / abandoned results:** five matches (Sassuolo–Pescara 2016/17, Bastia–Lyon 2016/17, Verona–Roma 2020/21, Spezia–Verona 2022/23, Union Berlin–Bochum 2024/25) have different scores in different sources, and no source is right by rule (football-data holds the awarded score for Bastia–Lyon, FotMob for the others). Their 90-minute score is left blank and `score_conflict` is set rather than guessed. 114 awarded forfeits in feeder leagues have an empty status reason, marked `unspecified` / `result_unreliable`.
- **FotMob `unavailable` lists are not a usable injury history.** Virgil van Dijk (ACL, Oct 2020–2021) appears in none of Liverpool's 2020/21 lists; entries are 0–3 per team. Use lineup-derived features instead.
- **Duplicates fixed:** calendar-year leagues (Norway) return the same season under two labels; deduplicated on match id.
- **Alias bug fixed:** a stray (date, score) coincidence attached Understat's "Stoke" to Tottenham and "Watford" to Chelsea, creating 548 duplicate joins and 519 score mismatches. Aliases now need ≥2 votes and ≥5% share, and a clashing alias goes to the team with most votes. After the fix the only score disagreements are the five above.
- **Cross-checks that pass:** football-data score equals FotMob in 21,883/21,886 joined rows; Understat equals FotMob in 21,905/21,910 (the rest are the same disputed matches).

### 11.3 Feature engine (`src/features/asof.py`)

One chronological pass over two event types per match: RESULT at kickoff + 150 min and QUERY at kickoff − 60 min (RESULT sorts first at ties, a match's own RESULT is always after its own QUERY).
Features per team (`home_*`, `away_*`) and match: cross-league Elo (K=20, ×1.5 for UCL/UEL/UECL, home advantage 65, goal-difference multiplier, 25% pull toward the league mean each new season with the mean fixed once per season, newcomers start 30 below the league mean); domestic league position/points/GD from the official table (awarded results count); form over 5/10 matches; rest days and matches in 14/30 days (only competitions we hold, so domestic cups are missing); rolling FotMob xG, shots, possession, pass accuracy, corners, cards, big chances, lineup rating (5/10); rolling Understat xG/npxG/PPDA/deep; lineup continuity and the starters' prior ratings; head-to-head over the last five meetings. Labels (`y_*`, `result_90`) are separate columns.

### 11.4 Verification of the engine

- **Property tests:** scrambling all results after time T never changes features of earlier matches (random synthetic leagues, 5 seeds); a match's own score never reaches its own features; same-day ordering; Elo zero-sum and order-independent season pull.
- **Real-data leakage test:** scrambling results, team stats, Understat metrics and player ratings for every match from 2023-01-01 leaves all 10,000+ earlier feature rows bit-identical (`tests/test_asof_real_data.py`).
- Two engine bugs were found by the tests and fixed: an order-dependent season pull and a crash on half-known scores.
- **Face validity:** top Elo at the end of 2024-25 is Liverpool, Arsenal, PSG, Inter, Bayern, Barcelona, Real Madrid.
- **Baseline vs market** (5 leagues, 10,705 matches in 2019-2024, 3-class Brier, binned Elo→H/D/A fitted on seasons ≤2018 only): constant 0.652, our Elo model 0.5946, Pinnacle opening 0.5775, Pinnacle closing 0.5757. The Elo feature alone recovers ~75% of the distance from constant to market.
- **Feature coverage by season:** Understat xG from 2014; FotMob xG, shots, possession from 2019/20 (2019/20 has no FotMob xG); lineup features from 2018/19; early-2014 seasons lack the h2h history.

### 11.5 Known limits

League-only context (no domestic cups), so rest days and congestion are understated for teams in cups; FotMob market values and ages are current-at-fetch and are deliberately not features; `elo_diff` uses a fixed home advantage, including at neutral venues; the Elo league prior is learned only through European results, so the relative strength of isolated leagues is approximate.
