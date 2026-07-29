# Regeneration reconciliation — hourly observations, 2026-07-29

Task 4.1/4.1b of `harden-parquet-provenance`. The old tree
(`data/parquet/*.parquet`, 109 files) was left intact as the baseline;
the new tree was written to `data/parquet/obs/uk-hourly-weather-obs/`.
**Nothing has been retired** — that decision is Richard's.

## Headline

| | old | new |
|---|---|---|
| rows | 96,169,820 | **96,193,967** (+24,147) |
| files parsed | 34,238 | 34,238 |
| counties | 105 | 105 |
| failures | (not durably recorded) | 0 |
| values coerced to null | 15 (run total only) | 26, attributed to file and column |

## Every difference, explained

**101 of 105 counties are byte-for-byte equivalent on values.** For each,
row count, per-column non-null count, and min/max/sum of
`air_temperature`, `dewpoint`, `wind_speed`, `msl_pressure`, `rltv_hum`
and `visibility` are identical between trees. Zero differences.

**Four counties gained rows — all from five station-year files that were
entirely missing from the old tree:**

| county | station | year | old rows | new rows |
|---|---|---|---|---|
| ayrshire | 01013_saughall | 1999 | **0** | 3,508 |
| fife | 00239_fife-ness | 1999 | **0** | 4,599 |
| fife | 00239_fife-ness | 2000 | 3 | 4,617 |
| hampshire | 00862_odiham | 2014 | 5 | 8,728 |
| kent | 00752_sheerness | 2006 | 2 | 2,695 |

The residual +3 / +5 / +2 in adjacent years (fife 1998, hampshire 2013,
kent 2005) is boundary-hour spill: a station-year file contains a few
observations timestamped either side of midnight on 1 January, so
recovering a file adds a handful of rows to its neighbouring years.

**No duplication.** For the two stations whose gains fell inside
already-present years, row count equals distinct-key count
(`src_id, ob_time, met_domain_name, version_num`) in *both* trees:
Odiham 423,471/423,471 → 432,199/432,199; Sheerness 41,038/41,038 →
43,733/43,733. The added rows are genuine distinct observations.

## Root cause — and why this vindicates the change

The original parse aborted an entire station-year file on the first
value that failed typed parsing (WMO sky-obscured markers such as `/`
and `&` in declared-integer cloud-code columns). That defect was found
and fixed at the time, **but the fix was followed by re-parsing only the
counties visible in the terminal's truncated failure output**. The
failure list was printed, never written down. Files failing in
ayrshire, fife, hampshire and kent scrolled past unseen and stayed
missing.

That is precisely the defect the review identified as "a printed summary
is not a durable record", and precisely the outcome it predicted: up to
six station-years silently absent from a dataset reported as complete.
The count was 96,169,820 either way — which is why row-count agreement
was rejected as a verification method. Only the value-level comparison
surfaced it.

Under the new pipeline the same values coerce to null and are recorded
per file and per column in `run-record.json` (16 entries, all in
`hi_cld_type_id` / `med_cld_type_id`), the file parses to completion, and
no file can go missing without appearing in a durable artefact.

## Other differences

- `ob_time` now carries a millisecond UTC timestamp logical type
  (`isAdjustedToUTC=true`). The old files stored bare INT64 with **no
  logical type at all** — which is why consumers had to call
  `to_timestamp()` by hand. Instants are unchanged.
- File-level metadata now carries the archive release
  (`dataset-version-202507`, single release confirmed by the header
  pass), per-column units, and the generator version.
- Schema: 104 columns, dataset-wide union, **zero widenings and zero
  numeric-vs-string conflicts** across all 34,238 files — the conflict
  policy was exercised and the archive is internally consistent.
- Zero `src_id` mismatches: no station is mis-filed relative to its
  directory.
- Zero empty-field and zero undeclared-column events.

## Status

Tasks 4.1 and 4.1b: complete. Task 4.2 (fate of the originally-failing
files): answered above — five station-years recovered, none genuinely
corrupt, none now absent. Task 4.3 (derived-table regeneration) is not
required: `station-history` derives from capability files and the GHSL
and Stamp layers from their own sources, none of which changed. The UNAS
refresh and the retirement of the old tree remain open, both reserved
to Richard.
