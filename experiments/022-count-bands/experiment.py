#!/usr/bin/env python3
"""Experiment 022 — Native count-band arms vs direct threshold questions.

On the exact 48 fixtures and frozen named_full states of Experiment 020's
protocol (predeclared paired sample), compare:
  - direct Noul over/under questions at the goal line 2.5 and corner line 9.5
  - Score count-band rubrics (8 goal bands, 10 corner bands) with the
    over/under probability derived from the full band distribution
  - Choice count-band options with the same derivation
Band forecasts are also scored as distributions with the ranked probability
score (RPS). Frozen question set: QSET-022-v1. Retrospective cohort, exploratory.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "022-count-bands"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import band_parsing as BP  # noqa: E402
import band_questions as QB  # noqa: E402

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.features import state as state_mod  # noqa: E402
from src.jev_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    JevClient,
    JevConfigError,
)
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "022-count-bands"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PROTOCOL_PATH = RESULTS_DIR / "protocol-v1.json"
COHORT = "retrospective_2025_26"
PROTOCOL_020 = REPO_ROOT / "results" / "020-football-pilot" / "protocol-v1.json"
ARMS = (
    "noul_thresholds",
    "score_goal_bands",
    "score_corner_bands",
    "choice_goal_bands",
    "choice_corner_bands",
)
RETRY_DELAYS_S = (2.0, 5.0)


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


def freeze_protocol() -> dict[str, Any]:
    """Reuse 020's frozen fixture list; rebuild/verify the named_full states."""
    protocol_020 = json.loads(PROTOCOL_020.read_text())
    fixtures = [f for f in protocol_020["fixtures"]]

    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    matches = pd.read_parquet(DERIVED_DIR / "matches.parquet")
    meta = matches.set_index("match_id")
    inputs_by_id = inputs.set_index("match_id")

    states: dict[str, dict[str, Any]] = {}
    for f in fixtures:
        row = inputs_by_id.loc[f["match_id"]]
        meta_row = meta.loc[f["match_id"]]
        state = state_mod.state_from_row(
            row.to_dict(), meta_row.to_dict(), anonymized=False
        )
        h = canonical_hash(state)
        if h != f["state_hashes"]["named_full"]:
            print(
                f"FATAL: state hash drift for {f['match_id']}; 020 states not reproducible.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        states[f["match_id"]] = state
        f["arm_questions"] = {arm: arm_questions(arm) for arm in ARMS}

    protocol = {
        "protocol_version": "022-protocol-v1",
        "frozen_at_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "cohort": COHORT,
        "paired_with": "results/020-football-pilot/protocol-v1.json (same 48 fixtures, same states)",
        "model_requested": DEFAULT_MODEL,
        "question_set_version": QB.QUESTION_SET_VERSION,
        "prob_derivation_version": BP.PROB_DERIVATION_VERSION,
        "goal_bands": [list(b) for b in QB.GOAL_BANDS],
        "corner_bands": [list(b) for b in QB.CORNER_BANDS],
        "lines": {"goal_line": QB.GOAL_LINE, "corner_line": QB.CORNER_LINE},
        "arms": list(ARMS),
        "metrics": {
            "brier_binary": "(p - y)^2 for the over/under event at each line",
            "rps": "ranked probability score of the band distribution vs actual count band",
            "log_loss_floor": 0.01,
        },
        "retries": {
            "max_retries": len(RETRY_DELAYS_S),
            "delays_s": list(RETRY_DELAYS_S),
        },
        "n_fixtures": len(fixtures),
        "fixtures": fixtures,
    }
    write_json(RESULTS_DIR / "states-001.json", states)
    return protocol


def arm_questions(arm: str) -> dict[str, dict[str, Any]]:
    if arm == "noul_thresholds":
        return QB.noul_threshold_questions()
    if arm in ("score_goal_bands", "score_corner_bands"):
        return {arm: QB.score_band_questions()[arm]}
    if arm in ("choice_goal_bands", "choice_corner_bands"):
        return {arm: QB.choice_band_questions()[arm]}
    raise ValueError(f"unknown arm {arm}")


def parse_call(arm: str, body: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "events": {},
        "derivation_version": BP.PROB_DERIVATION_VERSION,
    }
    rejections: list[str] = []
    answers = body.get("answers", {})

    if arm == "noul_thresholds":
        for event_id, answer in answers.items():
            raw = answer.get("noul")
            prob, reason = (
                (float(raw), None)
                if isinstance(raw, (int, float))
                and not isinstance(raw, bool)
                and 0.0 <= raw <= 1.0
                else (None, f"noul invalid: {raw!r}")
            )
            parsed["events"][event_id] = {"raw": raw, "prob": prob, "reject": reason}
            if reason:
                rejections.append(f"{event_id}: {reason}")
        parsed["one_x_two"] = None
    elif arm in ("score_goal_bands", "choice_goal_bands"):
        bands, line, answer = QB.GOAL_BANDS, QB.GOAL_LINE, answers.get(arm, {})
        probs_raw = answer.get("probabilities")
        if arm.startswith("score") and isinstance(probs_raw, dict):
            # Score keys probabilities by rubric level index; map level i -> band i.
            probs_raw = {
                bands[i][0]: probs_raw[str(i)]
                for i in range(len(bands))
                if str(i) in {str(k) for k in probs_raw}
            }
        dist, reason, one_hot = BP.parse_band_distribution(
            probs_raw, [b[0] for b in bands]
        )
        over = BP.over_probability(dist, bands, line) if dist else None
        parsed["events"]["goal_bands"] = {
            "distribution": dist,
            "over_2_5": over,
            "one_hot": one_hot,
            "raw_score_or_choice": answer.get("score", answer.get("choice")),
            "reject": reason,
        }
        if reason:
            rejections.append(f"goal_bands: {reason}")
    elif arm in ("score_corner_bands", "choice_corner_bands"):
        bands, line, answer = QB.CORNER_BANDS, QB.CORNER_LINE, answers.get(arm, {})
        probs_raw = answer.get("probabilities")
        if arm.startswith("score") and isinstance(probs_raw, dict):
            probs_raw = {
                bands[i][0]: probs_raw[str(i)]
                for i in range(len(bands))
                if str(i) in {str(k) for k in probs_raw}
            }
        dist, reason, one_hot = BP.parse_band_distribution(
            probs_raw, [b[0] for b in bands]
        )
        over = BP.over_probability(dist, bands, line) if dist else None
        parsed["events"]["corner_bands"] = {
            "distribution": dist,
            "corners_over_9_5": over,
            "one_hot": one_hot,
            "raw_score_or_choice": answer.get("score", answer.get("choice")),
            "reject": reason,
        }
        if reason:
            rejections.append(f"corner_bands: {reason}")
    parsed["validation"] = "ok" if not rejections else "rejected"
    parsed["rejections"] = rejections
    return parsed


def call_with_retry(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    for attempt in range(1 + len(RETRY_DELAYS_S)):
        try:
            return client.system_one(state=state, questions=questions)
        except Exception:
            if attempt < len(RETRY_DELAYS_S):
                import time

                time.sleep(RETRY_DELAYS_S[attempt])
            continue
    return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze-only",
        action="store_true",
        help="freeze the protocol without API calls",
    )
    args = parser.parse_args()
    load_env()
    model = DEFAULT_MODEL
    started = utc_now_iso()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if PROTOCOL_PATH.exists():
        protocol = json.loads(PROTOCOL_PATH.read_text())
        print(f"Protocol already frozen at {protocol['frozen_at_utc']}; reusing.")
    else:
        protocol = freeze_protocol()
        write_json(PROTOCOL_PATH, protocol)
        print(
            f"Froze 022 protocol: {protocol['n_fixtures']} fixtures x {len(ARMS)} arms."
        )
    if args.freeze_only:
        print("Freeze-only mode: no API calls made.")
        return 0

    # Self-check before any scored call: every label key the analyzer needs must exist.
    required_label_keys = {
        "over_2_5",
        "corner_over_9_5",
        "goals_home_90",
        "goals_away_90",
        "corner_total_90",
    }
    for f in protocol["fixtures"]:
        missing = required_label_keys - set(f["labels"])
        if missing:
            print(
                f"FATAL: fixture {f['match_id']} labels missing keys {missing}",
                file=sys.stderr,
            )
            return 2

    states = json.loads((RESULTS_DIR / "states-001.json").read_text())
    stream_path = RESULTS_DIR / "stream-001.jsonl"
    trials: list[dict[str, Any]] = []
    done: set[str] = set()
    if stream_path.exists():
        with stream_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    trials.append(rec)
                    done.add(rec["run_local_id"])
        print(f"Resuming: {len(done)} calls already recorded in {stream_path.name}.")
    exit_code = 0

    try:
        with (
            JevClient(model=model, base_url=DEFAULT_BASE_URL) as client,
            stream_path.open("a") as stream,
        ):
            for fx_index, fixture in enumerate(protocol["fixtures"]):
                state = states[fixture["match_id"]]
                if canonical_hash(state) != fixture["state_hashes"]["named_full"]:
                    print(
                        f"FATAL: state corrupt for {fixture['match_id']}",
                        file=sys.stderr,
                    )
                    return 2
                for arm in ARMS:
                    run_local_id = f"{fixture['match_id']}:{arm}"
                    if run_local_id in done:
                        continue
                    questions = arm_questions(arm)
                    request_time = utc_now_iso()
                    result = call_with_retry(client, state, questions)
                    trial: dict[str, Any] = {
                        "experiment_id": EXPERIMENT_ID,
                        "run_local_id": f"{fixture['match_id']}:{arm}",
                        "fixture_index": fx_index,
                        "match_id": fixture["match_id"],
                        "competition": fixture["competition"],
                        "cohort": COHORT,
                        "arm": arm,
                        "state_sha256": canonical_hash(state),
                        "question_set_version": QB.QUESTION_SET_VERSION,
                        "model_requested": model,
                        "kickoff_utc": fixture["kickoff_utc"],
                        "cutoff_utc": fixture["cutoff_utc"],
                        "request_time_utc": request_time,
                        "error": None,
                        "parsed": {},
                        "fixture_labels": fixture["labels"],
                    }
                    if result is None:
                        trial["error"] = {"kind": "transport_after_retries"}
                        trial["parsed"] = {"validation": "not_attempted"}
                        trials.append(trial)
                        stream.write(
                            json.dumps(trial, ensure_ascii=False, allow_nan=False)
                            + "\n"
                        )
                        stream.flush()
                        exit_code = 1
                        print(
                            f"[{fx_index + 1}] {arm} {fixture['match_id']} -> FAILED",
                            flush=True,
                        )
                        continue
                    usage = result.usage if isinstance(result.usage, dict) else {}
                    input_tokens = usage.get("input_tokens")
                    trial.update(
                        {
                            "http_status": result.status_code,
                            "request_id": result.request_id,
                            "latency_ms": round(result.latency_ms, 1),
                            "input_tokens": input_tokens,
                            "output_tokens": usage.get("output_tokens"),
                            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
                            "model_returned": result.model,
                            "response_time_utc": utc_now_iso(),
                            "raw_response": result.body,
                        }
                    )
                    try:
                        trial["parsed"] = parse_call(arm, result.body)
                    except Exception as exc:
                        trial["parsed"] = {
                            "validation": "parser_error",
                            "rejections": [f"{type(exc).__name__}: {exc}"],
                        }
                        trial["error"] = {
                            "kind": "parser_exception",
                            "message": str(exc)[:300],
                        }
                    trials.append(trial)
                    stream.write(
                        json.dumps(trial, ensure_ascii=False, allow_nan=False) + "\n"
                    )
                    stream.flush()
                    status = trial["parsed"]["validation"]
                    if status != "ok":
                        exit_code = 1
                    print(
                        f"[{fx_index + 1}/{protocol['n_fixtures']}] {arm} {fixture['match_id']} -> {status}",
                        flush=True,
                    )
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    analysis = analyze(trials)
    path = next_run_path(RESULTS_DIR)
    write_json(
        path,
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": path.stem,
            "timestamp_utc": started,
            "protocol_version": protocol["protocol_version"],
            "model_requested": model,
            "git_sha": git_sha(),
            "question_set_version": QB.QUESTION_SET_VERSION,
            "summary": analysis,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print(json.dumps(analysis["totals"], indent=2))
    return exit_code


def analyze(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Paired over/under Brier comparisons and band RPS."""
    by_arm_event: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in trials:
        if t["error"] or t["parsed"]["validation"] != "ok":
            continue
        labels = t["fixture_labels"]
        arm = t["arm"]
        if arm == "noul_thresholds":
            event_to_label = {
                "over_2_5": "over_2_5",
                "corners_over_9_5": "corner_over_9_5",
            }
            for event in ("over_2_5", "corners_over_9_5"):
                ep = t["parsed"]["events"].get(event, {})
                if ep.get("prob") is None:
                    continue
                outcome = labels[event_to_label[event]]
                by_arm_event.setdefault((arm, event), []).append(
                    {"prob": ep["prob"], "outcome": outcome}
                )
        elif arm.endswith("goal_bands"):
            ep = t["parsed"]["events"].get("goal_bands", {})
            if ep.get("over_2_5") is None:
                continue
            by_arm_event.setdefault((arm, "over_2_5"), []).append(
                {
                    "prob": ep["over_2_5"],
                    "outcome": labels["over_2_5"],
                    "dist": ep["distribution"],
                    "one_hot": ep["one_hot"],
                    "actual_count": labels["goals_home_90"] + labels["goals_away_90"],
                }
            )
        elif arm.endswith("corner_bands"):
            ep = t["parsed"]["events"].get("corner_bands", {})
            if ep.get("corners_over_9_5") is None:
                continue
            by_arm_event.setdefault((arm, "corners_over_9_5"), []).append(
                {
                    "prob": ep["corners_over_9_5"],
                    "outcome": labels["corner_over_9_5"],
                    "dist": ep["distribution"],
                    "one_hot": ep["one_hot"],
                    "actual_count": labels["corner_total_90"],
                }
            )

    arms_summary: dict[str, Any] = {}
    for (arm, event), rows in sorted(by_arm_event.items()):
        briers = [(r["prob"] - (1.0 if r["outcome"] else 0.0)) ** 2 for r in rows]
        entry = {
            "n": len(rows),
            "brier_binary": round(sum(briers) / len(briers), 5),
            "mean_prob": round(sum(r["prob"] for r in rows) / len(rows), 4),
        }
        if "dist" in rows[0]:
            entry["mean_prob"] = round(sum(r["prob"] for r in rows) / len(rows), 4)
            entry["one_hot_count"] = sum(1 for r in rows if r["one_hot"])
            bands = QB.GOAL_BANDS if "goal" in arm else QB.CORNER_BANDS
            band_order = [b[0] for b in bands]
            rps_vals = []
            for r in rows:
                idx = QB.band_index_for_count(bands, r["actual_count"])
                rps_vals.append(BP.rps(r["dist"], band_order, idx))
            entry["rps"] = round(sum(rps_vals) / len(rps_vals), 5)
        arms_summary[f"{arm}/{event}"] = entry

    # Paired contrasts at each line: derived band probability vs direct Noul.
    by_match: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for t in trials:
        if t["error"] or t["parsed"]["validation"] != "ok":
            continue
        arm = t["arm"]
        if arm == "noul_thresholds":
            event_to_label = {
                "over_2_5": "over_2_5",
                "corners_over_9_5": "corner_over_9_5",
            }
            for ev in ("over_2_5", "corners_over_9_5"):
                ep = t["parsed"]["events"].get(ev, {})
                if ep.get("prob") is not None:
                    by_match.setdefault((ev, "noul"), {})[t["match_id"]] = {
                        "prob": ep["prob"],
                        "outcome": t["fixture_labels"][event_to_label[ev]],
                    }
        elif arm.endswith("goal_bands"):
            ep = t["parsed"]["events"].get("goal_bands", {})
            if ep.get("over_2_5") is not None:
                kind = "score" if arm.startswith("score") else "choice"
                by_match.setdefault(("over_2_5", kind), {})[t["match_id"]] = {
                    "prob": ep["over_2_5"],
                    "outcome": t["fixture_labels"]["over_2_5"],
                }
        elif arm.endswith("corner_bands"):
            ep = t["parsed"]["events"].get("corner_bands", {})
            if ep.get("corners_over_9_5") is not None:
                kind = "score" if arm.startswith("score") else "choice"
                by_match.setdefault(("corners_over_9_5", kind), {})[t["match_id"]] = {
                    "prob": ep["corners_over_9_5"],
                    "outcome": t["fixture_labels"]["corner_over_9_5"],
                }

    rng = np.random.RandomState(42)
    contrasts: dict[str, Any] = {}
    for event in ("over_2_5", "corners_over_9_5"):
        for kind in ("score", "choice"):
            direct = by_match.get((event, "noul"), {})
            other = by_match.get((event, kind), {})
            common = sorted(set(direct) & set(other))
            if not common:
                continue
            diffs = np.array(
                [
                    (direct[m]["prob"] - (1.0 if direct[m]["outcome"] else 0.0)) ** 2
                    - (other[m]["prob"] - (1.0 if other[m]["outcome"] else 0.0)) ** 2
                    for m in common
                ]
            )
            boots = [
                float(np.mean(rng.choice(diffs, len(diffs)))) for _ in range(10000)
            ]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            contrasts[f"noul_direct_minus_{kind}_bands/{event}"] = {
                "n_paired": len(common),
                "mean_diff": round(float(np.mean(diffs)), 5),
                "ci95": [round(float(lo), 5), round(float(hi), 5)],
                "excludes_zero": bool(lo * hi > 0),
            }
    return {
        "totals": {
            "attempted_calls": len(trials),
            "successful_calls": sum(
                1
                for t in trials
                if not t["error"] and t["parsed"]["validation"] == "ok"
            ),
            "failed_calls": sum(1 for t in trials if t["error"]),
            "rejected_parses": sum(
                1
                for t in trials
                if not t["error"] and t["parsed"]["validation"] == "rejected"
            ),
            "total_input_tokens": sum(t["input_tokens"] or 0 for t in trials),
            "total_estimated_cost_usd": round(
                sum(t["estimated_cost_usd"] or 0.0 for t in trials), 6
            ),
        },
        "arms": arms_summary,
        "paired_contrasts": contrasts,
    }


if __name__ == "__main__":
    raise SystemExit(main())
