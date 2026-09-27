# Phase 4 — Data Research Plan for FootyQuant v2

## Objective

Research and document the best free (or low-cost) sources of football match data, pre-match statistics, and market odds — sufficient to feed Jev System One for probabilistic football outcome prediction. The goal is to identify data sources that can be integrated into a reproducible experimental pipeline, tested against Jev in Phase 4 experiments, and eventually scaled into FootyQuant v2.

## The Jev Input Pipeline — What Data Does Jev Need?

Jev's `state` field accepts text or JSON describing the situation. For a football match, the state should give Jev maximum relevant context to make an informed decision. The question is: **what data would a professional football analyst consider before predicting a match outcome?**

### Tier 1 — Core match context (minimum viable)

- **Match identity:** home team, away team, competition, date
- **League table:** each team's position, points, goal difference at kickoff
- **Recent form:** last 5 results, goals scored/conceded per match over recent period
- **Head-to-head:** results of last ~5 meetings between these teams

### Tier 2 — Advanced team statistics

- **Expected goals (xG):** season xG for/against, recent match xG
- **Attack/defense metrics:** shots per game, shots on target, possession %, pass completion, corners
- **Player-level data:** top scorer availability, key injuries/suspensions
- **Manager data:** manager win rate, head-to-head record vs opposing manager

### Tier 3 — Market and situational context

- **Pre-match odds** (opening and closing) from sharp bookmakers (Pinnacle preferred)
- **Market movement** (significant odds shifts)
- **Venue details:** stadium capacity, away team travel distance
- **Referee data:** referee appointments and historical card rates
- **Weather conditions** at kickoff

### Tier 4 — Temporal and narrative context

- **Match importance** (title race, relegation battle, mid-table)
- **Fatigue context:** days since last match, upcoming fixture congestion
- **Motivation factors:** derby match, revenge narrative, former player returning
- **Squad rotation patterns** around cup competitions

The research should prioritize **Tier 1 (core) and Tier 2 (advanced)** — these are the most measurable and have the largest free-data availability. Tier 3 (odds/market) is critical for the eventual market comparison. Tier 4 is supplementary and may be derived programmatically.

## Research Questions

### 1. Free API Sources

For each potential API source, document:

| Question | Why it matters |
|----------|----------------|
| What data does it expose? (full endpoint list) | Core match data, advanced stats, lineups, xG, odds, etc. |
| Is it truly free? Rate limits? | Can we get 500+ matches/season? |
| Coverage: which leagues? | Premier League, La Liga, Bundesliga, Serie A, Ligue 1, UCL, major national teams |
| Historical data available? How far back? | We need multiple seasons for validation |
| Data format? JSON / CSV / GraphQL? | Ease of ingestion |
| Any terms-of-use restrictions on predictions? | Betting-related use may be prohibited by some APIs |
| Authentication method? API key? | Setup overhead |

**Tools to use:**
- **Firecrawl** (10k YC credits available, [github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)) — use it for:
  - Mapping API documentation sites to discover all available endpoints
  - Extracting structured endpoint specs from API docs
  - Scraping football data sites that don't have an API
  - Multi-page research on data availability across leagues

- **Advanced Google dorking** — use specific search operators to find free data sources that may not appear in standard results:
  ```
  site:github.com "football" "API" "free"
  site:github.com "soccer" "data" json
  "football data" "REST API" free tier
  site:kaggle.com "football match data" 2024
  "API-Football" OR "Football-data.org" alternatives free
  inurl:api "premier league" stats json
  ```

- **Crawlee.dev** ([crawlee.dev/blog](https://crawlee.dev/blog)) — refer to their anti-blocking strategies if scraping is needed:
  - Proxy rotation
  - Browser fingerprint management
  - Rate limiting and retry patterns
  - How to avoid being blocked by football data sites like FBref, Transfermarkt, WhoScored

- **Parsebot** — for extracting structured data from HTML pages that lack an API

### 2. Scraping Candidates

For sites without official APIs, can we extract data reliably?

| Site | What it offers | Scraping viability |
|------|----------------|--------------------|
| FBref.com | Full match stats, xG, advanced metrics (via StatsBomb) | High quality, may rate-limit |
| Transfermarkt | Player values, injuries, lineups, market context | Moderate, aggressive bot protection |
| WhoScored.com | Detailed match stats, player ratings | Moderate |
| Understat.com | xG data for major leagues | High quality, simple structure |
| Sofascore | Detailed live and historical stats | Has an unofficial API, worth investigating |
| FotMob | Detailed match stats, player ratings, lineups | Detailed data, investigate their API patterns |

### 3. Odds Data Sources

For the market comparison (eventual Phase 4 goal), we need pre-match odds:

- **The Odds API** (the-odds-api.com) — free tier available, covers major leagues
- **Football-data.org** — limited odds coverage
- **API-Football** (rapidapi.com) — includes bookmaker odds on paid tier
- Direct scraping from **Oddsportal** or **Pinnacle** — legally grey, high bot protection

### 4. Data Storage & Pipeline Considerations

- **Frequency of updates:** daily match data is fine; pre-match odds change intra-day
- **Reproducibility:** every prediction must have an `information_cutoff` timestamp. Data must be versioned.
- **Cost scaling:** free tier APIs typically cap at 100-1000 requests/day. We need to plan how many matches we can realistically process per day/week.
- **Backfilling historical data:** which sources let us fetch 5+ years of historical data?

## Recommended Starting League

Per the handoff: **the league with the most free data availability should be the starting point.**

Premier League is the strong candidate:
- Most extensive free data coverage across all sources
- Largest betting market (most liquidity, sharpest odds)
- 380 matches per season (good sample size)
- All major APIs include it

Secondary candidates in order of data availability: Bundesliga, La Liga, Serie A, Ligue 1. UCL is important but has fewer matches per season.

## Deliverables

After the research session, bring back:

1. **Recommended data source(s)** — name, URL, coverage, rate limits, authentication requirements
2. **Concrete data schema** — what fields we can actually get, in what format
3. **Sample API response** — a real or representative JSON snippet for a single match
4. **Integration plan** — how to fetch, store, and feed this data to Jev in Phase 4 experiments
5. **Limitations identified** — what data is NOT available for free, and whether to pay for it or proxy through scraping

## Decision Criteria for Source Selection

The final source must satisfy these requirements in order of priority:

1. **Free to use** — or within a very low budget (< $5/month)
2. **Covers all Tier 1 data** for at least one major league for at least one full season
3. **Machine-readable format** (JSON strongly preferred)
4. **Adequate rate limits** for our experimental volume (at least 100 requests/day)
5. **Legally permissible** for prediction research (check terms of service)
6. **Ideally covers Tier 2 data** (xG, shots, possession) — this is what differentiates a serious model from a casual one

## What Happens Next (Back in This Repo)

Once the data research is complete, we will:

1. Document the chosen data source in `docs/api-notes.md` and a new `docs/data-sources.md`
2. Write a data fetching module (`src/data/`) that collects match data at the correct information cutoff
3. Build the state construction logic that formats match data into Jev's `state` field
4. Run Phase 4 Experiment 020 — the first football prediction experiment
5. Compare Jev's predictions against bookmaker implied probability and simple baselines (Elo, Poisson)
6. Measure calibration, Brier score, and potential ROI

The goal is **not** to build a betting bot. The goal is to rigorously measure whether Jev adds value beyond what's already priced into the market.