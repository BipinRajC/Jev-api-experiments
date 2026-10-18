#!/usr/bin/env python3
"""Tabular ML baseline for Experiment 021 (and the ML arm of 025).

Gradient-boosted trees (sklearn HistGradientBoosting) on the audited,
label-free as-of feature table:
  - fitted on development seasons (2014/15-2024/25) only;
  - a 2024/25 validation split is used for the (predeclared, minimal) model
    choices: leaf count and max iterations;
  - applied to the 021 eval cohort (2025/26 + already-played 2026/27);
  - the eval cohort's outcomes are never used for fitting or tuning.

Outputs:
  - results/021-retrospective-locked/ml-predictions-v1.parquet
  - results/021-retrospective-locked/ml-fit-v1.json (chosen settings + metrics)
Deterministic (fixed random_state); no network access.
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

from src.data.cli import DERIVED_DIR  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results" / "021-retrospective-locked"
DEV_MAX_SEASON = 2024
TUNE_SEASON = 2024
EVAL_SEASONS = (2025, 2026)
RANDOM_STATE = 42
ID_COLUMNS = {
    "match_id",
    "season_start",
    "round",
    "kickoff_utc",
    "cutoff_utc",
    "home_id",
    "away_id",
    "home_name",
    "away_name",
}


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Numeric, non-identifier, non-constant columns (as-of features, audited leak-free)."""
    cols = []
    for c in df.columns:
        if (
            c in ID_COLUMNS
            or c.endswith(("_utc",))
            or c.startswith(("home_name", "away_name"))
        ):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique(dropna=True) > 1:
            # constant columns break sklearn's binning and carry no signal
            cols.append(c)
    return cols


def fit_market(
    train_x: pd.DataFrame,
    train_y: np.ndarray,
    val_x: pd.DataFrame,
    val_y: np.ndarray,
    *,
    n_iter: int = 300,
) -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier

    clf = HistGradientBoostingClassifier(
        max_iter=n_iter,
        max_leaf_nodes=31,
        learning_rate=0.06,
        random_state=RANDOM_STATE,
        early_stopping=False,
    )
    clf.fit(train_x, train_y)
    return clf


def main() -> int:
    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    labels = pd.read_parquet(DERIVED_DIR / "market_labels.parquet")
    lab = labels[[c for c in labels.columns if c != "competition"]]
    # Feature columns are selected from the RAW label-free inputs table only;
    # selecting them after the label merge would leak outcome columns.
    features = feature_columns(inputs)
    df = inputs.merge(lab, on="match_id", validate="one_to_one")
    df = df[df["label_valid_90"].fillna(False) & df["corner_total_90"].notna()]
    print(f"features: {len(features)}")

    # Guard: no label column may appear among the features.
    forbidden = {
        "result_90",
        "goals_home_90",
        "goals_away_90",
        "total_goals_90",
        "over_2_5",
        "btts_yes",
        "corner_total_90",
        "corner_conflict",
        "label_valid_90",
    }
    leaked = sorted(forbidden & set(features))
    if leaked:
        print(f"FATAL: leaked label columns among features: {leaked}", file=sys.stderr)
        return 2
    print(f"features: {len(features)}")

    dev = df[df["season_start"] <= DEV_MAX_SEASON]
    tune = dev[dev["season_start"] == TUNE_SEASON]
    train = dev[dev["season_start"] < TUNE_SEASON]
    eval_df = df[df["season_start"].isin(EVAL_SEASONS)].copy()

    # Predeclared minimal choices: score a small iteration grid on the 2024/25
    # validation split for the 1X2 task only, then reuse the winner everywhere.
    def brier3(y_true: np.ndarray, proba: np.ndarray, classes: list[str]) -> float:
        total = 0.0
        for i, cls in enumerate(classes):
            total += (proba[:, i] - (y_true == cls).astype(float)) ** 2
        return float(np.mean(total))

    chosen_iter = 300
    best = None
    for n_iter in (100, 300, 600):
        clf = fit_market(
            train[features],
            train["result_90"].to_numpy(),
            tune[features],
            tune["result_90"].to_numpy(),
            n_iter=n_iter,
        )
        proba = clf.predict_proba(tune[features])
        score = brier3(tune["result_90"].to_numpy(), proba, list(clf.classes_))
        print(f"  n_iter={n_iter}: 2024/25 val 3-class Brier {score:.5f}")
        if best is None or score < best[1]:
            best = (n_iter, score)
    chosen_iter = best[0]
    print(f"chosen max_iter={chosen_iter}")

    # Final models: refit on ALL dev seasons (<= 2024/25) with the chosen size.
    models: dict[str, Any] = {}
    tasks = {
        "result_90": ("multiclass", dev["result_90"].to_numpy()),
        "over_2_5": ("binary", dev["over_2_5"].astype(bool).to_numpy()),
        "btts_yes": ("binary", dev["btts_yes"].astype(bool).to_numpy()),
        "corner_over_9_5": ("binary", (dev["corner_total_90"] > 9.5).to_numpy()),
    }
    for task, (kind, y) in tasks.items():
        models[task] = fit_market(
            dev[features], y, dev[features], y, n_iter=chosen_iter
        )
        print(f"fit {task} ({kind})")

    # Predict the eval cohort.
    out = eval_df[["match_id", "season_start", "competition"]].copy()
    for task in ("result_90", "over_2_5", "btts_yes", "corner_over_9_5"):
        proba = models[task].predict_proba(eval_df[features])
        if task == "result_90":
            for i, cls in enumerate(models[task].classes_):
                out[f"ml_{cls.lower()}"] = proba[:, i]
        else:
            pos = list(models[task].classes_).index(True)
            out[f"ml_{task}"] = proba[:, pos]
    out.to_parquet(RESULTS_DIR / "ml-predictions-v1.parquet", index=False)

    # Eval performance (report only; the model never trained on these rows).
    merged = out.merge(
        labels[["match_id", "result_90", "over_2_5", "btts_yes", "corner_total_90"]],
        on="match_id",
        validate="one_to_one",
    )
    perf: dict[str, Any] = {
        "chosen_max_iter": chosen_iter,
        "n_features": len(features),
        "n_train": len(dev),
        "n_eval": len(out),
    }
    b3 = np.mean(
        [
            (r["ml_h"] - (r["result_90"] == "H")) ** 2
            + (r["ml_d"] - (r["result_90"] == "D")) ** 2
            + (r["ml_a"] - (r["result_90"] == "A")) ** 2
            for _, r in merged.iterrows()
        ]
    )
    perf["ml_1x2_brier"] = round(float(b3), 5)
    for task, ycol in (("over_2_5", "over_2_5"), ("btts_yes", "btts_yes")):
        b = np.mean(
            [(r[f"ml_{task}"] - float(r[ycol])) ** 2 for _, r in merged.iterrows()]
        )
        perf[f"ml_{task}_brier"] = round(float(b), 5)
    merged["corner_over_9_5_label"] = merged["corner_total_90"] > 9.5
    b = np.mean(
        [
            (r["ml_corner_over_9_5"] - float(r["corner_over_9_5_label"])) ** 2
            for _, r in merged.iterrows()
        ]
    )
    perf["ml_corner_over_brier"] = round(float(b), 5)
    with open(RESULTS_DIR / "ml-fit-v1.json", "w") as fh:
        fh.write(json.dumps(perf, indent=2) + "\n")
    print(json.dumps(perf, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
