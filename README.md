# Jev API Experiments

An empirical research repository for understanding and evaluating TypeSafe's Jev System One model.

This is **not** FootyQuant v2. Findings here may later inform that product. They do not yet.

## Purpose

Characterize the TypeSafe Jev API by running controlled experiments, saving raw evidence, and updating hypotheses only after measurement.

## Research philosophy

Hypothesis → experiment design → controlled test → raw observations → quantitative analysis → conclusion → next hypothesis.

Status labels:

- **SUPPORTED** — evidence from the named experiment(s) is consistent with the hypothesis under the stated conditions
- **REJECTED** — evidence contradicts the hypothesis under the stated conditions
- **INCONCLUSIVE** — evidence is insufficient or mixed
- **UNTESTED** — not yet measured

Do not treat marketing claims, blog posts, or demos as facts until they are tested here.

## Current status

- Early access to TypeSafe Jev
- Direct TypeSafe API access
- Experiments run: `001`–`019` (API behavior and synthetic calibration); `020`–`023` (football pilot, count bands, ablations, locked retrospective); `024` **ACTIVE** (prospective 2026/27 series); `025` pending; `026` WAITING FOR RESEARCH
- Football headline (retrospective, exploratory): Score 1X2 ties a simple Elo baseline; Noul's binary outputs need calibration; Choice is unusable raw. See `experiments/021-retrospective-locked/README.md`

## Long-term objective

Use **validated** findings from this repository to inform whether, and how, Jev should appear in a future FootyQuant v2 football prediction and betting-market analysis system covering competitions such as UEFA Champions League, Premier League, and La Liga.

## Important distinction

This repository is research. It is not yet:

- a betting product
- a production application
- a recommendation engine
- a subscription service

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `TYPESAFE_API_KEY` in `.env`. Never commit `.env` or paste the key into source, docs, or chat.

Pinned model default: `jev-1.13.0` (not the moving alias `jev-latest`).

## Run Experiment 001

```bash
python experiments/001-api-sanity/experiment.py
```

Raw output is written to `results/001-api-sanity/run-NNN.json`.

## Tests

```bash
python -m pytest
```

## Football data layer

The data CLI collects five domestic leagues, UCL, and rating-only feeder competitions. Raw responses live in ignored `data/raw/`; rebuilt Parquet files live in ignored `data/derived/`. Finished target fixtures have match details, while feeder competitions contribute results to cross-league Elo.

```bash
.venv/bin/python -m src.data.cli status
.venv/bin/python -m src.data.cli build-tables
.venv/bin/python -m src.data.cli build-features
.venv/bin/python -m src.data.cli audit
```

Read `data/derived/model_inputs.parquet` for label-free historical ML inputs, `market_labels.parquet` for outcomes, and `upcoming_inputs.parquet` for future fixtures. `matches.parquet` and `upcoming.parquet` supply names and data-quality fields. The `state` command prints an allowlisted JSON record for Jev:

```bash
.venv/bin/python -m src.data.cli state --match-id MATCH_ID
.venv/bin/python -m src.data.cli state --match-id MATCH_ID --upcoming
.venv/bin/python -m src.data.cli state --match-id MATCH_ID --upcoming --anonymized
```

The upcoming command refuses a match once its 60-minute cutoff has passed. `capture-due` archives ESPN pages when an upcoming fixture is near that cutoff and updates `forward_quotes.parquet`; the quote table records source and capture times and leaves uncertain event matches unlinked. Its displayed prices are not verified executable bookmaker quotes. See [daily and pregame timer setup](ops/systemd/README.md).

For the table schema, label rules, quality flags, and Python ingestion example, see the [data layer usage guide](docs/data-layer-usage.md).

## Layout

```
src/                 HTTP client, request schema, helpers
experiments/         one directory per experiment
results/             raw run artifacts (no secrets)
docs/                hypotheses, findings, API notes
```

## Experiment roadmap (not implemented yet)

Phase 1 — API understanding: 001–006  
Phase 2 — Decision behavior: 007–014  
Phase 3 — Calibration against known probabilities  
Phase 4 — Football, only after earlier phases, with strict information-cutoff controls

## Docs

- [docs/hypotheses.md](docs/hypotheses.md)
- [docs/findings.md](docs/findings.md)
- [docs/api-notes.md](docs/api-notes.md)
- [experiments/001-api-sanity/README.md](experiments/001-api-sanity/README.md)
