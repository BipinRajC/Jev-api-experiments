from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features import asof


def load_inputs(derived_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    read = lambda name: pd.read_parquet(derived_dir / f"{name}.parquet")  # noqa: E731
    return read("matches"), read("team_stats"), read("understat_team_match"), read("players")


def run(derived_dir: Path) -> pd.DataFrame:
    """Builds data/derived/features.parquet: one row per top-5 / UCL match, as-of the cutoff."""
    matches, team_stats, us_team, players = load_inputs(derived_dir)
    features = asof.build_features(matches, team_stats, us_team, players)
    features.to_parquet(derived_dir / "features.parquet", index=False)
    return features
