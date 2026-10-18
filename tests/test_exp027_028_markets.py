"""Focused tests for Experiments 027 and 028."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "024-prospective-series"))

_spec27 = importlib.util.spec_from_file_location(
    "exp027_questions",
    REPO_ROOT / "experiments" / "027-lines-and-totals" / "questions.py",
)
Q27 = importlib.util.module_from_spec(_spec27)
_spec27.loader.exec_module(Q27)

_spec28 = importlib.util.spec_from_file_location(
    "exp028_questions", REPO_ROOT / "experiments" / "028-first-goal" / "questions.py"
)
Q28 = importlib.util.module_from_spec(_spec28)
sys.modules["exp028_questions"] = Q28
_spec28.loader.exec_module(Q28)


class TestQ027:
    def test_question_shapes(self):
        nq = Q27.noul_lines_questions()
        assert set(nq) == {
            "total_goals_over_1_5",
            "total_goals_over_3_5",
            "corners_over_11_5",
        }
        assert all(q["type"] == "noul" for q in nq.values())
        sq = Q27.score_lines_questions()
        assert all(len(q["criteria"]) == 9 for q in sq.values())
        cq = Q27.choice_lines_questions()
        assert all(set(q["criteria"]) == {"yes", "no"} for q in cq.values())

    def test_corner_line_wording(self):
        assert "11.5" in Q27.PROPOSITIONS["corners_over_11_5"]


class TestQ028:
    def test_first_goal_choice_shape(self):
        q = Q28.choice_first_goal_question()
        assert set(q["first_goal"]["criteria"]) == {"home", "away", "no_goal"}

    def test_parse_first_goal_choice_valid(self):
        body = {
            "answers": {
                "first_goal": {
                    "type": "choice",
                    "choice": "home",
                    "probabilities": {"home": 0.5, "away": 0.3, "no_goal": 0.2},
                    "confidence": 0.8,
                }
            }
        }
        parsed = Q28.parse_first_goal_choice(body)
        assert parsed["validation"] == "ok"
        assert parsed["first_goal"]["distribution"]["home"] == pytest.approx(0.5)
        assert parsed["first_goal"]["choice"] == "home"

    def test_parse_first_goal_choice_missing_key_rejected(self):
        body = {
            "answers": {
                "first_goal": {
                    "type": "choice",
                    "probabilities": {"home": 0.7, "away": 0.3},
                    "confidence": 0.9,
                }
            }
        }
        assert Q28.parse_first_goal_choice(body)["validation"] == "rejected"

    def test_build_first_goal_labels(self):
        shots = pd.DataFrame(
            [
                # m1: away scores first (minute 10), home equalizes later
                {
                    "match_id": "m1",
                    "team_id": 200,
                    "minute": 10.0,
                    "minute_added": 0.0,
                    "period": "FirstHalf",
                    "event_type": "Goal",
                    "is_own_goal": False,
                },
                {
                    "match_id": "m1",
                    "team_id": 100,
                    "minute": 80.0,
                    "minute_added": 0.0,
                    "period": "SecondHalf",
                    "event_type": "Goal",
                    "is_own_goal": False,
                },
                # m2: home goal at 5; extra-time goal ignored
                {
                    "match_id": "m2",
                    "team_id": 100,
                    "minute": 5.0,
                    "minute_added": 0.0,
                    "period": "FirstHalf",
                    "event_type": "Goal",
                    "is_own_goal": False,
                },
                {
                    "match_id": "m2",
                    "team_id": 100,
                    "minute": 95.0,
                    "minute_added": 0.0,
                    "period": "SecondHalfExtra",
                    "event_type": "Goal",
                    "is_own_goal": False,
                },
                # m3: own goal by the home team (team 100) → benefits away
                {
                    "match_id": "m3",
                    "team_id": 100,
                    "minute": 30.0,
                    "minute_added": 0.0,
                    "period": "FirstHalf",
                    "event_type": "Goal",
                    "is_own_goal": True,
                },
                # m4: shot map exists but no goals → no_goal
                {
                    "match_id": "m4",
                    "team_id": 100,
                    "minute": 12.0,
                    "minute_added": 0.0,
                    "period": "FirstHalf",
                    "event_type": "Miss",
                    "is_own_goal": False,
                },
            ]
        )
        matches = pd.DataFrame(
            [
                {"match_id": "m1", "home_id": 100, "away_id": 200},
                {"match_id": "m2", "home_id": 100, "away_id": 200},
                {"match_id": "m3", "home_id": 100, "away_id": 200},
                {"match_id": "m4", "home_id": 100, "away_id": 200},
                {
                    "match_id": "m5",
                    "home_id": 100,
                    "away_id": 200,
                },  # no shot map at all
            ]
        )
        out = Q28.build_first_goal_labels(shots, matches).set_index("match_id")
        assert out.at["m1", "first_goal"] == "away"
        assert out.at["m2", "first_goal"] == "home"
        assert out.at["m3", "first_goal"] == "away"  # own goal by home benefits away
        assert out.at["m4", "first_goal"] == "no_goal"
        assert out.at["m5", "first_goal"] is None  # no shot map → never guessed


class TestRunnerWiring:
    def test_all_extension_arms_registered(self):
        import predict_due as PD

        expected = {
            "noul_ext",
            "score_ext",
            "choice_ext",
            "noul_lines",
            "score_lines",
            "choice_lines",
            "noul_first",
            "score_first",
            "choice_first",
        }
        assert expected <= set(PD.ARMS)
        for arm in expected:
            questions, qset = PD.arm_questions_for(arm)
            assert len(questions) >= 1 and qset.startswith("QSET-0")

    def test_parse_call_handles_lines_and_first_noul(self):
        import importlib.util

        _spec20 = importlib.util.spec_from_file_location(
            "exp020_for_027_test",
            REPO_ROOT / "experiments" / "020-football-pilot" / "experiment.py",
        )
        exp020 = importlib.util.module_from_spec(_spec20)
        _spec20.loader.exec_module(exp020)
        parse_call = exp020.parse_call

        body = {
            "answers": {
                "total_goals_over_1_5": {"type": "noul", "noul": 0.77},
                "total_goals_over_3_5": {"type": "noul", "noul": 0.31},
                "corners_over_11_5": {"type": "noul", "noul": 0.29},
            }
        }
        parsed = parse_call("noul_lines", body)
        assert parsed["validation"] == "ok"
        assert parsed["events"]["total_goals_over_1_5"]["prob"] == pytest.approx(0.77)
        # 028 noul arm parses through the same generic path
        body_first = {
            "answers": {
                "first_goal_home": {"type": "noul", "noul": 0.55},
                "first_goal_away": {"type": "noul", "noul": 0.35},
            }
        }
        assert parse_call("noul_first", body_first)["validation"] == "ok"
