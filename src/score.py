from __future__ import annotations

from typing import Any


def extract_score(body: dict[str, Any], question_id: str) -> dict[str, Any]:
    answers = body.get("answers")
    if not isinstance(answers, dict) or question_id not in answers:
        raise ValueError(f"Missing Score answer for {question_id}")
    answer = answers[question_id]
    if not isinstance(answer, dict) or answer.get("type") != "score":
        raise ValueError(f"Answer {question_id} is not a score object: {answer}")
    score = answer.get("score")
    legend = answer.get("legend")
    probabilities = answer.get("probabilities")
    confidence = answer.get("confidence")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError(f"Answer {question_id} score is not numeric: {score}")
    if not isinstance(legend, dict):
        raise ValueError(f"Answer {question_id} legend missing: {legend}")
    if not isinstance(probabilities, dict):
        raise ValueError(f"Answer {question_id} probabilities missing: {probabilities}")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError(
            f"Answer {question_id} confidence is not numeric: {confidence}"
        )
    return {
        "score": float(score),
        "legend": {str(k): str(v) for k, v in legend.items()},
        "probabilities": {str(k): float(v) for k, v in probabilities.items()},
        "confidence": float(confidence),
    }


def probabilities_sum(probabilities: dict[str, float]) -> float:
    return float(sum(probabilities.values()))
