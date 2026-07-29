## MODIFIED Requirements

### Requirement: Type coercion and null handling
The parser SHALL coerce each value to its declared type, mapping the
`NA` sentinel to null, and SHALL parse `ob_time` as a UTC datetime.
Values that fail typed parsing SHALL be coerced to null and counted
**per (file, column)**, not merely per run, so a systematically corrupt
column is localisable rather than hidden inside an aggregate. Non-finite
floats (`inf`, `NaN`) SHALL be rejected as invalid rather than admitted.

#### Scenario: NA becomes null
- **WHEN** a float column holds `NA`
- **THEN** the record holds null, not 0.0 and not the string "NA"

#### Scenario: corruption is localisable
- **WHEN** a column in one file yields many coerced nulls
- **THEN** the run report names that file and column with its count, not just a run total

#### Scenario: non-finite floats rejected
- **WHEN** a declared-float column holds `inf` or `NaN`
- **THEN** the value is treated as invalid (counted, nulled), never admitted where it could silently poison a mean

#### Scenario: float-formatted integers accepted
- **WHEN** a declared-int column holds `300.0` (MIDAS files do this, e.g. wind_direction)
- **THEN** the record holds integer 300

#### Scenario: out-of-range integers rejected, never saturated
- **WHEN** a declared-int column holds a value outside i64 range (e.g. `1e30`, whose fractional part is zero)
- **THEN** it is rejected and counted, never silently saturated to i64::MAX — a valid-looking integer from an invalid token is the worst outcome

#### Scenario: lenient int parsing is tested at its edges
- **WHEN** the lenient integer parser is exercised
- **THEN** table-driven tests cover accept (`300.0`), reject (`300.5`, `/`, `&`), and out-of-range magnitudes, so the trickiest function in the parser is not the untested one

## ADDED Requirements

### Requirement: Empty fields distinguished from NA
An empty field SHALL be counted separately from the documented `NA`
sentinel. Both yield null, but `NA` is the archive's declared
missing-value marker while an empty field is a structural anomaly
(short row, trailing comma) — exactly the corruption class this change
exists to make localisable.

#### Scenario: structural anomalies surface
- **WHEN** a file contains empty fields rather than `NA`
- **THEN** the run record reports them per (file, column), separately from NA counts

### Requirement: Undeclared-column fallback counted
Columns present in a data section but undeclared in the header default
to string; the parser SHALL count and report such fallbacks per (file,
column) rather than applying them silently, since an undeclared numeric
column would otherwise become text without trace.

#### Scenario: a silent string column becomes visible
- **WHEN** a file's data section contains a column with no `type` declaration
- **THEN** the fallback is counted and reported with file and column name
