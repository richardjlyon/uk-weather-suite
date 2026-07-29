# Design: add-badc-parser

## Approach

New `parser` module in `midas-fetch` plus a `parse` subcommand. Two layers:

1. **`badc` reader** (pure, testable): `parse_file(&str) -> Result<BadcFile>`
   where `BadcFile` holds global attributes, column declarations
   (name → declared type), and rows as typed values
   (`Value::{Float(f32), Int(i32), Str(String), Time(NaiveDateTime), Null}`).
   No I/O beyond the caller handing it file contents — fixtures test this
   layer directly (red/green/refactor).
2. **`parquet` writer**: per county, stream `BadcFile` rows into Arrow
   builders using the union schema, write one Parquet file per county.
   Parallelism with rayon across files within a county and across counties
   (the work is CPU-bound parsing, not I/O).

## Decisions

- **arrow-rs + parquet crates**, matching the ECAD-processor precedent;
  f32 for observations, timestamp[s] for `ob_time`.
- **Schema from data, not hardcoded**: column declarations are read per
  file; the county schema is the union. Guards against MIDAS varying
  columns across stations/years.
- **Quality/flag columns as nullable Utf8** — cheap, lossless, and
  analysis decides later what flags mean.
- **Fail-fast per file, tolerant per county**: a bad file is reported and
  skipped; parsing never silently drops rows within a file.
- **Fixtures**: trimmed real files (header + ~5 rows) cut from the Avon
  download into `midas-fetch/tests/fixtures/`, including deliberately
  broken variants (no `end data`, bad int, mangled header line).

## Risks

- Column sets may drift across years (old files have fewer columns) —
  handled by union schema; test with a 1957 vs 2018 fixture pair.
- `ob_time` format assumed `YYYY-MM-DD HH:MM:SS`; validated by fixture
  from real data; parser errors loudly on deviation.
