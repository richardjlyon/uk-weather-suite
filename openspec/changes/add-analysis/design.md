# Design: add-analysis

## Shape

`ukweather.analysis` (Python, uv), consuming: county observation Parquet
(96.17M hourly rows), `station-history.parquet`, and a **fixed, cited
version** of `station-classification.parquet` (Zenodo/OSF DOI). DuckDB
for the heavy joins/aggregations; statsmodels/scipy for estimation.

Modules:
- `analysis.anomaly` — station-month anomalies vs each station's own
  baseline over its usable window; Tmin/Tmax derived from hourly series
  per day, with the derivation rule documented (MIDAS hourly →
  daily min/max; compare against MIDAS's own daily dataset on a sample
  as a cross-check task).
- `analysis.trend` — single-slope break-intercept station models;
  paired-difference-series estimation with union-of-breaks intercepts;
  AR(1)/block-bootstrap/ARFIMA uncertainty; Theil–Sen robustness;
  record-length gate from the completeness standard.
- `analysis.pairs` — matched-pair construction (altitude, coastal
  distance, latitude, instrument era where known; distance cap; one
  control reusable with weighting documented); regional weighting so
  cohort statistics are area-balanced, not station-density-balanced.
- `analysis.battery` — the five fingerprint tests (seasonal Tmin/Tmax,
  wind-tercile strata, dose–response, staggered event-study, diurnal
  profile).
- `analysis.homog` — benchmarked own-PHA (pass criterion, NOAA-PHA
  fallback); CRUTEM5 common-subset context ingest; raw-vs-own-PHA
  adjudication reporting.
- `analysis.report` — headline + FDR machinery + bound outputs
  (disputed-cohort trends, sensitivity grid, attrition ledger,
  minimum-detectable-divergence).

## Key decisions

- **Primary endpoint** is singular and frozen in the proposal: matched-
  pair Tmin trend divergence 1975–2018 at (2 km, calibrated tolerance).
  The radius follows the classifier's LCZ-source-area justification; the
  tolerance is the calibrated one — no number invented in this change.
- **Anomalies, not absolutes**; breaks handled by intercept shifts in
  single-slope models, never by averaging separately-fitted segment
  slopes; the primary is the trend of each pair's difference series on
  common support.
- **FDR everywhere**: α_FDR = 2·α_global (Wilks 2016) across
  station-level tests, with sensitivity to the factor reported. The
  battery carries a battery-level correction plus the deposited
  decision rule; the single pre-registered primary is reported with its
  own uncertainty, alone.
- **Own-PHA symmetry rule**: our homogenisation pass must be applied
  blind to classification (station labels stripped), so it cannot be
  accused of treating cohorts differently.
- **Order of operations**: the full pipeline is built and tested on
  synthetic data with known injected UHI signal (power check doubles as
  an end-to-end test) BEFORE the classification deposit is opened.
  Synthetic-first is both a test strategy and the pre-registration
  discipline made practical.

## Red-team dispositions (first review, 2026-07-28)

| # | Finding | Disposition |
|---|---|---|
| 1 | Segment-slope averaging is not the window trend; cohort-correlated AWS breaks bias it | Primary = paired-difference-series trend on common support; single-slope models with break intercepts; killer synthetic case mandated |
| 2 | Own-PHA unbenchmarked; blindness structurally hollow; CRUTEM5 coverage mirage | Venema/ISTI benchmark with published skill required before adjudication; neighbour cohort-composition diagnostic; CRUTEM5 demoted to common-subset context with N |
| 3 | Staggered TWFE DiD demolished by econometrics literature | Stacked event-study vs never-treated matched controls (Callaway–Sant'Anna style); TWFE barred; event-time convention pre-registered |
| 4 | AR(1)-only invites the long-memory (Cohn & Lins) attack | Paired differencing cancels shared noise; block-bootstrap + ARFIMA sensitivity required on the headline |
| 5 | No battery decision rule; battery multiplicity uncontrolled | Deposited decision rule (must-pass set, reversed-sign handling, refutation pattern); battery-level correction |
| 6 | Regional weighting undefined inside frozen primary | Equal-area cells + empty-cell rule named in deposit |
| 7 | Calibration-site circularity | Exclusion or exclusion-robustness headline required |
| 8 | Manual-era overnight wind cannot support fingerprints 2/5 | Wind-completeness gate; AWS-era subset stated openly; anemometer exposure a named limitation |
| 9 | No materiality threshold; no UK literature | Pre-registered materiality threshold; required UK comparison table |
| 10–13 | Spencer as authority; α factor; few clusters; Tmin definition | Parker/Hausfather cited for design; sensitivity stated; wild-cluster bootstrap; 09–09 climatological-day definition |

## Risks

- Calm-tercile power in a maritime climate — mitigated by tercile
  design; the minimum-detectable-divergence statement makes residual
  weakness visible rather than hidden.
- CRUTEM5 UK station adjustments are NMS-supplied and not uniformly
  applied (round-3 review note) — why own-PHA is mandatory, not
  alternative.
- Tmin from hourly may disagree with MIDAS daily Tmin (observation-day
  conventions, 09–09 climatological days) — cross-check task; if
  material, use MIDAS daily temperature dataset for Tmin/Tmax and keep
  hourly for wind/diurnal strata.
- One-control-many-pairs correlation — inverse-variance weighting with
  cluster-robust errors at the control level; stated in spec.
