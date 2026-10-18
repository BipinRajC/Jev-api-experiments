"""Experiment 027 registered question set (QSET-027-v1).

Lines/totals extension covering the user's preferred betting lines:
  - total_goals_over_1_5 and total_goals_over_3_5 (spanning the curve around
    the live over_2_5 arm; under = complement of the same record)
  - corners_over_11_5 (the user's usual under-11.5 corner bet; under =
    complement)

All events are 90-minute propositions in the canonical QSET-020-v1 style.
Settlement: total goals lines from label_valid_90-gated goals_home_90 +
goals_away_90; the corners line from conflict-free corner_total_90.

Lines locked from 2014/15-2024/25 development data (rates):
  over 1.5 goals 0.7670, over 3.5 goals 0.3060, over 11.5 corners 0.2917.
Baselines (frozen, experiments/021-retrospective-locked/baselines.py):
  Dixon-Coles score-matrix tails for the goal lines; the NB corner-count
  model for corners 11.5.
"""

from __future__ import annotations

QUESTION_SET_VERSION = "QSET-027-v1"

PROPOSITIONS: dict[str, str] = {
    "total_goals_over_1_5": (
        "The match has at least 2 total goals after 90 minutes plus stoppage time, "
        "excluding extra time and penalties."
    ),
    "total_goals_over_3_5": (
        "The match has at least 4 total goals after 90 minutes plus stoppage time, "
        "excluding extra time and penalties."
    ),
    "corners_over_11_5": (
        "The match has more than 11.5 total corners during 90 minutes plus stoppage time."
    ),
}

NOUL_TEMPLATE = "Is the following proposition true? {proposition}"
SCORE_INSTRUCTIONS_TEMPLATE = "How likely is the following proposition? Answer on the labelled scale. {proposition}"
CHOICE_INSTRUCTIONS_TEMPLATE = (
    "Answer the following proposition with yes or no. {proposition}"
)

SCORE_CRITERIA: list[dict[str, object]] = [
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

CHOICE_YESNO_CRITERIA: dict[str, str] = {
    "yes": "The proposition is true.",
    "no": "The proposition is false.",
}

LINES_EVENTS = tuple(PROPOSITIONS.keys())
DEV_RATES = {
    "total_goals_over_1_5": 0.7670,
    "total_goals_over_3_5": 0.3060,
    "corners_over_11_5": 0.2917,
}


def noul_lines_questions() -> dict[str, dict[str, object]]:
    return {
        event: {"type": "noul", "instructions": NOUL_TEMPLATE.format(proposition=prop)}
        for event, prop in PROPOSITIONS.items()
    }


def score_lines_questions() -> dict[str, dict[str, object]]:
    return {
        event: {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_TEMPLATE.format(proposition=prop),
            "criteria": [dict(c) for c in SCORE_CRITERIA],
        }
        for event, prop in PROPOSITIONS.items()
    }


def choice_lines_questions() -> dict[str, dict[str, object]]:
    return {
        event: {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS_TEMPLATE.format(proposition=prop),
            "criteria": dict(CHOICE_YESNO_CRITERIA),
        }
        for event, prop in PROPOSITIONS.items()
    }
