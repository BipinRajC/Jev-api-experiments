#!/usr/bin/env python3
"""Compute frozen mathematical baselines for Experiment 021's eval fixtures.

Fits on development seasons (2014/15–2024/25) only and applies to the 021
evaluation fixtures (2025/26 + already-played 2026/27). Outputs:
  - results/021-retrospective-locked/baseline-predictions-v1.parquet
  - results/021-retrospective-locked/baseline-fit-v1.json (fit diagnostics +
    eval-cohort performance, for the 021 README)
Deterministic; no network access.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "021-retrospective-locked"))

import baselines as B  # noqa: E402

from src.data.cli import DERIVED_DIR  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results" / "021-retrospective-locked"
DEV_MAX_SEASON = 2024
EVAL_SEASONS = (2025, 2026)


def main() -> int:
    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    labels = pd.read_parquet(DERIVED_DIR / "market_labels.parquet")
    matches = pd.read_parquet(DERIVED_DIR / "matches.parquet")

    lab = labels[[c for c in labels.columns if c != "competition"]]
    df = inputs.merge(lab, on="match_id", validate="one_to_one").merge(
        matches[
            [
                "match_id",
                "home_name",
                "away_name",
                "kickoff_disagreement",
                "details_pending",
            ]
        ],
        on="match_id",
        validate="one_to_one",
    )
    df = df[df["label_valid_90"].fillna(False)]

    dev = df[df["season_start"] <= DEV_MAX_SEASON].copy()
    eval_df = df[df["season_start"].isin(EVAL_SEASONS)].copy()
    eval_df = eval_df[eval_df["corner_total_90"].notna()]
    print(f"dev rows: {len(dev)}, eval rows: {len(eval_df)}")

    ref_time = pd.Timestamp(dev["kickoff_utc"].max())
    dev_days = (
        ref_time - pd.to_datetime(dev["kickoff_utc"])
    ).dt.total_seconds().to_numpy() / 86400.0

    diagnostics: dict[str, Any] = {"baseline_version": B.BASELINE_VERSION}

    # 1. prior frequencies (development seasons)
    prior = B.prior_frequencies(
        dev["result_90"].to_numpy(),
        dev["over_2_5"].to_numpy().astype(bool),
        dev["btts_yes"].to_numpy().astype(bool),
        (dev["corner_total_90"] > 9.5).to_numpy(),
    )
    diagnostics["prior_frequencies_dev"] = prior

    # 2. Elo logistic (development fixtures)
    elo = B.EloLogit().fit(dev["elo_diff"].to_numpy(), dev["result_90"].to_numpy())
    diagnostics["elo_logit_classes"] = list(elo.classes_)

    # 3. Dixon-Coles on development results (drop rows with missing team names)
    dc_dev = dev.dropna(subset=["home_name", "away_name"])
    dc = B.DixonColes().fit(
        dc_dev["home_name"].tolist(),
        dc_dev["away_name"].tolist(),
        dc_dev["goals_home_90"].to_numpy(),
        dc_dev["goals_away_90"].to_numpy(),
        dc_days := (ref_time - pd.to_datetime(dc_dev["kickoff_utc"]))
        .dt.total_seconds()
        .to_numpy()
        / 86400.0,
    )
    diagnostics["dixon_coles"] = {
        "n_teams": len(dc.attack),
        "home_adv": round(dc.home_adv, 4),
        "rho": round(dc.rho, 5),
        "n_dev_matches": len(dc_dev),
    }

    # 4. corner model (development corner totals)
    corner = B.corner_over_probability(dev["corner_total_90"].dropna().to_numpy(), 9.5)
    diagnostics["corner_model"] = {
        k: (round(v, 4) if isinstance(v, float) else v)
        if not isinstance(v, dict)
        else {k2: round(v2, 4) for k2, v2 in v.items()}
        for k, v in corner.items()
    }

    # Apply to eval fixtures.
    rows = []
    for _, r in eval_df.iterrows():
        try:
            dc_p = dc.outcome_probs(r["home_name"], r["away_name"])
        except KeyError:
            dc_p = {}  # team unseen in development data (rare)
        elo_p = elo.predict_proba(np.array([r["elo_diff"]]))
        rows.append(
            {
                "match_id": r["match_id"],
                "season_start": int(r["season_start"]),
                "competition": r["competition"],
                "prior_home": prior["p_home"],
                "prior_draw": prior["p_draw"],
                "prior_away": prior["p_away"],
                "prior_over_2_5": prior["p_over_2_5"],
                "prior_btts": prior["p_btts"],
                "prior_corners_over": prior.get("p_corners_over"),
                "elo_home": float(elo_p.get("H", [np.nan])[0]),
                "elo_draw": float(elo_p.get("D", [np.nan])[0]),
                "elo_away": float(elo_p.get("A", [np.nan])[0]),
                "dc_home": dc_p.get("home"),
                "dc_draw": dc_p.get("draw"),
                "dc_away": dc_p.get("away"),
                "dc_over_2_5": dc_p.get("over_2_5"),
                "dc_btts": dc_p.get("btts"),
                "corner_over": corner["p_over"],
                "result_90": r["result_90"],
                "over_2_5": bool(r["over_2_5"]),
                "btts_yes": bool(r["btts_yes"]),
                "corner_over_9_5": bool(r["corner_total_90"] > 9.5),
            }
        )
    out = pd.DataFrame(rows)
    out.to_parquet(RESULTS_DIR / "baseline-predictions-v1.parquet", index=False)

    # Eval performance (baselines never saw these outcomes).
    def brier3(p, y):
        return (
            (p["home"] - (y == "H")) ** 2
            + (p["draw"] - (y == "D")) ** 2
            + (p["away"] - (y == "A")) ** 2
        )

    perf = {}
    for name, h, d, a in (
        ("prior", "prior_home", "prior_draw", "prior_away"),
        ("elo", "elo_home", "elo_draw", "elo_away"),
        ("dc", "dc_home", "dc_draw", "dc_away"),
    ):
        sub = out.dropna(subset=[h, d, a])
        b = np.mean(
            [
                (r[h] - (r["result_90"] == "H")) ** 2
                + (r[d] - (r["result_90"] == "D")) ** 2
                + (r[a] - (r["result_90"] == "A")) ** 2
                for _, r in sub.iterrows()
            ]
        )
        perf[f"{name}_1x2_brier"] = round(float(b), 5)
        perf[f"{name}_n"] = len(sub)
    for name, col, ycol in (
        ("prior", "prior_over_2_5", "over_2_5"),
        ("dc", "dc_over_2_5", "over_2_5"),
        ("prior", "prior_btts", "btts_yes"),
        ("dc", "dc_btts", "btts_yes"),
    ):
        sub = out.dropna(subset=[col])
        b = np.mean([(r[col] - float(r[ycol])) ** 2 for _, r in sub.iterrows()])
        perf[f"{name}_{ycol}_brier"] = round(float(b), 5)
    sub = out.dropna(subset=["corner_over"])
    perf["corner_prior_over_brier"] = round(
        float(
            np.mean(
                [
                    (r["corner_over"] - float(r["corner_over_9_5"])) ** 2
                    for _, r in sub.iterrows()
                ]
            )
        ),
        5,
    )
    perf["corner_n"] = len(sub)
    diagnostics["eval_performance"] = perf

    with open(RESULTS_DIR / "baseline-fit-v1.json", "w") as fh:
        fh.write(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(diagnostics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
