# Census layer (1981+) — licence and provenance record

*Amendment context: pre-1981 census depth is out of scope (design.md
amendment 2026-07-29 — the GBHD parish series is withdrawn from UK Data
Service download; Vision of Britain no longer serves downloads; historic
parish geometry is special-request only). This layer uses only open,
no-account sources.*

## Counts — NOMIS (retrieved 2026-07-29)

Datasets (identifiers recorded per output row):

| census | table | geography |
|---|---|---|
| 1981 | NM_66_1 (1981 SAS), cell 1 "All Present residents : Total persons" | TYPE33 1981 frozen wards (EW) |
| 1991 | NM_38_1 (1991 SAS), cell 268501249 "S01:1 Present residents : Total persons" | TYPE1 1991 frozen wards (EW) |
| 2001 | NM_1634_1 (KS001), cell 0 "All people" | TYPE304 LSOA 2001 (EW) |
| 2011 | NM_144_1 (KS101EW), cell 0 "All usual residents" | TYPE298 LSOA 2011 (EW) |
| 2021 | NM_2021_1 (TS001), c2021_restype_3=0 "Total: All usual residents" | TYPE151 LSOA 2021 (EW) |

Definitional note: 1981/1991 SAS count PRESENT residents; 2001+ count
USUAL residents. The 1991→2001 growth step mixes definitions slightly;
documented, absorbed by calibrated tolerances.

Licence, quoted verbatim from https://www.nomisweb.co.uk/home/copyright.asp
(retrieved 2026-07-29):

> "All material on the Office for National Statistics (ONS) and Nomis
> websites is subject to Crown Copyright protection unless otherwise
> indicated. … Under the terms of the Open Government Licence (OGL) and
> UK Government Licensing Framework … anyone wishing to use or re-use
> ONS material, whether commercially or privately, may do so freely
> without a specific application for a licence, subject to the
> conditions of the OGL and the Framework. … Users should include a
> source accreditation to ONS: Source: Office for National Statistics"

## Boundaries — ONS Open Geography Portal (retrieved 2026-07-29)

ArcGIS feature services (generalised/clipped where available; exact
service URL recorded per output row): Wards_1981_Boundaries_EW,
WD_1991_EW, Lower_Layer_Super_Output_Areas_Dec_2001_EW_BGC_2022,
LSOA_Dec_2011_Boundaries_Generalised_Clipped_BGC_EW_V3,
Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5.

Licence: **Open Government Licence v3.0**. Required attribution:

> Source: Office for National Statistics licensed under the Open
> Government Licence v.3.0. Contains OS data © Crown copyright and
> database right 2026.

## Coverage

England and Wales only in this pass. Scottish and Northern Irish
census data ARE openly available (Scotland's Census / NRS bulk
downloads and boundary products; NISRA PxStat API and Small Area
geographies) but are separate integrations; Scottish and NI stations
carry reason codes `no-census-boundaries-scotland` /
`no-census-boundaries-northern-ireland` — never silent nulls.

## Semantics (binding, from the spec)

- 10 km ring only; the code REFUSES finer rings (polygons would smear).
- One-way: growth can vote urbanised; absence of growth never disputes
  another layer's urbanised finding (carried per row).
- Pre-1981 comparison windows abstain, reason `no-open-census-pre-1981`;
  nothing is interpolated backwards.

Cache: `counts-<year>.csv` and `boundaries-<year>.geojson` in this
directory, SHA-256 manifest `census.sha256`.
