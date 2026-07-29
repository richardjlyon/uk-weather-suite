## ADDED Requirements

### Requirement: Observations and derived tables are separated
Observation Parquet SHALL live under `data/parquet/obs/<dataset>/` and
derived tables (station history, built-up fractions, SMOD classes, Stamp
classes, classification) under `data/parquet/derived/`, so that a glob
over observation files cannot pick up a derived table of different
schema.

#### Scenario: globbing observations is safe
- **WHEN** a consumer reads all observation files for a dataset by glob
- **THEN** only observation files match, and the read succeeds without union-by-name workarounds

### Requirement: Data documentation
`docs/DATA.md` SHALL describe every produced file: its path, the change
that produces it, its schema summary, its provenance fields, its
versioning discipline, and its known semantics (including the
report-vs-station-hour duplicate rule).

#### Scenario: a newcomer can find the contract
- **WHEN** any session or collaborator needs to know what a file contains and who wrote it
- **THEN** `docs/DATA.md` answers it without reading code or spec history
