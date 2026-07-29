# UK Weather Suite — plan

*2026-07-28. Approved by Richard.*

## Aim

A suite to test whether urbanisation around UK weather stations shows up in
the temperature record (urban heat effect), by giving every station a
time-varying urban/rural classification and comparing cohort trends.
Sibling of the US-side idea captured in the vault
(`Ideas/Does homogenisation make rural stations follow the towns.md`).

## Decisions

- **Source: MIDAS Open, not ECA&D.** ECA&D carries only ~131 UK temperature
  stations; MIDAS Open is the Met Office's own archive (1853–present, OGL,
  release v202507). The old `rjl-climate/ECAD-processor` is superseded, kept
  for reference only.
- **Rust where parallelism pays** (Richard, 2026-07-28): the MIDAS
  crawler/downloader/parser (tens of thousands of small BADC-CSV files) is
  Rust → Parquet. Land-cover extraction and analysis are Python (uv).
- **Classification is time-varying**: built-up fraction in rings
  (500 m / 2 km / 10 km) around each station per GHSL epoch, with
  self-computed spectral and census validation layers and a 1930s Land
  Utilisation Survey baseline screen (UKCEH LCM an optional cross-check).
  No single static urban/rural tag. Full method: the
  `add-station-classifier` OpenSpec change (twice red-teamed, 2026-07-28).
- **Headline claim narrowed to post-1975** (Richard, 2026-07-28): the
  satellite evidence floor is 1975, so the analysis claims post-1975
  contamination only. The 1930s survey screen protects the control
  cohort but cannot date earlier change. **Deferred phase two**: a
  pre-1975 quantitative layer from digitised historic OS maps (NLS
  georeferenced sheets), proposed as its own red-teamed change after
  the classifier runs end to end — this is the route to the interwar/
  post-war engulfing story, not an optional extra.

## Findings from the CEDA spike (2026-07-28)

- Archive layout: `data/<dataset>/dataset-version-202507/<county>/<id_station>/qc-version-{0,1}/<one CSV per year>`
  plus a per-station `capability.csv`. 108 counties in daily-temperature.
- Directory listings are **public**, and `?json` returns a clean JSON listing
  (path, name, type, size, md5) — the crawler needs no HTML scraping.
- File downloads **require auth**: `data.ceda.ac.uk` 302s to `dap.ceda.ac.uk`,
  which serves a login page anonymously. Auth is `Authorization: Bearer <token>`.
- Tokens: 3-day life from the web UI (max 2 active); the token API
  (`POST https://services.ceda.ac.uk/api/token/create/`, HTTP basic auth)
  mints tokens programmatically — the downloader self-refreshes.

## Phases

0. **Spike** — ✅ 2026-07-28. CEDA access via Richard's token (Keychain
   `ceda-token`); Avon county verified end to end.
1. **midas-fetch** — ✅ hourly weather obs complete 2026-07-28: 34,238 qc-1
   files (33.5 GB) fetched and parsed to 96.17M rows / 1,537 stations /
   1.34 GB Parquet (OpenSpec change `2026-07-28-add-badc-parser`; 15 WMO
   cloud-code values coerced to null, counted). Remaining: daily
   temperature + rainfall datasets; capability files → station table;
   verify how station moves are represented (new station id vs amended
   location).
2. **Land cover** — GHSL GHS-BUILT-S epochs + UKCEH LCM → per-station
   time-varying classification Parquet. Check LCM licence.
3. **Analysis** — cohort construction (long-record still-rural vs urbanised),
   trend comparison, UHI estimates.

## Open questions

- Station moves: does MIDAS re-site under the same station id? (Weston-super-Mare
  appears as three separate ids — suggests moves get new ids. Verify from
  capability files.)
- UKCEH LCM licence terms for this use.
- Hourly vs daily rainfall: start daily; hourly only if an analysis needs it.
