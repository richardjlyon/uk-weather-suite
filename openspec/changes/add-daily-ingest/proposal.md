# Proposal: add-daily-ingest

## Why

Two forcing reasons. (1) The analysis spec's trend-engine requires
hourly-derived Tmin/Tmax to be cross-checked against the MIDAS daily
temperature dataset, whose 09:00–09:00 climatological-day convention is
the official basis for UK extrema — if they diverge, daily becomes the
extrema source, so we need it on disk either way. (2) The CEDA access
token in the Keychain expires 2026-07-31; fetching now costs nothing but
the disk, refetching later costs a re-auth round with Richard.

Also absorbs the outstanding commitment (2026-07-28) to retrofit tests
to the midas-fetch crawler/downloader, which shipped spike-style.

## What Changes

- Fetch and parse **uk-daily-temperature-obs** and **uk-daily-rain-obs**
  (qc-version-1, dataset-version-202507) through the existing
  `midas-fetch` pipeline into per-county Parquet, alongside the hourly
  data: index → resumable fetch → parse, same commands, new dataset
  arguments.
- **Convention documentation**: the daily datasets' observation-day
  conventions (09–09 day attribution for Tmin/Tmax, rain-day rules) are
  extracted from the BADC-CSV headers/documentation and recorded in
  `docs/`, because the analysis extrema cross-check depends on stating
  them precisely, not guessing.
- **Fetcher test retrofit** (`midas-fetch`): unit/integration tests for
  the CEDA JSON listing parser (fixtures from captured listings), the
  token source chain (Keychain `ceda-token` then `ceda-credentials`,
  mocked — no network, no real secrets), resumable-fetch skip logic
  (size-match skip, re-fetch on mismatch), and the dap-vs-data host
  redirect rule. Live-network behaviour stays verified by use; logic
  becomes tested code.
- **Cross-dataset sanity**: for a sample of stations, daily-dataset Tmax
  /Tmin compared against hourly-derived extrema; the discrepancy
  distribution is reported to `docs/` as the input the analysis-phase
  extrema decision (add-analysis task 1.2) will cite.

## Capabilities

### New Capabilities
- `daily-ingest`: MIDAS Open daily temperature and rainfall in Parquet
  with conventions documented and hourly cross-check reported.
- `fetcher-tests`: the midas-fetch acquisition logic under test.

### Modified Capabilities

(none — **the predicted fork did not materialise**. Daily files do carry
`ob_end_time` rather than `ob_time`, but the reader promotes whatever
column the header marks as the time coordinate
(`coordinate_variable,<col>,t`), so both daily datasets parsed with no
code change at all. The sanctioned delta reserved for this was not
needed and is withdrawn; the parser's stability is preserved intact.)

## Non-goals

- No hourly re-parse, no schema changes to existing Parquet.
- No analysis decisions here — the extrema-source decision belongs to
  add-analysis task 1.2; this change only puts the evidence on disk.
- No qc-version-0 data.
- No other MIDAS datasets (soil temperature, sunshine, radiation) —
  fetch cost is cheap but scope discipline is cheaper; a later change
  can add them if an analysis requirement names them.
