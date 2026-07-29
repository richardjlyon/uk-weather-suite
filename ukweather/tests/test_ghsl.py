"""Tests for ukweather.ghsl — GHSL ring extraction (spec: builtup-extraction).

Unit tests run on synthetic arrays with analytically known fractions;
integration tests (marked) need the real tiles under data/ghsl/.
"""

import math
from pathlib import Path

import numpy as np
import pytest
from affine import Affine
from pyproj import Transformer

from ukweather.ghsl import (
    EPOCHS,
    epoch_provenance,
    ring_polygon,
    ring_stats,
    sample_raster_class,
)

DATA = Path(__file__).parents[2] / "data" / "ghsl"

# A synthetic 100 m grid mimicking the GHSL Mollweide layout: 60 x 60
# cells with origin chosen at a round number. Values are m^2 per cell
# (0..10000), as in GHS-BUILT-S and GHS-LAND; nodata is 65535.
ORIGIN_X, ORIGIN_Y = -300_000.0, 6_400_000.0
T = Affine(100.0, 0.0, ORIGIN_X, 0.0, -100.0, ORIGIN_Y)
SHAPE = (60, 60)
CX = ORIGIN_X + 30 * 100.0  # centre of the grid, on a cell corner
CY = ORIGIN_Y - 30 * 100.0
NODATA = 65535


def full(value):
    return np.full(SHAPE, value, dtype=np.uint16)


def left_half(value_left, value_right):
    a = np.full(SHAPE, value_right, dtype=np.uint16)
    a[:, :30] = value_left  # columns left of x = CX
    return a


# --- epoch provenance (per the R2023A data package, shipped in-tile) -------


class TestEpochProvenance:
    def test_all_epochs_covered(self):
        assert EPOCHS == [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
        for e in EPOCHS:
            assert epoch_provenance(e)["tag"] in {"sensor-anchored", "interpolated", "projected"}

    @pytest.mark.parametrize(
        "epoch,sensor",
        [(1975, "MSS"), (1990, "TM"), (2000, "ETM+")],
    )
    def test_sensor_anchored(self, epoch, sensor):
        p = epoch_provenance(epoch)
        assert p["tag"] == "sensor-anchored"
        assert p["anchor_sensor"] == sensor

    @pytest.mark.parametrize("epoch", [1980, 1985, 1995, 2005, 2010, 2015])
    def test_interpolated(self, epoch):
        p = epoch_provenance(epoch)
        assert p["tag"] == "interpolated"
        assert p["anchor_sensor"] is None

    @pytest.mark.parametrize("epoch", [2020, 2025])
    def test_projected_after_last_observation(self, epoch):
        # last observation is the 2018 S2 composite; everything later is
        # extrapolated, per the data package
        p = epoch_provenance(epoch)
        assert p["tag"] == "projected"

    def test_nearest_observation_recorded(self):
        # 2015 sits between the OLI 2014 and S2 2018 observations; the
        # nearest is recorded so the task-5 alignment config can decide
        # how observations map to shipped epochs
        p = epoch_provenance(2015)
        assert (p["nearest_obs_year"], p["nearest_obs_sensor"]) == (2014, "OLI")
        assert p["obs_offset_years"] == 1
        p = epoch_provenance(2020)
        assert (p["nearest_obs_year"], p["nearest_obs_sensor"]) == (2018, "S2")


# --- ring geometry and CRS -------------------------------------------------


class TestRingGeometry:
    def test_ring_area_preserved_in_mollweide(self):
        # Mollweide is equal-area: the projected ring polygon's area must
        # match pi r^2 closely (small buffer-discretisation error only)
        for r in (500, 2000, 10000):
            poly = ring_polygon(51.5, -2.6, r)
            assert poly.area == pytest.approx(math.pi * r * r, rel=2e-3)

    def test_crs_round_trip(self):
        fwd = Transformer.from_crs("EPSG:4326", "ESRI:54009", always_xy=True)
        inv = Transformer.from_crs("ESRI:54009", "EPSG:4326", always_xy=True)
        lon, lat = -2.952, 51.364  # Weston-super-Mare 01298
        x, y = fwd.transform(lon, lat)
        lon2, lat2 = inv.transform(x, y)
        assert lon2 == pytest.approx(lon, abs=1e-9)
        assert lat2 == pytest.approx(lat, abs=1e-9)


# --- ring stats on synthetic rasters ---------------------------------------


class TestRingStats:
    def poly(self, r=1000.0):
        # a true circle in projected coordinates, centred on a cell corner
        from shapely.geometry import Point

        return Point(CX, CY).buffer(r, quad_segs=256)

    def test_fully_built_land_ring(self):
        s = ring_stats(full(10000), full(10000), T, self.poly())
        assert s["reason"] is None
        assert s["builtup_fraction"] == pytest.approx(1.0, abs=1e-6)
        assert s["land_fraction"] == pytest.approx(1.0, abs=1e-6)
        assert s["ring_area_m2"] == pytest.approx(math.pi * 1000 * 1000, rel=2e-3)

    def test_half_plane_split_is_area_weighted(self):
        # built on the left half-plane only; ring centred on the divide
        s = ring_stats(left_half(10000, 0), full(10000), T, self.poly())
        assert s["builtup_fraction"] == pytest.approx(0.5, abs=1e-3)

    def test_partial_pixel_weighted_by_intersected_area(self):
        # spec scenario: a pixel partly inside the ring contributes by its
        # intersected area. Ring of radius 80 m centred on the corner
        # shared by four cells (so it stays inside them), exactly one of
        # which is built: the built quadrant is exactly a quarter of the
        # ring.
        built = full(0)
        built[29, 30] = 10000  # cell NE of the centre corner
        s = ring_stats(built, full(10000), T, self.poly(80.0))
        assert s["builtup_fraction"] == pytest.approx(0.25, abs=1e-3)

    def test_coastal_ring_uses_land_denominator(self):
        # spec scenario: half the ring is sea; fraction computed over the
        # land half and the land fraction stored alongside
        land = left_half(10000, 0)
        built = left_half(10000, 0)
        s = ring_stats(built, land, T, self.poly())
        assert s["land_fraction"] == pytest.approx(0.5, abs=1e-3)
        assert s["builtup_fraction"] == pytest.approx(1.0, abs=1e-3)

    def test_partial_land_cells_weight_denominator(self):
        # coastal cells with fractional land (e.g. 5000 m^2) halve the
        # denominator rather than being counted as full land
        s = ring_stats(full(2500), full(5000), T, self.poly())
        assert s["land_fraction"] == pytest.approx(0.5, abs=1e-6)
        assert s["builtup_fraction"] == pytest.approx(0.5, abs=1e-6)

    def test_all_sea_ring_is_null_with_reason(self):
        s = ring_stats(full(0), full(0), T, self.poly())
        assert s["builtup_fraction"] is None
        assert s["reason"] == "no-land-in-ring"

    def test_builtup_missing_over_real_land_is_null_with_reason(self):
        # built-up nodata where GHS-LAND says land exists is a genuine
        # data gap, never silently zeroed
        built = full(10000)
        built[25:35, 25:35] = NODATA
        s = ring_stats(built, full(10000), T, self.poly())
        assert s["builtup_fraction"] is None
        assert s["reason"] == "no-coverage"

    def test_offshore_nodata_is_sea_not_a_gap(self):
        # GHSL only processes land + a coastal buffer: far-offshore ocean
        # is nodata in BOTH rasters (verified at North Rona). Such cells
        # are sea — the ring behaves like the coastal scenario, not a gap.
        built = left_half(5000, NODATA)
        land = left_half(10000, NODATA)
        s = ring_stats(built, land, T, self.poly())
        assert s["reason"] is None
        assert s["land_fraction"] == pytest.approx(0.5, abs=1e-3)
        assert s["builtup_fraction"] == pytest.approx(0.5, abs=1e-3)

    def test_ring_outside_window_is_null_with_reason(self):
        # window does not cover the ring at all
        poly = self.poly().buffer(0)  # copy
        from shapely import affinity

        far = affinity.translate(poly, xoff=1e6)
        s = ring_stats(full(10000), full(10000), T, far)
        assert s["builtup_fraction"] is None
        assert s["reason"] == "no-coverage"


# --- SMOD sampling ---------------------------------------------------------


class TestSmodSampling:
    def test_raw_class_code_preserved(self):
        # spec: SMOD stores the published class code uninterpreted — 13
        # stays 13, never grouped to urban/rural at ingest
        a = np.full((10, 10), 10, dtype=np.int16)
        a[4, 5] = 13
        t = Affine(1000.0, 0.0, 0.0, 0.0, -1000.0, 0.0)
        # point inside cell row 4, col 5
        assert sample_raster_class(a, t, x=5500.0, y=-4500.0, nodata=-200) == 13

    def test_nodata_returns_none(self):
        a = np.full((10, 10), -200, dtype=np.int16)
        t = Affine(1000.0, 0.0, 0.0, 0.0, -1000.0, 0.0)
        assert sample_raster_class(a, t, x=500.0, y=-500.0, nodata=-200) is None


# --- integration against the real tiles ------------------------------------


@pytest.mark.skipif(not (DATA / "built-s").is_dir(), reason="GHSL tiles not downloaded")
class TestRealTiles:
    def test_known_landmark_urban_vs_rural(self):
        # CRS + mosaic end-to-end: central London must read overwhelmingly
        # more built-up than Rannoch Moor in the 2020 epoch
        from ukweather.ghsl import GhslData

        g = GhslData(DATA)
        london = g.extract_station("test-london", 51.5074, -0.1278, epochs=[2020])
        moor = g.extract_station("test-moor", 56.63, -4.77, epochs=[2020])
        l500 = next(r for r in london if r["ring_m"] == 500)
        m500 = next(r for r in moor if r["ring_m"] == 500)
        assert l500["builtup_fraction"] > 0.3
        assert m500["builtup_fraction"] < 0.02
        assert l500["builtup_fraction"] > 10 * max(m500["builtup_fraction"], 1e-6)

    def test_provenance_columns_present(self):
        from ukweather.ghsl import GhslData

        g = GhslData(DATA)
        rows = g.extract_station("test-london", 51.5074, -0.1278, epochs=[1975])
        r = rows[0]
        assert r["product"] == "GHS_BUILT_S"
        assert r["release"] == "R2023A"
        assert r["version"] == "V1_0"
        assert "R3_C19" in r["tile_ids"]  # London: Mollweide y ~6.06e6, x ~-8.9e3
        assert len(r["tile_checksums"].split(";")[0]) == 64
        assert r["provenance_tag"] == "sensor-anchored"
        assert r["anchor_sensor"] == "MSS"
