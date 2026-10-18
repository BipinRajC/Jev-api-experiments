"""Parse and validate primitive outputs for Experiment 020.

Derivation version PROB-DERIVE-020-v1:
  - Noul event probability: the raw ``noul`` value (must be finite in [0, 1]).
  - Score event probability: returned ``score / 8`` on the nine-level 0-8 rubric
    (score must be finite in [0, 8]). Level probabilities are retained as-is.
  - Choice binary event probability: ``probabilities["yes"]``.
  - Choice 1X2 primary distribution: ``probabilities`` for home/draw/away.
  - Noul/Score 1X2 primary distribution: the three raw event values normalized
    by their sum; a non-positive or non-finite sum is rejected, never repaired.

``confidence`` is never used as an event probability. Missing, non-finite,
out-of-range, incoherent, or zero-sum outputs are rejected and logged; no
probability is invented for a rejected answer.
"""

from __future__ import annotations

import math
from typing import Any

PROB_DERIVATION_VERSION = "PROB-DERIVE-020-v1"

_ONE_X_TWO_KEYS = ("home_win", "draw", "away_win")


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def parse_noul_event(raw_noul: Any) -> tuple[float | None, str | None]:
    """Return (event_probability, rejection_reason)."""
    if not _finite(raw_noul):
        return None, f"noul not finite numeric: {raw_noul!r}"
    value = float(raw_noul)
    if not 0.0 <= value <= 1.0:
        return None, f"noul out of range [0,1]: {value}"
    return value, None


def parse_score_event(raw_score: Any) -> tuple[float | None, str | None]:
    """Return (event_probability = score/8, rejection_reason)."""
    if not _finite(raw_score):
        return None, f"score not finite numeric: {raw_score!r}"
    value = float(raw_score)
    if not 0.0 <= value <= 8.0:
        return None, f"score out of range [0,8]: {value}"
    return value / 8.0, None


def parse_choice_binary(probabilities: Any) -> tuple[float | None, str | None]:
    """Return (event_probability = P(yes), rejection_reason)."""
    if not isinstance(probabilities, dict):
        return None, f"choice probabilities not a dict: {probabilities!r}"
    if "yes" not in probabilities:
        return None, f"choice probabilities missing 'yes': {probabilities!r}"
    yes = probabilities["yes"]
    if not _finite(yes):
        return None, f"choice 'yes' not finite numeric: {yes!r}"
    value = float(yes)
    if not 0.0 <= value <= 1.0:
        return None, f"choice 'yes' out of range [0,1]: {value}"
    return value, None


def normalize_three_way(
    raw: dict[str, float],
) -> tuple[dict[str, float] | None, str | None]:
    """Normalize three raw event probabilities by their sum."""
    if set(raw) != set(_ONE_X_TWO_KEYS):
        return None, f"three-way keys wrong: {sorted(raw)}"
    values = [raw[k] for k in _ONE_X_TWO_KEYS]
    if not all(_finite(v) and 0.0 <= v <= 1.0 for v in values):
        return None, f"three-way raw values not finite in [0,1]: {raw}"
    total = sum(values)
    if not math.isfinite(total) or total <= 0.0:
        return None, f"three-way sum not positive finite: {total}"
    return {k: raw[k] / total for k in _ONE_X_TWO_KEYS}, None


def parse_choice_1x2(probabilities: Any) -> tuple[dict[str, float] | None, str | None]:
    """Primary Choice 1X2 distribution (already a distribution; validate and order)."""
    if not isinstance(probabilities, dict):
        return None, f"choice probabilities not a dict: {probabilities!r}"
    missing = [k for k in ("home", "draw", "away") if k not in probabilities]
    if missing:
        return (
            None,
            f"choice 1X2 probabilities missing keys {missing}: {probabilities!r}",
        )
    values = {
        f"{k}_win" if k != "draw" else "draw": float(probabilities[k])
        for k in ("home", "draw", "away")
    }
    if not all(_finite(v) and 0.0 <= v <= 1.0 for v in values.values()):
        return None, f"choice 1X2 probabilities not finite in [0,1]: {values}"
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0.0:
        return None, f"choice 1X2 sum not positive finite: {total}"
    return {k: v / total for k, v in values.items()}, None


def brier_three_way(probs: dict[str, float], result: str) -> float | None:
    """mean over classes of (p_k - y_k)^2 for one match; result in {H, D, A} or None."""
    if result not in ("H", "D", "A"):
        return None
    key = {"H": "home_win", "D": "draw", "A": "away_win"}[result]
    if set(probs) != set(_ONE_X_TWO_KEYS):
        return None
    return sum((probs[k] - (1.0 if k == key else 0.0)) ** 2 for k in _ONE_X_TWO_KEYS)


def brier_binary(prob: float | None, outcome: bool | None) -> float | None:
    """(p - y)^2 for one binary market; None when either input is missing."""
    if prob is None or outcome is None:
        return None
    return (prob - (1.0 if outcome else 0.0)) ** 2


LOG_LOSS_FLOOR = 0.01


def log_loss_fixed_floor(
    prob: float, outcome: bool, floor: float = LOG_LOSS_FLOOR
) -> float:
    """Fixed-floor log loss for one binary outcome."""
    p = min(max(prob, floor), 1.0 - floor)
    y = 1.0 if outcome else 0.0
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def log_loss_three_way_fixed_floor(
    probs: dict[str, float], result: str, floor: float = LOG_LOSS_FLOOR
) -> float | None:
    """Fixed-floor log loss of the realised outcome's probability (three-class)."""
    if result not in ("H", "D", "A"):
        return None
    key = {"H": "home_win", "D": "draw", "A": "away_win"}[result]
    p = min(max(probs[key], floor), 1.0)
    return -math.log(p)
