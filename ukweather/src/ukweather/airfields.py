"""Airfield screen from OpenStreetMap aeroway features
(spec: first-principles-validation, Airfield screen requirement;
source pinning: design.md "Airfield-screen source pinning", 2026-07-29).

Screens every station's rings (500 m / 2 km / 10 km — the same true-circle
AEQD ring geometry as the GHSL and Stamp layers) against OSM
`aeroway=aerodrome|runway|taxiway|apron` features, including `disused:`
and `abandoned:` variants, pulled once for the whole UK from the public
Overpass API and cached to disk with a SHA-256 manifest.

THE SCREEN IS ONE-WAY. An OSM hit flags a station as ineligible for the
still-rural control cohort; an ABSENCE NEVER CERTIFIES A STATION CLEAN —
OSM's coverage of disused wartime airfields is uneven, and the spec says
so. Every row carries this in `screen_semantics`, and the flagged list
publishes the OSM feature ids so any flag can be checked.

Licence: OSM data © OpenStreetMap contributors, ODbL 1.0. Attribution
and retrieval details in data/airfields/LICENCE-NOTE.md.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, polygonize, transform as shp_transform

RINGS_M = [500, 2000, 10000]
AEROWAY_VALUES = ("aerodrome", "runway", "taxiway", "apron")
TAG_KEYS = ("aeroway", "disused:aeroway", "abandoned:aeroway")
UK_BBOX = (49.7, -8.7, 61.0, 2.0)  # south, west, north, east
OVERPASS = "https://overpass-api.de/api/interpreter"
BNG = "EPSG:27700"
SOURCE = "OpenStreetMap aeroway features via Overpass API"
LICENCE = "ODbL 1.0"

_TO_BNG = Transformer.from_crs("EPSG:4326", BNG, always_xy=True)


def _feature_kind(tags: dict) -> str | None:
    """The aeroway value with its lifecycle prefix, e.g. 'runway',
    'disused:aerodrome' — or None if the element is not one of ours."""
    for key in TAG_KEYS:
        v = tags.get(key)
        if v in AEROWAY_VALUES:
            prefix = "" if key == "aeroway" else key.split(":")[0] + ":"
            return prefix + v
    return None


def _coords_bng(geometry: list[dict]) -> list[tuple[float, float]]:
    lons = [p["lon"] for p in geometry]
    lats = [p["lat"] for p in geometry]
    xs, ys = _TO_BNG.transform(lons, lats)
    return list(zip(xs, ys))


def element_geometries(elements: list[dict]) -> list[tuple[str, str, shapely.Geometry]]:
    """(feature_id, kind, BNG geometry) for every relevant OSM element.

    Nodes become points; open ways linestrings; closed ways polygons;
    relations have their member ways merged and polygonized where they
    close (aerodrome boundaries are often split into several open ways),
    falling back to the raw lines where they do not.
    """
    out = []
    for el in elements:
        kind = _feature_kind(el.get("tags", {}))
        if kind is None:
            continue
        fid = f"{el['type']}/{el['id']}"
        if el["type"] == "node":
            x, y = _TO_BNG.transform(el["lon"], el["lat"])
            out.append((fid, kind, Point(x, y)))
        elif el["type"] == "way" and el.get("geometry"):
            pts = _coords_bng(el["geometry"])
            if len(pts) >= 4 and pts[0] == pts[-1]:
                out.append((fid, kind, Polygon(pts)))
            elif len(pts) >= 2:
                out.append((fid, kind, LineString(pts)))
        elif el["type"] == "relation":
            lines = [
                LineString(_coords_bng(m["geometry"]))
                for m in el.get("members", [])
                if m.get("type") == "way" and len(m.get("geometry", [])) >= 2
            ]
            if not lines:
                continue
            merged = linemerge(lines)
            polys = list(polygonize(merged))
            if polys:
                geom = shapely.MultiPolygon(polys) if len(polys) > 1 else polys[0]
            else:
                geom = merged
            out.append((fid, kind, geom))
    return out


def _ring_bng(lat: float, lon: float, radius_m: float) -> shapely.Polygon:
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    tr = Transformer.from_crs(aeqd, BNG, always_xy=True)
    return shp_transform(tr.transform, Point(0.0, 0.0).buffer(radius_m, quad_segs=64))


def ring_hits(
    lat: float,
    lon: float,
    features: list[tuple[str, str, shapely.Geometry]],
    tree: shapely.STRtree | None = None,
) -> dict[int, list[tuple[str, str]]]:
    """Per ring: the (feature_id, kind) list of intersecting features."""
    geoms = [f[2] for f in features]
    if tree is None and geoms:
        tree = shapely.STRtree(geoms)
    hits: dict[int, list[tuple[str, str]]] = {}
    for r in RINGS_M:
        ring = _ring_bng(lat, lon, r)
        found: list[tuple[str, str]] = []
        if tree is not None:
            for i in tree.query(ring, predicate="intersects"):
                found.append((features[int(i)][0], features[int(i)][1]))
        hits[r] = sorted(found)
    return hits


SEMANTICS = (
    "one-way screen: an OSM hit flags the station ineligible for the "
    "still-rural control cohort; absence certifies nothing (OSM coverage "
    "of disused wartime airfields is uneven)"
)


def screen_station(
    src_id: str,
    lat: float,
    lon: float,
    features: list[tuple[str, str, shapely.Geometry]],
    retrieved: str,
    tree: shapely.STRtree | None = None,
) -> list[dict]:
    hits = ring_hits(lat, lon, features, tree)
    flag = any(hits[r] for r in RINGS_M)
    rows = []
    for r in RINGS_M:
        rows.append(
            {
                "src_id": src_id,
                "lat": lat,
                "lon": lon,
                "ring_m": r,
                "hit": bool(hits[r]),
                "feature_ids": ";".join(f for f, _ in hits[r]),
                "feature_kinds": ";".join(k for _, k in hits[r]),
                "airfield_flag": flag,
                "screen_semantics": SEMANTICS,
                "source": SOURCE,
                "licence": LICENCE,
                "retrieved": retrieved,
            }
        )
    return rows


# --- Overpass fetch ---------------------------------------------------------


def overpass_query(tag_key: str) -> str:
    s, w, n, e = UK_BBOX
    values = "|".join(AEROWAY_VALUES)
    return (
        f'[out:json][timeout:900];nwr["{tag_key}"~"^({values})$"]'
        f"({s},{w},{n},{e});out geom;"
    )


def fetch_all(cache_dir: Path, retries: int = 5) -> list[dict]:
    """One cached Overpass pull per tag family (3 requests total for the
    whole UK — the polite alternative to 1,537 per-station queries).
    Re-running reuses the cache; a manifest records SHA-256 per file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    elements: list[dict] = []
    for key in TAG_KEYS:
        path = cache_dir / f"overpass-{key.replace(':', '-')}.json"
        if not path.exists():
            q = overpass_query(key)
            body = urllib.parse.urlencode({"data": q}).encode()
            for attempt in range(retries):
                try:
                    req = urllib.request.Request(
                        OVERPASS,
                        data=body,
                        headers={"User-Agent": "uk-weather-suite/0.1 (airfield screen)"},
                    )
                    with urllib.request.urlopen(req, timeout=1200) as r:
                        data = json.load(r)
                    break
                except Exception:
                    if attempt == retries - 1:
                        raise
                    time.sleep(30 * (attempt + 1))
            tmp = path.with_suffix(".part")
            tmp.write_text(json.dumps(data))
            tmp.rename(path)
            time.sleep(5)  # pause between the three pulls
        elements.extend(json.loads(path.read_text())["elements"])
    manifest = cache_dir / "overpass.sha256"
    with open(manifest, "w") as m:
        for p in sorted(cache_dir.glob("overpass-*.json")):
            m.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    return elements


def main() -> None:
    import argparse
    from datetime import date

    import pyarrow as pa
    import pyarrow.parquet as pq

    from ukweather.ghsl import stations_from_history

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("station_history", type=Path)
    ap.add_argument("cache_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--retrieved", default=str(date.today()))
    args = ap.parse_args()

    elements = fetch_all(args.cache_dir)
    features = element_geometries(elements)
    print(f"{len(elements)} OSM elements, {len(features)} usable geometries")
    tree = shapely.STRtree([f[2] for f in features])

    rows = []
    for i, (src_id, lat, lon) in enumerate(stations_from_history(args.station_history)):
        rows.extend(screen_station(src_id, lat, lon, features, args.retrieved, tree))
        if (i + 1) % 200 == 0:
            print(f"{i + 1} stations screened", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.out)
    flagged = len({r["src_id"] for r in rows if r["airfield_flag"]})
    print(f"{len(rows)} rows -> {args.out}; {flagged} stations flagged")


if __name__ == "__main__":
    main()
