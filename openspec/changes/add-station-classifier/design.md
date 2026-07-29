# Design: add-station-classifier

## Shape

Python (`ukweather`, uv): raster/geo work where the ecosystem (rasterio,
shapely, pyproj, duckdb) beats Rust and compute is modest (1,537 stations
× epochs × 3 rings). If extraction proves slow, batch rings per raster
tile.

Modules:
- `ukweather.stations` — station-history table from MIDAS capability
  files: coordinates (+ stated precision), altitude, operating years,
  segment breaks (any coordinate, altitude or instrument-era change),
  move-semantics verification, unknown-instrument-history flags.
- `ukweather.ghsl` — GHS-BUILT-S + GHS-SMOD tiles per epoch;
  area-weighted ring extraction over land-masked rings; epoch provenance
  (observed/interpolated/projected) from JRC release documentation.
- `ukweather.spectral` — Landsat Collection 2 (TM onward, 1984+) and
  Sentinel-2: growing-season (May–Sep) cloud-free composites per ring per
  decade; NDVI primary, NDBI corroborative; per-sensor harmonisation
  documented.
- `ukweather.census` — GB population per census decade 1801+ (1941 gap
  documented), 10 km ring only, one-way check.
- `ukweather.stamp` — 1930s Land Utilisation Survey (EA digitised open
  dataset): dominant class per ring; binary rural screen for control
  eligibility; NLS Historic Maps API extracts for audit (attribution).
- `ukweather.classify` — join layers on aligned epochs, apply the numeric
  agreement rule, emit versioned classification Parquet + run report.

## Key decisions

- **Rings 500 m / 2 km / 10 km**; fractions over land area (coastal
  stations otherwise structurally deflated).
- **Continuous-first**; cohorts derived; full sensitivity grid retained,
  but the analysis phase pre-registers one primary (radius, threshold)
  pair before any trend is computed — the grid is robustness, not a menu.
- **Headline on sensor-anchored GHSL epochs only** (~1975 MSS, 1990/2000
  /2014 Landsat, 2018 S2 per JRC — themselves ML estimates anchored to
  imagery, tagged honestly); interpolated epochs are context, never
  headline; every pair votes with its own sensor-combination-calibrated
  tolerance (cross-sensor wider, never banned).
- **Agreement rule (structure frozen; tolerances derived)**: votes on
  named comparison windows per an explicit epoch-alignment mapping;
  layers without data abstain (recorded); every epoch pair votes with a
  tolerance calibrated for its own sensor combination (cross-sensor pairs
  wider, never banned), evaluated at the pre-registered primary radius;
  the percentile and familywise rule are fixed in the spec (99th of
  no-change max-|Δ|), all in one versioned config.
  Changing anything is a new classification version. The whole frozen
  package is externally deposited (Zenodo/OSF) before analysis.
- **Disputed cohort is reported, not buried**: size, geography, and
  (analysis phase) its temperature trends appear alongside headline
  results.
- **Identification** (analysis-phase commitment): within-segment
  comparisons and matched pairs stratified on altitude, coastal distance,
  latitude; robustness cut to a common altitude band (< 300 m).
- **Altitude**: (1) constant offsets cancel in within-station
  trends/anomalies; (2) cohort confounding handled by
  matching/stratification; (3) any altitude change = segment break.
- **Headline claim scope**: post-1975 contamination only. The 1930s LUS
  screen hardens control eligibility but cannot date 1930s→1975 change
  (WWII airfields, non-residential development are invisible to both it
  and the census), so it does not license a broader claim. Claiming only
  what the evidence floor supports is the defence; the pre-1975 story is
  phase two (historic OS maps), reusing this machinery unchanged.
- **Institutional-risk posture**: GHSL is the primary *convenience*
  measure; the independence claim applies strictly to the self-computed
  validation layers (raw-band arithmetic, census tables). SMOD shares
  GHSL's pipeline and is labelled non-independent.
- **Coordinate care**: MIDAS lat/lon vs GHSL Mollweide vs BNG through
  pyproj, tested against known landmarks.

## Red-team dispositions (review of 2026-07-28)

| # | Finding | Disposition |
|---|---|---|
| 1 | Station moves/instruments unhandled; survivorship | `station-history` capability added; segment breaks; matched-pair identification committed; survivorship documented in cohort report |
| 2 | GHSL epochs mostly interpolated; motte-and-bailey | Epoch provenance tags; headline on observed only; independence claim reworded |
| 3 | No NDBI before TM (1984) | 1984 floor stated; 1975 epoch downgraded to lower confidence |
| 4 | Agreement undefined; exclusion is selection | Numeric rule + tolerances frozen; disputed cohort published incl. trends |
| 5 | Forking paths | Pre-registered primary pair; grid demoted to robustness |
| 6 | No engagement with homogenised record | Raw + HadUK-grid comparison committed |
| 7 | NDBI bare-soil confusion; sensor drift | Growing-season window; NDVI primary; harmonisation documented |
| 8 | Census can't see airports; 1941 gap | 10 km ring only; one-way check; gap documented |
| 9 | Water in ring denominator; micrositing | Land-masked rings; micrositing scoped out explicitly |
| 10 | SMOD not independent | Relabelled convenience view |

## Red-team dispositions (second review, 2026-07-28)

| # | Finding | Disposition |
|---|---|---|
| N1 | Cross-sensor step changes poison the frozen 0.05 tolerance | Same-sensor change discipline; reference-site calibration; tolerances derived not asserted |
| N2 | Claim shrinks to post-1975; pre-1975 engulfment invisible | Headline claim narrowed to post-1975 (Richard, 2026-07-28); 1930s LUS screen retained as control-cohort armour; pre-1975 OS-maps layer deferred to explicit phase-two change |
| N3 | No cohort floor | Cohort viability floor + attrition ledger requirement |
| N4 | One-way census ejects high-growth-region stations | Exclusion-neutrality reporting (altitude/coast/latitude distributions) |
| N5 | Tolerances arbitrary; rule not executable | Derived tolerances; epoch-alignment mapping in config; abstention semantics; vote radius = primary radius |
| A6 | HadUK-grid is not homogenised (Hollis 2019) | CRUTEM5 adjusted stations and/or self-run pairwise homogenisation; HadUK-grid barred as a homogenised reference |
| A1 | Instrument changes only in prose | Instrument/observation-practice break requirement + unknown-history flag |
| N6 | plan.md ring inconsistency | plan.md corrected to 500 m/2 km/10 km |
| N7 | Coordinate precision untreated | Precision recorded; coarse-location flag at 500 m ring |
| N8 | Self-attested pre-registration | External deposit requirement (DOI cited by analysis) |

## Red-team dispositions (third review, 2026-07-28)

| # | Finding | Disposition |
|---|---|---|
| R3-1 | Same-sensor ban leaves ≤1 change pair; taxonomy self-contradicts | Per-pair calibrated tolerances (cross-sensor wider, not banned); explicit anchoring schedule MSS/TM/ETM+/OLI/S2; spectral layer calibrated identically |
| R3-2 | Stamp screen absent north of ~55.8° N; licence not "open"; airfield hole | NLS full-GB sheets for Scotland; EA Conditional Licence stated accurately; `no-stamp-coverage` flag; airfield gazetteer screen for control candidates |
| R3-3 | Reference sites author-picked; percentile a forking path; deposit too late | Rule-defined sites (NNR/SSSI ∩ zero building footprint), land-cover stratified; percentile + familywise rule fixed in spec; deposit moved before the gating classification run |
| R3-4 | "and/or" homogenised comparison | Both CRUTEM5 and self-run PHA required |

## Risks

- Observed-epoch cadence (~5 points, 1975–2018) is coarse; accepted —
  honesty over resolution.
- Historic census boundaries are third-party digitisations; mitigated by
  10 km-only, one-way use.
- LCM licence may not permit this use; cross-check optional, GHSL + own
  layers suffice.
- Pre-1990 Landsat coverage of GB may be thin even for TM; fall back to
  2 km rings for the 1980s and say so.

## Amendment (versioned): GHSL epoch carriers (approved by Richard, 2026-07-28; red-teamed 2026-07-29)

Discovered at implementation (task 3.2): the shipped GHSL grid is
strictly 5-yearly and contains **no E2014 or E2018 rasters**. The OLI
(2014) and S2 (2018) observations named as sensor anchors in the
builtup-extraction spec are carried by the **E2015** (interpolated
toward OLI-2014) and **E2020** (extrapolated from S2-2018) grids. The
epoch-alignment config SHALL declare E2015 and E2020 as the carriers of
those anchors, with the observation-offset columns
(`nearest_obs_year/sensor`, `obs_offset_years`) making the gap explicit
in every row. This amends the headline-eligible epoch set and is
treated as what it is — a versioned parameter change, recorded before
any calibration run or deposit. The claim window ends at the latest
observation year (2018); E2020 is a carrier raster, never a claim
endpoint. Focused red-team review (2026-07-29) drove the anchor-carrier
tag, the carrier-pair schedule, and the E2020 disclosure/robustness
requirements now in the builtup-extraction spec.

## Data-source pinning (research 2026-07-29, before the layers are built)

- **Reference sites (protected areas)**: Natural England publishes SSSI
  and NNR boundaries under the **Open Government Licence** via
  data.gov.uk and the Natural England Open Data Geoportal — commercial
  use permitted, no licence obstacle to depositing the derived
  reference-site list. Scotland's equivalent (NatureScot) still to be
  pinned; JNCC hosts UK-wide protected-area downloads as a fallback
  route.
- **Census layer**: Great Britain Historical GIS / Vision of Britain
  statistical and boundary data are distributed through the **UK Data
  Service** (study "gbhd"), mostly open licences but **limiting
  commercial use**; crucially, **historic parish boundaries carry a
  stricter licence** — not-for-profit research, teaching or education
  only, no commercial reproduction, since commercial parish-boundary
  licensing is GBHGIS's income. Consequences for this project: (a) the
  census layer is usable for the research and for publication of derived
  statistics, but (b) parish-boundary geometry must NOT be redistributed
  in the Zenodo/OSF deposit — deposit derived densities and boundary
  identifiers plus retrieval instructions instead. Task 1.3's licence
  check must confirm this against the actual UKDS terms at download
  time, and the deposit-packaging step must honour it.

## Airfield-screen source pinning (research 2026-07-29)

No single authoritative open national airfield gazetteer exists with
usable licensing (the candidates found are club/enthusiast maps, KML
exports, or single-council open-data sets). The defensible route is
**OpenStreetMap aeroway features** (`aeroway=aerodrome`, plus
`disused:`/`abandoned:` variants, and `aeroway=runway|taxiway|apron`
geometry where mapped), under ODbL with attribution, queried through the
public Overpass API — no account, and the same ring-fraction arithmetic
the GHSL and Stamp layers already use, so the screen stays
first-principles. OSM's completeness for *disused* wartime airfields is
uneven, so the screen is one-way: an OSM hit flags a station, an absence
never certifies a station clean, and the flagged list is published for
inspection. Post-war OS mapping via the NLS API remains the audit route
for any contested station.

## Amendment (versioned): census layer narrowed to 1981+ (2026-07-29)

Implementation established that the pre-1981 census route recorded in
"Data-source pinning" is stale and worse than an account barrier: the
GB Historical Database's parish-level population series (1801–1951) is
marked "currently unavailable for download" in UKDS's own records,
Vision of Britain no longer offers downloads, and historic parish
boundary geometry is special-request only (gbhgis@port.ac.uk,
non-commercial). Verified open substitutes: **NOMIS** census counts
(no account) for 1981/1991/2001/2011/2021, and **ONS Open Geography
Portal** boundary geometry (OGL) back to 1981 EDs/wards for England
and Wales.

Disposition: the census layer is narrowed to 1981+. This follows the
already-decided claim scope (post-1975 headline) rather than weakening
it — 1981–2021 spans the claim window — and it removes the licence
hazard the earlier pinning flagged, since OGL geometry may be
redistributed where the parish geometry could not. Pre-1981 depth moves
to the deferred phase-two change, conditional on a data request that is
Richard's to send (drafted, unsent). Versioned as a parameter change:
recorded before any calibration run.

## Spectral layer: read resolution and concurrency (measured 2026-07-29)

The first pilot projected roughly 80 hours for a full spectral run,
which is not viable. Measured on Planetary Computer Landsat Collection 2
(6 scenes, 10 km window over Eskdalemuir, warm connection):

| read resolution | mean per read |
|---|---|
| 30 m (native) | 1.26 s |
| 60 m (overview) | 0.28 s |

**Decision: composites are computed from 60 m overview reads**, not
native 30 m. Justification: every reported value is a ring *mean* — the
500 m ring still contains ~218 pixels at 60 m, the 2 km ring ~3,500 —
so the loss of native resolution does not change what is being measured,
while the read cost falls 4.5×. Recorded here as a versioned parameter
because resolution is a property of the measurement, not an
implementation detail; changing it creates a new classification version.

The remaining cost is I/O-bound (remote COG reads), so it parallelises
close to linearly across stations. Together these take the projected run
from ~80 hours to under an hour. Correctness is unaffected: the same
bands, the same growing-season windows, the same cloud masking, the same
scene ids recorded.
