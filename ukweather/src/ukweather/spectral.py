"""Own spectral indices from raw scenes
(spec: first-principles-validation, "Own spectral indices from raw
scenes"; tasks 1.4 + 4.1 of add-station-classifier).

NDVI (primary) and NDBI (corroborative) per station ring per decade,
computed by band arithmetic on published Landsat Collection 2 Level-2
surface reflectance — no third-party land classification product
anywhere in this path. A third party can reproduce every value from the
scene ids recorded per composite.

Binding rules implemented here:
- growing season only (May–September acquisitions);
- 1984 floor: the 1970s decade is `no-swir-sensor` (Landsat MSS has no
  SWIR band, so NDBI cannot exist); nothing is hindcast; within the
  1980s decade only 1984+ scenes are used;
- insufficiency is explicit: a ring lacking clear coverage is null with
  a reason code, never interpolated (finer rings can be null while the
  2 km ring computes — rings are independent);
- per-sensor provenance per value (TM / ETM+ / OLI), because tolerance
  calibration is per sensor pair;
- rings are the same AEQD true circles as the GHSL/Stamp/airfield
  layers.

Data path: Microsoft Planetary Computer STAC API (landsat-c2-l2), no
account; asset hrefs signed via the planetary-computer package. Only
ring-bbox windows are read from the COGs, never whole scenes. Scene
searches and per-station results are cached on disk so the run is
resumable and a crash loses nothing.

Composite: per decade and sensor, the per-pixel MEDIAN of clear
(qa_pixel-masked) growing-season observations, indices computed on the
composite bands, then area-weighted ring means via the same cell-weight
machinery as the GHSL layer. Decade sensors: 1980s/1990s TM,
2000s ETM+, 2010s/2020s OLI (Sentinel-2 is a possible later addition;
its absence is a scoping note, not a silent gap).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from affine import Affine

from ukweather.ghsl import cell_weights, ring_polygon  # Mollweide helpers unused here
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform as shp_transform
import shapely

RINGS_M = [500, 2000, 10000]
DECADES = [1970, 1980, 1990, 2000, 2010, 2020]
SWIR_FLOOR_YEAR = 1984
MIN_SCENES = 2
MIN_VALID_FRACTION = 0.8
GROWING_MONTHS = range(5, 10)  # May..September inclusive

# Designated platforms per decade: keeps each composite single-sensor so
# the per-sensor-pair tolerance calibration has clean provenance.
DECADE_PLATFORMS = {
    1980: ["landsat-4", "landsat-5"],
    1990: ["landsat-5"],
    2000: ["landsat-7"],
    2010: ["landsat-8"],
    2020: ["landsat-8", "landsat-9"],
}
MAX_SCENES_PER_COMPOSITE = 8  # lowest cloud cover first
MAX_CLOUD_COVER = 70.0

STAC_API = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
BANDS = ["red", "nir08", "swir16", "qa_pixel"]


# --- pure arithmetic (spec: documented arithmetic, reproducible) -----------


def scale_l2_reflectance(dn: np.ndarray) -> np.ndarray:
    """Landsat Collection 2 Level-2 surface reflectance scaling."""
    return dn * 0.0000275 - 0.2


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(nir + red != 0, (nir - red) / (nir + red), np.nan)


def ndbi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(swir + nir != 0, (swir - nir) / (swir + nir), np.nan)


def clear_mask(qa_pixel: np.ndarray) -> np.ndarray:
    """True where the pixel is usable: not fill, not dilated cloud, not
    cirrus, not cloud, not cloud shadow (qa_pixel bits 0-4)."""
    bad = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)
    return (qa_pixel & bad) == 0


def in_growing_season(date_iso: str) -> bool:
    return int(date_iso[5:7]) in GROWING_MONTHS


def decade_of(year: int) -> int:
    return (year // 10) * 10


def sensor_of_platform(platform: str) -> str:
    p = platform.lower().replace("_", "-")
    if p in ("landsat-4", "landsat-5"):
        return "TM"
    if p == "landsat-7":
        return "ETM+"
    if p in ("landsat-8", "landsat-9"):
        return "OLI"
    raise ValueError(f"unknown platform {platform}")


def composite_median(
    stack: np.ndarray, clear: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Median over the scene axis of clear observations only.

    stack: (n_scenes, rows, cols) float; clear: same shape, bool.
    Returns (composite, n_clear_obs) with NaN where nothing is clear.
    """
    masked = np.where(clear, stack, np.nan)
    with np.errstate(all="ignore"):
        comp = np.nanmedian(masked, axis=0)
    nobs = clear.sum(axis=0)
    return comp, nobs


def ring_index_stats(
    index: np.ndarray,
    nobs: np.ndarray,
    transform: Affine,
    cx: float,
    cy: float,
    radius_m: float,
) -> dict:
    """Area-weighted ring mean of a composite index. Null with a reason
    code when clear coverage is insufficient — never interpolated."""
    ring = Point(cx, cy).buffer(radius_m, quad_segs=64)
    cw = cell_weights(ring, transform, index.shape)
    out = {"value": None, "valid_fraction": None, "reason": None}
    if cw is None:
        out["reason"] = "no-scene-coverage"
        return out
    rs, cs, w = cw
    vals = index[rs, cs]
    valid = ~np.isnan(vals)
    wsum = w.sum()
    if wsum <= 0:
        out["reason"] = "no-scene-coverage"
        return out
    valid_fraction = float((w * valid).sum() / wsum)
    out["valid_fraction"] = valid_fraction
    if valid_fraction < MIN_VALID_FRACTION:
        out["reason"] = "insufficient-clear-coverage"
        return out
    out["value"] = float((w * np.where(valid, vals, 0.0)).sum() / (w * valid).sum())
    return out


# --- STAC search and COG windows (cached, resumable) ------------------------


def _ring_wgs84_bbox(lat: float, lon: float, radius_m: float, pad: float = 300.0):
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    tr = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)
    ring = shp_transform(tr.transform, Point(0, 0).buffer(radius_m + pad, quad_segs=16))
    return ring.bounds


def search_scenes(
    lat: float, lon: float, decade: int, cache_path: Path
) -> list[dict]:
    """STAC search for growing-season scenes of the decade's designated
    platforms over the station, cached to disk. Enforces the 1984 floor
    inside the 1980s decade."""
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    from pystac_client import Client

    y0 = max(decade, SWIR_FLOOR_YEAR)
    y1 = decade + 9
    client = Client.open(STAC_API)
    bbox = _ring_wgs84_bbox(lat, lon, max(RINGS_M))
    hits = []
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=f"{y0}-05-01/{y1}-09-30",
        query={
            "eo:cloud_cover": {"lt": MAX_CLOUD_COVER},
            "platform": {"in": DECADE_PLATFORMS[decade]},
        },
        limit=200,
    )
    for item in search.items():
        date = item.datetime.strftime("%Y-%m-%d")
        if not in_growing_season(date):
            continue
        if int(date[:4]) < SWIR_FLOOR_YEAR:
            continue
        if not all(b in item.assets for b in BANDS):
            continue
        hits.append(
            {
                "id": item.id,
                "date": date,
                "platform": item.properties.get("platform", ""),
                "cloud_cover": item.properties.get("eo:cloud_cover"),
                "assets": {b: item.assets[b].href for b in BANDS},
                "epsg": item.properties.get("proj:epsg")
                or item.properties.get("proj:code", "").replace("EPSG:", ""),
            }
        )
    hits.sort(key=lambda h: (h["cloud_cover"] if h["cloud_cover"] is not None else 100))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".part")
    tmp.write_text(json.dumps(hits))
    tmp.rename(cache_path)
    return hits


def read_scene_window(scene: dict, lat: float, lon: float, radius_m: float):
    """Read the ring-bbox window of the scene's four bands (COG range
    reads only). Returns (bands dict, transform) in the scene CRS, or
    None if the window misses the scene."""
    import planetary_computer
    import rasterio
    from rasterio.windows import Window, from_bounds

    epsg = int(scene["epsg"])
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    x, y = tr.transform(lon, lat)
    xmin, ymin, xmax, ymax = (
        x - radius_m - 100, y - radius_m - 100, x + radius_m + 100, y + radius_m + 100,
    )
    bands = {}
    transform = None
    for b in BANDS:
        href = planetary_computer.sign(scene["assets"][b])
        with rasterio.open(href) as ds:
            w = from_bounds(xmin, ymin, xmax, ymax, ds.transform)
            w = Window(
                round(w.col_off), round(w.row_off), round(w.width), round(w.height)
            )
            full = Window(0, 0, ds.width, ds.height)
            w = w.intersection(full)
            if w.width <= 0 or w.height <= 0:
                return None
            arr = ds.read(1, window=w)
            if transform is None:
                transform = ds.window_transform(w)
                shape0 = arr.shape
            elif arr.shape != shape0:
                return None
            bands[b] = arr
    return bands, transform


def station_decade_composite(
    scenes: list[dict], lat: float, lon: float
) -> dict | None:
    """Median composite of up to MAX_SCENES_PER_COMPOSITE scenes over the
    10 km ring bbox; returns per-ring NDVI/NDBI stats plus provenance."""
    used = []
    reds, nirs, swirs, clears = [], [], [], []
    transform = None
    shape = None
    for scene in scenes:
        if len(used) >= MAX_SCENES_PER_COMPOSITE:
            break
        try:
            got = read_scene_window(scene, lat, lon, max(RINGS_M))
        except Exception:
            continue  # unreadable scene: skip, provenance shows what was used
        if got is None:
            continue
        bands, t = got
        if transform is None:
            transform, shape = t, bands["red"].shape
        elif bands["red"].shape != shape or t != transform:
            continue  # different grid (adjacent path/row) — keep it simple
        clear = clear_mask(bands["qa_pixel"])
        reds.append(scale_l2_reflectance(bands["red"].astype(np.float64)))
        nirs.append(scale_l2_reflectance(bands["nir08"].astype(np.float64)))
        swirs.append(scale_l2_reflectance(bands["swir16"].astype(np.float64)))
        clears.append(clear)
        used.append(scene)
    if len(used) < MIN_SCENES:
        return {"scenes": used, "reason": "insufficient-clear-scenes"}

    clear = np.stack(clears)
    red_c, _ = composite_median(np.stack(reds), clear)
    nir_c, nobs = composite_median(np.stack(nirs), clear)
    swir_c, _ = composite_median(np.stack(swirs), clear)
    ndvi_c = ndvi(red_c, nir_c)
    ndbi_c = ndbi(nir_c, swir_c)

    # ring stats in the scene CRS (UTM): build rings around the projected
    # station point — at ring scales the AEQD/UTM difference is negligible
    epsg = int(used[0]["epsg"])
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    cx, cy = tr.transform(lon, lat)
    rings = {}
    for r in RINGS_M:
        rings[r] = {
            "ndvi": ring_index_stats(ndvi_c, nobs, transform, cx, cy, r),
            "ndbi": ring_index_stats(ndbi_c, nobs, transform, cx, cy, r),
        }
    return {"scenes": used, "rings": rings, "reason": None}


def build_station(
    src_id: str, lat: float, lon: float, cache_dir: Path, retrieved: str
) -> list[dict]:
    """All rows for one station, cached as JSON so re-runs skip it."""
    done = cache_dir / "results" / f"{src_id}.json"
    if done.exists():
        return json.loads(done.read_text())
    rows = []
    base = {"src_id": src_id, "lat": lat, "lon": lon, "retrieved": retrieved}
    for decade in DECADES:
        if decade < 1980:
            for r in RINGS_M:
                rows.append(
                    {
                        **base, "decade": decade, "ring_m": r,
                        "ndvi": None, "ndbi": None, "valid_fraction": None,
                        "sensor": None, "n_scenes": 0, "scene_ids": "",
                        "reason": "no-swir-sensor",
                    }
                )
            continue
        cache = cache_dir / "search" / f"{src_id}-{decade}.json"
        scenes = search_scenes(lat, lon, decade, cache)
        comp = station_decade_composite(scenes, lat, lon)
        sensor = (
            sensor_of_platform(comp["scenes"][0]["platform"]) if comp["scenes"] else None
        )
        scene_ids = ";".join(s["id"] for s in comp["scenes"])
        for r in RINGS_M:
            row = {
                **base, "decade": decade, "ring_m": r,
                "ndvi": None, "ndbi": None, "valid_fraction": None,
                "sensor": sensor, "n_scenes": len(comp["scenes"]),
                "scene_ids": scene_ids, "reason": comp["reason"],
            }
            if comp["reason"] is None:
                stats = comp["rings"][r]
                row["ndvi"] = stats["ndvi"]["value"]
                row["ndbi"] = stats["ndbi"]["value"]
                row["valid_fraction"] = stats["ndvi"]["valid_fraction"]
                row["reason"] = stats["ndvi"]["reason"]
            rows.append(row)
    done.parent.mkdir(parents=True, exist_ok=True)
    tmp = done.with_suffix(".part")
    tmp.write_text(json.dumps(rows))
    tmp.rename(done)
    return rows


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
    ap.add_argument("--limit", type=int, default=None, help="pilot: first N stations")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--retrieved", default=str(date.today()))
    args = ap.parse_args()

    stations = stations_from_history(args.station_history)
    if args.limit:
        stations = stations[: args.limit]

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(build_station, s, la, lo, args.cache_dir, args.retrieved): s
            for s, la, lo in stations
        }
        for i, f in enumerate(as_completed(futs)):
            rows.extend(f.result())
            if (i + 1) % 10 == 0:
                el = time.time() - t0
                print(
                    f"{i + 1}/{len(stations)} stations, {el:.0f}s elapsed, "
                    f"{el / (i + 1):.1f}s/station",
                    flush=True,
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.out)
    print(f"{len(rows)} rows -> {args.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
