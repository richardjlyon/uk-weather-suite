# Proposal: add-scotland-pre1975-screen

*(Directory name retained; the NLS/Stamp raster route it was first
written for was abandoned on review — see "Why the first design died".)*

## Why

Scottish stations have no pre-satellite screen: the Environment
Agency's digitisation of the 1930s Land Utilisation Survey stops at the
English/Welsh border. Without a screen, a Scottish station that was
already built around before 1975 can enter the still-rural control
cohort undetected — and Scotland is where the long-record rural stations
live, so excluding it wholesale (as Northern Ireland was excluded) would
leave a UK study whose controls are all English and Welsh lowland.

**Sized before designing** (2026-07-29, from data on hand): of 438
uncovered GB stations, 303 are rural in 2020, and only **72 have records
of 30 years or more** (45 at 40 years). The screen therefore has to
serve tens of stations, not hundreds — which rules out building a
bespoke raster-classification pipeline for it.

## Why the first design died

The first version proposed classifying NLS scans of the Land Utilisation
Survey by its printed colour key. Adversarial review (2026-07-29) killed
it on four counts, each verified:

1. **The layer is not in the API.** The NLS Historic Maps API serves five
   OS series; the Land Utilisation Survey is not among them, and the
   free-tier/CC-BY terms cited belong to those OS layers.
2. **Copyright complicates the deposit.** Stamp died 1966, so the
   survey is in copyright to 2036; the LUS scans are CC-BY-**NC-SA**,
   and Suggitt et al. (2023) state the full-resolution land-use data
   "remain under copyright and are not available". Note the honest
   qualifier: the England/Wales EA source is *also* non-commercially
   licensed, so this alone would not have killed the route — see
   "Licence position across the screen" below.
3. **The colour premise was inverted.** Stamp's key is yellow =
   heath/moorland and brown = arable (the draft had them swapped), and
   red is *"land agriculturally unproductive"* — cliffs, scree, quarries
   and dunes as well as buildings. The screen's decision class was the
   ambiguous one, and would have false-flagged upland rural stations
   with a crag in the ring: the single error this screen must not make.
   (Colour classification of these scans is itself published and
   validated — HistMapR, Auffret et al. 2017, used by Suggitt et al. on
   these very sheets; what failed here was the API, the licence, the
   unpublished sheets and *our* class mapping, not the technique.)
4. **The Scottish sheets are a different physical object.** 57 upland
   sheets were never published; NLS holds 1960s hand-coloured copies of
   Stamp's manuscripts. A palette calibrated on lithographed border
   sheets measures nothing about hand-colouring.

## What Changes

- **Source swapped to the OS Popular Edition, Scotland (1920–1930)** —
  contemporaneous with the survey, covering all Scotland including the
  uplands with no unpublished-sheet gap, served by the NLS Historic Maps
  API. Its terms are stated as CC-BY 3.0 on the API page but CC-BY-SA
  3.0 elsewhere, so they are treated as **unverified until confirmed at
  task 1.1** — with viewer permalinks as the redistribution-free
  fallback for per-station evidence. It shows buildings directly, which
  is what a binary "already-built-up-before-1975" screen asks, rather
  than a land-use taxonomy that must then be collapsed to binary.
- **Scope: control-cohort candidates only** (~72 stations at the 30-year
  record threshold; the exact set is derived by rule from the
  classification table, not hand-picked).
- **Measure is building-symbol detection, not ink fraction**: connected
  components of the solid-black building rendering, filtered on size,
  solidity and aspect. An ink-area fraction would measure the map rather
  than the ground — at one inch to the mile a place-name label covers
  several percent of a 500 m ring against under one percent for a
  three-building farm — and would not be comparable with GHSL.
  Ambiguous evidence excludes a station rather than admitting it.
- **The rule decides; extracts are evidence**: the rule and its
  parameters are frozen, published and hashed before any extract is
  viewed or any temperature series joined. Extracts let a reader check
  the rule's verdict; they are never an input to membership. Overrides
  are numbered, reason-coded and reported with and without.
- **Instrument gap calibrated, not disclosed**: the route is run over
  EA-screened stations and its 2×2 agreement published, with the
  Scottish operating point set to reproduce EA decisions — because the
  instrument boundary coincides with the long-record rural cohort
  boundary, an unmeasured leniency would bias the load-bearing stations
  in the flattering direction.
- **Corroboration demoted to a gross-error detector**: hectad urban
  proportions are a 100 km² square against a 314 km² disc and derive
  from the same LUS red class this design avoids, so they are not an
  agreement metric.
- **Honest floor retained**: if the screen cannot be made to work, the
  affected stations are excluded with a measured reason, exactly as
  Northern Ireland was.

## Licence position across the screen (resolved 2026-07-29)

Both halves of the pre-1975 screen rest on non-commercially licensed
sources: the EA Digital Land Utilisation Survey carries the EA
Conditional Licence with a non-commercial restriction and Audrey N.
Clark's copyright; the NLS map terms are stated variously as CC-BY 3.0
(API page), CC-BY-SA 3.0 (elsewhere) and non-commercial (general image
terms). The position that makes both coherent, and which this change
adopts: **per-station derived binary facts are deposited; source
imagery and full-resolution derivatives are not.** Where a licence is
unconfirmed or forbids redistribution, per-station evidence is a
viewer permalink rather than pixels. The earlier framing ("licence
drives the source choice") was inconsistent and is withdrawn: the
source choice is driven by fitness — API availability, upland coverage,
and answering the binary question directly.

## Capabilities

### New Capabilities
- `scotland-pre1975-screen`: pre-satellite built-up screen for
  EA-uncovered GB control candidates from CC-BY OS Popular Edition
  mapping, with per-station published extracts.

### Modified Capabilities

(none)

## Non-goals

- No Land Utilisation Survey raster classification (killed on review:
  not in the API, NC-SA licensed, colour premise unsound, Scottish
  sheets unpublished).
- No bespoke reimplementation of published methods: if Suggitt et al.'s
  validated 5 m Scottish rasters can be obtained (a request only
  Richard can send), they supersede this route and the change is
  re-scoped to consume them.
- No Northern Ireland (excluded by decision 2026-07-29).
- No claim that this screen matches the EA vector screen class-for-class
  — it is a different, coarser question (built or not), stated as such
  and bounded by the overlap calibration.
- No re-screening of the whole network by this route for consistency:
  the API's England/Wales tiles are a different edition (New Popular
  1945–47) with different symbology, so uniformity of layer name would
  not be uniformity of instrument.
