"""Regression tests for Experiment 021 arm questions and protocol integrity."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "exp021_module",
    REPO_ROOT / "experiments" / "021-retrospective-locked" / "experiment.py",
)
exp021 = importlib.util.module_from_spec(_spec)
sys.modules["exp021_module"] = exp021
_spec.loader.exec_module(exp021)


def test_choice_1x2_sends_a_single_choice_question():
    """Regression: choice_1x2 previously fell through to the score branch."""
    q = exp021.arm_questions("choice_1x2")
    assert list(q.keys()) == ["result_1x2"]
    assert q["result_1x2"]["type"] == "choice"
    assert set(q["result_1x2"]["criteria"]) == {"home", "draw", "away"}


def test_choice_binary_sends_choice_questions():
    q = exp021.arm_questions("choice_binary")
    assert set(q) == {"over_2_5", "btts_yes", "corners_over_9_5"}
    assert all(v["type"] == "choice" for v in q.values())


def test_noul_and_score_arms_unchanged():
    assert all(v["type"] == "noul" for v in exp021.arm_questions("noul_1x2").values())
    assert all(v["type"] == "noul" for v in exp021.arm_questions("noul_binary").values())
    assert all(v["type"] == "score" for v in exp021.arm_questions("score_1x2").values())
    assert all(v["type"] == "score" for v in exp021.arm_questions("score_binary").values())
