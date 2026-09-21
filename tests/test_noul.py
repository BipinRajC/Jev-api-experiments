import pytest

from src.noul import extract_noul, summarize_values


def test_extract_noul_reads_numeric_field():
    body = {
        "model": "jev-1.13.0",
        "answers": {"is_blue": {"type": "noul", "noul": 0.99}},
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    assert extract_noul(body, "is_blue") == 0.99


def test_extract_noul_rejects_missing_answer():
    with pytest.raises(ValueError, match="is_blue"):
        extract_noul({"answers": {}}, "is_blue")


def test_extract_noul_rejects_wrong_type():
    with pytest.raises(ValueError, match="noul"):
        extract_noul(
            {"answers": {"is_blue": {"type": "choice", "choice": "x"}}},
            "is_blue",
        )


def test_summarize_values_reports_min_max_mean_range():
    stats = summarize_values([0.10, 0.20, 0.30])
    assert stats["n"] == 3
    assert stats["min"] == 0.10
    assert stats["max"] == 0.30
    assert stats["mean"] == pytest.approx(0.20)
    assert stats["range"] == pytest.approx(0.20)
