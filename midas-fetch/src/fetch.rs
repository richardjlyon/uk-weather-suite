//! Download files from an index, concurrently, with a bearer token.
//! Files land under <out_dir>/<county>/<station>/[qc-version-N/]<name>,
//! mirroring the archive. Existing files with matching size are skipped,
//! so re-runs resume.

use crate::index::Index;
use crate::token;
use anyhow::{Context, Result};
use futures::{StreamExt, stream};
use indicatif::{ProgressBar, ProgressStyle};
use std::path::{Path, PathBuf};

pub async fn run(
    index_path: &str,
    county: Option<&str>,
    qc: u8,
    out_dir: &str,
    concurrency: usize,
) -> Result<()> {
    let index: Index = serde_json::from_slice(
        &std::fs::read(index_path).with_context(|| format!("reading {index_path}"))?,
    )?;

    // Capability/metadata files always come along; data files filtered by qc.
    let files: Vec<_> = index
        .files
        .iter()
        .filter(|f| county.is_none_or(|c| f.county == c))
        .filter(|f| f.qc.is_none_or(|q| q == qc))
        .collect();
    println!("{} files to fetch", files.len());

    let tok = token::mint().await?;
    let client = reqwest::Client::builder().gzip(true).build()?;

    let bar = ProgressBar::new(files.len() as u64).with_style(
        ProgressStyle::with_template("{bar:40} {pos}/{len} {msg}")?,
    );

    let results: Vec<Result<bool>> = stream::iter(files)
        .map(|f| {
            let client = client.clone();
            let token = tok.access_token.clone();
            let bar = bar.clone();
            let dest = local_path(out_dir, &f.county, &f.station, f.qc, &f.name);
            // dap serves the bytes; going via data.ceda.ac.uk loses the
            // Authorization header on the cross-host redirect.
            let url = format!("https://dap.ceda.ac.uk{}", f.path);
            let size = f.size;
            async move {
                let fetched = fetch_one(&client, &token, &url, &dest, size).await;
                bar.inc(1);
                fetched
            }
        })
        .buffer_unordered(concurrency)
        .collect()
        .await;
    bar.finish();

    let mut fetched = 0usize;
    let mut skipped = 0usize;
    let mut failed = 0usize;
    for r in &results {
        match r {
            Ok(true) => fetched += 1,
            Ok(false) => skipped += 1,
            Err(e) => {
                failed += 1;
                eprintln!("FAIL {e:#}");
            }
        }
    }
    println!("fetched {fetched}, skipped {skipped} (already present), failed {failed}");
    Ok(())
}

fn local_path(out_dir: &str, county: &str, station: &str, qc: Option<u8>, name: &str) -> PathBuf {
    let mut p = Path::new(out_dir).join(county).join(station);
    if let Some(q) = qc {
        p = p.join(format!("qc-version-{q}"));
    }
    p.join(name)
}

/// Returns Ok(true) if downloaded, Ok(false) if skipped as already present.
async fn fetch_one(
    client: &reqwest::Client,
    token: &str,
    url: &str,
    dest: &Path,
    expected_size: Option<u64>,
) -> Result<bool> {
    if let (Ok(meta), Some(want)) = (std::fs::metadata(dest), expected_size)
        && meta.len() == want
    {
        return Ok(false);
    }
    let resp = client
        .get(url)
        .bearer_auth(token)
        .send()
        .await
        .with_context(|| format!("GET {url}"))?
        .error_for_status()
        .with_context(|| format!("GET {url}"))?;
    let bytes = resp.bytes().await.with_context(|| format!("body {url}"))?;
    if let Some(dir) = dest.parent() {
        tokio::fs::create_dir_all(dir).await?;
    }
    tokio::fs::write(dest, &bytes).await.with_context(|| format!("writing {}", dest.display()))?;
    Ok(true)
}
