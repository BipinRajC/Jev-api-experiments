"""Experiment 023 state variants (STATE-ABL-023-v1).

Progressive as-of state compositions, built by filtering the frozen named_full
state of Experiment 020. Field groups (prefixes on each side's team dict):
  identity : fixture block only (competition, team names, season, kickoff, cutoff)
  elo      : elo, elo_games (teams) + elo_diff, elo_exp_home (comparison)
  table    : dom_* (league, position, played, points, gd, gf, ga, ppg)
  form     : form_*, gf_5/10, ga_5/10, matches_played_total, rest_days,
             matches_14d, matches_30d, rolling fm_/us_ shot/xG fields
  h2h      : h2h_* comparison fields
xi_* (lineup-derived) fields appear only in the full state, mirroring 020.
"""

from __future__ import annotations

from typing import Any

STATE_ABLATION_VERSION = "STATE-ABL-023-v1"

TEAM_PREFIX_GROUPS: dict[str, tuple[str, ...]] = {
    "elo": ("elo", "elo_games"),
    "table": ("dom_",),
    "form": (
        "form_",
        "gf_5",
        "ga_5",
        "gf_10",
        "ga_10",
        "matches_played_total",
        "rest_days",
        "matches_14d",
        "matches_30d",
        "fm_",
        "us_",
    ),
}
COMPARISON_GROUPS: dict[str, tuple[str, ...]] = {
    "elo": ("elo_diff", "elo_exp_home"),
    "h2h": ("h2h_",),
}

VARIANTS: dict[str, dict[str, list[str]]] = {
    "identity_only": {"team": (), "comparison": ()},
    "identity_elo": {"team": ("elo",), "comparison": ("elo",)},
    "identity_elo_form": {
        "team": ("elo", "table", "form"),
        "comparison": ("elo", "h2h"),
    },
}


def _matches(key: str, prefixes: tuple[str, ...]) -> bool:
    return any(key == p or key.startswith(p) for p in prefixes)


def filtered_state(full_state: dict[str, Any], variant: str) -> dict[str, Any]:
    """Return a copy of the full state restricted to the variant's field groups."""
    if variant == "full":
        return json_copy(full_state)
    if variant not in VARIANTS:
        raise ValueError(f"unknown state variant {variant}")
    groups = VARIANTS[variant]
    out: dict[str, Any] = {
        "schema_version": full_state["schema_version"],
        "fixture": json_copy(full_state["fixture"]),
        "teams": {},
        "comparison": {},
    }
    team_prefixes = tuple(p for g in groups["team"] for p in TEAM_PREFIX_GROUPS[g])
    comp_prefixes = tuple(p for g in groups["comparison"] for p in COMPARISON_GROUPS[g])
    for side, fields in full_state.get("teams", {}).items():
        out["teams"][side] = {
            k: v for k, v in fields.items() if _matches(k, team_prefixes)
        }
    out["comparison"] = {
        k: v
        for k, v in full_state.get("comparison", {}).items()
        if _matches(k, comp_prefixes)
    }
    if "coverage_note" in full_state:
        out["coverage_note"] = full_state["coverage_note"]
    return out


def json_copy(obj: Any) -> Any:
    import copy

    return copy.deepcopy(obj)
