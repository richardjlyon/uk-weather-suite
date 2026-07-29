# Tasks: add-station-classifier

## 1. Data acquisition & licences

- [x] 1.1 Download GHS-BUILT-S and GHS-SMOD UK tiles for all epochs
      1975–2025; record release versions and checksums.
- [ ] 1.2 Verify UKCEH LCM licence for this use; if unusable, drop the
      cross-check and note it in design.md.
- [x] 1.3 Pin the census source (Vision of Britain / UKDS boundaries),
      verify licence, and document the tables used.
- [x] 1.4 Confirm Landsat Collection 2 access path (USGS M2M or AWS open
      bucket) and Sentinel-2 access; no keys in repo.
- [ ] 1.5 Download the EA digitised 1930s Land Utilisation Survey (EA
      Conditional Licence — record exact terms); identify NLS
      georeferenced Land Utilisation sheets covering Scotland; register
      NLS Historic Maps API (free tier) for audit extracts.
- [ ] 1.6 Implement the reference-site admission rule (NNR/SSSI core
      parcels with continuous statutory protection predating 1975 ∩ zero
      current mapped building footprint),
      stratified by candidate-station land cover; publish list + imagery
      audit extracts before any calibration run.
- [x] 1.7 Source open airfield gazetteers (+ post-war OS mapping route)
      for the airfield screen.

## 2. Station history (backbone)

- [x] 2.1 Extract station lat/lon/altitude/operating-years from downloaded
      capability files into the station-history table (TDD): segment
      breaks on any coordinate/altitude change, explicit gaps.
- [x] 2.2 Move-semantics audit: verify empirically whether relocation
      appears as same-id amendment or new id; detect co-located id
      clusters (name stem + proximity + abutting years); document with
      examples.
- [x] 2.3 Survivorship counts: same-era openings vs closures/fragmentation
      for long-record cohort reporting.
- [x] 2.4 Instrument/observation-practice audit: derive AWS-transition and
      equipment breaks where metadata allows; flag unknown histories;
      record coordinate precision per station.

## 3. GHSL extraction (TDD)

- [x] 3.1 Red: tests for area-weighted, land-masked ring extraction
      against a synthetic raster with known fractions (incl. a coastal
      case); CRS round-trip test against a known landmark.
- [x] 3.2 Green: `ukweather.ghsl` extraction over all stations × epochs ×
      rings; observed/interpolated/projected provenance tags from JRC
      release docs; nulls with reason codes for coverage gaps.
- [x] 3.3 SMOD class capture, labelled non-independent, with provenance
      metadata.

## 4. First-principles layers (TDD)

- [x] 4.1 Spectral: growing-season (May–Sep) decadal composites from
      Landsat TM+ (1984 floor enforced, `no-swir-sensor` reason code
      earlier) and Sentinel-2; NDVI primary, NDBI corroborative;
      per-sensor harmonisation documented; tests on a hand-verified
      station pair (one urbanised, one rural).
- [x] 4.2 Census: density in the 10 km ring only, per census decade (1941
      gap documented); one-way growth check; refusal test for fine rings.
- [ ] 4.3 Stamp layer: dominant 1930s class per ring; binary rural screen;
      audit-extract lookup by sheet reference (TDD on a known-urban and
      known-rural 1930s site).
- [ ] 4.4 Calibration run: no-change distributions per sensor-pair (GHSL
      and spectral), per land-cover stratum; tolerances at the spec-fixed
      99th familywise percentile; versioned tolerance config with
      calibration data.
- [x] 4.5 Airfield screen: binary flag for control candidates from
      gazetteers/OS mapping; publish flagged list with sources.

## 5. Classification table

- [ ] 5.1 Numeric agreement rule from versioned tolerance config;
      `confirmed`/`disputed` flags with voting-layer detail; run report
      listing every disputed station with disagreeing layers and
      geographic summary.
- [ ] 5.2 Emit versioned `station-classification.parquet` with confidence
      tiers; cohort functions across the full sensitivity grid;
      survivorship counts in cohort reports.
- [ ] 5.3 Sanity review: map the still-rural cohort, spot-check 10
      stations by eye against current imagery; record findings.

## 6. Close out

- [ ] 6.1 Validate change, update README/plan.md, rclone Parquet to UNAS,
      archive change, update vault project note.
- [ ] 6.2 Record the phase-two pre-1975 evidence layer (historic OS maps
      via NLS georeferenced sheets) in plan.md as deferred work, so the
      narrowed headline claim and its widening path stay visible.
