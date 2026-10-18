"""Experiment 020 frozen question set (QSET-020-v1).

Canonical 90-minute event wordings from docs/phase4-jev-football-experiment-plan.md
section 4, reused as propositions across primitive-specific instructions.
The exact strings below were frozen before the first scored call; do not edit
them in place. Any revision must be a new version constant.

Events (90 minutes plus stoppage time, excluding extra time and penalties):
  home_win, draw, away_win, over_2_5, btts_yes, corners_over_9_5.
"""

from __future__ import annotations

QUESTION_SET_VERSION = "QSET-020-v1"
CORNER_LINE = 9.5
CORNER_LINE_LABEL = "corners_over_9_5"

PROPOSITIONS: dict[str, str] = {
    "home_win": (
        "The home team wins after 90 minutes plus stoppage time, excluding extra time and penalties."
    ),
    "draw": (
        "The match is a draw after 90 minutes plus stoppage time, excluding extra time and penalties."
    ),
    "away_win": (
        "The away team wins after 90 minutes plus stoppage time, excluding extra time and penalties."
    ),
    "over_2_5": (
        "The match has at least 3 total goals after 90 minutes plus stoppage time."
    ),
    "btts_yes": (
        "Both teams score at least one goal after 90 minutes plus stoppage time."
    ),
    CORNER_LINE_LABEL: (
        "The match has more than 9.5 total corners during 90 minutes plus stoppage time."
    ),
}

NOUL_TEMPLATE = "Is the following proposition true? {proposition}"

SCORE_INSTRUCTIONS_TEMPLATE = "How likely is the following proposition? Answer on the labelled scale. {proposition}"

# Nine explicitly labelled levels, 0% to 100% in 12.5-point steps.
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

CHOICE_YESNO_INSTRUCTIONS_TEMPLATE = (
    "Answer the following proposition with yes or no. {proposition}"
)

CHOICE_YESNO_CRITERIA: dict[str, str] = {
    "yes": "The proposition is true.",
    "no": "The proposition is false.",
}

CHOICE_1X2_INSTRUCTIONS = (
    "Which result is most likely after 90 minutes plus stoppage time, "
    "excluding extra time and penalties?"
)

CHOICE_1X2_CRITERIA: dict[str, str] = {
    "home": PROPOSITIONS["home_win"],
    "draw": PROPOSITIONS["draw"],
    "away": PROPOSITIONS["away_win"],
}

# 1X2 propositions in fixed order for batching and normalization.
ONE_X_TWO_EVENTS: tuple[str, str, str] = ("home_win", "draw", "away_win")
# Binary markets batched into one request per primitive.
BINARY_EVENTS: tuple[str, str, str] = ("over_2_5", "btts_yes", CORNER_LINE_LABEL)


def noul_questions() -> dict[str, dict[str, object]]:
    """Batched Noul questions for all six events."""
    return {
        event: {"type": "noul", "instructions": NOUL_TEMPLATE.format(proposition=prop)}
        for event, prop in PROPOSITIONS.items()
    }


def score_questions() -> dict[str, dict[str, object]]:
    """Batched Score questions (nine-level rubric) for all six events."""
    return {
        event: {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_TEMPLATE.format(proposition=prop),
            "criteria": [dict(c) for c in SCORE_CRITERIA],
        }
        for event, prop in PROPOSITIONS.items()
    }


def choice_binary_questions() -> dict[str, dict[str, object]]:
    """Batched yes/no Choice questions for the three binary events."""
    questions: dict[str, dict[str, object]] = {}
    for event in BINARY_EVENTS:
        questions[event] = {
            "type": "choice",
            "instructions": CHOICE_YESNO_INSTRUCTIONS_TEMPLATE.format(
                proposition=PROPOSITIONS[event]
            ),
            "criteria": dict(CHOICE_YESNO_CRITERIA),
        }
    return questions


def choice_1x2_question() -> dict[str, dict[str, object]]:
    """Single three-way Choice question for 1X2."""
    return {
        "result_1x2": {
            "type": "choice",
            "instructions": CHOICE_1X2_INSTRUCTIONS,
            "criteria": dict(CHOICE_1X2_CRITERIA),
        }
    }
