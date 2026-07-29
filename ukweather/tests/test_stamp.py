"""Tests for ukweather.stamp — 1930s Land Utilisation Survey screen
(spec: first-principles-validation, LUS baseline screen requirement).

Synthetic tests use hand-made square parcels with exactly known areas;
fixture tests use real features harvested from the EA OGC API for a
known-urban (London St James's Park) and known-rural (Eskdalemuir)
station, cut to tests/fixtures/stamp/.
"""

import json
import math
from pathlib import Path

import pytest

from ukweather.stamp import (
    GRIDCODE_CLASSES,
    classify_ring,
    ring_row,
)

FIXTURES = Path(__file__).parent / "fixtures" / "stamp"


def square_feature(gridcode: int, lon0, lat0, dlon, dlat):
    """A lon/lat-aligned rectangle as a GeoJSON feature."""
    return {
        "type": "Feature",
        "properties": {"gridcode": gridcode},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon0, lat0], [lon0 + dlon, lat0],
                [lon0 + dlon, lat0 + dlat], [lon0, lat0 + dlat], [lon0, lat0],
            ]],
        },
    }


LAT, LON = 52.0, -1.5  # arbitrary inland point


class TestLegend:
    def test_gridcodes_match_ea_wms_style(self):
        assert GRIDCODE_CLASSES == {
            1: "rough-grazing", 2: "urban", 3: "water", 4: "arable",
            5: "suburban", 6: "grassland", 7: "woodland", 8: "orchard",
        }


class TestClassifyRing:
    def big(self, gridcode, half_deg=0.5):
        # a parcel far larger than any ring, centred on the station
        return square_feature(gridcode, LON - half_deg, LAT - half_deg,
                              2 * half_deg, 2 * half_deg)

    def test_single_class_covers_ring(self):
        c = classify_ring([self.big(4)], LAT, LON, 2000)
        assert c["dominant_class"] == "arable"
        assert c["coverage_fraction"] == pytest.approx(1.0, abs=1e-3)
        assert c["class_fractions"]["arable"] == pytest.approx(1.0, abs=1e-3)

    def test_dominant_by_intersected_area(self):
        # urban parcel covers the east half of the ring, arable the west
        # half plus everything beyond: dominant inside the ring is a tie
        # broken by area — make urban slightly larger by shifting the
        # boundary west of centre
        west = square_feature(4, LON - 0.5, LAT - 0.5, 0.495, 1.0)
        east = square_feature(2, LON - 0.005, LAT - 0.5, 0.505, 1.0)
        c = classify_ring([west, east], LAT, LON, 2000)
        assert c["dominant_class"] == "urban"
        assert c["class_fractions"]["urban"] > 0.5
        assert c["class_fractions"]["arable"] < 0.5
        assert c["coverage_fraction"] == pytest.approx(1.0, abs=1e-3)

    def test_partial_coverage_recorded(self):
        # survey covers only the west half of the ring
        west_only = square_feature(6, LON - 0.5, LAT - 0.5, 0.5, 1.0)
        c = classify_ring([west_only], LAT, LON, 2000)
        assert c["coverage_fraction"] == pytest.approx(0.5, abs=2e-3)
        assert c["dominant_class"] == "grassland"

    def test_no_features_is_no_coverage_not_a_class(self):
        # spec: a station with no survey coverage is flagged, never
        # silently classified
        c = classify_ring([], LAT, LON, 2000)
        assert c["coverage_fraction"] == 0.0
        assert c["dominant_class"] is None


class TestRingRow:
    def test_rural_screen_true_for_rural_class(self):
        big = square_feature(1, LON - 0.5, LAT - 0.5, 1.0, 1.0)
        r = ring_row("x", LAT, LON, 500, [big])
        assert r["dominant_class"] == "rough-grazing"
        assert r["rural_screen"] is True
        assert r["no_stamp_coverage"] is False

    @pytest.mark.parametrize("code,name", [(2, "urban"), (5, "suburban")])
    def test_rural_screen_false_for_urban_suburban(self, code, name):
        big = square_feature(code, LON - 0.5, LAT - 0.5, 1.0, 1.0)
        r = ring_row("x", LAT, LON, 500, [big])
        assert r["dominant_class"] == name
        assert r["rural_screen"] is False

    def test_uncovered_station_flagged_never_classified(self):
        r = ring_row("x", 57.5, -4.5, 500, [])  # north of the EA extent
        assert r["no_stamp_coverage"] is True
        assert r["dominant_class"] is None
        assert r["rural_screen"] is None


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="stamp fixtures not cut yet")
class TestRealFixtures:
    """TDD on a known-urban and a known-rural 1930s site (task 4.3)."""

    def load(self, name):
        return json.loads((FIXTURES / name).read_text())["features"]

    def test_st_jamess_park_reads_urban_or_suburban(self):
        feats = self.load("00697_st-jamess-park.geojson")
        r = ring_row("00697", 51.504, -0.129, 2000, feats)
        assert r["dominant_class"] in {"urban", "suburban"}
        assert r["rural_screen"] is False
        assert r["no_stamp_coverage"] is False

    def test_princetown_dartmoor_reads_rural(self):
        feats = self.load("01350_princetown-prison.geojson")
        r = ring_row("01350", 50.549, -4.001, 2000, feats)
        assert r["dominant_class"] not in {None, "urban", "suburban"}
        assert r["rural_screen"] is True

    def test_eskdalemuir_is_a_real_no_coverage_case(self):
        # the EA digitisation does not cover Dumfriesshire (verified by
        # bbox counts: Dumfries and Eskdalemuir return zero features while
        # Jedburgh and Berwick are covered) — the station must be flagged,
        # never silently classified
        feats = self.load("01023_eskdalemuir.geojson")
        assert feats == []
        r = ring_row("01023", 55.312, -3.207, 2000, feats)
        assert r["no_stamp_coverage"] is True
        assert r["dominant_class"] is None
        assert r["rural_screen"] is None
