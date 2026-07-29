# EA Digital Land Utilisation Survey 1933–1949 — licence record

Dataset: **Digital Land Utilisation Survey 1933-1949**, Environment
Agency, dataset id `7a723d0f-d465-11e4-b475-f0def148f590`,
https://environment.data.gov.uk/dataset/7a723d0f-d465-11e4-b475-f0def148f590

Dataset description (from the portal, retrieved 2026-07-28): "These
data are a digital version of the 1 inch to 1 mile 'Dudley Stamp Maps'
that provide a pre-war land survey. These data have been scanned and
digitised and contain the following land use classifications: Rough
Grazing; Urban; Water; Arable; Suburban, Pasture; Woodland; Orchard."

Licence stated on the portal: **Environment Agency Conditional
Licence**, https://www.gov.uk/government/publications/environment-agency-conditional-licence/environment-agency-conditional-licence
(statutory guidance, updated 5 May 2016). Key terms, quoted verbatim
from that page (retrieved 2026-07-28):

> We grant you a worldwide, royalty-free, perpetual, non-exclusive
> licence to use the Information subject to the conditions below.

> 2. You are free, subject to the conditions identified below, to:
> copy, publish, distribute and transmit the Information; adapt the
> Information; exploit the Information commercially and
> non-commercially for example, by combining it with other Information,
> or by including it in your own product or application.

> 3. You must (where you do any of the above): […] ensure that you take
> appropriate note of the Abstract, including any information warnings,
> attribution statements and licence conditions; […] do not mislead
> others or misrepresent the Information or its source; acknowledge the
> source of the Information in your product or application by including
> or linking to any attribution statement specified by us and, where
> possible, provide a link to this licence; If we do not provide a
> specific attribution statement, you must use the following:
> "Contains Environment Agency information © Environment Agency and/or
> database right".

> 6. No warranty — The Information is licensed 'as is' […] We are not
> liable for any errors or omissions in the Information.

> 10. About the Environment Agency Conditional Licence — The
> Environment Agency licenses information under an Open Government
> Licence wherever possible. This Conditional Licence is used where an
> Open Government Licence is not possible.

**Attribution to carry in any output using this layer:**
"Contains Environment Agency information © Environment Agency and/or
database right".

Note for the project spec: the spec describes this licence as
"non-commercial"; the 2016 Conditional Licence text as published in
fact permits commercial exploitation subject to attribution and the
dataset Abstract's conditions. It remains correct that this is NOT the
Open Government Licence and must never be described as "open". Flagged
to the coordinator rather than resolved here.

## Acquisition route

The portal's bulk file links (api.agrimetrics.co.uk, .gdb.zip/.gpkg.zip)
are dead — the host no longer resolves in DNS (checked 2026-07-28). The
data were instead retrieved from the EA's own live services for this
dataset: the OGC API - Features endpoint
`https://environment.data.gov.uk/geoservices/datasets/7a723d0f-d465-11e4-b475-f0def148f590/ogc/features/v1`
(collection `Digital_Land_Utilisation_Survey_1930`, 1,494,322 features,
GeoJSON, CRS84), harvested per station-ring area of interest into
`features/` with a SHA-256 manifest.

## Class legend (gridcode)

From the dataset's own WMS style (GetLegendGraphic, format
application/json, retrieved 2026-07-28):

| gridcode | class |
|---|---|
| 1 | Rough Grazing |
| 2 | Urban |
| 3 | Water |
| 4 | Arable |
| 5 | Suburban |
| 6 | Grassland |
| 7 | Woodland |
| 8 | Orchard |

Feature properties carry only `id, gridcode, length_m, area_sqm` — no
survey sheet references or sheet dates. Per-station source metadata
therefore records the dataset id, endpoint, retrieval date and feature
count; sheet-level provenance is not available from this dataset.
