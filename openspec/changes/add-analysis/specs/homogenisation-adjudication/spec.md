## ADDED Requirements

### Requirement: Benchmarked own-PHA with a pass criterion
The primary adjudication SHALL be raw MIDAS vs our own
pairwise-homogenisation output. Before adjudicating anything, that
implementation SHALL be benchmarked on obtained-and-re-archived
benchmark worlds with truth files — COST-HOME (Venema et al. 2012;
the canonical hosting has link-rotted, so the copy is sourced from the
authors/journal supplement and re-deposited with our package), with the
Killick (2021) comparison suite as named fallback — against a
**pre-registered minimum skill criterion** relative to the published
Venema-2012 contributions. Merely measuring skill is not the gate:
failing the criterion demotes own-PHA and installs an established
implementation (NOAA PHA) as adjudicator. HadUK-grid SHALL NOT appear
as a homogenised reference.

#### Scenario: benchmark before verdicts
- **WHEN** the own-PHA pass is used on real data
- **THEN** its benchmark skill, the pass criterion, and the re-archived benchmark data all predate that use in the deposit

#### Scenario: failing the criterion has a consequence
- **WHEN** own-PHA falls short of the pre-registered skill criterion
- **THEN** NOAA PHA adjudicates and own-PHA is reported as a robustness arm only

### Requirement: CRUTEM5 as bounded context
CRUTEM5 comparison SHALL be restricted to the common-station subset,
with N stated prominently, labelled context rather than adjudication
(CRUTEM5's UK coverage is a small fraction of the network and its
adjustments are NMS-supplied and non-uniform).

#### Scenario: no population sleight of hand
- **WHEN** CRUTEM5 numbers appear
- **THEN** they are computed on the common subset only, N is stated beside them, and no cross-population difference is described as an effect of homogenisation

### Requirement: Blind adjudicating pass with structural diagnostics
The adjudicating pass — whichever implementation it is, own-PHA or the
NOAA PHA fallback — SHALL run blind to
classification labels, apply one documented algorithm to all stations,
publish its adjustment log (station, date, magnitude), AND publish a
neighbour-network cohort-composition diagnostic — the cohort mix of
every station's adjustment neighbourhood — because label-stripping
alone cannot make neighbour-based adjustment cohort-blind where urban
stations have urban-dominated neighbourhoods.

#### Scenario: structural blindness is measured, not asserted
- **WHEN** the own-PHA pass runs
- **THEN** the neighbourhood cohort-composition distribution is published per cohort, and any shared-signal blindness risk it reveals is carried into the interpretation

### Requirement: The seeding question answered
The report SHALL directly address the project's seeding hypothesis: does
homogenisation move still-rural stations' trends toward their urbanised
neighbours' (adjustment direction and magnitude by cohort), or does it
remove the urban signal as Hausfather et al. (2013) found for USHCN?

#### Scenario: the US question, UK answer
- **WHEN** the adjudication (raw vs own-PHA, CRUTEM5 context) completes
- **THEN** the report quantifies per-cohort adjustment direction, so the "rural follows the towns" claim is confirmed, refuted, or bounded for the UK
