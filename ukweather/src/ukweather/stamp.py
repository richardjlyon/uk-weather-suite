"""1930s Land Utilisation Survey screen (spec: first-principles-validation).

Computes the dominant 1930s class per station ring (500 m / 2 km /
10 km) from the EA Digital Land Utilisation Survey 1933-1949, and the
binary rural control-eligibility screen (rural = dominant class not
Urban/Suburban). A station ring with no survey coverage is flagged
`no_stamp_coverage` and never classified — stations north of the EA
extent (~55.8 N) fall out this way and await the NLS sheet protocol.

Source: EA dataset 7a723d0f-d465-11e4-b475-f0def148f590 via the EA
OGC API - Features service (the portal's bulk-file host,
api.agrimetrics.co.uk, is dead). Features carry only id/gridcode/
length/area — no sheet references or dates — so per-station provenance
records the dataset id, endpoint and retrieval date; sheet-level
provenance is not available from this dataset (see
data/stamp/LICENCE-NOTE.md, which also records the Environment Agency
Conditional Licence terms and required attribution).

Class legend from the dataset's own WMS style (GetLegendGraphic JSON).

Geometry: rings are true circles built in a station-centred azimuthal
equidistant projection; features (GeoJSON CRS84) and rings are
intersected in British National Grid (EPSG:27700), appropriate for the
England/Wales/southern-Scotland extent of this dataset.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import shapely
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shp_transform

GRIDCODE_CLASSES = {
    1: "rough-grazing", 2: "urban", 3: "water", 4: "arable",
    5: "suburban", 6: "grassland", 7: "woodland", 8: "orchard",
}
NON_RURAL = {"urban", "suburban"}
RINGS_M = [500, 2000, 10000]
BNG = "EPSG:27700"
DATASET_ID = "7a723d0f-d465-11e4-b475-f0def148f590"
API = (
    "https://environment.data.gov.uk/geoservices/datasets/"
    f"{DATASET_ID}/ogc/features/v1/collections/"
    "Digital_Land_Utilisation_Survey_1930/items"
)

_TO_BNG = Transformer.from_crs("EPSG:4326", BNG, always_xy=True)


def _ring_bng(lat: float, lon: float, radius_m: float) -> shapely.Polygon:
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    tr = Transformer.from_crs(aeqd, BNG, always_xy=True)
    return shp_transform(tr.transform, Point(0.0, 0.0).buffer(radius_m, quad_segs=64))


def classify_ring(
    features: list[dict], lat: float, lon: float, radius_m: float
) -> dict:
    """Per-class intersected-area fractions of the ring, coverage
    fraction, and the dominant class (None when nothing intersects —
    never a silent classification)."""
    ring = _ring_bng(lat, lon, radius_m)
    ring_area = ring.area
    areas = {name: 0.0 for name in GRIDCODE_CLASSES.values()}
    for f in features:
        code = f["properties"].get("gridcode")
        name = GRIDCODE_CLASSES.get(code)
        if name is None:
            continue
        geom = shp_transform(_TO_BNG.transform, shape(f["geometry"]))
        if not geom.intersects(ring):
            continue
        areas[name] += geom.intersection(ring).area
    covered = sum(areas.values())
    dominant = max(areas, key=lambda k: areas[k]) if covered > 0.0 else None
    return {
        "class_fractions": {k: v / ring_area for k, v in areas.items()},
        "coverage_fraction": min(covered / ring_area, 1.0),
        "dominant_class": dominant,
    }


def ring_row(
    src_id: str,
    lat: float,
    lon: float,
    radius_m: float,
    features: list[dict],
    retrieved: str | None = None,
) -> dict:
    c = classify_ring(features, lat, lon, radius_m)
    uncovered = c["dominant_class"] is None
    row = {
        "src_id": src_id,
        "lat": lat,
        "lon": lon,
        "ring_m": int(radius_m),
        "dominant_class": c["dominant_class"],
        "rural_screen": None if uncovered else c["dominant_class"] not in NON_RURAL,
        "no_stamp_coverage": uncovered,
        "coverage_fraction": c["coverage_fraction"],
        "n_features": len(features),
        "source": "EA-Digital-Land-Utilisation-Survey-1933-1949",
        "dataset_id": DATASET_ID,
        "endpoint": API,
        "retrieved": retrieved,
    }
    for name, frac in c["class_fractions"].items():
        row[f"frac_{name.replace('-', '_')}"] = frac
    return row


# --- harvest ----------------------------------------------------------------


def _bbox_crs84(lat: float, lon: float, radius_m: float) -> tuple:
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    tr = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)
    ring = shp_transform(tr.transform, Point(0.0, 0.0).buffer(radius_m, quad_segs=16))
    return ring.bounds  # lonmin, latmin, lonmax, latmax


def fetch_station_features(
    lat: float, lon: float, radius_m: float = 10_200, limit: int = 1000, retries: int = 5
) -> dict:
    """All features whose geometry intersects the station's outer-ring
    bounding box, paged through the OGC API."""
    bbox = _bbox_crs84(lat, lon, radius_m)
    url = f"{API}?f=json&limit={limit}&bbox=" + ",".join(f"{v:.6f}" for v in bbox)
    features = []
    while url:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        # the portal's WAF intermittently 403s the default
                        # Python-urllib agent; identify ourselves properly
                        "User-Agent": "uk-weather-suite/0.1 (station-classifier research)",
                        "Accept": "application/geo+json, application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=120) as r:
                    page = json.load(r)
                time.sleep(0.3)  # pace paged pulls politely
                break
            except urllib.error.HTTPError as e:
                if attempt == retries - 1:
                    raise
                # WAF blocks need a real cooldown, not seconds
                time.sleep(60 * (attempt + 1) if e.code in (403, 429) else 5 * (attempt + 1))
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))
        features.extend(page.get("features", []))
        url = next(
            (l["href"] for l in page.get("links", []) if l.get("rel") == "next"), None
        )
    return {"type": "FeatureCollection", "features": features}


def harvest(
    stations: list[tuple[str, float, float]], out_dir: Path, workers: int = 6
) -> None:
    """Resumable per-station harvest into out_dir/<src_id>.geojson with a
    SHA-256 manifest. Modest concurrency; .part files make interrupted
    downloads restart cleanly."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [
        (src_id, lat, lon)
        for src_id, lat, lon in stations
        if not (out_dir / f"{src_id}.geojson").exists()
    ]

    def one(job):
        src_id, lat, lon = job
        fc = fetch_station_features(lat, lon)
        path = out_dir / f"{src_id}.geojson"
        tmp = path.with_suffix(".part")
        tmp.write_text(json.dumps(fc))
        tmp.rename(path)
        return src_id

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, f in enumerate(as_completed(ex.submit(one, j) for j in todo)):
            f.result()  # re-raise failures
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(todo)} stations harvested", flush=True)
    manifest = out_dir.parent / "features.sha256"
    with open(manifest, "w") as m:
        for p in sorted(out_dir.glob("*.geojson")):
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            m.write(f"{digest}  features/{p.name}\n")
    print(f"manifest -> {manifest}")


def main() -> None:
    import argparse
    from datetime import date

    import pyarrow as pa
    import pyarrow.parquet as pq

    from ukweather.ghsl import stations_from_history

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("station_history", type=Path)
    ap.add_argument("stamp_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--retrieved", default=str(date.today()))
    args = ap.parse_args()

    stations = stations_from_history(args.station_history)
    features_dir = args.stamp_dir / "features"
    harvest(stations, features_dir)

    rows = []
    for i, (src_id, lat, lon) in enumerate(stations):
        feats = json.loads((features_dir / f"{src_id}.geojson").read_text())["features"]
        for r in RINGS_M:
            rows.append(ring_row(src_id, lat, lon, r, feats, retrieved=args.retrieved))
        if (i + 1) % 200 == 0:
            print(f"{i + 1}/{len(stations)} stations classified", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.out)
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
