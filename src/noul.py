from __future__ import annotations

from typing import Any


def extract_noul(body: dict[str, Any], question_id: str) -> float:
    answers = body.get("answers")
    if not isinstance(answers, dict) or question_id not in answers:
        raise ValueError(f"Missing Noul answer for {question_id}")
    answer = answers[question_id]
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        raise ValueError(f"Answer {question_id} is not a noul object: {answer}")
    value = answer.get("noul")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Answer {question_id} noul is not numeric: {value}")
    return float(value)


def summarize_values(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("values must be non-empty")
    minimum = min(values)
    maximum = max(values)
    mean = sum(values) / len(values)
    return {
        "n": len(values),
        "min": minimum,
        "max": maximum,
        "mean": mean,
        "range": maximum - minimum,
    }
