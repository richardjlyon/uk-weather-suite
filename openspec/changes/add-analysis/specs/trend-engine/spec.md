## ADDED Requirements

### Requirement: Within-station anomalies
Trends SHALL be computed on within-station monthly anomalies relative to
the station's own baseline, never on absolute temperatures across
stations, so fixed offsets (altitude, exposure) cancel by construction.

#### Scenario: no absolute cross-station comparison
- **WHEN** any cohort statistic is computed
- **THEN** its inputs are anomaly trends, and no absolute-temperature comparison between different stations exists in the pipeline

### Requirement: Break-respecting single-slope models
Station-level trend models SHALL carry an intercept shift at every
station-history break (new src_id, gap, instrument-era) and a single
slope over the analysis window; averaging separately-estimated
segment slopes over non-common sub-periods is barred (it does not
estimate the window trend and is biased under nonlinear common
warming when break dates differ).

#### Scenario: AWS transition handled by intercept, not by averaging
- **WHEN** a station's record contains an AWS-transition break in 1993
- **THEN** the model fits one 1975–2018 slope with an intercept shift at 1993, and no average of two separately-fitted slopes is used

### Requirement: Primary inference on paired difference series
The primary endpoint SHALL be estimated as the trend of each matched
pair's difference series over the pair's common temporal support —
differencing before trend estimation, so shared climate signal
(including nonlinear common warming and shared long-memory noise)
cancels by construction. The difference-series model SHALL carry
intercept shifts at the union of both members' documented break dates
and a single slope; "difference of two separately fitted station
slopes" is NOT the primary estimator and appears only as robustness.

#### Scenario: both members' breaks modelled in the difference
- **WHEN** the urban member has an AWS break in 1993 and the rural member in 1997
- **THEN** the difference-series model carries intercept shifts at 1993 AND 1997, and neither step is absorbed into the slope

#### Scenario: non-common support never differenced
- **WHEN** a pair's members have different usable windows
- **THEN** the difference series exists only on the overlap, the overlap length is recorded, and pairs below the minimum overlap are excluded via the attrition ledger

#### Scenario: difference first, then deseasonalise
- **WHEN** the paired difference series is formed
- **THEN** the seasonal cycle is removed from the DIFFERENCE, not from each member before differencing — taking per-station anomalies first is biased whenever the two members have different missingness, because each station's monthly climatology is then computed over a different set of years, so a station absent disproportionately in cool early years acquires a climatology that is too warm and anomalies that are too cool, and the difference inherits a spurious trend (measured on synthetic killer world 2: 0.006 ± 0.002 °C/decade from ZERO injected signal; nil after reordering)

### Requirement: Autocorrelation and long-memory discipline
Trend standard errors SHALL be corrected for serial correlation (AR(1)
effective-sample-size at minimum), with Theil–Sen slopes as robustness,
AND primary-endpoint inference SHALL include block-bootstrap and
long-memory (ARFIMA) sensitivity — the Cohn & Lins long-term-persistence
critique is answered inside the design.

#### Scenario: naive OLS never reported alone
- **WHEN** a trend and its uncertainty are reported
- **THEN** the uncertainty is autocorrelation-corrected, and Theil–Sen is available for the same series

#### Scenario: long-memory sensitivity on the headline
- **WHEN** the primary endpoint is reported
- **THEN** block-bootstrap and ARFIMA-based uncertainties appear alongside the AR(1) result, and the conclusion states whether it survives all three

### Requirement: Record-length gate from a stated standard
The minimum usable record SHALL be derived from a stated completeness
standard (documented against WMO/climatological norms) and frozen in the
versioned config before the classification deposit is opened; stations
failing the gate are excluded with reason codes in the attrition ledger.

#### Scenario: no eyeballed cutoffs
- **WHEN** the record-length gate is set
- **THEN** the config cites the standard it derives from, and changing it creates a new analysis version

### Requirement: Daily extrema come from the MIDAS daily dataset
Tmin/Tmax SHALL be taken from the MIDAS daily-temperature dataset on its
09–09 climatological day (`ob_end_time` 09:00, `ob_hour_count` 24), NOT
derived from hourly observations. Resolved 2026-07-29 by measurement
(docs/extrema-source-2026-07-29.md): across 542 stations and ~4.05M
station-days, **66.6% of hourly station-days carry a single temperature
reading and only 23.5% carry 20–24**, with just 113 of 542 stations
having any full day. Hourly-derived extrema would restrict the primary
endpoint to a minority of station-days and would select automated,
often airport-adjacent sites — a non-random restriction favouring
exactly the cohort the study must not favour.

#### Scenario: the primary endpoint is not silently restricted
- **WHEN** the primary endpoint is computed
- **THEN** its extrema come from the daily dataset, and no station is excluded merely for lacking full diurnal hourly coverage

#### Scenario: hourly-dependent fingerprints declare their subset
- **WHEN** the calm/windy or diurnal-profile fingerprints are computed (both of which genuinely need hourly data)
- **THEN** they are restricted to station-days with full diurnal coverage, and that restriction and its size are stated in the report rather than left implicit
