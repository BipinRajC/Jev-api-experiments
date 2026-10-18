"""Parse and validate Experiment 022 band answers (PROB-DERIVE-022-v1).

A band answer is usable only when it returns a full distribution over ALL
expected band keys with finite values in [0,1]. The distribution is normalized
by its (positive, finite) sum with the normalization recorded. The derived
over/under probability at a line is the summed probability of bands above the
line. A missing level, a non-finite value, or a zero-sum distribution is
rejected and logged; no probability is invented. A one-hot distribution is
accepted as a (degenerate) full distribution and its limitation is reported.
"""

from __future__ import annotations

import math
from typing import Any

PROB_DERIVATION_VERSION = "PROB-DERIVE-022-v1"


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def parse_band_distribution(
    raw_probabilities: Any,
    expected_band_ids: list[str],
) -> tuple[dict[str, float] | None, str | None, bool]:
    """Return (normalized distribution, rejection_reason, is_one_hot)."""
    if not isinstance(raw_probabilities, dict):
        return None, f"band probabilities not a dict: {raw_probabilities!r}", False
    keys = {str(k) for k in raw_probabilities.keys()}
    missing = [b for b in expected_band_ids if b not in keys]
    if missing:
        return None, f"band probabilities missing levels {missing}", False
    values: dict[str, float] = {}
    for band_id in expected_band_ids:
        v = raw_probabilities[band_id]
        if not _finite(v) or not 0.0 <= float(v) <= 1.0:
            return None, f"band probability {band_id} not finite in [0,1]: {v!r}", False
        values[band_id] = float(v)
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0.0:
        return None, f"band distribution sum not positive finite: {total}", False
    normalized = {k: v / total for k, v in values.items()}
    one_hot = sum(1 for v in normalized.values() if v >= 0.999) == 1
    return normalized, None, one_hot


def band_ids_over_line(bands: list[tuple[str, str, int, int]], line: float) -> set[str]:
    """Band ids whose counts exceed the line (over the half-line)."""
    return {band_id for band_id, _, low, _ in bands if low > line}


def over_probability(
    distribution: dict[str, float],
    bands: list[tuple[str, str, int, int]],
    line: float,
) -> float:
    """Sum of band probabilities strictly above the line."""
    over_ids = band_ids_over_line(bands, line)
    return sum(p for band_id, p in distribution.items() if band_id in over_ids)


def rps(
    distribution: dict[str, float],
    band_order: list[str],
    actual_band_index: int,
) -> float:
    """Ranked probability score for an ordered band distribution.

    RPS = sum_{k=0}^{K-2} (CDFp(k) - CDFo(k))^2 / (K-1); lower is better.
    """
    k_total = len(band_order)
    if not 0 <= actual_band_index < k_total:
        raise ValueError(f"actual band index {actual_band_index} out of range")
    cum_p = 0.0
    total = 0.0
    for i, band_id in enumerate(band_order[:-1]):
        cum_p += distribution[band_id]
        cum_o = 1.0 if actual_band_index <= i else 0.0
        total += (cum_p - cum_o) ** 2
    return total / (k_total - 1)
