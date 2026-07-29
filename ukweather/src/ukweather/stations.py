"""Station-history table from MIDAS Open capability files.

Builds the per-station segment timeline required by the station-history
capability (openspec/changes/add-station-classifier/specs/station-history):
segment breaks on any coordinate, altitude or instrument-era change,
explicit gaps, coordinate precision, move-semantics verification and
survivorship counts.

Empirical ground (dv-202507, verified across all 1,537 stations and
34,238 annual files): a src_id carries exactly one location/height in the
capability file and in every annual file — MIDAS Open represents
relocation as a NEW src_id, never as a same-id amendment. The builder
still cross-checks every annual header against the capability file and
records `coordinate_moved_within_id` so a future dataset version cannot
silently break that assumption.

Coordinate precision: MIDAS states locations to a fixed number of decimal
places. Precision is taken as the worst-axis half grid step (the maximum
quantisation error): 3 dp ≈ 56 m, 2 dp ≈ 560 m, 1 dp ≈ 5.6 km in
latitude. Stations coarser than 100 m carry `coarse_location_flag` for
the 500 m ring, per spec.

Instrument eras: the capability id table's met_domain_name vocabulary in
this dataset is DLY3208, SYNOP, NCM, HSUN3445 (manual-era report types)
and AWSHRLY (automatic weather station). A station with an AWSHRLY row
starting after its first data year gets an aws-transition segment break
at that year. A station with no AWSHRLY row has no derivable instrument
history and is flagged `instrument_history_unknown`, per spec.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

METRES_PER_DEGREE_LAT = 111_320.0
AWS_DOMAINS = {"AWSHRLY"}
CLUSTER_MAX_KM = 5.0


@dataclass
class CapabilityRow:
    id: str
    id_type: str
    met_domain_name: str
    first_year: int
    last_year: int


@dataclass
class Capability:
    src_id: str
    name: str
    county: str
    lat: float
    lon: float
    lat_dp: int
    lon_dp: int
    height_m: float | None
    first_valid_year: int
    last_valid_year: int
    collection_version: str
    rows: list[CapabilityRow] = field(default_factory=list)


@dataclass
class Segment:
    start_year: int
    end_year: int
    break_reason: str  # open | resumed-after-gap | aws-transition | coordinate-change
    era: str  # manual | aws | unknown


@dataclass
class Cluster:
    members: list[str]  # src_ids
    name_stems: list[str]
    max_km: float


def _decimal_places(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def parse_capability(path: Path) -> Capability:
    """Parse a BADC-CSV capability file (globals + id table)."""
    globals_: dict[str, list[str]] = {}
    rows: list[CapabilityRow] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        in_data = False
        for rec in reader:
            if not rec:
                continue
            if rec[0] == "data":
                in_data = True
                continue
            if rec[0] == "end data":
                break
            if in_data:
                if rec[0] == "id":  # column-header line
                    continue
                rows.append(
                    CapabilityRow(
                        id=rec[0],
                        id_type=rec[1],
                        met_domain_name=rec[2],
                        first_year=int(float(rec[3])),
                        last_year=int(float(rec[4])),
                    )
                )
            elif len(rec) >= 3 and rec[1] == "G":
                globals_[rec[0]] = rec[2:]

    lat_s, lon_s = globals_["location"][0], globals_["location"][1]
    dv = globals_["date_valid"]
    height = globals_.get("height")
    return Capability(
        src_id=globals_["src_id"][0],
        name=globals_["observation_station"][0],
        county=globals_["historic_county_name"][0],
        lat=float(lat_s),
        lon=float(lon_s),
        lat_dp=_decimal_places(lat_s),
        lon_dp=_decimal_places(lon_s),
        height_m=float(height[0]) if height else None,
        first_valid_year=int(dv[0][:4]),
        last_valid_year=int(dv[1][:4]),
        collection_version=globals_["collection_version_number"][0],
        rows=rows,
    )


def annual_header(path: Path, max_lines: int = 40) -> dict:
    """Read src_id/location/height from an annual data file's BADC header."""
    out: dict = {}
    with open(path, newline="") as f:
        for i, rec in enumerate(csv.reader(f)):
            if i >= max_lines or (rec and rec[0] == "data"):
                break
            if len(rec) >= 3 and rec[1] == "G":
                if rec[0] == "midas_station_id":
                    out["src_id"] = rec[2]
                elif rec[0] == "location":
                    out["lat"], out["lon"] = float(rec[2]), float(rec[3])
                elif rec[0] == "height":
                    out["height_m"] = float(rec[2])
    return out


def coordinate_precision_m(lat: float, lat_dp: int, lon_dp: int) -> float:
    """Worst-axis half grid step in metres for coordinates stated to
    lat_dp/lon_dp decimal places."""
    lat_err = METRES_PER_DEGREE_LAT * 10**-lat_dp / 2
    lon_err = METRES_PER_DEGREE_LAT * math.cos(math.radians(lat)) * 10**-lon_dp / 2
    return max(lat_err, lon_err)


_YEAR_RE = re.compile(r"_(\d{4})\.csv$")


def station_data_years(station_dir: Path) -> list[int]:
    """Years with data files present under qc-version-1 (the archive's own
    evidence of operation — gaps here are real, never bridged)."""
    qc = station_dir / "qc-version-1"
    if not qc.is_dir():
        return []
    years = []
    for p in qc.iterdir():
        m = _YEAR_RE.search(p.name)
        if m:
            years.append(int(m.group(1)))
    return sorted(years)


def aws_transition_year(cap: Capability) -> int | None:
    """First year of automatic observation, where the metadata records it."""
    aws_years = [r.first_year for r in cap.rows if r.met_domain_name in AWS_DOMAINS]
    return min(aws_years) if aws_years else None


def segment_station(years: list[int], aws_from: int | None) -> list[Segment]:
    """Split a station's data years into segments: a new segment starts at
    every gap and at the AWS transition. No gap is ever bridged."""
    if not years:
        return []

    def era(year: int) -> str:
        if aws_from is None:
            return "unknown"
        return "aws" if year >= aws_from else "manual"

    segments: list[Segment] = []
    start = prev = years[0]
    reason = "open"
    for y in years[1:] + [None]:  # sentinel flushes the last segment
        gap = y is None or y != prev + 1
        aws_break = y is not None and aws_from is not None and y == aws_from > start
        if gap or aws_break:
            segments.append(
                Segment(start_year=start, end_year=prev, break_reason=reason, era=era(start))
            )
            if y is not None:
                start = y
                reason = "aws-transition" if aws_break and not gap else "resumed-after-gap"
        if y is not None:
            prev = y
    return segments


_NO_SUFFIX_RE = re.compile(r"(?:-no)?-\d+$")


def name_stem_tokens(name: str) -> list[str]:
    """Normalised name tokens with trailing 'no-N'/number suffixes removed."""
    return _NO_SUFFIX_RE.sub("", name.lower()).split("-")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def find_relocation_clusters(caps: list[Capability]) -> list[Cluster]:
    """Candidate relocation clusters: pairs whose name stems are in a
    token-prefix relation (weston-super-mare / weston-super-mare-worle)
    within CLUSTER_MAX_KM, merged transitively. Reported for the analysis
    phase's matched-pair logic, never auto-merged."""
    parent = {c.src_id: c.src_id for c in caps}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for i, a in enumerate(caps):
        ta = name_stem_tokens(a.name)
        for b in caps[i + 1 :]:
            tb = name_stem_tokens(b.name)
            n = min(len(ta), len(tb))
            if ta[:n] != tb[:n]:
                continue
            if _haversine_km(a.lat, a.lon, b.lat, b.lon) > CLUSTER_MAX_KM:
                continue
            union(a.src_id, b.src_id)

    groups: dict[str, list[Capability]] = {}
    for c in caps:
        groups.setdefault(find(c.src_id), []).append(c)

    clusters = []
    for members in groups.values():
        if len(members) < 2:
            continue
        max_km = max(
            _haversine_km(a.lat, a.lon, b.lat, b.lon)
            for i, a in enumerate(members)
            for b in members[i + 1 :]
        )
        clusters.append(
            Cluster(
                members=[c.src_id for c in members],
                name_stems=sorted({c.name for c in members}),
                max_km=round(max_km, 2),
            )
        )
    return clusters


def survivorship_by_decade(
    stations: list[dict], open_threshold_year: int
) -> dict[int, dict[str, int]]:
    """Openings vs closures per opening decade, so control-cohort
    survivorship is quantified rather than ignored."""
    out: dict[int, dict[str, int]] = {}
    for s in stations:
        decade = s["first_year"] // 10 * 10
        d = out.setdefault(decade, {"opened": 0, "still_open": 0, "closed": 0})
        d["opened"] += 1
        if s["last_year"] >= open_threshold_year:
            d["still_open"] += 1
        else:
            d["closed"] += 1
    return out


def _station_dirs(raw_root: Path):
    for county_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
        for station_dir in sorted(p for p in county_dir.iterdir() if p.is_dir()):
            caps = list(station_dir.glob("*capability*.csv"))
            if caps:
                yield station_dir, caps[0]


def build_station_history(
    raw_root: Path, verify_annual_headers: bool = True
) -> list[dict]:
    """One row per station segment, from every capability file under
    raw_root. Cross-checks annual headers against the capability file so
    same-id coordinate amendments are detected, not assumed absent."""
    rows: list[dict] = []
    caps: list[Capability] = []
    per_station: list[dict] = []

    for station_dir, cap_file in _station_dirs(raw_root):
        cap = parse_capability(cap_file)
        caps.append(cap)
        years = station_data_years(station_dir)
        aws_from = aws_transition_year(cap)

        moved = False
        if verify_annual_headers:
            for p in sorted((station_dir / "qc-version-1").glob("*.csv")):
                hdr = annual_header(p)
                if (
                    hdr.get("lat") != cap.lat
                    or hdr.get("lon") != cap.lon
                    or hdr.get("height_m") != cap.height_m
                ):
                    moved = True
                    break

        precision = coordinate_precision_m(cap.lat, cap.lat_dp, cap.lon_dp)
        segments = segment_station(years, aws_from)
        first_year = years[0] if years else cap.first_valid_year
        last_year = years[-1] if years else cap.last_valid_year
        per_station.append(
            {"src_id": cap.src_id, "first_year": first_year, "last_year": last_year}
        )
        for i, seg in enumerate(segments):
            rows.append(
                {
                    "src_id": cap.src_id,
                    "name": cap.name,
                    "county": cap.county,
                    "segment": i,
                    "start_year": seg.start_year,
                    "end_year": seg.end_year,
                    "break_reason": seg.break_reason,
                    "era": seg.era,
                    "lat": cap.lat,
                    "lon": cap.lon,
                    "height_m": cap.height_m,
                    "lat_dp": cap.lat_dp,
                    "lon_dp": cap.lon_dp,
                    "coordinate_precision_m": round(precision, 1),
                    "coarse_location_flag": precision > 100.0,
                    "aws_from_year": aws_from,
                    "instrument_history_unknown": aws_from is None,
                    "coordinate_moved_within_id": moved,
                    "station_first_year": first_year,
                    "station_last_year": last_year,
                    "n_segments": len(segments),
                    "collection_version": cap.collection_version,
                    "cluster_id": None,  # filled below
                }
            )

    clusters = find_relocation_clusters(caps)
    cluster_of = {
        src: f"cluster-{sorted(c.members)[0]}" for c in clusters for src in c.members
    }
    for r in rows:
        r["cluster_id"] = cluster_of.get(r["src_id"])
    return rows


def write_parquet(rows: list[dict], out_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("raw_root", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    rows = build_station_history(args.raw_root)
    write_parquet(rows, args.out)
    print(f"{len(rows)} segments, {len({r['src_id'] for r in rows})} stations -> {args.out}")


if __name__ == "__main__":
    main()
