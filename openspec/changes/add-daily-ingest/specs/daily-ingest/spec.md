## ADDED Requirements

### Requirement: Daily datasets fetched and parsed
The system SHALL index, fetch (qc-version-1 plus capability files) and
parse uk-daily-temperature-obs and uk-daily-rain-obs
(dataset-version-202507) into per-county Parquet under
`data/parquet/obs/<dataset>/` (the layout contract set by
harden-parquet-provenance), using the existing midas-fetch pipeline
unchanged, with fetch summaries (fetched/skipped/failed) recorded and
zero unresolved failures before parse.

#### Scenario: resumable to zero failures
- **WHEN** a fetch pass ends with transient failures
- **THEN** re-running fetches only the missing files, and the recorded final state shows failed = 0 before parsing begins

#### Scenario: parser changes limited to the sanctioned delta
- **WHEN** a daily file violates an expectation of the archived parser capabilities
- **THEN** the file is reported as a finding, and the only parser modification permitted within this change is the named time-column mapping delta (ob_end_time/ob_date handling for daily datasets) — any other violation stays a finding for a future change

### Requirement: Observation-day conventions documented
The system SHALL record, in `docs/daily-conventions.md`, the
observation-day attribution rules for daily Tmin, Tmax and rainfall
(the 09:00–09:00 climatological day and which calendar day each extreme
is attributed to), AND the row-selection rules the cross-check applies
(`ob_hour_count` filter, `met_domain_name` and `version_num`
deduplication — daily files carry multiple rows per station-day),
quoted or justified from the dataset documentation/headers with
sources, before the cross-check runs.

#### Scenario: conventions precede comparison
- **WHEN** the hourly-vs-daily cross-check is computed
- **THEN** the attribution rule it assumes is the documented one, cited, not inferred from the data

### Requirement: Hourly-vs-daily extrema cross-check report
The system SHALL compare daily-dataset Tmax/Tmin against hourly-derived
extrema for a sample selected by a stated rule (stratified by region
and era from all stations with at least a stated number of overlapping
years), fixed before any discrepancy is computed, and
publish the discrepancy distribution (by station, season, instrument
era) to `docs/` as the evidence base for the analysis-phase extrema
decision — described, not decided, here.

#### Scenario: evidence without a verdict
- **WHEN** the cross-check report is produced
- **THEN** it quantifies discrepancies and their structure, cites the conventions doc, and makes no extrema-source decision
