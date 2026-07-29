"""Census population density in the 10 km ring, 1981 onward
(spec: first-principles-validation, Census population density, as
amended 2026-07-29 — pre-1981 depth is out of scope: the historic
parish series is withdrawn from UK Data Service download; see the
design.md amendment).

Sources (all open, no account; identifiers recorded per row):
counts from NOMIS, boundary geometry from the ONS Open Geography Portal
(OGL). England and Wales only in this pass — Scottish and Northern
Irish census data exist openly (Scotland's Census / NRS, NISRA) but are
separate integrations; their stations carry explicit reason codes,
never silent nulls. Licences quoted in data/census/LICENCE-NOTE.md.

Binding semantics:
- 10 km ring ONLY. Requests for finer rings RAISE: ward/LSOA polygons
  are coarser than 500 m / 2 km rings and would smear.
- ONE-WAY: density growth can vote urbanised; absence of growth never
  disputes another layer's urbanised finding (carried per row in
  `one_way_semantics`).
- Comparison windows before 1981 abstain with reason
  `no-open-census-pre-1981` (an explicit abstention row per station);
  nothing is interpolated backwards.

Definitional note: the 1981 and 1991 SAS tables count PRESENT residents
(the SAS convention); 2001+ tables count USUAL residents. The 1991→2001
step therefore mixes definitions slightly; documented here and in
docs/DATA.md, absorbed by the calibrated change tolerances.

Density is population over the LAND area of the ring (GHS-LAND, via
builtup-fractions.parquet), consistent with the GHSL layer's land
denominators; the denominator cancels in growth comparisons either way.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
import urllib.request
from pathlib import Path

import shapely
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shp_transform

RING_M = 10_000
YEARS = [1981, 1991, 2001, 2011, 2021]
BNG = "EPSG:27700"
COVERAGE_FLOOR = 0.8  # of ring land area; below this the density is nulled
RETRIEVED_DEFAULT = None

# Pinned source identifiers (discovered and verified 2026-07-29).
SOURCES = {
    1981: {
        "counts": "NM_66_1 (1981 SAS) cell=1 'All Present residents : Total persons'",
        "nomis_url": (
            "https://www.nomisweb.co.uk/api/v01/dataset/NM_66_1.data.csv"
            "?date=latest&geography=TYPE33&cell=1&measures=20100"
        ),
        "geography": "1981 frozen wards EW",
        "boundaries": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Wards_1981_Boundaries_EW/FeatureServer/0"
        ),
    },
    1991: {
        "counts": "NM_38_1 (1991 SAS) cell=268501249 'S01:1 Present residents : Total persons'",
        "nomis_url": (
            "https://www.nomisweb.co.uk/api/v01/dataset/NM_38_1.data.csv"
            "?date=latest&geography=TYPE1&cell=268501249&measures=20100"
        ),
        "geography": "1991 frozen wards EW",
        "boundaries": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "WD_1991_EW/FeatureServer/0"
        ),
        # The boundary file's WD91CDO field actually carries census-style
        # codes (e.g. 02ATGC) while NOMIS keys on OPCS-style codes
        # (01AEGC); this names-and-codes service bridges the two
        # (its WD91CDC matches the boundary codes, its WD91CDO matches
        # NOMIS). Verified on Stonebridge/Brent, 2026-07-29.
        "code_lookup": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Wards_April_1991_Names_and_Codes_in_the_United_Kingdom_2022/"
            "FeatureServer/0"
        ),
        "code_lookup_from": "WD91CDC",
        "code_lookup_to": "WD91CDO",
    },
    2001: {
        "counts": "NM_1634_1 (KS001) cell=0 'All people'",
        "nomis_url": (
            "https://www.nomisweb.co.uk/api/v01/dataset/NM_1634_1.data.csv"
            "?date=latest&geography=TYPE304&cell=0&measures=20100"
        ),
        "geography": "2001 super output areas - lower layer EW",
        "boundaries": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Lower_Layer_Super_Output_Areas_Dec_2001_EW_BGC_2022/FeatureServer/0"
        ),
    },
    2011: {
        "counts": "NM_144_1 (KS101EW) CELL=0 'All usual residents', RURAL_URBAN=0",
        "nomis_url": (
            "https://www.nomisweb.co.uk/api/v01/dataset/NM_144_1.data.csv"
            "?date=latest&geography=TYPE298&rural_urban=0&cell=0&measures=20100"
        ),
        "geography": "2011 super output areas - lower layer EW",
        "boundaries": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "LSOA_Dec_2011_Boundaries_Generalised_Clipped_BGC_EW_V3/FeatureServer/0"
        ),
    },
    2021: {
        "counts": "NM_2021_1 (TS001) c2021_restype_3=0 'Total: All usual residents'",
        "nomis_url": (
            "https://www.nomisweb.co.uk/api/v01/dataset/NM_2021_1.data.csv"
            "?date=latest&geography=TYPE151&c2021_restype_3=0&measures=20100"
        ),
        "geography": "2021 super output areas - lower layer EW",
        "boundaries": (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5/"
            "FeatureServer/0"
        ),
    },
}

NI_COUNTIES = {"antrim", "armagh", "down", "fermanagh", "londonderry", "tyrone"}
SCOTTISH_COUNTIES = {
    "aberdeenshire", "angus", "argyll-in-highland-region",
    "argyll-in-strathclyde-region", "ayrshire", "banffshire", "berwickshire",
    "buteshire", "caithness", "dumfriesshire", "dunbartonshire", "east-lothian",
    "fife", "inverness-shire", "kincardineshire", "kinross-shire",
    "kirkcudbrightshire", "lanarkshire", "midlothian-in-lothian-region",
    "moray-in-grampian-region", "moray-in-highland-region", "nairnshire",
    "orkney", "peebleshire", "perthshire-in-central-region",
    "perthshire-in-tayside-region", "renfrewshire", "ross-and-cromarty",
    "roxburghshire", "selkirkshire", "shetland", "stirling-in-central-region",
    "sutherland", "west-lothian-in-lothian-region", "western-isles",
    "wigtownshire",
}

ONE_WAY = (
    "one-way: density growth can vote urbanised; absence of growth never "
    "disputes another layer's urbanised finding (airports and retail parks "
    "have no residents)"
)

_TO_BNG = Transformer.from_crs("EPSG:4326", BNG, always_xy=True)


def ring_bng(lat: float, lon: float, radius_m: float) -> shapely.Polygon:
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    tr = Transformer.from_crs(aeqd, BNG, always_xy=True)
    return shp_transform(tr.transform, Point(0.0, 0.0).buffer(radius_m, quad_segs=64))


def apportion_population(
    units: list[tuple[str, shapely.Geometry, float]],
    lat: float,
    lon: float,
    ring_m: float,
    tree: shapely.STRtree | None = None,
) -> dict:
    """Area-weighted population inside the station's ring.

    units: (code, BNG polygon, population). REFUSES any ring finer than
    10 km — census polygons are coarser than fine rings and would smear
    (spec scenario: no fine-ring smearing).
    """
    if ring_m != RING_M:
        raise ValueError(
            f"census density is 10 km-only: a {ring_m} m ring would smear "
            "ward/LSOA polygons across it (spec: no fine-ring smearing)"
        )
    ring = ring_bng(lat, lon, ring_m)
    pop = 0.0
    covered = 0.0
    n = 0
    idx = (
        tree.query(ring, predicate="intersects")
        if tree is not None
        else range(len(units))
    )
    for i in idx:
        code, geom, unit_pop = units[int(i)]
        inter = geom.intersection(ring).area
        if inter <= 0.0 or geom.area <= 0.0:
            continue
        pop += unit_pop * inter / geom.area
        covered += inter
        n += 1
    return {"population_in_ring": pop, "covered_area_m2": covered, "n_units": n}


def build_station_rows(
    src_id: str,
    lat: float,
    lon: float,
    county: str,
    units_per_year: dict[int, list],
    land_m2: float,
    retrieved: str,
    trees: dict[int, shapely.STRtree] | None = None,
) -> list[dict]:
    """One abstention row (pre-1981) plus one row per census year."""
    nation_reason = None
    if county in SCOTTISH_COUNTIES:
        nation_reason = "no-census-boundaries-scotland"
    elif county in NI_COUNTIES:
        nation_reason = "no-census-boundaries-northern-ireland"

    base = {
        "src_id": src_id,
        "lat": lat,
        "lon": lon,
        "county": county,
        "ring_m": RING_M,
        "land_km2": land_m2 / 1e6 if land_m2 else None,
        "one_way_semantics": ONE_WAY,
        "retrieved": retrieved,
    }
    rows = [
        {
            **base,
            "census_year": None,
            "population_in_ring": None,
            "density_per_km2": None,
            "density_delta_prev": None,
            "coverage_fraction": None,
            "n_units": 0,
            "geography": None,
            "counts_table": None,
            "boundary_service": None,
            "abstention": True,
            "reason": "no-open-census-pre-1981",
        }
    ]
    prev_density = None
    for year in sorted(YEARS):
        src = SOURCES[year]
        row = {
            **base,
            "census_year": year,
            "population_in_ring": None,
            "density_per_km2": None,
            "density_delta_prev": None,
            "coverage_fraction": None,
            "n_units": 0,
            "geography": src["geography"],
            "counts_table": src["counts"],
            "boundary_service": src["boundaries"],
            "abstention": False,
            "reason": None,
        }
        if nation_reason:
            row["reason"] = nation_reason
            rows.append(row)
            continue
        a = apportion_population(
            units_per_year.get(year, []), lat, lon, RING_M,
            tree=(trees or {}).get(year),
        )
        coverage = a["covered_area_m2"] / land_m2 if land_m2 else 0.0
        row["coverage_fraction"] = min(coverage, 1.0)
        row["n_units"] = a["n_units"]
        if land_m2 and coverage >= COVERAGE_FLOOR:
            density = a["population_in_ring"] / (land_m2 / 1e6)
            row["population_in_ring"] = a["population_in_ring"]
            row["density_per_km2"] = density
            if prev_density is not None:
                row["density_delta_prev"] = density - prev_density
            prev_density = density
        else:
            row["reason"] = "insufficient-boundary-coverage"
        rows.append(row)
    return rows


# --- fetch (cached, manifested) --------------------------------------------


def _get(url: str, retries: int = 5) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "uk-weather-suite/0.1 (census layer)"}
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_counts(year: int, cache_dir: Path) -> dict[str, float]:
    """NOMIS counts as {geography_code: population}, paged, cached."""
    path = cache_dir / f"counts-{year}.csv"
    if not path.exists():
        chunks = []
        offset = 0
        while True:
            url = f"{SOURCES[year]['nomis_url']}&recordlimit=25000&recordoffset={offset}"
            text = _get(url).decode()
            lines = text.strip().splitlines()
            if offset == 0:
                chunks.append(lines[0])
            body = lines[1:]
            chunks.extend(body)
            if len(body) < 25000:
                break
            offset += 25000
            time.sleep(1)
        tmp = path.with_suffix(".part")
        tmp.write_text("\n".join(chunks))
        tmp.rename(path)
    out = {}
    with open(path, newline="") as f:
        for rec in csv.DictReader(f):
            code = rec["GEOGRAPHY_CODE"]
            val = rec["OBS_VALUE"]
            if val:
                out[code] = float(val)
    return out


def fetch_boundaries(year: int, cache_dir: Path) -> list[dict]:
    """ONS geoportal features (GeoJSON, EPSG:4326), cached PER PAGE so an
    interrupted fetch resumes at the next page, then assembled once."""
    path = cache_dir / f"boundaries-{year}.geojson"
    if path.exists():
        return json.loads(path.read_text())["features"]

    pages_dir = cache_dir / "pages" / str(year)
    pages_dir.mkdir(parents=True, exist_ok=True)
    feats = []
    offset = 0
    while True:
        page_path = pages_dir / f"offset-{offset:07d}.json"
        if page_path.exists():
            page = json.loads(page_path.read_text())
        else:
            url = (
                f"{SOURCES[year]['boundaries']}/query?where=1%3D1&outFields=*"
                f"&outSR=4326&f=geojson&resultOffset={offset}"
            )
            page = json.loads(_get(url))
            tmp = page_path.with_suffix(".part")
            tmp.write_text(json.dumps(page))
            tmp.rename(page_path)
            print(f"  {year}: page at offset {offset} cached", flush=True)
            time.sleep(1)
        got = page.get("features", [])
        feats.extend(got)
        if not got:
            break
        offset += len(got)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    tmp.rename(path)
    return feats


def _code_of(props: dict) -> str | None:
    """The unit code that NOMIS keys on. For 1981/1991 wards NOMIS uses
    the old-style codes (e.g. '01AAAA'), which the boundary layers carry
    in *CDO fields; the *CD fields hold harmonised H-codes NOMIS does not
    use. Prefer *cdo, fall back to *cd."""
    for suffix in ("cdo", "cd"):
        for k, v in props.items():
            if k.lower().endswith(suffix) and isinstance(v, str):
                return v
    return None


def prepare_geometry(geom: shapely.Geometry) -> shapely.Geometry:
    """Repair invalid rings (generalised boundaries occasionally carry
    self-intersections that crash GEOS set operations)."""
    return geom if geom.is_valid else shapely.make_valid(geom)


def build_units(
    features: list[dict],
    counts: dict[str, float],
    translate: dict[str, str] | None = None,
):
    """(code, BNG geometry, population) for features with a matching count.
    `translate` maps boundary-file codes to the coding NOMIS keys on
    (needed for 1991, where the two products use different old-style
    ward code schemes)."""
    units = []
    unmatched = 0
    for f in features:
        code = _code_of(f.get("properties", {}))
        if translate and code in translate:
            code = translate[code]
        if code is None or code not in counts:
            unmatched += 1
            continue
        geom = prepare_geometry(shp_transform(_TO_BNG.transform, shape(f["geometry"])))
        units.append((code, geom, counts[code]))
    return units, unmatched


def fetch_code_lookup(year: int, cache_dir: Path) -> dict[str, str]:
    """Boundary-code -> NOMIS-code translation from the ONS names-and-codes
    service, where one is pinned for the year."""
    src = SOURCES[year]
    if "code_lookup" not in src:
        return {}
    path = cache_dir / f"code-lookup-{year}.json"
    if not path.exists():
        rows = []
        offset = 0
        while True:
            url = (
                f"{src['code_lookup']}/query?where=1%3D1&outFields=*"
                f"&f=json&resultOffset={offset}"
            )
            page = json.loads(_get(url))
            got = page.get("features", [])
            rows.extend(a["attributes"] for a in got)
            if not got:
                break
            offset += len(got)
            time.sleep(1)
        tmp = path.with_suffix(".part")
        tmp.write_text(json.dumps(rows))
        tmp.rename(path)
    rows = json.loads(path.read_text())
    fr, to = src["code_lookup_from"], src["code_lookup_to"]
    return {r[fr]: r[to] for r in rows if r.get(fr) and r.get(to)}


def write_manifest(cache_dir: Path) -> None:
    manifest = cache_dir / "census.sha256"
    with open(manifest, "w") as m:
        for p in sorted(cache_dir.glob("counts-*.csv")) + sorted(
            cache_dir.glob("boundaries-*.geojson")
        ):
            m.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")


def main() -> None:
    import argparse
    from datetime import date

    import pyarrow as pa
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("station_history", type=Path)
    ap.add_argument("builtup_fractions", type=Path)
    ap.add_argument("cache_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--retrieved", default=str(date.today()))
    args = ap.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    h = pq.read_table(
        args.station_history, columns=["src_id", "name", "county", "lat", "lon"]
    ).to_pylist()
    stations = {r["src_id"]: r for r in h}
    land = {
        r["src_id"]: r["land_m2"]
        for r in pq.read_table(
            args.builtup_fractions, columns=["src_id", "ring_m", "epoch", "land_m2"]
        ).to_pylist()
        if r["ring_m"] == RING_M and r["epoch"] == 2020
    }

    units_per_year: dict[int, list] = {}
    trees: dict[int, shapely.STRtree] = {}
    for year in YEARS:
        counts = fetch_counts(year, args.cache_dir)
        feats = fetch_boundaries(year, args.cache_dir)
        translate = fetch_code_lookup(year, args.cache_dir)
        units, unmatched = build_units(feats, counts, translate=translate)
        units_per_year[year] = units
        trees[year] = shapely.STRtree([u[1] for u in units])
        print(
            f"{year}: {len(counts)} counts, {len(feats)} boundaries, "
            f"{len(units)} matched units, {unmatched} unmatched",
            flush=True,
        )
    write_manifest(args.cache_dir)

    rows = []
    for i, s in enumerate(sorted(stations.values(), key=lambda r: r["src_id"])):
        rows.extend(
            build_station_rows(
                s["src_id"], s["lat"], s["lon"], s["county"], units_per_year,
                land.get(s["src_id"]) or 0.0, args.retrieved, trees,
            )
        )
        if (i + 1) % 200 == 0:
            print(f"{i + 1} stations", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.out)
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
