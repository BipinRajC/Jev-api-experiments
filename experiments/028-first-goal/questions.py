"""Experiment 028 — first goal by which team.

Registered question set QSET-028-v1. The three-way market: which team scores
the first goal of the match (home / away / no goal at all, i.e. 0-0 after 90').

Label construction (build_first_goal_labels): from the parsed FotMob shot maps
(shots.parquet, systematic from 2020/21), take the earliest Goal event by
(period order FirstHalf < SecondHalf, then minute, then minute_added). Own
goals (is_own_goal) count FOR the opposing team, per the standard settlement
of "first goal by which team". Matches with no Goal event get the no_goal
label. Extra-time events are excluded (90-minute settlement).

Development rates (2014/15-2024/25 shot-map seasons 2020/21-2024/25) are
computed by build_first_goal_labels on dev rows; the 021 Dixon-Coles matrix's
P(0-0) is the structural no-goal baseline.
"""

from __future__ import annotations

QUESTION_SET_VERSION = "QSET-028-v1"

FIRST_GOAL_INSTRUCTIONS = (
    "Which team scores the first goal of the match, considering only goals "
    "during the first 90 minutes plus stoppage time, excluding extra time and penalties?"
)

FIRST_GOAL_CRITERIA: dict[str, str] = {
    "home": "The home team scores the first goal of the match.",
    "away": "The away team scores the first goal of the match.",
    "no_goal": "The match ends 0-0 after 90 minutes; neither team scores.",
}

NOUL_FIRST_HOME = (
    "The home team scores the first goal of the match during the first 90 minutes "
    "plus stoppage time, excluding extra time and penalties."
)
NOUL_FIRST_AWAY = (
    "The away team scores the first goal of the match during the first 90 minutes "
    "plus stoppage time, excluding extra time and penalties."
)

SCORE_FIRST_INSTRUCTIONS = (
    "Which team scores the first goal of the match, considering only goals during "
    "the first 90 minutes plus stoppage time? Assign a probability level to each option."
)


def choice_first_goal_question() -> dict[str, dict[str, object]]:
    return {
        "first_goal": {
            "type": "choice",
            "instructions": FIRST_GOAL_INSTRUCTIONS,
            "criteria": dict(FIRST_GOAL_CRITERIA),
        }
    }


def parse_first_goal_choice(body: dict) -> dict:
    """Parse the three-way first-goal Choice answer into a validated distribution.

    Returns {'events': {}, 'first_goal': {...}} compatible with the runner's
    parsed-record shape. Rejected (never repaired) when the answer is missing,
    has wrong keys, non-finite values, or a zero sum.
    """
    import math

    parsed = {
        "events": {},
        "first_goal": None,
        "rejections": [],
        "derivation_version": "FIRSTGOAL-028-v1",
    }
    answers = body.get("answers", {})
    answer = answers.get("first_goal")
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        parsed["rejections"].append(f"first_goal answer missing/not choice: {answer!r}")
        parsed["validation"] = "rejected"
        return parsed
    probs = answer.get("probabilities")
    if not isinstance(probs, dict):
        parsed["rejections"].append(f"first_goal probabilities not a dict: {probs!r}")
        parsed["validation"] = "rejected"
        return parsed
    missing = [k for k in ("home", "away", "no_goal") if k not in probs]
    if missing:
        parsed["rejections"].append(f"first_goal probabilities missing keys {missing}")
        parsed["validation"] = "rejected"
        return parsed
    values = {}
    for k in ("home", "away", "no_goal"):
        v = probs[k]
        if (
            not isinstance(v, (int, float))
            or isinstance(v, bool)
            or not math.isfinite(v)
            or not 0.0 <= v <= 1.0
        ):
            parsed["rejections"].append(f"first_goal '{k}' not finite in [0,1]: {v!r}")
            parsed["validation"] = "rejected"
            return parsed
        values[k] = float(v)
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0:
        parsed["rejections"].append(f"first_goal sum not positive finite: {total}")
        parsed["validation"] = "rejected"
        return parsed
    parsed["first_goal"] = {
        "distribution": {k: v / total for k, v in values.items()},
        "choice": answer.get("choice"),
        "confidence": answer.get("confidence"),
    }
    parsed["validation"] = "ok"
    return parsed


def noul_first_goal_questions() -> dict[str, dict[str, object]]:
    return {
        "first_goal_home": {"type": "noul", "instructions": NOUL_FIRST_HOME},
        "first_goal_away": {"type": "noul", "instructions": NOUL_FIRST_AWAY},
    }


def score_first_goal_questions() -> dict[str, dict[str, object]]:
    return {
        "first_goal_home": {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_HOME,
            "criteria": [dict(c) for c in SCORE_CRITERIA_SHARED],
        },
        "first_goal_away": {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_AWAY,
            "criteria": [dict(c) for c in SCORE_CRITERIA_SHARED],
        },
    }


SCORE_CRITERIA_SHARED: list[dict[str, object]] = [
    {"score": 0, "label": "impossible (0%)"},
    {"score": 1, "label": "very unlikely (12.5%)"},
    {"score": 2, "label": "unlikely (25%)"},
    {"score": 3, "label": "somewhat unlikely (37.5%)"},
    {"score": 4, "label": "even odds (50%)"},
    {"score": 5, "label": "somewhat likely (62.5%)"},
    {"score": 6, "label": "likely (75%)"},
    {"score": 7, "label": "very likely (87.5%)"},
    {"score": 8, "label": "certain (100%)"},
]

SCORE_INSTRUCTIONS_HOME = (
    "How likely is the following proposition? Answer on the labelled scale. "
    + NOUL_FIRST_HOME
)
SCORE_INSTRUCTIONS_AWAY = (
    "How likely is the following proposition? Answer on the labelled scale. "
    + NOUL_FIRST_AWAY
)


def build_first_goal_labels(
    shots: "pd.DataFrame",
    matches: "pd.DataFrame",
) -> "pd.DataFrame":
    """One row per match: first_goal in {home, away, no_goal}.

    - Matches without a shot map (no rows in shots) get first_goal = None
      (label unavailable), never a guess.
    - Matches with a shot map and no Goal event get "no_goal".
    - Own goals count for the benefiting (non-shooting) team.
    - Only FirstHalf/SecondHalf events; extra time and shootouts excluded.

    matches: DataFrame with match_id, home_id, away_id.
    """
    import pandas as pd

    out = matches[["match_id", "home_id", "away_id"]].copy()
    out["first_goal"] = None
    out["first_goal_minute"] = None
    out = out.set_index("match_id")

    goals = shots[shots["event_type"] == "Goal"].copy()
    goals = goals[goals["period"].isin(("FirstHalf", "SecondHalf"))]
    goals["_order"] = (
        goals["period"].map({"FirstHalf": 0, "SecondHalf": 1}).fillna(9) * 1000
        + goals["minute"].fillna(0)
        + goals["minute_added"].fillna(0) / 100.0
    )
    first = goals.sort_values("_order").groupby("match_id").first()

    for mid, row in first.iterrows():
        if mid not in out.index:
            continue
        home_id, away_id = out.at[mid, "home_id"], out.at[mid, "away_id"]
        if row["is_own_goal"]:
            side = "away" if row["team_id"] == home_id else "home"
        elif row["team_id"] == home_id:
            side = "home"
        elif row["team_id"] == away_id:
            side = "away"
        else:
            continue
        out.at[mid, "first_goal"] = side
        out.at[mid, "first_goal_minute"] = (
            None if pd.isna(row["minute"]) else float(row["minute"])
        )
    # matches with a shot map but no goal: no_goal
    has_map = set(shots["match_id"].unique())
    out.loc[out.index.isin(has_map) & out["first_goal"].isna(), "first_goal"] = (
        "no_goal"
    )
    return out.reset_index()
