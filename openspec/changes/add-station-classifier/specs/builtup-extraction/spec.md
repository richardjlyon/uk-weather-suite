## ADDED Requirements

### Requirement: GHSL ring extraction
The system SHALL compute, for every station and every GHSL epoch
(1975–2025, 5-yearly), the built-up fraction within rings of 500 m, 2 km
and 10 km of the station coordinate, using area-weighted pixel
intersection, with the denominator being the land area of the ring.

#### Scenario: fraction is area-weighted
- **WHEN** a 100 m pixel lies partly inside the 500 m ring
- **THEN** its built-up contribution is weighted by the intersected area, not counted whole or dropped

#### Scenario: every station, every epoch
- **WHEN** extraction runs over the station table
- **THEN** the output holds one row per station × epoch × ring with no silent gaps; missing raster coverage is an explicit null with a reason code

#### Scenario: coastal ring uses land denominator
- **WHEN** 60% of a station's 10 km ring is sea
- **THEN** the built-up fraction is computed over the remaining land area, and the land fraction is stored alongside

### Requirement: Epoch provenance tagging
The system SHALL tag every GHSL epoch value per the JRC release
documentation as one of: sensor-anchored (raster epoch coincides with
an observation: E1975 MSS, E1990 TM, E2000 ETM+), **anchor-carrier**
(raster interpolated/extrapolated per JRC but carrying a named
observation at a recorded offset: E2015 carries OLI-2014, E2020 carries
S2-2018), interpolated, or projected. Downstream headline cohort
derivation SHALL use sensor-anchored and anchor-carrier epochs only,
and the claim window ends at the latest *observation* year (2018) —
E2020 is a carrier raster, never a claim endpoint.

#### Scenario: interpolated epoch never headline
- **WHEN** a cohort derivation runs
- **THEN** epochs tagged interpolated or projected are excluded from cohort membership decisions, while remaining available as context

#### Scenario: anchoring sensor recorded
- **WHEN** a sensor-anchored epoch value is stored
- **THEN** the anchoring sensor generation (MSS, TM/ETM+, OLI, S2) is stored with it

### Requirement: Per-pair sensor-step calibration
Every GHSL epoch pair SHALL carry a change tolerance derived from that
pair's carrier combination, per the explicit carrier schedule: MSS 1975
(E1975), TM 1990 (E1990), ETM+ 2000 (E2000), OLI 2014 (carried by
E2015, blended toward S2), S2 2018 (carried by E2020, extrapolated
+2 yr) — measured on the reference-site set; cross-sensor pairs are not
excluded but vote with their own, wider calibrated tolerances, so
sensor steps cannot masquerade as urbanisation while change evidence
spans observations from 1975 to 2018.

#### Scenario: cross-sensor pair votes with its own tolerance
- **WHEN** a station's built-up fraction rises between the E2015 (OLI-2014 carrier) and E2020 (S2-2018 carrier) rasters by more than that pair's calibrated no-change tolerance
- **THEN** the pair casts an urbanised vote, and the applied tolerance, carrier offsets and calibration provenance are recorded with the vote

#### Scenario: taxonomy is explicit
- **WHEN** any epoch pair is evaluated
- **THEN** its sensor combination is taken from the stored anchoring schedule, never inferred ad hoc

### Requirement: Rule-defined reference sites
The reference-site set SHALL be admitted by an external citable rule
whose inputs exist as published datasets: protected-area core parcels
(NNR/SSSI) protected from before 1975 and currently protected, with no
de-notification on record, intersected with zero *current* mapped
building footprint (OS OpenMap Local / OSM) — no 1975 footprint layer
exists and none is pretended — stratified by the land-cover classes of
candidate control stations, and published with imagery audit extracts
BEFORE calibration runs. Author judgement SHALL NOT admit or remove
individual sites; the citation parser is a rule input, its version and
content hash frozen in the deposit before the full run, and any
post-freeze parser change is a dated amendment reported with the
admitted-count delta it caused.

Protection start SHALL be taken from the site's ORIGINAL statutory
notification date — the 1949-Act notification or "first notified" date
(England citation PDFs; Wales `first_notified` / NNR `DEC_DATE`) —
never a 1981-Act renotification or "confirmed" date, which post-dates
1975 in every case and is silent on when protection began. The rule
tests protection start and current designation; it does not observe
intervening lapses. Sites appearing in a published de-notification
record are excluded in whole; a partial de-notification abstains with
`boundary-history-unresolved`. The de-notification source is named per
country in the deposit; where no published register exists, the screen
is recorded for that country as unperformed, never as passed. The
residual assumptions — that no undocumented lapse occurred, and that no
boundary change went unrecorded in the source — are declared in the
deposit as assumptions, not findings.

A date is admitted for the site's *current mapped polygon* only: where
the source records a boundary-change indicator — a predecessor-site
note, an extension or partial de-notification note, or a Date of
Revision — post-dating the original date, the site abstains with reason
code `boundary-history-unresolved`, unless the current polygon is shown
to lie within the boundary in force at the original date by a published
historic boundary dataset named in the deposit before the run (no such
dataset is known as of writing; absent one, all such sites abstain). A
Date of Renotification alone SHALL NOT trigger abstention: the 1981-Act
renotification was near-universal and is not evidence of boundary
change. The deposit SHALL report the admitted count under each
boundary-change indicator separately and under both renotification
readings (renotification-triggering and not). Where a country's date route
carries no boundary-history information (a GIS field rather than a
citation), the boundary screen is recorded for that country as
unperformed, never as passed; where that country's citations are read
for parser validation, their boundary-change indicators are applied
under the same rule. Calibration SHALL NOT proceed if the stratum with
the largest admitted count falls below the pre-registered minimum
n = 20 — a collapse of the admitted set is a halt and a report, never a
quietly wider tolerance. The per-country date fields are not assumed
equivalent: the
deposit SHALL record each source's published definition, and the
England parser SHALL be validated before calibration against a
manually-read England sample (unconditional) and against Welsh
citations where the deposit records them as machine-readable — if not,
the Wales check is recorded as unperformed, never as passed.

Where a country publishes no original-date route for a designation
type, every site of that type in that country SHALL abstain with an
explicit per-country, per-designation reason code recorded in the
deposit (country coverage lives in a dated table there, not in this
rule), and the resulting stratum thinning declared — abstention is a
disclosed limitation, never a silent relaxation to "currently
protected". The direction of abstention's effect on either hypothesis
is not assumed: the deposit SHALL report cohort composition by country,
and the primary analysis SHALL be repeated with stations excluded whose
gating stratum fell below n = 20 admitted sites and therefore used the
widest-stratum fallback. Any later acquisition of
original dates for an abstaining country is a versioned, dated
amendment reported as a declared secondary analysis alongside the
frozen primary — never a silent re-freeze.

#### Scenario: no hand-picked sites
- **WHEN** the reference list is produced
- **THEN** every member cites the rule inputs that admitted it, and the rule (not a curated list) is what the deposit freezes

#### Scenario: renotification never substitutes
- **WHEN** no original notification date can be established for a site
- **THEN** the site is not admitted; it abstains with reason code `no-original-date`, sub-coded (`renotification-only`, `original-field-blank`, `original-field-absent`, `no-text`) and reported per sub-code in the deposit — a blank or absent original-date field is never read as evidence of any notification year. An identity failure — a citation whose parsed site name does not match the layer — abstains under the distinct top-level code `identity-unverified`, because the citation may hold a sound date that cannot be proven to belong to this polygon

#### Scenario: revision after the original date is not silently ignored
- **WHEN** a citation carries a boundary-change indicator — a predecessor-site note, an extension or partial de-notification note, or a Date of Revision — post-dating the original notification
- **THEN** the indicator date and note text are stored with the record, and the site abstains with `boundary-history-unresolved` rather than being admitted on the original date; a Date of Renotification alone does not trigger this

#### Scenario: per-country abstention is explicit
- **WHEN** a country publishes no original notification date for a designation type
- **THEN** every site of that type in that country abstains with a reason code, the abstention and its stratum thinning appear in the deposit's dated country-coverage table, and the rule is not relaxed to admit them

#### Scenario: citation identity verified before a date is accepted
- **WHEN** an England date is read from a citation PDF
- **THEN** the PDF is fetched by the layer's `hyperlink` key (never `ref_code`, which resolves to a different site), the parsed site name is asserted against the layer name, and a name mismatch abstains as `identity-unverified` while a scanned image or unparseable citation abstains under `no-original-date` — never a guessed or defaulted date

#### Scenario: missingness is measured, not assumed
- **WHEN** the citation fetch completes
- **THEN** the deposit reports reason-code counts cross-tabulated by land-cover stratum, and the parser's recovery rate measured against a random sample of at least 50 England citations plus ALL `no-text` citations (or a random 50 of them if more exist), dates established by manual reading and deposited, and against Welsh `first_notified` ground truth where Welsh citations are recorded as machine-readable — so the age distribution of unparseable English citations is measured, not inferred from a different country's documents

#### Scenario: stratified error, not moorland error
- **WHEN** tolerances are derived
- **THEN** each land-cover stratum yields its own no-change distribution, and a station is gated by its own stratum's tolerance (or the widest among strata meeting n ≥ 20, where its own stratum's admitted count is below n = 20)

### Requirement: Studentised familywise tolerance construction
Tolerances SHALL be constructed as follows, fixed here and not
configurable: for each epoch pair p and land-cover stratum, the
no-change spread s_p is estimated on the reference sites; a single
critical value c is the 99th percentile of the reference-site
distribution of max over admissible pairs of |Δ_p|/s_p; each pair's
tolerance is c × s_p. This yields per-pair, cross-sensor-wider
tolerances AND one familywise false-ejection bound — the same
construction, not two competing rules. The division of labour is
stated in the deposit: each stratum's n ≥ 20 supports only its spread
estimate s_p; the 99th-percentile critical value c is taken from the
pooled reference-site distribution, never per stratum.

#### Scenario: multiple testing does not eject the control cohort
- **WHEN** a genuinely unchanged station is evaluated across all its admissible pairs and layers
- **THEN** its familywise false-ejection probability is bounded by the single critical value, not multiplied per test

#### Scenario: quiet pairs keep narrow gates
- **WHEN** the E2015→E2020 pair's spread is far smaller than E1975→E1990's
- **THEN** its tolerance c × s_p is correspondingly narrower — recent urbanisation is not gated at MSS-era width

#### Scenario: extrapolated-carrier disclosure
- **WHEN** calibration and classification run
- **THEN** E2020-involving pair spreads are published separately, and the run report includes a robustness cohort comparison with all E2020-involving pairs excluded, with disclosure if any cohort membership flips (JRC's extrapolation model can project growth at non-pristine stations that zero-footprint reference sites cannot exhibit)

### Requirement: Minimum-detectable-change disclosure
The calibration report SHALL publish, per stratum: the reference-site
count, and each pair's tolerance expressed as the minimum detectable
built-up change per ring — so a null result can be distinguished from an
underpowered one.

#### Scenario: power is stated, not assumed
- **WHEN** the analysis reports no cohort divergence
- **THEN** the reader can see what magnitude of urbanisation the classifier could have detected, per pair and ring

### Requirement: SMOD class capture
The system SHALL record the GHSL Degree of Urbanisation (SMOD) class at
each station location for each epoch, stored as the published class code,
uninterpreted, and documented as a convenience view derived from the same
JRC pipeline as GHS-BUILT-S — not an independent layer, and never a voter
in the agreement rule.

#### Scenario: class code preserved
- **WHEN** SMOD codes a station's cell as 13 (rural cluster)
- **THEN** the table stores 13, and any coarser urban/rural grouping is derived downstream, never at ingest

### Requirement: Reproducible tile provenance
The system SHALL record, for every extraction, the GHSL product name,
release version, tile id and download checksum, so any value can be traced
to a specific published raster.

#### Scenario: provenance survives to output
- **WHEN** a built-up fraction appears in the classification table
- **THEN** the raster release and tile it came from are recoverable from stored metadata
