# Reference sites — source and licence record

Retrieved 2026-07-29 for the classifier's tolerance calibration
(`add-station-classifier`, "Rule-defined reference sites").

## Sites of Special Scientific Interest (England)

- **Source**: Natural England, via the DEFRA spatial data WFS
  `https://environment.data.gov.uk/spatialdata/sites-of-special-scientific-interest-england/wfs`
  feature type
  `dataset-ba8dc201-66ef-4983-9d46-7378af21027e:Sites_of_Special_Scientific_Interest_England`
- **Retrieved**: 2026-07-29, 4,128 features, EPSG:27700, 207.8 MB GeoJSON
- **Licence**: Open Government Licence. Natural England publishes its
  datasets under the OGL, which permits commercial and non-commercial
  use with attribution — so unlike the 1930s land-use and census
  sources, derived reference-site definitions **may** be redistributed
  in the pre-registration deposit.
- **Required attribution**: "Contains Natural England data © Natural
  England and database right [year]. Contains Ordnance Survey data ©
  Crown copyright and database right."

## National Nature Reserves (England)

- **Source**: Natural England via the same DEFRA WFS, feature type
  `dataset-ff213e4c-423a-4d7e-9e6f-b220600a8db3:National_Nature_Reserves_England`
- **Retrieved**: 2026-07-29, 224 features, 31.7 MB
- **Licence**: Open Government Licence, as above.

## Scotland — SSSI and NNR (NatureScot)

- **Source**: NatureScot protected-areas WFS
  `https://ogc.nature.scot/geoserver/protectedareas/wfs`, layers
  `protectedareas:sssi` and `protectedareas:nnr`
- **Retrieved**: 2026-07-29 — SSSI 15,877 features (115.2 MB), NNR 747
  features (4.3 MB)
- **Licence**: Open Government Licence v3.0 ("contains SNH information
  licensed under the Open Government Licence v3.0"), so derived
  reference-site definitions may be deposited.
- **Note**: Scotland's SSSI count is far higher than England's (15,877
  against 4,128) because the Scottish layer is split by feature parcel
  rather than by site. Dissolve by site identifier before use, or the
  land-cover stratification will be weighted by parcel fragmentation
  rather than by area.

## Wales — SSSI and NNR (Natural Resources Wales)

- **Verified 2026-07-29: Wales is NOT covered by the Natural England
  extract** and publishes separately, as suspected. Fetched from
  `https://datamap.gov.wales/geoserver/ows`, layers `inspire-nrw:NRW_SSSI`
  and `inspire-nrw:NRW_NNR`.
- **Retrieved**: SSSI 1,088 features (76.9 MB), NNR 76 features (4.6 MB)
- **Licence**: NRW publishes under the Open Government Licence;
  attribution "Contains Natural Resources Wales information © Natural
  Resources Wales and Database Right" to be confirmed verbatim from the
  dataset metadata before deposit.

## Coverage summary

| nation | SSSI | NNR | source |
|---|---:|---:|---|
| England | 4,128 | 224 | Natural England (DEFRA WFS) |
| Scotland | 15,877* | 747 | NatureScot |
| Wales | 1,088 | 76 | Natural Resources Wales |

\* parcel-split, not site-split — dissolve before use.

Great Britain is therefore fully covered for the reference-site rule.

## Still to obtain

- **Northern Ireland** protected areas (NIEA) — needed only if NI
  stations ever re-enter scope; they are currently excluded from the
  control cohort by decision, so this is not blocking.
- **Building footprints** for the "zero current mapped building
  footprint" half of the admission rule (OS OpenMap Local, OGL, or OSM
  under ODbL).

## Why these sites

The classifier's tolerance calibration measures apparent change at
places where no real change occurred, so the reference set must be
admitted by an external rule rather than by our judgement: protected-area
core parcels with continuous statutory protection predating 1975 and
zero current mapped building footprint, stratified by the land-cover
classes of candidate control stations. See the spec requirement
"Rule-defined reference sites".

## Building footprints — OS OpenMap Local

The reference-site admission rule requires "zero current mapped building
footprint" as well as protected status. Source: **Ordnance Survey
OpenMap Local**, GB GeoPackage, ~3.5 GB, downloaded 2026-07-29 direct
from the OS Data Hub API with **no account** (`api.os.uk/downloads/v1/
products/OpenMapLocal/downloads?area=GB&format=GeoPackage&redirect`).

- **Licence**: Open Government Licence. Attribution: "Contains OS data
  © Crown copyright and database right [year]."
- **Layer of interest**: `building` polygons.
- **Why this rather than OSM**: national, uniform, authoritative and
  OGL — OSM building coverage varies by mapper enthusiasm, which would
  make the admission rule's strictness vary geographically. OSM remains
  the right source for the airfield screen, where the feature type is
  well mapped and the screen is one-way.
