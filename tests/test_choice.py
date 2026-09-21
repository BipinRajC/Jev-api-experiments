import pytest

from src.choice import extract_choice, probabilities_sum


def test_extract_choice_reads_label_probabilities_and_confidence():
    body = {
        "answers": {
            "color": {
                "type": "choice",
                "choice": "blue",
                "probabilities": {"blue": 0.8, "grey": 0.15, "unspecified": 0.05},
                "confidence": 0.7,
            }
        }
    }
    parsed = extract_choice(body, "color")
    assert parsed["choice"] == "blue"
    assert parsed["probabilities"]["blue"] == 0.8
    assert parsed["confidence"] == 0.7


def test_extract_choice_rejects_wrong_type():
    with pytest.raises(ValueError, match="choice"):
        extract_choice(
            {"answers": {"color": {"type": "noul", "noul": 0.9}}},
            "color",
        )


def test_probabilities_sum_is_one():
    assert probabilities_sum({"blue": 0.5, "grey": 0.5}) == pytest.approx(1.0)
