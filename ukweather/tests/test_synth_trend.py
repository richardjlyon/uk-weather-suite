"""Synthetic validation of the primary estimator.

Spec: add-analysis, "Synthetic validation before deposit opening". The
pipeline must recover a known injected signal, return null when there is
none, and — the point of the exercise — return null on the two killer
worlds that are built to fool a naive estimator.
"""

from __future__ import annotations

import numpy as np

from ukweather import synth
from ukweather.trend import paired_difference_trend


def cohort_effect(world: synth.World, seed: int = 0) -> tuple[float, float]:
    """Mean paired-difference trend (urbanised minus control), and its
    standard error across pairs. Pairs are formed arbitrarily but
    one-to-one, which is enough for a synthetic world where stations
    differ only by cohort."""
    rng = np.random.default_rng(seed)
    urb = sorted(world.urbanised)
    ctl = sorted(world.controls)
    rng.shuffle(urb)
    rng.shuffle(ctl)
    slopes = []
    for u, c in zip(urb, ctl):
        fit = paired_difference_trend(
            world.years,
            world.series[u],
            world.series[c],
            tuple(b for b, _ in world.breaks.get(u, [])),
            tuple(b for b, _ in world.breaks.get(c, [])),
        )
        if np.isfinite(fit.slope_per_decade):
            slopes.append(fit.slope_per_decade)
    arr = np.array(slopes)
    return float(arr.mean()), float(arr.std(ddof=1) / np.sqrt(arr.size))


def test_known_signal_is_recovered():
    w = synth.world_signal(uhi_per_decade=0.30, seed=11)
    est, se = cohort_effect(w, seed=11)
    assert abs(est - 0.30) < 0.05, f"expected ~0.30 C/decade, got {est:.3f}"
    assert est / se > 5, "a real signal must be clearly distinguishable from zero"


def test_no_signal_returns_null():
    w = synth.world_null(seed=12)
    est, se = cohort_effect(w, seed=12)
    assert abs(est) < 2.5 * se, f"null world must not produce a signal: {est:.3f} +/- {se:.3f}"


def test_killer_cohort_correlated_breaks_returns_null():
    """Killer 1. Accelerating warming, urban stations breaking a decade
    before rural ones, real step magnitudes, and ZERO urban heat.
    A design that averages segment slopes fails here; the paired
    difference with union-of-breaks intercepts must not."""
    w = synth.killer_breaks(seed=13)
    assert w.injected_uhi_per_decade == 0.0
    steps = [s for sts in w.breaks.values() for _, s in sts]
    assert np.std(steps) > 0.1, "date-only breaks would make this test vacuous"
    est, se = cohort_effect(w, seed=13)
    assert abs(est) < 2.5 * se, (
        f"cohort-correlated breaks manufactured a signal: {est:.3f} +/- {se:.3f}"
    )


def test_killer_cohort_correlated_missingness_returns_null():
    """Killer 2. Rural stations gap more, and earlier, under accelerating
    warming, with ZERO urban heat."""
    w = synth.killer_missing(seed=14)
    assert w.injected_uhi_per_decade == 0.0
    est, se = cohort_effect(w, seed=14)
    assert abs(est) < 2.5 * se, (
        f"cohort-correlated missingness manufactured a signal: {est:.3f} +/- {se:.3f}"
    )


def test_naive_segment_averaging_would_have_failed():
    """Demonstrates why the estimator is specified as it is: fitting the
    two sides of a break separately and averaging the slopes DOES
    manufacture a signal on killer world 1. This test documents the
    trap rather than the fix."""
    w = synth.killer_breaks(seed=15)
    from ukweather.trend import fit_trend, monthly_anomalies

    def naive(sid: str) -> float:
        y = monthly_anomalies(w.years, w.series[sid])
        bs = [b for b, _ in w.breaks.get(sid, [])]
        if not bs:
            return fit_trend(w.years, y).slope_per_decade
        b = bs[0]
        left = w.years < b
        f1 = fit_trend(w.years[left], y[left])
        f2 = fit_trend(w.years[~left], y[~left])
        vals = [f.slope_per_decade for f in (f1, f2) if np.isfinite(f.slope_per_decade)]
        return float(np.mean(vals)) if vals else np.nan

    urb = [naive(s) for s in sorted(w.urbanised)]
    ctl = [naive(s) for s in sorted(w.controls)]
    gap = np.nanmean(urb) - np.nanmean(ctl)
    assert abs(gap) > 0.05, (
        "the naive estimator was expected to be fooled here; if it is not, "
        "the killer world is too weak to be doing its job"
    )
