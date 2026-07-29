# Proposal: add-analysis

## Why

The classifier change (frozen, four red-team rounds) produces a
versioned, externally deposited station classification. This change
specifies the temperature analysis that consumes it — pre-registered
before any trend is computed, so the design cannot be accused of being
shaped by its results. Grounded in the methodology research of
2026-07-28 (vault: Research/Deep, UHI detection methodology).

## Headline question (claim window 1975–2018)

Do stations whose surroundings urbanised within the satellite record
show temperature trends that diverge from confirmed still-rural
stations — and what does homogenisation do to any divergence: remove it
(as Hausfather et al. 2013 found for USHCN) or transfer it into rural
series? Both outcomes are reportable; the design is symmetric.

## What Changes

- New `ukweather.analysis` module computing, from the deposited
  classification version and the observations Parquet:
- **Primary endpoint (pre-registered here)**: difference in 1975–2018
  trend of **night-time minimum temperature (Tmin)** between urbanised
  and confirmed-still-rural stations, as **matched pairs** stratified on
  altitude, coastal distance, latitude AND instrument era where known
  (Hausfather et al. controlled instrument type in pairing; stations with
  unknown instrument history form a stated robustness cut, not silent
  members), evaluated at the **2 km ring** with the **calibrated
  tolerance** from the classifier's reference-site calibration as the
  urbanised/unchanged cut. Cohort statistics are **regionally weighted**
  so the station-dense south-east cannot dominate (Hausfather's
  pairing-plus-gridding precedent). One endpoint; everything else is
  secondary or robustness.
- **Trend machinery**: within-station monthly anomalies (station's own
  baseline, so fixed offsets cancel). **The primary estimand is the
  trend of each matched pair's DIFFERENCE series over the pair's common
  temporal support** — differencing first cancels shared climate signal
  (including nonlinear common warming and shared long-memory noise);
  station-level models carry break intercepts (new src_id, gap, AWS
  transition) and a single slope, never estimates averaged across
  non-common sub-periods. Uncertainty: AR(1)-corrected at minimum, with
  block-bootstrap and long-memory (ARFIMA) sensitivity required — the
  Cohn & Lins critique answered inside the design, not left to referees.
  Theil–Sen as robustness. Minimum usable record length declared in
  config before the deposit is opened, derived from a stated
  completeness standard (WMO norms cited), not chosen by eye. "Night-time
  minimum" is defined once, precisely, on the 09–09 climatological day.
- **UHI fingerprint battery (secondary, confirmatory)**:
  1. Tmin vs Tmax asymmetry — urban contamination predicts divergence in
     Tmin, little in Tmax (Spencer 2023: summer UHI ~3.5× larger in
     Tmin), stratified by season — UHI has a seasonal cycle that
     averaging conceals;
  2. calm-vs-windy-night stratification from our own hourly wind
     observations, strata defined as seasonal terciles of each station's
     wind distribution (Parker 2006's design run natively — fixed-knot
     thresholds would starve the calm stratum in a maritime climate);
  3. dose–response: trend against continuous built-up *change*
     (Spencer-style pair regression), no thresholds;
  4. event-study for staggered urbanisation using a stacked
     estimator against never-treated matched controls
     (Callaway–Sant'Anna-style; naive two-way fixed-effects DiD is
     barred — Goodman-Bacon/de Chaisemartin critique), with the
     event-time convention for interval-dated (5-yearly epoch) change
     pre-registered;
  5. diurnal profile of the divergence (hourly data: UHI peaks hours
     after sunset).
- **Homogenisation adjudication**: the primary comparison is raw MIDAS
  vs our own pairwise-homogenisation pass, which SHALL first be
  **benchmarked on re-archived COST-HOME worlds (Venema et al. 2012;
  Killick 2021 fallback) against a pre-registered pass criterion** —
  failing it installs NOAA PHA as adjudicator; an unbenchmarked or
  merely-measured reimplementation adjudicates nothing. CRUTEM5 is demoted to context: reported on the
  common-station subset only, with N stated (CRUTEM5's UK coverage is a
  small fraction of our 1,537). Blindness is demonstrated structurally,
  not asserted: a neighbour-network cohort-composition diagnostic is
  published so readers can see how urban-dominated each station's
  adjustment neighbourhood is. This is the UK twin of the US
  homogenisation question that seeded the project.
- **Statistical discipline**: Benjamini–Hochberg false-discovery-rate
  control across all station-level tests with α_FDR = 2·α_global
  (Wilks 2016, verified from the paper; sensitivity to the factor
  reported); no per-station "significance" outside the FDR framework.
  The fingerprint battery carries its own battery-level multiplicity
  control AND a **pre-registered decision rule**: named must-pass
  fingerprints, what any reversed-sign fingerprint does to the claim,
  and what pattern refutes — decided before data, not narrated after.
- **Materiality threshold (pre-registered)**: the deposit states what
  divergence magnitude the contamination hypothesis predicts and what
  is material against the UK's ~0.2–0.3 °C/decade trend, so neither a
  trivial positive nor an honest null can be spun.
- **UK literature engagement**: a required comparison table against the
  existing UK urban-climate corpus (CET urban adjustment, London UHI
  literature, HadUK-grid papers), so the work reads as situated, not
  parachuted. Design choices cite Parker/Hausfather; Spencer is
  corroboration, not authority.
- **Classifier interface hygiene**: any classifier calibration
  reference site appearing in an analysis cohort is excluded, or the
  headline re-run without it — tolerance-tuning circularity closed.
- **Bound outputs (inherited from the classifier spec, restated as
  requirements here)**: disputed-cohort trends alongside headline;
  sensitivity grid across radius × tolerance published in full;
  attrition ledger; minimum-detectable-divergence statement so a null is
  distinguishable from underpower.

## Capabilities

### New Capabilities
- `trend-engine`: anomaly construction, single-slope break-intercept
  models, paired-difference-series estimation, autocorrelation and
  long-memory discipline, record-length gating.
- `cohort-comparison`: matched-pair construction, primary endpoint,
  fingerprint battery, FDR control.
- `homogenisation-adjudication`: benchmarked own-PHA adjudication (raw
  vs own-PHA), CRUTEM5 common-subset context.

### Modified Capabilities

(none)

## Non-goals

- No claim outside 1975–2018; no pre-1975 quantitative claims (phase-two
  gate in the classifier spec).
- No gridded/national series construction — this is a station-cohort
  study, not a rival national record.
- No attribution of the non-urban residual trend (to CO2 or anything
  else): the study tests contamination of the record, not causes of
  warming.
- No revision of classification parameters from within this change
  (deposit is upstream and fixed).
