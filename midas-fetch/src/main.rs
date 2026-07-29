//! midas-fetch: download the Met Office MIDAS Open archive from CEDA.
//!
//! CEDA directory listings are public JSON (`<url>/?json`); file downloads
//! need a bearer token. Tokens last ~3 days; we mint them on demand from
//! the CEDA token API using credentials held in the macOS Keychain
//! (service `ceda-credentials`).

mod ceda;
mod fetch;
mod index;
mod token;

use midas_fetch::parse_cmd;

use anyhow::Result;
use clap::{Parser, Subcommand};

const ARCHIVE_ROOT: &str = "https://data.ceda.ac.uk/badc/ukmo-midas-open/data";
const DEFAULT_VERSION: &str = "202507";

#[derive(Parser)]
#[command(name = "midas-fetch", about, version)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Mint a CEDA access token from Keychain credentials and print its expiry
    Token,
    /// Crawl the archive listings and build a station index (no auth needed)
    Index {
        /// Dataset, e.g. uk-daily-temperature-obs, uk-daily-rain-obs
        #[arg(long, default_value = "uk-daily-temperature-obs")]
        dataset: String,
        /// Dataset version
        #[arg(long, default_value = DEFAULT_VERSION)]
        version: String,
        /// Output directory for the index
        #[arg(long, default_value = "data/index")]
        out_dir: String,
    },
    /// Download station files listed in an index
    Fetch {
        /// Index file produced by `index`
        #[arg(long)]
        index: String,
        /// Restrict to one county (e.g. avon) for spikes
        #[arg(long)]
        county: Option<String>,
        /// qc version to download (1 = quality-controlled)
        #[arg(long, default_value = "1")]
        qc: u8,
        /// Output directory for raw CSVs
        #[arg(long, default_value = "data/raw")]
        out_dir: String,
        /// Concurrent downloads
        #[arg(long, default_value = "16")]
        concurrency: usize,
    },
    /// Parse downloaded BADC-CSV files into per-county Parquet under
    /// <out_dir>/obs/<dataset>/
    Parse {
        /// Directory of raw downloads
        #[arg(long, default_value = "data/raw")]
        raw_dir: String,
        /// Root output directory (obs/<dataset>/ is appended)
        #[arg(long, default_value = "data/parquet")]
        out_dir: String,
        /// Dataset name, e.g. uk-hourly-weather-obs — names the output
        /// directory so the layout is constructed, not operator-typed
        #[arg(long, default_value = "uk-hourly-weather-obs")]
        dataset: String,
        /// Restrict to one county
        #[arg(long)]
        county: Option<String>,
        /// qc version to parse
        #[arg(long, default_value = "1")]
        qc: u8,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Token => {
            let tok = token::mint().await?;
            println!("token OK, expires {}", tok.expires);
        }
        Command::Index { dataset, version, out_dir } => {
            index::build(&dataset, &version, &out_dir).await?;
        }
        Command::Fetch { index, county, qc, out_dir, concurrency } => {
            fetch::run(&index, county.as_deref(), qc, &out_dir, concurrency).await?;
        }
        Command::Parse { raw_dir, out_dir, dataset, county, qc } => {
            parse_cmd::run(&raw_dir, &out_dir, county.as_deref(), qc, &dataset)?;
        }
    }
    Ok(())
}
