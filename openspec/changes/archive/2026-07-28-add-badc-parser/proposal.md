# Proposal: add-badc-parser

## Why

34,238 hourly observation files (~33.5 GB of BADC-CSV) are landing from CEDA
and are unusable for analysis in that form: per-station-per-year files, a
metadata header block, 104 columns, `NA` sentinels and per-column quality
flags. Analysis needs one queryable columnar dataset.

## What Changes

- New `parse` subcommand on `midas-fetch`: read every downloaded BADC-CSV
  file for a dataset and write partitioned Parquet.
- BADC-CSV reader: parse the header block (global attributes + per-column
  `long_name`/`type` declarations) and the `data`…`end data` section.
- Type coercion per the header's declared types; `NA` → null; timestamps
  parsed to proper datetimes.
- Quality flags (`*_q`) and per-element `_j` columns carried through, not
  interpreted.
- Station attributes (src_id, county, station name) attached to every row.
- Parallel: one file per task, streamed into per-county Parquet row groups.

## Capabilities

### New Capabilities
- `badc-parse`: parse MIDAS Open BADC-CSV observation files into typed
  records with nulls and quality flags preserved.
- `parquet-output`: write parsed records as partitioned Parquet with a
  stable, documented schema.

### Modified Capabilities

(none — first spec'd change; crawler/fetcher specs will be retrofitted in
`add-fetcher-tests`)

## Non-goals

- No interpretation or filtering by quality flag (analysis-side concern).
- No capability/metadata-file parsing (separate change: station table).
- No daily datasets yet — hourly first, same reader will generalise.
- No de-duplication across qc versions; qc-1 only.
