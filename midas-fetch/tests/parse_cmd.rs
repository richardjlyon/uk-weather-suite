//! Integration tests for the two-pass `parse` command on synthetic raw
//! trees. Spec: parquet-output (harden-parquet-provenance).

use midas_fetch::parse_cmd::run;
use std::path::Path;

fn station_csv(version: &str, type_decl: &str, rows: &str) -> String {
    format!(
        "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,{version}\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\n\
         type,src_id,int\n\
         {type_decl}\n\
         data\n\
         ob_time,src_id,wind_speed\n\
         {rows}end data\n"
    )
}

fn write_station(raw: &Path, county: &str, station: &str, year: u32, content: &str) {
    let dir = raw.join(county).join(station).join("qc-version-1");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join(format!("{station}_{year}.csv")), content).unwrap();
}

fn temp_tree(name: &str) -> (std::path::PathBuf, std::path::PathBuf) {
    let base = std::env::temp_dir().join(name);
    std::fs::remove_dir_all(&base).ok();
    let raw = base.join("raw");
    let out = base.join("out");
    std::fs::create_dir_all(&raw).unwrap();
    (raw, out)
}

#[test]
fn two_counties_one_schema_and_run_record() {
    let (raw, out) = temp_tree("mf-cmd-happy");
    write_station(&raw, "avon", "00001_alpha", 1990,
        &station_csv("dataset-version-202507", "type,wind_speed,int",
                     "1990-01-01 00:00:00,1,5\n"));
    write_station(&raw, "kent", "00002_beta", 1991,
        &station_csv("dataset-version-202507", "type,wind_speed,float",
                     "1991-01-01 00:00:00,2,5.5\n"));
    // a corrupt file must not sink its county
    let dir = raw.join("kent").join("00002_beta").join("qc-version-1");
    std::fs::write(dir.join("00002_beta_1992.csv"), "garbage with no data marker\n").unwrap();

    run(raw.to_str().unwrap(), out.to_str().unwrap(), None, 1, "test-ds").unwrap();

    let obs = out.join("obs").join("test-ds");
    assert!(obs.join("avon.parquet").exists());
    assert!(obs.join("kent.parquet").exists());

    let record: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(obs.join("run-record.json")).unwrap())
            .unwrap();
    assert_eq!(record["dataset"], "test-ds");
    assert_eq!(record["counties_written"], 2);
    assert_eq!(record["files_parsed"], 2);
    assert_eq!(record["releases"][0], "dataset-version-202507");
    // int-vs-float widening across counties is recorded
    assert_eq!(record["schema_widenings"][0]["column"], "wind_speed");
    // the corrupt file appears in failures with its path
    let failures = record["failures"].as_array().unwrap();
    assert_eq!(failures.len(), 1);
    assert!(failures[0]["path"].as_str().unwrap().contains("00002_beta_1992.csv"));
    // both files have started/finished stamps
    assert!(record["started"].as_str().unwrap().contains("T"));

    std::fs::remove_dir_all(raw.parent().unwrap()).ok();
}

#[test]
fn numeric_vs_string_conflict_aborts_with_no_output() {
    let (raw, out) = temp_tree("mf-cmd-abort");
    write_station(&raw, "avon", "00001_alpha", 1990,
        &station_csv("dataset-version-202507", "type,wind_speed,int",
                     "1990-01-01 00:00:00,1,5\n"));
    write_station(&raw, "kent", "00002_beta", 1991,
        &station_csv("dataset-version-202507", "type,wind_speed,char",
                     "1991-01-01 00:00:00,2,calm\n"));

    let err = run(raw.to_str().unwrap(), out.to_str().unwrap(), None, 1, "test-ds")
        .unwrap_err()
        .to_string();
    assert!(err.contains("wind_speed"), "column named: {err}");
    assert!(err.contains("00001_alpha") && err.contains("00002_beta"),
            "both stations named: {err}");
    assert!(!out.join("obs").join("test-ds").join("avon.parquet").exists(),
            "no output may exist after a schema abort");

    std::fs::remove_dir_all(raw.parent().unwrap()).ok();
}

#[test]
fn all_fail_county_writes_no_stub_and_run_continues() {
    let (raw, out) = temp_tree("mf-cmd-allfail");
    write_station(&raw, "avon", "00001_alpha", 1990,
        &station_csv("dataset-version-202507", "type,wind_speed,int",
                     "1990-01-01 00:00:00,1,5\n"));
    let dir = raw.join("kent").join("00002_beta").join("qc-version-1");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("00002_beta_1991.csv"), "no data marker here\n").unwrap();

    run(raw.to_str().unwrap(), out.to_str().unwrap(), None, 1, "test-ds").unwrap();

    let obs = out.join("obs").join("test-ds");
    assert!(obs.join("avon.parquet").exists());
    assert!(!obs.join("kent.parquet").exists(), "all-fail county must leave no stub");
    let record: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(obs.join("run-record.json")).unwrap())
            .unwrap();
    assert_eq!(record["counties_written"], 1);
    assert_eq!(record["counties_skipped_all_failed"][0], "kent");

    std::fs::remove_dir_all(raw.parent().unwrap()).ok();
}
