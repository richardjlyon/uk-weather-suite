"""Tests for ukweather.stations — station-history table from MIDAS capability files.

Fixtures are cut verbatim from real MIDAS Open dv-202507 files under
tests/fixtures/. Spec: openspec/changes/add-station-classifier/specs/station-history.
"""

from pathlib import Path

import pytest

from ukweather.stations import (
    Capability,
    annual_header,
    aws_transition_year,
    build_station_history,
    coordinate_precision_m,
    find_relocation_clusters,
    parse_capability,
    segment_station,
    station_data_years,
    survivorship_by_decade,
)

FIXTURES = Path(__file__).parent / "fixtures"
CAP = FIXTURES / "capability"


def cap_path(fragment: str) -> Path:
    matches = [p for p in CAP.iterdir() if fragment in p.name]
    assert len(matches) == 1, f"{fragment}: {matches}"
    return matches[0]


# --- parsing ---------------------------------------------------------------


class TestParseCapability:
    def test_grangemouth_globals(self):
        cap = parse_capability(cap_path("00962_grangemouth"))
        assert cap.src_id == "00962"
        assert cap.name == "grangemouth"
        assert cap.county == "stirling-in-central-region"
        assert cap.lat == pytest.approx(56.018)
        assert cap.lon == pytest.approx(-3.72)
        assert cap.height_m == 4.0
        assert cap.first_valid_year == 1972
        assert cap.last_valid_year == 1978
        assert cap.collection_version == "dataset-version-202507"

    def test_grangemouth_id_rows(self):
        cap = parse_capability(cap_path("00962_grangemouth"))
        assert len(cap.rows) == 1
        row = cap.rows[0]
        assert (row.id, row.id_type, row.met_domain_name) == ("6296", "DCNN", "DLY3208")
        assert (row.first_year, row.last_year) == (1972, 1978)

    def test_rothamsted_multiple_rows(self):
        cap = parse_capability(cap_path("00471_rothamsted"))
        domains = {r.met_domain_name for r in cap.rows}
        assert domains == {"SYNOP", "HSUN3445", "DLY3208", "AWSHRLY"}

    def test_decimal_places_recorded(self):
        cap = parse_capability(cap_path("18974_tiree"))
        # location,G,56.5,-6.881
        assert cap.lat_dp == 1
        assert cap.lon_dp == 3

    def test_annual_header(self):
        p = (
            FIXTURES
            / "tree/avon/01312_bath/qc-version-1"
            / "midas-open_uk-hourly-weather-obs_dv-202507_avon_01312_bath_qcv-1_1904.csv"
        )
        hdr = annual_header(p)
        assert hdr["src_id"] == "01312"
        assert hdr["lat"] == pytest.approx(51.386)
        assert hdr["lon"] == pytest.approx(-2.355)
        assert hdr["height_m"] == 20.0


# --- coordinate precision --------------------------------------------------


class TestCoordinatePrecision:
    def test_three_dp_is_fine(self):
        # 3 dp lat: half grid step ~55.7 m -> not coarser than 100 m
        p = coordinate_precision_m(lat=51.386, lat_dp=3, lon_dp=3)
        assert p < 100

    def test_one_dp_lat_is_coarse(self):
        # Tiree: lat to 0.1 degrees -> ~5.6 km half step
        p = coordinate_precision_m(lat=56.5, lat_dp=1, lon_dp=3)
        assert p > 1000

    def test_two_dp_is_coarse(self):
        # 2 dp -> ~557 m half step: coarser than 100 m, flagged per spec
        p = coordinate_precision_m(lat=51.0, lat_dp=2, lon_dp=2)
        assert p > 100

    def test_lon_scaled_by_latitude(self):
        # at 60 N a lon degree is half a lat degree; lon-limited precision
        p_north = coordinate_precision_m(lat=60.0, lat_dp=3, lon_dp=2)
        p_south = coordinate_precision_m(lat=50.0, lat_dp=3, lon_dp=2)
        assert p_north < p_south  # cos(60) < cos(50) shrinks the lon step


# --- data years and gaps ---------------------------------------------------


class TestStationDataYears:
    def test_years_from_annual_filenames(self):
        d = FIXTURES / "tree/avon/01312_bath"
        assert station_data_years(d) == [1904, 1905, 1913, 1916, 1958]


# --- segmentation ----------------------------------------------------------


class TestSegmentation:
    def test_contiguous_years_single_segment(self):
        segs = segment_station(years=[1972, 1973, 1974], aws_from=None)
        assert len(segs) == 1
        assert (segs[0].start_year, segs[0].end_year) == (1972, 1974)
        assert segs[0].break_reason == "open"

    def test_gap_breaks_segment_and_is_explicit(self):
        # spec: no invented continuity — the gap is explicit, never bridged
        segs = segment_station(years=[1904, 1905, 1913, 1916, 1917, 1918], aws_from=None)
        starts = [(s.start_year, s.end_year, s.break_reason) for s in segs]
        assert starts == [
            (1904, 1905, "open"),
            (1913, 1913, "resumed-after-gap"),
            (1916, 1918, "resumed-after-gap"),
        ]

    def test_aws_transition_breaks_segment(self):
        # spec: AWS transition breaks the segment; within-segment analysis
        # never spans it
        segs = segment_station(years=list(range(1990, 2005)), aws_from=1999)
        assert [(s.start_year, s.end_year) for s in segs] == [
            (1990, 1998),
            (1999, 2004),
        ]
        assert segs[1].break_reason == "aws-transition"
        assert segs[0].era == "manual"
        assert segs[1].era == "aws"

    def test_aws_from_start_no_break(self):
        segs = segment_station(years=[2000, 2001], aws_from=2000)
        assert len(segs) == 1
        assert segs[0].era == "aws"

    def test_no_instrument_info_era_unknown(self):
        segs = segment_station(years=[1972, 1973], aws_from=None)
        assert segs[0].era == "unknown"


# --- instrument audit ------------------------------------------------------


class TestAwsTransition:
    def test_rothamsted_aws_from_1999(self):
        cap = parse_capability(cap_path("00471_rothamsted"))
        assert aws_transition_year(cap) == 1999

    def test_grangemouth_unknown(self):
        cap = parse_capability(cap_path("00962_grangemouth"))
        assert aws_transition_year(cap) is None


# --- move semantics: co-located id clusters --------------------------------


class TestRelocationClusters:
    def weston_caps(self) -> list[Capability]:
        return [
            parse_capability(cap_path(f))
            for f in [
                "01298_weston-super-mare_",
                "01299_weston-super-mare-no-2",
                "30273_weston-super-mare-worle",
                "17342_weston-super-mare-uphill",
                "01312_bath",
                "00962_grangemouth",
            ]
        ]

    def test_weston_ids_form_one_cluster(self):
        clusters = find_relocation_clusters(self.weston_caps())
        weston = [c for c in clusters if any("weston" in s for s in c.name_stems)]
        assert len(weston) == 1
        assert set(weston[0].members) == {"01298", "01299", "30273", "17342"}

    def test_unrelated_stations_not_clustered(self):
        clusters = find_relocation_clusters(self.weston_caps())
        clustered = {m for c in clusters for m in c.members}
        assert "01312" not in clustered  # bath
        assert "00962" not in clustered  # grangemouth


# --- survivorship ----------------------------------------------------------


class TestSurvivorship:
    def test_counts_by_opening_decade(self):
        stations = [
            {"src_id": "a", "first_year": 1904, "last_year": 1958},
            {"src_id": "b", "first_year": 1904, "last_year": 2024},
            {"src_id": "c", "first_year": 1972, "last_year": 1978},
        ]
        s = survivorship_by_decade(stations, open_threshold_year=2023)
        assert s[1900] == {"opened": 2, "still_open": 1, "closed": 1}
        assert s[1970] == {"opened": 1, "still_open": 0, "closed": 1}


# --- integration: build from a raw tree ------------------------------------


class TestBuildStationHistory:
    def test_bath_fixture_tree(self):
        rows = build_station_history(FIXTURES / "tree")
        assert {r["src_id"] for r in rows} == {"01312"}
        segs = [r for r in rows if r["src_id"] == "01312"]
        # fixture tree holds annual files for 1904, 1905, 1913, 1916, 1958
        # only, so 1916 and 1958 are themselves gap-separated
        assert [(r["start_year"], r["end_year"]) for r in segs] == [
            (1904, 1905),
            (1913, 1913),
            (1916, 1916),
            (1958, 1958),
        ]
        r = segs[0]
        assert r["name"] == "bath"
        assert r["county"] == "avon"
        assert r["lat"] == pytest.approx(51.386)
        assert r["height_m"] == 20.0
        assert r["instrument_history_unknown"] is True
        assert r["coarse_location_flag"] is False
        assert r["coordinate_moved_within_id"] is False
        assert r["collection_version"] == "dataset-version-202507"
