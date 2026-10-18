#!/usr/bin/env python3
"""Out-of-fold calibration analysis for Experiment 021 (CALIB-021-v1).

Fits per-(arm, market) calibration maps on the 2025/26 portion of the frozen
021 predictions and evaluates raw vs calibrated Brier on the untouched
2026/27 portion (n=366). This satisfies the phase-4 rule that a calibration
map may only be fitted on earlier predictions, never on the scored fixtures:
2025/26 strictly precedes 2026/27 in the chronological split.

Methods (predeclared):
  - binary markets: isotonic regression and logistic recalibration on the
    logit of the raw probability; both reported, logistic is primary.
  - 1X2: multinomial logistic on log-ratio margins of the raw distribution
    (a simple 3-class recalibration); raw scores remain the primary result.

Writes results/021-retrospective-locked/calibration-v1.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "021-retrospective-locked"
STREAM = RESULTS_DIR / "stream-001.jsonl"
CALIB_TRAIN_SEASON = 2025
CALIB_EVAL_SEASON = 2026


def load_latest() -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    with STREAM.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            latest[rec["run_local_id"]] = rec
    return list(latest.values())


def main() -> int:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    latest = load_latest()
    rows: dict[tuple[str, str], list[tuple[int, Any, Any]]] = defaultdict(list)
    for t in latest:
        if t["error"] or t["parsed"].get("validation") != "ok":
            continue
        lab = t["fixture_labels"]
        if t["arm"].endswith("binary"):
            for ev, lk in (
                ("over_2_5", "over_2_5"),
                ("btts_yes", "btts_yes"),
                ("corners_over_9_5", "corner_over_9_5"),
            ):
                p = t["parsed"]["events"].get(ev, {}).get("prob")
                if p is not None:
                    rows[(t["arm"], ev)].append(
                        (t["season_start"], float(p), int(lab[lk]))
                    )
        elif t["arm"].endswith("1x2"):
            d = t["parsed"]["one_x_two"]["distribution"]
            rows[(t["arm"], "1x2")].append((t["season_start"], d, lab["result_90"]))

    def logit(p: np.ndarray) -> np.ndarray:
        p = np.clip(p, 1e-3, 1 - 1e-3)
        return np.log(p / (1 - p)).reshape(-1, 1)

    out: dict[str, Any] = {
        "calibration_version": "CALIB-021-v1",
        "train_season": CALIB_TRAIN_SEASON,
        "eval_season": CALIB_EVAL_SEASON,
        "methods": "binary: isotonic + logistic-on-logit (logistic primary); 1x2: multinomial logistic on log-ratio margins",
        "results": {},
    }
    for (arm, ev), data in sorted(rows.items()):
        s25 = [r for r in data if r[0] == CALIB_TRAIN_SEASON]
        s26 = [r for r in data if r[0] == CALIB_EVAL_SEASON]
        if not s25 or not s26:
            continue
        entry: dict[str, Any] = {"n_train": len(s25), "n_eval": len(s26)}
        if ev == "1x2":

            def feats(d: dict[str, float]) -> list[float]:
                h, dr, a = d["home_win"], d["draw"], d["away_win"]
                return [
                    float(np.log(max(h, 1e-3) / max(a, 1e-3))),
                    float(np.log(max(h, 1e-3) / max(dr, 1e-3))),
                ]

            X25 = np.array([feats(r[1]) for r in s25])
            y25 = np.array([r[2] for r in s25])
            X26 = np.array([feats(r[1]) for r in s26])
            y26 = np.array([r[2] for r in s26])
            clf = LogisticRegression(max_iter=1000).fit(X25, y25)
            pr = clf.predict_proba(X26)
            classes = list(clf.classes_)
            raw = float(
                np.mean(
                    [
                        (r[1]["home_win"] - (r[2] == "H")) ** 2
                        + (r[1]["draw"] - (r[2] == "D")) ** 2
                        + (r[1]["away_win"] - (r[2] == "A")) ** 2
                        for r in s26
                    ]
                )
            )
            cal = float(
                np.mean(
                    [
                        (pr[i, classes.index("H")] - (y26[i] == "H")) ** 2
                        + (pr[i, classes.index("D")] - (y26[i] == "D")) ** 2
                        + (pr[i, classes.index("A")] - (y26[i] == "A")) ** 2
                        for i in range(len(s26))
                    ]
                )
            )
            entry.update(
                {"brier_raw_26": round(raw, 5), "brier_calibrated_26": round(cal, 5)}
            )
        else:
            p25 = np.array([r[1] for r in s25])
            y25 = np.array([r[2] for r in s25])
            p26 = np.array([r[1] for r in s26])
            y26 = np.array([r[2] for r in s26])
            iso = IsotonicRegression(out_of_bounds="clip").fit(p25, y25)
            lr = LogisticRegression(max_iter=1000).fit(logit(p25), y25)
            cal_iso = float(np.mean((iso.predict(p26) - y26) ** 2))
            cal_lr = float(
                np.mean(
                    (lr.predict_proba(logit(p26))[:, list(lr.classes_).index(1)] - y26)
                    ** 2
                )
            )
            entry.update(
                {
                    "brier_raw_26": round(float(np.mean((p26 - y26) ** 2)), 5),
                    "brier_isotonic_26": round(cal_iso, 5),
                    "brier_logistic_26": round(cal_lr, 5),
                }
            )
        out["results"][f"{arm}/{ev}"] = entry

    with open(RESULTS_DIR / "calibration-v1.json", "w") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
