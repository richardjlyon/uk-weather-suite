"""Tests for ukweather.airfields — OSM aeroway airfield screen
(spec: first-principles-validation, Airfield screen requirement).

The screen is ONE-WAY: a hit flags a station ineligible for the
still-rural control cohort; absence never certifies anything (OSM's
coverage of disused wartime airfields is uneven).
"""

import json
from pathlib import Path

import pytest

from ukweather.airfields import (
    element_geometries,
    ring_hits,
    screen_station,
)

FIXTURES = Path(__file__).parent / "fixtures" / "airfields"

LAT, LON = 52.0, -1.5


def node(id, lat, lon, tags):
    return {"type": "node", "id": id, "lat": lat, "lon": lon, "tags": tags}


def way(id, coords, tags):
    return {
        "type": "way",
        "id": id,
        "geometry": [{"lat": la, "lon": lo} for la, lo in coords],
        "tags": tags,
    }


class TestElementGeometries:
    def test_node_becomes_point(self):
        feats = element_geometries([node(1, LAT, LON, {"aeroway": "aerodrome"})])
        assert len(feats) == 1
        fid, kind, geom = feats[0]
        assert fid == "node/1"
        assert kind == "aerodrome"
        assert geom.geom_type == "Point"

    def test_open_way_becomes_linestring(self):
        feats = element_geometries(
            [way(2, [(LAT, LON), (LAT + 0.01, LON)], {"aeroway": "runway"})]
        )
        assert feats[0][2].geom_type == "LineString"
        assert feats[0][1] == "runway"

    def test_closed_way_becomes_polygon(self):
        coords = [(LAT, LON), (LAT + 0.01, LON), (LAT + 0.01, LON + 0.01),
                  (LAT, LON + 0.01), (LAT, LON)]
        feats = element_geometries([way(3, coords, {"aeroway": "aerodrome"})])
        assert feats[0][2].geom_type == "Polygon"

    def test_disused_and_abandoned_variants_kept_with_prefix(self):
        feats = element_geometries(
            [
                node(4, LAT, LON, {"disused:aeroway": "aerodrome"}),
                node(5, LAT, LON, {"abandoned:aeroway": "runway"}),
            ]
        )
        kinds = {f[1] for f in feats}
        assert kinds == {"disused:aerodrome", "abandoned:runway"}

    def test_relation_outer_ways_polygonized(self):
        # an aerodrome boundary split into two open member ways that close
        # as a ring together
        rel = {
            "type": "relation",
            "id": 6,
            "tags": {"aeroway": "aerodrome", "type": "multipolygon"},
            "members": [
                {
                    "type": "way",
                    "role": "outer",
                    "geometry": [
                        {"lat": LAT, "lon": LON},
                        {"lat": LAT + 0.01, "lon": LON},
                        {"lat": LAT + 0.01, "lon": LON + 0.01},
                    ],
                },
                {
                    "type": "way",
                    "role": "outer",
                    "geometry": [
                        {"lat": LAT + 0.01, "lon": LON + 0.01},
                        {"lat": LAT, "lon": LON + 0.01},
                        {"lat": LAT, "lon": LON},
                    ],
                },
            ],
        }
        feats = element_geometries([rel])
        assert feats[0][0] == "relation/6"
        assert feats[0][2].geom_type in ("Polygon", "MultiPolygon")

    def test_untagged_or_irrelevant_elements_skipped(self):
        feats = element_geometries(
            [node(7, LAT, LON, {"amenity": "cafe"}), node(8, LAT, LON, {})]
        )
        assert feats == []


class TestRingHits:
    def test_runway_1km_away_hits_2km_and_10km_not_500m(self):
        # a runway ~1 km east of the station
        feats = element_geometries(
            [way(10, [(LAT, LON + 0.015), (LAT, LON + 0.03)], {"aeroway": "runway"})]
        )
        hits = ring_hits(LAT, LON, feats)
        assert hits[500] == []
        assert [h[0] for h in hits[2000]] == ["way/10"]
        assert [h[0] for h in hits[10000]] == ["way/10"]

    def test_station_inside_aerodrome_polygon_hits_all_rings(self):
        coords = [(LAT - 0.02, LON - 0.03), (LAT + 0.02, LON - 0.03),
                  (LAT + 0.02, LON + 0.03), (LAT - 0.02, LON + 0.03),
                  (LAT - 0.02, LON - 0.03)]
        feats = element_geometries([way(11, coords, {"aeroway": "aerodrome"})])
        hits = ring_hits(LAT, LON, feats)
        for r in (500, 2000, 10000):
            assert [h[0] for h in hits[r]] == ["way/11"], f"ring {r}"

    def test_no_features_no_hits(self):
        hits = ring_hits(LAT, LON, [])
        assert all(hits[r] == [] for r in (500, 2000, 10000))


class TestScreenStation:
    def test_flagged_with_ring_and_feature_detail(self):
        feats = element_geometries(
            [way(12, [(LAT, LON + 0.015), (LAT, LON + 0.03)],
                 {"aeroway": "runway"})]
        )
        rows = screen_station("00042", LAT, LON, feats, retrieved="2026-07-29")
        assert len(rows) == 3  # one per ring
        by_ring = {r["ring_m"]: r for r in rows}
        assert by_ring[500]["hit"] is False
        assert by_ring[2000]["hit"] is True
        assert by_ring[2000]["feature_ids"] == "way/12"
        assert by_ring[2000]["feature_kinds"] == "runway"
        # the station-level flag: any ring hit
        assert all(r["airfield_flag"] is True for r in rows)
        assert rows[0]["source"].startswith("OpenStreetMap")
        assert rows[0]["licence"] == "ODbL 1.0"

    def test_absence_flags_nothing_and_certifies_nothing(self):
        # one-way semantics: absence yields hit=False and flag=False, and
        # the screen_semantics column states that absence certifies nothing
        rows = screen_station("00043", LAT, LON, [], retrieved="2026-07-29")
        assert all(r["hit"] is False and r["airfield_flag"] is False for r in rows)
        assert "absence certifies nothing" in rows[0]["screen_semantics"]


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="airfield fixtures not cut yet")
class TestRealFixtures:
    def load(self, name):
        return json.loads((FIXTURES / name).read_text())["elements"]

    def test_known_aerodrome_station_flags(self):
        # cut from the real Overpass pull around a MIDAS station sited on an
        # active aerodrome; must flag at the 500 m ring
        d = json.loads((FIXTURES / "aerodrome-station.json").read_text())
        feats = element_geometries(d["elements"])
        rows = screen_station(d["src_id"], d["lat"], d["lon"], feats,
                              retrieved="2026-07-29")
        assert {r["ring_m"]: r["hit"] for r in rows}[500] is True

    def test_eskdalemuir_does_not_flag(self):
        d = json.loads((FIXTURES / "eskdalemuir.json").read_text())
        feats = element_geometries(d["elements"])
        rows = screen_station(d["src_id"], d["lat"], d["lon"], feats,
                              retrieved="2026-07-29")
        assert all(r["hit"] is False for r in rows)
