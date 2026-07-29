//! BADC-CSV reader for MIDAS Open observation files.
//!
//! Format: a header block of `key,column,value[,...]` lines (`G` in the
//! column slot means a global attribute), then a `data` line, a column-name
//! row, observation rows, and an `end data` terminator. Column types are
//! declared in the header (`type,<column>,<int|float|char|...>`); the time
//! coordinate is marked with `coordinate_variable,<column>,t` and promoted
//! to a parsed datetime regardless of its declared storage type.
//!
//! Coercion policy (spec: badc-parse, harden-parquet-provenance): values
//! that fail typed parsing coerce to null and are counted per column, so a
//! systematically corrupt column is localisable; empty fields are counted
//! separately from the documented `NA` sentinel; non-finite floats are
//! rejected; out-of-range integers are rejected, never saturated; columns
//! present in the data section but undeclared in the header fall back to
//! string and the fallback is counted.

use anyhow::{Result, bail};
use chrono::NaiveDateTime;
use std::collections::{BTreeMap, HashMap};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ColumnType {
    Int,
    Float,
    Str,
    Time,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Int(i64),
    Float(f32),
    Str(String),
    Time(NaiveDateTime),
    Null,
}

/// Per-column tallies of null-producing events, kept distinct because they
/// mean different things: `na` is the archive's declared missing-value
/// marker, `empty` is a structural anomaly, `coerced` is a value that failed
/// typed parsing.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct ColCounts {
    pub coerced: usize,
    pub empty: usize,
    pub na: usize,
}

/// Header-only view of a file: everything before the data rows.
#[derive(Debug)]
pub struct Header {
    pub attributes: HashMap<String, String>,
    pub columns: Vec<String>,
    /// Declared type per column (after time-coordinate promotion).
    pub types: HashMap<String, ColumnType>,
    /// Columns present in the data section with no `type` declaration.
    pub undeclared_columns: Vec<String>,
    /// Units per column, from the trailing field of `long_name` lines
    /// (MIDAS writes `long_name,<col>,<description>,<unit>`; dimensionless
    /// columns carry "1").
    pub units: BTreeMap<String, String>,
}

#[derive(Debug)]
pub struct BadcFile {
    /// Global attributes (rows with `G` in the column slot).
    pub attributes: HashMap<String, String>,
    /// Column names in file order, from the row after `data`.
    pub columns: Vec<String>,
    /// Declared type per column (after time-coordinate promotion).
    pub types: HashMap<String, ColumnType>,
    /// Units per column from the header.
    pub units: BTreeMap<String, String>,
    /// Observation rows, each aligned with `columns`.
    pub rows: Vec<Vec<Value>>,
    /// Total values that failed typed parsing (sum of per-column counts).
    pub coerced_nulls: usize,
    /// Per-column coercion/empty/NA tallies (only columns with events).
    pub col_counts: BTreeMap<String, ColCounts>,
    /// Value count per column that took the undeclared-string fallback.
    pub undeclared: BTreeMap<String, usize>,
}

impl BadcFile {
    pub fn column_type(&self, column: &str) -> Option<ColumnType> {
        self.types.get(column).copied()
    }

    /// (column, type) pairs in file column order; undeclared columns are Str.
    pub fn types_in_order(&self) -> impl Iterator<Item = (String, ColumnType)> + '_ {
        self.columns
            .iter()
            .map(|c| (c.clone(), self.column_type(c).unwrap_or(ColumnType::Str)))
    }
}

const TIME_FORMAT: &str = "%Y-%m-%d %H:%M:%S";

/// Parse the header block and column row only — no data rows. Cheap enough
/// to run over the whole archive as the schema pass.
pub fn parse_header(content: &str) -> Result<Header> {
    let mut lines = content.lines().enumerate();
    parse_header_from(&mut lines)
}

fn parse_header_from<'a>(
    lines: &mut impl Iterator<Item = (usize, &'a str)>,
) -> Result<Header> {
    let mut attributes = HashMap::new();
    let mut types: HashMap<String, ColumnType> = HashMap::new();
    let mut units: BTreeMap<String, String> = BTreeMap::new();
    let mut time_columns: Vec<String> = Vec::new();

    let mut found_data = false;
    for (n, line) in lines.by_ref() {
        let line = line.trim_end();
        if line == "data" {
            found_data = true;
            break;
        }
        if line.is_empty() {
            continue;
        }
        let mut parts = line.splitn(3, ',');
        let (key, col, value) = match (parts.next(), parts.next(), parts.next()) {
            (Some(k), Some(c), Some(v)) => (k.trim(), c.trim(), v),
            _ => bail!("line {}: malformed header line: {line:?}", n + 1),
        };
        match (key, col) {
            (_, "G") => {
                attributes.insert(key.to_string(), value.to_string());
            }
            ("type", _) => {
                let t = match value.split(',').next().unwrap_or("").trim() {
                    "int" => ColumnType::Int,
                    "float" => ColumnType::Float,
                    _ => ColumnType::Str, // char and anything else stored as text
                };
                types.insert(col.to_string(), t);
            }
            ("long_name", _) => {
                // unit is the trailing CSV field: long_name,<col>,<desc>,<unit>
                if let Some(unit) = value.rsplit(',').next() {
                    let unit = unit.trim();
                    if !unit.is_empty() {
                        units.insert(col.to_string(), unit.to_string());
                    }
                }
            }
            ("coordinate_variable", _) if value.trim().starts_with('t') => {
                time_columns.push(col.to_string());
            }
            _ => {} // comments etc. — not needed
        }
    }
    if !found_data {
        bail!("no 'data' marker found");
    }
    for c in &time_columns {
        types.insert(c.clone(), ColumnType::Time);
    }
    // Quality (_q) and flag (_j) columns are codes, not quantities — MIDAS
    // declares them int, but we preserve them verbatim as strings so codes
    // like "09" and "9" stay distinct and uninterpreted.
    for (col, ty) in types.iter_mut() {
        if col.ends_with("_q") || col.ends_with("_j") {
            *ty = ColumnType::Str;
        }
    }

    let Some((_, column_row)) = lines.next() else {
        bail!("file ends after 'data' marker");
    };
    let columns: Vec<String> =
        column_row.trim_end().split(',').map(str::to_string).collect();
    let undeclared_columns: Vec<String> =
        columns.iter().filter(|c| !types.contains_key(*c)).cloned().collect();

    Ok(Header { attributes, columns, types, undeclared_columns, units })
}

pub fn parse_file(content: &str) -> Result<BadcFile> {
    let mut lines = content.lines().enumerate();
    let header = parse_header_from(&mut lines)?;
    let Header { attributes, columns, types, undeclared_columns, units } = header;

    let mut rows = Vec::new();
    let mut col_counts: BTreeMap<String, ColCounts> = BTreeMap::new();
    let mut undeclared: BTreeMap<String, usize> = BTreeMap::new();
    let mut terminated = false;
    for (n, line) in lines {
        let line = line.trim_end();
        if line == "end data" {
            terminated = true;
            break;
        }
        if line.is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split(',').collect();
        if fields.len() != columns.len() {
            bail!(
                "line {}: {} fields but {} columns declared",
                n + 1,
                fields.len(),
                columns.len()
            );
        }
        let mut row = Vec::with_capacity(columns.len());
        for (col, raw) in columns.iter().zip(&fields) {
            let raw = raw.trim();
            if raw == "NA" {
                col_counts.entry(col.clone()).or_default().na += 1;
                row.push(Value::Null);
                continue;
            }
            if raw.is_empty() {
                col_counts.entry(col.clone()).or_default().empty += 1;
                row.push(Value::Null);
                continue;
            }
            let declared = types.get(col).copied();
            if declared.is_none() {
                *undeclared.entry(col.clone()).or_default() += 1;
            }
            let ty = declared.unwrap_or(ColumnType::Str);
            // Any value that fails typed parsing coerces to null and is
            // counted per column — a bad value never sinks its station-year.
            let mut coerce = || {
                col_counts.entry(col.clone()).or_default().coerced += 1;
                Value::Null
            };
            let v = match ty {
                // MIDAS writes float-formatted values into declared-int
                // columns (e.g. wind_direction "300.0") — accept when
                // integral and in range. WMO markers ("/", "&") and
                // out-of-range magnitudes become counted nulls.
                ColumnType::Int => {
                    parse_int_lenient(raw).map(Value::Int).unwrap_or_else(&mut coerce)
                }
                ColumnType::Float => match raw.parse::<f32>() {
                    Ok(f) if f.is_finite() => Value::Float(f),
                    _ => coerce(), // garbage or non-finite: never admitted
                },
                ColumnType::Time => NaiveDateTime::parse_from_str(raw, TIME_FORMAT)
                    .map(Value::Time)
                    .unwrap_or_else(|_| coerce()),
                ColumnType::Str => Value::Str(raw.to_string()),
            };
            row.push(v);
        }
        rows.push(row);
    }
    if !terminated {
        bail!("no 'end data' marker: file truncated or corrupt");
    }

    let coerced_nulls = col_counts.values().map(|c| c.coerced).sum();
    let _ = undeclared_columns; // undeclared value counts carry the information
    Ok(BadcFile {
        attributes,
        columns,
        types,
        units,
        rows,
        coerced_nulls,
        col_counts,
        undeclared,
    })
}

/// Lenient integer parsing for MIDAS declared-int columns: accepts plain
/// integers and float-formatted integers ("300.0"); rejects fractions,
/// non-numeric tokens, non-finite values, and magnitudes outside i64 —
/// rejection means a counted null, never a saturated i64::MAX.
pub fn parse_int_lenient(raw: &str) -> Option<i64> {
    if let Ok(i) = raw.parse::<i64>() {
        return Some(i);
    }
    match raw.parse::<f64>() {
        Ok(f)
            if f.is_finite()
                && f.fract() == 0.0
                && f >= -(2f64.powi(63))
                && f < 2f64.powi(63) =>
        {
            Some(f as i64)
        }
        _ => None,
    }
}
