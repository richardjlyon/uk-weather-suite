//! CEDA archive listing client. Listings are public: `<url>/?json` returns
//! `{ "path": ..., "items": [{name, type, size, md5, ...}] }`.

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Listing {
    pub items: Vec<Item>,
}

#[derive(Debug, Deserialize)]
pub struct Item {
    pub name: String,
    #[serde(rename = "type")]
    pub kind: String, // "file" | "dir"
    pub path: String,
    #[serde(default)]
    pub size: Option<u64>,
    #[serde(default)]
    pub md5: Option<String>,
}

impl Item {
    pub fn is_dir(&self) -> bool {
        self.kind == "dir"
    }
}

pub async fn list(client: &reqwest::Client, url: &str) -> Result<Listing> {
    // CEDA sheds connections under concurrent load; retry with backoff.
    let mut delay = std::time::Duration::from_millis(500);
    let mut last_err = None;
    for _ in 0..5 {
        match try_list(client, url).await {
            Ok(l) => return Ok(l),
            Err(e) => {
                last_err = Some(e);
                tokio::time::sleep(delay).await;
                delay *= 2;
            }
        }
    }
    Err(last_err.unwrap())
}

async fn try_list(client: &reqwest::Client, url: &str) -> Result<Listing> {
    let resp = client
        .get(format!("{url}/?json"))
        .send()
        .await
        .with_context(|| format!("listing {url}"))?
        .error_for_status()
        .with_context(|| format!("listing {url}"))?;
    let listing = resp
        .json::<Listing>()
        .await
        .with_context(|| format!("parsing listing {url}"))?;
    Ok(listing)
}
