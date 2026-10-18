from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features import asof


def load_inputs(derived_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    read = lambda name: pd.read_parquet(derived_dir / f"{name}.parquet")  # noqa: E731
    return read("matches"), read("team_stats"), read("understat_team_match"), read("players")


def run(derived_dir: Path) -> pd.DataFrame:
    """Build historical features and a separate label-free table for direct model ingestion."""
    matches, team_stats, us_team, players = load_inputs(derived_dir)
    features = asof.build_features(matches, team_stats, us_team, players)
    features.to_parquet(derived_dir / "features.parquet", index=False)
    label_columns = [c for c in features if c.startswith("y_") or c in {"result_90", "result_unreliable"}]
    model_inputs = features.drop(columns=label_columns)
    model_inputs.to_parquet(derived_dir / "model_inputs.parquet", index=False)
    upcoming_path = derived_dir / "upcoming.parquet"
    if upcoming_path.exists():
        upcoming = pd.read_parquet(upcoming_path)
        future = asof.build_upcoming_features(matches, team_stats, us_team, players, upcoming) if not upcoming.empty else model_inputs.iloc[0:0].copy()
        future.to_parquet(derived_dir / "upcoming_inputs.parquet", index=False)
    return features
