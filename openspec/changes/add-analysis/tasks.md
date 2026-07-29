# Tasks: add-analysis

## 1. Foundations

- [ ] 1.1 Pin the completeness/record-length standard (WMO norms cited);
      freeze in versioned config.
- [x] 1.2 Tmin/Tmax derivation cross-check: hourly-derived extrema vs
      MIDAS daily-temperature dataset on a station sample; decide extrema
      source per spec; ingest daily dataset if required.
- [ ] 1.3 CRUTEM5 UK-station ingest with provenance; common-subset N
      established early.
- [ ] 1.4 Obtain COST-HOME benchmark worlds + truth files (authors /
      journal supplement — canonical hosting is 404); re-archive with
      the deposit; Killick 2021 suite as fallback; author the own-PHA
      minimum skill criterion.

## 2. Trend engine (TDD)

- [x] 2.1 Anomaly construction; single-slope break-intercept models with
      AR(1)-corrected SEs; Theil–Sen; paired-difference-series trend on
      common support — tests on synthetic series with known slopes,
      breaks, and autocorrelation.
- [ ] 2.2 Record-length gate + attrition ledger entries.

## 3. Pairing and cohorts (TDD)

- [ ] 3.1 Matched-pair construction (altitude/coast/latitude/instrument-
      era bands, distance cap, control-reuse weighting, cluster-robust
      errors); regional weighting; tests on synthetic station sets with
      known confounding.

## 4. Fingerprint battery (TDD)

- [ ] 4.1 Seasonal Tmin/Tmax asymmetry; wind terciles from hourly wind;
      diurnal profile machinery.
- [ ] 4.2 Dose–response pair regression; stacked event-study vs
      never-treated matched controls (Callaway–Sant'Anna-style; TWFE
      barred), event-time convention per spec.

## 5. Homogenisation adjudication

- [ ] 5.1 Own-PHA implementation (documented algorithm, blind inputs,
      adjustment log, neighbour cohort-composition diagnostic).
- [ ] 5.2 Benchmark own-PHA on the re-archived COST-HOME worlds
      (Killick 2021 fallback) against the pre-registered pass
      criterion; failure installs NOAA PHA per spec.
- [ ] 5.3 Raw vs own-PHA adjudication reporting; CRUTEM5 common-subset
      context table with N.

## 6. Synthetic end-to-end validation

- [x] 6.1 Synthetic UK-like network with injected UHI signals (and zero
      case); full-pipeline recovery within stated tolerance; power curve
      → minimum-detectable-divergence statement.

## 6b. Pre-registration content

- [ ] 6b.1 Author the battery decision rule (must-pass set, reversed-sign
      handling, refutation pattern) and materiality threshold with
      justification.
- [ ] 6b.2 UK urban-climate literature comparison table (CET urban
      adjustment, London UHI corpus, HadUK-grid papers).

## 7. Pre-registration and freeze

- [ ] 7.1 Assemble the pre-registration package (this spec, configs,
      synthetic validation results); external deposit alongside the
      classification deposit; record DOIs.
- [ ] 7.2 Validate change --strict; red-team roast; fold findings;
      re-roast to verdict; only then open the classification deposit.
