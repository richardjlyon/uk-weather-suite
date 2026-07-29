# Tasks: add-qc-adjustment-audit

## 1. Acquisition and parse

- [x] 1.1 Fetch qc-0 for daily temperature and hourly before the CEDA
      token expires (done 2026-07-29: 23,816 + 19,535 files, 0 failures).
- [x] 1.2 Parse qc-0 daily temperature through the unchanged pipeline
      with its own run record (22,179 files, 485,138 rows, 0 failures).
- [ ] 1.3 Parse qc-0 rainfall for the negative control.

## 2. Freeze the rules (before any difference is computed)

- [ ] 2.1 Verify the `_q` flag decoding against archive documentation and
      real data; freeze the reason-flag partition.
- [ ] 2.2 Record the pre-registered interpretation and hash the frozen
      configuration.
- [ ] 2.3 Recorded literature search on whether this measurement has been
      published for the UK network, with dates and search terms — the
      claim of novelty must be evidenced, not asserted.

## 3. Measurement (TDD)

- [ ] 3.1 Identity join with duplicate-key abort and residual classes;
      tests including a re-attributed `met_domain_name` case.
- [ ] 3.2 Classification of every qc-1 observation as unchanged /
      changed / deleted / created, over the qc-1 denominator.
- [ ] 3.3 Two-part decomposition: P(changed) and E[Δ|changed] by year,
      as station-month anomalies, count-weighted.
- [ ] 3.4 Deleted-value anomaly distribution (the asymmetric-deletion
      test).
- [ ] 3.5 Series reconstruction with qc-0 substituted; network trend
      difference in °C/decade; station-clustered bootstrap intervals.

## 4. Controls and stratification

- [ ] 4.1 Strata: era, month, station type, urban/rural classification.
- [ ] 4.2 Coverage by era, stated with every conclusion.
- [ ] 4.3 Negative control: identical measurement on daily rainfall,
      reported beside temperature.
- [ ] 4.4 Magnitude-threshold robustness sweep, whole surface published.

## 5. Close out

- [ ] 5.1 Report written against the pre-registered interpretation
      verbatim, including the min>max expected-null-shape statement and
      the MIDAS-is-not-HadUK-Grid scope limit.
- [ ] 5.2 Validate the change; adversarial review; fold findings;
      re-review to verdict; archive; vault note via coordinator.
