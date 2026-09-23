#!/usr/bin/env python3
"""Experiment 007 — Mixed / Non-Trivial Evidence.

Tests whether Jev produces partial/non-one-hot outputs when evidence is
genuinely mixed, using synthetic probabilistic problems with known
ground-truth probabilities.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.choice import extract_choice  # noqa: E402
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
from src.noul import extract_noul  # noqa: E402
from src.score import extract_score  # noqa: E402
from src.utils import (  # noqa: E402
    estimate_input_cost_usd,
    load_env,
    next_run_path,
    sanitize_headers,
    utc_now_iso,
    write_json,
)

EXPERIMENT_ID = "007-mixed-evidence"
RESULTS_DIR = REPO_ROOT / "results" / EXPERIMENT_ID

# ---------------------------------------------------------------------------
# Sub-experiment A — Noul with known probabilities
# ---------------------------------------------------------------------------
NOUL_COIN_STATE_TEMPLATE = (
    "A biased coin lands heads {pct}% of the time and tails {other}% of the time. "
    "The coin is flipped once."
)

NOUL_CASES = [
    {
        "case_id": "noul_coin_fair",
        "pct": 50,
        "description": "fair coin",
        "ground_truth_p_heads": 0.50,
    },
    {
        "case_id": "noul_coin_70",
        "pct": 70,
        "description": "70% heads",
        "ground_truth_p_heads": 0.70,
    },
    {
        "case_id": "noul_coin_30",
        "pct": 30,
        "description": "30% heads",
        "ground_truth_p_heads": 0.30,
    },
    {
        "case_id": "noul_coin_90",
        "pct": 90,
        "description": "90% heads",
        "ground_truth_p_heads": 0.90,
    },
    {
        "case_id": "noul_coin_10",
        "pct": 10,
        "description": "10% heads",
        "ground_truth_p_heads": 0.10,
    },
    {
        "case_id": "noul_coin_taut_yes",
        "pct": 100,
        "description": "tautological yes (100%)",
        "ground_truth_p_heads": 1.0,
    },
    {
        "case_id": "noul_coin_taut_no",
        "pct": 0,
        "description": "tautological no (0%)",
        "ground_truth_p_heads": 0.0,
    },
]

# ---------------------------------------------------------------------------
# Sub-experiment B — Choice with probabilistic urn
# ---------------------------------------------------------------------------
CHOICE_URN_STATE = (
    "An urn contains 50 red balls, 30 blue balls, and 20 green balls. "
    "One ball is drawn uniformly at random."
)

CHOICE_URN_QUESTIONS = {
    "urn_color": {
        "type": "choice",
        "instructions": "What color will the randomly drawn ball be?",
        "criteria": {
            "red": "The ball is red.",
            "blue": "The ball is blue.",
            "green": "The ball is green.",
        },
    }
}

# ---------------------------------------------------------------------------
# Sub-experiment C — Score with graded evidence
# ---------------------------------------------------------------------------
SCORE_RUBRIC = [
    {"score": 0, "label": "no evidence"},
    {"score": 1, "label": "very weak evidence"},
    {"score": 2, "label": "weak evidence"},
    {"score": 3, "label": "moderate evidence"},
    {"score": 4, "label": "strong evidence"},
    {"score": 5, "label": "overwhelming evidence"},
]

SCORE_QUESTIONS = {
    "evidence_level": {
        "type": "score",
        "instructions": (
            "Based on the description, what level of evidence supports the "
            "stated hypothesis?"
        ),
        "criteria": SCORE_RUBRIC,
    }
}

SCORE_CASES = [
    {
        "case_id": "score_vague_hint",
        "state": (
            "Hypothesis: The supplement reduces symptom duration. "
            "Some preliminary data suggests the supplement might reduce symptom "
            "duration, but the sample size is tiny and contradictory data also exists."
        ),
        "description": "intended ~1 (very weak)",
        "intended_range": (0, 2),
    },
    {
        "case_id": "score_weak_study",
        "state": (
            "Hypothesis: The intervention improves test scores. "
            "A single small study with n=30 and p=0.08 supports the intervention. "
            "No replication exists."
        ),
        "description": "intended ~2 (weak)",
        "intended_range": (1, 3),
    },
    {
        "case_id": "score_moderate",
        "state": (
            "Hypothesis: The treatment reduces recovery time. "
            "Two independent studies with moderate sample sizes find statistically "
            "significant results. One replication attempt failed."
        ),
        "description": "intended ~3 (moderate)",
        "intended_range": (2, 4),
    },
    {
        "case_id": "score_strong",
        "state": (
            "Hypothesis: The drug lowers blood pressure. "
            "Five large randomized controlled trials consistently support the "
            "hypothesis. Two meta-analyses confirm the effect."
        ),
        "description": "intended ~4 (strong)",
        "intended_range": (3, 5),
    },
    {
        "case_id": "score_overwhelming",
        "state": (
            "Hypothesis: Smoking causes lung cancer. "
            "Dozens of independent labs across multiple countries have replicated "
            "the finding. The effect is well-established scientific consensus."
        ),
        "description": "intended ~5 (overwhelming)",
        "intended_range": (4, 5),
    },
]


def _coin_state(pct: int) -> str:
    return NOUL_COIN_STATE_TEMPLATE.format(pct=pct, other=100 - pct)


def _noul_coin_questions() -> dict[str, dict]:
    return {
        "heads_noul": {
            "type": "noul",
            "instructions": "Will the next flip land heads?",
        }
    }


def _batch_coin_questions() -> dict[str, dict]:
    return {
        "heads_noul": {
            "type": "noul",
            "instructions": "Will the next flip land heads?",
        },
        "coin_choice": {
            "type": "choice",
            "instructions": "What will the next flip land on?",
            "criteria": {
                "heads": "The coin lands heads.",
                "tails": "The coin lands tails.",
            },
        },
        "coin_score": {
            "type": "score",
            "instructions": "How likely is it that the coin lands heads?",
            "criteria": [
                {"score": 0, "label": "impossible"},
                {"score": 1, "label": "unlikely"},
                {"score": 2, "label": "even odds"},
                {"score": 3, "label": "likely"},
                {"score": 4, "label": "certain"},
            ],
        },
    }


def main() -> int:
    load_env()
    model = os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
    started_at = utc_now_iso()
    trials: list[dict] = []
    exit_code = 0

    try:
        with JevClient(model=model, base_url=base_url) as client:
            for coin_case in NOUL_CASES:
                state = _coin_state(coin_case["pct"])
                trial = _run_batch_trial(
                    client,
                    coin_case["case_id"],
                    state,
                    _batch_coin_questions(),
                    coin_case,
                )
                trials.append(trial)
                _print_coin_trial(trial)
                if trial.get("error"):
                    exit_code = 1

            urn_trial = _run_urn_trial(client)
            trials.append(urn_trial)
            _print_urn_trial(urn_trial)
            if urn_trial.get("error"):
                exit_code = 1

            for sc_case in SCORE_CASES:
                trial = _run_batch_trial(
                    client,
                    sc_case["case_id"],
                    sc_case["state"],
                    SCORE_QUESTIONS,
                    sc_case,
                )
                trials.append(trial)
                _print_score_trial(trial)
                if trial.get("error"):
                    exit_code = 1

    except JevConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    analysis = _analyze(trials)

    path = next_run_path(RESULTS_DIR)
    write_json(
        path,
        {
            "experiment_id": EXPERIMENT_ID,
            "run_id": path.stem,
            "timestamp": started_at,
            "model_requested": model,
            "api": {
                "provider": "typesafe_direct",
                "base_url": base_url,
                "endpoint": "/v1/systemone",
                "method": "POST",
            },
            "design": {
                "description": (
                    "Batch calls per case with Noul+Choice+Score coin questions, "
                    "one standalone Choice urn call, and Score-only evidence calls."
                ),
                "noul_cases": [
                    {k: v for k, v in c.items() if k != "state"} for c in NOUL_CASES
                ],
                "choice_urn": {
                    "state": CHOICE_URN_STATE,
                    "options": ["red", "blue", "green"],
                    "composition": {"red": 50, "blue": 30, "green": 20},
                },
                "score_cases": [
                    {"case_id": c["case_id"], "description": c["description"]}
                    for c in SCORE_CASES
                ],
                "score_rubric": SCORE_RUBRIC,
            },
            "analysis": analysis,
            "trials": trials,
        },
    )
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    print("--- Analysis ---")
    for key, val in analysis.items():
        print(f"  {key}: {val}")
    return exit_code


# ---------------------------------------------------------------------------
# Trial runners
# ---------------------------------------------------------------------------


def _run_batch_trial(
    client: JevClient,
    case_id: str,
    state: str,
    questions: dict[str, dict],
    case_meta: dict,
) -> dict:
    record = _empty_trial(case_id, state)
    try:
        result = client.system_one(state=state, questions=questions)
    except JevAuthError as exc:
        record["error"] = _error("auth", exc)
        return record
    except JevValidationError as exc:
        record["error"] = _error("validation", exc)
        return record
    except JevRateLimitError as exc:
        record["error"] = _error("rate_limit", exc)
        return record
    except JevTimeoutError as exc:
        record["error"] = {"kind": "timeout", "message": str(exc)}
        return record
    except JevMalformedResponseError as exc:
        record["error"] = {"kind": "malformed_response", "message": str(exc)}
        return record
    except JevAPIError as exc:
        record["error"] = _error("api", exc)
        return record

    usage = result.usage if isinstance(result.usage, dict) else {}
    input_tokens = usage.get("input_tokens")
    record.update(
        {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": result.latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
            "model_returned": result.model,
            "response_headers": sanitize_headers(result.headers),
            "raw_response": result.body,
        }
    )

    parsed: dict[str, dict] = {}
    for qid in questions:
        answer_data = result.body.get("answers", {}).get(qid, {})
        qtype = answer_data.get("type", "unknown")
        parsed[qid] = {"type": qtype}
        if qtype == "noul":
            parsed[qid]["noul"] = answer_data.get("noul")
        elif qtype == "choice":
            parsed[qid]["choice"] = answer_data.get("choice")
            parsed[qid]["probabilities"] = answer_data.get("probabilities")
            parsed[qid]["confidence"] = answer_data.get("confidence")
        elif qtype == "score":
            parsed[qid]["score"] = answer_data.get("score")
            parsed[qid]["legend"] = answer_data.get("legend")
            parsed[qid]["probabilities"] = answer_data.get("probabilities")
            parsed[qid]["confidence"] = answer_data.get("confidence")
    record["parsed"] = parsed

    record["case_meta"] = {k: v for k, v in case_meta.items() if k != "state"}
    return record


def _run_urn_trial(client: JevClient) -> dict:
    record = _empty_trial("choice_urn", CHOICE_URN_STATE)
    try:
        result = client.system_one(
            state=CHOICE_URN_STATE, questions=CHOICE_URN_QUESTIONS
        )
    except JevAuthError as exc:
        record["error"] = _error("auth", exc)
        return record
    except JevValidationError as exc:
        record["error"] = _error("validation", exc)
        return record
    except JevRateLimitError as exc:
        record["error"] = _error("rate_limit", exc)
        return record
    except JevTimeoutError as exc:
        record["error"] = {"kind": "timeout", "message": str(exc)}
        return record
    except JevMalformedResponseError as exc:
        record["error"] = {"kind": "malformed_response", "message": str(exc)}
        return record
    except JevAPIError as exc:
        record["error"] = _error("api", exc)
        return record

    usage = result.usage if isinstance(result.usage, dict) else {}
    input_tokens = usage.get("input_tokens")
    record.update(
        {
            "http_status": result.status_code,
            "request_id": result.request_id,
            "latency_ms": result.latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost_usd": estimate_input_cost_usd(input_tokens),
            "model_returned": result.model,
            "response_headers": sanitize_headers(result.headers),
            "raw_response": result.body,
        }
    )
    try:
        choice_data = extract_choice(result.body, "urn_color")
        record["parsed"] = {
            "urn_color": {
                "type": "choice",
                "choice": choice_data["choice"],
                "probabilities": choice_data["probabilities"],
                "confidence": choice_data["confidence"],
            }
        }
    except ValueError as exc:
        record["error"] = {"kind": "parse", "message": str(exc)}

    record["case_meta"] = {
        "composition": {"red": 50, "blue": 30, "green": 20},
        "description": "probabilistic urn, non-trivial Choice",
    }
    return record


def _empty_trial(case_id: str, state: str) -> dict:
    return {
        "case_id": case_id,
        "state": state,
        "timestamp": utc_now_iso(),
        "http_status": None,
        "request_id": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "model_returned": None,
        "response_headers": {},
        "raw_response": None,
        "parsed": {},
        "error": None,
    }


def _error(kind: str, exc) -> dict:
    return {
        "kind": kind,
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "body": getattr(exc, "body", None),
        "request_id": getattr(exc, "request_id", None),
    }


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _print_coin_trial(trial: dict) -> None:
    p = trial.get("parsed", {})
    noul = p.get("heads_noul", {}).get("noul")
    choice = p.get("coin_choice", {})
    score = p.get("coin_score", {})
    print(
        f"{trial['case_id']} HTTP {trial.get('http_status')} "
        f"noul={noul} "
        f"choice={choice.get('choice')} "
        f"score={score.get('score')} "
        f"choice_conf={choice.get('confidence')} "
        f"score_conf={score.get('confidence')} "
        f"lat={trial.get('latency_ms')}"
    )


def _print_urn_trial(trial: dict) -> None:
    p = trial.get("parsed", {}).get("urn_color", {})
    print(
        f"choice_urn HTTP {trial.get('http_status')} "
        f"choice={p.get('choice')} "
        f"probs={p.get('probabilities')} "
        f"conf={p.get('confidence')} "
        f"lat={trial.get('latency_ms')}"
    )


def _print_score_trial(trial: dict) -> None:
    p = trial.get("parsed", {}).get("evidence_level", {})
    print(
        f"{trial['case_id']} HTTP {trial.get('http_status')} "
        f"score={p.get('score')} "
        f"probs={p.get('probabilities')} "
        f"conf={p.get('confidence')} "
        f"lat={trial.get('latency_ms')}"
    )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _analyze(trials: list[dict]) -> dict:
    analysis: dict = {}

    noul_results = []
    for t in trials:
        p = t.get("parsed", {})
        heads_noul = p.get("heads_noul", {})
        if heads_noul.get("type") == "noul" and heads_noul.get("noul") is not None:
            meta = t.get("case_meta", {})
            noul_results.append(
                {
                    "case_id": t["case_id"],
                    "noul": heads_noul["noul"],
                    "ground_truth": meta.get("ground_truth_p_heads"),
                }
            )

    if noul_results:
        extreme_count = sum(
            1 for r in noul_results if r["noul"] in (0.0, 1.0, 0.99, 0.01)
        )
        non_extreme = [
            r for r in noul_results if r["noul"] not in (0.0, 1.0, 0.99, 0.01)
        ]
        analysis["noul_count"] = len(noul_results)
        analysis["noul_extreme_count"] = extreme_count
        analysis["noul_non_extreme_count"] = len(non_extreme)
        if non_extreme:
            analysis["noul_non_extreme_values"] = non_extreme
            ground_diffs = [
                abs(r["noul"] - r["ground_truth"])
                for r in non_extreme
                if r["ground_truth"] is not None
            ]
            if ground_diffs:
                analysis["noul_mean_abs_error"] = sum(ground_diffs) / len(ground_diffs)
                analysis["noul_max_abs_error"] = max(ground_diffs)
                analysis["noul_min_abs_error"] = min(ground_diffs)

    urn_trial = next((t for t in trials if t["case_id"] == "choice_urn"), None)
    if urn_trial:
        urn = urn_trial.get("parsed", {}).get("urn_color", {})
        probs = urn.get("probabilities", {})
        analysis["urn_choice_label"] = urn.get("choice")
        analysis["urn_probabilities"] = probs
        analysis["urn_confidence"] = urn.get("confidence")
        one_hot = (
            sum(1 for v in probs.values() if v > 0.99) == 1
            and sum(1 for v in probs.values() if v < 0.01) == len(probs) - 1
        )
        analysis["urn_is_one_hot"] = one_hot

    score_results = []
    for t in trials:
        p = t.get("parsed", {}).get("evidence_level", {})
        if p.get("type") == "score" and p.get("score") is not None:
            score_results.append(
                {
                    "case_id": t["case_id"],
                    "score": p["score"],
                    "confidence": p.get("confidence"),
                    "probabilities": p.get("probabilities"),
                }
            )
    if score_results:
        analysis["score_count"] = len(score_results)
        integer_count = sum(
            1
            for r in score_results
            if isinstance(r["score"], (int, float)) and r["score"] == int(r["score"])
        )
        analysis["score_integer_count"] = integer_count
        analysis["score_non_integer_count"] = len(score_results) - integer_count
        confs = [r["confidence"] for r in score_results if r["confidence"] is not None]
        if confs:
            analysis["score_confidence_values"] = confs
            analysis["score_confidence_lt_1_count"] = sum(1 for c in confs if c < 1.0)

    all_confs = []
    for t in trials:
        for _, pd in t.get("parsed", {}).items():
            c = pd.get("confidence")
            if c is not None:
                all_confs.append(
                    {"case_id": t["case_id"], "qtype": pd.get("type"), "confidence": c}
                )
    if all_confs:
        all_ones = sum(1 for c in all_confs if c["confidence"] == 1.0)
        analysis["total_confidence_values"] = len(all_confs)
        analysis["confidence_1_count"] = all_ones
        analysis["confidence_lt_1_count"] = len(all_confs) - all_ones

    return analysis


if __name__ == "__main__":
    raise SystemExit(main())
