# Proposal: harden-parquet-provenance

## Why

A retroactive adversarial review (2026-07-29) of the archived
`add-badc-parser` change — the foundation every downstream number rests
on — found one fatal and six serious defects. The 96.17M-row hourly
Parquet is *faithful to source* (15 coerced values in 96M is noise), but
three defects cannot be retrofitted onto the existing files and would
surface later as unexplainable analysis artefacts: no cross-county
schema guarantee, no dataset-version provenance, no timezone annotation.
Fix and regenerate now, before `add-analysis` consumes it.

## What Changes

**Fatal**
- **Dataset-wide union schema**: the promoted `parquet-output` capability
  requires "the schema SHALL be identical across counties within a
  dataset"; the implementation computes the union *per county*, so the
  same column can be Float32 in one county and Utf8 in another
  (undeclared columns silently default to string). Two-pass parse:
  build the union across all counties first under a stated conflict
  policy (numeric widens and is recorded; numeric-vs-string aborts
  naming both stations — abort-only would risk an unparseable archive),
  then write every county against that one schema. Undeclared-column string fallbacks are
  counted and reported like coerced nulls.

**Serious**
- **Dataset-version provenance**: `collection_version_number` is parsed
  and discarded. Written as Parquet file-level metadata (and per-row
  where releases could ever mix), so a row can be traced to the archive
  release it came from — v202601 will re-issue earlier years.
- **UTC-annotated timestamps**: `ob_time` is written as a *naive*
  timestamp though MIDAS is GMT year-round. Annotate as UTC so no
  downstream join can silently apply a one-hour summer offset across
  96M rows; add a round-trip test asserting a timestamp value (the
  existing test never checks one).
- **Per-column coercion attribution**: coerced nulls are counted per run
  only, so a systematically corrupt column appears as one number with
  nothing to localise it. Count per (file, column); report non-zero.
- **Run record reconstructed**: the archived change's own task required
  recording row counts and failures; the archive holds none, and the six
  files that failed the first parse pass are unaccounted for — up to six
  station-years may be silently absent. Their fate is established and
  recorded, or their absence is quantified.
- **Per-county error containment**: a schema conflict aborts the whole
  run mid-way (earlier counties written, later ones absent, failure list
  never printed) though the design promised per-county tolerance. Also:
  a county whose files all fail currently writes a meta-only stub file.
- **Duplicate semantics documented**: MIDAS hourly files carry multiple
  reports per station-hour (different message streams). Rows are
  *reports*, not unique station-hours; consumers must deduplicate on
  (src_id, ob_time, met_domain_name, version_num). Stated as a
  requirement so the
  analysis change cannot treat row-count as observation-count.
- **`parse_int_lenient` tested**: the trickiest function has no tests;
  add table-driven coverage (accept 300.0, reject 300.5, edges) and
  reject non-finite floats.

**Data layout** (found while building the docs visualisation): derived
tables live in the same directory as observation files, so a glob over
`data/parquet/*.parquet` fails or mixes schemas. Observations move to
`data/parquet/obs/<dataset>/`, derived tables to `data/parquet/derived/`,
documented in `docs/DATA.md`.

- **Regeneration**: re-run the parse over the untouched raw CSVs to new
  paths with the old tree intact, then verify by per-county value-level
  comparison (row counts, per-column non-null counts, numeric min/max/
  sum) — row count alone is invariant to every defect being fixed, and
  some fixes are expected to move values. Old trees retired only after
  the comparison passes.

## Capabilities

### New Capabilities
- `data-layout`: documented directory contract separating observations
  from derived tables.

### Modified Capabilities
- `parquet-output`: dataset-wide schema, version metadata, UTC
  timestamps, per-county containment, duplicate semantics.
- `badc-parse`: per-column coercion attribution, non-finite rejection,
  lenient-int tests.

## Non-goals

- No re-fetch of raw CSVs — a sha256 manifest over `data/raw` is
  written as task 0.1 to make "unchanged" an artefact rather than an
  assertion.
- No deduplication of message streams — documented, not performed;
  dedup belongs to the analysis, which knows which stream it wants.
- No schema redesign beyond the fixes above.
- No change to the classifier or analysis specs; their inputs are
  regenerated, not redefined.
