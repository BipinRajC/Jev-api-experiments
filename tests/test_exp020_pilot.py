"""Focused tests for Experiment 020 parsing, selection, and metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import parsing as P  # noqa: E402
import questions as Q  # noqa: E402
import selection as SEL  # noqa: E402


# ---------------------------------------------------------------------------
# Known-answer metric tests


class TestMetrics:
    def test_brier_binary_known_answers(self):
        assert P.brier_binary(0.8, True) == pytest.approx(0.04)
        assert P.brier_binary(0.8, False) == pytest.approx(0.64)
        assert P.brier_binary(0.5, True) == pytest.approx(0.25)
        assert P.brier_binary(None, True) is None
        assert P.brier_binary(0.5, None) is None

    def test_brier_three_way_known_answers(self):
        perfect = {"home_win": 1.0, "draw": 0.0, "away_win": 0.0}
        assert P.brier_three_way(perfect, "H") == pytest.approx(0.0)
        uniform = {"home_win": 1 / 3, "draw": 1 / 3, "away_win": 1 / 3}
        # uniform: (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = 4/9 + 1/9 + 1/9 = 6/9
        assert P.brier_three_way(uniform, "H") == pytest.approx(6 / 9)
        assert P.brier_three_way(uniform, "X") is None
        assert P.brier_three_way({"home_win": 1.0}, "H") is None

    def test_log_loss_fixed_floor(self):
        # floor prevents infinite loss
        assert P.log_loss_fixed_floor(1.0, True) == pytest.approx(-np.log(0.99))
        assert P.log_loss_fixed_floor(0.0, False) == pytest.approx(-np.log(0.99))
        assert P.log_loss_fixed_floor(0.5, True) == pytest.approx(np.log(2))
        assert P.log_loss_fixed_floor(0.8, True) == pytest.approx(-np.log(0.8))

    def test_log_loss_three_way(self):
        probs = {"home_win": 0.6, "draw": 0.3, "away_win": 0.1}
        assert P.log_loss_three_way_fixed_floor(probs, "H") == pytest.approx(
            -np.log(0.6)
        )
        # floor applies when the realised outcome has a tiny probability
        assert P.log_loss_three_way_fixed_floor(probs, "A") == pytest.approx(
            -np.log(0.1)
        )
        tiny = {"home_win": 0.0, "draw": 0.0, "away_win": 1.0}
        assert P.log_loss_three_way_fixed_floor(tiny, "H") == pytest.approx(
            -np.log(0.01)
        )


# ---------------------------------------------------------------------------
# Parsing / validation tests


class TestParsers:
    def test_noul_accepts_and_rejects(self):
        assert P.parse_noul_event(0.66) == (0.66, None)
        assert P.parse_noul_event(0)[0] == 0.0
        assert P.parse_noul_event(1)[0] == 1.0
        assert P.parse_noul_event(None)[1] is not None
        assert P.parse_noul_event(float("nan"))[1] is not None
        assert P.parse_noul_event(1.2)[1] is not None
        assert P.parse_noul_event(-0.1)[1] is not None
        assert P.parse_noul_event(True)[1] is not None  # bool is not a probability

    def test_score_maps_to_eighths(self):
        assert P.parse_score_event(0) == (0.0, None)
        assert P.parse_score_event(4) == (0.5, None)
        assert P.parse_score_event(8) == (1.0, None)
        assert P.parse_score_event(2.4) == (0.3, None)  # interpolated scores allowed
        assert P.parse_score_event(8.5)[1] is not None
        assert P.parse_score_event(-1)[1] is not None

    def test_choice_binary_uses_yes(self):
        assert P.parse_choice_binary({"yes": 0.7, "no": 0.3}) == (0.7, None)
        assert P.parse_choice_binary({"no": 1.0})[1] is not None
        assert P.parse_choice_binary({"yes": 1.4})[1] is not None
        assert P.parse_choice_binary("yes")[1] is not None

    def test_normalize_three_way(self):
        dist, reason = P.normalize_three_way(
            {"home_win": 0.4, "draw": 0.3, "away_win": 0.2}
        )
        assert reason is None
        assert sum(dist.values()) == pytest.approx(1.0)
        assert dist["home_win"] == pytest.approx(0.4 / 0.9)
        # zero-sum rejected, never normalized
        dist, reason = P.normalize_three_way(
            {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        )
        assert dist is None and reason is not None
        # missing key rejected
        dist, reason = P.normalize_three_way({"home_win": 0.5, "draw": 0.5})
        assert dist is None and reason is not None

    def test_choice_1x2_validated_and_ordered(self):
        dist, reason = P.parse_choice_1x2({"home": 0.5, "draw": 0.25, "away": 0.25})
        assert reason is None
        assert set(dist) == {"home_win", "draw", "away_win"}
        assert sum(dist.values()) == pytest.approx(1.0)
        # one-hot choice still yields a valid distribution
        dist, reason = P.parse_choice_1x2({"home": 1.0, "draw": 0.0, "away": 0.0})
        assert reason is None and dist["home_win"] == 1.0
        # missing key rejected
        assert P.parse_choice_1x2({"home": 1.0})[1] is not None

    def test_parse_call_full_choice_1x2_body(self):
        from experiment import parse_call

        body = {
            "answers": {
                "result_1x2": {
                    "type": "choice",
                    "choice": "home",
                    "probabilities": {"home": 0.6, "draw": 0.3, "away": 0.1},
                    "confidence": 0.9,
                }
            }
        }
        parsed = parse_call("choice_1x2", body)
        assert parsed["validation"] == "ok"
        assert parsed["one_x_two"]["distribution"]["home_win"] == pytest.approx(0.6)
        # confidence is never the probability
        assert parsed["one_x_two"]["confidence"] == 0.9

    def test_parse_call_rejects_missing_answer(self):
        from experiment import parse_call

        body = {
            "answers": {
                "home_win": {"type": "noul", "noul": 0.5},
                "draw": {"type": "noul", "noul": 0.3},
            }
        }
        parsed = parse_call("noul_1x2", body)
        assert parsed["validation"] == "rejected"  # away_win missing -> zero/absent sum

    def test_parse_call_score_binary(self):
        from experiment import parse_call

        body = {
            "answers": {
                "over_2_5": {
                    "type": "score",
                    "score": 6.0,
                    "probabilities": {"6": 1.0},
                    "legend": {},
                    "confidence": 0.9,
                },
                "btts_yes": {
                    "type": "score",
                    "score": 2.0,
                    "probabilities": {"2": 1.0},
                    "legend": {},
                    "confidence": 0.9,
                },
                "corners_over_9_5": {
                    "type": "score",
                    "score": 4.0,
                    "probabilities": {"4": 1.0},
                    "legend": {},
                    "confidence": 0.9,
                },
            }
        }
        parsed = parse_call("score_binary", body)
        assert parsed["validation"] == "ok"
        assert parsed["events"]["over_2_5"]["prob"] == pytest.approx(0.75)
        assert parsed["events"]["btts_yes"]["prob"] == pytest.approx(0.25)
        assert parsed["events"]["corners_over_9_5"]["prob"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Analysis regression


class TestAnalysis:
    def test_repeat_pairs_regression(self):
        """Regression: analyze() must build the r1 index before the r2 diff loop."""
        from experiment import analyze

        protocol = {
            "fixtures": [
                {
                    "match_id": "m1",
                    "labels": {
                        "result_90": "H",
                        "over_2_5": True,
                        "btts_yes": False,
                        "corner_over_9_5": True,
                    },
                }
            ],
            "eligibility_exclusions": [],
        }

        def trial(ridx, prob):
            return {
                "repeat_index": ridx,
                "match_id": "m1",
                "arm": "noul_binary",
                "error": None,
                "input_tokens": None,
                "estimated_cost_usd": None,
                "parsed": {
                    "validation": "ok",
                    "events": {"over_2_5": {"prob": prob, "reject": None}},
                    "one_x_two": {"distribution": None},
                },
            }

        summary = analyze([trial(1, 0.6), trial(2, 0.7)], protocol)
        assert summary["totals"]["repeat_pairs"] == 1
        assert summary["repeat_spread"]["over_2_5"]["n_pairs"] == 1
        assert summary["repeat_spread"]["over_2_5"]["mean_abs_diff"] == pytest.approx(
            0.1
        )


# ---------------------------------------------------------------------------
# Question set invariants


class TestQuestionSet:
    def test_nine_score_levels(self):
        assert len(Q.SCORE_CRITERIA) == 9
        assert [c["score"] for c in Q.SCORE_CRITERIA] == list(range(9))

    def test_corner_line_wording(self):
        assert "9.5" in Q.PROPOSITIONS["corners_over_9_5"]

    def test_arm_questions_cover_expected_events(self):
        from experiment import arm_questions

        assert set(arm_questions("noul_1x2")) == {"home_win", "draw", "away_win"}
        assert set(arm_questions("noul_binary")) == {
            "over_2_5",
            "btts_yes",
            "corners_over_9_5",
        }
        assert set(arm_questions("score_1x2")) == {"home_win", "draw", "away_win"}
        assert set(arm_questions("score_binary")) == {
            "over_2_5",
            "btts_yes",
            "corners_over_9_5",
        }
        assert set(arm_questions("choice_1x2")) == {"result_1x2"}
        assert set(arm_questions("choice_binary")) == {
            "over_2_5",
            "btts_yes",
            "corners_over_9_5",
        }
        # control arms use Noul 1X2 questions
        assert set(arm_questions("ctrl_namesdate_noul_1x2")) == {
            "home_win",
            "draw",
            "away_win",
        }
        assert set(arm_questions("ctrl_anon_noul_1x2")) == {
            "home_win",
            "draw",
            "away_win",
        }


# ---------------------------------------------------------------------------
# Selection determinism on synthetic data


def _synthetic_frames(n_per_comp=40):
    rng = np.random.RandomState(7)
    rows, labs, matches = [], [], []
    for comp in SEL.COMPETITION_ORDER:
        for i in range(n_per_comp):
            mid = f"{comp}_{i}"
            elo_diff = rng.normal(0, 200)
            rows.append(
                {
                    "match_id": mid,
                    "competition": comp,
                    "season_start": 2025,
                    "round": f"R{i}",
                    "kickoff_utc": pd.Timestamp("2025-08-01")
                    + pd.Timedelta(days=i, hours=i % 5),
                    "elo_diff": elo_diff,
                }
            )
            labs.append(
                {
                    "match_id": mid,
                    "label_valid_90": True,
                    "result_90": "H",
                    "goals_home_90": 1,
                    "goals_away_90": 0,
                    "over_2_5": False,
                    "btts_yes": False,
                    "corner_total_90": 9.0 + (i % 3),
                    "corner_source": "fotmob",
                    "corner_conflict": False,
                }
            )
            matches.append(
                {
                    "match_id": mid,
                    "home_name": f"H {comp}",
                    "away_name": f"A {comp}",
                    "kickoff_disagreement": False,
                    "details_pending": False,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(labs), pd.DataFrame(matches)


class TestSelection:
    def test_deterministic_and_stratified(self):
        inputs, labels, matches = _synthetic_frames()
        s1, ex1 = SEL.select_fixtures(inputs, labels, matches)
        s2, ex2 = SEL.select_fixtures(inputs, labels, matches)
        pd.testing.assert_frame_equal(s1, s2)
        assert len(s1) == SEL.PER_COMPETITION * len(SEL.COMPETITION_ORDER)
        assert s1["competition"].value_counts().eq(SEL.PER_COMPETITION).all()
        assert ex1 and ex1[0]["n_excluded"] == 0

    def test_exclusion_groups_applied(self):
        inputs, labels, matches = _synthetic_frames()
        labels.loc[labels.index[0], "corner_conflict"] = True
        labels.loc[labels.index[1], "corner_total_90"] = None
        matches.loc[matches.index[2], "kickoff_disagreement"] = True
        matches.loc[matches.index[3], "details_pending"] = True
        selected, exclusions = SEL.select_fixtures(inputs, labels, matches)
        assert exclusions[0]["n_excluded"] == 4
        assert len(selected) == SEL.PER_COMPETITION * len(SEL.COMPETITION_ORDER)

    def test_repeat_subset_covers_competitions(self):
        inputs, labels, matches = _synthetic_frames()
        selected, _ = SEL.select_fixtures(inputs, labels, matches)
        subset = SEL.repeat_subset(selected)
        assert len(subset) == SEL.REPEAT_SUBSET_N
        assert len(set(subset)) == len(subset)
        chosen = selected.set_index("match_id").loc[subset]
        assert set(chosen["competition"]) <= set(SEL.COMPETITION_ORDER)

    def test_selection_is_seed_sensitive(self):
        inputs, labels, matches = _synthetic_frames()
        s1, _ = SEL.select_fixtures(inputs, labels, matches, seed=1)
        s2, _ = SEL.select_fixtures(inputs, labels, matches, seed=999)
        assert list(s1["match_id"]) != list(s2["match_id"])
