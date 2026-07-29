# Proposal: add-qc-adjustment-audit

## Why

Where the Met Office changes a stored observation, the superseded record
is retained: `qc-version-0` holds **only records that were changed**,
and `qc-version-1` holds the current best version of everything. So the
archive contains a partial but genuine change log of their own editorial
judgement — what a value was before they altered it, and what it became.
It is measurable on data they publish themselves.

Richard's hypothesis (2026-07-29) is that Met Office processing adds a
systematic warming bias. This change tests it, and is built so it can
**fail**: population, denominator, partition rule, statistic and
interpretation are frozen here, before any difference is computed, and
the design was rewritten after adversarial review demolished its first
version.

## What qc-0 actually is (corrected 2026-07-29)

The first draft of this change assumed each station-year is published
twice. **That is false**, and both the documentation and the data say
so. The Met Office Surface Data Users Guide: *"When a change is made to
any value in a table record, the original record is stored with Version
Number 0 and a new record is created for the corrected version having
version number 1… On initial storage all new records are given Version
Number 1."*

Measured on the parsed archive: qc-0 daily temperature contains
**485,138 rows against qc-1's 18,383,777** — 2.6%. Coverage is heavily
modern: **88% of qc-0 rows fall in 2000 or later**, against a record
that starts in the 1850s.

Three consequences, all fatal to the first draft and now designed around:

1. **The qc-0 population is selected by the Met Office on the outcome**
   — a record is there precisely because they changed it. Any statistic
   computed over qc-0 alone answers "how big are the changes they made",
   never "do they change things".
2. **The denominator must be qc-1**, with a difference of zero imputed
   wherever no qc-0 record exists. Otherwise the "proportion changed" is
   100% by construction.
3. **A trend computed on the qc-0 set alone is uninterpretable**: its
   era composition shifts violently, so a perfectly neutral procedure
   would show a trend, and a real thumb applied thinly to early decades
   would be invisible.

## What is measured

The network effect of quality control is **rate × magnitude**, so both
are measured, separately and together, over the qc-1 denominator:

1. **Rate**: proportion of qc-1 observations in covered station-years
   that have a qc-0 predecessor, by year, element and month.
2. **Magnitude**: the signed difference (qc-1 − qc-0) where one exists,
   as an anomaly against the station-month climatology.
3. **Voids and creations as first-class outcomes**: a value present in
   qc-0 and null in qc-1 is a *deletion*, and carries no signed
   difference — yet asymmetric deletion of cold readings is the most
   plausible route from quality control to spurious warming. Deletions
   and creations are counted, and the anomaly distribution of deleted
   values is reported.
4. **The headline quantity**: the difference in network trend, in
   °C/decade, between the qc-1 series and the same series with qc-0
   values substituted, over the covered subset. This is what a reader
   actually wants to know and what makes the result quotable or
   dismissible.
5. **Stratification**: era, month, station type, and this project's own
   urban/rural classification.

## Partition: the archive labels its own reasons

The first draft proposed inventing a magnitude-based taxonomy of
"corrections" versus "shifts" — a rule to be written by the person
holding the hypothesis, after seeing the data. Replaced: MIDAS's `_q`
columns encode the reason, including `qc_estimate` values distinguishing
automatic estimation, manual setting, retrospective observer
information, and *systematic adjustment* — the last being literally the
class this hypothesis is about. The partition is therefore taken from
the archive's own flags, external to us; a magnitude rule survives only
as a robustness sweep across thresholds with the whole surface
published, never a single chosen cut.

## Pre-registered interpretation (frozen before results)

- **Null**: rate and magnitude show no drift once era composition,
  season and station mix are controlled; deletions are symmetric in
  anomaly; the °C/decade effect on the series is indistinguishable from
  zero.
- **Confirms**: a positive °C/decade effect that survives the negative
  control, is present in both Tmax and Tmin, and does not vanish under
  stratification.
- **Refutes**: effect indistinguishable from zero, or driven by
  documented automatic/observer corrections, or reversing under
  stratification, or matched by the negative control.
- **Expected honest outcome**: quality control touches a small share of
  observations, mostly flagged as documented corrections, with a
  negligible effect on the series. That is publishable and will be
  published.

## Negative control

The identical measurement is run on **daily rainfall**, an element with
no warming narrative attached. If rate and magnitude drift the same way
there, the finding is a change in quality-control regime over time — not
a temperature thumb — and must be reported as such.

## Capabilities

### New Capabilities
- `qc-audit`: measurement of Met Office quality-control adjustments from
  the published superseded-record store, over the qc-1 denominator.

### Modified Capabilities

(none)

## Non-goals

- No claim about *why* any change was made; we measure what changed.
- **No inference about published national series.** MIDAS qc-1 is not
  the input to HadUK-Grid or HadCET, which carry their own quality
  control and homogenisation. Nothing here demonstrates a path from
  record supersession to any published national temperature figure, and
  the report will say so.
- No extrapolation beyond the covered subset.
- No merging with the urban-heat primary endpoint: separate question,
  separate pre-registration, separate report.
