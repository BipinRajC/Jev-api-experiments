# GLM 5.3 Flash handoff: Jev experiments on real football data

Prepared 2026-10-19 for the repository at `/home/bipin/jev-api-experiments`.

Copy the **Prompt for GLM 5.3 Flash** section into the new session, or give the new model this file and tell it to follow that section. This handoff describes the research contract; it does not claim that any football Jev experiment has already run.

## Current answer to “is the data ready?”

**Yes for a controlled retrospective pilot and as-of football inputs, subject to the preflight below.** The completed backfill and repaired data layer pass the current integrity audit. This is not a claim that every future experiment can already be finished: prospective fixtures still have to be predicted before kickoff and later settled; the 2026/27 season is in progress; some prices lack verified timing or market coverage; and the user's additional mathematical research for market extensions has not arrived.

Observed locally on 2026-10-19; rerun these commands because the daily refresh changes the data:

```bash
.venv/bin/python -m src.data.cli status
.venv/bin/python -m src.data.cli audit
git status --short --branch
```

| Audit item | Observed value | Meaning |
|---|---:|---|
| Finished match rows / market-label rows | 63,875 / 63,875 | Includes collected competitions beyond the six headline competitions. |
| Finished target-match input rows | 23,585 | Label-free, cutoff-aware historical inputs. |
| Upcoming fixture / input rows | 1,521 / 1,521 | Future states can be built without a completed-match result. |
| Forward quote rows | 730 | Displayed prices with provenance; validity as executable quotes is unverified. |
| Recently finished details pending / overdue | 7 / 0 | Pending details follow the daily retrieval window. Recheck before selecting matches. |
| Score / kickoff / corner conflicts | 4 / 16 / 412 | Explicit quality flags or null labels; do not quietly include affected outcomes. |
| Unmatched quote rows | 120 | Do not force these onto fixtures. |
| Duplicate IDs / late cutoffs / leaked columns / audit errors | 0 / 0 / 0 / 0 | Present audit gate passed. |

The previous 001–019 experiments are **synthetic or API behavior experiments**, not football outcome evidence. Their results and styles provide a reproducibility template, not a football calibration correction. In particular, do not apply Experiment 019's approximate Noul bias adjustment to football without fitting and testing it on separate football cohorts.

## Prompt for GLM 5.3 Flash

You are continuing the Jev research in `/home/bipin/jev-api-experiments`. Implement and run the real football experiments described in `docs/phase4-jev-football-experiment-plan.md`, beginning with **Experiment 020**. Work autonomously, record the exact evidence, validate each experiment, write its README with findings, and commit completed work **one experiment at a time**. Preserve the existing 001–019 format. Do not rerun or overwrite 001–019.

### 1. Read the project before changing it

Read, in this order:

1. `README.md`, `docs/phase4-jev-football-experiment-plan.md`, and `docs/data-layer-usage.md` for the objective, data contracts, cutoff, cohorts, and experiment sequence. Treat the plan's older “partly rebuilt” counts as historical text; measure current counts yourself.
2. `docs/hypotheses.md`, `docs/findings.md`, `docs/api-notes.md`, and `docs/handoff-phase2.md` for research conventions and Jev caveats.
3. `experiments/001-api-sanity/README.md`, `experiments/019-calibration/README.md`, their `experiment.py` files and corresponding `results/*/run-*.json`; skim the other 002–018 READMEs and scripts to preserve their naming, result schema, and style.
4. `src/jev_client.py`, `src/schemas.py`, `src/noul.py`, `src/score.py`, `src/choice.py`, `src/utils.py`, `src/features/state.py`, `src/features/asof.py`, `src/data/cli.py`, `src/data/markets.py`, `src/data/quotes.py`, and relevant tests. Reuse the existing client and data interfaces where appropriate.
5. `ops/systemd/README.md` and the current Git status to understand the laptop's daily refresh and near-cutoff quote collection.

The working tree at handoff contains untracked `docs/2026-10-18-181227-footyquant-claude.txt` and `docs/data-inventory-2026-10-18.md`. **Never stage or commit the Claude transcript.** Keep the old inventory out of experiment commits unless separately asked to publish it. Do not use `git add .` or `git add -A`.

### 2. Research objective and honest interpretation

Find which **Noul, Score, and Choice** configuration gives the best validated probability forecasts **for each market**, and whether frozen Jev predictions add value to chronological mathematical and tabular ML baselines for FootyQuant. Cover home/draw/away (1X2), over/under 2.5 total goals, BTTS, and a historically chosen total-corners half-line. Test other markets only under Experiment 026 after the user supplies the promised mathematical research and the data/settlement audit supports them. All events refer to 90 minutes plus stoppage time, excluding extra time and penalties.

Keep three cohorts separate:

| Cohort | Use | Claim allowed |
|---|---|---|
| Historical development through 2024/25 | Fit and tune baselines, corner line and evaluation machinery with rolling-origin splits; fit Jev calibration only if separate, earlier Jev predictions exist. | Development evidence only. |
| 2025/26 and 2026/27 matches already played when first queried | Jev pilot, contamination checks, retrospective comparisons and ablations. | Exploratory. Jev may know past results even when the input state is reconstructed as-of. |
| 2026/27 fixtures first queried and archived before their recorded cutoff | Locked forward predictions and eventual scoring. | Primary evidence for real pre-match performance, after enough fixtures settle. |

Assign cohort by the **first actual Jev request time**, never by season alone. Retrospective backtests cannot establish a live betting edge. Never claim a winner or profitable market from an outcome-only result, a single favorable subset, or the earlier synthetic experiments. Report UCL separately from domestic leagues where coverage differs.

### 3. Preflight before any paid football batch

1. Run `status` and `audit` above; save their JSON/text, UTC timestamp, Git SHA, input-table hashes or source manifest, and the exact environment/dependency versions used. A failing audit blocks the scored batch until the underlying problem is fixed and reaudited. Recheck after parser or source changes.
2. Confirm eligibility and null rates **by season, competition, market, and source** from `data/derived/model_inputs.parquet`, `upcoming_inputs.parquet`, `market_labels.parquet`, and `matches.parquet`. Join by `match_id` with one-to-one validation. Use `label_valid_90` for goal markets and a non-null, regulation-only `corner_total_90` for corners. Log every excluded match and reason. Do not force-match quotes or conflicting source rows.
3. Run a leakage and timing review: inspect the allowlisted `state` output, conservative kickoff/cutoff, prior-match release delay, standings/form, anonymized form, and any proposed new field. The historical cutoff is the earlier source kickoff minus 60 minutes. Exclude current-match scores, post-match stats, closing odds, actual XI without a proven publication timestamp, outcome labels, and any future information. Treat the 16 kickoff disagreements as a recorded sensitivity or exclusion group.
4. Freeze a versioned protocol **before scored calls**: eligibility manifest and exclusions, 90-minute settlement, exact question punctuation and criteria, state schema, corner line/bins, model IDs, primitive output parsing, comparisons, random seed and request rotation, calibration method, metrics, confidence intervals, retry behavior, and missing-response policy. Record hashes and a UTC freeze time. Pilot data must not be used to choose the reported winner or silently change the locked cohort. If a revision is needed, version it and keep old records immutable.
5. Verify the current TypeSafe API/model reference and account access at execution time. Keep `jev-1.13.0` as the continuity arm if still available; any `jev-1.14.0` arm must be explicitly separate and paired. Avoid moving aliases in scored records. Check balance/rate limits and measure actual pilot token use, latency and failures; calculate projected cost for the next batch and record the budget decision. Never print or store `TYPESAFE_API_KEY` or Authorization headers.

The data audit passing does **not** verify a bookmaker price's provider timestamp or executability. Historical football-data odds are post-hoc references, not default state features or same-cutoff comparisons; the 2025/26 Pinnacle feed has a documented reliability warning in the phase-4 plan. Historical BTTS/corners odds and UCL odds are not available in the joined tables. ESPN's displayed `close` field is not proof of a true close. Only compare a captured quote if fixture, bookmaker, side, line, settlement, and timing all match; preserve missing market comparisons otherwise.

### 4. Fixed Jev arms and result contract

Use the **same frozen fixture state** and semantically matched 90-minute event definition for all three primitives. Preserve raw API responses and the transformation separately:

| Primitive | Binary event probability | 1X2 probability |
|---|---|---|
| Noul | Raw `noul` for the registered yes/no proposition. | Ask H/D/A propositions; retain three raw numbers, normalize their sum for the primary distribution. |
| Score | Nine explicitly labelled 0%–100% probability levels in 12.5-point steps; use returned `score / 8`. | Ask parallel H/D/A rubrics; retain raw values and normalize their sum. Preserve level probabilities too. |
| Choice | Use `probabilities["yes"]` for a yes/no Choice. | Use one H/D/A Choice distribution as the primary arm; keep a separately named binary one-vs-rest arm if run. |

Never substitute a `confidence` field for event probability. Reject and log missing, non-finite, out-of-range, incoherent, or zero-sum outputs. Do not repair a failed answer by inventing a probability. For count bands, confirm the actual API response semantics first; derive threshold probabilities from a **valid full distribution** only, with line-aligned bands and a separately scored distribution metric. If Choice returns one-hot distributions or Score only a point score, report that limitation rather than constructing unsupported soft probabilities.

Store immutable evidence under the matching numbered `results/<NNN>-<slug>/` directory, following `run-001.json`, `run-002.json`, etc. Include a manifest/protocol and, for each attempted call: experiment/run/fixture/competition/season/cohort IDs; market, side and exact line; state JSON and SHA-256; question set/version and full request body with secrets removed; requested and returned model IDs; UTC kickoff, cutoff, request and response times; raw response or sanitized error and request ID; parsed result and validation status; token usage, latency, retries, source/build Git SHA, and relevant source hashes. Distinguish missing calls, transport failures, malformed outputs and ineligible labels. Retain raw values and any derived probabilities, with the derivation version. Make reruns append new runs; never overwrite old JSON or silently replace failed fixtures.

For prospective work, write the prediction record **before the fixture's cutoff**, and later append a separate settlement record. Never relabel a call after cutoff as prospective. Build/capture a state starting about 75 minutes before kickoff, finish all planned Jev calls no later than the 60-minute cutoff, and record any qualifying price captured within 15 minutes before the request. If a quote or a primitive is missing, retain the rest of the fixture's record and mark coverage accordingly. Do not assume the existing quote-capture timer also performs Jev inference: implement and validate an explicit prediction/archival path before calling Experiment 024 operational.

### 5. Experiment sequence and deliverables

Use these numbered directories, or another clear slug consistent with 001–019. Preserve the IDs and scope from the phase-4 plan.

| ID | Work | Minimum validation/evidence |
|---|---|---|
| 020 | Infrastructure and contamination pilot on **30–50** stratified, already completed 2025/26 fixtures. Run Noul, Score and Choice on 1X2, O/U 2.5, BTTS and a development-selected corner line; include names/date-only and anonymized controls. | Confirm response shape and parsing for every arm; line/label consistency; matched sample counts; repeats; measured tokens, cost, latency, failures; identify any suspicious named/date-only behavior. Exploratory results only. Freeze the core protocol. |
| 021 | Locked retrospective comparison on **all eligible** 2025/26 and already completed pre-start 2026/27 target fixtures. | Run every primitive on the same match/market sets; report coverage, raw scores and calibrated scores **only if** the calibration map was fitted on separate earlier predictions, by-league/season breakdown, paired uncertainty, and prior-season/Elo/goal/corner/ML baselines where valid. Outcome scoring still applies without odds. |
| 022 | Native Score/Choice goal and corner count bands versus direct Noul thresholds on a predeclared paired sample. | Verify bins, normalization, summed tail probabilities, count distribution metric and matched threshold result; do not treat a selected Choice band as a full probability distribution. |
| 023 | State, wording, repeatability and model-version ablations on fixed paired subsets. | Identity/form/xG/rest additions, named versus anonymized, repeat spread; only timestamp-proven lineups or pre-cutoff matching quotes in optional arms. Label each arm and model version separately. |
| 024 | Prospective 2026/27 series. Set up the cutoff-time runner and append-only prediction archive as soon as 020 has validated the protocol, even if 021–023 analyses continue. | Prove states/calls/archives are pre-cutoff, keep failed and missing records, settle later in separate artifacts, give descriptive interim results after 250 eligible completed matches and a final report only after season end. Clearly mark the README `ACTIVE` until then. |
| 025 | Chronological Jev-plus-ML comparison, separately by market and primitive. | Time-respecting out-of-fold training and calibration; same later evaluation matches for ML alone versus ML plus frozen Jev. Retrospective stacking stays exploratory until enough prospective records exist. |
| 026 | Mathematical market extension after the user's research arrives. | Record its dated source and protocol revision; audit candidate market period, label coverage, line, settlement, price provenance, appropriate mathematical baseline and prospective confirmation before running Jev. Leave it `WAITING FOR RESEARCH` if the research is absent; do not invent it. |

Start forward capture promptly after 020 because missed kickoffs cannot be recovered. Commit 020's validated work first, then commit each completed experiment in ID order. Prospective 024 setup and pre-cutoff records may need **024-scoped commits while 021–023 continue**; document this scheduling exception. Do not mark 024, 025's prospective conclusion, or 026 complete just to advance the numbering. A long-running experiment can have an initial protocol/runner commit and later append-only result commits, all scoped and labelled with that experiment ID.

### 6. Evaluation and validation for **every** experiment

Before writing conclusions, independently check raw artifacts against the summary. For 1X2 compute three-class Brier `mean(sum_k (p_k-y_k)^2)`; for binary markets compute `mean((p-y)^2)`. Lower is better. Also report fixed-floor log loss, reliability/calibration, coverage, invalid/failure rate, input tokens, latency and repeat-call spread. For count-band distributions use an appropriate ranked probability score. Compare on **paired identical fixtures**, with 95% uncertainty intervals for paired differences clustered by match round or date, plus competition/season breakdowns. Do not compare the absolute 1X2 Brier scale with the binary-market Brier scale. Predeclare Noul-vs-Score and Noul-vs-Choice contrasts; handle multiple comparisons or label claims exploratory.

Check at least:

- Manifest totals = eligible + each mutually exclusive exclusion reason; attempted = successful + failed; paired N = actual intersection, never the largest arm's N.
- No duplicate fixture/market/primitive/configuration keys; exact UTC ordering and prospective cutoff; labels recomputed from 90-minute goals/corners on a spot-checked sample; corner conflicts remain unscored.
- Every scored probability is finite and in `[0,1]`; H/D/A distribution sums to 1 after a recorded normalization; line and side match the label and any quoted price; no future/outcome/odds leakage in default states.
- Raw response, parser output, metrics and README numbers agree on a sample and in aggregate; scoring code passes independent known-answer examples and focused tests for failure/edge cases.
- Material parser, data, runner and evaluator changes pass relevant tests, then run `.venv/bin/python -m pytest` and `.venv/bin/python -m src.data.cli audit` before committing the affected experiment. Save the executed commands and results in the README or a run manifest. A failing check is documented and fixed before claiming completion.

Baselines should include prior-season rates, as-of Elo for 1X2, joint-goals Poisson/Dixon–Coles for 1X2/goals/BTTS, a dispersion-checked count model for corners, then market-specific tabular ML. Use rolling-origin development through 2024/25 and never train a model or calibration map on the same scored validation fixtures. If there are no earlier out-of-sample Jev predictions to fit a calibration map, report raw Jev scores only and mark calibrated scores pending; do not fit on the evaluated cohort. Same-cutoff market comparison requires independently verified line and capture timing; otherwise report only outcome and non-market baseline comparisons. A profitable-looking retrospective result is not a decision rule.

### 7. README, findings, and Git contract

For **each** numbered experiment, write `experiments/<NNN>-<slug>/README.md` in the 001–019 style. Keep these headings, populated with actual evidence: **Objective; Hypothesis; Experimental setup; Variables; Controls; Expected result; Falsification criteria; Sample size; Metrics computed; Results; Analysis; Conclusion; Limitations; Next experiment.** Add eligibility/exclusions, protocol version, artifact paths and hashes, tests, dates, model IDs and costs where useful. A setup-only or running experiment must say so clearly; never fill Results with forecasts you have not obtained. Create an executable `experiment.py` or clearly documented runner and relevant focused tests. Preserve raw results under `results/<NNN>-<slug>/run-*.json` plus any manifest/prediction/settlement files needed for replay.

Add new numbered hypotheses to `docs/hypotheses.md` before testing, with conditions and predeclared falsification criteria; update their statuses only from actual results. Append evidence-backed numbered findings to `docs/findings.md`, with experiment/run IDs, N, exclusions, metric uncertainty, conditions, interpretation and limits. Never rewrite F001–F027 as if they were football studies. Use `INCONCLUSIVE` when data do not distinguish hypotheses. Log negative or invalid results just as carefully as positive ones.

After validating an experiment, inspect `git diff --check`, `git status`, the proposed staged file list and the diff. Stage **explicit paths** belonging to that experiment: its script/README/tests/results and only the shared code/docs needed for that experiment. Commit with a descriptive subject such as `experiment(020): validate football primitive pilot`. Then verify the commit contains the intended files and record its SHA before moving to the next experiment. Keep each experiment's work in its own commit or small series of scoped commits; do not bundle multiple completed experiments into one commit. Do not push unless the user requests it. Do not commit `data/raw/`, `data/derived/`, `.env`, API keys, Authorization headers, the excluded Claude transcript, or unrelated workspace files. If a result artifact would be enormous, preserve a lossless, integrity-checked archive and record a reviewable manifest rather than silently discarding observations; do not publish secrets.

At each stopping point, report: completed experiment IDs and commit SHAs, active IDs, number of attempted/valid/paired fixtures by market, exact validation commands and status, remaining data/price/model limitations, actual spend or measured token usage, and the next concrete action. If no prospective fixture has yet reached its cutoff, say the prospective analysis is pending; do not backfill it with a post-match call.

**Begin now:** read the listed files, rerun the data audit and Git status, define and freeze Experiment 020's exact manifest/questions/validation rules, measure the pilot, write its evidence and README, validate it, and commit it before treating 021 as complete. Set up 024's forward prediction path in time for future fixtures. Continue according to the phase-4 plan and this contract, preserving truthful `ACTIVE` or `WAITING FOR RESEARCH` status wherever real-world timing or the user's later input is required.
