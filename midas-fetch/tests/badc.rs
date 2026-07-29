//! Integration tests for the BADC-CSV reader, driven by fixtures cut from
//! real MIDAS Open files (see tests/fixtures/). Spec: openspec change
//! add-badc-parser, capability badc-parse.

use midas_fetch::badc::{ColumnType, Value, parse_file};

fn fixture(name: &str) -> String {
    std::fs::read_to_string(format!("{}/tests/fixtures/{name}", env!("CARGO_MANIFEST_DIR")))
        .unwrap()
}

#[test]
fn header_attributes_extracted() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    assert_eq!(f.attributes.get("observation_station").unwrap(), "bristol-weather-centre");
    assert_eq!(f.attributes.get("historic_county_name").unwrap(), "avon");
}

#[test]
fn header_column_types_declared() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    assert_eq!(f.column_type("air_temperature"), Some(ColumnType::Float));
    assert_eq!(f.column_type("src_id"), Some(ColumnType::Int));
    // ob_time is declared `char` but marked as the time coordinate via
    // `coordinate_variable,ob_time,t` — the reader must promote it to Time.
    assert_eq!(f.column_type("ob_time"), Some(ColumnType::Time));
}

#[test]
fn data_section_bounded() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    // fixtures carry exactly 5 observation rows
    assert_eq!(f.rows.len(), 5);
    // and the first column row is the header row, not data
    assert_eq!(f.columns[0], "ob_time");
}

#[test]
fn na_becomes_null() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    let has_null = f
        .rows
        .iter()
        .flat_map(|r| r.iter())
        .any(|v| matches!(v, Value::Null));
    assert!(has_null, "expected at least one NA -> Null in fixture rows");
    // and no literal "NA" strings survive
    let stray_na = f
        .rows
        .iter()
        .flat_map(|r| r.iter())
        .any(|v| matches!(v, Value::Str(s) if s == "NA"));
    assert!(!stray_na);
}

#[test]
fn ob_time_parsed_as_datetime() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    let i = f.columns.iter().position(|c| c == "ob_time").unwrap();
    match &f.rows[0][i] {
        Value::Time(t) => assert_eq!(t.format("%M:%S").to_string(), "00:00"),
        other => panic!("ob_time not parsed as Time: {other:?}"),
    }
}

#[test]
fn quality_columns_kept_as_strings() {
    let f = parse_file(&fixture("modern.csv")).unwrap();
    let i = f
        .columns
        .iter()
        .position(|c| c == "air_temperature_q")
        .unwrap();
    assert!(
        f.rows
            .iter()
            .all(|r| matches!(&r[i], Value::Str(_) | Value::Null)),
        "quality flags must stay strings (or null), never numbers"
    );
}

#[test]
fn src_id_attribution() {
    let f = parse_file(&fixture("second-station.csv")).unwrap();
    let i = f.columns.iter().position(|c| c == "src_id").unwrap();
    assert!(matches!(f.rows[0][i], Value::Int(62122)));
}

#[test]
fn truncated_file_is_corrupt() {
    let err = parse_file(&fixture("truncated.csv")).unwrap_err().to_string();
    assert!(err.contains("end data"), "error should name the missing marker: {err}");
}

#[test]
fn bad_int_coerced_to_null_and_counted() {
    // Real MIDAS files carry WMO markers ("/", "&") in declared-int cloud
    // columns; the parser nulls them and counts the coercion — never silent.
    let f = parse_file(&fixture("bad-int.csv")).unwrap();
    assert_eq!(f.coerced_nulls, 1, "one corrupted int must be counted");
    let i = f.columns.iter().position(|c| c == "src_id").unwrap();
    assert!(matches!(f.rows[0][i], Value::Null), "the bad token must become null");
}

#[test]
fn bad_header_fails() {
    assert!(parse_file(&fixture("bad-header.csv")).is_err());
}

#[test]
fn differing_column_sets_parse_independently() {
    // A minimal synthetic file with a reduced column set — the parser must
    // take its schema from the file, not from a hardcoded layout.
    let mini = "\
Conventions,G,BADC-CSV,1
observation_station,G,testville
coordinate_variable,ob_time,t
type,ob_time,char
type,src_id,int
type,air_temperature,float
data
ob_time,src_id,air_temperature
2020-01-01 00:00:00,999,1.5
2020-01-01 01:00:00,999,NA
end data
";
    let f = parse_file(mini).unwrap();
    assert_eq!(f.columns.len(), 3);
    assert_eq!(f.rows.len(), 2);
    let i = f.columns.iter().position(|c| c == "air_temperature").unwrap();
    assert!(matches!(f.rows[0][i], Value::Float(x) if (x - 1.5).abs() < 1e-6));
    assert!(matches!(f.rows[1][i], Value::Null));
}

// ---------------------------------------------------------------------------
// harden-parquet-provenance: badc-parse fixes (tasks 1.1, 1.2)
// ---------------------------------------------------------------------------

use midas_fetch::badc::{parse_header, parse_int_lenient};

#[test]
fn lenient_int_table_driven() {
    // spec: accept float-formatted integers; reject fractions, WMO markers,
    // out-of-range magnitudes and non-finite tokens — never saturate.
    let accept: &[(&str, i64)] = &[
        ("300", 300),
        ("300.0", 300),
        ("-5", -5),
        ("0", 0),
        ("9223372036854775807", i64::MAX),
        ("-9223372036854775808", i64::MIN),
    ];
    for (raw, want) in accept {
        assert_eq!(parse_int_lenient(raw), Some(*want), "should accept {raw:?}");
    }
    let reject = ["300.5", "/", "&", "", "1e30", "-1e30", "inf", "-inf", "NaN",
                  "9223372036854775808.0", "abc"];
    for raw in reject {
        assert_eq!(parse_int_lenient(raw), None, "should reject {raw:?}");
    }
}

fn mini(rows: &str) -> String {
    format!(
        "Conventions,G,BADC-CSV,1\n\
         observation_station,G,testville\n\
         collection_version_number,G,dataset-version-202507\n\
         coordinate_variable,ob_time,t\n\
         type,ob_time,char\n\
         type,src_id,int\n\
         type,air_temperature,float\n\
         long_name,air_temperature,Air temperature,degC\n\
         data\n\
         ob_time,src_id,air_temperature\n\
         {rows}end data\n"
    )
}

#[test]
fn non_finite_floats_rejected_and_counted() {
    let f = parse_file(&mini(
        "2020-01-01 00:00:00,999,inf\n2020-01-01 01:00:00,999,NaN\n2020-01-01 02:00:00,999,1.5\n",
    ))
    .unwrap();
    let i = f.columns.iter().position(|c| c == "air_temperature").unwrap();
    assert!(matches!(f.rows[0][i], Value::Null), "inf must be nulled");
    assert!(matches!(f.rows[1][i], Value::Null), "NaN must be nulled");
    assert!(matches!(f.rows[2][i], Value::Float(x) if (x - 1.5).abs() < 1e-6));
    assert_eq!(f.col_counts.get("air_temperature").unwrap().coerced, 2);
}

#[test]
fn float_garbage_coerces_instead_of_aborting() {
    // previously a bad float aborted the whole station-year
    let f = parse_file(&mini("2020-01-01 00:00:00,999,abc\n")).unwrap();
    let i = f.columns.iter().position(|c| c == "air_temperature").unwrap();
    assert!(matches!(f.rows[0][i], Value::Null));
    assert_eq!(f.col_counts.get("air_temperature").unwrap().coerced, 1);
}

#[test]
fn datetime_garbage_coerces_instead_of_aborting() {
    let f = parse_file(&mini("not-a-date,999,1.5\n")).unwrap();
    let i = f.columns.iter().position(|c| c == "ob_time").unwrap();
    assert!(matches!(f.rows[0][i], Value::Null));
    assert_eq!(f.col_counts.get("ob_time").unwrap().coerced, 1);
}

#[test]
fn empty_fields_counted_separately_from_na() {
    let f = parse_file(&mini(
        "2020-01-01 00:00:00,999,NA\n2020-01-01 01:00:00,999,\n2020-01-01 02:00:00,999,NA\n",
    ))
    .unwrap();
    let c = f.col_counts.get("air_temperature").unwrap();
    assert_eq!(c.na, 2, "NA sentinel count");
    assert_eq!(c.empty, 1, "empty-field count is separate");
    assert_eq!(c.coerced, 0);
}

#[test]
fn per_column_attribution() {
    let f = parse_file(&mini(
        "2020-01-01 00:00:00,xxx,abc\n2020-01-01 01:00:00,yyy,1.5\n",
    ))
    .unwrap();
    assert_eq!(f.col_counts.get("src_id").unwrap().coerced, 2);
    assert_eq!(f.col_counts.get("air_temperature").unwrap().coerced, 1);
    assert_eq!(f.coerced_nulls, 3, "total remains the sum of per-column counts");
}

#[test]
fn undeclared_column_fallback_counted() {
    // column `mystery` appears in the data section with no type declaration
    let src = "Conventions,G,BADC-CSV,1\n\
               coordinate_variable,ob_time,t\n\
               type,ob_time,char\n\
               type,src_id,int\n\
               data\n\
               ob_time,src_id,mystery\n\
               2020-01-01 00:00:00,999,42\n\
               2020-01-01 01:00:00,999,43\n\
               end data\n";
    let f = parse_file(src).unwrap();
    assert_eq!(f.undeclared.get("mystery"), Some(&2), "two values took the string fallback");
    let i = f.columns.iter().position(|c| c == "mystery").unwrap();
    assert!(matches!(&f.rows[0][i], Value::Str(s) if s == "42"));
}

#[test]
fn header_only_parse_matches_full_parse() {
    let content = fixture("modern.csv");
    let h = parse_header(&content).unwrap();
    let f = parse_file(&content).unwrap();
    assert_eq!(h.columns, f.columns);
    assert_eq!(h.attributes.get("collection_version_number"),
               f.attributes.get("collection_version_number"));
    for c in &h.columns {
        assert_eq!(h.types.get(c), f.types.get(c), "type of {c}");
    }
    assert_eq!(h.units.get("air_temperature").map(String::as_str), Some("degC"));
}
