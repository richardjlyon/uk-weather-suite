//! County-level Parquet writer against a dataset-wide union schema.
//!
//! Spec (parquet-output, harden-parquet-provenance): the schema is built
//! once for the whole dataset in a header-only pass (`build_union`), with a
//! stated conflict policy — numeric conflicts widen to the wider numeric
//! type and are recorded; numeric-vs-string conflicts abort naming both
//! declaring stations. Every county then writes against that one schema.
//! `ob_time` is a UTC-annotated timestamp. Archive release and units are
//! written as file-level metadata; a per-row `collection_version` column is
//! added when a run ingests more than one release. Rows are flushed in
//! batches (per station file / ~1M rows), never whole-county buffered.

use crate::badc::{BadcFile, ColumnType, Header, Value};
use anyhow::{Context, Result};
use arrow::array::{ArrayRef, Float32Builder, Int64Builder, StringBuilder, TimestampMillisecondBuilder};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::WriterProperties;
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::path::Path;
use std::sync::Arc;

/// A parsed station-year file plus its archive context.
pub struct StationFile {
    pub county: String,
    pub station_dir: String,
    pub src_id: i64,
    /// Source file name, for per-file reporting.
    pub source_file: String,
    pub file: BadcFile,
}

pub struct WriteReport {
    pub rows_written: usize,
    /// (source_file, count of rows whose in-file src_id disagrees with the
    /// directory-derived one). The directory value wins in the column; the
    /// disagreement is reported, not laundered.
    pub src_id_mismatches: Vec<(String, usize)>,
}

/// A recorded int→float widening from the union pass.
#[derive(Debug, Clone, Serialize)]
pub struct Widening {
    pub column: String,
    pub from: String,
    pub to: String,
    /// The station that declared each side (int-declarer, float-declarer).
    pub stations: Vec<String>,
}

/// The dataset-wide schema, frozen before any file is written.
#[derive(Debug)]
pub struct DatasetSchema {
    pub columns: BTreeMap<String, ColumnType>,
    pub widenings: Vec<Widening>,
    pub releases: BTreeSet<String>,
    pub units: BTreeMap<String, String>,
}

impl DatasetSchema {
    pub fn per_row_release(&self) -> bool {
        self.releases.len() > 1
    }
}

/// Attribution columns added to every row.
const META_COLS: [(&str, ColumnType); 3] = [
    ("county", ColumnType::Str),
    ("station_file_name", ColumnType::Str),
    ("src_id", ColumnType::Int),
];
/// Per-row release column, present only when releases mix.
const RELEASE_COL: &str = "collection_version";

/// Build the dataset-wide union schema from header-only parses.
///
/// Conflict policy (fixed in spec, not configurable): Int vs Float widens
/// to Float and is recorded; any conflict involving a string or time
/// declaration aborts, naming the column and both declaring stations —
/// before any output exists.
pub fn build_union(headers: &[(String, &Header)]) -> Result<DatasetSchema> {
    let mut columns: BTreeMap<String, ColumnType> = BTreeMap::new();
    let mut declarer: BTreeMap<String, String> = BTreeMap::new();
    let mut widenings: Vec<Widening> = Vec::new();
    let mut releases: BTreeSet<String> = BTreeSet::new();
    let mut units: BTreeMap<String, String> = BTreeMap::new();

    for (station, h) in headers {
        if let Some(rel) = h.attributes.get("collection_version_number") {
            releases.insert(rel.trim().to_string());
        }
        for (col, unit) in &h.units {
            units.entry(col.clone()).or_insert_with(|| unit.clone());
        }
        for c in &h.columns {
            let ty = h.types.get(c).copied().unwrap_or(ColumnType::Str);
            match columns.get(c) {
                None => {
                    columns.insert(c.clone(), ty);
                    declarer.insert(c.clone(), station.clone());
                }
                Some(prev) if *prev == ty => {}
                Some(prev) => {
                    let first = declarer.get(c).cloned().unwrap_or_default();
                    match (*prev, ty) {
                        (ColumnType::Int, ColumnType::Float)
                        | (ColumnType::Float, ColumnType::Int) => {
                            if *prev == ColumnType::Int {
                                columns.insert(c.clone(), ColumnType::Float);
                            }
                            if !widenings.iter().any(|w| &w.column == c) {
                                widenings.push(Widening {
                                    column: c.clone(),
                                    from: "int".into(),
                                    to: "float".into(),
                                    stations: vec![first, station.clone()],
                                });
                            }
                        }
                        (a, b) => anyhow::bail!(
                            "schema conflict: column {c} declared {a:?} by station \
                             {first} and {b:?} by station {station} — \
                             numeric-vs-string conflicts abort before any output \
                             is written",
                        ),
                    }
                }
            }
        }
    }
    Ok(DatasetSchema { columns, widenings, releases, units })
}

fn arrow_fields(ds: &DatasetSchema) -> Vec<Field> {
    let mut union = ds.columns.clone();
    for (name, ty) in META_COLS {
        union.insert(name.to_string(), ty);
    }
    let mut fields: Vec<Field> = union
        .iter()
        .map(|(name, ty)| Field::new(name, arrow_type(*ty), true))
        .collect();
    if ds.per_row_release() {
        fields.push(Field::new(RELEASE_COL, DataType::Utf8, true));
    }
    fields.sort_by(|a, b| a.name().cmp(b.name()));
    fields
}

fn file_metadata(ds: &DatasetSchema) -> HashMap<String, String> {
    let mut m = HashMap::new();
    m.insert(
        "midas:collection_version_number".to_string(),
        ds.releases.iter().cloned().collect::<Vec<_>>().join(";"),
    );
    m.insert("midas:units".to_string(), serde_json::to_string(&ds.units).unwrap());
    if !ds.widenings.is_empty() {
        m.insert(
            "midas:schema_widenings".to_string(),
            serde_json::to_string(&ds.widenings).unwrap(),
        );
    }
    m.insert("midas:generator".to_string(),
             format!("midas-fetch {} (harden-parquet-provenance)", env!("CARGO_PKG_VERSION")));
    m
}

/// Write one county's stations against the frozen dataset schema, flushing
/// a batch per station file or every `rows_per_flush` rows. Writes no file
/// at all when `stations` is empty — an all-fail county must not leave a
/// meta-only stub.
pub fn write_county(
    out: &Path,
    stations: &[StationFile],
    ds: &DatasetSchema,
    rows_per_flush: usize,
) -> Result<WriteReport> {
    let mut report = WriteReport { rows_written: 0, src_id_mismatches: Vec::new() };
    if stations.is_empty() {
        return Ok(report);
    }

    let fields = arrow_fields(ds);
    let schema = Arc::new(Schema::new_with_metadata(fields, file_metadata(ds)));
    let names: Vec<String> = schema.fields().iter().map(|f| f.name().clone()).collect();

    if let Some(dir) = out.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let props =
        WriterProperties::builder().set_compression(Compression::ZSTD(Default::default())).build();
    let mut writer = ArrowWriter::try_new(
        std::fs::File::create(out).with_context(|| format!("creating {}", out.display()))?,
        schema.clone(),
        Some(props),
    )?;

    let new_builders = |schema: &Schema| -> Vec<Box<dyn ColBuilder>> {
        schema
            .fields()
            .iter()
            .map(|f| -> Box<dyn ColBuilder> {
                match f.data_type() {
                    DataType::Int64 => Box::new(Int64Builder::new()),
                    DataType::Float32 => Box::new(Float32Builder::new()),
                    DataType::Utf8 => Box::new(StringBuilder::new()),
                    DataType::Timestamp(TimeUnit::Millisecond, _) => {
                        Box::new(TimestampMillisecondBuilder::new().with_timezone("UTC"))
                    }
                    other => unreachable!("unhandled arrow type {other:?}"),
                }
            })
            .collect()
    };

    let mut builders = new_builders(&schema);
    let mut pending = 0usize;

    for s in stations {
        let col_index: BTreeMap<&str, usize> =
            s.file.columns.iter().enumerate().map(|(i, c)| (c.as_str(), i)).collect();
        let release = s
            .file
            .attributes
            .get("collection_version_number")
            .map(|r| r.trim().to_string())
            .unwrap_or_default();
        let mut mismatches = 0usize;
        let in_file_src = col_index.get("src_id").copied();

        for row in &s.file.rows {
            if let Some(i) = in_file_src
                && let Value::Int(v) = &row[i]
                && *v != s.src_id
            {
                mismatches += 1;
            }
            for (b, name) in builders.iter_mut().zip(&names) {
                let v = match name.as_str() {
                    "county" => Some(Value::Str(s.county.clone())),
                    "station_file_name" => Some(Value::Str(s.station_dir.clone())),
                    "src_id" => Some(Value::Int(s.src_id)),
                    n if n == RELEASE_COL && ds.per_row_release() => {
                        Some(Value::Str(release.clone()))
                    }
                    n => col_index.get(n).map(|&i| row[i].clone()),
                };
                b.append(v.as_ref().unwrap_or(&Value::Null));
            }
            report.rows_written += 1;
            pending += 1;
            if pending >= rows_per_flush {
                flush(&mut writer, &schema, &mut builders, &new_builders)?;
                pending = 0;
            }
        }
        if mismatches > 0 {
            report.src_id_mismatches.push((s.source_file.clone(), mismatches));
        }
        // flush per station file keeps peak memory to one file's rows
        if pending > 0 {
            flush(&mut writer, &schema, &mut builders, &new_builders)?;
            pending = 0;
        }
    }

    writer.close()?;
    Ok(report)
}

fn flush(
    writer: &mut ArrowWriter<std::fs::File>,
    schema: &Arc<Schema>,
    builders: &mut Vec<Box<dyn ColBuilder>>,
    new_builders: &impl Fn(&Schema) -> Vec<Box<dyn ColBuilder>>,
) -> Result<()> {
    let arrays: Vec<ArrayRef> = builders.iter_mut().map(|b| b.finish_col()).collect();
    let batch = RecordBatch::try_new(schema.clone(), arrays)?;
    writer.write(&batch)?;
    *builders = new_builders(schema);
    Ok(())
}

fn arrow_type(ty: ColumnType) -> DataType {
    match ty {
        ColumnType::Int => DataType::Int64,
        // Float32 by decision, not inheritance: MIDAS values carry at most
        // 6 significant figures (see docs/DATA.md, float precision).
        ColumnType::Float => DataType::Float32,
        ColumnType::Str => DataType::Utf8,
        // UTC-annotated: MIDAS observation times are GMT year-round.
        // Millisecond unit deliberately: Parquet has no seconds-unit
        // TIMESTAMP logical type, so second-unit arrow timestamps are
        // written as bare INT64 and the UTC annotation is invisible to
        // non-arrow readers (pyarrow, duckdb). Milliseconds carry
        // TIMESTAMP(isAdjustedToUTC=true) for every consumer.
        ColumnType::Time => DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
    }
}

/// Type-erased column builder so heterogeneous columns fit one Vec.
trait ColBuilder {
    fn append(&mut self, v: &Value);
    fn finish_col(&mut self) -> ArrayRef;
}

impl ColBuilder for Int64Builder {
    fn append(&mut self, v: &Value) {
        match v {
            Value::Int(i) => self.append_value(*i),
            _ => self.append_null(),
        }
    }
    fn finish_col(&mut self) -> ArrayRef {
        Arc::new(self.finish())
    }
}

impl ColBuilder for Float32Builder {
    fn append(&mut self, v: &Value) {
        match v {
            // Int values can land in widened float columns.
            Value::Float(f) => self.append_value(*f),
            Value::Int(i) => self.append_value(*i as f32),
            _ => self.append_null(),
        }
    }
    fn finish_col(&mut self) -> ArrayRef {
        Arc::new(self.finish())
    }
}

impl ColBuilder for StringBuilder {
    fn append(&mut self, v: &Value) {
        match v {
            Value::Str(s) => self.append_value(s),
            _ => self.append_null(),
        }
    }
    fn finish_col(&mut self) -> ArrayRef {
        Arc::new(self.finish())
    }
}

impl ColBuilder for TimestampMillisecondBuilder {
    fn append(&mut self, v: &Value) {
        match v {
            Value::Time(t) => self.append_value(t.and_utc().timestamp_millis()),
            _ => self.append_null(),
        }
    }
    fn finish_col(&mut self) -> ArrayRef {
        Arc::new(self.finish())
    }
}
