"""Focused tests for Experiment 023 state-variant filtering and analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "023-state-ablations"))

import importlib.util  # noqa: E402

import state_variants as SV  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exp023_module",
    REPO_ROOT / "experiments" / "023-state-ablations" / "experiment.py",
)
exp023 = importlib.util.module_from_spec(_spec)
sys.modules["exp023_module"] = exp023
_spec.loader.exec_module(exp023)


def _full_state() -> dict:
    return {
        "schema_version": 1,
        "fixture": {
            "competition": "EPL",
            "home_team": "Alpha",
            "away_team": "Beta",
            "season_start": 2025,
            "kickoff_utc": "x",
            "information_cutoff_utc": "y",
        },
        "teams": {
            "home": {
                "elo": 1600.0,
                "elo_games": 100,
                "dom_pos": 3,
                "dom_pts": 30,
                "form_pts_5": 9,
                "gf_5": 8,
                "rest_days": 6,
                "fm_xg_5": 5.5,
                "us_xg_5": 5.2,
                "xi_continuity": 0.8,
                "xi_prior_rating": 6.9,
            },
            "away": {
                "elo": 1500.0,
                "elo_games": 100,
                "dom_pos": 8,
                "dom_pts": 20,
                "form_pts_5": 5,
                "gf_5": 4,
                "rest_days": 7,
                "fm_xg_5": 4.0,
                "xi_continuity": 0.7,
                "xi_prior_rating": 6.5,
            },
        },
        "comparison": {
            "elo_diff": 100.0,
            "elo_exp_home": 0.64,
            "h2h_n": 10,
            "h2h_home_ppg": 1.5,
        },
        "coverage_note": "n",
    }


class TestStateVariants:
    def test_identity_only_strips_everything(self):
        s = SV.filtered_state(_full_state(), "identity_only")
        assert set(s) == {
            "schema_version",
            "fixture",
            "teams",
            "comparison",
            "coverage_note",
        }
        assert s["fixture"]["home_team"] == "Alpha"
        assert s["teams"] == {"home": {}, "away": {}}
        assert s["comparison"] == {}

    def test_identity_elo_group(self):
        s = SV.filtered_state(_full_state(), "identity_elo")
        assert set(s["teams"]["home"]) == {"elo", "elo_games"}
        assert set(s["comparison"]) == {"elo_diff", "elo_exp_home"}
        assert "xi_continuity" not in s["teams"]["home"]

    def test_identity_elo_form_includes_table_form_rest_but_not_xi(self):
        s = SV.filtered_state(_full_state(), "identity_elo_form")
        home = s["teams"]["home"]
        assert "dom_pos" in home and "form_pts_5" in home and "rest_days" in home
        assert "fm_xg_5" in home and "us_xg_5" in home
        assert "xi_continuity" not in home and "xi_prior_rating" not in home
        assert "h2h_n" in s["comparison"]

    def test_full_returns_identical_copy(self):
        orig = _full_state()
        s = SV.filtered_state(orig, "full")
        assert s == orig and s is not orig

    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError):
            SV.filtered_state(_full_state(), "bogus")

    def test_filtering_does_not_mutate_original(self):
        orig = _full_state()
        SV.filtered_state(orig, "identity_only")
        assert orig["teams"]["home"]["elo"] == 1600.0


class TestAnalyze:
    def test_repeat_and_contrasts(self):
        from exp023_module import analyze

        def trial(match, arm, ridx, pH):
            return {
                "error": None,
                "match_id": match,
                "arm": arm,
                "repeat_index": ridx,
                "input_tokens": 100,
                "latency_ms": 5.0,
                "estimated_cost_usd": 0.0,
                "model_returned": "jev-1.13.0",
                "parsed": {
                    "validation": "ok",
                    "one_x_two": {
                        "distribution": {
                            "home_win": pH,
                            "draw": 0.2,
                            "away_win": 0.8 - pH,
                        }
                    },
                    "events": {},
                },
                "fixture_labels": {"result_90": "H"},
            }

        trials = [
            trial("m1", "full_113", 1, 0.6),
            trial("m1", "full_113", 2, 0.6),
            trial("m1", "id_only_113", 1, 0.4),
        ]
        summary = analyze(trials)
        assert summary["totals"]["successful_calls"] == 3
        assert summary["arms"]["full_113"]["n"] == 2  # both repeats scored
        assert "paired_vs_full_113" in summary["arms"]["id_only_113"]
        assert summary["repeat_spread"]["full_113"]["n"] == 1
        assert summary["repeat_spread"]["full_113"]["mean_l1"] == pytest.approx(0.0)
