"""GHSL ring extraction (spec: builtup-extraction).

Computes, for every station x epoch x ring (500 m / 2 km / 10 km), the
built-up fraction from GHS-BUILT-S over the LAND area of the ring, with
area-weighted pixel intersection, plus the GHS-SMOD class at the station
cell. Rings are true geodesic circles (built in an azimuthal equidistant
projection centred on the station, then projected to the raster's
Mollweide CRS, which is equal-area so ring areas survive projection).

Land mask: GHS-BUILT-S codes sea as 0, not NoData (verified empirically:
mid-Bristol-Channel cells read 0), and the tile-schema "land" shapefile
is only 1000 km tile outlines — so neither carries usable land/water
information. The land denominator therefore comes from the sibling
GHS-LAND R2022A product (permanent land surface, m^2 per cell, on the
same 100 m Mollweide grid; the R2023A data package states GHS-LAND
"remains as a R2022 dataset").

Epoch provenance (per the GHSL Data Package 2023 PDF, section 2.1,
shipped inside every tile zip): the multi-temporal product interpolates
five observed collections — Landsat MSS (1975), TM (1990), ETM+ (2000),
OLI (2014) and the Sentinel-2 2018 composite. Shipped 5-yearly epochs
1975/1990/2000 coincide with observations and are tagged
sensor-anchored; 1980-2015 are interpolated; epochs after the last
observation (2020, 2025, 2030) are extrapolated and tagged projected.
NOTE: the OLI 2014 and S2 2018 observations fall between shipped grid
epochs, so no shipped epoch is anchored to OLI or S2; the nearest
observation and its offset are recorded per row so the task-5
epoch-alignment configuration can decide how observations map to
shipped epochs.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import shapely
from affine import Affine
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform as shp_transform

EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
RINGS_M = [500, 2000, 10000]
OBSERVATIONS = [(1975, "MSS"), (1990, "TM"), (2000, "ETM+"), (2014, "OLI"), (2018, "S2")]
CELL_AREA = 10_000.0  # m^2 per 100 m cell; values are m^2 per cell (0..10000)
NODATA = 65535
MOLLWEIDE = "ESRI:54009"


def epoch_provenance(epoch: int) -> dict:
    """Tag a shipped epoch per the JRC R2023A data package (see module
    docstring), recording the nearest observation for the alignment
    config."""
    obs_years = {y: s for y, s in OBSERVATIONS}
    nearest = min(obs_years, key=lambda y: (abs(y - epoch), y))
    if epoch in obs_years:
        tag, anchor = "sensor-anchored", obs_years[epoch]
    elif epoch > max(obs_years):
        tag, anchor = "projected", None
    else:
        tag, anchor = "interpolated", None
    return {
        "tag": tag,
        "anchor_sensor": anchor,
        "nearest_obs_year": nearest,
        "nearest_obs_sensor": obs_years[nearest],
        "obs_offset_years": abs(epoch - nearest),
    }


def ring_polygon(lat: float, lon: float, radius_m: float) -> shapely.Polygon:
    """True circle of radius_m around the station, as a polygon in the
    Mollweide raster CRS."""
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    to_moll = Transformer.from_crs(aeqd, MOLLWEIDE, always_xy=True)
    circle = Point(0.0, 0.0).buffer(radius_m, quad_segs=64)
    return shp_transform(to_moll.transform, circle)


def cell_weights(
    poly: shapely.Polygon, transform: Affine, shape: tuple[int, int]
) -> tuple[slice, slice, np.ndarray] | None:
    """Fraction of each grid cell's area inside poly, over the cell window
    covering poly's bounds. Interior cells weight 1; boundary cells get
    exact intersected area. Returns None if the window does not fully
    cover the polygon's bounds (caller reports no-coverage)."""
    inv = ~transform
    xmin, ymin, xmax, ymax = poly.bounds
    c0f, r0f = inv * (xmin, ymax)
    c1f, r1f = inv * (xmax, ymin)
    r0, c0 = int(np.floor(r0f)), int(np.floor(c0f))
    r1, c1 = int(np.ceil(r1f)), int(np.ceil(c1f))
    if r0 < 0 or c0 < 0 or r1 > shape[0] or c1 > shape[1]:
        return None
    rows = np.arange(r0, r1)
    cols = np.arange(c0, c1)
    cc, rr = np.meshgrid(cols, rows)
    x0, y0 = transform * (cc, rr)          # cell top-left corners
    x1, y1 = transform * (cc + 1, rr + 1)  # cell bottom-right corners
    boxes = shapely.box(x0.ravel(), np.minimum(y0, y1).ravel(),
                        x1.ravel(), np.maximum(y0, y1).ravel())
    shapely.prepare(poly)
    inside = shapely.contains_properly(poly, boxes)
    touching = shapely.intersects(poly, boxes) & ~inside
    w = np.where(inside, 1.0, 0.0)
    if touching.any():
        w[touching] = shapely.area(shapely.intersection(boxes[touching], poly)) / CELL_AREA
    return slice(r0, r1), slice(c0, c1), w.reshape(len(rows), len(cols))


def ring_stats(
    built: np.ndarray, land: np.ndarray, transform: Affine, poly: shapely.Polygon
) -> dict:
    """Area-weighted built-up fraction over the land area of the ring.

    built, land: m^2 per cell (GHS-BUILT-S / GHS-LAND), NODATA = 65535.
    """
    return _ring_stats_from_weights(
        built, land, cell_weights(poly, transform, built.shape)
    )


def sample_raster_class(
    arr: np.ndarray, transform: Affine, x: float, y: float, nodata
) -> int | None:
    """Raw class code of the cell containing (x, y), uninterpreted."""
    c, r = ~transform * (x, y)
    r, c = int(np.floor(r)), int(np.floor(c))
    if not (0 <= r < arr.shape[0] and 0 <= c < arr.shape[1]):
        return None
    v = arr[r, c]
    return None if v == nodata else int(v)


class Mosaic:
    """A set of same-grid GHSL tiles read as one raster. Tiles must share
    resolution and grid alignment (asserted)."""

    def __init__(self, zip_paths: list[Path]):
        import rasterio

        self.parts = []
        res = None
        for z in sorted(zip_paths):
            tif = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith(".tif"))
            ds = rasterio.open(f"zip://{z}!/{tif}")
            if res is None:
                res = ds.res
                self.nodata = ds.nodata
                self.dtype = ds.dtypes[0]
            assert ds.res == res, f"resolution mismatch in {z.name}"
            assert (ds.bounds.left / res[0]) % 1 == 0 and (ds.bounds.top / res[1]) % 1 == 0, (
                f"grid misalignment in {z.name}"
            )
            tile_id = "_".join(tif.replace(".tif", "").split("_")[-2:])
            self.parts.append((ds, tile_id, z.name))
        self.res = res

    def read(self, xmin, ymin, xmax, ymax):
        """Read a bbox stitched across tiles. Returns (array, transform,
        tile_ids) with cells not covered by any tile set to nodata."""
        from rasterio.windows import Window, from_bounds

        rx, ry = self.res
        # snap outward to the grid
        xmin = np.floor(xmin / rx) * rx
        xmax = np.ceil(xmax / rx) * rx
        ymin = np.floor(ymin / ry) * ry
        ymax = np.ceil(ymax / ry) * ry
        ncols = round((xmax - xmin) / rx)
        nrows = round((ymax - ymin) / ry)
        out = np.full((nrows, ncols), self.nodata, dtype=self.dtype)
        covered = np.zeros((nrows, ncols), dtype=bool)
        t = Affine(rx, 0.0, xmin, 0.0, -ry, ymax)
        used = []
        for ds, tile_id, zname in self.parts:
            b = ds.bounds
            ix0, ix1 = max(xmin, b.left), min(xmax, b.right)
            iy0, iy1 = max(ymin, b.bottom), min(ymax, b.top)
            if ix0 >= ix1 or iy0 >= iy1:
                continue
            w = from_bounds(ix0, iy0, ix1, iy1, ds.transform)
            w = Window(round(w.col_off), round(w.row_off), round(w.width), round(w.height))
            a = ds.read(1, window=w)
            r0 = round((ymax - iy1) / ry)
            c0 = round((ix0 - xmin) / rx)
            out[r0 : r0 + a.shape[0], c0 : c0 + a.shape[1]] = a
            covered[r0 : r0 + a.shape[0], c0 : c0 + a.shape[1]] = True
            used.append((tile_id, zname))
        return out, t, used, covered


class GhslData:
    """The downloaded GHSL products under data/ghsl/, with checksum
    provenance from checksums.sha256."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.checksums = {}
        for line in (self.root / "checksums.sha256").read_text().splitlines():
            digest, name = line.split()
            self.checksums[Path(name).name] = digest
        self.built = {
            e: Mosaic(sorted(self.root.glob(f"built-s/GHS_BUILT_S_E{e}_*.zip")))
            for e in EPOCHS
        }
        self.smod = {
            e: Mosaic(sorted(self.root.glob(f"smod/GHS_SMOD_E{e}_*.zip")))
            for e in EPOCHS
        }
        self.land = Mosaic(sorted(self.root.glob("land/GHS_LAND_E2018_*.zip")))

    def _provenance_cols(self, epoch):
        p = epoch_provenance(epoch)
        return {
            "provenance_tag": p["tag"],
            "anchor_sensor": p["anchor_sensor"],
            "nearest_obs_year": p["nearest_obs_year"],
            "nearest_obs_sensor": p["nearest_obs_sensor"],
            "obs_offset_years": p["obs_offset_years"],
        }

    def extract_station(
        self, src_id: str, lat: float, lon: float, epochs: list[int] | None = None
    ) -> list[dict]:
        """Built-up rows for one station: one row per epoch x ring."""
        epochs = epochs or EPOCHS
        rings = {r: ring_polygon(lat, lon, r) for r in RINGS_M}
        pad = 200.0
        xmin, ymin, xmax, ymax = rings[max(RINGS_M)].bounds
        bbox = (xmin - pad, ymin - pad, xmax + pad, ymax + pad)
        land_arr, land_t, land_used, land_cov = self.land.read(*bbox)
        weights = {}  # computed once per ring; the grid is epoch-invariant
        rows = []
        for epoch in epochs:
            built_arr, built_t, built_used, built_cov = self.built[epoch].read(*bbox)
            assert built_t == land_t, "GHS-LAND grid must match GHS-BUILT-S"
            cov = built_cov & land_cov
            for r in RINGS_M:
                if r not in weights:
                    weights[r] = cell_weights(rings[r], built_t, built_arr.shape)
                s = _ring_stats_from_weights(built_arr, land_arr, weights[r], cov)
                rows.append(
                    {
                        "src_id": src_id,
                        "lat": lat,
                        "lon": lon,
                        "epoch": epoch,
                        "ring_m": r,
                        **s,
                        **self._provenance_cols(epoch),
                        "product": "GHS_BUILT_S",
                        "release": "R2023A",
                        "version": "V1_0",
                        "tile_ids": ";".join(t for t, _ in built_used),
                        "tile_checksums": ";".join(self.checksums[z] for _, z in built_used),
                        "land_product": "GHS_LAND_E2018_R2022A_V1_0",
                        "land_tile_ids": ";".join(t for t, _ in land_used),
                        "land_tile_checksums": ";".join(self.checksums[z] for _, z in land_used),
                    }
                )
        return rows

    def extract_smod(
        self, src_id: str, lat: float, lon: float, epochs: list[int] | None = None
    ) -> list[dict]:
        """SMOD class rows for one station: one row per epoch. Raw class
        codes, uninterpreted; a convenience view derived from the same JRC
        pipeline as GHS-BUILT-S — non-independent, never a voter."""
        to_moll = Transformer.from_crs("EPSG:4326", MOLLWEIDE, always_xy=True)
        x, y = to_moll.transform(lon, lat)
        rows = []
        for epoch in epochs or EPOCHS:
            m = self.smod[epoch]
            arr, t, used, _ = m.read(x - 1500, y - 1500, x + 1500, y + 1500)
            cls = sample_raster_class(arr, t, x, y, m.nodata)
            rows.append(
                {
                    "src_id": src_id,
                    "lat": lat,
                    "lon": lon,
                    "epoch": epoch,
                    "smod_class": cls,
                    "reason": None if cls is not None else "no-coverage",
                    **self._provenance_cols(epoch),
                    "product": "GHS_SMOD",
                    "release": "R2023A",
                    "version": "V2_0",
                    "tile_ids": ";".join(t_ for t_, _ in used),
                    "tile_checksums": ";".join(self.checksums[z] for _, z in used),
                    "independent": False,
                }
            )
        return rows


def _ring_stats_from_weights(built, land, cw, covered=None) -> dict:
    """Weighted stats with GHSL nodata semantics: the products process
    only land + a coastal buffer, so cells that are nodata in GHS-LAND
    are open sea (0 land), not a data gap. A genuine gap is built-up
    nodata over real land, or ring cells outside every tile (covered
    mask False)."""
    out = {
        "builtup_m2": None, "land_m2": None, "ring_area_m2": None,
        "land_fraction": None, "builtup_fraction": None, "reason": None,
    }
    if cw is None:
        out["reason"] = "no-coverage"
        return out
    rs, cs, w = cw
    b = built[rs, cs].astype(np.float64)
    l = land[rs, cs].astype(np.float64)
    in_ring = w > 0
    if covered is not None and (in_ring & ~covered[rs, cs]).any():
        out["reason"] = "no-coverage"
        return out
    l[l == NODATA] = 0.0  # offshore, outside the processing footprint: sea
    if (in_ring & (b == NODATA) & (l > 0)).any():
        out["reason"] = "no-coverage"  # built-up missing over real land
        return out
    b[b == NODATA] = 0.0
    ring_area = float(w.sum() * CELL_AREA)
    land_m2 = float((w * l).sum())
    out["ring_area_m2"] = ring_area
    out["land_m2"] = land_m2
    out["land_fraction"] = land_m2 / ring_area
    if land_m2 <= 0.0:
        out["reason"] = "no-land-in-ring"
        return out
    builtup_m2 = float((w * b).sum())
    out["builtup_m2"] = builtup_m2
    out["builtup_fraction"] = builtup_m2 / land_m2
    return out


def stations_from_history(parquet_path: Path) -> list[tuple[str, float, float]]:
    import pyarrow.parquet as pq

    t = pq.read_table(parquet_path, columns=["src_id", "lat", "lon"]).to_pylist()
    seen = {}
    for r in t:
        seen[r["src_id"]] = (r["src_id"], r["lat"], r["lon"])
    return sorted(seen.values())


def main() -> None:
    import argparse

    import pyarrow as pa
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ghsl_root", type=Path)
    ap.add_argument("station_history", type=Path)
    ap.add_argument("builtup_out", type=Path)
    ap.add_argument("smod_out", type=Path)
    args = ap.parse_args()

    g = GhslData(args.ghsl_root)
    stations = stations_from_history(args.station_history)
    built_rows, smod_rows = [], []
    for i, (src_id, lat, lon) in enumerate(stations):
        built_rows.extend(g.extract_station(src_id, lat, lon))
        smod_rows.extend(g.extract_smod(src_id, lat, lon))
        if (i + 1) % 100 == 0:
            print(f"{i + 1}/{len(stations)} stations", flush=True)

    for rows, path in [(built_rows, args.builtup_out), (smod_rows, args.smod_out)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), path)
        print(f"{len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
