## ADDED Requirements

### Requirement: Own spectral indices from raw scenes
The system SHALL compute NDVI (primary) and NDBI (corroborative) per
station ring per decade from raw Landsat Collection 2 (TM onward, 1984+)
and Sentinel-2 band data, using growing-season (May–September) cloud-free
composites and only band arithmetic on published reflectance values — no
third-party land classification products in this path. Spectral change
tolerances SHALL be calibrated per sensor pair on the same rule-defined
reference sites as GHSL (see builtup-extraction), under the same
studentised familywise tolerance construction — never merely
"documented".

#### Scenario: no institutional classifier in the loop
- **WHEN** the spectral layer is computed
- **THEN** its inputs are raw scene bands and its transforms are documented arithmetic, reproducible by a third party from the same scene ids

#### Scenario: 1984 floor stated, not fudged
- **WHEN** a decade predates Landsat TM (1984)
- **THEN** the spectral layer is null with reason code `no-swir-sensor`; no index is hindcast

#### Scenario: growing-season window enforced
- **WHEN** compositing scenes for a decade
- **THEN** only May–September acquisitions enter the composite, so ploughed winter fields cannot read as built-up

#### Scenario: thin early coverage handled explicitly
- **WHEN** a decade has insufficient cloud-free scenes for a station's 500 m ring
- **THEN** the value is null with a reason code (never interpolated), and the 2 km ring is reported if computable

### Requirement: Census population density
The system SHALL compute population density within the 10 km ring only,
for each census from **1981 onward** — counts from NOMIS and boundary
geometry from the ONS Open Geography Portal (OGL), both openly
available without registration — stored with source table identifiers
and retrieval dates. Pre-1981 census depth is **out of scope**
(amendment 2026-07-29): the parish-level historic series is withdrawn
from UK Data Service download, Vision of Britain no longer serves
downloads, and historic parish boundary geometry is special-request
only. The 1981–2021 span covers the claim window (1975–2018), so the
layer's function within this change is preserved; restoring pre-1981
depth belongs to the deferred phase-two change and requires a data
request only Richard can send.

#### Scenario: one-way check
- **WHEN** census density enters the agreement rule
- **THEN** density growth can vote `urbanised`; absence of growth NEVER votes against another layer's `urbanised` finding (airports and retail parks have no residents)

#### Scenario: unavailable historic depth is stated, not faked
- **WHEN** a comparison window predates 1981
- **THEN** the census layer abstains with reason `no-open-census-pre-1981`, recorded as an abstention (not agreement), and no density is interpolated backwards

#### Scenario: no fine-ring smearing
- **WHEN** a 500 m or 2 km ring value is requested from census data
- **THEN** the system refuses: parish/district polygons are coarser than these rings and would smear

### Requirement: 1930s Land Utilisation Survey baseline screen
The system SHALL extract the dominant 1930s Land Utilisation Survey class
for each station ring — from the EA digitised dataset (**England, Wales
and border fragments only**; verified 2026-07-29) under the EA
Conditional Licence (which permits commercial use with attribution —
described accurately, and never as "open data") and, for stations
outside the EA extent, from the NLS georeferenced full-GB sheets by the
same ring protocol, the source recorded per station. A station with no survey
coverage is flagged `no-stamp-coverage`, never silently classified.
Control-cohort eligibility SHALL require a rural class (not
Urban/Suburban) in the 1930s survey. **Northern Ireland stations are
excluded from the still-rural control cohort** (Richard, 2026-07-29):
the Land Utilisation Survey covered Great Britain only, no equivalent
1930s survey exists for NI, so the pre-satellite screen cannot be
applied there — 158 stations, excluded by stated reason rather than
screened by a weaker rule than the rest of the network. The exclusion,
its count and its reason SHALL appear in the cohort report. The layer is a binary level screen, never a change voter, and
never a basis for widening the headline claim: it cannot date or
quantify change between the 1930s and 1975, so the headline claim stays
post-1975 (see proposal, Headline claim scope). The survey's provenance
(volunteer field survey, 1931–1949 coverage window, sheet dates) is
recorded per station.

#### Scenario: pre-satellite engulfment excluded
- **WHEN** a station's 2 km ring is classed Urban or Suburban in the 1930s survey but shows no satellite-era change
- **THEN** the station is ineligible for the still-rural control cohort, with the 1930s class recorded as the reason

#### Scenario: audit extract available
- **WHEN** a station's 1930s classification is challenged
- **THEN** the georeferenced period map extract (NLS Historic Maps API, attributed) for its rings can be produced from stored sheet references

#### Scenario: Scotland is screened, not skipped
- **WHEN** a Scottish station lies outside the EA dataset's extent (which is England, Wales and border fragments only — verified 2026-07-29, NOT "southern Scotland to 55.8N" as first assumed)
- **THEN** its 1930s class comes from the NLS route, and the source (EA vector features vs NLS sheet) is recorded

#### Scenario: Northern Ireland excluded, not silently failed
- **WHEN** cohort eligibility is computed for a Northern Ireland station
- **THEN** it is excluded with reason `no-1930s-survey-ni`, counted in the cohort report, and never treated as either passing or failing the screen

### Requirement: Airfield screen
Control-cohort candidates SHALL be screened against open airfield
gazetteers and post-war OS mapping for runway/apron presence within
their rings — hard surfaces invisible to building-footprint rasters and
censuses — producing a published binary flag with sources cited; flagged
stations are ineligible for the still-rural control cohort.

#### Scenario: the aerodrome control station is caught
- **WHEN** a long-record station sits on a WWII airfield that reads rural in the 1930s survey, low built-up in 1975 and stable in census
- **THEN** the airfield screen flags it and it does not enter the still-rural control cohort

### Requirement: Derived-tolerance cross-modality agreement rule
The system SHALL apply the agreement rule with tolerances derived from
the reference-site calibration (see builtup-extraction) and an explicit
epoch-alignment mapping defined in the versioned configuration: each
voting layer's periods are mapped to named comparison windows before any
vote, and a layer with no data in a window abstains (recorded as
abstained, not agreeing). The GHSL vote SHALL be evaluated at the same
ring radius as the pre-registered primary. `confirmed` requires all
voting layers to agree; otherwise `disputed` with the disagreeing layers
named. Changing any tolerance or the alignment mapping creates a new
classification version.

#### Scenario: disagreement is visible, not fatal
- **WHEN** GHSL votes urbanised but NDVI does not
- **THEN** the station-epoch is `disputed` with both layers named, excluded from headline cohorts, and listed in the run report with its geography

#### Scenario: one-way census cannot dispute
- **WHEN** spectral and GHSL vote urbanised and census shows no growth
- **THEN** the result is `confirmed` urbanised — census silence is not disagreement

#### Scenario: abstention is not agreement
- **WHEN** NDVI has no data for a comparison window (e.g. pre-1984)
- **THEN** the window's result rests on the remaining voters and the abstention is recorded in the station's audit row

#### Scenario: agreement confirms
- **WHEN** all voting layers show a station's surroundings unchanged and rural across all sensor-anchored and anchor-carrier epochs
- **THEN** the station is eligible for the still-rural control cohort
