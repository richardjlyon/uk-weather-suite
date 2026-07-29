## ADDED Requirements

### Requirement: Fixed classification version
All cohort work SHALL consume a single, cited, externally deposited
classification version (DOI); the analysis SHALL fail loudly if the
deposit's checksums do not match the local table.

#### Scenario: no undeposited classification
- **WHEN** the pipeline starts
- **THEN** it verifies the classification table against the deposit manifest and aborts on mismatch

### Requirement: Matched-pair primary endpoint
The primary endpoint SHALL be the matched-pair difference in Tmin
anomaly trend (1975–2018) between urbanised and confirmed-still-rural
stations at the 2 km ring and calibrated tolerance, with pairs matched
on altitude band, coastal distance band, latitude band, and instrument
era where known; pair-distance caps, control reuse weighting, and
cluster-robust errors at the shared-control level SHALL be specified in
the frozen config. Cohort statistics SHALL be regionally weighted.

#### Scenario: exactly one primary
- **WHEN** results are reported
- **THEN** one pre-registered primary endpoint is identified as such, and every other statistic is labelled secondary or robustness

#### Scenario: unknown instrument history is a robustness cut
- **WHEN** pairs include stations with unknown instrument history
- **THEN** the headline is also reported for the known-era-only subset, and both appear together

### Requirement: Regional weighting defined
The regional weighting scheme SHALL be named in the frozen config —
equal-area cells over the UK (Northern Ireland included) with a
stated cell size and a stated
empty-cell rule — before any cohort statistic is computed; cell
definitions are part of the deposit.

#### Scenario: no tunable geography
- **WHEN** cohort statistics are regionally weighted
- **THEN** the cells, weights and empty-cell rule are those in the deposit, and no alternative weighting appears unless labelled robustness

### Requirement: Effective-cluster safeguards
Where controls are reused across pairs, uncertainty SHALL use
cluster-robust errors at the shared-control level with a wild-cluster
bootstrap when the effective number of clusters is small (threshold
stated in config).

#### Scenario: few clusters handled honestly
- **WHEN** a comparison rests on few effective control clusters
- **THEN** wild-cluster bootstrap intervals are reported and the effective cluster count is stated

### Requirement: Calibration-site exclusion
Stations that served as classifier calibration reference sites SHALL be
excluded from analysis cohorts, or the headline SHALL additionally be
reported with them excluded; the run report lists any overlap.

#### Scenario: no tolerance circularity
- **WHEN** cohorts are built
- **THEN** the overlap with calibration sites is zero or the exclusion-robustness headline is published alongside

### Requirement: Fingerprint battery with pre-registered decision rule
The analysis SHALL report, as secondary confirmatory tests: seasonal
Tmin-vs-Tmax asymmetry; calm-vs-windy stratification (strata as
seasonal terciles of each station's own wind distribution); dose–response
of trend against continuous built-up change; a stacked event-study
against never-treated matched controls (Callaway–Sant'Anna-style;
two-way fixed-effects DiD barred) with a pre-registered event-time
convention for interval-dated change; and the diurnal profile. The
deposit SHALL contain a decision rule naming must-pass fingerprints,
the effect of any reversed-sign fingerprint, and the pattern that
refutes; the battery SHALL carry a stated battery-level multiplicity
control. Must-pass eligibility SHALL be conditioned on demonstrated
synthetic power (at least a stated level at the materiality threshold,
from the synthetic power curve), and the rule SHALL distinguish
"failed with adequate power" (counts against the claim) from "failed
underpowered" (counts as absent) — a true positive cannot be executed
by an underpowered fingerprint, and the must-pass set cannot be
curated to be unfailable.

#### Scenario: outcomes are judged by the rule, not narrated
- **WHEN** the battery completes
- **THEN** the report applies the deposited decision rule verbatim and states the resulting claim grade; no post hoc weighing of fingerprints appears

#### Scenario: wind and diurnal fingerprints gated by data reality
- **WHEN** a station's overnight hourly wind coverage fails the stated completeness gate (manual-era stations often reported few overnight hours)
- **THEN** it is excluded from the calm/windy and diurnal fingerprints with a reason code, those fingerprints are reported for the AWS-era subset openly, and anemometer exposure is named as a limitation

### Requirement: FDR discipline
All station-level test collections SHALL be evaluated under
Benjamini–Hochberg false-discovery-rate control with α_FDR = 2·α_global
(Wilks 2016); per-station significance outside the FDR framework SHALL
NOT be reported.

#### Scenario: no stippling
- **WHEN** station-level results are mapped or listed
- **THEN** the significant set is the B–H set, and the achieved thresholds are stated

### Requirement: Bound outputs
Every analysis run SHALL publish: disputed-cohort trends alongside the
headline; the full radius × tolerance sensitivity grid; the attrition
ledger; the exclusion-neutrality distributions; a
minimum-detectable-divergence statement derived from the synthetic
power check; the pre-registered materiality threshold with its
justification; the UK urban-climate literature comparison table; and
the FDR-factor sensitivity.

#### Scenario: null is interpretable
- **WHEN** the headline shows no divergence
- **THEN** the report states the smallest divergence the design could have detected, so null and underpowered are distinguishable

### Requirement: Synthetic validation before deposit opening
The full pipeline SHALL be validated end-to-end on synthetic data with
known injected UHI signals (including a zero-signal case) BEFORE the
classification deposit is opened; recovered signals must match injected
ones within stated tolerance, and the injected-zero case must produce a
null. The synthetic suite SHALL include two killer cases, both with
ZERO injected UHI and both required to return null: (1) accelerating
common warming with cohort-correlated break dates whose breaks inject
non-zero step magnitudes drawn from a stated realistic distribution
(date-only breaks would make the test vacuous); (2) cohort-correlated
missingness and attrition sampled from the real network's completeness
metadata (metadata only, never temperatures), since within-support
missing months interacting with own-baseline anomalies under
accelerating warming can fabricate divergence. A stated completeness
rule governs monthly values built from partial days.

#### Scenario: cohort-correlated breaks cannot fake a signal
- **WHEN** the synthetic world has nonlinear common warming, urban stations breaking earlier with realistic step magnitudes, and no UHI
- **THEN** the pipeline reports null, or the design is revised before any real data is touched

#### Scenario: cohort-correlated missingness cannot fake a signal
- **WHEN** the synthetic world reproduces the real network's cohort-differential gaps and closures with no UHI
- **THEN** the pipeline reports null, or the design is revised before any real data is touched

#### Scenario: pipeline proves itself blind
- **WHEN** the synthetic suite runs
- **THEN** injected signal is recovered, injected zero yields null, and both results are part of the deposited pre-registration package
