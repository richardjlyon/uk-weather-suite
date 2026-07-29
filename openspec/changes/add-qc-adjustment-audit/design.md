# Design: add-qc-adjustment-audit

## What we are actually working with

`qc-version-0` is the Met Office's **superseded-record store**: a record
appears there only because they changed it. Verified on the parsed
archive — 485,138 qc-0 daily-temperature rows against 18,383,777 qc-1
rows (2.6%), with 88% of qc-0 rows in 2000 or later. Every design
decision below follows from that fact, which the first draft of this
change got wrong.

## Approach

`ukweather.qc_audit` (Python, uv; DuckDB over Parquet):

1. qc-0 parsed through the unchanged hardened pipeline into its own
   dataset directory with its own run record (done: 22,179 files,
   485,138 rows, 0 failures).
2. Join on observation identity — `(src_id, ob_end_time, ob_hour_count,
   met_domain_name)`; `version_num` deliberately excluded because it *is*
   the version. Duplicate keys abort.
3. Left-join onto the qc-1 denominator, imputing zero difference where
   no predecessor exists; classify each qc-1 observation as unchanged,
   changed (signed difference), deleted, or created.
4. Two-part decomposition by year: P(changed) and E[Δ | changed],
   anomalies against station-month climatology.
5. Reconstruct the series with qc-0 values substituted; the headline is
   the difference in network trend in °C/decade.
6. Partition by the archive's `_q` reason flags; magnitude thresholds
   only as a published sweep.
7. Station-clustered bootstrap for uncertainty; count-weighted annual
   means.
8. Negative control on daily rainfall, same pipeline.

## Key decisions

- **The denominator is qc-1.** Any rate computed over qc-0 is 100% by
  construction. This single point invalidated the first draft's headline.
- **Rate and magnitude are separated**, because the network effect is
  their product and the qc-0 set's era composition shifts violently — a
  neutral procedure would show a magnitude trend on that set, and a
  genuine thin early thumb would be invisible.
- **Deletions are first-class.** A voided cold reading warms a station's
  mean and produces no signed difference. The first draft could not have
  seen the most plausible mechanism it was looking for.
- **The taxonomy is the archive's, not ours.** Writing our own
  correction-versus-shift rule after seeing the data, while holding a
  hypothesis, is the forking path this project bans elsewhere. MIDAS's
  `_q` codes already distinguish automatic estimation, manual setting,
  retrospective observer information and systematic adjustment.
- **The headline is °C/decade on the series**, not drift in correction
  size — otherwise the result is dismissible in one sentence regardless
  of its sign.
- **Station-clustered bootstrap, not AR(1)**: the dominant dependence is
  runs of correlated corrections at one station, which AR(1) on a
  network annual mean does not touch.
- **A negative control is mandatory.** Rainfall discriminates "warming
  thumb" from "quality-control regime changed over time" — the single
  most likely benign explanation for any positive result.

## Risks

- **The honest expected result is a small null.** Quality control
  touching a few percent of observations, mostly flagged as documented
  corrections, with a negligible series effect. Published either way.
- **Coverage is era-skewed and cannot be fixed**, only controlled for
  and stated: pre-1990 records were largely keyed from paper registers
  and never met the automated suite, so early sparsity reflects
  operational history rather than editorial restraint.
- **Attribution limits**: we measure what changed, never why.
- **The temptation this design exists to resist**: the author has stated
  the answer he expects. Every degree of freedom is therefore fixed
  here, the reason taxonomy is taken from outside the project, and a
  negative control is built in so that the most likely benign
  explanation is tested rather than argued away.

## Prior review

First draft reviewed adversarially 2026-07-29 and returned "revise" with
four fatals: the join key included the version column and would have
matched nothing; the premise that each station-year is published twice
was false; the primary statistic measured magnitude while the hypothesis
concerns rate × magnitude; and deletions — the most plausible mechanism
— were invisible to a signed-difference mean. All four are addressed
above, along with the serious findings (archive reason flags, clustered
uncertainty, seasonal control, negative control, series-level headline,
and the min>max repair asymmetry named as an expected null shape).
