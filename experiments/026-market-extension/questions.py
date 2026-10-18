"""Experiment 026 registered question set (QSET-026-v1).

Extension markets registered from the user's mathematical research
(docs/footyquant-math-research-2026-10-18.pdf, sha256 b4419ccb..., received
2026-10-19). Events follow the canonical 90-minute wording style of
QSET-020-v1. Settlement definitions:

  - home_team_over_1_5 : goals_home_90 >= 2 (valid_90 gate)
  - away_team_over_1_5 : goals_away_90 >= 2 (valid_90 gate)
  - handicap_home_minus_1_5 : goals_home_90 - goals_away_90 >= 2 (valid_90 gate)
  - first_half_over_1_5 : fd_stat_HTHG + fd_stat_HTAG >= 2 (football-data
    half-time score; domestic leagues only, ~93% coverage; UCL label is null)

Candidate lines were locked from 2014/15-2024/25 development data by the
predeclared nearest-to-balanced rule:
  home_over_1_5 0.4471, away_over_1_5 0.3433, first_half_over_1_5 0.3496,
  handicap_home_minus_1_5 0.2351.
Cards and shots-on-target are EXCLUDED: FotMob team stats include extra time and
provider card counts disagree; the 90-minute scope is unproven.
Mathematical baselines per the research (Deliverable J steps 1-3): the frozen
Dixon-Coles score matrix marginals for team goals and the handicap; a constant
development base rate for first-half goals (no structural half-time model yet).
"""

from __future__ import annotations

QUESTION_SET_VERSION = "QSET-026-v1"

PROPOSITIONS: dict[str, str] = {
    "home_team_over_1_5": (
        "The home team scores at least 2 goals after 90 minutes plus stoppage time, "
        "excluding extra time and penalties."
    ),
    "away_team_over_1_5": (
        "The away team scores at least 2 goals after 90 minutes plus stoppage time, "
        "excluding extra time and penalties."
    ),
    "handicap_home_minus_1_5": (
        "The home team wins by at least 2 goals after 90 minutes plus stoppage time, "
        "excluding extra time and penalties."
    ),
    "first_half_over_1_5": (
        "The match has at least 2 goals scored before half-time (the first 45 minutes "
        "plus first-half stoppage time)."
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

EXTENSION_EVENTS = tuple(PROPOSITIONS.keys())


def noul_ext_questions() -> dict[str, dict[str, object]]:
    return {
        event: {"type": "noul", "instructions": NOUL_TEMPLATE.format(proposition=prop)}
        for event, prop in PROPOSITIONS.items()
    }


def score_ext_questions() -> dict[str, dict[str, object]]:
    return {
        event: {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS_TEMPLATE.format(proposition=prop),
            "criteria": [dict(c) for c in SCORE_CRITERIA],
        }
        for event, prop in PROPOSITIONS.items()
    }


def choice_ext_questions() -> dict[str, dict[str, object]]:
    return {
        event: {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS_TEMPLATE.format(proposition=prop),
            "criteria": dict(CHOICE_YESNO_CRITERIA),
        }
        for event, prop in PROPOSITIONS.items()
    }
