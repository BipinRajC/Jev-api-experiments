"""End-to-end leakage test on the real derived tables (skipped when they have not been built)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features import asof, build
from src.utils import REPO_ROOT

DERIVED = REPO_ROOT / "data" / "derived"
pytestmark = pytest.mark.skipif(
    not (DERIVED / "matches.parquet").exists(), reason="derived tables not built (run build-tables)"
)
CUT = pd.Timestamp("2023-01-01", tz="UTC")
LABELS = ["y_goals_home", "y_goals_away", "result_unreliable", "y_decided_by", "result_90"]


def scrambled_inputs():
    matches, stats, us, players = build.load_inputs(DERIVED)
    rng = np.random.default_rng(7)
    late = matches["kickoff_utc"] >= CUT
    shuffled = matches.copy()
    cols = ["final_home_goals", "final_away_goals", "goals_90_home", "goals_90_away"]
    order = rng.permutation(late.sum())  # permute whole rows so each match keeps a consistent score pair
    shuffled.loc[late, cols] = matches.loc[late, cols].to_numpy()[order]
    late_ids = set(matches.loc[late, "match_id"])

    def jitter(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        out = df.copy()
        rows = out["match_id"].isin(late_ids)
        for col in columns:
            if not pd.api.types.is_numeric_dtype(out[col]):
                continue
            out[col] = out[col].astype(float)
            out.loc[rows, col] = out.loc[rows, col] * rng.uniform(0.3, 2.0, rows.sum())
        return out

    stat_cols = [c for c in stats.columns if c not in ("match_id", "team_id", "is_home", "formation", "coach_id", "coach_name")]
    us_cols = [c for c in us.columns if c.startswith("us_")]
    players = players.copy()
    rows = players["match_id"].isin(late_ids)
    players.loc[rows, "rating"] = rng.uniform(4, 10, rows.sum())
    return (matches, stats, us, players), (shuffled, jitter(stats, stat_cols), jitter(us, us_cols), players)


def test_scrambling_everything_from_2023_never_changes_features_before_the_cutoff() -> None:
    original, perturbed = scrambled_inputs()
    a = asof.build_features(*original)
    b = asof.build_features(*perturbed)
    early_a = a[a["cutoff_utc"] <= CUT].drop(columns=LABELS).reset_index(drop=True)
    early_b = b[b["cutoff_utc"] <= CUT].drop(columns=LABELS).reset_index(drop=True)
    assert len(early_a) > 10_000
    pd.testing.assert_frame_equal(early_a, early_b)  # bit-identical, NaNs included
    late_a = a[a["cutoff_utc"] > CUT].drop(columns=LABELS)
    late_b = b[b["cutoff_utc"] > CUT].drop(columns=LABELS)
    assert not late_a.reset_index(drop=True).equals(late_b.reset_index(drop=True))  # the scramble had an effect
