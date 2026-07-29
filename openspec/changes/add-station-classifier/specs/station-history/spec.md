## ADDED Requirements

### Requirement: Station segment timeline
The system SHALL build, from the MIDAS capability/metadata files, a
per-station timeline of location (lat/lon), altitude, and operating
years, segmented such that any change in coordinates or altitude starts a
new segment.

#### Scenario: altitude change breaks the segment
- **WHEN** a station's recorded altitude changes between metadata records
- **THEN** the timeline shows two segments with the change date, and downstream analysis never treats the record as continuous across the break

#### Scenario: no invented continuity
- **WHEN** metadata is missing for a period
- **THEN** the gap is explicit in the timeline, never bridged by assumption

### Requirement: Instrument and observation-practice breaks
The system SHALL derive instrument-era changes from MIDAS metadata where
recorded (station type, equipment, observation schedule — notably the
manual→automatic (AWS) transition) and treat each as a segment break; where
the metadata cannot support this, the station SHALL carry an explicit
`instrument-history-unknown` flag that propagates to cohort reports.

#### Scenario: AWS transition breaks the segment
- **WHEN** a station's metadata records conversion to automatic observation
- **THEN** the timeline shows a break at that date, and within-segment analysis never spans it

#### Scenario: unknown instrument history is visible
- **WHEN** no instrument information is derivable for a station
- **THEN** the station is flagged, and cohort reports state how many members carry the flag

### Requirement: Coordinate precision recorded
The system SHALL record the precision of each station's coordinates as
given by MIDAS, and results for the 500 m ring SHALL carry a flag wherever
stated precision is coarser than 100 m.

#### Scenario: coarse coordinates flagged at fine rings
- **WHEN** a station's location is recorded to ~1 km precision
- **THEN** its 500 m-ring values are flagged unreliable-location and excluded from primary cohort derivation at that radius

### Requirement: Move-semantics verification
The system SHALL verify empirically how MIDAS represents station
relocation (same src_id with amended location vs a new src_id), by
auditing the capability files across the network, and SHALL record the
finding with examples in the data documentation.

#### Scenario: co-located id clusters detected
- **WHEN** two src_ids share a name stem and overlapping or abutting operating years within a small distance (e.g. the three Weston-super-Mare ids)
- **THEN** they are reported as a candidate relocation cluster for the analysis phase's matched-pair logic

### Requirement: Survivorship documentation
Cohort reporting SHALL include, for the long-record cohort, the number of
stations that opened in the same era but closed or fragmented, so
survivorship of the control cohort is quantified rather than ignored.

#### Scenario: attrition is visible
- **WHEN** a still-rural control cohort of N stations is derived
- **THEN** the report states how many same-era stations were excluded by closure, relocation or record fragmentation
