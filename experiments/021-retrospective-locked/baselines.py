"""Mathematical baselines for Experiments 021/025 (BASELINE-021-v1).

All baselines are fitted on development data only (seasons through 2024/25)
and applied to later seasons; nothing here ever sees the evaluated season's
results.

Components:
  - prior_frequencies: constant H/D/A, over-2.5, BTTS, corners-over-9.5 rates
    from the development seasons.
  - EloLogit: multinomial logistic mapping of the as-of Elo difference to
    H/D/A probabilities (sklearn, fitted on development fixtures).
  - DixonColes: joint-goals Poisson model with team attack/defense parameters,
    home advantage, time decay, and the Dixon-Coles low-score correction;
    produces 1X2, over/under 2.5, and BTTS probabilities from a score matrix.
  - CornerModel: dispersion-checked count model for total corners; negative
    binomial (method of moments) when variance/mean exceeds 1.1, Poisson
    otherwise; P(total > line) from the count distribution; optional Elo
    logistic adjustment is NOT included in v1 (kept deliberately simple).

Every function is deterministic; random seeds are fixed where relevant.
"""

from __future__ import annotations

from typing import Any

import numpy as np

BASELINE_VERSION = "BASELINE-021-v1"
MAX_GOALS = 11  # score-matrix side length; tail probabilities folded into 10


def prior_frequencies(
    result_90: np.ndarray,
    over_2_5: np.ndarray,
    btts: np.ndarray,
    corners_over: np.ndarray | None,
) -> dict[str, float]:
    """Constant base-rate baseline from development-season outcomes."""
    n = len(result_90)
    out = {
        "p_home": float(np.mean(result_90 == "H")),
        "p_draw": float(np.mean(result_90 == "D")),
        "p_away": float(np.mean(result_90 == "A")),
        "p_over_2_5": float(np.mean(over_2_5)),
        "p_btts": float(np.mean(btts)),
    }
    if corners_over is not None and len(corners_over):
        out["p_corners_over"] = float(np.mean(corners_over))
    out["n"] = n
    return out


class EloLogit:
    """Multinomial logistic H/D/A probabilities from the as-of Elo difference."""

    def __init__(self) -> None:
        self._clf: Any = None

    def fit(self, elo_diff: np.ndarray, result_90: np.ndarray) -> "EloLogit":
        from sklearn.linear_model import LogisticRegression

        x = np.asarray(elo_diff, dtype=float).reshape(-1, 1)
        self._clf = LogisticRegression(max_iter=1000)
        self._clf.fit(x, result_90)
        self.classes_ = list(self._clf.classes_)
        return self

    def predict_proba(self, elo_diff: np.ndarray) -> dict[str, np.ndarray]:
        x = np.asarray(elo_diff, dtype=float).reshape(-1, 1)
        proba = self._clf.predict_proba(x)
        out: dict[str, np.ndarray] = {}
        for i, cls in enumerate(self.classes_):
            out[str(cls)] = proba[:, i]
        return out


def _tau(x: int, y: int, mu_home: float, mu_away: float, rho: float) -> float:
    """Dixon-Coles low-score dependency correction."""
    if x == 0 and y == 0:
        return 1.0 - mu_home * mu_away * rho
    if x == 0 and y == 1:
        return 1.0 + mu_home * rho
    if x == 1 and y == 0:
        return 1.0 + mu_away * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


class DixonColes:
    """Joint-goals Poisson model with DC correction.

    Fit with the standard iterative proportional updates on weighted match
    results; time-decay weights w = exp(-xi * age_days).
    """

    def __init__(self, xi_per_day: float = 0.0015, n_iter: int = 30) -> None:
        self.xi_per_day = xi_per_day
        self.n_iter = n_iter
        self.attack: dict[str, float] = {}
        self.defense: dict[str, float] = {}
        self.home_adv: float = 1.0
        self.rho: float = 0.0

    @staticmethod
    def _weights(kickoff_days_ago: np.ndarray, xi_per_day: float) -> np.ndarray:
        return np.exp(-xi_per_day * np.asarray(kickoff_days_ago, dtype=float))

    def fit(
        self,
        home_team: list[str],
        away_team: list[str],
        goals_home: np.ndarray,
        goals_away: np.ndarray,
        kickoff_days_ago: np.ndarray,
    ) -> "DixonColes":
        teams = sorted(set(home_team) | set(away_team))
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        w = self._weights(kickoff_days_ago, self.xi_per_day)
        gh = np.asarray(goals_home, dtype=float)
        ga = np.asarray(goals_away, dtype=float)
        h_idx = np.array([idx[t] for t in home_team])
        a_idx = np.array([idx[t] for t in away_team])

        attack = np.full(n, 1.0)
        defense = np.full(n, 1.0)
        home_adv = 1.2
        for _ in range(self.n_iter):
            # attack update: scored goals / opponent-defense terms (attack excluded)
            num = np.bincount(h_idx, weights=w * gh, minlength=n) + np.bincount(
                a_idx, weights=w * ga, minlength=n
            )
            den = np.bincount(
                h_idx, weights=w * home_adv * defense[a_idx], minlength=n
            ) + np.bincount(a_idx, weights=w * defense[h_idx], minlength=n)
            attack = np.where(den > 0, num / np.maximum(den, 1e-9), 1.0)
            attack = attack / np.exp(
                np.mean(np.log(np.maximum(attack, 1e-9)))
            )  # mean 1
            # defense update: conceded goals / opponent-attack terms (defense excluded)
            num_d = np.bincount(h_idx, weights=w * ga, minlength=n) + np.bincount(
                a_idx, weights=w * gh, minlength=n
            )
            den_d = np.bincount(
                h_idx, weights=w * attack[a_idx], minlength=n
            ) + np.bincount(a_idx, weights=w * home_adv * attack[h_idx], minlength=n)
            defense = np.where(den_d > 0, num_d / np.maximum(den_d, 1e-9), 1.0)
            defense = defense / np.exp(np.mean(np.log(np.maximum(defense, 1e-9))))
            # home advantage: scored-at-home / expected-at-home (gamma excluded)
            mu_h_no_gamma = attack[h_idx] * defense[a_idx]
            home_adv = (
                float(np.sum(w * gh) / max(np.sum(w * mu_h_no_gamma), 1e-9))
                if np.sum(w * mu_h_no_gamma) > 0
                else home_adv
            )

        self.attack = {t: float(attack[idx[t]]) for t in teams}
        self.defense = {t: float(defense[idx[t]]) for t in teams}
        self.home_adv = float(home_adv)

        # rho: 1-D weighted MLE over the four low-score cells, given rates.
        from scipy.optimize import minimize_scalar

        mu_h = home_adv * attack[h_idx] * defense[a_idx]
        mu_a = attack[a_idx] * defense[h_idx]

        def neg_ll(rho: float) -> float:
            if not -0.2 < rho < 0.2:
                return 1e9
            ll = 0.0
            tau = np.array(
                [
                    _tau(int(x), int(y), mh, ma, rho)
                    for x, y, mh, ma in zip(gh, ga, mu_h, mu_a)
                ]
            )
            if np.any(tau <= 0):
                return 1e9
            from scipy.stats import poisson

            p = poisson.pmf(gh, mu_h) * poisson.pmf(ga, mu_a) * tau
            ll = float(np.sum(w * np.log(np.maximum(p, 1e-12))))
            return -ll

        res = minimize_scalar(neg_ll, bounds=(-0.19, 0.19), method="bounded")
        self.rho = float(res.x)
        return self

    def score_matrix(self, home_team: str, away_team: str) -> np.ndarray:
        """P(home goals = x, away goals = y), x,y in 0..MAX_GOALS-1."""
        from scipy.stats import poisson

        mu_h = self.home_adv * self.attack[home_team] * self.defense[away_team]
        mu_a = self.attack[away_team] * self.defense[home_team]
        xs = np.arange(MAX_GOALS)
        pmf_h = poisson.pmf(xs, mu_h)
        pmf_a = poisson.pmf(xs, mu_a)
        m = np.outer(pmf_h, pmf_a)
        tau = np.array(
            [
                _tau(int(x), int(y), mu_h, mu_a, self.rho)
                for x in range(MAX_GOALS)
                for y in range(MAX_GOALS)
            ]
        ).reshape(MAX_GOALS, MAX_GOALS)
        m = m * tau
        total = m.sum()
        if total <= 0 or not np.isfinite(total):
            raise ValueError(f"degenerate score matrix for {home_team} vs {away_team}")
        return m / total

    def outcome_probs(self, home_team: str, away_team: str) -> dict[str, float]:
        m = self.score_matrix(home_team, away_team)
        ph = float(np.tril(m, -1).sum())  # x > y → home win
        pd_ = float(np.trace(m))
        pa = float(np.triu(m, 1).sum())
        gh = np.arange(MAX_GOALS)[:, None]
        ga = np.arange(MAX_GOALS)[None, :]
        p_over = float(m[(gh + ga) > 2.5].sum())
        p_btts = float(m[(gh >= 1) & (ga >= 1)].sum())
        return {"home": ph, "draw": pd_, "away": pa, "over_2_5": p_over, "btts": p_btts}


def corner_dispersion(corner_totals: np.ndarray) -> dict[str, float]:
    """Mean/variance/dispersion ratio for total corners."""
    arr = np.asarray(corner_totals, dtype=float)
    mean = float(np.mean(arr))
    var = float(np.var(arr, ddof=1))
    return {
        "mean": mean,
        "variance": var,
        "dispersion_ratio": var / mean if mean > 0 else float("inf"),
    }


def corner_over_probability(
    corner_totals: np.ndarray, line: float = 9.5
) -> dict[str, Any]:
    """Dispersion-checked P(total > line) from the development distribution.

    Uses a negative binomial (method of moments) when the dispersion ratio
    exceeds 1.1, otherwise Poisson. The count grid extends to mean + 8*sd.
    """
    from scipy.stats import nbinom, poisson

    disp = corner_dispersion(corner_totals)
    mean = disp["mean"]
    max_count = int(np.ceil(mean + 8 * np.sqrt(max(disp["variance"], 1.0)))) + 2
    counts = np.arange(0, max_count + 1)
    if disp["dispersion_ratio"] > 1.1:
        # NB via method of moments: var = mean + mean^2/size
        size = mean**2 / max(disp["variance"] - mean, 1e-9)
        p = size / (size + mean)
        pmf = nbinom.pmf(counts, size, p)
        model = "negative_binomial"
    else:
        pmf = poisson.pmf(counts, mean)
        model = "poisson"
    pmf = pmf / pmf.sum()
    p_over = float(pmf[counts > line].sum())
    return {"model": model, "p_over": p_over, "dispersion": disp, "line": line}
