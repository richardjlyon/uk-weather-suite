# Station history — data documentation

*Source: MIDAS Open uk-hourly-weather-obs, dataset-version-202507 (1,537
stations, 34,238 annual qc-version-1 files). Built by
`ukweather.stations` into `data/parquet/derived/station-history.parquet`
(layout per docs/DATA.md).*

## How MIDAS Open represents station moves (verified, not assumed)

**A relocation is a new `src_id`, never a same-id amendment.** Verified
empirically two ways:

1. Every one of the 1,537 capability files carries exactly one
   `location`, one `height` and one `date_valid` line — the format has
   nowhere to record a second position for the same id.
2. Every one of the 34,238 annual data files' BADC headers was
   cross-checked against its station's capability file: **zero**
   stations show a changed location or height anywhere in their record
   (`coordinate_moved_within_id` is false for all stations).

Example — the four Weston-super-Mare ids (detected as one candidate
relocation cluster):

| src_id | name | location | height | data years |
|---|---|---|---|---|
| 01298 | weston-super-mare | 51.364, −2.952 | 94 m | 1972–1973 |
| 01299 | weston-super-mare-no-2 | 51.364, −2.908 | 5 m | 1985–1994 |
| 17342 | weston-super-mare-uphill | 51.322, −2.971 | 6 m | 1996–1998 |
| 30273 | weston-super-mare-worle | 51.361, −2.916 | 8 m | 2000–2001 |

Consequence for the analysis: a "station move" can never contaminate a
single src_id's series in this dataset version; instead, moves fragment
records across ids. The relocation-cluster detection (name-stem
token-prefix match within 5 km, merged transitively) reports candidates
for the analysis phase's matched-pair logic: **130 clusters covering 289
src_ids**. Clusters are flagged (`cluster_id`), never merged.

The builder still checks every annual header on every run, so a future
dataset version that starts amending locations in place would be caught,
not silently mis-segmented.

## Segmentation

One row per station segment. A new segment starts at:

- any gap in the years with data files present (gaps are explicit, never
  bridged) — 276 `resumed-after-gap` breaks;
- the manual→automatic (AWS) transition, where the capability id table
  records an `AWSHRLY` row beginning after the station's first data
  year — 107 `aws-transition` breaks (a further 16 transitions coincide
  with a gap or fall outside the data-file span, where the gap break or
  span end already separates the eras);
- any within-id coordinate or altitude change (none exist in dv-202507;
  the check remains active).

1,920 segments over 1,537 stations; 290 stations have more than one
segment.

## Instrument history

The capability `met_domain_name` vocabulary in this dataset: `DLY3208`,
`SYNOP`, `NCM`, `HSUN3445` (manual-era report types) and `AWSHRLY`
(automatic weather station). Where a station has an `AWSHRLY` row its
AWS era is derivable: 123 stations transitioned during their record, 34
were automatic from the start. The remaining **1,380 stations carry
`instrument_history_unknown`** — the metadata cannot support an
instrument timeline for them, and per the spec the flag propagates to
cohort reports rather than being papered over.

## Coordinate precision

MIDAS states locations to 1–3 decimal places. Precision is recorded as
the worst-axis half grid step (maximum quantisation error): 3 dp ≈ 56 m,
2 dp ≈ 560 m, 1 dp ≈ 5.6 km of latitude (longitude scaled by cos lat).
**273 stations are coarser than 100 m** and carry
`coarse_location_flag`; per the spec their 500 m-ring results are
flagged unreliable-location and excluded from primary cohort derivation
at that radius.

## Survivorship (openings vs closures by opening decade)

Closure threshold: last data year before 2023. The 1970s cohort
dominates and attrits hardest — relevant to any long-record control
cohort.

| decade | opened | still open | closed |
|---|---|---|---|
| pre-1900 | 13 | 6 | 7 |
| 1900s | 12 | 3 | 9 |
| 1910s | 24 | 7 | 17 |
| 1920s | 18 | 7 | 11 |
| 1930s | 7 | 5 | 2 |
| 1940s | 13 | 8 | 5 |
| 1950s | 64 | 27 | 37 |
| 1960s | 52 | 14 | 38 |
| 1970s | 599 | 86 | 513 |
| 1980s | 304 | 60 | 244 |
| 1990s | 267 | 75 | 192 |
| 2000s | 83 | 29 | 54 |
| 2010s | 58 | 49 | 9 |
| 2020s | 23 | 21 | 2 |

## Table columns

`src_id, name, county, segment, start_year, end_year, break_reason
(open | resumed-after-gap | aws-transition | coordinate-change), era
(manual | aws | unknown), lat, lon, height_m, lat_dp, lon_dp,
coordinate_precision_m, coarse_location_flag, aws_from_year,
instrument_history_unknown, coordinate_moved_within_id,
station_first_year, station_last_year, n_segments, collection_version,
cluster_id`.

Note: operating years here are the years with hourly-obs data files in
this dataset version. The capability `date_valid` range is parsed but
the data-file years are authoritative for segmentation, because they are
the archive's own evidence of operation.
