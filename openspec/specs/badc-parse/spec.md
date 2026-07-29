# badc-parse Specification

## Purpose
TBD - created by archiving change add-badc-parser. Update Purpose after archive.
## Requirements
### Requirement: BADC-CSV header parsing
The parser SHALL read the BADC-CSV header block (rows before the `data`
marker) and extract global attributes (station name, historic county,
location, height) and per-column declarations (`long_name`, `type`, units)
keyed by column name.

#### Scenario: header declares column types
- **WHEN** the header contains `type,air_temperature,float` and `type,src_id,int`
- **THEN** the parser records `air_temperature` as float and `src_id` as integer

#### Scenario: malformed header line
- **WHEN** a header line does not fit the `key,column,value[,extra]` shape
- **THEN** the parser fails with an error naming the file and line number

### Requirement: Data section parsing
The parser SHALL parse only rows between the `data` line (whose next row is
the column-name row) and the `end data` line, and SHALL error if either
marker is missing.

#### Scenario: data section bounded
- **WHEN** a file has 283 header lines, a column row, observation rows, then `end data`
- **THEN** exactly the observation rows are parsed, none of the header

#### Scenario: truncated file
- **WHEN** a file ends without an `end data` line
- **THEN** the parser reports the file as corrupt rather than silently keeping partial rows

### Requirement: Type coercion and null handling
The parser SHALL coerce each value to its declared type, mapping the `NA`
sentinel to null, and SHALL parse `ob_time` as a naive UTC datetime.

#### Scenario: NA becomes null
- **WHEN** a float column holds `NA`
- **THEN** the record holds null, not 0.0 and not the string "NA"

#### Scenario: unparseable value coerced to null, counted
- **WHEN** a declared-int column holds a token that is not an integral number and not `NA`
  (real MIDAS files carry WMO markers like `/` and `&` in cloud-code columns)
- **THEN** the record holds null, and the file's parse result reports a count of coerced
  values so the loss is visible, never silent

#### Scenario: float-formatted integers accepted
- **WHEN** a declared-int column holds `300.0` (MIDAS files do this, e.g. wind_direction)
- **THEN** the record holds integer 300

### Requirement: Quality and flag columns preserved
The parser SHALL carry `*_q` quality columns and `*_j` flag columns through
unmodified as nullable strings, without interpreting them.

#### Scenario: quality flags survive
- **WHEN** `air_temperature_q` holds `9`
- **THEN** the output record holds `"9"` for that column

