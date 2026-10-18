"""Focused tests for Experiment 024 due-window and settlement logic."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "024-prospective-series"))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))


def _upcoming_row(kickoff: datetime, match_id: str = "m1") -> dict:
    return {
        "match_id": match_id,
        "competition": "EPL",
        "season_start": 2026,
        "round": "9",
        "kickoff_utc": kickoff,
        "cutoff_utc": kickoff - timedelta(minutes=60),
        "home_name": "Alpha",
        "away_name": "Beta",
    }


class TestDueWindow:
    def test_due_selection(self, monkeypatch, tmp_path):
        import predict_due as PD

        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        rows = [
            _upcoming_row(now + timedelta(minutes=70)),  # due
            _upcoming_row(now + timedelta(minutes=90), "m2"),  # not yet due
            _upcoming_row(now + timedelta(minutes=30), "m3"),  # cutoff passed
        ]
        upcoming = pd.DataFrame(rows)
        inputs = pd.DataFrame(
            [
                {
                    "match_id": r["match_id"],
                    "home_elo": 1500,
                    "away_elo": 1500,
                }
                for r in rows
            ]
        )
        monkeypatch.setattr(PD, "DERIVED_DIR", tmp_path)
        upcoming.to_parquet(tmp_path / "upcoming.parquet")
        inputs.to_parquet(tmp_path / "upcoming_inputs.parquet")
        monkeypatch.setattr(PD, "predicted_keys", lambda: set())

        due, diag = PD.load_due_fixtures(now)
        assert [d["match_id"] for d in due] == ["m1"]
        assert (
            diag["n_due"] == 1
            and diag["n_cutoff_passed"] == 1
            and diag["n_not_due_yet"] == 1
        )
        assert due[0]["minutes_to_kickoff_at_selection"] == pytest.approx(70.0)

    def test_already_predicted_skipped(self, monkeypatch, tmp_path):
        import predict_due as PD

        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        rows = [_upcoming_row(now + timedelta(minutes=70))]
        upcoming = pd.DataFrame(rows)
        inputs = pd.DataFrame([{"match_id": "m1", "home_elo": 1500, "away_elo": 1500}])
        monkeypatch.setattr(PD, "DERIVED_DIR", tmp_path)
        upcoming.to_parquet(tmp_path / "upcoming.parquet")
        inputs.to_parquet(tmp_path / "upcoming_inputs.parquet")
        all_arms = {f"m1:{a}" for a in PD.ARMS}
        monkeypatch.setattr(PD, "predicted_keys", lambda: all_arms)

        due, diag = PD.load_due_fixtures(now)
        assert due == []
        assert diag["n_already_predicted"] == 1

    def test_state_contains_no_result_fields(self, monkeypatch, tmp_path):
        import predict_due as PD

        now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        row = _upcoming_row(now + timedelta(minutes=70))
        row_with_labels = {
            **row,
            "result_90": "H",
            "goals_home_90": 3,
            "over_2_5": True,
            "btts_yes": True,
            "corner_total_90": 11,
        }
        upcoming = pd.DataFrame([row])
        inputs = pd.DataFrame([row_with_labels])
        monkeypatch.setattr(PD, "DERIVED_DIR", tmp_path)
        upcoming.to_parquet(tmp_path / "upcoming.parquet")
        inputs.to_parquet(tmp_path / "upcoming_inputs.parquet")
        monkeypatch.setattr(PD, "predicted_keys", lambda: set())

        due, _ = PD.load_due_fixtures(now)
        assert len(due) == 1
        blob = json.dumps(due[0]["state"])
        for forbidden in (
            "result_90",
            "goals_home_90",
            "over_2_5",
            "btts_yes",
            "corner_total_90",
            "odds",
        ):
            assert forbidden not in blob


class TestQuoteMatching:
    def test_only_quotes_within_15_minutes_before_request(self, monkeypatch, tmp_path):
        import predict_due as PD

        request_time = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        rows = [
            {
                "match_id": "m1",
                "captured_at_utc": request_time - timedelta(minutes=5),
                "provider": "espn",
                "market": "1X2",
                "side": "home",
                "line": None,
                "decimal_odds": 1.5,
                "price_semantics": "displayed_close_unverified",
                "source_file": "x",
            },
            {
                "match_id": "m1",
                "captured_at_utc": request_time - timedelta(minutes=40),
                "provider": "espn",
                "market": "1X2",
                "side": "home",
                "line": None,
                "decimal_odds": 1.4,
                "price_semantics": "displayed_close_unverified",
                "source_file": "y",
            },
            {
                "match_id": "m1",
                "captured_at_utc": request_time + timedelta(minutes=5),
                "provider": "espn",
                "market": "1X2",
                "side": "home",
                "line": None,
                "decimal_odds": 1.6,
                "price_semantics": "displayed_close_unverified",
                "source_file": "z",
            },
            {
                "match_id": "m2",
                "captured_at_utc": request_time - timedelta(minutes=1),
                "provider": "espn",
                "market": "1X2",
                "side": "home",
                "line": None,
                "decimal_odds": 2.0,
                "price_semantics": "displayed_close_unverified",
                "source_file": "w",
            },
        ]
        quotes = pd.DataFrame(rows)
        monkeypatch.setattr(PD, "DERIVED_DIR", tmp_path)
        quotes.to_parquet(tmp_path / "forward_quotes.parquet")

        out = PD.matching_quotes("m1", request_time)
        assert len(out) == 1
        assert out[0]["decimal_odds"] == 1.5


class TestExtensionArms:
    def test_026_questions_registered(self):
        import importlib.util

        _spec = importlib.util.spec_from_file_location(
            "exp026_questions_test",
            REPO_ROOT / "experiments" / "026-market-extension" / "questions.py",
        )
        Q26 = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(Q26)

        assert Q26.QUESTION_SET_VERSION == "QSET-026-v1"
        assert set(Q26.EXTENSION_EVENTS) == {
            "home_team_over_1_5",
            "away_team_over_1_5",
            "handicap_home_minus_1_5",
            "first_half_over_1_5",
        }
        nq = Q26.noul_ext_questions()
        assert len(nq) == 4 and all(q["type"] == "noul" for q in nq.values())
        sq = Q26.score_ext_questions()
        assert all(len(q["criteria"]) == 9 for q in sq.values())
        cq = Q26.choice_ext_questions()
        assert all(set(q["criteria"]) == {"yes", "no"} for q in cq.values())

    def test_runner_has_extension_arms_and_versions(self):
        import predict_due as PD

        assert {"noul_ext", "score_ext", "choice_ext"} <= set(PD.ARMS)
        for arm in ("noul_ext", "score_ext", "choice_ext"):
            questions, qset = PD.arm_questions_for(arm)
            assert qset == "QSET-026-v1"
            assert len(questions) == 4
        # core arms keep the frozen 020 question set
        _, core_qset = PD.arm_questions_for("noul_1x2")
        assert core_qset == "QSET-020-v1"

    def test_parse_call_handles_extension_arms(self):
        from experiment import parse_call

        body = {
            "answers": {
                "home_team_over_1_5": {"type": "noul", "noul": 0.44},
                "away_team_over_1_5": {"type": "noul", "noul": 0.34},
                "handicap_home_minus_1_5": {"type": "noul", "noul": 0.23},
                "first_half_over_1_5": {"type": "noul", "noul": 0.35},
            }
        }
        parsed = parse_call("noul_ext", body)
        assert parsed["validation"] == "ok"
        assert parsed["events"]["home_team_over_1_5"]["prob"] == pytest.approx(0.44)


class TestSettlement:
    def test_settlement_appends_and_is_idempotent(self, monkeypatch, tmp_path):
        import settle as S

        results = tmp_path / "results" / S.EXPERIMENT_ID
        results.mkdir(parents=True)
        pred = {
            "experiment_id": S.EXPERIMENT_ID,
            "run_local_id": "m1:noul_1x2",
            "match_id": "m1",
            "arm": "noul_1x2",
            "validation": "ok",
            "pre_cutoff": True,
        }
        (results / "predictions.jsonl").write_text(json.dumps(pred) + "\n")

        labels = pd.DataFrame(
            [
                {
                    "match_id": "m1",
                    "label_valid_90": True,
                    "result_90": "H",
                    "goals_home_90": 3.0,
                    "goals_away_90": 1.0,
                    "over_2_5": True,
                    "btts_yes": True,
                    "corner_total_90": 10.0,
                    "corner_conflict": False,
                }
            ]
        )
        derived = tmp_path
        labels.to_parquet(derived / "market_labels.parquet")
        odds = pd.DataFrame(
            [{"match_id": "m1", "fd_stat_HTHG": 2.0, "fd_stat_HTAG": 0.0}]
        )
        odds.to_parquet(derived / "odds.parquet")
        monkeypatch.setattr(S, "PREDICTIONS_PATH", results / "predictions.jsonl")
        monkeypatch.setattr(S, "SETTLEMENTS_PATH", results / "settlements.jsonl")
        monkeypatch.setattr(S, "DERIVED_DIR", derived)

        assert S.main([]) == 0
        recs = [
            json.loads(l)
            for l in (results / "settlements.jsonl").read_text().splitlines()
            if l.strip()
        ]
        assert len(recs) == 1
        assert recs[0]["result_90"] == "H" and recs[0]["goals_home_90"] == 3.0
        # 026 extension-market labels
        assert recs[0]["home_team_over_1_5"] is True
        assert recs[0]["away_team_over_1_5"] is False
        assert recs[0]["handicap_home_minus_1_5"] is True
        assert recs[0]["first_half_home_goals"] == 2.0
        assert recs[0]["first_half_over_1_5"] is True
        # rerun: idempotent
        assert S.main([]) == 0
        recs2 = [
            json.loads(l)
            for l in (results / "settlements.jsonl").read_text().splitlines()
            if l.strip()
        ]
        assert len(recs2) == 1

    def test_unfinished_match_not_settled(self, monkeypatch, tmp_path):
        import settle as S

        results = tmp_path / "results" / S.EXPERIMENT_ID
        results.mkdir(parents=True)
        pred = {
            "experiment_id": S.EXPERIMENT_ID,
            "run_local_id": "mX:noul_1x2",
            "match_id": "mX",
            "arm": "noul_1x2",
            "validation": "ok",
            "pre_cutoff": True,
        }
        (results / "predictions.jsonl").write_text(json.dumps(pred) + "\n")
        labels = pd.DataFrame(
            [
                {
                    "match_id": "m1",
                    "label_valid_90": True,
                    "result_90": "D",
                    "goals_home_90": 1.0,
                    "goals_away_90": 1.0,
                    "over_2_5": False,
                    "btts_yes": True,
                    "corner_total_90": 9.0,
                    "corner_conflict": False,
                }
            ]
        )
        derived = tmp_path
        labels.to_parquet(derived / "market_labels.parquet")
        odds = pd.DataFrame(
            [{"match_id": "m1", "fd_stat_HTHG": 1.0, "fd_stat_HTAG": 0.0}]
        )
        odds.to_parquet(derived / "odds.parquet")
        monkeypatch.setattr(S, "PREDICTIONS_PATH", results / "predictions.jsonl")
        monkeypatch.setattr(S, "SETTLEMENTS_PATH", results / "settlements.jsonl")
        monkeypatch.setattr(S, "DERIVED_DIR", derived)

        assert S.main([]) == 0
        assert not (results / "settlements.jsonl").exists()
