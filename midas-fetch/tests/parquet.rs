//! Tests for the county Parquet writer. Spec: openspec change
//! add-badc-parser, capability parquet-output.

use arrow::array::{Array, Float32Array, Int64Array, StringArray};
use midas_fetch::badc::parse_file;
use midas_fetch::parquet_out::{StationFile, write_county};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

fn fixture(name: &str) -> String {
    std::fs::read_to_string(format!("{}/tests/fixtures/{name}", env!("CARGO_MANIFEST_DIR")))
        .unwrap()
}

/// Two stations with different column sets -> one county file, union schema.
#[test]
fn county_roundtrip_with_union_schema() {
    let full = parse_file(&fixture("modern.csv")).unwrap();
    let mini = parse_file(
        "Conventions,G,BADC-CSV,1\n\
         observation_station,G,testville\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\n\
         type,src_id,int\n\
         type,air_temperature,float\n\
         data\n\
         ob_time,src_id,air_temperature\n\
         2020-01-01 00:00:00,999,1.5\n\
         2020-01-01 01:00:00,999,NA\n\
         end data\n",
    )
    .unwrap();

    let dir = std::env::temp_dir().join("midas-fetch-test-parquet");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("avon.parquet");

    let ha = midas_fetch::badc::parse_header(&fixture("modern.csv")).unwrap();
    let hb = midas_fetch::badc::parse_header(
        "Conventions,G,BADC-CSV,1\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\nend data\n",
    )
    .unwrap();
    let ds = midas_fetch::parquet_out::build_union(&[("a".into(), &ha), ("b".into(), &hb)])
        .unwrap();
    let stations = vec![
        StationFile {
            county: "avon".into(),
            station_dir: "00675_bristol-weather-centre".into(),
            src_id: 675,
            source_file: "modern_1995.csv".into(),
            file: full,
        },
        StationFile {
            county: "avon".into(),
            station_dir: "99999_testville".into(),
            src_id: 99999,
            source_file: "mini_2020.csv".into(),
            file: mini,
        },
    ];
    let report = write_county(&out, &stations, &ds, 1_000_000).unwrap();
    assert_eq!(report.rows_written, 7); // 5 + 2

    // --- re-read and verify ---
    let reader = ParquetRecordBatchReaderBuilder::try_new(std::fs::File::open(&out).unwrap())
        .unwrap()
        .build()
        .unwrap();
    let batches: Vec<_> = reader.map(|b| b.unwrap()).collect();
    let batch = arrow::compute::concat_batches(&batches[0].schema(), &batches).unwrap();
    assert_eq!(batch.num_rows(), 7);

    let schema = batch.schema();

    // station attribution columns exist
    let county = batch
        .column(schema.index_of("county").unwrap())
        .as_any()
        .downcast_ref::<StringArray>()
        .unwrap();
    assert_eq!(county.value(0), "avon");

    let src = batch
        .column(schema.index_of("src_id").unwrap())
        .as_any()
        .downcast_ref::<Int64Array>()
        .unwrap();
    assert_eq!(src.value(0), 675);
    assert_eq!(src.value(6), 99999);

    // union schema: modern.csv's wind_speed exists; null for the mini rows
    let wind = batch
        .column(schema.index_of("wind_speed").unwrap())
        .as_any()
        .downcast_ref::<Float32Array>()
        .unwrap();
    assert!(wind.is_null(5) && wind.is_null(6), "mini-station rows must be null for absent columns");

    // values survive the round trip
    let temp = batch
        .column(schema.index_of("air_temperature").unwrap())
        .as_any()
        .downcast_ref::<Float32Array>()
        .unwrap();
    assert!((temp.value(5) - 1.5).abs() < 1e-6);
    assert!(temp.is_null(6)); // the NA row

    std::fs::remove_dir_all(&dir).ok();
}

// ---------------------------------------------------------------------------
// harden-parquet-provenance: parquet-output fixes (tasks 2.1-2.6)
// ---------------------------------------------------------------------------

use arrow::array::TimestampMillisecondArray;
use arrow::datatypes::{DataType, TimeUnit};
use midas_fetch::badc::parse_header;
use midas_fetch::parquet_out::build_union;

fn header_src(version: &str, cols: &[(&str, &str)]) -> String {
    let mut s = format!(
        "Conventions,G,BADC-CSV,1\ncollection_version_number,G,{version}\n\
         coordinate_variable,ob_time,t\ntype,ob_time,char\n"
    );
    for (c, t) in cols {
        s.push_str(&format!("type,{c},{t}\n"));
    }
    s.push_str("data\nob_time");
    for (c, _) in cols {
        s.push_str(&format!(",{c}"));
    }
    s.push_str("\nend data\n");
    s
}

#[test]
fn union_widens_numeric_conflict_and_records_it() {
    let a = parse_header(&header_src("dataset-version-202507", &[("wind", "int")])).unwrap();
    let b = parse_header(&header_src("dataset-version-202507", &[("wind", "float")])).unwrap();
    let ds = build_union(&[("st-a".into(), &a), ("st-b".into(), &b)]).unwrap();
    use midas_fetch::badc::ColumnType;
    assert_eq!(ds.columns.get("wind"), Some(&ColumnType::Float), "int+float widens to float");
    assert_eq!(ds.widenings.len(), 1);
    let w = &ds.widenings[0];
    assert_eq!(w.column, "wind");
    assert!(w.stations.contains(&"st-a".to_string()) && w.stations.contains(&"st-b".to_string()),
            "both declaring stations recorded: {:?}", w.stations);
}

#[test]
fn union_aborts_on_numeric_vs_string_naming_both_stations() {
    let a = parse_header(&header_src("dataset-version-202507", &[("code", "int")])).unwrap();
    let b = parse_header(&header_src("dataset-version-202507", &[("code", "char")])).unwrap();
    let err = build_union(&[("st-num".into(), &a), ("st-str".into(), &b)])
        .unwrap_err()
        .to_string();
    assert!(err.contains("code"), "column named: {err}");
    assert!(err.contains("st-num") && err.contains("st-str"), "both stations named: {err}");
}

#[test]
fn union_merges_complementary_columns_and_releases() {
    let a = parse_header(&header_src("dataset-version-202507", &[("wind", "int")])).unwrap();
    let b = parse_header(&header_src("dataset-version-202601", &[("temp", "float")])).unwrap();
    let ds = build_union(&[("a".into(), &a), ("b".into(), &b)]).unwrap();
    assert!(ds.columns.contains_key("wind") && ds.columns.contains_key("temp"));
    assert_eq!(ds.releases.len(), 2, "distinct releases collected");
}

fn write_two_stations(dir_name: &str, rows_per_flush: usize) -> std::path::PathBuf {
    let full = parse_file(&fixture("modern.csv")).unwrap();
    let mini = parse_file(
        "Conventions,G,BADC-CSV,1\n\
         observation_station,G,testville\n\
         collection_version_number,G,dataset-version-202507\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\n\
         type,src_id,int\n\
         type,air_temperature,float\n\
         data\n\
         ob_time,src_id,air_temperature\n\
         2020-01-01 00:00:00,999,1.5\n\
         2020-01-01 01:00:00,999,NA\n\
         end data\n",
    )
    .unwrap();
    let ha = parse_header(&fixture("modern.csv")).unwrap();
    let content_b = "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,dataset-version-202507\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\nend data\n";
    let hb = parse_header(content_b).unwrap();
    let ds = build_union(&[("a".into(), &ha), ("b".into(), &hb)]).unwrap();

    let dir = std::env::temp_dir().join(dir_name);
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("avon.parquet");
    let stations = vec![
        StationFile {
            county: "avon".into(),
            station_dir: "00675_bristol-weather-centre".into(),
            src_id: 675,
            source_file: "..._1995.csv".into(),
            file: full,
        },
        StationFile {
            county: "avon".into(),
            station_dir: "99999_testville".into(),
            src_id: 99999,
            source_file: "..._2020.csv".into(),
            file: mini,
        },
    ];
    write_county(&out, &stations, &ds, rows_per_flush).unwrap();
    out
}

fn read_all(out: &std::path::Path) -> (arrow::record_batch::RecordBatch, std::collections::HashMap<String, String>) {
    let reader = ParquetRecordBatchReaderBuilder::try_new(std::fs::File::open(out).unwrap()).unwrap();
    let meta: std::collections::HashMap<String, String> = reader
        .schema()
        .metadata()
        .clone()
        .into_iter()
        .collect();
    let batches: Vec<_> = reader.build().unwrap().map(|b| b.unwrap()).collect();
    let batch = arrow::compute::concat_batches(&batches[0].schema(), &batches).unwrap();
    (batch, meta)
}

#[test]
fn ob_time_is_utc_annotated_and_value_round_trips() {
    let out = write_two_stations("mf-test-utc", 1_000_000);
    let (batch, _) = read_all(&out);
    let schema = batch.schema();
    let f = schema.field_with_name("ob_time").unwrap();
    match f.data_type() {
        DataType::Timestamp(TimeUnit::Millisecond, Some(tz)) => assert_eq!(tz.as_ref(), "UTC"),
        other => panic!("ob_time must be UTC-annotated, got {other:?}"),
    }
    // modern.csv's first row is 1995-01-01 00:00:00 GMT = epoch 788918400
    let col = batch
        .column(schema.index_of("ob_time").unwrap())
        .as_any()
        .downcast_ref::<TimestampMillisecondArray>()
        .unwrap();
    assert_eq!(col.value(0), 788_918_400_000, "known timestamp value must round-trip");
    std::fs::remove_dir_all(out.parent().unwrap()).ok();
}

#[test]
fn file_metadata_carries_release_and_units() {
    let out = write_two_stations("mf-test-meta", 1_000_000);
    let (_, meta) = read_all(&out);
    assert_eq!(meta.get("midas:collection_version_number").map(String::as_str),
               Some("dataset-version-202507"));
    let units: std::collections::HashMap<String, String> =
        serde_json::from_str(meta.get("midas:units").unwrap()).unwrap();
    assert_eq!(units.get("air_temperature").map(String::as_str), Some("degC"));
    std::fs::remove_dir_all(out.parent().unwrap()).ok();
}

#[test]
fn batch_flushing_preserves_rows() {
    // flush every 3 rows: 7 rows -> multiple batches, same content
    let out = write_two_stations("mf-test-flush", 3);
    let (batch, _) = read_all(&out);
    assert_eq!(batch.num_rows(), 7);
    std::fs::remove_dir_all(out.parent().unwrap()).ok();
}

#[test]
fn dataset_schema_applies_columns_missing_from_every_station_in_county() {
    // a column declared only in another county appears here as all-null
    let ha = parse_header(&header_src("dataset-version-202507", &[("only_elsewhere", "float")])).unwrap();
    let content_b = "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,dataset-version-202507\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\nend data\n";
    let hb = parse_header(content_b).unwrap();
    let ds = build_union(&[("other-county-station".into(), &ha), ("local".into(), &hb)]).unwrap();

    let mini = parse_file(
        "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,dataset-version-202507\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\n\
         2020-01-01 00:00:00,7,2.5\n\
         end data\n",
    )
    .unwrap();
    let dir = std::env::temp_dir().join("mf-test-cross-county");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("c.parquet");
    write_county(
        &out,
        &[StationFile {
            county: "c".into(),
            station_dir: "00007_local".into(),
            src_id: 7,
            source_file: "f.csv".into(),
            file: mini,
        }],
        &ds,
        1_000_000,
    )
    .unwrap();
    let (batch, _) = read_all(&out);
    let schema = batch.schema();
    let col = batch.column(schema.index_of("only_elsewhere").unwrap());
    assert_eq!(col.null_count(), 1, "column from another county present and null");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn no_stub_file_for_empty_station_list() {
    let ha = parse_header(&fixture("modern.csv")).unwrap();
    let ds = build_union(&[("a".into(), &ha)]).unwrap();
    let dir = std::env::temp_dir().join("mf-test-stub");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("empty.parquet");
    let report = write_county(&out, &[], &ds, 1_000_000).unwrap();
    assert_eq!(report.rows_written, 0);
    assert!(!out.exists(), "an all-fail county must not leave a stub file");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn src_id_mismatch_counted_not_laundered() {
    // in-file src_id 62122 vs directory-derived 675: directory value wins in
    // the column, but the disagreement is counted per file
    let second = parse_file(&fixture("second-station.csv")).unwrap();
    let h = parse_header(&fixture("second-station.csv")).unwrap();
    let ds = build_union(&[("s".into(), &h)]).unwrap();
    let dir = std::env::temp_dir().join("mf-test-mismatch");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("x.parquet");
    let report = write_county(
        &out,
        &[StationFile {
            county: "x".into(),
            station_dir: "00675_wrong-dir".into(),
            src_id: 675,
            source_file: "second_1995.csv".into(),
            file: second,
        }],
        &ds,
        1_000_000,
    )
    .unwrap();
    assert_eq!(report.src_id_mismatches.len(), 1);
    assert_eq!(report.src_id_mismatches[0].0, "second_1995.csv");
    assert!(report.src_id_mismatches[0].1 > 0);
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn per_row_release_column_when_releases_mix() {
    let full = parse_file(&fixture("modern.csv")).unwrap(); // 202507
    let other = parse_file(
        "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,dataset-version-202601\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\n\
         2020-01-01 00:00:00,5,1.0\n\
         end data\n",
    )
    .unwrap();
    let ha = parse_header(&fixture("modern.csv")).unwrap();
    let hb = parse_header(
        "Conventions,G,BADC-CSV,1\n\
         collection_version_number,G,dataset-version-202601\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\ntype,src_id,int\ntype,air_temperature,float\n\
         data\nob_time,src_id,air_temperature\nend data\n",
    )
    .unwrap();
    let ds = build_union(&[("a".into(), &ha), ("b".into(), &hb)]).unwrap();
    assert_eq!(ds.releases.len(), 2);

    let dir = std::env::temp_dir().join("mf-test-two-releases");
    std::fs::create_dir_all(&dir).unwrap();
    let out = dir.join("m.parquet");
    write_county(
        &out,
        &[
            StationFile { county: "m".into(), station_dir: "a".into(), src_id: 675,
                          source_file: "a.csv".into(), file: full },
            StationFile { county: "m".into(), station_dir: "b".into(), src_id: 5,
                          source_file: "b.csv".into(), file: other },
        ],
        &ds,
        1_000_000,
    )
    .unwrap();
    let (batch, meta) = read_all(&out);
    let schema = batch.schema();
    let rel = batch
        .column(schema.index_of("collection_version").unwrap())
        .as_any()
        .downcast_ref::<StringArray>()
        .unwrap();
    assert_eq!(rel.value(0), "dataset-version-202507");
    assert_eq!(rel.value(5), "dataset-version-202601");
    assert!(meta.get("midas:collection_version_number").unwrap().contains("202507"));
    std::fs::remove_dir_all(&dir).ok();
}
