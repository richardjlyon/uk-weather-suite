## ADDED Requirements

### Requirement: Scope is control-cohort candidates, derived by rule
The screen SHALL apply to EA-uncovered GB stations that are control-cohort
candidates under a stated rule (rural at the primary ring in the latest
sensor-anchored epoch, with a record length at or above the analysis
change's stated minimum), computed from the classification table — never
a hand-picked list. The candidate count SHALL be published with the
screen.

#### Scenario: the cohort is derived, not chosen
- **WHEN** the screened set is produced
- **THEN** it is reproducible by re-running the stated rule, and the rule and resulting count appear in the run report

### Requirement: Built-up screen by building-symbol detection, not ink fraction
Pre-1975 built-up presence SHALL be measured from the OS Popular Edition,
Scotland (1920–1930) served by the NLS Historic Maps API, as **connected
components of the solid-black building rendering passing stated size,
solidity and aspect filters** — reported as a count of building-like
components and the extent of the largest cluster per ring. An ink-area
fraction SHALL NOT be used and SHALL NOT be compared with GHSL built-up
fraction: at 1:63,360 a single place-name label covers several percent of
a 500 m ring while a three-building farm covers under one percent, and
building symbols are drawn at minimum size (a several-fold area
exaggeration), so an ink fraction measures the rendering, not the ground.

#### Scenario: map furniture does not read as settlement
- **WHEN** a rural ring contains place-name type, spot heights, a parish boundary and rough-pasture limit marks
- **THEN** none pass the component filters, and the ring is not flagged built

#### Scenario: the measure is not commensurable with GHSL, and is not treated as if it were
- **WHEN** the screen result is stored
- **THEN** it is recorded as a distinct quantity with its own units and no threshold is ported from the GHSL layer

### Requirement: Conservative decision rule
Where the component evidence is ambiguous the station SHALL be excluded
from the control cohort rather than admitted, and the count excluded for
ambiguity SHALL be published. Contamination of the control cohort is the
only error that damages the study; over-exclusion costs sample size,
which at this cohort size is affordable and reportable.

#### Scenario: ambiguity resolves against inclusion
- **WHEN** a ring's components neither clearly pass nor clearly fail the filters
- **THEN** the station is excluded from controls with reason `ambiguous-pre1975`, and the total so excluded appears in the cohort report

### Requirement: Licence verified before reliance, with a redistribution-free fallback
The layer's terms SHALL be confirmed verbatim with a retrieval date
before any extract is published — the NLS API page states CC-BY 3.0
while other sources state CC-BY-SA 3.0 and NLS's general image terms are
non-commercial, so the licence is treated as unverified until checked.
If the confirmed terms do not permit redistribution of imagery, the
per-station evidence SHALL be a **georeferenced viewer permalink**
rather than published pixels — licence-neutral, and a reviewer still
sees the map. Required attribution SHALL appear on each published
extract, not only in the licence note.

#### Scenario: the deposit never carries unlicensed imagery
- **WHEN** extracts would enter the deposit under unconfirmed or NC/SA-incompatible terms
- **THEN** permalinks are deposited instead, and the substitution is recorded

### Requirement: The rule decides; extracts are evidence, not input
The decision rule and its parameters SHALL be frozen, published and
hashed **before any extract is viewed** and before any temperature
series is joined. Extracts are audit artefacts for readers, never an
input to cohort membership. Any override of the rule SHALL be a
numbered, reason-coded, published exception, and cohort results SHALL be
reported both with and without overrides — so discretion becomes a
measured sensitivity rather than an unbounded liberty.

#### Scenario: no discretionary control selection
- **WHEN** a station's membership is decided
- **THEN** it follows from the frozen rule alone, and the extract exists so a reader can check the rule's verdict — not so an author could revise it

#### Scenario: overrides are bounded and visible
- **WHEN** any override is applied
- **THEN** it carries a number and a reason code, appears in the report, and the headline is published with and without it

### Requirement: Map-artefact hazards treated
The implementation SHALL state and test its treatment of hazards
specific to scanned early-20th-century OS mapping: exaggerated road and
railway symbol widths (which inflate apparent development — a stated
buffer treatment, with ring area lost to it reported), JPEG tile
compression artefacts at boundaries (smoothing at a stated window before
measurement), sheet edges and marginalia, and georeferencing
registration error relative to the smallest ring.

#### Scenario: symbol width does not manufacture urbanisation
- **WHEN** a rural station's ring contains a main road drawn at exaggerated width
- **THEN** the stated buffer treatment applies, the affected area is reported, and the station is not flagged built on symbology alone

#### Scenario: registration error bounds the finest ring
- **WHEN** the 500 m ring is measured
- **THEN** the stated georeferencing accuracy is compared against it, and rings finer than the error bound are reported as unreliable rather than precise

### Requirement: Instrument calibration against the EA-screened overlap
Because England/Wales are screened by a land-use vector source and
Scotland by this map-based one — and the instrument boundary coincides
with the boundary of the long-record rural cohort — the OS route SHALL
be run over EA-screened stations and its 2×2 agreement with the EA
decision published. The Scottish operating point SHALL be set to the one
that reproduces EA decisions, with the edition caveat stated (the API's
England/Wales tiles are the New Popular 1945–47, a different edition and
symbology, so the calibration bounds the instrument gap rather than
eliminating it).

#### Scenario: the instrument gap is measured, not merely disclosed
- **WHEN** the screen is applied to Scotland
- **THEN** its false-negative and false-positive rates against the EA decision are published from the overlap, and the operating point cites them

#### Scenario: failing calibration triggers the floor immediately
- **WHEN** the agreement table shows the OS route cannot reproduce EA decisions at any operating point
- **THEN** the honest floor is taken at once — Scotland's stations excluded with the measured reason — and no tuning toward a preferred cohort occurs

### Requirement: Independent corroboration where free
The 10 km ring result SHALL, where the comparison is available, be
checked against published hectad urban proportions (Suggitt et al. 2023, CC-BY-NC — a check, never
redistributed) as a **gross-error detector only**: it fires where hectad
urban is high and this screen reports unbuilt. It is not an agreement
metric — the hectad is a 100 km² square against a 314 km² disc offset by
up to 7 km, and its urban class derives from the same Land Utilisation
Survey red category whose ambiguity (buildings mixed with cliffs and
quarries) this design exists to avoid, so it is not independent.

#### Scenario: corroboration flags gross error, nothing finer
- **WHEN** hectad urban is high and the screen reports unbuilt
- **THEN** the station is flagged for inspection; smaller discrepancies are not treated as disagreement, and geometry and non-independence are stated wherever the comparison appears

### Requirement: Honest floor
If the screen cannot be made to work to the stated hazard treatments, or
the API layer proves unavailable, the affected stations SHALL be
excluded from the control cohort with the measured reason recorded — the
same posture as the Northern Ireland exclusion — rather than screened
unreliably or admitted unscreened.

#### Scenario: failure is survivable and visible
- **WHEN** the screen is abandoned for some or all stations
- **THEN** the cohort report states how many stations were excluded, and why, with the evidence that led to it
