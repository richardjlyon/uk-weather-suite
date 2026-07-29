"""Trend estimation for the paired-difference primary endpoint.

Spec: add-analysis, trend-engine. The estimator is deliberately narrow —
the review killed two earlier designs, so what survives is:

* anomalies within a station, never absolute cross-station comparison;
* a **single slope with intercept shifts at breaks**, never an average
  of separately-fitted segment slopes (that is not the window trend and
  is biased when break dates differ between cohorts);
* the primary quantity is the trend of a matched pair's **difference
  series** on its common support, carrying intercept shifts at the union
  of both members' break dates, because differencing cancels the shared
  climate signal — including nonlinear warming and shared long-memory
  noise — by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MONTHS_PER_YEAR = 12


@dataclass
class TrendFit:
    slope_per_decade: float
    stderr_per_decade: float
    n: int
    breaks_modelled: tuple[float, ...]


def monthly_anomalies(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Remove each station's own seasonal cycle. Fixed offsets and the
    seasonal shape cancel; nothing is compared across stations."""
    out = np.full_like(x, np.nan, dtype=float)
    month = np.floor((t % 1.0) * MONTHS_PER_YEAR).astype(int)
    for m in range(MONTHS_PER_YEAR):
        sel = month == m
        vals = x[sel]
        if np.isfinite(vals).sum() >= 3:
            out[sel] = vals - np.nanmean(vals)
    return out


def _design(t: np.ndarray, breaks: tuple[float, ...]) -> np.ndarray:
    cols = [np.ones_like(t), (t - t[0]) / 10.0]
    for b in breaks:
        cols.append((t >= b).astype(float))
    return np.column_stack(cols)


def _ar1_effective_n(resid: np.ndarray) -> float:
    """Effective sample size under AR(1); the standard correction for
    serially correlated residuals."""
    r = resid[np.isfinite(resid)]
    if r.size < 10:
        return float(r.size)
    r1 = float(np.corrcoef(r[:-1], r[1:])[0, 1])
    r1 = min(max(r1, 0.0), 0.99)
    return float(r.size * (1 - r1) / (1 + r1))


def fit_trend(t: np.ndarray, y: np.ndarray, breaks: tuple[float, ...] = ()) -> TrendFit:
    """Single-slope model with intercept shifts at `breaks`, AR(1)-corrected."""
    ok = np.isfinite(y)
    if ok.sum() < 24:
        return TrendFit(np.nan, np.nan, int(ok.sum()), breaks)
    tt, yy = t[ok], y[ok]
    breaks = tuple(b for b in breaks if tt[0] < b < tt[-1])
    X = _design(tt, breaks)
    beta, *_ = np.linalg.lstsq(X, yy, rcond=None)
    resid = yy - X @ beta
    dof_n = _ar1_effective_n(resid)
    p = X.shape[1]
    if dof_n <= p + 1:
        return TrendFit(float(beta[1]), np.nan, int(ok.sum()), breaks)
    s2 = float(resid @ resid) / (dof_n - p)
    xtx_inv = np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(s2 * xtx_inv[1, 1] * (yy.size / dof_n)))
    return TrendFit(float(beta[1]), se, int(ok.sum()), breaks)


def paired_difference_trend(
    t: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    breaks_a: tuple[float, ...] = (),
    breaks_b: tuple[float, ...] = (),
) -> TrendFit:
    """THE primary estimator: trend of (a - b) on common support, with
    intercept shifts at the union of both members' break dates.

    Order matters, and the synthetic killer worlds proved it. Taking each
    station's anomalies *first* and differencing after is biased when the
    two members have different missingness: each station's monthly
    climatology is then computed over a different set of years, so a
    station that is absent disproportionately in cool early years gets a
    climatology that is too warm and anomalies that are too cool, and the
    difference inherits a spurious trend. Differencing first and taking
    the seasonal cycle out of the *difference* removes it: the
    climatology is then computed on exactly the months where both members
    reported.
    """
    raw = a - b  # NaN wherever either member is missing => common support
    d = monthly_anomalies(t, raw)
    return fit_trend(t, d, tuple(sorted(set(breaks_a) | set(breaks_b))))
