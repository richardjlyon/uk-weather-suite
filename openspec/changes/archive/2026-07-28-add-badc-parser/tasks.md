# Tasks: add-badc-parser

## 1. Fixtures (red precondition)

- [ ] 1.1 Cut fixtures from downloaded Avon data into
      `midas-fetch/tests/fixtures/`: a modern hourly file (header + ~5 rows
      + `end data`), an early-era file with fewer columns, and broken
      variants: `truncated.csv` (no `end data`), `bad-int.csv`,
      `bad-header.csv`.

## 2. badc reader — red

- [ ] 2.1 Write failing integration tests in `midas-fetch/tests/badc.rs`
      covering: header attribute extraction, column type declarations,
      data-section bounds, NA→null, ob_time parsing, quality columns as
      strings, and the three failure fixtures erroring with context.

## 3. badc reader — green

- [ ] 3.1 Implement `src/badc.rs` (`parse_file`, `BadcFile`, `Value`) until
      all tests pass.

## 4. Refactor

- [ ] 4.1 Tidy the reader (shared error type with file/line context, no
      clippy warnings), tests stay green.

## 5. Parquet writer

- [ ] 5.1 Failing test: two small fixture stations with differing column
      sets parse into one county Parquet with the union schema, correct
      row counts, src_id/county/station attribution, and re-read values
      matching the fixture (round-trip via the parquet crate reader).
- [ ] 5.2 Implement `src/parquet_out.rs` (union schema, Arrow builders,
      one file per county) to green.

## 6. `parse` subcommand

- [ ] 6.1 Wire `parse --dataset <d> [--county c]` to walk `data/raw`,
      parallelise with rayon, and print the summary (parsed/rows/failed).
- [ ] 6.2 Run over the full downloaded hourly archive; record row counts
      and failures in the change; spot-check against source files.

## 7. Close out

- [ ] 7.1 `openspec validate add-badc-parser --strict` clean; update
      README and docs/plan.md; commit.
