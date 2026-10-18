#!/usr/bin/env python3
"""Experiment 020 — Football infrastructure and contamination pilot.

Runs Noul, Score, and Choice on 1X2, over/under 2.5, BTTS, and corners over 9.5
for 48 stratified completed 2025/26 fixtures, plus names/date-only and
anonymized 1X2 controls and a seeded repeat subset. Exploratory only: all calls
happen after the matches finished (retrospective cohort).

Protocol freeze: results/020-football-pilot/protocol-v1.json is written (or
verified byte-identical) before the first scored call. Runs are append-only:
each invocation writes the next run-NNN.json and never overwrites.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))

import questions as Q  # noqa: E402
import parsing as P  # noqa: E402
import selection as SEL  # noqa: E402

from src.data.cli import DERIVED_DIR  # noqa: E402
from src.features import state as state_mod  # noqa: E402
from src.jev_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    JevAPIError,
    JevAuthError,
    JevClient,
    JevConfigError,
    JevMalformedResponseError,
    JevRateLimitError,
    JevTimeoutError,
    JevValidationError,
)
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "020-football-pilot"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PROTOCOL_PATH = RESULTS_DIR / "protocol-v1.json"
COHORT = "retrospective_2025_26"
RETRY_DELAYS_S = (2.0, 5.0)

ARMS_CORE = (
    "noul_1x2",
    "noul_binary",
    "score_1x2",
    "score_binary",
    "choice_1x2",
    "choice_binary",
)
ARMS_CONTROL = ("ctrl_namesdate_noul_1x2", "ctrl_anon_noul_1x2")
ARMS_ALL = ARMS_CORE + ARMS_CONTROL


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


# ---------------------------------------------------------------------------
# State construction


def state_names_date_only(full_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": full_state["schema_version"],
        "fixture": full_state["fixture"],
        "coverage_note": "Control arm: names and dates only; all performance fields omitted.",
    }


def build_states(
    inputs_row: pd.Series, meta_row: pd.Series
) -> dict[str, dict[str, Any]]:
    row = inputs_row.to_dict()
    meta = meta_row.to_dict()
    named = state_mod.state_from_row(row, meta, anonymized=False)
    return {
        "named_full": named,
        "named_date_only": state_names_date_only(named),
        "anonymized_full": state_mod.state_from_row(row, meta, anonymized=True),
    }


def arm_questions(arm: str) -> dict[str, dict[str, Any]]:
    if arm.endswith("_1x2"):
        if "choice" in arm:
            return Q.choice_1x2_question()
        if "noul" in arm:
            return {
                e: q for e, q in Q.noul_questions().items() if e in Q.ONE_X_TWO_EVENTS
            }
        return {e: q for e, q in Q.score_questions().items() if e in Q.ONE_X_TWO_EVENTS}
    if arm == "noul_binary":
        return {e: q for e, q in Q.noul_questions().items() if e in Q.BINARY_EVENTS}
    if arm == "score_binary":
        return {e: q for e, q in Q.score_questions().items() if e in Q.BINARY_EVENTS}
    if arm == "choice_binary":
        return Q.choice_binary_questions()
    raise ValueError(f"unknown arm {arm}")


def arm_state_variant(arm: str) -> str:
    if arm == "ctrl_namesdate_noul_1x2":
        return "named_date_only"
    if arm == "ctrl_anon_noul_1x2":
        return "anonymized_full"
    return "named_full"


# ---------------------------------------------------------------------------
# Request execution with retries


def call_with_retry(
    client: JevClient, state: dict[str, Any], questions: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1 + len(RETRY_DELAYS_S)):
        request_time = utc_now_iso()
        try:
            result = client.system_one(state=state, questions=questions)
        except (JevAuthError, JevValidationError, JevMalformedResponseError) as exc:
            # non-retryable (must precede JevAPIError: auth/validation are subclasses)
            return None, {
                "attempts": attempts
                + [
                    {
                        "attempt": attempt + 1,
                        "request_time_utc": request_time,
                        "error_kind": type(exc).__name__,
                        "message": str(exc)[:500],
                        "status_code": getattr(exc, "status_code", None),
                    }
                ],
                "result": None,
            }
        except (JevTimeoutError, JevRateLimitError, JevAPIError) as exc:
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "request_time_utc": request_time,
                    "error_kind": type(exc).__name__,
                    "message": str(exc)[:500],
                    "status_code": getattr(exc, "status_code", None),
                    "request_id": getattr(exc, "request_id", None),
                }
            )
            if attempt < len(RETRY_DELAYS_S):
                time.sleep(RETRY_DELAYS_S[attempt])
            continue
        response_time = utc_now_iso()
        usage = result.usage if isinstance(result.usage, dict) else {}
        input_tokens = usage.get("input_tokens")
        return {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": round(result.latency_ms, 1),
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
            "model_returned": result.model,
            "response_time_utc": response_time,
            "raw_response": result.body,
        }, {"attempts": attempts, "result": None}
    return None, {"attempts": attempts, "result": None}


# ---------------------------------------------------------------------------
# Parsing one call into validated probabilities


def parse_call(arm: str, body: dict[str, Any]) -> dict[str, Any]:
    """Return {'events': {...}, 'one_x_two': ..., 'validation': ...}."""
    answers = body.get("answers", {})
    parsed: dict[str, Any] = {
        "events": {},
        "derivation_version": P.PROB_DERIVATION_VERSION,
    }
    rejections: list[str] = []

    raw_by_event: dict[str, float] = {}
    for event_id, answer in answers.items():
        if event_id == "result_1x2":
            continue
        kind = answer.get("type")
        if kind == "noul":
            raw = answer.get("noul")
            prob, reason = P.parse_noul_event(raw)
            parsed["events"][event_id] = {"raw": raw, "prob": prob, "reject": reason}
        elif kind == "score":
            raw = answer.get("score")
            prob, reason = P.parse_score_event(raw)
            parsed["events"][event_id] = {
                "raw": raw,
                "prob": prob,
                "reject": reason,
                "level_probabilities": answer.get("probabilities"),
            }
            if prob is not None:
                raw_by_event[event_id] = prob
        elif kind == "choice":
            prob, reason = P.parse_choice_binary(answer.get("probabilities"))
            parsed["events"][event_id] = {
                "raw_choice": answer.get("choice"),
                "prob": prob,
                "reject": reason,
                "confidence": answer.get("confidence"),
            }
        if parsed["events"][event_id]["reject"]:
            rejections.append(f"{event_id}: {parsed['events'][event_id]['reject']}")
        elif kind in ("noul",):
            raw_by_event[event_id] = parsed["events"][event_id]["prob"]

    # Noul/Score 1X2 raw values feed sum-normalization.
    if arm.endswith("_1x2") and ("noul" in arm or "score" in arm):
        dist, reason = P.normalize_three_way(raw_by_event)
        parsed["one_x_two"] = {"distribution": dist, "reject": reason}
        if reason:
            rejections.append(f"one_x_two: {reason}")
    elif arm == "choice_1x2":
        answer = answers.get("result_1x2", {})
        dist, reason = P.parse_choice_1x2(answer.get("probabilities"))
        parsed["one_x_two"] = {
            "distribution": dist,
            "reject": reason,
            "choice": answer.get("choice"),
            "confidence": answer.get("confidence"),
        }
        if reason:
            rejections.append(f"one_x_two: {reason}")
    parsed["validation"] = "ok" if not rejections else "rejected"
    parsed["rejections"] = rejections
    return parsed


# ---------------------------------------------------------------------------
# Protocol freeze


def load_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    labels = pd.read_parquet(DERIVED_DIR / "market_labels.parquet")
    matches = pd.read_parquet(DERIVED_DIR / "matches.parquet")
    return inputs, labels, matches


def freeze_protocol(inputs, labels, matches) -> dict[str, Any]:
    selected, exclusions = SEL.select_fixtures(inputs, labels, matches)
    repeat_ids = SEL.repeat_subset(selected)
    meta_cols = ["match_id", "home_name", "away_name"]
    meta = matches[meta_cols].set_index("match_id")

    fixtures: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        meta_row = meta.loc[row["match_id"]]
        states = build_states(row, meta_row)
        fixture_record = {
            "match_id": row["match_id"],
            "competition": row["competition"],
            "season_start": int(row["season_start"]),
            "round": row.get("round"),
            "kickoff_utc": row["kickoff_utc"].isoformat(),
            "cutoff_utc": row["cutoff_utc"].isoformat(),
            "home_name": meta_row["home_name"],
            "away_name": meta_row["away_name"],
            "strength_tercile": row["strength_tercile"],
            "abs_elo_diff": round(float(row["abs_elo_diff"]), 1),
            "labels": {
                "result_90": row["result_90"],
                "goals_home_90": row["goals_home_90"],
                "goals_away_90": row["goals_away_90"],
                "over_2_5": bool(row["over_2_5"]),
                "btts_yes": bool(row["btts_yes"]),
                "corner_total_90": row["corner_total_90"],
                "corner_source": row["corner_source"],
                "corner_over_9_5": bool(row["corner_total_90"] > Q.CORNER_LINE),
            },
            "state_hashes": {
                variant: canonical_hash(s) for variant, s in states.items()
            },
            "repeat": row["match_id"] in repeat_ids,
        }
        fixtures.append(fixture_record)

    protocol = {
        "protocol_version": "020-protocol-v1",
        "frozen_at_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "cohort": COHORT,
        "model_requested": DEFAULT_MODEL,
        "question_set_version": Q.QUESTION_SET_VERSION,
        "prob_derivation_version": P.PROB_DERIVATION_VERSION,
        "corner_line": Q.CORNER_LINE,
        "selection": {
            "seed": SEL.SEED,
            "per_competition": SEL.PER_COMPETITION,
            "competition_order": list(SEL.COMPETITION_ORDER),
            "season_start": SEL.SEASON_START,
            "strength_bins": "abs(elo_diff) terciles within competition, allocation 3/3/2",
            "repeat_subset_n": SEL.REPEAT_SUBSET_N,
            "repeat_subset": repeat_ids,
        },
        "arms": {
            arm: {
                "questions": arm_questions(arm),
                "state_variant": arm_state_variant(arm),
            }
            for arm in ARMS_ALL
        },
        "request_order_rotation": "per fixture, a seeded shuffle of ARMS_ALL using RandomState(seed+2) at fixture index",
        "metrics": {
            "brier_1x2": "mean over classes of (p_k - y_k)^2",
            "brier_binary": "(p - y)^2",
            "log_loss_floor": P.LOG_LOSS_FLOOR,
            "calibration_bins": [round(0.1 * i, 1) for i in range(10)],
        },
        "retries": {
            "max_retries": len(RETRY_DELAYS_S),
            "delays_s": list(RETRY_DELAYS_S),
            "retry_on": ["timeout", "rate_limit", "api_error_5xx", "network"],
        },
        "scoring_rule": "90 minutes plus stoppage time; corner line 9.5; labels from market_labels.parquet",
        "eligibility_exclusions": exclusions,
        "n_fixtures": len(fixtures),
        "fixtures": fixtures,
    }
    return protocol


# ---------------------------------------------------------------------------
# Main


def main(argv: list[str] | None = None) -> int:
    freeze_only = "--freeze-only" in (argv or sys.argv[1:])
    load_env()
    model = DEFAULT_MODEL
    base_url = DEFAULT_BASE_URL
    started = utc_now_iso()

    inputs, labels, matches = load_tables()
    protocol = freeze_protocol(inputs, labels, matches)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if PROTOCOL_PATH.exists():
        existing = json.loads(PROTOCOL_PATH.read_text())
        if existing["fixtures"] != protocol["fixtures"]:
            print(
                "FATAL: frozen protocol fixture set differs from current selection; refusing to run.",
                file=sys.stderr,
            )
            return 2
        protocol = existing
        print(f"Protocol already frozen at {existing['frozen_at_utc']}; reusing.")
    else:
        write_json(PROTOCOL_PATH, protocol)
        print(
            f"Froze protocol with {protocol['n_fixtures']} fixtures at {protocol['frozen_at_utc']}."
        )
    if freeze_only:
        print("Freeze-only mode: no API calls made.")
        return 0

    meta_cols = ["match_id", "home_name", "away_name"]
    meta = matches[meta_cols].set_index("match_id")
    inputs_by_id = inputs.set_index("match_id")

    rng = np.random.RandomState(SEL.SEED + 2)
    trials: list[dict[str, Any]] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for fx_index, fixture in enumerate(protocol["fixtures"]):
                match_id = fixture["match_id"]
                inputs_row = inputs_by_id.loc[match_id]
                meta_row = meta.loc[match_id]
                states = build_states(inputs_row, meta_row)
                arm_order = list(ARMS_ALL)
                rng.shuffle(arm_order)
                for arm in arm_order:
                    run_arms = [1, 2] if fixture["repeat"] and arm in ARMS_CORE else [1]
                    for repeat_index in run_arms:
                        trial = run_one_call(
                            client,
                            model,
                            protocol,
                            fixture,
                            fx_index,
                            states,
                            arm,
                            repeat_index,
                        )
                        trials.append(trial)
                        status = (
                            trial["parsed"]["validation"]
                            if trial["error"] is None
                            else "ERROR"
                        )
                        print(
                            f"[{fx_index + 1}/{protocol['n_fixtures']}] {arm} r{repeat_index} "
                            f"{match_id} -> {status} in={trial.get('input_tokens')} tok {trial.get('latency_ms')}ms",
                            flush=True,
                        )
                        if trial["error"] is not None or status != "ok":
                            exit_code = 1
    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    analysis = analyze(trials, protocol)
    path = next_run_path(RESULTS_DIR)
    write_json(
        path,
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": path.stem,
            "timestamp_utc": started,
            "cohort": COHORT,
            "protocol_version": protocol["protocol_version"],
            "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "model_requested": model,
            "git_sha": git_sha(),
            "question_set_version": Q.QUESTION_SET_VERSION,
            "summary": analysis,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print(json.dumps(analysis["totals"], indent=2))
    return exit_code


def run_one_call(
    client: JevClient,
    model: str,
    protocol: dict[str, Any],
    fixture: dict[str, Any],
    fx_index: int,
    states: dict[str, dict[str, Any]],
    arm: str,
    repeat_index: int,
) -> dict[str, Any]:
    state_variant = arm_state_variant(arm)
    state = states[state_variant]
    questions = arm_questions(arm)
    request_time = utc_now_iso()
    body, meta = call_with_retry(client, state, questions)
    attempts = meta["attempts"]
    trial: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "run_local_id": f"{fixture['match_id']}:{arm}:r{repeat_index}",
        "fixture_index": fx_index,
        "match_id": fixture["match_id"],
        "competition": fixture["competition"],
        "season_start": fixture["season_start"],
        "round": fixture["round"],
        "cohort": COHORT,
        "arm": arm,
        "repeat_index": repeat_index,
        "state_variant": state_variant,
        "state": state,
        "state_sha256": canonical_hash(state),
        "question_set_version": Q.QUESTION_SET_VERSION,
        "request_questions": questions,
        "model_requested": model,
        "kickoff_utc": fixture["kickoff_utc"],
        "cutoff_utc": fixture["cutoff_utc"],
        "request_time_utc": request_time,
        "attempts": attempts,
        "retries": len(attempts),
        "http_status": None,
        "request_id": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "model_returned": None,
        "response_time_utc": None,
        "raw_response": None,
        "error": None,
        "parsed": {},
        "fixture_labels": fixture["labels"],
    }
    if body is None:
        kinds = [a.get("error_kind") for a in attempts]
        trial["error"] = {
            "kind": kinds[-1] if kinds else "unknown",
            "attempts": attempts,
        }
        trial["parsed"] = {"validation": "not_attempted"}
        return trial

    trial.update(
        {
            k: body[k]
            for k in (
                "http_status",
                "request_id",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "estimated_cost_usd",
                "model_returned",
                "response_time_utc",
                "raw_response",
            )
        }
    )
    trial["response_headers_sanitized"] = (
        None  # headers not retained per-call in the pilot
    )
    try:
        trial["parsed"] = parse_call(arm, body["raw_response"])
    except Exception as exc:  # parser must never invent probabilities
        trial["parsed"] = {
            "validation": "parser_error",
            "rejections": [f"{type(exc).__name__}: {exc}"],
        }
        trial["error"] = {"kind": "parser_exception", "message": str(exc)[:300]}
    return trial


# ---------------------------------------------------------------------------
# Analysis


def analyze(trials: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    labels_by_id = {f["match_id"]: f["labels"] for f in protocol["fixtures"]}
    totals = {
        "attempted_calls": len(trials),
        "successful_calls": 0,
        "failed_calls": 0,
        "rejected_parses": 0,
        "distinct_fixtures": len({t["match_id"] for t in trials}),
        "repeat_pairs": 0,
        "total_input_tokens": 0,
        "total_estimated_cost_usd": 0.0,
    }
    per_arm: dict[str, dict[str, Any]] = {}

    for t in trials:
        if t["error"] is not None or t["parsed"].get("validation") != "ok":
            if t["error"] is not None:
                totals["failed_calls"] += 1
            else:
                totals["rejected_parses"] += 1
            continue
        totals["successful_calls"] += 1
        totals["total_input_tokens"] += t["input_tokens"] or 0
        totals["total_estimated_cost_usd"] += t["estimated_cost_usd"] or 0.0

        arm = t["arm"]
        labels = labels_by_id[t["match_id"]]
        slot = per_arm.setdefault(
            arm,
            {
                "n_calls": 0,
                "events": {},
                "one_x_two": {"n": 0, "brier_3class": [], "log_loss": []},
            },
        )
        slot["n_calls"] += 1
        for event, ep in t["parsed"]["events"].items():
            if ep.get("reject") or ep.get("prob") is None:
                continue
            ev_slot = slot["events"].setdefault(
                event, {"n": 0, "brier": [], "log_loss": [], "probs": []}
            )
            ev_slot["n"] += 1
            prob = ep["prob"]
            ev_slot["probs"].append(prob)
            if event == "home_win":
                outcome, y = labels["result_90"] == "H", None
            elif event == "away_win":
                outcome = labels["result_90"] == "A"
            elif event == "draw":
                outcome = labels["result_90"] == "D"
            elif event == "over_2_5":
                outcome = labels["over_2_5"]
            elif event == "btts_yes":
                outcome = labels["btts_yes"]
            elif event == Q.CORNER_LINE_LABEL:
                outcome = labels["corner_over_9_5"]
            else:
                continue
            if event in ("home_win", "draw", "away_win"):
                continue  # scored via the 1X2 distribution below
            b = P.brier_binary(prob, outcome)
            if b is not None:
                ev_slot["brier"].append(b)
                ev_slot["log_loss"].append(P.log_loss_fixed_floor(prob, outcome))

        dist_slot = t["parsed"].get("one_x_two") or {}
        dist = dist_slot.get("distribution")
        if dist:
            slot["one_x_two"]["n"] += 1
            b = P.brier_three_way(dist, labels["result_90"])
            if b is not None:
                slot["one_x_two"]["brier_3class"].append(b)
                ll = P.log_loss_three_way_fixed_floor(dist, labels["result_90"])
                if ll is not None:
                    slot["one_x_two"]["log_loss"].append(ll)

    def _finalize(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"n": 0, "mean": None}
        return {
            "n": len(values),
            "mean": round(sum(values) / len(values), 5),
            "stdev": round(float(np.std(values, ddof=1)), 5)
            if len(values) > 1
            else None,
        }

    summary_arms: dict[str, Any] = {}
    for arm, slot in per_arm.items():
        entry: dict[str, Any] = {"n_calls": slot["n_calls"], "events": {}}
        for event, ev in slot["events"].items():
            entry["events"][event] = {
                "n": ev["n"],
                "mean_prob": round(sum(ev["probs"]) / len(ev["probs"]), 4)
                if ev["probs"]
                else None,
                "brier_binary": _finalize(ev["brier"])
                if ev["brier"]
                else {"n": 0, "mean": None},
                "log_loss_fixed_floor": _finalize(ev["log_loss"])
                if ev["log_loss"]
                else {"n": 0, "mean": None},
            }
        entry["one_x_two"] = {
            "n": slot["one_x_two"]["n"],
            "brier_3class": _finalize(slot["one_x_two"]["brier_3class"]),
            "log_loss_fixed_floor": _finalize(slot["one_x_two"]["log_loss"]),
        }
        summary_arms[arm] = entry

    # Repeat spread: absolute difference between repeat 1 and 2 per fixture/arm/event.
    repeat_diffs: dict[str, list[float]] = {}
    first: dict[str, dict[str, Any]] = {}
    for t in trials:
        if t["repeat_index"] == 1 and t["parsed"].get("validation") == "ok":
            probs = {e: ep.get("prob") for e, ep in t["parsed"]["events"].items()}
            dist_slot = t["parsed"].get("one_x_two") or {}
            if dist_slot.get("distribution"):
                probs["__one_x_two__"] = dist_slot["distribution"]
            first[f"{t['match_id']}:{t['arm']}:r1"] = probs
    for t in trials:
        if t["repeat_index"] != 2 or t["parsed"].get("validation") != "ok":
            continue
        key1 = f"{t['match_id']}:{t['arm']}:r1"
        base = first.get(key1)
        if base is None:
            continue
        for event, ep in t["parsed"]["events"].items():
            other = base.get(event)
            if other is not None and ep.get("prob") is not None:
                repeat_diffs.setdefault(event, []).append(abs(ep["prob"] - other))
        d1 = (t["parsed"].get("one_x_two") or {}).get("distribution")
        d0 = base.get("__one_x_two__")
        if d1 and d0:
            repeat_diffs.setdefault("one_x_two_l1", []).append(
                sum(abs(d1[k] - d0[k]) for k in d1)
            )
        totals["repeat_pairs"] += 1

    repeat_summary = {
        event: {
            "n_pairs": len(vals),
            "mean_abs_diff": round(sum(vals) / len(vals), 5) if vals else None,
            "max_abs_diff": round(max(vals), 5) if vals else None,
        }
        for event, vals in repeat_diffs.items()
    }

    totals["total_estimated_cost_usd"] = round(totals["total_estimated_cost_usd"], 6)
    return {
        "totals": totals,
        "arms": summary_arms,
        "repeat_spread": repeat_summary,
        "exclusions": protocol["eligibility_exclusions"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
