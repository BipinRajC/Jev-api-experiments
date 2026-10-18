#!/usr/bin/env python3
"""Final analysis for Experiment 021: Jev arms vs mathematical and ML baselines.

Loads the append-only stream (per-call records), the frozen mathematical
baseline predictions, and the tabular ML predictions, then computes:
  - per-arm/per-baseline scores on the common paired fixtures (1X2 three-class
    Brier; binary Brier per market),
  - Brier skill vs the prior-season baseline,
  - paired contrasts (Noul vs Score, Noul vs Choice, each Jev arm vs the best
    non-Jev baseline) with 95% CIs from a date-clustered bootstrap,
  - per-competition and per-season breakdowns,
  - coverage, failure, and cost tables.

Writes results/021-retrospective-locked/analysis-v1.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import parsing as P20  # noqa: E402

RESULTS_DIR = REPO_ROOT / "results" / "021-retrospective-locked"
STREAM = RESULTS_DIR / "stream-001.jsonl"
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 42
CONTRASTS = (("noul", "score"), ("noul", "choice"))


def load_stream() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return (latest record per run_local_id, superseded summary).

    Retried attempts (e.g., the corrected choice_1x2 re-run) supersede earlier
    rejected records with the same run_local_id; superseded records stay in
    the stream and are reported, never silently dropped.
    """
    latest: dict[str, dict[str, Any]] = {}
    superseded = defaultdict(int)
    with STREAM.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = rec["run_local_id"]
            if key in latest:
                superseded[key] += 1
            latest[key] = rec
    return list(latest.values()), {
        "n_stream_lines": sum(1 for _ in open(STREAM)),
        "n_unique_run_local_ids": len(latest),
        "n_superseded_attempts": sum(superseded.values()),
    }


def jev_arm_tables(
    recs: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    """Return (per-arm tables keyed by match, coverage summary)."""
    one_x_two: dict[str, dict[str, dict[str, Any]]] = {}
    binary: dict[str, dict[str, dict[str, Any]]] = {}
    coverage = defaultdict(int)
    models = set()
    for t in recs:
        models.add(t.get("model_returned"))
        if t["error"] is not None:
            coverage[f"{t['arm']}:failed"] += 1
            continue
        if t["parsed"].get("validation") != "ok":
            coverage[f"{t['arm']}:rejected"] += 1
            continue
        coverage[f"{t['arm']}:ok"] += 1
        labels = t["fixture_labels"]
        dist = (t["parsed"].get("one_x_two") or {}).get("distribution")
        if dist:
            b = P20.brier_three_way(dist, labels["result_90"])
            if b is not None:
                one_x_two.setdefault(t["arm"], {})[t["match_id"]] = {
                    "brier": b,
                    "kickoff": t["kickoff_utc"],
                    "competition": t["competition"],
                    "season_start": t["season_start"],
                }
        for ev, key, label_key in (
            ("over_2_5", "over_2_5", "over_2_5"),
            ("btts_yes", "btts_yes", "btts_yes"),
            ("corners_over_9_5", "corners_over_9_5", "corner_over_9_5"),
        ):
            ep = t["parsed"]["events"].get(ev, {})
            if ep.get("prob") is not None:
                b = P20.brier_binary(ep["prob"], labels[label_key])
                if b is not None:
                    binary.setdefault((t["arm"], ev), {})[t["match_id"]] = {
                        "brier": b,
                        "kickoff": t["kickoff_utc"],
                        "competition": t["competition"],
                        "season_start": t["season_start"],
                    }
    return (one_x_two, binary), {
        "models_returned": sorted(m for m in models if m),
        "coverage": dict(coverage),
    }


def clustered_bootstrap_ci(
    diffs: np.ndarray, clusters: np.ndarray, n_boot: int, seed: int
) -> tuple[float, float]:
    """95% CI for the mean of paired diffs, resampling whole clusters (dates)."""
    rng = np.random.RandomState(seed)
    unique = np.unique(clusters)
    by_cluster = {c: diffs[clusters == c] for c in unique}
    means = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        vals = np.concatenate([by_cluster[c] for c in sampled])
        means[i] = vals.mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_contrast(
    table_a: dict[str, dict[str, Any]], table_b: dict[str, dict[str, Any]], *, seed: int
) -> dict[str, Any] | None:
    common = sorted(set(table_a) & set(table_b))
    if not common:
        return None
    diffs = np.array([table_a[m]["brier"] - table_b[m]["brier"] for m in common])
    clusters = np.array([str(table_a[m]["kickoff"])[:10] for m in common])
    lo, hi = clustered_bootstrap_ci(diffs, clusters, BOOTSTRAP_N, seed)
    return {
        "n_paired": len(common),
        "mean_diff": round(float(diffs.mean()), 5),
        "ci95_date_clustered": [round(lo, 5), round(hi, 5)],
        "excludes_zero": bool(lo * hi > 0),
    }


def breakdown(table: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for v in table.values():
        groups[str(v[key])].append(v["brier"])
    return {
        k: {"n": len(v), "brier": round(float(np.mean(v)), 5)}
        for k, v in sorted(groups.items())
    }


def main() -> int:
    recs, superseded_info = load_stream()
    (one_x_two, binary), coverage = jev_arm_tables(recs)

    baselines = pd.read_parquet(
        RESULTS_DIR / "baseline-predictions-v1.parquet"
    ).set_index("match_id")
    ml = pd.read_parquet(RESULTS_DIR / "ml-predictions-v1.parquet").set_index(
        "match_id"
    )
    ml_extra = ml.drop(
        columns=[c for c in ("season_start", "competition") if c in ml.columns]
    )
    baselines = baselines.join(ml_extra, how="left")

    # Baseline 1X2 tables (brier computed per fixture).
    base_1x2: dict[str, dict[str, dict[str, Any]]] = {}
    for name, cols in (
        ("prior", ("prior_home", "prior_draw", "prior_away")),
        ("elo", ("elo_home", "elo_draw", "elo_away")),
        ("dc", ("dc_home", "dc_draw", "dc_away")),
        ("ml", ("ml_h", "ml_d", "ml_a")),
    ):
        table = {}
        for mid, r in baselines.iterrows():
            h, d, a = r[cols[0]], r[cols[1]], r[cols[2]]
            if any(pd.isna(x) for x in (h, d, a)):
                continue
            y = r["result_90"]
            b = (h - (y == "H")) ** 2 + (d - (y == "D")) ** 2 + (a - (y == "A")) ** 2
            table[mid] = {
                "brier": float(b),
                "kickoff": str(r["kickoff_utc"])
                if "kickoff_utc" in baselines.columns
                else "",
                "competition": r["competition"],
                "season_start": int(r["season_start"]),
            }
        base_1x2[name] = table

    # Baseline binary tables keyed (model_name, event).
    base_bin2: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    label_col_for_event = {
        "over_2_5": "over_2_5",
        "btts_yes": "btts_yes",
        "corners_over_9_5": "corner_over_9_5",
    }
    for name, cols in (
        (
            "prior",
            [
                ("prior_over_2_5", "over_2_5"),
                ("prior_btts", "btts_yes"),
                ("prior_corners_over", "corners_over_9_5"),
            ],
        ),
        ("dc", [("dc_over_2_5", "over_2_5"), ("dc_btts", "btts_yes")]),
        (
            "ml",
            [
                ("ml_over_2_5", "over_2_5"),
                ("ml_btts_yes", "btts_yes"),
                ("ml_corner_over_9_5", "corners_over_9_5"),
            ],
        ),
    ):
        for col, event in cols:
            table = {}
            for mid, r in baselines.iterrows():
                v = r[col]
                if v is None or pd.isna(v):
                    continue
                y = float(r[label_col_for_event[event]])
                table[mid] = {
                    "brier": float((v - y) ** 2),
                    "kickoff": "",
                    "competition": r["competition"],
                    "season_start": int(r["season_start"]),
                }
            base_bin2[(name, event)] = table
    col_to_event = {
        "prior_over_2_5": "over_2_5",
        "dc_over_2_5": "over_2_5",
        "ml_over_2_5": "over_2_5",
        "prior_btts": "btts_yes",
        "dc_btts": "btts_yes",
        "ml_btts_yes": "btts_yes",
        "prior_corners_over": "corners_over_9_5",
        "ml_corner_over_9_5": "corners_over_9_5",
    }
    for name, cols in (
        (
            "prior",
            [
                ("prior_over_2_5", "over_2_5"),
                ("prior_btts", "btts_yes"),
                ("prior_corners_over", "corners_over_9_5"),
            ],
        ),
        ("dc", [("dc_over_2_5", "over_2_5"), ("dc_btts", "btts_yes")]),
        (
            "ml",
            [
                ("ml_over_2_5", "over_2_5"),
                ("ml_btts_yes", "btts_yes"),
                ("ml_corner_over_9_5", "corners_over_9_5"),
            ],
        ),
    ):
        for col, event in cols:
            table = {}
            for mid, r in baselines.iterrows():
                v = r[col]
                if v is None or pd.isna(v):
                    continue
                y = float(
                    r[
                        {
                            "over_2_5": "over_2_5",
                            "btts_yes": "btts_yes",
                            "corners_over_9_5": "corner_over_9_5",
                        }[event]
                    ]
                )
                table[mid] = {
                    "brier": float((v - y) ** 2),
                    "kickoff": "",
                    "competition": r["competition"],
                    "season_start": int(r["season_start"]),
                }
            base_bin2[(name, event)] = table

    # Scores on the 1X2 common set.
    analysis: dict[str, Any] = {"coverage": coverage, "superseded": superseded_info}

    def summarize(table: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not table:
            return {"n": 0}
        briers = [v["brier"] for v in table.values()]
        out = {
            "n": len(briers),
            "brier_3class": round(float(np.mean(briers)), 5),
            "by_competition": breakdown(table, "competition"),
            "by_season": breakdown(table, "season_start"),
        }
        prior_table = base_1x2["prior"]
        common = sorted(set(table) & set(prior_table))
        if common:
            skill = np.mean(
                [prior_table[m]["brier"] - table[m]["brier"] for m in common]
            )
            out["brier_skill_vs_prior"] = round(float(skill), 5)
        return out

    analysis["one_x_two"] = {
        **{arm: summarize(t) for arm, t in one_x_two.items()},
        **{f"baseline_{name}": summarize(t) for name, t in base_1x2.items()},
    }
    analysis["binary"] = {}
    for arm, ev in (
        ("noul_binary", "over_2_5"),
        ("noul_binary", "btts_yes"),
        ("noul_binary", "corners_over_9_5"),
        ("score_binary", "over_2_5"),
        ("score_binary", "btts_yes"),
        ("score_binary", "corners_over_9_5"),
        ("choice_binary", "over_2_5"),
        ("choice_binary", "btts_yes"),
        ("choice_binary", "corners_over_9_5"),
    ):
        table = binary.get((arm, ev), {})
        entry = summarize(table)
        for bname, btable in base_bin2.items():
            if bname[1] != ev:
                continue
            common = sorted(set(table) & set(btable))
            if common:
                entry[f"brier_skill_vs_{bname[0]}"] = round(
                    float(
                        np.mean(
                            [btable[m]["brier"] - table[m]["brier"] for m in common]
                        )
                    ),
                    5,
                )
        analysis["binary"][f"{arm}/{ev}"] = entry
    for bname, btable in base_bin2.items():
        analysis["binary"][f"baseline_{bname[0]}/{bname[1]}"] = summarize(btable)

    # Paired contrasts (date-clustered bootstrap, distinct seeds per contrast).
    contrasts: dict[str, Any] = {}
    seed = BOOTSTRAP_SEED
    for a, b in CONTRASTS:
        c = paired_contrast(
            one_x_two.get(f"{a}_1x2", {}), one_x_two.get(f"{b}_1x2", {}), seed=seed
        )
        if c:
            contrasts[f"{a}_1x2_vs_{b}_1x2"] = c
        seed += 1
    for ev in ("over_2_5", "btts_yes", "corners_over_9_5"):
        for a, b in CONTRASTS:
            c = paired_contrast(
                binary.get((f"{a}_binary", ev), {}),
                binary.get((f"{b}_binary", ev), {}),
                seed=seed,
            )
            if c:
                contrasts[f"{a}_binary_vs_{b}_binary/{ev}"] = c
            seed += 1
    # each 1X2 Jev arm vs the best fixed non-Jev baseline (Elo) and ML
    for jarm in ("noul_1x2", "score_1x2", "choice_1x2"):
        for bname in ("elo", "ml"):
            c = paired_contrast(one_x_two.get(jarm, {}), base_1x2[bname], seed=seed)
            if c:
                contrasts[f"{jarm}_vs_{bname}"] = c
            seed += 1

    analysis["paired_contrasts"] = contrasts

    # Costs.
    totals = {
        "stream_records": len(recs),
        "total_input_tokens": sum(t.get("input_tokens") or 0 for t in recs),
        "total_estimated_cost_usd": round(
            sum(t.get("estimated_cost_usd") or 0.0 for t in recs), 4
        ),
    }
    analysis["totals"] = totals

    with open(RESULTS_DIR / "analysis-v1.json", "w") as fh:
        fh.write(json.dumps(analysis, indent=2) + "\n")
    print(json.dumps(totals, indent=2))
    print(json.dumps(analysis["one_x_two"], indent=2))
    print(json.dumps(analysis["binary"], indent=2))
    print(json.dumps(contrasts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
