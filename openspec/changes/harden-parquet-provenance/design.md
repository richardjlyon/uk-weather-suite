# Design: harden-parquet-provenance

## Approach

Two-pass parse in `parse_cmd`:

1. **Schema pass** — walk every county's files, parse headers only
   (the BADC reader already separates header from data), accumulate the
   dataset-wide union of (column → declared type). Conflicts are fatal
   *here*, before any output is written, and are reported with both
   declaring stations named. Undeclared columns (which default to
   string) are counted and listed, so a silent Utf8 fallback becomes
   visible rather than structural.
2. **Write pass** — as today, but every county writes against the
   frozen dataset-wide schema; per-county failure is contained
   (recorded, run continues); empty counties write nothing.

Header-only parsing is cheap relative to the full run (the hourly parse
took ~18 min wall clock, dominated by data-section work), so the extra
pass is minutes.

## Key decisions

- **Fail early on type conflict, not silently on read.** A conflict is
  a real finding about the archive; better to stop before writing than
  to leave the analyst discovering it in a query a month later.
- **Version as file metadata, not a per-row column** for the current
  single-release case: no row-size cost, and the archive is
  single-release per parse run. A per-row column is required only if a
  future run mixes releases — the requirement covers that case
  conditionally.
- **UTC annotation, not a value change.** The stored instants are
  already correct (MIDAS is GMT year-round); only the schema's timezone
  field changes. No data migration, but regeneration is needed because
  Parquet schema is written at file creation.
- **Duplicates documented, never removed.** Removing them here would
  bake an analysis decision into the ingest layer; the analysis knows
  which message stream it wants and must say so.
- **Directory move over in-place cohabitation.** `data/parquet/obs/`
  and `data/parquet/derived/` — the glob hazard is otherwise permanent,
  and it has already bitten once (docs visualisation, 2026-07-29).
- **Verification is value-level, not row-count.** Row count is
  invariant to every defect being fixed, and some fixes are *expected*
  to move values and rows: non-finite rejection nulls values that
  currently pass, and making float/datetime failures coerce (rather
  than abort the whole station-year, as today) will resurrect files
  that previously failed — plausibly some of the six. So the new tree
  is written **alongside** the old, and verification is a per-county
  comparison of row count, per-column non-null count, and min/max/sum
  (plus max for int columns, to learn whether i64 saturation already
  bit) — every difference explained in the run record before anything
  is retired.
- **Nothing is destroyed before verification.** A sha256 manifest over
  `data/raw` is written first (the "unchanged and checksummed" claim
  currently has no artefact behind it); the new tree is written to new
  paths; the UNAS refresh is `rclone copy` to a new remote path; old
  local and remote trees are retired only after the comparison passes.
- **Batch flushing, not whole-county buffering.** A dataset-wide union
  widens every county to the full column set, so buffering a whole
  county — already the design's weakest point — would raise peak RAM
  and could kill the process where per-county error containment cannot
  see it. Flush per station file (or ~1M rows) through the same writer.
- **`--dataset` is a flag, not an operator convention.** `parse
  --dataset <d>` constructs `<out>/obs/<dataset>/<county>.parquet`
  itself; the dataset segment being operator-typed is the actual root
  cause of the glob-mixing this change attributes to layout.
- **The single-release assumption is checked, not asserted.** The
  header-only pass records the distinct set of
  `collection_version_number` values; more than one triggers the
  per-row release column the requirement already provides for.

## Risks

- The six originally-failing files may be unrecoverable from the record;
  if so, the honest output is a quantified statement of what is missing,
  not a silent gap. (They are re-parsed in the new run regardless, so
  their current status becomes knowable.)
- Dataset-wide union could surface a genuine cross-county type conflict
  that the per-county code has been hiding. That is the point; it stops
  the run and gets spec'd.
- Downstream paths change with the directory move: the classifier's
  station-history and GHSL outputs and the docs visualisation all
  reference `data/parquet/`. All are regenerable or one-line edits, and
  no external consumer exists yet — cheapest moment to do this.
