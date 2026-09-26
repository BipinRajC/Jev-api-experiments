#!/usr/bin/env python3
"""Calibration metrics for Phase 3.

Computes Brier score, log loss, calibration error, and reliability
components for a list of (predicted_probability, actual_outcome) pairs.
"""

from __future__ import annotations

import math
import statistics
from typing import Any


def brier_score(predictions: list[tuple[float, int]]) -> float:
    """Brier score: mean of (pred - actual)^2. Lower is better.

    Args:
        predictions: list of (predicted_probability, actual_0or1) pairs.
    Returns:
        Brier score (0 = perfect, 0.25 = constant 0.5 baseline).
    """
    if not predictions:
        return 0.0
    n = len(predictions)
    return sum((p - a) ** 2 for p, a in predictions) / n


def log_loss(predictions: list[tuple[float, int]], eps: float = 1e-15) -> float:
    """Log loss (cross-entropy). Lower is better.

    Clips predictions to [eps, 1-eps] to avoid log(0).

    Args:
        predictions: list of (predicted_probability, actual_0or1) pairs.
        eps: epsilon for clipping.
    Returns:
        Log loss.
    """
    if not predictions:
        return 0.0
    n = len(predictions)
    total = 0.0
    for p, a in predictions:
        p = max(eps, min(1 - eps, p))
        total += a * math.log(p) + (1 - a) * math.log(1 - p)
    return -total / n


def calibration_error(
    predictions: list[tuple[float, int]], bins: int = 10
) -> dict[str, Any]:
    """Compute calibration error and reliability components.

    Partitions predictions into bins by predicted probability, computes
    the mean predicted probability and outcome frequency per bin.

    Args:
        predictions: list of (predicted_probability, actual_0or1) pairs.
        bins: number of equal-width bins.
    Returns:
        dict with calibration_error, bin_summaries, etc.
    """
    if not predictions:
        return {"calibration_error": 0.0, "bin_summaries": [], "n": 0}

    bin_edges = [i / bins for i in range(bins + 1)]
    bins_data: list[list[tuple[float, int]]] = [[] for _ in range(bins)]

    for p, a in predictions:
        # Put p=1.0 in the last bin.
        idx = min(int(p * bins), bins - 1)
        bins_data[idx].append((p, a))

    bin_summaries = []
    for i, group in enumerate(bins_data):
        if not group:
            continue
        mean_pred = statistics.mean(p for p, _ in group)
        mean_actual = statistics.mean(a for _, a in group)
        count = len(group)
        bin_summaries.append(
            {
                "bin": i,
                "bin_range": f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}",
                "count": count,
                "mean_predicted": round(mean_pred, 4),
                "mean_actual": round(mean_actual, 4),
                "abs_error": round(abs(mean_pred - mean_actual), 4),
            }
        )

    # Expected calibration error (ECE): weighted average of |mean_pred - mean_actual|.
    total_count = len(predictions)
    ece = sum(b["abs_error"] * b["count"] / total_count for b in bin_summaries)

    return {
        "calibration_error_ece": round(ece, 4),
        "bin_count": len(bin_summaries),
        "bin_summaries": bin_summaries,
        "n": total_count,
    }


def summarize_predictions(
    predictions: list[tuple[float, int]],
    ground_truth_label: str = "",
) -> dict[str, Any]:
    """Compute all calibration metrics.

    Args:
        predictions: list of (predicted_probability, actual_0or1) pairs.
        ground_truth_label: optional label for reporting.
    Returns:
        dict with all metrics.
    """
    brier = brier_score(predictions)
    ll = log_loss(predictions)
    cal = calibration_error(predictions)

    # Constant baselines.
    base_rate = statistics.mean(a for _, a in predictions)
    constant_half_brier = brier_score([(0.5, a) for _, a in predictions])
    constant_base_brier = brier_score([(base_rate, a) for _, a in predictions])

    return {
        "label": ground_truth_label,
        "n": len(predictions),
        "brier_score": round(brier, 6),
        "log_loss": round(ll, 6),
        "brier_constant_0.5_baseline": round(constant_half_brier, 6),
        "brier_constant_base_rate_baseline": round(constant_base_brier, 6),
        **cal,
    }
