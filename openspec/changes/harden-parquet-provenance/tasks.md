# Tasks: harden-parquet-provenance

## 0. Provenance and safety (before anything is written)

- [x] 0.1 sha256 manifest over `data/raw`, committed — the "unchanged
      and checksummed" claim currently has no artefact behind it.
- [ ] 0.2 Confirm the old Parquet tree and its UNAS copy are intact and
      will not be overwritten (new tree goes to new paths; UNAS refresh
      is `rclone copy` to a new remote path, never a sync that could
      delete the baseline).

## 1. Parser fixes (TDD)

- [x] 1.1 Per-(file, column) coercion attribution; undeclared-column
      fallback counting; empty-vs-NA separation; reject non-finite
      floats; reject (never saturate) out-of-range ints — tests first.
- [x] 1.2 Table-driven `parse_int_lenient` tests (accept 300.0; reject
      300.5, `/`, `&`, out-of-range magnitudes).
- [x] 1.3 Keep the directory-derived `src_id` but count and report rows
      whose in-file `src_id` disagrees (mis-filed stations are currently
      laundered into consistency).

## 2. Writer fixes (TDD)

- [x] 2.1 Dataset-wide union schema: header-only pass; numeric
      conflicts widen (recorded), numeric-vs-string aborts naming both
      stations; distinct release set collected; tests with counties
      declaring widening, aborting and complementary columns.
- [x] 2.2 UTC-annotated `ob_time`; round-trip test asserting a known
      timestamp value.
- [x] 2.3 Archive-release metadata (file-level; per-row when the header
      pass finds more than one release); units from the header in the
      same metadata map.
- [x] 2.4 Per-county error containment; no stub file for an all-fail
      county; durable machine-readable run record written beside the
      output; county count reports counties actually written.
- [x] 2.5 Batch flushing per station file (~1M rows) instead of
      whole-county buffering — the dataset-wide union widens every
      county, and an OOM is invisible to per-county containment.
- [x] 2.6 `parse --dataset <d>` constructs `<out>/obs/<dataset>/…`
      itself; decide and document float storage precision (f32 vs f64)
      rather than inheriting it.

## 3. Layout and documentation

- [x] 3.1 Move observations to `data/parquet/obs/<dataset>/`, derived
      tables to `data/parquet/derived/`; update the classifier code
      paths, `docs/station-history.md`, and the docs visualisation;
      leave a symlink at the old path for one change cycle rather than
      trusting a grep.
- [x] 3.2 Write `docs/DATA.md` (every file: path, producing change,
      schema summary, provenance, versioning, duplicate semantics).

## 4. Regeneration and reconciliation

- [x] 4.1 Re-run the hourly parse from untouched raw CSVs to the NEW
      paths, old tree untouched.
- [x] 4.1b Value-level comparison old vs new, per county: row count,
      per-column non-null count, min/max/sum for numeric columns (and
      max for ints, to learn whether i64 saturation already bit). Every
      difference explained in the run record. Old trees retired only
      after this passes.
- [x] 4.2 Establish the fate of the six files that failed the original
      parse pass; record their status (recovered / genuinely corrupt /
      absent) with counts — no silent gap.
- [ ] 4.3 Regenerate derived tables that depend on observation paths;
      refresh the UNAS backup.

## 5. Close out

- [ ] 5.1 Validate --strict; roast; fold; re-roast to verdict; archive;
      vault note via coordinator.
