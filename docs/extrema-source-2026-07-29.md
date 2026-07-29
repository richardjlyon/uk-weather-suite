# Extrema source: hourly-derived vs MIDAS daily

Evidence for `add-analysis` task 1.2 and `add-daily-ingest` task 3.2.
Produced 2026-07-29 over the first 30 counties of the regenerated hourly
dataset (542 stations, ~4.05M station-days with at least one temperature
reading) and the parsed daily-temperature dataset.

## The finding

Observations per station-day in the **hourly** dataset, counting only
rows with a non-null `air_temperature`:

| observations that day | station-days | share |
|---|---:|---:|
| 1 only | 2,699,844 | **66.6%** |
| 2–3 | 127,395 | 3.1% |
| 4–11 | 251,421 | 6.2% |
| 12–19 | 21,567 | 0.5% |
| 20–24 (usable for daily extrema) | 952,979 | **23.5%** |

**Only 113 of 542 stations have even one full 24-observation day.**

The name "hourly weather observations" describes the dataset's *schema*,
not its density: most contributing stations report a single synoptic
observation per day, and full diurnal coverage is the exception.

## Consequence — the decision task 1.2 exists to make

**Daily Tmin/Tmax must come from the MIDAS daily-temperature dataset,
not from hourly-derived extrema.** Deriving extrema from hourly would
silently restrict the primary endpoint to roughly a quarter of
station-days and a fifth of stations, and — worse — that restriction
would not be random: it would select automated, well-instrumented,
often airport-adjacent sites, which is precisely the cohort the study
must not favour.

The daily dataset is unambiguous about its own periods: `ob_end_time`
at 09:00 with `ob_hour_count` 24 is the 09–09 climatological day
(77,404 rows in the Avon sample), with separate 12-hour periods ending
09:00 and 21:00 (24,560 and 24,561) giving the daytime and overnight
extremes.

## What the hourly dataset is therefore for

1. **Wind, for the calm-versus-windy stratification** (the Parker test)
   — but only where genuine hourly coverage exists, so that fingerprint
   is restricted to the ~23.5% of station-days with full diurnal
   reporting, and that restriction must be stated rather than hidden.
2. **The diurnal profile of any divergence** — same restriction.
3. Everything else in the primary endpoint comes from daily.

## Caveat on the earlier cross-check attempt

An initial comparison on Avon matched only 19 station-days and showed a
1.6 °C bias in the minimum. That figure is an artefact of the sparsity
above (and of comparing a 24-hour daily period against whatever handful
of hourly readings existed), not a real disagreement between the
datasets. It is recorded here so the number is not later mistaken for a
measured bias. A genuine like-for-like comparison is only possible on
the full-coverage subset and should be run there before the analysis
freezes.

## Status

`add-analysis` task 1.2: **answered** — extrema source is the MIDAS
daily-temperature dataset; the spec's conditional ("if material
discrepancies exist, ingest the daily dataset") is resolved in favour of
daily, for a reason stronger than discrepancy: the hourly data cannot
support the measurement for most stations at all.
