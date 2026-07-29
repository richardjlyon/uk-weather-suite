//! CEDA access tokens. Minted on demand from the token API
//! (<https://help.ceda.ac.uk/article/5100-archive-access-tokens>) with
//! HTTP basic auth. Credentials come from the macOS Keychain, service
//! `ceda-credentials` (account = CEDA username, password = CEDA password):
//!
//! ```sh
//! security add-generic-password -s ceda-credentials -a <username> -w
//! ```

use anyhow::{Context, Result, bail};
use serde::Deserialize;
use std::process::Command;

const TOKEN_API: &str = "https://services.ceda.ac.uk/api/token/create/";
const KEYCHAIN_SERVICE: &str = "ceda-credentials";

pub struct Token {
    pub access_token: String,
    pub expires: String,
}

#[derive(Deserialize)]
struct TokenResponse {
    access_token: AccessToken,
}

#[derive(Deserialize)]
struct AccessToken {
    token: String,
    #[serde(default)]
    expires: Option<String>,
}

fn keychain(args: &[&str]) -> Result<String> {
    let out = Command::new("security")
        .args(args)
        .output()
        .context("running security(1)")?;
    if !out.status.success() {
        bail!(
            "no CEDA credentials in Keychain (service '{KEYCHAIN_SERVICE}'). Add them with:\n  \
             security add-generic-password -s {KEYCHAIN_SERVICE} -a <ceda-username> -w"
        );
    }
    Ok(String::from_utf8(out.stdout)?.trim().to_string())
}

fn credentials() -> Result<(String, String)> {
    // Account name is embedded in the item; -w prints only the password.
    let dump = keychain(&["find-generic-password", "-s", KEYCHAIN_SERVICE])?;
    let user = dump
        .lines()
        .find_map(|l| {
            let l = l.trim();
            l.strip_prefix("\"acct\"<blob>=\"")
                .and_then(|r| r.strip_suffix('"'))
                .map(str::to_string)
        })
        .context("could not read account name from Keychain item")?;
    let pass = keychain(&["find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"])?;
    Ok((user, pass))
}

/// Get a token: a stored one from Keychain item `ceda-token` if present,
/// otherwise mint a fresh one (valid ~3 days) from `ceda-credentials`.
pub async fn mint() -> Result<Token> {
    if let Ok(stored) = keychain(&["find-generic-password", "-s", "ceda-token", "-w"]) {
        return Ok(Token { access_token: stored, expires: "stored token (unknown)".into() });
    }
    mint_fresh().await
}

async fn mint_fresh() -> Result<Token> {
    let (user, pass) = credentials()?;
    let client = reqwest::Client::new();
    let resp = client
        .post(TOKEN_API)
        .basic_auth(&user, Some(&pass))
        .send()
        .await
        .context("calling CEDA token API")?;
    if !resp.status().is_success() {
        bail!("CEDA token API refused ({}): check Keychain credentials", resp.status());
    }
    let tr = resp.json::<TokenResponse>().await.context("parsing token response")?;
    Ok(Token {
        access_token: tr.access_token.token,
        expires: tr.access_token.expires.unwrap_or_else(|| "unknown".into()),
    })
}
