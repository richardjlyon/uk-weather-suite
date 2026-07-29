"""Tests for ukweather.census — 10 km ring census density, 1981+
(spec: first-principles-validation, Census population density, as
amended 2026-07-29).

Binding behaviours under test: the 10 km-only refusal (fine rings would
smear), area-weighted apportionment, the pre-1981 abstention, one-way
semantics carried in the data, and nation reason codes for uncovered
stations.
"""

import math

import pytest
from pyproj import Transformer
from shapely.geometry import Point, box

from ukweather.census import (
    RING_M,
    YEARS,
    apportion_population,
    build_station_rows,
    ring_bng,
)

LAT, LON = 52.0, -1.5
_TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
CX, CY = _TO_BNG.transform(LON, LAT)
RING_AREA = math.pi * RING_M**2


class TestRefusal:
    @pytest.mark.parametrize("bad", [500, 2000])
    def test_fine_rings_refused(self, bad):
        # spec scenario: parish/ward polygons are coarser than these rings
        # and would smear — the system refuses, it does not warn
        with pytest.raises(ValueError, match="smear"):
            apportion_population([], LAT, LON, ring_m=bad)

    def test_10km_accepted(self):
        out = apportion_population([], LAT, LON, ring_m=10000)
        assert out["population_in_ring"] == 0.0


class TestApportionment:
    def test_polygon_fully_inside_counts_fully(self):
        poly = box(CX - 1000, CY - 1000, CX + 1000, CY + 1000)
        out = apportion_population([("U1", poly, 100.0)], LAT, LON, RING_M)
        assert out["population_in_ring"] == pytest.approx(100.0, rel=1e-3)
        assert out["n_units"] == 1

    def test_polygon_half_inside_counts_half(self):
        # a unit straddling the ring edge: square centred on the ring
        # boundary due east, small enough that the arc is near-straight
        edge_x = CX + RING_M
        poly = box(edge_x - 500, CY - 500, edge_x + 500, CY + 500)
        out = apportion_population([("U2", poly, 80.0)], LAT, LON, RING_M)
        assert out["population_in_ring"] == pytest.approx(40.0, rel=0.02)

    def test_covered_area_accumulates(self):
        poly = box(CX - 1000, CY - 1000, CX + 1000, CY + 1000)
        out = apportion_population([("U1", poly, 10.0)], LAT, LON, RING_M)
        assert out["covered_area_m2"] == pytest.approx(4_000_000, rel=1e-3)


class TestBuildStationRows:
    def units_covering_ring(self, pop=1000.0):
        # one big unit covering the whole ring
        big = box(CX - 2 * RING_M, CY - 2 * RING_M, CX + 2 * RING_M, CY + 2 * RING_M)
        return [("BIG", big, pop)]

    def land_m2(self):
        return RING_AREA  # fully-land ring for tests

    def test_rows_for_all_years_plus_abstention(self):
        per_year = {y: self.units_covering_ring() for y in YEARS}
        rows = build_station_rows(
            "00042", LAT, LON, "oxfordshire", per_year, self.land_m2(), "2026-07-29"
        )
        years = [r["census_year"] for r in rows]
        assert years == [None] + sorted(YEARS)  # abstention row first
        pre = rows[0]
        assert pre["abstention"] is True
        assert pre["reason"] == "no-open-census-pre-1981"
        assert pre["density_per_km2"] is None

    def test_density_over_land_area(self):
        # a unit fully inside the ring contributes ALL its population; a
        # surrounding zero-population unit provides the ring coverage
        inner = box(CX - 1000, CY - 1000, CX + 1000, CY + 1000)
        outer = box(CX - 2 * RING_M, CY - 2 * RING_M, CX + 2 * RING_M, CY + 2 * RING_M)
        per_year = {y: [("IN", inner, 3141.5926), ("OUT", outer, 0.0)] for y in YEARS}
        rows = build_station_rows(
            "00042", LAT, LON, "kent", per_year, self.land_m2(), "2026-07-29"
        )
        r = next(r for r in rows if r["census_year"] == 2011)
        # ring covers pi*100 km^2; population chosen to give 10 per km^2
        assert r["density_per_km2"] == pytest.approx(10.0, rel=1e-2)
        assert r["coverage_fraction"] == pytest.approx(1.0, abs=0.01)
        assert r["reason"] is None

    def test_one_way_semantics_in_every_row(self):
        per_year = {y: self.units_covering_ring() for y in YEARS}
        rows = build_station_rows(
            "00042", LAT, LON, "kent", per_year, self.land_m2(), "2026-07-29"
        )
        assert all("never disputes" in r["one_way_semantics"] for r in rows)

    def test_growth_delta_computed_between_available_years(self):
        per_year = {y: self.units_covering_ring(pop=1000.0 * (i + 1))
                    for i, y in enumerate(sorted(YEARS))}
        rows = build_station_rows(
            "00042", LAT, LON, "kent", per_year, self.land_m2(), "2026-07-29"
        )
        r91 = next(r for r in rows if r["census_year"] == 1991)
        assert r91["density_delta_prev"] == pytest.approx(
            r91["density_per_km2"] / 2, rel=1e-3
        )

    def test_insufficient_coverage_nulled_with_reason(self):
        # units cover only ~half the ring's land: density would be biased
        # low, so it is nulled with a recorded reason, never silently kept
        west_only = box(CX - 2 * RING_M, CY - 2 * RING_M, CX, CY + 2 * RING_M)
        per_year = {y: [("W", west_only, 500.0)] for y in YEARS}
        rows = build_station_rows(
            "00042", LAT, LON, "kent", per_year, self.land_m2(), "2026-07-29"
        )
        r = next(r for r in rows if r["census_year"] == 2011)
        assert r["density_per_km2"] is None
        assert r["reason"] == "insufficient-boundary-coverage"
        assert r["coverage_fraction"] == pytest.approx(0.5, abs=0.02)

    def test_scotland_station_flagged_not_silently_null(self):
        rows = build_station_rows(
            "01023", 55.312, -3.207, "dumfriesshire", {y: [] for y in YEARS},
            self.land_m2(), "2026-07-29"
        )
        r = next(r for r in rows if r["census_year"] == 2011)
        assert r["density_per_km2"] is None
        assert r["reason"] == "no-census-boundaries-scotland"

    def test_ni_station_flagged_not_silently_null(self):
        rows = build_station_rows(
            "01487", 54.17, -6.34, "down", {y: [] for y in YEARS},
            self.land_m2(), "2026-07-29"
        )
        r = next(r for r in rows if r["census_year"] == 1981)
        assert r["reason"] == "no-census-boundaries-northern-ireland"


class TestInvalidGeometry:
    def test_bowtie_polygon_does_not_crash_apportionment(self):
        # generalised boundaries occasionally contain self-intersecting
        # rings; they must be repaired, not crash the build
        from shapely.geometry import Polygon

        bowtie = Polygon([
            (CX - 1000, CY - 1000), (CX + 1000, CY + 1000),
            (CX + 1000, CY - 1000), (CX - 1000, CY + 1000),
            (CX - 1000, CY - 1000),
        ])
        from ukweather.census import prepare_geometry
        fixed = prepare_geometry(bowtie)
        out = apportion_population([("BT", fixed, 100.0)], LAT, LON, RING_M)
        assert out["population_in_ring"] == pytest.approx(100.0, rel=1e-2)


class TestCodeTranslation:
    def test_boundary_codes_translated_through_lookup(self):
        # 1991: boundary files carry census-style codes (02ATGC) while
        # NOMIS counts key on OPCS-style codes (01AEGC); the names-and-
        # codes lookup bridges them
        from ukweather.census import build_units

        features = [{
            "properties": {"WD91CDO": "02ATGC", "WD91NM": "Stonebridge"},
            "geometry": {"type": "Polygon", "coordinates": [[
                [-1.5, 52.0], [-1.49, 52.0], [-1.49, 52.01], [-1.5, 52.01], [-1.5, 52.0]
            ]]},
        }]
        counts = {"01AEGC": 5000.0}
        units, unmatched = build_units(features, counts,
                                       translate={"02ATGC": "01AEGC"})
        assert unmatched == 0
        assert units[0][0] == "01AEGC"
        assert units[0][2] == 5000.0
