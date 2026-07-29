# UK Weather Suite

An observational study of whether land-use change around UK weather
stations has affected the temperature record they produce, and what the
Met Office's homogenisation and quality-control processing does to any
such effect.

Every station receives a **time-varying** urban/rural classification
derived from several independent published data sources. That
classification is frozen and externally deposited **before** any
temperature data are analysed.

## Study design and bias controls

This study is pre-registered in the ordinary scientific sense: the
classification rules, the estimator and the decision criteria are fixed
in writing before the temperature data are touched, and the analysis
runs to completion and is reported whichever way it comes out.

Two hypotheses are under test, **both two-sided**:

1. Whether station surroundings have urbanised enough to affect
   measured temperature.
2. Whether Met Office homogenisation and quality-control processing
   imparts any systematic directional effect on the record.

The author's motivating question is hypothesis 2, with a declared prior
expectation of a warming direction. The design exists so that
expectation cannot steer the result:

- Every specification change goes through adversarial review until the
  reviewer has no substantive objection left, then is implemented
  test-first. The review history is part of the record (`openspec/`).
- Reference sites are admitted by an external citable rule over
  published datasets — author judgement cannot admit or remove sites.
- Coverage limits abstain explicitly with reason codes; a screen that
  cannot run is recorded as unperformed, never as passed.
- The estimator was validated on synthetic zero-signal worlds and the
  validation caught (and fixed) a real bias in an earlier construction.
- Results are published as measured. The preliminary quality-control
  audit measured a small effect **opposite** to the declared prior — a
  slight net cooling (−0.019 °C) — and that is recorded in
  `docs/qc-audit-preliminary-2026-07-29.md`.

Status: classification layers built; reference-site admission rule
frozen to publishable grade; the frozen classification table and
external deposit (Zenodo/OSF) are pending. **No temperature analysis
has been run against real classifications yet.**

## Components

| Component | Language | Purpose |
|---|---|---|
| `midas-fetch/` | Rust | Crawl, download and parse the Met Office MIDAS Open archive (CEDA) into Parquet |
| `ukweather/` | Python (uv) | Station classification layers + analysis suite |
| `openspec/` | — | Specifications, amendments and review history for every change |
| `docs/` | — | Findings, decisions and data licences |

## Data sources

All inputs are published datasets; licences are recorded in
`docs/licences/`.

- **Weather**: [MIDAS Open](https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/)
  — Met Office UK land surface stations, 1853–present, Open Government
  Licence. Hourly and daily observations plus per-station metadata.
- **Built-up surface**: [GHS-BUILT-S](https://data.jrc.ec.europa.eu/dataset/9f06f36f-4b11-47ec-abb0-4f8b7b1d72ea)
  (JRC) — 100 m cells, 5-yearly epochs; built-up fraction within rings
  of 500 m, 2 km and 10 km of each station, with per-epoch sensor
  provenance.
- **Spectral indices**: NDVI/NDBI from raw Landsat via Microsoft
  Planetary Computer.
- **Historical land use**: 1930s Land Utilisation Survey (England &
  Wales); OS Popular Edition (Scotland, specified).
- **Census density**: 1981–2021.
- **Airfields**: OpenStreetMap aeroway (one-way screen).
- **Reference sites**: SSSI/NNR layers from Natural England, Natural
  Resources Wales and NatureScot (all OGL), admitted by the rule in
  `openspec/changes/add-station-classifier/specs/builtup-extraction/spec.md`.

The `data/` tree (≈66 GB) is not in the repository; every dataset above
is fetchable from its published source, and checksum manifests are in
`manifests/`.

## CEDA access

Directory listings are public. File downloads need a CEDA account.
`midas-fetch` mints short-lived access tokens from the
[token API](https://help.ceda.ac.uk/article/5100-archive-access-tokens)
using credentials in the macOS Keychain — never stored in this repo.

## Layout

```
midas-fetch/     Rust downloader/parser
ukweather/       Python package (uv): layers, classifier, analysis
openspec/        Specifications and amendment history
docs/            Findings, decisions, licences
manifests/       Data checksums
data/            Local data (gitignored, fetchable from sources above)
```
