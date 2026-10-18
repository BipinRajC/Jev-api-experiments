#!/usr/bin/env python3
"""Experiment 025 — Chronological Jev-plus-ML comparison.

Question: do frozen Jev outputs add measurable skill to the tabular ML
baseline, market by market and primitive by primitive?

Design (STACK-025-v1, frozen before evaluation):
  - Data: the frozen artifacts of 021 (Jev predictions by match/primitive) and
    021's ML baseline predictions. No API calls.
  - Chronological split: fit the stack layer on 2025/26 fixtures (n=1,920),
    evaluate on the untouched 2026/27 fixtures (n=366). Nothing fitted on the
    evaluation rows.
  - Arms, per market:
      ml_alone        : logistic layer on the ML probabilities only
      ml_plus_<prim>  : logistic layer on ML + that primitive's Jev probabilities
      jev_<prim>_alone: logistic layer on the Jev probabilities only
  - The ML tree model itself is NOT refitted (its frozen eval predictions are
    the base layer); only the logistic stack layer is fitted on 2025/26.
  - 1X2: multinomial logistic on [ml_h, ml_d, ml_a] (+ jev_h, jev_d, jev_a).
    Binary: logistic on [ml_p] (+ jev_p).
  - Metrics: 3-class / binary Brier on 2026/27; paired contrasts (ML+Jev vs
    ML alone, ML+Jev vs Jev alone) with date-clustered bootstrap CIs.
    Exploratory: the decisive test remains the prospective 024 cohort.

Writes results/025-jev-plus-ml/protocol-v1.json (frozen), run-001.json and
stack-predictions-v1.parquet.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import parsing as P20  # noqa: E402

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.utils import next_run_path, utc_now_iso, write_json  # noqa: E402

EXPERIMENT_ID = "025-jev-plus-ml"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
DIR_021 = REPO_ROOT / "results" / "021-retrospective-locked"
STREAM_021 = DIR_021 / "stream-001.jsonl"
STACK_TRAIN_SEASON = 2025
STACK_EVAL_SEASON = 2026
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 42
RANDOM_STATE = 42
PRIMITIVES = ("noul", "score", "choice")
BINARY_MARKETS = {
    "over_2_5": ("noul_binary", "score_binary", "choice_binary", "ml_over_2_5"),
    "btts_yes": ("noul_binary", "score_binary", "choice_binary", "ml_btts_yes"),
    "corners_over_9_5": (
        "noul_binary",
        "score_binary",
        "choice_binary",
        "ml_corner_over_9_5",
    ),
}
LABEL_KEYS = {
    "over_2_5": "over_2_5",
    "btts_yes": "btts_yes",
    "corners_over_9_5": "corner_over_9_5",
}


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


def git_sha() -> str | None:
    from subprocess import run

    try:
        out = run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load_jev_predictions() -> pd.DataFrame:
    """One row per match with the frozen Jev probabilities per primitive."""
    latest: dict[str, dict[str, Any]] = {}
    with STREAM_021.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                latest[rec["run_local_id"]] = rec

    rows: dict[str, dict[str, Any]] = {}
    for rec in latest.values():
        if rec["error"] is not None or rec["parsed"].get("validation") != "ok":
            continue
        mid = rec["match_id"]
        rows.setdefault(
            mid,
            {
                "match_id": mid,
                "kickoff_utc": rec["kickoff_utc"],
                "competition": rec["competition"],
                "season_start": rec["season_start"],
            },
        )
        labels = rec["fixture_labels"]
        rows[mid]["result_90"] = labels["result_90"]
        if rec["arm"].endswith("1x2"):
            dist = rec["parsed"]["one_x_two"]["distribution"]
            prim = rec["arm"].split("_")[0]
            rows[mid][f"jev_{prim}_h"] = dist["home_win"]
            rows[mid][f"jev_{prim}_d"] = dist["draw"]
            rows[mid][f"jev_{prim}_a"] = dist["away_win"]
        elif rec["arm"].endswith("binary"):
            for ev in BINARY_MARKETS:
                p = rec["parsed"]["events"].get(ev, {}).get("prob")
                if p is not None:
                    prim = rec["arm"].split("_")[0]
                    rows[mid][f"jev_{prim}_{ev}"] = p
                    rows[mid][f"y_{LABEL_KEYS[ev]}"] = int(labels[LABEL_KEYS[ev]])
        rows[mid]["y_result_90"] = labels["result_90"]
    return pd.DataFrame(list(rows.values())).set_index("match_id")


def clustered_bootstrap_ci(
    diffs: np.ndarray, clusters: np.ndarray, n_boot: int, seed: int
) -> tuple[float, float]:
    rng = np.random.RandomState(seed)
    unique = np.unique(clusters)
    by_cluster = {c: diffs[clusters == c] for c in unique}
    means = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        means[i] = np.concatenate([by_cluster[c] for c in sampled]).mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def build_dataset() -> tuple[pd.DataFrame, dict[str, Any]]:
    jev = load_jev_predictions()
    ml = pd.read_parquet(DIR_021 / "ml-predictions-v1.parquet").set_index("match_id")
    diag: dict[str, Any] = {"n_jev": len(jev), "n_ml": len(ml)}
    df = jev.join(
        ml.drop(
            columns=[c for c in ("season_start", "competition") if c in ml.columns]
        ),
        how="inner",
    )
    diag["n_joined"] = len(df)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"])
    return df, diag


def fit_logistic(x: pd.DataFrame, y: np.ndarray, *, multiclass: bool):
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
    clf.fit(x.to_numpy(), y)
    return clf


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df, diag = build_dataset()

    protocol = {
        "protocol_version": "025-protocol-v1",
        "frozen_at_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "stack_spec": "STACK-025-v1",
        "split": {"train_season": STACK_TRAIN_SEASON, "eval_season": STACK_EVAL_SEASON},
        "arms": {
            "1x2": ["ml_alone"]
            + [f"ml_plus_{p}" for p in PRIMITIVES]
            + [f"jev_{p}_alone" for p in PRIMITIVES],
            "binary": ["ml_alone"]
            + [f"ml_plus_{p}" for p in PRIMITIVES]
            + [f"jev_{p}_alone" for p in PRIMITIVES],
        },
        "layer_model": "sklearn LogisticRegression(max_iter=2000, random_state=42); ML trees never refitted",
        "metrics": "3-class / binary Brier on the eval season; paired date-clustered bootstrap CIs",
        "bootstrap": {"n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED},
        "exploratory_note": "Retrospective stacking only; a product conclusion needs the 024 prospective cohort.",
        "input_artifacts": {
            "stream_021": str(STREAM_021.relative_to(REPO_ROOT)),
            "ml_predictions": str(
                (DIR_021 / "ml-predictions-v1.parquet").relative_to(REPO_ROOT)
            ),
        },
        "diagnostics": diag,
    }
    write_json(RESULTS_DIR / "protocol-v1.json", protocol)

    train = df[df["season_start"] == STACK_TRAIN_SEASON]
    eval_df = df[df["season_start"] == STACK_EVAL_SEASON]
    clusters = eval_df["kickoff_utc"].dt.strftime("%Y-%m-%d").to_numpy()

    results: dict[str, Any] = {"one_x_two": {}, "binary": {}}
    predictions = []

    # --- 1X2 ---
    y26 = eval_df["y_result_90"].to_numpy()
    y25 = train["y_result_90"].to_numpy()
    arm_features_1x2 = {
        "ml_alone": ["ml_h", "ml_d", "ml_a"],
        **{
            f"ml_plus_{p}": [
                "ml_h",
                "ml_d",
                "ml_a",
                f"jev_{p}_h",
                f"jev_{p}_d",
                f"jev_{p}_a",
            ]
            for p in PRIMITIVES
        },
        **{
            f"jev_{p}_alone": [f"jev_{p}_h", f"jev_{p}_d", f"jev_{p}_a"]
            for p in PRIMITIVES
        },
    }

    for arm, cols in arm_features_1x2.items():
        x_tr, x_ev = train[cols], eval_df[cols]
        mask_tr = ~x_tr.isna().any(axis=1).to_numpy()
        mask_ev = ~x_ev.isna().any(axis=1).to_numpy()
        clf = fit_logistic(x_tr[mask_tr], y25[mask_tr], multiclass=True)
        proba = clf.predict_proba(x_ev[mask_ev].to_numpy())
        classes = list(clf.classes_)
        y_ev = y26[mask_ev]
        brier_vec = (
            (proba[:, classes.index("H")] - (y_ev == "H")) ** 2
            + (proba[:, classes.index("D")] - (y_ev == "D")) ** 2
            + (proba[:, classes.index("A")] - (y_ev == "A")) ** 2
        )
        results["one_x_two"][arm] = {
            "n_eval": int(mask_ev.sum()),
            "brier_3class": round(float(brier_vec.mean()), 5),
        }
        for i, mid in enumerate(eval_df.index[mask_ev]):
            predictions.append(
                {
                    "match_id": mid,
                    "market": "1x2",
                    "arm": arm,
                    "p_home": float(proba[i, classes.index("H")]),
                    "p_draw": float(proba[i, classes.index("D")]),
                    "p_away": float(proba[i, classes.index("A")]),
                    "y_result": y_ev[i],
                    "brier": float(brier_vec[i]),
                }
            )

    # paired contrasts on common eval rows
    date_by_match = {
        mid: str(ts.strftime("%Y-%m-%d")) for mid, ts in eval_df["kickoff_utc"].items()
    }

    def paired(
        table_a: dict[str, float],
        table_b: dict[str, float],
        seed: int,
        label: str,
    ) -> None:
        common = sorted(set(table_a) & set(table_b))
        if not common:
            return
        diffs = np.array([table_a[m] - table_b[m] for m in common])
        cl = np.array([date_by_match.get(m, "unknown") for m in common])
        lo, hi = clustered_bootstrap_ci(diffs, cl, BOOTSTRAP_N, seed)
        results.setdefault("contrasts", {})[label] = {
            "n_paired": len(common),
            "mean_diff": round(float(diffs.mean()), 5),
            "ci95_date_clustered": [round(lo, 5), round(hi, 5)],
            "excludes_zero": bool(lo * hi > 0),
        }

    brier_by_match = {
        arm: {
            mid: r["brier"]
            for r in predictions
            if r["arm"] == arm
            for mid in [r["match_id"]]
        }
        for arm in arm_features_1x2
    }
    seed = BOOTSTRAP_SEED
    for p in PRIMITIVES:
        paired(
            brier_by_match[f"ml_plus_{p}"],
            brier_by_match["ml_alone"],
            seed,
            f"1x2:ml_plus_{p}_vs_ml_alone",
        )
        seed += 1
        paired(
            brier_by_match[f"ml_plus_{p}"],
            brier_by_match[f"jev_{p}_alone"],
            seed,
            f"1x2:ml_plus_{p}_vs_jev_alone",
        )
        seed += 1

    # --- Binary markets ---
    for market, (noul_arm, score_arm, choice_arm, ml_col) in BINARY_MARKETS.items():
        ycol = f"y_{LABEL_KEYS[market]}"
        prim_col = {
            "noul": f"jev_noul_{market}",
            "score": f"jev_score_{market}",
            "choice": f"jev_choice_{market}",
        }
        arms_bin = {"ml_alone": [ml_col]}
        for p in PRIMITIVES:
            arms_bin[f"ml_plus_{p}"] = [ml_col, prim_col[p]]
            arms_bin[f"jev_{p}_alone"] = [prim_col[p]]
        for arm, cols in arms_bin.items():
            x_tr, x_ev = train[cols], eval_df[cols]
            mask_tr = ~x_tr.isna().any(axis=1).to_numpy()
            mask_ev = ~x_ev.isna().any(axis=1).to_numpy()
            if mask_ev.sum() == 0:
                continue
            clf = fit_logistic(
                x_tr[mask_tr], train[ycol].to_numpy()[mask_tr], multiclass=False
            )
            proba = clf.predict_proba(x_ev[mask_ev].to_numpy())[
                :, list(clf.classes_).index(1)
            ]
            y_ev = eval_df[ycol].to_numpy()[mask_ev]
            brier_vec = (proba - y_ev) ** 2
            results["binary"][f"{market}/{arm}"] = {
                "n_eval": int(mask_ev.sum()),
                "brier_binary": round(float(brier_vec.mean()), 5),
            }
            for i, mid in enumerate(eval_df.index[mask_ev]):
                predictions.append(
                    {
                        "match_id": mid,
                        "market": market,
                        "arm": arm,
                        "p": float(proba[i]),
                        "y_binary": int(y_ev[i]),
                        "brier": float(brier_vec[i]),
                    }
                )
        for p in PRIMITIVES:
            t_a = {
                r["match_id"]: r["brier"]
                for r in predictions
                if r["market"] == market and r["arm"] == f"ml_plus_{p}"
            }
            t_b = {
                r["match_id"]: r["brier"]
                for r in predictions
                if r["market"] == market and r["arm"] == "ml_alone"
            }
            t_j = {
                r["match_id"]: r["brier"]
                for r in predictions
                if r["market"] == market and r["arm"] == f"jev_{p}_alone"
            }
            paired(t_a, t_b, seed, f"{market}:ml_plus_{p}_vs_ml_alone")
            seed += 1
            paired(t_a, t_j, seed, f"{market}:ml_plus_{p}_vs_jev_alone")
            seed += 1

    pd.DataFrame(predictions).to_parquet(
        RESULTS_DIR / "stack-predictions-v1.parquet", index=False
    )

    run = {
        "experiment_id": EXPERIMENT_ID,
        "protocol_version": protocol["protocol_version"],
        "timestamp_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "n_train": int((df["season_start"] == STACK_TRAIN_SEASON).sum()),
        "n_eval": int((df["season_start"] == STACK_EVAL_SEASON).sum()),
        "results": results,
    }
    path = next_run_path(RESULTS_DIR)
    write_json(path, run)
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
