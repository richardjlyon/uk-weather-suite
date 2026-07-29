## ADDED Requirements

### Requirement: Per-station per-epoch classification table
The system SHALL emit a versioned `station-classification.parquet` with
one row per station × epoch carrying: built-up fractions (all rings, land
denominators, provenance tags), SMOD class, spectral indices, census
density, 1930s Land Utilisation class, agreement status with
voting-layer and abstention detail, confidence tier, and Met Office WMO
siting class as descriptive metadata where published.

#### Scenario: siting class never load-bearing
- **WHEN** cohorts are derived from the table
- **THEN** the derivation uses no Met Office siting-class column

#### Scenario: confidence tiers propagate
- **WHEN** a station-epoch's classification rests on the 1975 GHSL epoch or on census-only coverage (pre-1975)
- **THEN** it carries a lower-confidence marker that propagates to any downstream output

### Requirement: Derived cohorts with pre-registered primary
Cohort derivations SHALL be computed as functions over the table across
the full radius × threshold grid, AND the analysis phase MUST declare a
single pre-registered primary (radius, threshold) pair — justified from
the source-area literature — before any temperature trend is computed.
The grid is robustness; the primary is the headline.

#### Scenario: primary declared before trends
- **WHEN** the analysis change is proposed
- **THEN** it names the primary (radius, threshold) pair and cites this requirement, and the declaration predates any trend computation

#### Scenario: grid still published
- **WHEN** headline results are produced at the primary pair
- **THEN** the same statistic across the full grid is published alongside, so robustness is demonstrated rather than asserted

### Requirement: Disputed-cohort reporting
Every classification run SHALL report the disputed cohort's size and
geography, and the analysis phase SHALL publish the disputed cohort's
temperature trends alongside headline results.

#### Scenario: exclusion is auditable
- **WHEN** N stations are excluded as disputed
- **THEN** the run report lists them with disagreeing layers and a geographic summary, and the analysis presents their trends so a reader can see what exclusion did

### Requirement: Classification frozen before analysis
The classification table SHALL be versioned; the analysis change SHALL
reference a fixed version; classification parameters MUST NOT be revised
in response to temperature results; any reclassification produces a new
version with a changelog entry.

#### Scenario: pre-registration discipline
- **WHEN** temperature analysis begins
- **THEN** it cites a classification table version whose content predates any trend computation

### Requirement: Headline claim scope discipline
Every headline cohort comparison and run-report summary SHALL be framed
as post-1975 urbanisation contamination. Pre-1975 layers (census
density, 1930s Land Utilisation class) SHALL appear only as
control-eligibility screens, one-way corroboration, or context — never
as quantitative evidence of dated change. Any output that would widen
the claim beyond post-1975 requires the phase-two pre-1975 evidence
layer (historic OS maps) as a separate, red-teamed change.

#### Scenario: screen cannot become evidence
- **WHEN** a run report or downstream analysis cites the 1930s survey or census layer
- **THEN** the citation is as eligibility/corroboration only, and the stated claim window remains 1975–2018 (the last sensor-anchored epoch), not "1975–present"

#### Scenario: phase-two gate
- **WHEN** an analysis proposes claims about pre-1975 urbanisation effects
- **THEN** it must reference a deployed pre-1975 evidence capability (not present in this change) or be rejected at review

### Requirement: Raw-and-homogenised comparison committed
The analysis phase SHALL compare cohort trends in both raw MIDAS series
and BOTH genuinely homogenised references — CRUTEM5's adjusted UK
stations AND a self-run pairwise-homogenisation pass. HadUK-grid
SHALL NOT be described or used as a homogenised reference (its input
stations are not homogenised; Hollis et al. 2019).

#### Scenario: the one-line rebuttal is closed
- **WHEN** headline results are produced from raw series
- **THEN** the same cohort comparison against both homogenised references appears in the same output

### Requirement: Cohort viability floor
The configuration SHALL state a minimum control-cohort size and a
geographic-spread requirement (declared before derivation); if a derived
control cohort falls below either, the run SHALL report "insufficient
confirmable control stations" as its outcome rather than weakening any
rule to fill the cohort.

#### Scenario: too-small cohort is an outcome, not a fudge
- **WHEN** the confirmed still-rural cohort at the primary parameters is smaller than the declared floor
- **THEN** the run says so explicitly, publishes the attrition ledger (how many stations each rule removed), and no tolerance is relaxed within that classification version

### Requirement: Exclusion-neutrality reporting
Every classification run SHALL report the disputed and excluded cohorts'
distributions of altitude, coastal distance and latitude against the
confirmed cohort's, so any climatic skew introduced by exclusion is
measured rather than suspected.

#### Scenario: skew is quantified
- **WHEN** exclusions concentrate in high-growth regions
- **THEN** the report shows the resulting distributional shift, and the analysis phase must address any material skew in its matching strategy

### Requirement: External pre-registration deposit
Before the classification run whose outputs it gates (not merely before
trend computation), the frozen package (tolerance config, calibration
data and reference-site rule, cohort definitions, floor values) SHALL be
deposited with an independent timestamping service (Zenodo or OSF), and
the analysis SHALL cite the deposit DOI — upstream parameters cannot be
tuned against cohort composition.

#### Scenario: pre-registration is third-party verifiable
- **WHEN** the analysis is published
- **THEN** a reader can retrieve the deposited package and confirm its timestamp predates the analysis
