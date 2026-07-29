## MODIFIED Requirements

### Requirement: Stable enriched schema
Every output row SHALL carry the observation columns (typed, nullable)
plus `src_id` (int), `county` (string), `station_file_name` (string),
and `ob_time` as a **UTC-annotated** Parquet timestamp (MIDAS observation
times are GMT year-round; the annotation prevents silent local-time
offsets downstream). The schema SHALL be identical across **all**
counties in a dataset, built as a dataset-wide union in a header-only
pass before any file is written. Declared-type conflicts SHALL be
resolved by a stated policy, not by abort-only: **numeric conflicts
(int vs float) widen to the wider numeric type**, with the widening
recorded in file metadata and the run report; **numeric-vs-string
conflicts abort** the pass with the column and both declaring stations
named, before output exists. Float storage precision SHALL be stated
explicitly in `docs/DATA.md` rather than inherited by default.

#### Scenario: station attribution
- **WHEN** rows from `avon/00675_bristol-weather-centre/.../..._1995.csv` are written
- **THEN** each carries `src_id` 675, county "avon", station_file_name "00675_bristol-weather-centre"

#### Scenario: one schema for the whole dataset
- **WHEN** two counties' stations declare different column subsets
- **THEN** both county files carry the identical dataset-wide union schema, with nulls where a station lacks a column

#### Scenario: numeric conflict widens, run completes
- **WHEN** one station declares a column int and another declares it float
- **THEN** the column is stored as the wider numeric type, the widening is recorded in file metadata and the run report, and the run completes

#### Scenario: numeric-vs-string conflict stops the run
- **WHEN** one station declares a column numeric and another declares it character
- **THEN** the schema pass aborts naming the column and BOTH declaring stations, and no Parquet is written

#### Scenario: timestamps are unambiguous
- **WHEN** `ob_time` is read by any consumer
- **THEN** its Parquet type carries the UTC timezone, and a round-trip test asserts a known timestamp value

### Requirement: Partitioned Parquet output
The `parse` subcommand SHALL walk the raw tree for a dataset and write
one Parquet file per county under `data/parquet/obs/<dataset>/`,
processing files in parallel. A county whose stations all fail SHALL
write no file (never a meta-only stub), and a failure while writing one
county SHALL be recorded and the run continued, not aborted.

#### Scenario: corrupt file does not sink the county
- **WHEN** one yearly file in a county fails to parse
- **THEN** the county's other files are still written and the failure is listed by path in the summary

#### Scenario: a failing county does not sink the run
- **WHEN** writing one county fails
- **THEN** the county is added to the failure list, remaining counties are still written, and the failure list is printed at the end

#### Scenario: no stub files
- **WHEN** every file in a county fails to parse
- **THEN** no Parquet file is created for that county and the county is reported

## ADDED Requirements

### Requirement: Archive-release provenance
Each output file SHALL record the source archive release
(`collection_version_number`, e.g. dataset-version-202507) as Parquet
file-level metadata, and SHALL additionally carry it as a per-row column
whenever a single parse run ingests more than one release.

#### Scenario: a row can be traced to its release
- **WHEN** a later archive release re-issues earlier years
- **THEN** rows from each release are distinguishable, and any value can be attributed to the release it came from

### Requirement: Durable run record
Every parse run SHALL write a machine-readable run record beside its
output: files parsed, rows per county, per-(file, column) coercion and
undeclared-fallback counts, every failure with its path and error,
schema-widening decisions, and the set of archive releases ingested.
A printed summary is not sufficient — the absence of a durable record
is what left the original run's six failing files untraceable.

#### Scenario: the run can be audited later
- **WHEN** a question arises months later about which files failed or which values were coerced
- **THEN** the run record answers it without re-running anything

### Requirement: Rows are reports, not station-hours
The output SHALL be documented as one row per *report*: MIDAS hourly
files carry multiple reports per station-hour from different message
streams. Consumers MUST deduplicate on
(src_id, ob_time, met_domain_name, version_num) as their analysis
requires — `version_num` distinguishes the originally received message
(0) from the current best quality-controlled version (1), so a key
omitting it picks arbitrarily between preliminary and QC'd values for
the same station-hour; `rec_st_ind` is a further discriminator. This
change SHALL NOT deduplicate.

#### Scenario: the consumer is warned, not surprised
- **WHEN** a downstream change counts rows as observations
- **THEN** the data documentation states the duplicate semantics and the deduplication key, so row-count is never mistaken for observation-count
