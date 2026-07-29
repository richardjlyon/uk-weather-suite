"""Synthetic station networks with known injected signal.

The analysis spec (add-analysis, "Synthetic validation before deposit
opening") requires the whole pipeline to prove itself on data whose
answer we already know, before the frozen classification is opened. Two
of those worlds are *killer cases*: they contain ZERO urban-heat signal
but are built to fool a naive estimator, and the pipeline must return
null on them or the design is revised before real data is touched.

Nothing here reads real observations. Randomness is seeded and the seed
is part of the returned world, so any result is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MONTHS_PER_YEAR = 12


@dataclass
class World:
    """A synthetic network: monthly series per station plus the truth."""

    years: np.ndarray  # decimal year per month step
    series: dict[str, np.ndarray]  # station id -> monthly temperature
    urbanised: set[str]
    breaks: dict[str, list[tuple[float, float]]]  # station -> [(year, step)]
    injected_uhi_per_decade: float
    seed: int
    notes: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def controls(self) -> set[str]:
        return set(self.series) - self.urbanised


def _time_axis(start: int, end: int) -> np.ndarray:
    n = (end - start) * MONTHS_PER_YEAR
    return start + np.arange(n) / MONTHS_PER_YEAR


def _common_signal(t: np.ndarray, rng: np.random.Generator, *, nonlinear: bool) -> np.ndarray:
    """Shared climate: seasonal cycle, warming, and correlated noise.

    `nonlinear` gives the accelerating shape the UK record actually has
    (little trend to ~1988, steeper after), which is what makes
    cohort-correlated breaks dangerous.
    """
    seasonal = 6.0 * np.sin(2 * np.pi * (t % 1.0))
    if nonlinear:
        warm = np.where(t < 1988, 0.02 * (t - t[0]), 0.02 * (1988 - t[0]) + 0.32 * (t - 1988))
    else:
        warm = 0.15 * (t - t[0]) / 10.0
    # AR(1) climate noise shared by all stations in the region
    noise = np.zeros_like(t)
    e = rng.normal(0, 0.7, size=t.size)
    for i in range(1, t.size):
        noise[i] = 0.55 * noise[i - 1] + e[i]
    return seasonal + warm + noise


def make_world(
    *,
    n_stations: int = 200,
    start: int = 1975,
    end: int = 2019,
    uhi_per_decade: float = 0.0,
    nonlinear_warming: bool = True,
    cohort_correlated_breaks: bool = False,
    break_step_sd: float = 0.0,
    cohort_correlated_missing: bool = False,
    seed: int = 1,
    notes: str = "",
) -> World:
    """Build a synthetic network.

    uhi_per_decade
        Warming added to urbanised stations only, ramped linearly. Zero
        for the killer cases.
    cohort_correlated_breaks
        Urban stations get their instrument break earlier than rural
        ones — the real pattern, since automation reached synoptic and
        airport sites first. Combined with nonlinear warming this is the
        classic way to manufacture a spurious cohort difference.
    break_step_sd
        Standard deviation of the break's step magnitude. **Date-only
        breaks make the test vacuous** (review finding, 2026-07-29), so
        a killer world must set this non-zero.
    cohort_correlated_missing
        Rural stations lose data at different times and rates from urban
        ones, so that within-support gaps differ by cohort.
    """
    rng = np.random.default_rng(seed)
    t = _time_axis(start, end)
    common = _common_signal(t, rng, nonlinear=nonlinear_warming)

    ids = [f"S{i:04d}" for i in range(n_stations)]
    urbanised = set(rng.choice(ids, size=n_stations // 2, replace=False).tolist())

    series: dict[str, np.ndarray] = {}
    breaks: dict[str, list[tuple[float, float]]] = {}

    for sid in ids:
        # station character: fixed offset (altitude/exposure) + own noise
        x = common + rng.normal(0, 1.2) + rng.normal(0, 0.35, size=t.size)

        if sid in urbanised and uhi_per_decade:
            ramp = (t - t[0]) / 10.0
            x = x + uhi_per_decade * ramp

        st: list[tuple[float, float]] = []
        if cohort_correlated_breaks:
            # urban sites automate earlier; rural later
            centre = 1992.0 if sid in urbanised else 2002.0
            byear = float(rng.normal(centre, 2.0))
            step = float(rng.normal(0.0, break_step_sd)) if break_step_sd else 0.0
            x = x + np.where(t >= byear, step, 0.0)
            st.append((byear, step))
        breaks[sid] = st

        if cohort_correlated_missing:
            # urban sites report more completely; rural sites gap more,
            # and their gaps concentrate in the earlier record
            p_missing = 0.03 if sid in urbanised else 0.14
            early = t < np.quantile(t, 0.4)
            drop = rng.random(t.size) < np.where(early, p_missing * 2, p_missing)
            x = np.where(drop, np.nan, x)

        series[sid] = x

    return World(
        years=t,
        series=series,
        urbanised=urbanised,
        breaks=breaks,
        injected_uhi_per_decade=uhi_per_decade,
        seed=seed,
        notes=notes,
        meta={
            "nonlinear_warming": nonlinear_warming,
            "cohort_correlated_breaks": cohort_correlated_breaks,
            "break_step_sd": break_step_sd,
            "cohort_correlated_missing": cohort_correlated_missing,
            "n_stations": n_stations,
            "start": start,
            "end": end,
        },
    )


# --- the pre-registered worlds -------------------------------------------------

def world_signal(uhi_per_decade: float = 0.3, seed: int = 1) -> World:
    """Plain world with a known urban-heat signal. Must be recovered."""
    return make_world(uhi_per_decade=uhi_per_decade, seed=seed,
                      notes=f"injected UHI {uhi_per_decade} C/decade")


def world_null(seed: int = 2) -> World:
    """No signal, no traps. Must return null."""
    return make_world(uhi_per_decade=0.0, seed=seed, notes="zero signal, no traps")


def killer_breaks(seed: int = 3) -> World:
    """Killer 1: accelerating warming + cohort-correlated breaks with
    realistic step magnitudes, and ZERO urban heat. Must return null."""
    return make_world(
        uhi_per_decade=0.0,
        nonlinear_warming=True,
        cohort_correlated_breaks=True,
        break_step_sd=0.25,
        seed=seed,
        notes="ZERO UHI; nonlinear warming; urban breaks ~1992, rural ~2002; steps sd 0.25 C",
    )


def killer_missing(seed: int = 4) -> World:
    """Killer 2: cohort-correlated missingness with ZERO urban heat.
    Must return null."""
    return make_world(
        uhi_per_decade=0.0,
        nonlinear_warming=True,
        cohort_correlated_missing=True,
        seed=seed,
        notes="ZERO UHI; nonlinear warming; rural stations gap more, and earlier",
    )
