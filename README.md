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
- $5 promotional monthly credit, currently expiring 19 October (year of credit grant)
- Experiments run: `001`–`006` (Phase 1 API understanding complete)

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
