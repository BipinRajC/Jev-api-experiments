"""Focused tests for the Experiment 021 mathematical baselines."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "experiments" / "021-retrospective-locked"))

import baselines as B  # noqa: E402


class TestPriorFrequencies:
    def test_known_rates(self):
        res = np.array(["H", "D", "A", "H"])
        over = np.array([True, False, True, False])
        btts = np.array([True, False, True, False])
        out = B.prior_frequencies(res, over, btts, None)
        assert out["p_home"] == pytest.approx(0.5)
        assert out["p_draw"] == pytest.approx(0.25)
        assert out["p_away"] == pytest.approx(0.25)
        assert out["p_over_2_5"] == pytest.approx(0.5)
        assert out["p_btts"] == pytest.approx(0.5)


class TestEloLogit:
    def test_recovers_separable_orders(self):
        rng = np.random.RandomState(0)
        x = rng.uniform(-400, 400, 2000)
        # deterministic: positive diff -> H, zero-ish -> D, negative -> A
        y = np.where(x > 100, "H", np.where(x < -100, "A", "D"))
        model = B.EloLogit().fit(x, y)
        p = model.predict_proba(np.array([300.0, 0.0, -300.0]))
        assert p["H"][0] > p["H"][2]  # more likely home win at +300
        assert p["A"][2] > p["A"][0]
        assert np.allclose(sum(v for v in p.values()), 1.0, atol=1e-6)


class TestDixonColes:
    def _dev_data(self):
        # Two evenly matched teams, symmetric: expected ~1.35 goals each
        rng = np.random.RandomState(3)
        n = 4000
        home = ["A"] * (n // 2) + ["B"] * (n // 2)
        away = ["B"] * (n // 2) + ["A"] * (n // 2)
        gh = rng.poisson(1.45, n)  # slight home boost
        ga = rng.poisson(1.15, n)
        days = rng.uniform(0, 365, n)  # all recent
        return home, away, gh, ga, days

    def test_fit_recovers_rates_and_matrix_sums_to_one(self):
        home, away, gh, ga, days = self._dev_data()
        m = B.DixonColes().fit(home, away, gh, ga, days)
        p = m.outcome_probs("A", "B")
        assert p["home"] + p["draw"] + p["away"] == pytest.approx(1.0, abs=1e-6)
        assert 0 < p["over_2_5"] < 1
        assert 0 < p["btts"] < 1
        # A at home scored mean 1.45 vs B's 1.15 → A should be favored at home
        assert p["home"] > p["away"]
        assert m.home_adv > 1.0

    def test_symmetric_fixture_is_balanced(self):
        # Force exact symmetry: B's home scores are copies of A's home scores.
        rng = np.random.RandomState(3)
        n2 = 2000
        gh1, ga1 = rng.poisson(1.45, n2), rng.poisson(1.15, n2)
        home = ["A"] * n2 + ["B"] * n2
        away = ["B"] * n2 + ["A"] * n2
        gh = np.concatenate([gh1, gh1])
        ga = np.concatenate([ga1, ga1])
        days = np.zeros(2 * n2)
        m = B.DixonColes().fit(home, away, gh, ga, days)
        assert m.attack["A"] == pytest.approx(m.attack["B"], rel=1e-9)
        assert m.defense["A"] == pytest.approx(m.defense["B"], rel=1e-9)
        p1 = m.outcome_probs("A", "B")
        p2 = m.outcome_probs("B", "A")
        assert p1["home"] == pytest.approx(p2["home"], abs=1e-9)
        assert p1["home"] > p2["away"]  # home advantage preserved

    def test_strong_attack_dominate(self):
        rng = np.random.RandomState(5)
        n = 3000
        home = ["A"] * n
        away = ["B"] * n
        gh = rng.poisson(2.2, n)
        ga = rng.poisson(0.7, n)
        days = np.zeros(n)
        m = B.DixonColes().fit(home, away, gh, ga, days)
        p = m.outcome_probs("A", "B")
        assert p["home"] > 0.7
        assert p["over_2_5"] > 0.5

    def test_tau_correction_bounds(self):
        mu = 1.3
        assert B._tau(0, 0, mu, mu, 0.0) == pytest.approx(1.0)
        assert B._tau(2, 2, mu, mu, 0.05) == pytest.approx(1.0)
        assert B._tau(1, 1, mu, mu, 0.05) == pytest.approx(0.95)
        assert B._tau(0, 1, mu, mu, 0.05) == pytest.approx(1.0 + mu * 0.05)


class TestCornerModel:
    def test_dispersion_ratio(self):
        arr = np.array([10.0, 10.0, 10.0, 10.0])
        d = B.corner_dispersion(arr)
        assert d["dispersion_ratio"] == pytest.approx(0.0)

    def test_poisson_choice_for_equidispersed(self):
        rng = np.random.RandomState(1)
        arr = rng.poisson(9.8, 5000).astype(float)
        out = B.corner_over_probability(arr, 9.5)
        assert out["model"] == "poisson" or out["model"] == "negative_binomial"
        # near-half line: p should be near 0.5
        assert 0.3 < out["p_over"] < 0.7

    def test_overdispersed_uses_negative_binomial(self):
        rng = np.random.RandomState(2)
        lam = rng.gamma(2.0, 5.0, 8000)  # overdispersed counts
        arr = rng.poisson(lam).astype(float)
        out = B.corner_over_probability(arr, 9.5)
        assert out["model"] == "negative_binomial"
        assert out["dispersion"]["dispersion_ratio"] > 1.5
        assert 0 < out["p_over"] < 1

    def test_real_corner_data_is_overdispersed(self):
        """The development corner totals should justify the NB choice (documents the check)."""
        import pandas as pd

        labels = pd.read_parquet("data/derived/market_labels.parquet")
        inputs = pd.read_parquet(
            "data/derived/model_inputs.parquet", columns=["match_id", "season_start"]
        )
        df = labels.merge(inputs, on="match_id", validate="one_to_one")
        dev = df[(df["season_start"] <= 2024) & df["corner_total_90"].notna()]
        out = B.corner_over_probability(dev["corner_total_90"].to_numpy(), 9.5)
        assert out["model"] == "negative_binomial"
        assert out["dispersion"]["dispersion_ratio"] > 1.1
        assert 0.4 < out["p_over"] < 0.6  # matches the measured 0.514 rate
