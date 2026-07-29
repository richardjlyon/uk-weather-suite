# QC adjustment audit — preliminary numbers and their caveats

**Status: PRELIMINARY, and superseded in part by adversarial review.**
Computed 2026-07-29 before the second review returned. Recorded here so
the numbers are not later quoted without the corrections below.

Data: MIDAS Open dataset-version-202507, daily temperature, qc-0
(superseded records) joined to qc-1 on observation identity.

## What was measured

- 485,138 qc-0 rows; 475,496 matched a qc-1 record (98%); 11 duplicate
  keys pending a pre-registered tie-break.
- Denominator: 10,530,529 qc-1 observations in covered station-years.
- Changed share: **1.4% of Tmax, 1.72% of Tmin**.
- Mean effect over all covered observations (zero imputed where
  unchanged): Tmax **−0.034 °C**, Tmin **−0.003 °C**; implied
  mean-temperature effect **−0.019 °C** — a slight *cooling*.

## Structure of the changes

Magnitude bands, Tmin: |Δ| ≤ 0.2 °C → mean −0.11; 0.2–1 → −0.385;
1–5 → +0.807; 5–20 → +3.672; >20 → +21.1 (444 records).
Tmax: ≤0.2 → +0.101; 0.2–1 → +0.176; 1–5 → −0.352; 5–20 → −0.11;
>20 → −6.03.

Reading: large changes are error repair (a +21 °C mean on the largest
minimum-temperature changes is garbage being fixed). The small-shift
class — the one that would reveal a systematic thumb — raises maxima
slightly and lowers minima slightly, which **widens the diurnal range
and very nearly cancels for mean temperature**.

Small-shift class by decade (mean-temperature effect): 2000s −0.010,
2010s −0.033, 2020s +0.002. Earlier decades have too few records to
interpret (3–10 changed minima per decade).

## Corrections required by the second review

1. **The deletion result was reported as "the one thread in the
   hypothesis's direction". Withdraw that framing.** Deleted values
   skewing cold (Tmax −0.161 °C, Tmin −0.551 °C against station-month
   means) is what *any* competent quality control produces — blocked,
   iced and failed sensors fail low far more often than high. It is the
   expected null behaviour, not evidence.
2. **That measurement was also circular**: the climatology baseline was
   computed from qc-1, which is warmer precisely because cold values
   were removed. It must be recomputed against the reconstructed
   as-received series.
3. **The mean effect above is dominated by the modern record.** qc-0
   retention is ~0.6% of observations before 2000 against ~5% after —
   a property of the archive's digital era, not of Met Office judgement.
   No trend may be computed across that boundary, and these figures
   should be read as "within the covered, modern-skewed subset".
4. **The min>max repair mechanism must be measured, not assumed**
   before any pattern is attributed to it.

## Bottom line, stated conservatively

Within the subset where the comparison is possible, Met Office quality
control alters 1.4–1.7% of daily temperature observations, and its net
effect on mean temperature is **slightly negative (−0.019 °C)**. The
large changes are plainly error repair; the small changes widen the
diurnal range and approximately cancel in the mean; no upward drift is
visible in the modern decades where coverage is dense.

**This does not support the hypothesis that Met Office quality control
adds a systematic warming bias.** It is silent on homogenisation, which
is a different process tested separately in `add-analysis`, and it says
nothing about HadUK-Grid or HadCET, which are built by other means.
