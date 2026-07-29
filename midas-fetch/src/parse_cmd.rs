//! `parse` subcommand: two-pass parse of data/raw/<county>/<station>/
//! qc-version-N/ into one Parquet per county under
//! `<out>/obs/<dataset>/`.
//!
//! Pass 1 (schema): header-only parse of every file, dataset-wide union
//! under the spec'd conflict policy (numeric widens, numeric-vs-string
//! aborts before any output). Pass 2 (write): full parse per county in
//! parallel, written against the frozen schema; a failing file or county
//! is recorded and the run continues. A machine-readable run record is
//! written beside the output — a printed summary is not durable.

use crate::badc;
use crate::parquet_out::{DatasetSchema, StationFile, build_union, write_county};
use anyhow::{Context, Result};
use rayon::prelude::*;
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const ROWS_PER_FLUSH: usize = 1_000_000;

#[derive(Serialize, Default)]
pub struct RunRecord {
    pub dataset: String,
    pub qc_version: u8,
    pub raw_dir: String,
    pub started: String,
    pub finished: String,
    pub releases: Vec<String>,
    pub schema_columns: usize,
    pub schema_widenings: Vec<crate::parquet_out::Widening>,
    pub counties_written: usize,
    pub counties_skipped_all_failed: Vec<String>,
    pub rows_per_county: BTreeMap<String, usize>,
    pub files_parsed: usize,
    pub total_rows: usize,
    /// Per-(file, column) counts, only non-zero entries.
    pub coercions: Vec<FileColumnCount>,
    pub empty_fields: Vec<FileColumnCount>,
    pub undeclared_fallbacks: Vec<FileColumnCount>,
    pub src_id_mismatches: Vec<FileCount>,
    pub failures: Vec<Failure>,
}

#[derive(Serialize)]
pub struct FileColumnCount {
    pub file: String,
    pub column: String,
    pub count: usize,
}

#[derive(Serialize)]
pub struct FileCount {
    pub file: String,
    pub count: usize,
}

#[derive(Serialize)]
pub struct Failure {
    pub path: String,
    pub error: String,
}

fn now_utc() -> String {
    chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

struct Job {
    county: String,
    station_dir: String,
    src_id: i64,
    path: PathBuf,
}

fn collect_jobs(raw: &Path, county_filter: Option<&str>, qc: u8) -> Result<Vec<Job>> {
    let mut counties: Vec<PathBuf> = std::fs::read_dir(raw)
        .with_context(|| format!("reading {} — has `fetch` run?", raw.display()))?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.is_dir())
        .filter(|p| county_filter.is_none_or(|c| p.file_name().is_some_and(|n| n == c)))
        .collect();
    counties.sort();

    let mut jobs = Vec::new();
    for county_path in &counties {
        let county = county_path.file_name().unwrap().to_string_lossy().to_string();
        for st in std::fs::read_dir(county_path)?.filter_map(|e| e.ok()) {
            let st_path = st.path();
            if !st_path.is_dir() {
                continue;
            }
            let station_dir = st.file_name().to_string_lossy().to_string();
            let src_id: i64 = station_dir
                .split('_')
                .next()
                .and_then(|s| s.parse().ok())
                .with_context(|| format!("station dir {station_dir} has no numeric prefix"))?;
            let qc_dir = st_path.join(format!("qc-version-{qc}"));
            if let Ok(entries) = std::fs::read_dir(&qc_dir) {
                for f in entries.filter_map(|e| e.ok()) {
                    if f.path().extension().is_some_and(|x| x == "csv") {
                        jobs.push(Job {
                            county: county.clone(),
                            station_dir: station_dir.clone(),
                            src_id,
                            path: f.path(),
                        });
                    }
                }
            }
        }
    }
    Ok(jobs)
}

/// Short file label for reports: <county>/<station>/<file name>.
fn file_label(job: &Job) -> String {
    format!(
        "{}/{}/{}",
        job.county,
        job.station_dir,
        job.path.file_name().unwrap_or_default().to_string_lossy()
    )
}

pub fn run(
    raw_dir: &str,
    out_dir: &str,
    county_filter: Option<&str>,
    qc: u8,
    dataset: &str,
) -> Result<()> {
    let raw = Path::new(raw_dir);
    let out_root = Path::new(out_dir).join("obs").join(dataset);
    let mut record = RunRecord {
        dataset: dataset.to_string(),
        qc_version: qc,
        raw_dir: raw_dir.to_string(),
        started: now_utc(),
        ..Default::default()
    };

    let jobs = collect_jobs(raw, county_filter, qc)?;
    println!("{} files to parse", jobs.len());

    // --- pass 1: header-only union schema, abort-before-write on conflict ---
    let headers: Vec<std::result::Result<(String, badc::Header), (PathBuf, String)>> = jobs
        .par_iter()
        .map(|j| {
            let content =
                std::fs::read_to_string(&j.path).map_err(|e| (j.path.clone(), e.to_string()))?;
            let h = badc::parse_header(&content)
                .map_err(|e| (j.path.clone(), format!("{e:#}")))?;
            Ok((j.station_dir.clone(), h))
        })
        .collect();
    let mut header_pairs: Vec<(String, badc::Header)> = Vec::new();
    let mut header_failures: Vec<(PathBuf, String)> = Vec::new();
    for h in headers {
        match h {
            Ok(p) => header_pairs.push(p),
            Err(f) => header_failures.push(f),
        }
    }
    let refs: Vec<(String, &badc::Header)> =
        header_pairs.iter().map(|(s, h)| (s.clone(), h)).collect();
    let ds: DatasetSchema = build_union(&refs)?; // conflict aborts here, pre-output
    println!(
        "schema pass: {} columns, {} widenings, releases: {:?}",
        ds.columns.len(),
        ds.widenings.len(),
        ds.releases
    );
    record.releases = ds.releases.iter().cloned().collect();
    record.schema_columns = ds.columns.len();
    record.schema_widenings = ds.widenings.clone();

    // --- pass 2: full parse + write per county against the frozen schema ---
    // files that failed the header pass cannot parse; skip them rather than
    // fail (and record) the same file twice
    let header_failed: std::collections::HashSet<&PathBuf> =
        header_failures.iter().map(|(p, _)| p).collect();
    // every county with any raw file appears here, so a county whose files
    // all failed the header pass is still reported as skipped
    let mut by_county: BTreeMap<String, Vec<&Job>> = BTreeMap::new();
    for j in &jobs {
        by_county.entry(j.county.clone()).or_default();
    }
    for j in jobs.iter().filter(|j| !header_failed.contains(&j.path)) {
        by_county.get_mut(&j.county).unwrap().push(j);
    }

    let mut failures: Vec<(PathBuf, String)> = header_failures.clone();
    for (county, county_jobs) in &by_county {
        let parsed: Vec<std::result::Result<StationFile, (PathBuf, String)>> = county_jobs
            .par_iter()
            .map(|j| {
                let content = std::fs::read_to_string(&j.path)
                    .map_err(|e| (j.path.clone(), e.to_string()))?;
                let file =
                    badc::parse_file(&content).map_err(|e| (j.path.clone(), format!("{e:#}")))?;
                Ok(StationFile {
                    county: j.county.clone(),
                    station_dir: j.station_dir.clone(),
                    src_id: j.src_id,
                    source_file: file_label(j),
                    file,
                })
            })
            .collect();

        let mut stations = Vec::new();
        for r in parsed {
            match r {
                Ok(s) => stations.push(s),
                Err(f) => failures.push(f),
            }
        }
        if stations.is_empty() {
            record.counties_skipped_all_failed.push(county.clone());
            eprintln!("{county}: every file failed — no output written");
            continue;
        }
        record.files_parsed += stations.len();

        // per-(file, column) tallies into the run record
        for s in &stations {
            for (col, c) in &s.file.col_counts {
                if c.coerced > 0 {
                    record.coercions.push(FileColumnCount {
                        file: s.source_file.clone(),
                        column: col.clone(),
                        count: c.coerced,
                    });
                }
                if c.empty > 0 {
                    record.empty_fields.push(FileColumnCount {
                        file: s.source_file.clone(),
                        column: col.clone(),
                        count: c.empty,
                    });
                }
            }
            for (col, n) in &s.file.undeclared {
                record.undeclared_fallbacks.push(FileColumnCount {
                    file: s.source_file.clone(),
                    column: col.clone(),
                    count: *n,
                });
            }
        }

        // a failing county is recorded and the run continues
        let out = out_root.join(format!("{county}.parquet"));
        match write_county(&out, &stations, &ds, ROWS_PER_FLUSH) {
            Ok(report) => {
                record.total_rows += report.rows_written;
                record.rows_per_county.insert(county.clone(), report.rows_written);
                record.counties_written += 1;
                for (file, count) in report.src_id_mismatches {
                    record.src_id_mismatches.push(FileCount { file, count });
                }
                println!("{county}: {} files, {} rows", stations.len(), report.rows_written);
            }
            Err(e) => {
                failures.push((out.clone(), format!("county write failed: {e:#}")));
                eprintln!("FAIL {county}: {e:#}");
            }
        }
    }

    record.failures = failures
        .iter()
        .map(|(p, e)| Failure { path: p.display().to_string(), error: e.clone() })
        .collect();
    record.finished = now_utc();

    let total_coerced: usize = record.coercions.iter().map(|c| c.count).sum();
    println!(
        "\nparsed {} files, wrote {} rows across {} counties, {} failures, \
         {total_coerced} values coerced to null",
        record.files_parsed,
        record.total_rows,
        record.counties_written,
        record.failures.len()
    );
    for f in &record.failures {
        eprintln!("FAIL {}: {}", f.path, f.error);
    }

    std::fs::create_dir_all(&out_root)?;
    let record_path = out_root.join("run-record.json");
    std::fs::write(&record_path, serde_json::to_string_pretty(&record)?)
        .with_context(|| format!("writing {}", record_path.display()))?;
    println!("run record -> {}", record_path.display());
    Ok(())
}
