# Phase 4 — Jev experiments on real football matches

Plan date: 2026-10-18. Execution begins after the 2014–2019 FotMob backfill and the data gates below. This document defines the evaluation protocol; it does not report football performance.

## 1. Research question and scope

Measure whether Jev's probabilities for **90-minute home win, draw, and away win** contain useful information beyond simple football models and the available pre-match market. Preserve the same match-level evidence so a later FootyQuant ML model can be compared with Jev and, if justified, use frozen Jev outputs as additional inputs.

The target competitions are Premier League, La Liga, Bundesliga, Serie A, Ligue 1, and UEFA Champions League. The first retrospective emphasis is **2025/26**, followed by the already played part of **2026/27**. Matches predicted and archived before kickoff later in 2026/27 form the decisive prospective cohort. Older seasons train and validate classical baselines; they are not the headline Jev result.

Every result is a 90-minute result including stoppage time, excluding extra time and penalties. Exclude cancelled, abandoned, awarded, disputed, and missing-score matches from scored outcomes. Report exclusions and missing data by competition and season.

## 2. Three evaluation cohorts

| Cohort | Matches | Use | Interpretation |
|---|---|---|---|
| Historical development | 2014/15–2024/25 | Fit league frequencies, Elo-to-1X2 mapping, Poisson/Dixon–Coles and tabular ML; use rolling season validation | Model development only. Historical Pinnacle closing odds are an after-the-fact reference. |
| Retrospective Jev | 2025/26 plus 2026/27 matches already played before the first frozen run | Pilot, contamination probes, prompt and state ablations, exploratory comparison | These calls occur after results exist. Jev may have prior knowledge of them, so they cannot establish a live edge. |
| Prospective Jev | 2026/27 fixtures whose state, request, response, and available odds are saved **before kickoff** | Locked primary evaluation of Jev versus baselines and same-cutoff market | This is the first cohort that can support a claim about real pre-match prediction. Keep UCL results separate from domestic leagues. |

Assign each match to a cohort by the **first prediction's recorded time**, not by season alone. A match predicted after kickoff stays retrospective even if its state was reconstructed from earlier data. Never move a match between cohorts after seeing its result.

## 3. Gates before any football Jev batch

1. Finish the 2014–2019 FotMob match-detail backfill. Compare every finished target fixture against its expected raw detail path; parse and validate the saved bodies. Rebuild `data/derived/*.parquet` only after the backfill finishes, then record row counts, null rates, source hashes, and the build commit.
2. Fix the source join in `src/data/tables.py`: competition, season, and home/away IDs are insufficient when clubs meet twice with the same home side. The 2022/23 Spezia–Verona league game and playoff are the known counterexample. Include kickoff date and score checks, require an unambiguous candidate, and re-audit the five currently flagged score conflicts. Keep football-data's `HxG` and `AxG` out of odds columns.
3. Make every collector return a failing exit status when any fetch fails. Verify that the daily job and data audit distinguish a complete refresh from a partial one. Correct the snapshot count in `status`.
4. Audit FotMob versus football-data kickoff times where both exist, especially differences over 15 minutes. Define one adjudicated kickoff per match and log the source. Resolve or exclude discrepancies that could change the information cutoff.
5. Add an **upcoming-fixture query path** to the as-of engine. The current `features.parquet` contains only finished matches. A prospective state must be built from an unplayed fixture at its recorded cutoff without using that fixture's result or completed-match record.
6. Add a near-cutoff capture job for forward quotes and fixtures. The current daily snapshot only stores raw responses and cannot guarantee a price near a match's cutoff. For the primary prospective protocol, assemble the state and capture the available quote starting 75 minutes before kickoff; complete the Jev call no later than 60 minutes before kickoff. Require a quote captured within 15 minutes before the Jev request for a same-cutoff market comparison. If no quote qualifies, retain the Jev prediction and mark the market comparison missing.
7. Prove field availability, not only event ordering. Historical completed-match lineups have no release timestamp in this cache: omit actual XI and lineup-derived features from the 60-minute state unless a timestamped pre-cutoff snapshot proves they were available. Exclude post-match stats, final tables, labels, and closing odds from every state.
8. Freeze the state schema, question wording, model ID, normalization rule, cohort assignment, exclusions, metrics, and comparison arms **before** the scored batch. A small pilot may test parsing and cost, but its outcomes cannot select the winning prompt for the locked evaluation.

The data gates are checked again after any source or parser change. The real-data future-scramble test remains useful, but it does not replace proof that a field was published before the cutoff.

## 4. Fixed Jev request and archived record

Use one structured JSON state per fixture. It contains match identity, competition, kickoff and cutoff UTC, source provenance, domestic standing when known, recent results and goals, cross-league Elo, rolling shots and xG, rest/congestion from competitions actually covered, and explicit coverage flags. Use stable key order and units. Omit unknown measurements instead of fabricating values. The default state contains **no bookmaker prices**.

Send three Noul questions in one request with fixed, literal wording:

```json
{
  "home_win_90": {"type": "noul", "instructions": "Will the home team win after 90 minutes plus stoppage time, excluding extra time and penalties?"},
  "draw_90": {"type": "noul", "instructions": "Will this match be a draw after 90 minutes plus stoppage time, excluding extra time and penalties?"},
  "away_win_90": {"type": "noul", "instructions": "Will the away team win after 90 minutes plus stoppage time, excluding extra time and penalties?"}
}
```

Store all three raw values. The primary 1X2 distribution is each value divided by their sum; reject and log an invalid, non-finite, out-of-range, or zero-sum set rather than silently imputing one. Report the raw sum and compare normalization/calibration choices on development data only. Choice is not the primary probability primitive because the relevant completed tests found it effectively one-hot.

Pin `jev-1.13.0` for the first full arm to preserve continuity with Experiments 001–019. TypeSafe's [model reference](https://docs.typesafe.ai/models) now also lists `jev-1.14.0` and maps `jev-preview` to it; run a separately named, paired 1.14 pilot for compatibility and cost, then predeclare whether to run both versions prospectively. Do not select a version by retrospective score or use moving aliases in archived requests. The [API reference](https://docs.typesafe.ai/api) confirms the `state`/`model`/`questions` request shape and token-usage response; verify account access and limits at execution time.

For every call, save an immutable record under `results/020-football/` or its numbered successor: match and cohort IDs, UTC request/response/cutoff/kickoff times, raw state and its SHA-256, question-set version, code/data versions, model requested/returned, raw response, request ID, token usage, parsing result, and any error. For prospective calls, also save the chosen odds quote, bookmaker, market, capture timestamp, and raw snapshot hash. Archive these **before kickoff**; append the eventual result later without rewriting the prediction record. Never store API keys.

## 5. Experiment sequence

| ID | Test | Comparison and decision |
|---|---|---|
| 020 | Infrastructure and contamination pilot: 30–50 completed 2025/26 matches stratified across leagues and favorite strength. Call with only names/date, then with an anonymized state, then with the full as-of state. | Verify request/response parsing, actual token cost, repeatability, and whether named/date-only answers look suspiciously informed. This is exploratory, not a performance claim. |
| 021 | Locked 1X2 retrospective run on all eligible 2025/26 matches and pre-start 2026/27 matches, for the six target competitions. | Three Noul values per match; compare with prior-season frequencies, Elo, Poisson, and available closing-market references. Report each league and UCL separately. Mark every score retrospective. |
| 022 | State ablations on a prespecified, paired sample: identity only; +Elo/table/form; +shots/xG; +rest/head-to-head; +timestamp-proven lineup; +pre-cutoff market price. | Measure paired change in proper scoring and calibration. Each arm uses the same matches and fixed question text. Never put closing odds or a field published after cutoff into a state. |
| 023 | Model and wording robustness: pinned 1.13 versus pinned 1.14; named versus anonymized teams; repeat identical calls on a small fixed subset. | Quantify model-version effects, name/date contamination, and output jitter. Treat each wording as a distinct model configuration. |
| 024 | Prospective 2026/27 series: automatically generate upcoming states and call Jev at the fixed cutoff for every eligible fixture. | Freeze predictions and same-cutoff quotes before kickoff. Evaluate on completed matches without editing the prompt or outcome rules. |
| 025 | Jev plus ML: compare an as-of tabular model with and without Jev's frozen probabilities. | Train and calibrate using chronological, out-of-fold predictions; evaluate the fixed combination only on later matches. A retrospective stack is exploratory until enough prospective Jev records exist. |
| 026 | Secondary markets, starting with over/under 2.5 if timestamped quotes exist. | Specify new Noul questions and market rules in a separate protocol before examining results. BTTS is an outcome-only study until a suitable pre-match odds source is archived. |

Complete the pilot and gates before running ID 021. Start ID 024 as soon as the forward path is valid; do not wait for the retrospective analysis to exhaust the remaining 2026/27 fixtures.

## 6. Benchmarks, splits, and statistics

Primary metric: mean **three-class Brier score**, `mean((pH-yH)^2 + (pD-yD)^2 + (pA-yA)^2)`. Lower is better. Secondary metrics: multiclass log loss with a fixed numerical floor, calibration/reliability by outcome and probability bin, coverage and failure rate, and scores by competition, season, and favorite/draw subgroup. Use paired differences on identical matches and report 95% uncertainty intervals by resampling match rounds or dates; show sample sizes and missing-market counts. A small positive difference or ROI is not an established edge.

Build baselines in increasing complexity: prior-season league frequencies; the repository's as-of Elo mapped to H/D/A on earlier seasons; a goals-based Poisson/Dixon–Coles model; then a tabular ML model using only admissible as-of fields. Fit/tune with rolling-origin seasons through 2024/25, use 2025/26 for retrospective validation, and keep the prospective series sealed. For a Jev stack, generate time-respecting Jev inputs and out-of-fold base-model predictions; never train on a row's own target-derived or closing-odds fields.

For 2025/26, football-data's [published warning](https://football-data.co.uk/data) says its Pinnacle feed became unreliable after 23 July 2025. Do not call those prices a clean sharp-market benchmark. Use available market-average/Betfair closing data as **post-hoc reference only**, with source and missingness reported. Historical UCL has no joined odds in this repository, so its retrospective primary comparison is against outcomes and non-market models. In the prospective cohort, compare with a bookmaker quote only if its recorded capture time is at or before the prediction cutoff; a later closing quote is a separate diagnostic, never an input or a same-cutoff comparator.

Report paired Brier difference for Jev versus Elo and versus the same-cutoff market on the common-coverage subset. Also report Jev plus ML versus ML alone. Predeclare these as the main comparisons; treat the many ablation and subgroup results as exploratory unless a later untouched cohort replicates them. First prospective interim report: after 250 eligible completed matches, descriptive only. Final 2026/27 report: after the season ends, including every eligible prediction and all failures.

## 7. Operating and decision rules

- Before paying for a full batch, check current Jev balance and organization limits, then measure input tokens and errors on the 30–50-match pilot. TypeSafe currently lists both pinned versions at [$0.042 per million input tokens](https://docs.typesafe.ai/models); use measured usage, not the transcript's estimated tokens per match, to set a dollar cap.
- Freeze a manifest of eligible fixtures before each batch. Log missing states, unavailable prices, timeouts, and invalid outputs as failures; do not replace them with easier fixtures. Do not rerun a failed prediction after kickoff and label it prospective.
- Preserve raw evidence and exact exclusion reasons. Compare source revisions against the snapshot hash. A changed historical source may prompt a sensitivity rerun, but the original prediction stays immutable.
- Decide whether Jev is useful for FootyQuant from **incremental prospective skill** over the fixed ML model and market, not from synthetic calibration or retrospective ROI. If it adds no measured skill, keep its role exploratory; if it does, evaluate calibration, cost, and stability before using it in recommendations.

## 8. Deliverables after execution

1. Rebuilt and audited raw-to-table and as-of datasets, including a repaired Spezia–Verona join and a field-availability audit.
2. Versioned state constructor, upcoming-fixture path, fixed Jev question set, and append-only prospective prediction archive.
3. Reproducible historical baselines and a fixed evaluation script that scores every arm on matched fixtures.
4. One experiment README and raw result artifact per numbered experiment, with hypothesis, setup, controls, exclusions, results, uncertainty, and limitations in the repository's existing format.
5. A final comparison table for Jev 1.13, Jev 1.14 where run, Elo, goals model, tabular ML, Jev-plus-ML, and the admissible market reference, separated into retrospective and prospective cohorts.
