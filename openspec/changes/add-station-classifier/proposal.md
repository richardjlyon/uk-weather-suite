# Proposal: add-station-classifier

## Why

The project's central question — does urbanisation around UK weather
stations show up in the temperature record? — requires every station to
carry a time-varying, defensible classification of its surroundings, and
an equally defensible history of the station itself. Richard agreed the
design 2026-07-28 after methodology research (vault: Research/Deep
2026-07-28); revised same day after independent adversarial review
(4 fatal, 4 serious findings — see design.md "Red-team dispositions").

## Headline claim scope (decided by Richard, 2026-07-28)

The headline claim of the eventual analysis is **post-1975 urbanisation
contamination**: whether stations whose surroundings urbanised within
the satellite record (1975–2018, the last sensor-anchored epoch) show
divergent temperature trends
against stations confirmed still-rural. Nothing in this change licenses
a quantitative claim about pre-1975 urbanisation — the satellite layers
cannot see it, and the census and 1930s-survey layers are eligibility
screens, not change-daters. The pre-1975 question is real (most British
station-engulfing was interwar and post-war) and is deferred to an
explicit phase-two change (see Deferred work), not quietly absorbed.

## What Changes

- New `ukweather` classification pipeline (Python) producing per-station,
  per-epoch classification and station-history tables as Parquet.
- **Station history (backbone)**: per-station timeline from MIDAS
  capability/metadata files — coordinates, altitude, operating years,
  and instrument/observation changes where derivable (the manual→AWS
  transition is a required, spec'd break class, not prose). Any
  coordinate, altitude or instrument-era change is a segment break.
  Station-move semantics (same id amended vs new id) verified against
  the data, not assumed. Coordinate precision recorded per station;
  500 m-ring results are flagged where precision is coarser than 100 m.
- **Primary measure (continuous)**: built-up fraction from GHSL
  GHS-BUILT-S (100 m) within rings of 500 m, 2 km, 10 km, computed over
  the *land* area of each ring. Every epoch is tagged sensor-anchored /
  interpolated / projected per the JRC release notes (JRC's "observed"
  epochs are themselves ML estimates anchored to imagery — the tag says
  so honestly); **headline cohorts use sensor-anchored epochs only;
  every epoch pair votes with a tolerance calibrated for its own sensor
  combination** (see Sensor-step discipline — cross-sensor pairs carry
  wider tolerances, they are not banned).
- **Categorical view**: GHS-SMOD Degree of Urbanisation class per epoch —
  a convenience view derived from the same JRC pipeline as the primary
  measure, and labelled as such (not independent).
- **First-principles validation** (computed by us from raw open data):
  1. spectral indices from raw Landsat/Sentinel-2 scenes: NDVI primary,
     NDBI corroborative; growing-season composites only; available from
     1984 (earlier sensors lack the required band — stated, not fudged);
  2. census population density in the 10 km ring per census decade,
     1801+ (no 1941 census — documented), used **one-way**: growth can
     confirm urbanisation; absence of growth never disputes it.
- **Pre-satellite baseline — 1930s Land Utilisation Survey**: Dudley
  Stamp's contemporary field survey (Urban/Suburban/Arable/etc.). EA's
  digitised, georeferenced dataset covers England, Wales and southern
  Scotland (~55.8° N) under the **EA Conditional Licence (non-commercial
  — never described as "open")**; stations north of that extent are
  screened from the NLS's georeferenced full-GB Land Utilisation sheets
  by the same ring protocol, and a station with no survey coverage is
  flagged `no-stamp-coverage`, never silently classified. Used as a
  **binary control-eligibility screen**: control-cohort stations must
  already be rural in the 1930s survey. Control candidates are
  additionally screened against open airfield gazetteers and post-war OS
  mapping (runways and aprons are invisible to building-footprint
  rasters and censuses alike). This armours the
  control cohort against pre-1975 engulfment it can detect, but it is a
  level check at one period — it cannot date or quantify change between
  the 1930s and 1975 (a WWII airfield built in 1942 next to a 1930s-rural
  station is invisible to it and to the census). The headline claim is
  therefore narrowed to post-1975 contamination regardless (see Headline
  claim scope). Audit trail: georeferenced period OS map extracts (NLS
  Historic Maps API, attribution) published for any station on request.
- **Sensor-step discipline**: every epoch pair's change tolerance is
  **derived from measured error at that pair's sensor combination** on a
  rule-defined reference-site set — cross-sensor pairs (MSS→TM 1975→1990,
  ETM+→OLI 2000→2014, OLI→S2 2014→2018) are not banned but carry their
  own, wider calibrated tolerances, so change evidence spans 1975–2018
  while sensor steps cannot masquerade as urbanisation. The spectral
  layer is calibrated the same way per sensor pair. Reference sites are
  admitted by an external citable rule, stratified by the land-cover
  classes of candidate control stations, published with audit extracts
  before calibration. Site admission requires continuous
  statutory protection predating 1975 plus zero *current* mapped
  building footprint — criteria whose datasets exist, unlike a 1975
  footprint layer. The tolerance construction is **studentised
  familywise**, fixed here and not tunable: each pair's no-change spread
  s_p is estimated per stratum on the reference sites; one critical
  value c is the 99th percentile of max over admissible pairs of
  |Δ_p|/s_p; each pair's tolerance is c × s_p — per-pair and
  cross-sensor-wider, with a single familywise false-ejection bound.
- **Numeric agreement rule** (structure frozen in spec; tolerances
  derived): each layer classifies each station-epoch as
  changed/unchanged on explicitly aligned epoch pairs (the alignment
  mapping is part of the spec); tolerances come from the reference-site
  calibration, are recorded in a versioned config, and the whole package
  is **externally deposited (Zenodo/OSF) before the classification run
  whose outputs it gates** — upstream parameters cannot be tuned against
  cohort composition either —
  pre-registration is timestamped by a third party, not self-attested.
  `confirmed` requires all voting layers with data to agree;
  disagreements are flagged `disputed` with layers named. The disputed
  cohort's size, geography, *climatic representativeness* (altitude,
  coastal distance, latitude vs the confirmed cohort) and — in the
  analysis phase — temperature trends are published alongside headline
  results, so exclusion is auditable and demonstrably neutral.
- **Cohort viability floor**: the spec states a minimum control-cohort
  size and geographic-spread requirement; if the machinery yields less,
  the honest output is "insufficient confirmable control stations", not
  a quietly weakened rule.
- **Confidence tiers**: 1975-epoch and pre-1975 classifications carry
  explicit lower-confidence markers (GHSL's weakest observed epoch;
  census-only coverage respectively).
- **Met Office WMO siting classes**: descriptive metadata only.
- Sensitivity: full radius × threshold grid retained as robustness; the
  analysis phase MUST pre-register a single primary (radius, threshold)
  pair before any trend is computed.

## Analysis-phase commitments (binding on the later analysis change)

Stated here so the classifier is built to serve them:
- Identification strategy: within-segment trend comparison and matched
  station pairs, stratified on altitude, coastal distance and latitude,
  with a common-altitude-band robustness cut.
- Comparison against raw MIDAS series AND CRUTEM5's adjusted UK
  stations AND a self-run pairwise-homogenisation pass (both, not
  either — NOT HadUK-grid, whose input stations are not homogenised per
  Hollis et al. 2019), so the result cannot be dismissed as "analysing
  data everyone agrees is contaminated".

## Capabilities

### New Capabilities
- `station-history`: per-station segment timeline (location, altitude,
  operating years, breaks) from MIDAS metadata.
- `builtup-extraction`: GHSL built-up fraction and SMOD class in
  land-masked rings, per epoch, with observed/interpolated provenance.
- `first-principles-validation`: self-computed spectral indices, census
  density, and the 1930s Land Utilisation Survey baseline screen, with
  the derived-tolerance cross-modality agreement rule and reference-site
  calibration.
- `classification-table`: versioned per-station per-epoch classification
  Parquet with confidence tiers, cohort derivation and disputed-cohort
  reporting.

### Modified Capabilities

(none)

## Deferred work (phase two, explicit)

- **Pre-1975 quantitative evidence layer**: dating and quantifying
  urbanisation between the 1930s survey and 1975 from digitised historic
  Ordnance Survey sheets (NLS georeferenced collections span multiple
  revisions per site), optionally with the Land Utilisation Survey used
  quantitatively rather than as a screen. This is the only
  first-principles route to the interwar/post-war engulfing story, and
  it would widen the headline claim beyond post-1975. It is a separate
  change with its own red-team pass, to be proposed after the post-1975
  classifier has run end-to-end — the ring/cohort/agreement machinery
  proven here is reused as-is.

## Non-goals

- No temperature analysis in this change (classification frozen first —
  pre-registration discipline).
- No pre-1975 quantitative change detection in this change: the census
  and 1930s-survey layers screen and corroborate but never date change;
  the headline claim stays post-1975 until the phase-two layer exists.
- No load-bearing use of Met Office siting classes, ONS rural-urban
  classes, or LCZ maps.
- No manual station-by-station classification (not reproducible at 1,537
  stations); micrositing (the car park by the sensor) is explicitly out
  of scope — this method operates at neighbourhood scale, 100 m+.
- No hindcasting of satellite measures before their sensors existed.
