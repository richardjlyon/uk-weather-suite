## ADDED Requirements

### Requirement: Partitioned Parquet output
The `parse` subcommand SHALL walk `data/raw/<county>/<station>/qc-version-N/`
for a dataset and write one Parquet file per county to
`data/parquet/<dataset>/<county>.parquet`, processing files in parallel.

#### Scenario: full-archive parse
- **WHEN** `midas-fetch parse --dataset uk-hourly-weather-obs` runs over downloaded data
- **THEN** every county directory yields one Parquet file and a summary reports files parsed, rows written, and files failed

#### Scenario: corrupt file does not sink the county
- **WHEN** one yearly file in a county fails to parse
- **THEN** the county's other files are still written and the failure is listed by path in the summary

### Requirement: Stable enriched schema
Every output row SHALL carry the observation columns (typed, nullable) plus
`src_id` (int), `county` (string), `station_file_name` (string), and
`ob_time` as a Parquet timestamp. The schema SHALL be identical across
counties within a dataset.

#### Scenario: station attribution
- **WHEN** rows from `avon/00675_bristol-weather-centre/.../..._1995.csv` are written
- **THEN** each carries `src_id` 675, county "avon", station_file_name "00675_bristol-weather-centre"

#### Scenario: schema union across stations
- **WHEN** two stations' files declare different column subsets
- **THEN** the county Parquet contains the union of columns with nulls where a station lacks a column
