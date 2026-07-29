"""Tests for ukweather.spectral — own spectral indices from raw scenes
(spec: first-principles-validation, Own spectral indices requirement).

All pure logic tested on synthetic arrays: band arithmetic on published
reflectance only, growing-season filter, the 1984 floor, qa_pixel cloud
masking, per-sensor provenance, ring aggregation and insufficiency
reason codes. No network in this file.
"""

import numpy as np
import pytest
from affine import Affine

from ukweather.spectral import (
    DECADES,
    MIN_SCENES,
    MIN_VALID_FRACTION,
    clear_mask,
    composite_median,
    decade_of,
    in_growing_season,
    ndbi,
    ndvi,
    ring_index_stats,
    scale_l2_reflectance,
    sensor_of_platform,
)

T = Affine(30.0, 0.0, 0.0, 0.0, -30.0, 0.0)  # 30 m grid at origin


class TestBandArithmetic:
    def test_l2_scaling(self):
        # Landsat C2 L2 surface reflectance: value * 0.0000275 - 0.2
        dn = np.array([7273.0])  # -> 0.0000275*7273 - 0.2 = 0.0000075...
        r = scale_l2_reflectance(dn)
        assert r[0] == pytest.approx(0.0000275 * 7273 - 0.2, abs=1e-9)

    def test_ndvi_known_value(self):
        nir = np.array([0.5]); red = np.array([0.1])
        assert ndvi(red=red, nir=nir)[0] == pytest.approx((0.5 - 0.1) / 0.6)

    def test_ndbi_known_value(self):
        swir = np.array([0.3]); nir = np.array([0.5])
        assert ndbi(nir=nir, swir=swir)[0] == pytest.approx((0.3 - 0.5) / 0.8)

    def test_zero_denominator_is_nan(self):
        out = ndvi(red=np.array([0.0]), nir=np.array([0.0]))
        assert np.isnan(out[0])


class TestQaMask:
    def test_cloud_and_shadow_bits_masked(self):
        # qa_pixel bits: 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud, 4 shadow
        qa = np.array([0b0000000, 1 << 3, 1 << 4, 1 << 1, 1 << 2, 1 << 0])
        m = clear_mask(qa)
        assert m.tolist() == [True, False, False, False, False, False]


class TestSeasonAndDecades:
    def test_growing_season_may_to_september(self):
        assert in_growing_season("2005-05-01")
        assert in_growing_season("2005-09-30")
        assert not in_growing_season("2005-04-30")
        assert not in_growing_season("2005-10-01")

    def test_decade_assignment(self):
        assert decade_of(1984) == 1980
        assert decade_of(1999) == 1990
        assert decade_of(2020) == 2020

    def test_decades_include_pre_floor_marker(self):
        assert DECADES == [1970, 1980, 1990, 2000, 2010, 2020]

    @pytest.mark.parametrize("platform,sensor", [
        ("landsat-4", "TM"), ("landsat-5", "TM"), ("landsat-7", "ETM+"),
        ("landsat-8", "OLI"), ("landsat-9", "OLI"),
    ])
    def test_sensor_of_platform(self, platform, sensor):
        assert sensor_of_platform(platform) == sensor


class TestComposite:
    def test_median_ignores_masked_observations(self):
        # 3 observations of a 1x2 grid; pixel 0 cloudy in obs 2
        stack = np.array([[[0.2, 0.4]], [[0.3, 0.5]], [[9.9, 0.6]]])
        clear = np.array([[[True, True]], [[True, True]], [[False, True]]])
        comp, nobs = composite_median(stack, clear)
        assert comp[0, 0] == pytest.approx(0.25)  # median of 0.2, 0.3
        assert comp[0, 1] == pytest.approx(0.5)
        assert nobs[0, 0] == 2 and nobs[0, 1] == 3

    def test_pixel_with_no_clear_obs_is_nan(self):
        stack = np.array([[[0.2]]]); clear = np.array([[[False]]])
        comp, nobs = composite_median(stack, clear)
        assert np.isnan(comp[0, 0]) and nobs[0, 0] == 0


class TestRingStats:
    def grid(self, value, shape=(60, 60)):
        return np.full(shape, value, dtype=float)

    def test_ring_mean_of_uniform_index(self):
        # ring centred mid-grid on the 30 m grid
        idx = self.grid(0.7)
        nobs = np.full(idx.shape, 5)
        s = ring_index_stats(idx, nobs, T, cx=900.0, cy=-900.0, radius_m=500)
        assert s["value"] == pytest.approx(0.7, abs=1e-6)
        assert s["reason"] is None
        assert s["valid_fraction"] == pytest.approx(1.0, abs=1e-3)

    def test_insufficient_clear_coverage_nulled(self):
        idx = self.grid(0.7)
        idx[:, 30:] = np.nan  # right half never clear
        nobs = np.where(np.isnan(idx), 0, 5)
        s = ring_index_stats(idx, nobs, T, cx=900.0, cy=-900.0, radius_m=500)
        assert s["value"] is None
        assert s["reason"] == "insufficient-clear-coverage"
        assert s["valid_fraction"] == pytest.approx(0.5, abs=0.05)

    def test_thresholds_documented_constants(self):
        assert MIN_SCENES >= 2
        assert 0.5 <= MIN_VALID_FRACTION <= 1.0
