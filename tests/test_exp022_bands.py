"""Focused tests for Experiment 022 band parsing and metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "022-count-bands"))

import importlib.util  # noqa: E402

import band_parsing as BP  # noqa: E402
import band_questions as QB  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exp022_module",
    REPO_ROOT / "experiments" / "022-count-bands" / "experiment.py",
)
exp022 = importlib.util.module_from_spec(_spec)
sys.modules["exp022_module"] = exp022  # allow `from exp022_module import ...` in tests
_spec.loader.exec_module(exp022)


class TestBandDefinitions:
    def test_goal_bands_align_with_line(self):
        over = QB.band_ids_over_line(QB.GOAL_BANDS, 2.5)
        assert over == {"g3", "g4", "g5", "g6", "g7"}
        assert QB.band_index_for_count(QB.GOAL_BANDS, 0) == 0
        assert QB.band_index_for_count(QB.GOAL_BANDS, 7) == 7
        assert QB.band_index_for_count(QB.GOAL_BANDS, 12) == 7

    def test_corner_bands_align_with_line(self):
        over = QB.band_ids_over_line(QB.CORNER_BANDS, 9.5)
        assert over == {"c5", "c6", "c7", "c8", "c9"}
        assert QB.band_index_for_count(QB.CORNER_BANDS, 5) == 0
        assert QB.band_index_for_count(QB.CORNER_BANDS, 9) == 4
        assert QB.band_index_for_count(QB.CORNER_BANDS, 10) == 5
        assert QB.band_index_for_count(QB.CORNER_BANDS, 20) == 9

    def test_score_criteria_limits(self):
        # TypeSafe Score allows at most 10 levels
        assert len(QB.GOAL_BANDS) == 8 <= 10
        assert len(QB.CORNER_BANDS) == 10 <= 10


class TestBandParsing:
    def test_full_distribution_normalized(self):
        raw = {
            "g0": 0.1,
            "g1": 0.1,
            "g2": 0.2,
            "g3": 0.2,
            "g4": 0.2,
            "g5": 0.1,
            "g6": 0.05,
            "g7": 0.05,
        }
        dist, reason, one_hot = BP.parse_band_distribution(
            raw, [b[0] for b in QB.GOAL_BANDS]
        )
        assert reason is None and one_hot is False
        assert sum(dist.values()) == pytest.approx(1.0)
        over = BP.over_probability(dist, QB.GOAL_BANDS, 2.5)
        assert over == pytest.approx(0.2 + 0.2 + 0.1 + 0.05 + 0.05)

    def test_missing_level_rejected(self):
        raw = {"g0": 1.0}  # most levels absent
        dist, reason, _ = BP.parse_band_distribution(raw, [b[0] for b in QB.GOAL_BANDS])
        assert dist is None and reason is not None and "missing" in reason

    def test_zero_sum_rejected(self):
        raw = {b[0]: 0.0 for b in QB.GOAL_BANDS}
        dist, reason, _ = BP.parse_band_distribution(raw, [b[0] for b in QB.GOAL_BANDS])
        assert dist is None and reason is not None

    def test_one_hot_is_degenerate_but_valid(self):
        raw = {b[0]: 0.0 for b in QB.GOAL_BANDS}
        raw["g2"] = 1.0
        dist, reason, one_hot = BP.parse_band_distribution(
            raw, [b[0] for b in QB.GOAL_BANDS]
        )
        assert reason is None and one_hot is True
        assert BP.over_probability(dist, QB.GOAL_BANDS, 2.5) == 0.0

    def test_out_of_range_rejected(self):
        raw = {b[0]: 0.125 for b in QB.GOAL_BANDS}
        raw["g4"] = 1.4
        dist, reason, _ = BP.parse_band_distribution(raw, [b[0] for b in QB.GOAL_BANDS])
        assert dist is None and reason is not None


class TestRPS:
    def test_known_answers(self):
        order = ["a", "b", "c"]
        # perfect distribution on band 1 (index 1): RPS 0
        perfect = {"a": 0.0, "b": 1.0, "c": 0.0}
        assert BP.rps(perfect, order, 1) == pytest.approx(0.0)
        # certain wrong: put everything on c when actual is a
        wrong = {"a": 0.0, "b": 0.0, "c": 1.0}
        # cuts: k=0: (0 - 1)^2 = 1; k=1: (0 - 1)^2 = 1; total 2 / (3-1) = 1.0
        assert BP.rps(wrong, order, 0) == pytest.approx(1.0)
        # uniform on 3 bands, actual index 0: cuts k=0: (1/3-1)^2=4/9; k=1: (2/3-1)^2=1/9; = 5/18
        uni = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
        assert BP.rps(uni, order, 0) == pytest.approx(5 / 18)

    def test_rps_lower_is_better(self):
        order = ["a", "b", "c"]
        good = {"a": 0.7, "b": 0.2, "c": 0.1}
        bad = {"a": 0.1, "b": 0.2, "c": 0.7}
        assert BP.rps(good, order, 0) < BP.rps(bad, order, 0)


class TestQuestionSet:
    def test_frozen_threshold_wordings_match_020(self):
        assert (
            QB.NOUL_THRESHOLD_PROPOSITIONS["over_2_5"]
            == "The match has at least 3 total goals after 90 minutes plus stoppage time."
        )
        assert "9.5" in QB.NOUL_THRESHOLD_PROPOSITIONS["corners_over_9_5"]

    def test_score_level_keys_mapped_to_bands(self):
        """Score answers key probabilities by rubric level index, not band id."""
        from exp022_module import parse_call

        body = {
            "answers": {
                "score_goal_bands": {
                    "type": "score",
                    "score": 2.0,
                    "legend": {},
                    "confidence": 0.9,
                    "probabilities": {
                        "0": 0.1,
                        "1": 0.1,
                        "2": 0.1,
                        "3": 0.15,
                        "4": 0.2,
                        "5": 0.15,
                        "6": 0.1,
                        "7": 0.1,
                    },
                }
            }
        }
        parsed = parse_call("score_goal_bands", body)
        assert parsed["validation"] == "ok"
        dist = parsed["events"]["goal_bands"]["distribution"]
        assert set(dist) == {b[0] for b in QB.GOAL_BANDS}
        assert parsed["events"]["goal_bands"]["over_2_5"] == pytest.approx(
            0.15 + 0.2 + 0.15 + 0.1 + 0.1
        )

    def test_score_missing_level_rejected(self):
        from exp022_module import parse_call

        body = {
            "answers": {
                "score_goal_bands": {
                    "type": "score",
                    "score": 2.0,
                    "legend": {},
                    "confidence": 0.9,
                    "probabilities": {"0": 0.5, "2": 0.5},  # levels 1,3..7 absent
                }
            }
        }
        parsed = parse_call("score_goal_bands", body)
        assert parsed["validation"] == "rejected"

    def test_arm_questions_shapes(self):
        from exp022_module import arm_questions

        assert set(arm_questions("noul_thresholds")) == {"over_2_5", "corners_over_9_5"}
        assert set(arm_questions("score_goal_bands")) == {"score_goal_bands"}
        assert set(arm_questions("choice_corner_bands")) == {"choice_corner_bands"}
        q = arm_questions("score_corner_bands")["score_corner_bands"]
        assert len(q["criteria"]) == 10
