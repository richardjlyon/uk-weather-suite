# OSM aeroway data — licence and provenance record

Source: **OpenStreetMap**, queried through the public Overpass API
(`https://overpass-api.de/api/interpreter`), retrieved 2026-07-29.
Three UK-wide pulls (bbox 49.7,-8.7,61.0,2.0), one per tag family:

- `aeroway` ~ `^(aerodrome|runway|taxiway|apron)$`
- `disused:aeroway` ~ same values
- `abandoned:aeroway` ~ same values

each as `nwr[...](bbox); out geom;` — cached in this directory as
`overpass-*.json` with SHA-256s in `overpass.sha256`. Re-running the
screen reuses the cache; deleting a cache file re-fetches it.

## Licence

OpenStreetMap data are © OpenStreetMap contributors and available under
the **Open Database Licence (ODbL) 1.0**
(https://www.openstreetmap.org/copyright). Attribution required in any
product using this layer:

> Contains data © OpenStreetMap contributors, licensed under the Open
> Database Licence (ODbL) 1.0.

The Overpass API is a public community service: bulk per-station
querying was deliberately avoided — the whole-UK pull is three requests
total.

## Semantics (binding, from the spec)

The screen is **one-way**: an OSM aeroway hit within a station's ring
flags the station ineligible for the still-rural control cohort; an
absence NEVER certifies a station clean — OSM's coverage of disused
wartime airfields is uneven. The flagged list publishes OSM feature ids
(`node/…`, `way/…`, `relation/…`) so every flag can be checked against
openstreetmap.org. Post-war OS mapping via the NLS API remains the
audit route for contested stations.
