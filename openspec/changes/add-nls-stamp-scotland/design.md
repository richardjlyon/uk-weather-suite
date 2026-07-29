# Design: Scotland pre-1975 screen

## Approach

`ukweather.scotland_screen` (Python, uv):

1. **Candidate derivation** — rule over the classification and
   station-history tables: EA-uncovered, GB (not NI), rural at the
   primary ring in the latest sensor-anchored epoch, record length at or
   above the analysis minimum. Current count at a 30-year threshold:
   **72 stations** (45 at 40 years). Published with the run.
2. **Tiles** — NLS Historic Maps API, layer "One-inch to the mile,
   Popular edition, Scotland, 1920–1930" (CC-BY 3.0), per candidate AOI
   at the 10 km ring bound, cached with a manifest (URL, retrieval date,
   checksum). At ~72 stations this is trivially inside the free tier.
3. **Measure** — **connected-component detection of the solid-black
   building rendering** (the Scottish Popular sheets show buildings
   solid black, unlike the hatched English rendering), filtered on size,
   solidity and aspect so that place-name type, spot heights, parish
   boundaries, rough-pasture limit marks and railway linework do not
   qualify. Reported as component count and largest-cluster extent per
   ring. **Not** an ink-area fraction: at 1:63,360 one place label
   covers several percent of a 500 m ring against under one percent for
   a three-building farm, and building symbols carry a several-fold
   minimum-size area exaggeration — an ink fraction would measure the
   map, not the ground, and would not be comparable with GHSL.
4. **Extracts** — the georeferenced crop for each station's rings is
   written out and published with its number.
5. **Corroborate** — compare the 10 km figure against published hectad
   urban proportions; list disagreements.
6. **Emit** — a screen table joined to the cohort logic, with `source =
   os-popular-edition` and a per-station tile retrieval date.

## Key decisions

- **Size first, then design.** The original 424-station framing implied
  a pipeline; 72 candidates implies a measurement plus published
  evidence per station. The rule-derived cohort keeps it reproducible
  while the extracts keep it auditable — automation alone would hide
  map quirks, eyeballing alone would invite "you chose your own
  controls".
- **Built-up extent, not land use.** The screen's question is binary and
  physical. The OS sheet answers it directly; the Land Utilisation
  Survey would have answered a different question that then needs
  collapsing — and its red class mixes buildings with cliffs and
  quarries, which is fatal for upland Scotland.
- **Fitness drives the source choice; licence drives what is
  deposited.** Both screen halves rest on non-commercial sources, so the
  coherent rule is: deposit per-station derived facts, never source
  imagery; where terms are unconfirmed or forbid redistribution, deposit
  viewer permalinks instead of pixels.
- **Zoom is pinned.** NLS serves the one-inch series only at z12–18;
  lower zooms silently return quarter-inch or 1:1M mapping, which the
  code would measure without complaint. The fetcher pins the zoom and a
  test asserts it.
- **Prior art beats reimplementation.** If Suggitt et al.'s validated
  5 m Scottish rasters can be obtained, they supersede this route
  entirely. Asking is an external action reserved to Richard; the
  request is drafted and staged, not sent.

## Risks

- **Instrument mismatch is calibrated, not merely disclosed.** The
  screen is a different instrument from the EA vector screen, and the
  boundary between them coincides with the boundary of the long-record
  rural cohort — so an unmeasured leniency would bias the load-bearing
  stations in the direction that flatters the headline. The overlap
  calibration (run this route over EA-screened stations, publish the
  2×2, set the operating point to reproduce EA decisions) bounds it.
  Caveat stated: the API's England/Wales tiles are the New Popular
  1945–47, a later edition with different symbology, so the calibration
  bounds the gap rather than closing it.
- **"Uncovered" is determined by feature presence, not by latitude.**
  The EA dataset's stated extent reaches 55.816° N, but Eskdalemuir
  (55.31° N) is uncovered and 86 uncovered stations lie south of that
  line — the published bounding box overstates actual coverage.
- **Symbol exaggeration** on early OS mapping inflates apparent
  development; the buffer treatment is a spec'd requirement, and its
  cost in ring area is reported per station.
- **Survey dates** vary across sheets (1920–1930); recorded per station,
  as the EA route records survey dates.
- **The cohort may shrink further** once the analysis change fixes its
  record-length minimum. If it falls below ~20 stations, the honest
  option is to state Scotland's contribution as small and bounded rather
  than to over-engineer its screen.
