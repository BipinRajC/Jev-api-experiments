"""Deterministic stratified fixture selection for Experiment 020.

Selects 48 completed 2025/26 fixtures (8 per target competition) stratified by
absolute Elo difference (prior-strength terciles), seeded, from fixtures that
are eligible for all four core markets:
  - label_valid_90 true (goal markets)
  - corner_total_90 non-null and corner_conflict false (corner market)
  - kickoff_disagreement false (recorded exclusion group)
  - details not pending
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 20261020
PER_COMPETITION = 8
COMPETITION_ORDER = ("EPL", "LALIGA", "BUNDESLIGA", "SERIEA", "LIGUE1", "UCL")
SEASON_START = 2025
REPEAT_SUBSET_N = 8


def select_fixtures(
    inputs: pd.DataFrame,
    labels: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    seed: int = SEED,
    per_competition: int = PER_COMPETITION,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Return (selected_frame, exclusion_log).

    inputs: model_inputs.parquet rows for the season.
    labels: market_labels.parquet.
    matches: matches.parquet (kickoff_disagreement, details_pending).
    """
    season = inputs[inputs["season_start"] == SEASON_START].copy()
    label_cols = [
        c for c in labels.columns if c != "competition"
    ]  # keep the inputs' competition column
    frame = season.merge(labels[label_cols], on="match_id", validate="one_to_one")
    frame = frame.merge(
        matches[["match_id", "kickoff_disagreement", "details_pending"]],
        on="match_id",
        validate="one_to_one",
    )

    exclusions: list[dict[str, object]] = []
    eligible = frame[
        frame["label_valid_90"].fillna(False).astype(bool)
        & frame["corner_total_90"].notna()
        & ~frame["corner_conflict"].fillna(False).astype(bool)
        & ~frame["kickoff_disagreement"].fillna(False).astype(bool)
        & ~frame["details_pending"].fillna(False).astype(bool)
    ].copy()
    exclusions.append(
        {
            "stage": "eligibility",
            "reason": "failed one of label_valid_90 / corner label / conflict / disagreement / pending",
            "n_excluded": int(len(frame) - len(eligible)),
        }
    )

    eligible["abs_elo_diff"] = eligible["elo_diff"].abs()
    rng = np.random.RandomState(seed)
    picks: list[pd.DataFrame] = []
    for competition in COMPETITION_ORDER:
        pool = eligible[eligible["competition"] == competition].sort_values(
            "kickoff_utc"
        )
        if len(pool) < per_competition:
            raise ValueError(f"{competition}: only {len(pool)} eligible fixtures")
        try:
            tercile = pd.qcut(pool["abs_elo_diff"], 3, labels=["low", "mid", "high"])
        except ValueError:
            tercile = pd.Series(["mid"] * len(pool), index=pool.index)
        pool = pool.assign(strength_tercile=tercile.astype(object))
        per_bin = per_competition // 3
        remainder = per_competition - 3 * per_bin
        names = ("low", "mid", "high")
        allocation = {names[i]: per_bin + (1 if i < remainder else 0) for i in range(3)}
        for bin_name, take in allocation.items():
            bin_pool = pool[pool["strength_tercile"] == bin_name]
            if len(bin_pool) < take:
                bin_pool = pool
            idx = rng.choice(bin_pool.index, size=take, replace=False)
            picks.append(pool.loc[idx])
    selected = pd.concat(picks).sort_values("kickoff_utc").reset_index(drop=True)
    return selected, exclusions


def repeat_subset(
    selected: pd.DataFrame, *, seed: int = SEED, n: int = REPEAT_SUBSET_N
) -> list[str]:
    """Seeded repeat subset covering every competition at least once when possible."""
    rng = np.random.RandomState(seed + 1)
    frame = selected.reset_index(drop=True)
    order = []
    for competition in COMPETITION_ORDER:
        ids = frame.loc[frame["competition"] == competition, "match_id"].tolist()
        if ids:
            order.append(ids[int(rng.randint(len(ids)))])
    remaining = [m for m in frame["match_id"] if m not in order]
    while len(order) < n and remaining:
        order.append(remaining.pop(int(rng.randint(len(remaining)))))
    return order[:n]
