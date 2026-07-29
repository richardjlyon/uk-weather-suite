# Design: add-daily-ingest

## Shape

No new machinery: `midas-fetch index/fetch/parse` already generalise by
dataset argument (the hourly run proved the path at 34,238 files). The
daily datasets are far smaller (daily temperature indexed at ~2 GB of
CSV in the 2026-07-28 crawl; rain similar order). Time pressure: fetch
happens first, against the live token, before the test retrofit —
acquisition is resumable and idempotent, so fetching early carries no
risk.

## Key decisions

- **Fetch before tests**: the token dies 2026-07-31; raw CSVs on disk
  are re-parseable forever. Order: index+fetch both datasets → parse →
  conventions doc → cross-check → test retrofit.
- **Parser is frozen behaviour — and the fork proved unnecessary**
  (verified 2026-07-29). Daily datasets do key on `ob_end_time`
  (temperature, with `ob_hour_count` 12/24 periods) and `ob_date`/
  `ob_day_cnt` (rain) rather than `ob_time`. But the reader promotes
  whichever column the header marks as the time coordinate
  (`coordinate_variable,<col>,t`) and the writer builds its schema from
  the union of what the files declare — so both daily datasets parsed
  with **no code change, no failures and no coercions**. The reserved
  delta is withdrawn. Generality that was written for the hourly
  archive turned out to carry the daily ones for free.
- **Test doubles, not live CEDA**: fetcher tests run from captured
  listing fixtures and mocked keychain/token calls; CI-safe, no
  secrets, no network. The one live-behaviour risk (CEDA changing its
  JSON shape) is caught by the next real fetch, not by tests.
- **Cross-check is descriptive here**: the discrepancy report states
  distributions (by station, season, era); the *decision* on extrema
  source is add-analysis task 1.2's, made against this evidence.
- **Rain-day conventions matter later** (dose–response uses precip as a
  covariate candidate at most); documented now while we are reading the
  headers anyway.

## Risks

- Daily-dataset column semantics may differ from hourly in ways the
  header declares poorly (e.g. accumulation periods for rain) —
  mitigated by the conventions-doc requirement being a gate on the
  cross-check, and by max/min attribution rules being quoted from the
  dataset documentation verbatim.
- Token could expire mid-fetch — fetch is resumable; if it lapses,
  the remainder needs a fresh token from Richard (or password into
  `ceda-credentials`), flagged immediately rather than silently.
- The 1,637-station daily-temperature network is larger than the
  1,537-station hourly network — station-history covers the hourly set;
  daily-only stations get history rows when (and if) an analysis
  requirement needs them, recorded as a known gap. The gap cannot bite
  this change: the cross-check sample is necessarily hourly∩daily,
  which station-history already covers.
