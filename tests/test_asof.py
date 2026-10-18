from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.features import asof

T0 = datetime(2024, 8, 17, 12, 30, tzinfo=timezone.utc)
LABEL_COLUMNS = ["y_goals_home", "y_goals_away", "result_unreliable", "y_decided_by", "result_90"]


def match(mid: str, kickoff: datetime, home: str, away: str, gh: int, ga: int, *, comp: str = "EPL", season: int = 2024) -> dict:
    return {
        "match_id": mid, "competition": comp, "season": f"{season}/{season + 1}", "season_start": season, "round": "1",
        "kickoff_utc": kickoff, "home_id": home, "away_id": away, "final_home_goals": gh, "final_away_goals": ga,
        "goals_90_home": gh, "goals_90_away": ga, "decided_by": "fulltime_short", "result_unreliable": False,
    }


def empty_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.DataFrame(columns=["match_id", "team_id", "is_home", "xg", "shots", "lineup_rating"]),
        pd.DataFrame(columns=["match_id", "team_id", "us_xg", "us_xga"]),
        pd.DataFrame(columns=["match_id", "team_id", "player_id", "starter", "rating"]),
    )


def features(rows: list[dict], **kwargs) -> pd.DataFrame:
    stats, us, players = empty_inputs()
    kwargs.setdefault("team_stats", stats)
    kwargs.setdefault("us_team", us)
    kwargs.setdefault("players", players)
    df = pd.DataFrame(rows)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    return asof.build_features(df, kwargs["team_stats"], kwargs["us_team"], kwargs["players"])


def feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in LABEL_COLUMNS if c in df.columns])


def test_a_match_still_in_progress_at_the_cutoff_is_not_counted() -> None:
    rows = [
        match("early", T0, "A", "B", 3, 0),  # kicks off 12:30, counts from 15:00
        match("same_day_3pm", T0 + timedelta(hours=2, minutes=30), "C", "A", 0, 0),  # cutoff 14:00: A's win not yet counted
        match("evening", T0 + timedelta(hours=5), "A", "D", 1, 1),  # cutoff 16:30: A's win counted
    ]
    f = features(rows).set_index("match_id")
    assert f.loc["same_day_3pm", "away_dom_played"] != f.loc["same_day_3pm", "away_dom_played"]  # NaN: A has no completed match
    assert f.loc["evening", "home_dom_played"] == 1 and f.loc["evening", "home_dom_pts"] == 3
    assert f.loc["evening", "home_elo"] > 1500


def test_a_matchs_own_result_never_reaches_its_own_features() -> None:
    base = [match("m1", T0, "A", "B", 1, 0), match("m2", T0 + timedelta(days=7), "A", "B", 2, 2)]
    changed = [dict(base[0]), match("m2", T0 + timedelta(days=7), "A", "B", 9, 0)]
    f1, f2 = features(base), features(changed)
    assert feature_columns(f1).equals(feature_columns(f2))  # m2's features ignore m2's own score
    assert f1.loc[1, "y_goals_home"] == 2 and f2.loc[1, "y_goals_home"] == 9  # only the label differs


def random_league(seed: int, n_teams: int = 6) -> list[dict]:
    rng = random.Random(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    fixtures = [(h, a) for h in teams for a in teams if h != a]
    rng.shuffle(fixtures)
    rows, when = [], T0
    for i, (h, a) in enumerate(fixtures):
        when = when + timedelta(days=rng.choice([2, 3, 4]), hours=rng.choice([0, 2, 5]))
        rows.append(match(f"m{i}", when, h, a, rng.randint(0, 4), rng.randint(0, 3)))
    return rows


def test_scrambling_results_after_time_t_never_changes_earlier_features() -> None:
    for seed in range(5):
        rows = random_league(seed)
        cut = rows[len(rows) // 2]["kickoff_utc"]
        rng = random.Random(seed + 100)
        scrambled = [
            dict(r, final_home_goals=rng.randint(0, 6), final_away_goals=rng.randint(0, 6)) if r["kickoff_utc"] >= cut else dict(r)
            for r in rows
        ]
        for r in scrambled:
            r["goals_90_home"], r["goals_90_away"] = r["final_home_goals"], r["final_away_goals"]
        a, b = features(rows), features(scrambled)
        before_a = feature_columns(a[a["cutoff_utc"] <= cut]).reset_index(drop=True)
        before_b = feature_columns(b[b["cutoff_utc"] <= cut]).reset_index(drop=True)
        assert len(before_a) > 10
        assert before_a.equals(before_b), f"leak detected for seed {seed}"
        assert not feature_columns(a).equals(feature_columns(b))  # the scramble does change later features


def test_elo_is_zero_sum_and_a_win_raises_the_winner() -> None:
    f = features([match("m1", T0, "A", "B", 2, 0), match("m2", T0 + timedelta(days=7), "A", "B", 1, 1)]).set_index("match_id")
    assert f.loc["m1", "home_elo"] == f.loc["m1", "away_elo"] == 1500.0
    assert f.loc["m2", "home_elo"] > 1500 > f.loc["m2", "away_elo"]
    assert np.isclose(f.loc["m2", "home_elo"] + f.loc["m2", "away_elo"], 3000.0)


def test_new_season_pulls_ratings_toward_the_league_mean_exactly_once() -> None:
    engine = asof.AsOfEngine()  # regression 0.25, k etc. defaults
    engine.elo = {"A": 1600.0, "B": 1400.0}
    engine.elo_season = {"A": 2024, "B": 2024}
    engine.team_league = {"A": "EPL", "B": "EPL"}
    engine.members[("EPL", 2024)] = {"A", "B"}  # previous season's league mean = 1500
    assert engine._elo_for("A", "EPL", 2024) == 1600.0  # same season: untouched
    assert engine._elo_for("A", "EPL", 2025) == 1600.0 + 0.25 * (1500.0 - 1600.0)
    assert engine._elo_for("A", "EPL", 2025) == 1575.0  # applied once, not again on the next read
    assert engine._elo_for("B", "EPL", 2025) == 1425.0


def test_newcomer_starts_just_below_its_leagues_mean() -> None:
    engine = asof.AsOfEngine()
    engine.elo = {"A": 1600.0, "B": 1400.0}
    engine.members[("EPL", 2024)] = {"A", "B"}
    assert engine._elo_for("NEW", "EPL", 2025) == 1500.0 + asof.EloParams().newcomer_offset
    assert asof.AsOfEngine()._elo_for("NEW", "EPL", 2025) == 1500.0  # no league information yet


def test_league_table_uses_the_official_awarded_score_but_form_uses_the_on_field_score() -> None:
    awarded = match("m1", T0, "A", "B", 3, 0)  # official (awarded) result 3-0 to A
    awarded["goals_90_home"], awarded["goals_90_away"] = float("nan"), float("nan")  # disputed: on-field score unknown
    awarded["result_unreliable"] = True
    f = features([awarded, match("m2", T0 + timedelta(days=7), "A", "C", 0, 0)]).set_index("match_id")
    assert f.loc["m2", "home_dom_pts"] == 3 and f.loc["m2", "home_dom_played"] == 1  # table counts the award
    assert f.loc["m2", "home_elo"] == 1500.0  # Elo skips the disputed result
    assert f.loc["m2", "home_form_str5"] == ""  # form skips it too


def test_rolling_stats_lineups_and_head_to_head() -> None:
    rows = [
        match("m1", T0, "A", "B", 2, 1),
        match("m2", T0 + timedelta(days=7), "B", "A", 0, 0),
        match("m3", T0 + timedelta(days=14), "A", "B", 1, 0),
    ]
    stats = pd.DataFrame(
        [
            {"match_id": "m1", "team_id": "A", "is_home": True, "xg": 2.0, "shots": 10, "lineup_rating": 7.0},
            {"match_id": "m1", "team_id": "B", "is_home": False, "xg": 0.5, "shots": 4, "lineup_rating": 6.0},
            {"match_id": "m2", "team_id": "B", "is_home": True, "xg": 1.0, "shots": 8, "lineup_rating": 6.0},
            {"match_id": "m2", "team_id": "A", "is_home": False, "xg": 1.5, "shots": 12, "lineup_rating": 7.0},
        ]
    )
    players = pd.DataFrame(
        [
            {"match_id": "m1", "team_id": "A", "player_id": "p1", "starter": True, "rating": 8.0},
            {"match_id": "m1", "team_id": "A", "player_id": "p2", "starter": True, "rating": 6.0},
            {"match_id": "m2", "team_id": "A", "player_id": "p1", "starter": True, "rating": 7.0},
            {"match_id": "m2", "team_id": "A", "player_id": "p3", "starter": True, "rating": 7.0},
            {"match_id": "m3", "team_id": "A", "player_id": "p1", "starter": True, "rating": 5.0},
            {"match_id": "m3", "team_id": "A", "player_id": "p3", "starter": True, "rating": 5.0},
        ]
    )
    f = features(rows, team_stats=stats, players=players).set_index("match_id")
    m3 = f.loc["m3"]
    assert np.isclose(m3["home_fm_xg_for_5"], 1.75) and np.isclose(m3["home_fm_xg_against_5"], 0.75)
    assert np.isclose(m3["home_shots_for_5"], 11.0)
    assert m3["home_form_str5"] == "WD" and np.isclose(m3["home_form_pts_5"], 2.0)
    assert m3["home_xi_continuity"] == 2  # p1 and p3 started the previous match too
    assert np.isclose(m3["home_xi_prior_rating"], (7.5 + 7.0) / 2)  # p1: mean(8, 7); p3: 7 — never m3's own 5.0
    assert m3["h2h_n"] == 2 and np.isclose(m3["h2h_home_ppg"], 2.0)
    assert np.isclose(m3["home_rest_days"], 7.0 - 1.0 / 24)  # last match 7 days earlier, cutoff is 1h before kickoff
    assert f.loc["m1", "home_xi_known_players"] == 0 and f.loc["m3", "home_xi_known_players"] == 2


def test_european_match_uses_the_clubs_domestic_table_and_a_bigger_k() -> None:
    domestic = [match("d1", T0, "A", "B", 1, 0), match("d2", T0 + timedelta(days=2), "C", "A", 0, 2)]
    euro = match("e1", T0 + timedelta(days=9), "A", "X", 0, 0, comp="UCL")
    f = features(domestic + [euro]).set_index("match_id")
    assert f.loc["e1", "home_dom_league"] == "EPL" and f.loc["e1", "home_dom_pts"] == 6 and f.loc["e1", "home_dom_pos"] == 1
    assert bool(f.loc["e1", "is_europe"])
    assert asof.EloParams().k_europe_multiplier > 1.0


def test_season_pull_does_not_depend_on_which_team_plays_first() -> None:
    def pulled(order: list[str]) -> dict[str, float]:
        engine = asof.AsOfEngine()
        engine.elo = {"A": 1600.0, "B": 1400.0, "C": 1500.0}
        engine.elo_season = {t: 2024 for t in engine.elo}
        engine.team_league = {t: "EPL" for t in engine.elo}
        engine.members[("EPL", 2024)] = set(engine.elo)
        return {t: engine._elo_for(t, "EPL", 2025) for t in order}

    assert pulled(["A", "B", "C"]) == pulled(["C", "B", "A"])


def test_a_half_known_90_minute_score_is_treated_as_unknown() -> None:
    odd = match("m1", T0, "A", "B", 2, 1)
    odd["goals_90_away"] = float("nan")  # should never happen, but must not crash or update Elo
    f = features([odd, match("m2", T0 + timedelta(days=7), "A", "B", 0, 0)]).set_index("match_id")
    assert f.loc["m2", "home_elo"] == 1500.0 and f.loc["m2", "home_form_str5"] == ""
