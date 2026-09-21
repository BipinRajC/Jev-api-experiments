from __future__ import annotations

from typing import Any


def extract_choice(body: dict[str, Any], question_id: str) -> dict[str, Any]:
    answers = body.get("answers")
    if not isinstance(answers, dict) or question_id not in answers:
        raise ValueError(f"Missing Choice answer for {question_id}")
    answer = answers[question_id]
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ValueError(f"Answer {question_id} is not a choice object: {answer}")
    choice = answer.get("choice")
    probabilities = answer.get("probabilities")
    confidence = answer.get("confidence")
    if not isinstance(choice, str):
        raise ValueError(f"Answer {question_id} choice is not a string: {choice}")
    if not isinstance(probabilities, dict):
        raise ValueError(f"Answer {question_id} probabilities missing: {probabilities}")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError(
            f"Answer {question_id} confidence is not numeric: {confidence}"
        )
    return {
        "choice": choice,
        "probabilities": {str(k): float(v) for k, v in probabilities.items()},
        "confidence": float(confidence),
    }


def probabilities_sum(probabilities: dict[str, float]) -> float:
    return float(sum(probabilities.values()))
