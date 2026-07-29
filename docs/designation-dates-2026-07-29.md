# Protected-site designation dates: what is actually published

**Date:** 2026-07-29
**Bears on:** finding 7; `add-station-classifier` task 1.6; the
"Rule-defined reference sites" requirement in
`openspec/changes/add-station-classifier/specs/builtup-extraction/spec.md`

The admission rule requires protected-area parcels "protected from
before 1975 and currently protected, with no de-notification on
record". Finding 7 recorded
that the England and Scotland layers on disk carry no designation date.
This note establishes what the *upstream publishers* hold, and the
answer changes what the rule can be written against.

## The trap: two different dates, one of them useless

Modern SSSI datasets record the date a site was notified under the
**Wildlife and Countryside Act 1981**. Almost every site of any age was
renotified under that Act during the 1980s. The 1981-Act date is
therefore *not* evidence of when protection began, and testing it
against a pre-1975 condition rejects sites whose protection in fact
began in the 1950s.

Welsh citation documents themselves are published at LERC Wales
Citations (`citations.lercwales.org.uk`; SSSI index at `/index_sssi`,
per-site pages at `/sssi/{n}`) — checked at source 2026-07-29: the
endpoint responds and enumerates sites, but the per-site page's static
HTML carries no citation text (content is script-loaded), so
machine-readability is NOT yet established, and the template family is
NRW/CCW's, not Natural England's. The parser-validation requirement in
the spec must budget for this: validating against Wales measures
template compatibility as well as recovery, which is why the spec also
requires a manually-read England sample.

Wales is the control case, because NRW publishes both dates in the GIS
layer already on disk:

| field | meaning | n | min | pre-1975 |
|---|---|---|---|---|
| `first_notified` | original notification (1949 Act) | 1,088 | 1950 | 280 (25.7%) |
| `confirmed` | 1981-Act renotification | 831 | 1977 | 0 (0.0%) |

Same sites, same file. Using `confirmed` yields an empty reference set
and would look like a legitimate null result. **Wales NNR `DEC_DATE`
behaves like `first_notified`** (min 1954, 16 of 76 pre-1975).

## Verified at source, per country

Checked 2026-07-29 against the live services, not the local copies.

### England — the date IS published, in the citation PDFs

- SSSI and NNR feature services
  (`services.arcgis.com/JJzESW51TqeY9uat/.../SSSI_England`,
  `.../National_Nature_Reserves_England`) carry no date field of any
  kind. Confirmed against the live service schema.
- The Designated Sites View site pages are ASP.NET WebForms driven by
  `__VIEWSTATE` postbacks — not a stable scrape and not a citable input.
- **Citation PDFs are directly addressable and contain the original
  date**, at
  `https://designatedsites.naturalengland.org.uk/PDFsForWeb/Citation/{id}.pdf`.

Two citation templates are in circulation and a parser must handle both:

```
Date Notified (Under 1949 Act): 1975        <- Ebsbury Down
Date Notified (Under 1981 Act): 1989
```
```
First Notified: 1968*                        <- Allen Confluence Gravels
Date of Revision: 1988
Date of Renotification: 7 December 1988
```

**Join key — this bites.** The citation id is the layer's `hyperlink`
field, **not** `ref_code`. Allen Confluence Gravels has
`ref_code=1003435`, `hyperlink=1005624`; fetching `1003435.pdf` returns
Ebsbury Down, Wiltshire — a different site 400 km away, with a valid
date, silently. Joining on `ref_code` produces a fully populated,
entirely wrong table. Any implementation must assert that the site name
parsed from the citation matches the layer name before accepting a date.

#### What the citations actually look like — three traps, all hit

Implemented in `ukweather/src/ukweather/citations.py`, tests in
`ukweather/tests/test_citations.py`. Each of these was found by running
against real citations, not by reading the format:

1. **A blank field must not borrow the next field's year.** The obvious
   regex (`label\s*([^\n]*)`) walks past a blank field's newline and
   captures whatever follows. On Alderford Common — 1949-Act field
   empty, 1981-Act field 1986 — that reports 1986 as the *original*
   notification. Finding 8 reintroduced by regex, and it silently
   admits a site first protected in 1986 to a pre-1975 set.
2. **But the value is often on the following line.** Confining the value
   to the label's own line fixes trap 1 and breaks Moulsford Downs,
   whose genuine 1955 date pdftotext renders as a separate block below
   the label. In a 12-site pilot this one change moved the admitted
   count from 6 to 5 and then back. **A field's value runs from its
   label to the next label** — neither same-line nor free-running.
3. **A third header template has no "SITE NAME" label at all.** Angram
   Bottoms reads `NORTH YORKSHIRE: ANGRAM BOTTOMS`, county and site on
   one line. Without a fallback the name-match guard rejects the site as
   a mismatch — a false rejection that quietly shrinks the reference set
   rather than corrupting it.

Two further observations recorded rather than interpreted:

- **Blank versus absent 1949-Act field.** A blank field probably means
  the site was first notified under the 1981 Act, but it may equally be
  an unfilled field. The fetcher records `original-field-blank` and
  `original-field-absent` as distinct observations and admits neither;
  **deciding what a blank means is the admission rule's job**, and the
  deposit should report the two counts separately.
- **Some citations are scanned images with no extractable text** (e.g.
  Ewefell Mire, `2000419.pdf`, four pages, no text layer). Recorded as
  `no-text` and undetermined. OCR is not attempted.

A 40-site pilot gives 26 parsed, 20 of them pre-1975, 13 undetermined
(7 absent, 6 blank), 1 with no text, 0 name mismatches.

Boundary-change indicator prevalence, checked 2026-07-29 over the first
400 cached citations (crude regex, first two pages, the project's own
`pdf_text`): "Date of Revision" 24/400 (6%), "Renotif" 13/400,
"formerly notified/part of" 5/400, no-text 2/400. Of ~188 sites whose
first-notified year regex-parses pre-1975, 16 carry a Date of Revision
— so the `boundary-history-unresolved` screen abstains roughly 8.5% of
pre-1975 candidates, not a collapse. The revision field is NOT the
near-universal renotification in disguise. (The low "Renotif" count is
a labelling artefact, not a contradiction of the near-universal 1980s
renotification: the 1949-Act template records the same event as "Date
Notified (Under 1981 Act)", and only the "First Notified" template
family uses the "Renotification" label — which also means the
boundary-change screen's sensitivity is template-dependent, since the
1949-Act template carries no Date of Revision field.) (Crude counts, superseded by
the full parsed run; recorded so the indicator list was checked by
daylight before freeze, not discovered at the calibration halt.) The pilot's 50%
pre-1975 sits ~3.5 sd above the Wales base rate of 25.7% (Binomial(40,
0.257): mean 10.3, sd 2.76, observed 20) — **not** attributable to
sampling noise. Either England genuinely differs from Wales, or
citation availability is correlated with site age (old typescript scans
yield `no-text`; blank 1949-Act fields mark young sites — the two
mechanisms need not cancel). The spec resolves this before calibration
with a manually-read England sample — at least 50 random citations plus
all `no-text` scans — and, only if Welsh citations prove
machine-readable (not yet established; see the LERC paragraph above),
a Welsh ground-truth check against `first_notified`.

### Scotland — not published

- The authoritative WFS (`ogc.nature.scot/geoserver/protectedareas`)
  schema has `STATUS` and `UPDATED` only. No designation date.
- SiteLink's API (`sitelink-api.nature.scot/sitelink-api/v1/sites`)
  returns all 2,188 protected sites in one request — note **1,422 are
  SSSIs**, against 15,877 parcels in the GeoJSON, confirming the
  parcel-split warning. Per-site records expose `designation.date`.
- **That date is the 1981-Act renotification.** Sampled 25 SSSIs spread
  across the register: range 1983–2003, **zero pre-1975**. The sample
  includes Rannoch Moor, Mousa and Fossil Grove — all protected since
  the 1950s or 60s, all carrying mid-1980s dates.
- Per-site `documents` lists carry Ramsar, JNCC and condition links but
  **no citation PDF**. There is no published route to the original
  Scottish notification date found on this pass.

## Consequence

The rule as specified is satisfiable for **England** (citation fetch and
parse, 4,128 sites) and **Wales** (already on disk, use
`first_notified`, never `confirmed`). It is **not** satisfiable for
Scotland from published data.

Do not relax the rule to "currently protected" — that admits recently
protected land and is the quiet substitution this project keeps
catching. The honest options are:

1. **Scotland abstains** from the reference-site set, consistent with
   finding 5, where Scotland already abstains from the 1930s land-use
   screen and the census-density layer.
2. **Staged request to NatureScot** for original notification dates,
   following the pattern of the GBHGIS and Suggitt requests. Richard
   sends; this is not ours to send.

Option 1 has an analytical cost that is not cosmetic. Reference sites
are stratified by land cover, and Scotland carries montane and blanket
bog strata that England and Wales barely hold — the same strata many
rural Scottish stations sit in. Losing Scotland thins exactly the
tolerance strata those stations would be gated by, which under the
"widest stratum where its own is thin" fallback makes those stations
harder to move off no-change. Both hypotheses are two-sided, so no
direction is claimed as conservative: holding genuinely urbanised
Scottish stations inside the control cohort contaminates the control
arm, and it shifts cohort geographic composition — a confound for the
homogenisation hypothesis, not a haircut. The spec therefore requires
the deposit to report cohort composition by country and the primary
analysis to be repeated excluding stations whose gating stratum fell
below n = 20 admitted sites and therefore used the widest-stratum
fallback. A second asymmetry to name in the deposit's limitations: the
boundary-change screen runs on England (citations) but is unperformed
for Wales (GIS field carries no boundary history), so one country's
admitted set is boundary-screened and the other's is not within the
same calibration pool — the imagery audit extracts are the compensating
control.

Recommendation: raise the NatureScot request now so it can run in
parallel, and specify the rule so that a country with no published
original date abstains explicitly, with the abstention recorded as a
reason code rather than an absence.
