import pytest

from src.score import extract_score, probabilities_sum


def test_extract_score_reads_value_legend_probabilities_and_confidence():
    body = {
        "answers": {
            "blueness": {
                "type": "score",
                "score": 1.05,
                "legend": {"0": "grey", "1": "unstated", "2": "blue"},
                "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05},
                "confidence": 0.92,
            }
        }
    }
    parsed = extract_score(body, "blueness")
    assert parsed["score"] == 1.05
    assert parsed["legend"]["1"] == "unstated"
    assert parsed["probabilities"]["1"] == 0.95
    assert parsed["confidence"] == 0.92


def test_extract_score_rejects_wrong_type():
    with pytest.raises(ValueError, match="score"):
        extract_score(
            {"answers": {"blueness": {"type": "noul", "noul": 0.9}}},
            "blueness",
        )


def test_probabilities_sum_is_one():
    assert probabilities_sum({"0": 0.2, "1": 0.3, "2": 0.5}) == pytest.approx(1.0)
