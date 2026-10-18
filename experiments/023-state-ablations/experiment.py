#!/usr/bin/env python3
"""Experiment 023 — State-composition, model-version, and repeatability ablations.

On the 48 fixtures and frozen named_full states of Experiment 020's protocol:
  - Noul 1X2 with progressive state compositions (identity only, +Elo,
    +table/form/rest, full) on jev-1.13.0, plus the anonymized full control.
  - Paired jev-1.14.0 arms on identity-only and full states.
  - Every 1.13 arm repeated once on all 48 fixtures for repeat spread.
Word/sensitivity-to-wording effects are NOT retested here (009/017 cover them).

Frozen question set: the Noul 1X2 questions of QSET-020-v1. Retrospective,
exploratory, fixed paired subsets. Streaming + resume like 021/022.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "020-football-pilot"))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "023-state-ablations"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import parsing as P20  # noqa: E402
import questions as Q20  # noqa: E402
import state_variants as SV  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exp020_for_023",
    REPO_ROOT / "experiments" / "020-football-pilot" / "experiment.py",
)
exp020 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp020)  # reuses 020's frozen Noul 1X2 parse_call verbatim

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

EXPERIMENT_ID = "023-state-ablations"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID
PROTOCOL_PATH = RESULTS_DIR / "protocol-v1.json"
PROTOCOL_020 = REPO_ROOT / "results" / "020-football-pilot" / "protocol-v1.json"
MODEL_113 = "jev-1.13.0"
MODEL_114 = "jev-1.14.0"
# (arm, model, state_variant)
ARMS: tuple[tuple[str, str, str], ...] = (
    ("id_only_113", MODEL_113, "identity_only"),
    ("id_elo_113", MODEL_113, "identity_elo"),
    ("id_elo_form_113", MODEL_113, "identity_elo_form"),
    ("full_113", MODEL_113, "full"),
    ("anon_full_113", MODEL_113, "anonymized"),
    ("id_only_114", MODEL_114, "identity_only"),
    ("full_114", MODEL_114, "full"),
)
REPEAT_ARMS = ("id_elo_form_113", "full_113")
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


def build_anon_state(inputs_row: pd.Series, meta_row: pd.Series) -> dict[str, Any]:
    return state_mod.state_from_row(
        inputs_row.to_dict(), meta_row.to_dict(), anonymized=True
    )


def freeze_protocol() -> dict[str, Any]:
    protocol_020 = json.loads(PROTOCOL_020.read_text())
    fixtures_020 = protocol_020["fixtures"]

    inputs = pd.read_parquet(DERIVED_DIR / "model_inputs.parquet")
    matches = pd.read_parquet(DERIVED_DIR / "matches.parquet")
    meta = matches.set_index("match_id")
    inputs_by_id = inputs.set_index("match_id")

    fixtures: list[dict[str, Any]] = []
    states_by_variant: dict[str, dict[str, dict[str, Any]]] = {}
    for f in fixtures_020:
        match_id = f["match_id"]
        row = inputs_by_id.loc[match_id]
        meta_row = meta.loc[match_id]
        full = state_mod.state_from_row(
            row.to_dict(), meta_row.to_dict(), anonymized=False
        )
        if canonical_hash(full) != f["state_hashes"]["named_full"]:
            print(f"FATAL: 020 state hash drift for {match_id}.", file=sys.stderr)
            raise SystemExit(2)
        variants = {v: SV.filtered_state(full, v) for v in SV.VARIANTS}
        variants["full"] = full
        variants["anonymized"] = build_anon_state(row, meta_row)
        for v, s in variants.items():
            states_by_variant.setdefault(v, {})[match_id] = s
        fixtures.append(
            {
                "match_id": match_id,
                "competition": f["competition"],
                "cohort": "retrospective_2025_26",
                "kickoff_utc": f["kickoff_utc"],
                "cutoff_utc": f["cutoff_utc"],
                "labels": f["labels"],
                "state_hashes": {v: canonical_hash(s) for v, s in variants.items()},
            }
        )

    protocol = {
        "protocol_version": "023-protocol-v1",
        "frozen_at_utc": utc_now_iso(),
        "git_sha": git_sha(),
        "cohort": "retrospective_2025_26",
        "paired_with": "results/020-football-pilot/protocol-v1.json (same 48 fixtures)",
        "state_ablation_version": SV.STATE_ABLATION_VERSION,
        "question_set_version": Q20.QUESTION_SET_VERSION,
        "noul_1x2_questions": {
            e: q for e, q in Q20.noul_questions().items() if e in Q20.ONE_X_TWO_EVENTS
        },
        "prob_derivation_version": P20.PROB_DERIVATION_VERSION,
        "arms": [{"arm": a, "model": m, "state_variant": v} for a, m, v in ARMS],
        "repeat_arms": list(REPEAT_ARMS),
        "wording_ablations": "not retested here; covered by experiments 009 and 017",
        "retries": {
            "max_retries": len(RETRY_DELAYS_S),
            "delays_s": list(RETRY_DELAYS_S),
        },
        "n_fixtures": len(fixtures),
        "fixtures": fixtures,
    }
    write_json(RESULTS_DIR / "states-001.json", states_by_variant)
    return protocol


def call_with_retry(
    client: JevClient,
    state: dict[str, Any],
    questions: dict[str, dict[str, Any]],
    model: str,
) -> dict[str, Any] | None:
    import time

    for attempt in range(1 + len(RETRY_DELAYS_S)):
        try:
            return client.system_one(state=state, questions=questions, model=model)
        except Exception:
            if attempt < len(RETRY_DELAYS_S):
                time.sleep(RETRY_DELAYS_S[attempt])
            continue
    return None


def run_one(
    client: JevClient,
    fixture: dict[str, Any],
    arm: str,
    model: str,
    state: dict[str, Any],
    state_variant: str,
    repeat_index: int,
) -> dict[str, Any]:
    questions = {
        e: q for e, q in Q20.noul_questions().items() if e in Q20.ONE_X_TWO_EVENTS
    }
    request_time = utc_now_iso()
    result = call_with_retry(client, state, questions, model)
    trial: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "run_local_id": f"{fixture['match_id']}:{arm}:r{repeat_index}",
        "match_id": fixture["match_id"],
        "competition": fixture["competition"],
        "cohort": fixture["cohort"],
        "arm": arm,
        "model_requested": model,
        "state_variant": state_variant,
        "state": state,
        "state_sha256": canonical_hash(state),
        "question_set_version": Q20.QUESTION_SET_VERSION,
        "request_questions": questions,
        "kickoff_utc": fixture["kickoff_utc"],
        "cutoff_utc": fixture["cutoff_utc"],
        "request_time_utc": request_time,
        "repeat_index": repeat_index,
        "error": None,
        "parsed": {},
        "fixture_labels": fixture["labels"],
    }
    if result is None:
        trial["error"] = {"kind": "transport_after_retries"}
        trial["parsed"] = {"validation": "not_attempted"}
        return trial
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
    # Reuse 020's Noul 1X2 parsing verbatim via its parse_call.
    try:
        # arm "noul_1x2" triggers the Noul 1X2 normalization path.
        trial["parsed"] = exp020.parse_call("noul_1x2", result.body)
    except Exception as exc:
        trial["parsed"] = {
            "validation": "parser_error",
            "rejections": [f"{type(exc).__name__}: {exc}"],
        }
        trial["error"] = {"kind": "parser_exception", "message": str(exc)[:300]}
    return trial


def analyze(trials: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [
        t
        for t in trials
        if not t["error"]
        and t["parsed"]["validation"] == "ok"
        and t["parsed"].get("one_x_two", {}).get("distribution")
    ]
    by_arm: dict[str, dict[str, list[float]]] = {}
    by_arm_match: dict[str, dict[str, dict[str, Any]]] = {}
    for t in ok:
        lab = t["fixture_labels"]
        dist = t["parsed"]["one_x_two"]["distribution"]
        b = P20.brier_three_way(dist, lab["result_90"])
        if b is None:
            continue
        slot = by_arm.setdefault(t["arm"], {"brier": [], "tokens": [], "latency": []})
        slot["brier"].append(b)
        slot["tokens"].append(t["input_tokens"] or 0)
        slot["latency"].append(t["latency_ms"] or 0.0)
        if t["repeat_index"] == 1:
            by_arm_match.setdefault(t["arm"], {})[t["match_id"]] = {
                "brier": b,
                "dist": dist,
            }

    arms_summary = {}
    for arm, slot in sorted(by_arm.items()):
        entry = {
            "n": len(slot["brier"]),
            "brier_3class": round(sum(slot["brier"]) / len(slot["brier"]), 5),
            "mean_input_tokens": round(sum(slot["tokens"]) / len(slot["tokens"]), 1),
            "mean_latency_ms": round(sum(slot["latency"]) / len(slot["latency"]), 1),
        }
        # paired contrasts vs full_113 (r1)
        base = by_arm_match.get("full_113", {})
        common = sorted(set(by_arm_match.get(arm, {})) & set(base))
        if common and arm != "full_113":
            diffs = np.array(
                [by_arm_match[arm][m]["brier"] - base[m]["brier"] for m in common]
            )
            rng = np.random.RandomState(42)
            boots = [
                float(np.mean(rng.choice(diffs, len(diffs)))) for _ in range(10000)
            ]
            lo, hi = np.percentile(boots, [2.5, 97.5])
            entry["paired_vs_full_113"] = {
                "n": len(common),
                "mean_diff": round(float(np.mean(diffs)), 5),
                "ci95": [round(float(lo), 5), round(float(hi), 5)],
                "excludes_zero": bool(lo * hi > 0),
            }
        arms_summary[arm] = entry

    # repeat spread per arm (r1 vs r2 same state and model)
    repeat = {}
    first = {}
    for t in ok:
        if t["repeat_index"] == 1:
            d = t["parsed"]["one_x_two"]["distribution"]
            first[f"{t['match_id']}:{t['arm']}"] = d
    for t in ok:
        if t["repeat_index"] != 2:
            continue
        d0 = first.get(f"{t['match_id']}:{t['arm']}")
        d1 = t["parsed"]["one_x_two"]["distribution"]
        if d0:
            l1 = sum(abs(d1[k] - d0[k]) for k in d1)
            repeat.setdefault(t["arm"], []).append(l1)
    repeat_summary = {
        arm: {
            "n": len(v),
            "mean_l1": round(sum(v) / len(v), 5),
            "max_l1": round(max(v), 5),
        }
        for arm, v in repeat.items()
    }

    totals = {
        "attempted_calls": len(trials),
        "successful_calls": len(ok),
        "failed_calls": sum(1 for t in trials if t["error"]),
        "rejected_parses": sum(
            1 for t in trials if not t["error"] and t["parsed"]["validation"] != "ok"
        ),
        "total_input_tokens": sum(t["input_tokens"] or 0 for t in trials),
        "total_estimated_cost_usd": round(
            sum(t["estimated_cost_usd"] or 0.0 for t in trials), 6
        ),
        "models_returned": sorted(
            {t["model_returned"] for t in trials if t["model_returned"]}
        ),
    }
    return {"totals": totals, "arms": arms_summary, "repeat_spread": repeat_summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    load_env()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if PROTOCOL_PATH.exists():
        protocol = json.loads(PROTOCOL_PATH.read_text())
        print(f"Protocol already frozen at {protocol['frozen_at_utc']}; reusing.")
    else:
        protocol = freeze_protocol()
        write_json(PROTOCOL_PATH, protocol)
        print(
            f"Froze 023 protocol: {protocol['n_fixtures']} fixtures x {len(ARMS)} arms (+repeats)."
        )
    if args.freeze_only:
        print("Freeze-only mode: no API calls made.")
        return 0

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
            JevClient(model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL) as client,
            stream_path.open("a") as stream,
        ):
            for fx_index, fixture in enumerate(protocol["fixtures"]):
                for arm, model, variant in ARMS:
                    repeats = (1, 2) if arm in REPEAT_ARMS else (1,)
                    for repeat_index in repeats:
                        run_local_id = f"{fixture['match_id']}:{arm}:r{repeat_index}"
                        if run_local_id in done:
                            continue
                        state = states[variant][fixture["match_id"]]
                        if canonical_hash(state) != fixture["state_hashes"][variant]:
                            print(
                                f"FATAL: state corrupt for {fixture['match_id']} {variant}",
                                file=sys.stderr,
                            )
                            return 2
                        trial = run_one(
                            client, fixture, arm, model, state, variant, repeat_index
                        )
                        trials.append(trial)
                        stream.write(
                            json.dumps(trial, ensure_ascii=False, allow_nan=False)
                            + "\n"
                        )
                        stream.flush()
                        status = (
                            trial["parsed"]["validation"]
                            if trial["error"] is None
                            else "ERROR"
                        )
                        if fx_index % 10 == 0 or status != "ok":
                            print(
                                f"[{fx_index + 1}/{protocol['n_fixtures']}] {arm} r{repeat_index} {fixture['match_id']} -> {status}",
                                flush=True,
                            )
                        if trial["error"] is not None or status != "ok":
                            exit_code = 1
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
            "timestamp_utc": utc_now_iso(),
            "protocol_version": protocol["protocol_version"],
            "model_requested": DEFAULT_MODEL,
            "git_sha": git_sha(),
            "question_set_version": Q20.QUESTION_SET_VERSION,
            "summary": analysis,
            "trials_reference": "stream-001.jsonl (append-only per-call records)",
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print(json.dumps(analysis["totals"], indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
