"""Experiment 022 frozen question set (QSET-022-v1).

Tests the native structured count-band forms of Score and Choice against direct
Noul over/under threshold questions, on the same fixtures/states as Experiment
020's pilot.

Bands are locked from development data (2014/15-2024/25, 21,863 goal labels /
20,863 corner labels):
  - goals: 8 bands 0,1,2,3,4,5,6,7+  (over 2.5 = bands 3..7)
  - corners: 10 bands 0-5,6,7,8,9,10,11,12,13,14+  (over 9.5 = bands 10..14)
"""

from __future__ import annotations

QUESTION_SET_VERSION = "QSET-022-v1"

# Band definitions: (id, label, count_low, count_high_inclusive)
GOAL_BANDS = [
    ("g0", "0 goals", 0, 0),
    ("g1", "1 goal", 1, 1),
    ("g2", "2 goals", 2, 2),
    ("g3", "3 goals", 3, 3),
    ("g4", "4 goals", 4, 4),
    ("g5", "5 goals", 5, 5),
    ("g6", "6 goals", 6, 6),
    ("g7", "7 or more goals", 7, 99),
]

CORNER_BANDS = [
    ("c0", "5 or fewer corners", 0, 5),
    ("c1", "6 corners", 6, 6),
    ("c2", "7 corners", 7, 7),
    ("c3", "8 corners", 8, 8),
    ("c4", "9 corners", 9, 9),
    ("c5", "10 corners", 10, 10),
    ("c6", "11 corners", 11, 11),
    ("c7", "12 corners", 12, 12),
    ("c8", "13 corners", 13, 13),
    ("c9", "14 or more corners", 14, 99),
]

GOALS_INSTRUCTIONS = (
    "How many total goals will the match have after 90 minutes plus stoppage "
    "time, excluding extra time and penalties?"
)
CORNERS_INSTRUCTIONS = (
    "How many total corners will the match have during 90 minutes plus stoppage time?"
)

SCORE_INSTRUCTIONS_TEMPLATE = "{question} Answer on the labelled scale."
CHOICE_INSTRUCTIONS_TEMPLATE = "{question} Choose the most likely band."

# Direct Noul threshold questions reuse Experiment 020's canonical propositions.
NOUL_THRESHOLD_PROPOSITIONS = {
    "over_2_5": "The match has at least 3 total goals after 90 minutes plus stoppage time.",
    "corners_over_9_5": "The match has more than 9.5 total corners during 90 minutes plus stoppage time.",
}
NOUL_TEMPLATE = "Is the following proposition true? {proposition}"

# Lines aligned with the band definitions.
GOAL_LINE = 2.5  # over = total goals >= 3 = bands g3..g7
CORNER_LINE = 9.5  # over = total corners >= 10 = bands c5..c9


def noul_threshold_questions() -> dict[str, dict[str, object]]:
    return {
        event: {"type": "noul", "instructions": NOUL_TEMPLATE.format(proposition=prop)}
        for event, prop in NOUL_THRESHOLD_PROPOSITIONS.items()
    }


def score_band_questions() -> dict[str, dict[str, object]]:
    """Two Score questions whose criteria are the count bands."""
    return {
        "score_goal_bands": {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_TEMPLATE.format(
                question=GOALS_INSTRUCTIONS
            ),
            "criteria": [
                {"score": i, "label": label}
                for i, (_, label, _, _) in enumerate(GOAL_BANDS)
            ],
        },
        "score_corner_bands": {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_TEMPLATE.format(
                question=CORNERS_INSTRUCTIONS
            ),
            "criteria": [
                {"score": i, "label": label}
                for i, (_, label, _, _) in enumerate(CORNER_BANDS)
            ],
        },
    }


def choice_band_questions() -> dict[str, dict[str, object]]:
    """Two Choice questions whose options are the count bands."""
    return {
        "choice_goal_bands": {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS_TEMPLATE.format(
                question=GOALS_INSTRUCTIONS
            ),
            "criteria": {band_id: label for band_id, label, _, _ in GOAL_BANDS},
        },
        "choice_corner_bands": {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS_TEMPLATE.format(
                question=CORNERS_INSTRUCTIONS
            ),
            "criteria": {band_id: label for band_id, label, _, _ in CORNER_BANDS},
        },
    }


def band_index_for_count(bands: list[tuple[str, str, int, int]], count: float) -> int:
    for i, (_, _, low, high) in enumerate(bands):
        if low <= count <= high:
            return i
    raise ValueError(f"count {count} outside band coverage")


def band_ids_over_line(bands: list[tuple[str, str, int, int]], line: float) -> set[str]:
    """Band ids whose counts exceed the line (over the half-line)."""
    return {band_id for band_id, _, low, _ in bands if low > line}
