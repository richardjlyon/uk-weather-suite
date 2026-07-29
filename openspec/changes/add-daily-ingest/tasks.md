# Tasks: add-daily-ingest

## 1. Acquisition (URGENT — token expires 2026-07-31)

- [ ] 1.1 Index uk-daily-temperature-obs and uk-daily-rain-obs
      (v202507); record file counts and sizes.
- [ ] 1.2 Fetch qc-1 + capability files for both, resumable to
      failed = 0; record summaries.

## 2. Parse

- [ ] 2.1 Parse both datasets to per-county Parquet via the unchanged
      pipeline; report row counts, coerced-null counts, and any
      parser findings (findings spec'd, parser untouched).

## 3. Conventions and cross-check

- [ ] 3.1 docs/daily-conventions.md: observation-day attribution rules
      quoted with sources.
- [ ] 3.2 Hourly-vs-daily extrema cross-check on a stated sample
      (eras × regions); discrepancy report to docs/.

## 4. Fetcher test retrofit (TDD against captured fixtures)

- [ ] 4.1 Capture listing fixtures (normal, empty, malformed);
      listing-parser tests.
- [ ] 4.2 Token-chain tests with mocked keychain/HTTP.
- [ ] 4.3 Skip/refetch and dap-host tests (redirect regression guard).

## 5. Close out

- [ ] 5.1 Validate --strict; roast; fold; re-roast to verdict; update
      README/plan.md; archive change; vault note via coordinator.
