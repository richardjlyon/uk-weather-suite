# Tasks: Scotland pre-1975 screen

## 1. Access and terms

- [ ] 1.1 Confirm the NLS Historic Maps API serves "One-inch to the
      mile, Popular edition, Scotland, 1920-1930"; register for the free
      tier; record layer id, terms and CC-BY attribution verbatim with
      retrieval date in `data/scotland-screen/LICENCE-NOTE.md`.
- [ ] 1.2 Draft (do not send) the request to Suggitt et al. for their
      validated 5 m Scottish LUS rasters — an external action reserved
      to Richard. If granted, this change is re-scoped to consume them.

## 2. Candidate derivation

- [ ] 2.1 Rule-derived candidate set from the classification and
      station-history tables; publish rule and count (72 at 30 years,
      45 at 40 years as of 2026-07-29).

## 3. Measure (TDD)

- [ ] 3.1 Tile fetch with manifest (URL, retrieval date, checksum),
      resumable, cached.
- [ ] 3.2 Component detection per ring: size/solidity/aspect filters on
      solid-black building rendering; component count and largest-cluster
      extent — tests on synthetic tiles including place-name type, a spot
      height, a parish boundary, railway linework and a JPEG-boundary
      case, none of which may qualify as buildings.
- [ ] 3.2b Pin the tile zoom to the one-inch range (z12–18); a test
      asserts it, because lower zooms silently return quarter-inch or
      1:1M mapping that the code would measure without complaint.
- [ ] 3.3 Registration-error check against the 500 m ring.

## 3c. Calibration against the EA overlap (before Scotland)

- [ ] 3c.1 Run the route over EA-screened stations; publish the 2×2
      agreement with EA decisions and set the operating point to
      reproduce them; state the edition caveat.
- [ ] 3c.2 If no operating point reproduces EA decisions, take the
      honest floor immediately and report — no tuning toward a preferred
      cohort.

## 4. Evidence and corroboration

- [ ] 4.1 Publish a georeferenced extract per screened station.
- [ ] 4.2 Compare 10 km results against published hectad urban
      proportions; list disagreements.
- [ ] 4.3 Sanity: Eskdalemuir should read unbuilt; an Edinburgh or
      Glasgow station should read built; include one upland station with
      a quarry or crag in the ring as the discriminating case.

## 5. Close out

- [ ] 5.1 Emit the screen table with `source = os-popular-edition`;
      wire into cohort logic beside the EA-derived rows.
- [ ] 5.2 Validate --strict; roast; fold; re-roast; archive; vault note
      via coordinator.
