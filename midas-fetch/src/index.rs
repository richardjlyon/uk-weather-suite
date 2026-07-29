//! Build a station/file index by crawling the public JSON listings.
//! Layout: <root>/<dataset>/dataset-version-<v>/<county>/<id_station>/
//!           <station>_capability.csv + qc-version-{0,1}/<yearly CSVs>

use crate::{ARCHIVE_ROOT, ceda};
use anyhow::Result;
use futures::{StreamExt, stream};
use indicatif::{ProgressBar, ProgressStyle};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// One yearly data file (or capability file) in the archive.
#[derive(Debug, Serialize, Deserialize)]
pub struct FileEntry {
    pub county: String,
    pub station: String, // e.g. "00676_filton"
    pub qc: Option<u8>,  // None = capability/metadata file
    pub name: String,
    pub path: String, // archive path, absolute under data.ceda.ac.uk
    pub size: Option<u64>,
    pub md5: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Index {
    pub dataset: String,
    pub version: String,
    pub files: Vec<FileEntry>,
}

pub async fn build(dataset: &str, version: &str, out_dir: &str) -> Result<()> {
    let client = reqwest::Client::builder().gzip(true).build()?;
    let root = format!("{ARCHIVE_ROOT}/{dataset}/dataset-version-{version}");

    let counties: Vec<String> = ceda::list(&client, &root)
        .await?
        .items
        .into_iter()
        .filter(ceda::Item::is_dir)
        .map(|i| i.name)
        .collect();
    println!("{} counties", counties.len());

    let bar = ProgressBar::new(counties.len() as u64).with_style(
        ProgressStyle::with_template("{bar:40} {pos}/{len} counties {msg}")?,
    );

    // One task per county; each walks its stations sequentially.
    let mut files: Vec<FileEntry> = stream::iter(counties)
        .map(|county| {
            let client = client.clone();
            let root = root.clone();
            let bar = bar.clone();
            async move {
                let res = crawl_county(&client, &root, &county).await;
                bar.inc(1);
                bar.set_message(county.clone());
                res
            }
        })
        .buffer_unordered(16)
        .collect::<Vec<_>>()
        .await
        .into_iter()
        .collect::<Result<Vec<_>>>()?
        .into_iter()
        .flatten()
        .collect();
    bar.finish();

    files.sort_by(|a, b| a.path.cmp(&b.path));
    let index = Index { dataset: dataset.into(), version: version.into(), files };

    std::fs::create_dir_all(out_dir)?;
    let out = Path::new(out_dir).join(format!("{dataset}-{version}.json"));
    std::fs::write(&out, serde_json::to_vec_pretty(&index)?)?;
    println!("{} files indexed -> {}", index.files.len(), out.display());
    Ok(())
}

async fn crawl_county(
    client: &reqwest::Client,
    root: &str,
    county: &str,
) -> Result<Vec<FileEntry>> {
    let mut out = Vec::new();
    let stations = ceda::list(client, &format!("{root}/{county}")).await?;
    for st in stations.items.iter().filter(|i| i.is_dir()) {
        let surl = format!("{root}/{county}/{}", st.name);
        for item in ceda::list(client, &surl).await?.items {
            if item.is_dir() {
                // qc-version-0 / qc-version-1
                let qc: u8 = item.name.trim_start_matches("qc-version-").parse().unwrap_or(0);
                for f in ceda::list(client, &format!("{surl}/{}", item.name)).await?.items {
                    if !f.is_dir() {
                        out.push(entry(county, &st.name, Some(qc), f));
                    }
                }
            } else {
                out.push(entry(county, &st.name, None, item));
            }
        }
    }
    Ok(out)
}

fn entry(county: &str, station: &str, qc: Option<u8>, f: ceda::Item) -> FileEntry {
    FileEntry {
        county: county.into(),
        station: station.into(),
        qc,
        name: f.name,
        path: f.path,
        size: f.size,
        md5: f.md5,
    }
}
