## ADDED Requirements

### Requirement: Join on observation identity, never on version
Records SHALL be paired on `(src_id, ob_end_time, ob_hour_count,
met_domain_name)` — the observation's identity. `version_num` SHALL NOT
appear in the key: it *is* the qc version (0 = originally received,
1 = current best), so including it returns the empty set. `version_num`
and `rec_st_ind` are carried as attributes and reported when they
differ. Duplicate keys within a version SHALL abort rather than fan out.

#### Scenario: the key cannot silently match nothing
- **WHEN** the join runs
- **THEN** a match rate of zero aborts as a defect, never reports as a finding

#### Scenario: re-attributed records are not lost
- **WHEN** a record's `met_domain_name` differs between versions
- **THEN** it is reported in a named residual class rather than counted as unmatched-and-forgotten

### Requirement: The denominator is qc-1, with zero imputed
Every statistic SHALL be computed over qc-1 observations in covered
station-years, with a difference of zero imputed where no qc-0
predecessor exists. Statistics over the qc-0 set alone SHALL be labelled
as conditional-on-change and never presented as headline.

#### Scenario: no 100%-by-construction rate
- **WHEN** the proportion of changed observations is reported
- **THEN** its denominator is qc-1 observations, not qc-0 records

#### Scenario: selection is stated, not denied
- **WHEN** the population is described
- **THEN** it states that qc-0 membership is determined by the Met Office on the fact of change, and that this is why every headline statistic uses the qc-1 denominator

### Requirement: Rate and magnitude are separated
The network effect being rate × magnitude, the analysis SHALL report
a two-part decomposition: the probability that an observation was
changed, as a function of year; and the signed difference given change,
as a function of year — with the product reported as the effect.
Neither part alone SHALL be presented as the result.

#### Scenario: composition shift cannot masquerade as drift
- **WHEN** a trend appears in the magnitude series
- **THEN** the rate series and the era composition of the covered set are reported beside it, so a change in coverage is distinguishable from a change in behaviour

#### Scenario: the change rate is descriptive only
- **WHEN** P(changed) is reported by year
- **THEN** it is labelled descriptive and SHALL NOT be interpreted as a trend in quality-control behaviour — retention is perfectly confounded with era (a change made while keying a paper register leaves no superseded record at all) and the confound is unobservable, not controllable

### Requirement: Deletions and creations are first-class outcomes
A value present in qc-0 and null in qc-1 is a **deletion**; the reverse
is a **creation**. Both SHALL be counted separately from signed
differences, and the distribution of deleted values' anomalies against
station-month climatology SHALL be reported — asymmetric deletion of
cold readings warms a station's mean while producing no signed
difference at all, and is the most plausible route from quality control
to spurious warming.

#### Scenario: asymmetry alone is pre-registered as NOT evidence
- **WHEN** deleted values are found to skew cold
- **THEN** that on its own is reported as the expected null behaviour — blocked, iced and failed sensors fail low far more often than high under any competent quality control — and the reported quantity is instead the **net effect on the station-month mean in °C, deletions and creations netted together**

#### Scenario: the climatology is not contaminated by the thing being tested
- **WHEN** anomalies are computed for deleted values
- **THEN** the baseline climatology is computed from the reconstructed as-received series, never from qc-1 — a qc-1 baseline is warmer precisely because cold values were removed, which would inflate the asymmetry under test

### Requirement: Partition by the archive's own reason flags
Changes SHALL be partitioned primarily by MIDAS's `_q` reason codes
(automatic estimation, manual setting, retrospective observer
information, systematic adjustment), which are external to this project
and pre-existing. A magnitude-based partition MAY be reported only as a
robustness sweep across thresholds with the entire surface published;
no single magnitude cut SHALL carry interpretive weight. The flag
decoding SHALL be verified against the archive documentation and real
data before use.

#### Scenario: the taxonomy is not ours to invent
- **WHEN** changes are classified
- **THEN** the classification comes from the archive's flags, and any magnitude rule appears only as a published threshold sweep

### Requirement: No trend is computed across the coverage onset
Retention of superseded records is a property of the archive's digital
era, not of Met Office judgement: measured coverage is ~0.6% of
observations before 2000 and ~5% after. Substituting qc-0 where it
exists therefore reproduces qc-1 exactly in the early record **by
construction** and diverges only in the modern period, so a trend
computed across that boundary converts any modern mean difference —
however benign — into a trend whose sign is merely the sign of the
modern difference. Trend statistics SHALL therefore be computed **only
within a stable-coverage window**, defined as years whose qc-0 coverage
exceeds a threshold stated in the frozen configuration before any
difference is examined, and every reported annual difference SHALL be
published beside its annual coverage rate.

#### Scenario: retention policy cannot masquerade as adjustment drift
- **WHEN** a trend is reported
- **THEN** it is bounded to the stable-coverage window, and no trend spanning the coverage onset appears anywhere in the report

#### Scenario: coverage travels with every number
- **WHEN** an annual mean difference is shown
- **THEN** that year's coverage rate is shown with it

### Requirement: Effect on the series, within the covered window
The effect SHALL be expressed as its consequence for temperature in °C
— mean effect per observation and, within the stable-coverage window,
per decade — never as drift in mean correction size, and always beside
the mechanical ceiling implied by the change rate.

#### Scenario: materiality is pre-computed, not argued afterwards
- **WHEN** any effect is claimed
- **THEN** it is reported against a materiality threshold and a mechanical ceiling (change rate × plausible mean magnitude) both stated in the frozen configuration

### Requirement: Uncertainty respects station clustering and unequal counts
Annual means SHALL be **station-equal weighted as primary** (count
weighting compounds the modern skew, since frequent reporters are
automated modern stations and that is exactly where qc-0 concentrates),
with count-weighting reported as robustness; duplicate keys SHALL be
resolved by a tie-break rule pre-registered now rather than an abort
that would be relaxed under pressure mid-analysis; and uncertainty
SHALL come from a station-clustered bootstrap (stations resampled with
replacement), not an AR(1) correction on the network annual mean — the
dominant dependence is runs of correlated corrections within a station,
which an AR(1) term does not capture and which would otherwise
understate uncertainty.

#### Scenario: one station cannot carry the result
- **WHEN** intervals are reported
- **THEN** they derive from resampling stations, and the number of effective station clusters is stated

### Requirement: Seasonal control
Differences SHALL be computed as anomalies against the station-month
mean, and month SHALL be a reported stratum — quality-control activity
concentrates in winter (frost, icing, snow-covered screens), so drifting
seasonal composition would otherwise produce a trend with no change in
behaviour.

#### Scenario: winter drift is not mistaken for bias
- **WHEN** the seasonal composition of changed records shifts across eras
- **THEN** the anomaly basis and the month stratification prevent it appearing as a temperature-adjustment trend

### Requirement: Negative controls, with their asymmetry stated
The primary negative control SHALL be **grass and concrete minimum
temperature** (`min_grss_temp`, `min_conc_temp`) — same file, same
station, same QC suite, same units, no headline series attached — with
daily rainfall as a secondary, weaker control. The report SHALL state
that these controls are **one-sided**: a matching drift refutes a
temperature-specific claim, while a null in the control corroborates
nothing, because a different procedure on a different element was always
free to behave differently. Rainfall in particular is a bounded,
zero-inflated variable whose QC concerns accumulations and traces, with
no min>max analogue and no common scale with °C.

#### Scenario: the control that actually discriminates
- **WHEN** temperature shows an effect
- **THEN** the same measurement on grass/concrete minima is reported beside it in the same units, and any matching pattern is reported as a QC-suite property rather than a screen-temperature finding

#### Scenario: one-sidedness is stated, not implied
- **WHEN** a control shows no effect
- **THEN** the report states that this does not corroborate the temperature finding

### Requirement: Expected null shapes are measured, not asserted
The `min_air_temp > max_air_temp` mechanism SHALL be **measured**: count
qc-0 records where min exceeds max and tabulate what qc-1 did to each
(repaired upward, repaired downward, voided, or merely flagged).
Comparable suites flag rather than repair, so an assumed repair
behaviour would be a pre-built escape hatch. The report SHALL also state
that agreement between Tmax and Tmin is a severity criterion, not two
independent confirmations — the same record, often the same
intervention.

#### Scenario: the mechanism is a result, not a premise
- **WHEN** the min>max shape is invoked to explain any pattern
- **THEN** it is supported by the measured tabulation, or dropped

### Requirement: Flag decoding pre-registered
The `_q` decode SHALL be pre-registered before use: the value is a
five-digit MESQL code stored as an integer, so it SHALL be zero-padded
to five before positional decoding; the specification SHALL state which
version's flag is read (qc-1's); and records whose reason digit does not
classify SHALL form an explicit residual class, reported separately and
never merged into another.

#### Scenario: no silently shifted digits
- **WHEN** a flag is decoded
- **THEN** it was zero-padded first, and the decode was verified against archive documentation and sample records before any classification was produced

### Requirement: Reproducibility of the archive snapshot
The MIDAS Open release version SHALL be named in the report
(dataset-version-202507), since qc-0 content differs between releases,
and "covered station-year" SHALL be defined explicitly (a station-year
containing at least one qc-0 record — which is selection on treatment,
and is stated as such).

#### Scenario: someone else can obtain the same inputs
- **WHEN** the report states its data
- **THEN** the release version and the covered-subset definition are both explicit

### Requirement: Coverage and scope stated with every conclusion
The report SHALL quantify qc-0 coverage by era (88% of qc-0 daily
temperature rows fall in 2000 or later) and SHALL state that conclusions
are scoped to the covered subset and to MIDAS itself.

#### Scenario: no silent extrapolation
- **WHEN** a conclusion is drawn
- **THEN** the covered share is stated beside it, and the report states that MIDAS qc-1 is not the input to HadUK-Grid or HadCET
