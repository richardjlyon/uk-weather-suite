# Data contract

*Change: harden-parquet-provenance (capability data-layout). Everything a
consumer needs to know about the produced files without reading code or
spec history.*

## Layout

```
data/
  raw/                      MIDAS Open BADC-CSV, hourly dataset (gitignored,
                            re-downloadable; sha256 manifest:
                            manifests/data-raw-hourly-202507.sha256)
  raw-daily-temp/,
  raw-daily-rain/           daily datasets (separate fetches)
  parquet/
    obs/<dataset>/          observation Parquet, one file per county, plus
                            run-record.json for the producing parse run
    derived/                derived tables (classifier outputs)
  ghsl/                     GHSL rasters + checksums (see data/ghsl/README.md)
  stamp/                    EA Land Utilisation Survey harvest + manifest
                            (see data/stamp/LICENCE-NOTE.md)
```

Observations and derived tables are separated so a glob over
`data/parquet/obs/<dataset>/*.parquet` can never pick up a derived table
of different schema. The `obs/<dataset>/` segment is constructed by
`midas-fetch parse --dataset <d>`, not typed by the operator.

**Transition note (2026-07-28):** the pre-layout hourly county files and
derived tables still sit directly under `data/parquet/` as the
verification baseline for the regeneration (task 4.1b of
harden-parquet-provenance). Canonical derived copies are in
`data/parquet/derived/`; the top-level originals are retired by Richard
only after the old-vs-new comparison passes.

## Observation files — `data/parquet/obs/<dataset>/<county>.parquet`

- **Producer**: `midas-fetch parse` (Rust), change
  harden-parquet-provenance.
- **Schema**: dataset-wide union of every station's declared columns,
  identical across all counties, built in a header-only pass before any
  file is written. Conflict policy: int-vs-float widens to float
  (recorded in file metadata `midas:schema_widenings` and the run
  record); numeric-vs-string aborts the run before output. Undeclared
  columns fall back to string, counted per (file, column).
- **Types**: declared ints are Int64; floats are **Float32 by decision,
  not inheritance** — MIDAS values carry at most six significant figures
  (temperatures to 0.1, pressures to 0.1 hPa), so Float32's 7 decimal
  digits are sufficient and halve the storage of the dominant column
  class. Quality (`_q`) and descriptor (`_j`) columns are strings,
  verbatim. `ob_time` is a **UTC-annotated millisecond timestamp**
  (MIDAS is GMT year-round; milliseconds deliberately — Parquet has no
  seconds-unit TIMESTAMP logical type, so a seconds-unit timestamp would
  be stored as bare INT64 and the UTC annotation would be invisible to
  pyarrow/duckdb, which is exactly the defect in the old files).
- **Attribution columns**: `src_id` (directory-derived), `county`,
  `station_file_name`. Rows whose in-file src_id disagrees with the
  directory are counted in the run record, never silently harmonised.
- **Provenance**: file metadata `midas:collection_version_number`
  (archive release, e.g. dataset-version-202507), `midas:units`
  (column → unit, from the BADC header), `midas:generator`. If one parse
  run ever ingests more than one release, every row additionally carries
  a `collection_version` column.
- **Null semantics**: `NA` sentinel, empty fields, and coercion failures
  (WMO `/` and `&` markers, non-finite floats, out-of-range integers,
  malformed values) all yield null; each class is counted separately per
  (file, column) in the run record.
- **Duplicate semantics — rows are reports, not station-hours.** MIDAS
  hourly files carry multiple reports per station-hour from different
  message streams. Consumers MUST deduplicate on
  `(src_id, ob_time, met_domain_name, version_num)` as their analysis
  requires — `version_num` distinguishes the originally received message
  (0) from the current best QC'd version (1), so omitting it picks
  arbitrarily between preliminary and QC'd values; `rec_st_ind` is a
  further discriminator. Row count is never observation count.
- **Run record**: `run-record.json` beside the county files — files
  parsed, rows per county, per-(file, column) coercion / empty-field /
  undeclared-fallback counts, src_id mismatches, schema widenings,
  releases ingested, every failure with path and error, start/finish
  times.

## Derived tables — `data/parquet/derived/`

| file | producer (change) | one row per | key columns |
|---|---|---|---|
| `station-history.parquet` | `ukweather.stations` (add-station-classifier) | station segment | src_id, segment, start/end year, break_reason, era, lat/lon/height, coordinate_precision_m, coarse_location_flag, instrument_history_unknown, cluster_id |
| `builtup-fractions.parquet` | `ukweather.ghsl` (add-station-classifier) | station × epoch × ring | builtup_fraction (land denominator), land_fraction, provenance_tag (sensor-anchored/interpolated/projected), anchor_sensor, nearest_obs_*, tile_ids, tile_checksums |
| `smod-classes.parquet` | `ukweather.ghsl` (add-station-classifier) | station × epoch | smod_class (raw JRC code, uninterpreted), independent=false (convenience view, never a voter) |
| `stamp-classes.parquet` | `ukweather.stamp` (add-station-classifier) | station × ring | dominant_class (1930s LUS), per-class fractions, coverage_fraction, rural_screen, no_stamp_coverage |
| `airfield-flags.parquet` | `ukweather.airfields` (add-station-classifier) | station × ring | hit, feature_ids/kinds (OSM, checkable on openstreetmap.org), airfield_flag, screen_semantics — **one-way**: a hit flags, absence certifies nothing (© OpenStreetMap contributors, ODbL 1.0; see data/airfields/LICENCE-NOTE.md) |
| `census-density.parquet` | `ukweather.census` (add-station-classifier) | station × census year (1981–2021, 10 km ring ONLY — finer rings refused) + one pre-1981 abstention row | density_per_km2 (over ring land area), density_delta_prev, coverage_fraction, counts_table/boundary_service/retrieved, reason (`no-open-census-pre-1981`, `no-census-boundaries-scotland`/`-northern-ireland`, `insufficient-boundary-coverage`), one_way_semantics — growth can vote urbanised, absence never disputes. NOMIS counts + ONS Open Geography OGL boundaries; 1981/1991 are *present* residents, 2001+ *usual* residents (see data/census/LICENCE-NOTE.md) |
| `spectral-indices.parquet` | `ukweather.spectral` (add-station-classifier) | station × decade (1970s–2020s) × ring | NDVI (primary), NDBI (corroborative) — band arithmetic on Landsat C2 L2 surface reflectance, growing-season (May–Sep) qa-masked median composites, single-sensor decades (TM/TM/ETM+/OLI/OLI recorded per row), scene_ids + n_scenes for third-party reproduction, `read_resolution_m`=60 (versioned parameter, design.md), water excluded via qa bit 7 + C2 valid-DN range with `water_fraction` reported. Reasons: `no-swir-sensor` (all pre-1984 — the floor), `insufficient-clear-scenes`, `insufficient-clear-coverage`, `ring-mostly-water`. Sentinel-2 deferred to its own change. Source: Microsoft Planetary Computer STAC (keyless), cached/resumable under `data/spectral/` |

Versioning discipline: derived tables are regenerable from raw inputs;
the classification table (future) is explicitly versioned and frozen
before analysis (see add-station-classifier, classification-table spec).

## Provenance chain

raw CSVs (sha256 manifest) → obs Parquet (release + units metadata, run
record) → derived tables (each row carries its source tile/dataset ids
and checksums where applicable) → analysis (consumes a named, frozen
classification version).

## airfield-flags.parquet (derived)

Produced by `ukweather.airfields` under `add-station-classifier` tasks
1.7 and 4.5 (committed 2026-07-29 inside commit `1d8dbf4`, whose message
covers only the regeneration — recorded here for traceability).

4,611 rows (1,537 stations × 3 rings). Per-ring `hit` with the OSM
feature ids that caused it, plus a station-level `airfield_flag`, and a
`screen_semantics` column carrying the one-way rule **in the data**: an
OSM hit flags a station ineligible for the still-rural control cohort;
an absence certifies nothing, because OSM's coverage of disused wartime
airfields is uneven.

Source: OpenStreetMap `aeroway` features (aerodrome, disused/abandoned
variants, runway/taxiway/apron geometry) via three cached UK-wide
Overpass pulls, 11,811 elements, sha256 manifest under `data/airfields/`;
ODbL, attribution in `data/airfields/LICENCE-NOTE.md`.

Per-ring hits: 132 stations at 500 m, 227 at 2 km, 1,056 at 10 km. Of
the 883 Stamp-rural stations: 99 / 159 / 696 respectively.

**Carried decision**: the gating radius for this screen must be declared
with the analysis change's pre-registered (radius, threshold) pair. At
10 km the screen flags 69% of the network, which would gut the control
cohort; the per-ring columns keep the choice open until it is declared
and frozen.
