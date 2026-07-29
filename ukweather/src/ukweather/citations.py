"""Original SSSI/NNR notification dates from Natural England citations
(spec: builtup-extraction, "Rule-defined reference sites"; evidence and
reasoning in docs/designation-dates-2026-07-29.md, findings 8 and 9).

The reference-site admission rule needs statutory protection CONTINUOUS
SINCE BEFORE 1975. No England GIS layer carries any date at all, and the
date that IS published elsewhere is the wrong one: almost every site of
any age was renotified under the Wildlife and Countryside Act 1981, so a
1980s date says nothing about when protection began. Wales proves the
trap — NRW publishes both, and `first_notified` reaches 1950 (26%
pre-1975) while `confirmed` bottoms out at 1977 (0% pre-1975).

Natural England publishes the ORIGINAL date in the per-site citation
PDF, as either "Date Notified (Under 1949 Act)" or "First Notified".
This module fetches those citations and extracts it.

TWO GUARDS, BOTH NON-NEGOTIABLE:

1. THE CITATION IS KEYED BY `hyperlink`, NOT `ref_code`. Fetching by
   ref_code returns a real, plausible, WRONG site: ref_code 1003435 is
   Allen Confluence Gravels in Northumberland, but 1003435.pdf is
   Ebsbury Down in Wiltshire. A ref_code join yields a fully populated
   and entirely wrong table. Every row therefore verifies the site name
   parsed from the PDF against the layer name, and a mismatch is a
   REJECTION, never a warning.

2. THE 1981-ACT DATE IS NEVER THE ANSWER. It is captured for context and
   stored in its own column, but `first_notified_year` is populated only
   from a 1949-Act / "First Notified" field. A site whose citation lacks
   one gets an explicit reason code, never a fallback.

Failures are per-site and explicit: one bad fetch or unparsable PDF
records a reason code and the run continues. There are no silent gaps —
every input site appears in the output exactly once, admitted or not.

Retrieval is cached to disk (a re-run re-fetches nothing) and rate
limited to one request per second by default. The citations are public
and published under the Open Government Licence; this is still someone
else's web server, so it is asked politely, once, with an honest
User-Agent.

Licence: © Natural England, Open Government Licence v3.0.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CITATION_URL = "https://designatedsites.naturalengland.org.uk/PDFsForWeb/Citation/{}.pdf"
USER_AGENT = (
    "uk-weather-suite/0.1 (non-commercial research; "
    "reference-site admission rule; contact via repository)"
)
MIN_INTERVAL_S = 1.0

# Field LABELS. The value is extracted by _field_value below, not by a
# capture group, because neither obvious approach works:
#
#   \s*([^\n]*)   walks past a blank field's newline and swallows the
#                 NEXT field's value — a citation reading "Date Notified
#                 (Under 1949 Act):" followed by the 1981-Act line then
#                 reports the 1981 date as the original. That is
#                 finding 8 reintroduced by regex.
#   [ \t]*([^\n]*) confines the value to the label's own line, but
#                 pdftotext renders some citations with the value in a
#                 separate block on the FOLLOWING line. Moulsford Downs
#                 really is 1955 and this silently loses it.
#
# So a field's value runs from its label to wherever the next label
# starts, and a blank field yields nothing.
ORIGINAL_FIELDS = (
    ("1949-act", re.compile(r"Date\s+Notified\s*\(\s*Under\s+1949\s+Act\s*\)\s*:?", re.I)),
    ("first-notified", re.compile(r"First\s+Notified\s*:?", re.I)),
)
# Read for context only. NEVER used to satisfy the pre-1975 test.
RENOTIFIED_FIELDS = (
    re.compile(r"Date\s+Notified\s*\(\s*Under\s+1981\s+Act\s*\)\s*:?", re.I),
    re.compile(r"Date\s+of\s+Renotification\s*:?", re.I),
)
# Boundary-change indicators (spec: "revision after the original date is
# not silently ignored"). A renotification alone is NOT one — the
# 1981-Act renotification was near-universal and says nothing about
# boundaries. A Date of Revision post-dating the original, or a
# predecessor-site / extension / de-notification note, means today's
# polygon cannot be assumed to be the one protected at the original
# date, so the site abstains as `boundary-history-unresolved`.
REVISION_FIELD = re.compile(r"Date\s+of\s+(?:Last\s+)?Revision\s*:?", re.I)
BOUNDARY_NOTE_RE = re.compile(
    r"formerly\s+(?:notified|part\s+of)|\bextension\b|\bde-?notif\w*", re.I
)
# A line that introduces another field, i.e. the end of this one.
LABEL_LINE_RE = re.compile(r"^\s*[A-Za-z][^\n:]{0,60}:")
MAX_VALUE_LINES = 4
SITE_NAME_RE = re.compile(r"SITE\s+NAME\s*:?\s*([^\n]+)", re.I)
# A third header template carries no "SITE NAME" label at all, putting
# county and site on one line: "NORTH YORKSHIRE: ANGRAM BOTTOMS". Take
# the text after the colon. When this guesses wrong the name simply
# fails to match and the site is rejected — the safe direction.
HEADER_FALLBACK_RE = re.compile(r"^[^:\n]{2,40}:\s*([^\n]+)$")
YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


@dataclass(frozen=True)
class Site:
    ref_code: str
    name: str
    hyperlink: str
    designation: str  # "SSSI" or "NNR"


def sites_from_geojson(path: Path, designation: str) -> list[Site]:
    """Read the Natural England layer, keeping the citation key."""
    data = json.loads(Path(path).read_text())
    out = []
    for f in data["features"]:
        p = f["properties"]
        out.append(
            Site(
                ref_code=str(p.get("ref_code") or ""),
                name=str(p.get("name") or ""),
                hyperlink=str(p.get("hyperlink") or "").strip(),
                designation=designation,
            )
        )
    return out


def normalise_name(name: str) -> str:
    """Compare names across the layer and the citation.

    The layer says "Allen Confluence Gravels SSSI"; the citation says
    "ALLEN CONFLUENCE GRAVELS". Case, punctuation and the designation
    suffix differ and none of that is a real difference.
    """
    n = name.upper()
    n = re.sub(r"\b(SSSI|NNR|S\.S\.S\.I\.)\b", " ", n)
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^A-Z0-9]+", " ", n)
    return " ".join(n.split())


def names_match(layer_name: str, citation_name: str) -> bool:
    a, b = normalise_name(layer_name), normalise_name(citation_name)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def _field_value(text: str, start: int) -> str:
    """Text belonging to a field, from the end of its label to the next.

    Stops at the next field label, so a blank field returns "" instead
    of borrowing the following field's value.
    """
    rest = text[start:]
    lines = rest.split("\n")
    out = [lines[0]]
    for line in lines[1:MAX_VALUE_LINES]:
        if LABEL_LINE_RE.match(line):
            break
        out.append(line)
    return " ".join(out).strip()


def _year(value: str) -> int | None:
    """First 4-digit year in a citation field value.

    Citations write an absent date as a dash (often mangled to "Ð" by
    the PDF's encoding), which must read as absent, not as a parse
    failure.
    """
    m = YEAR_RE.search(value or "")
    return int(m.group(1)) if m else None


def parse_citation(text: str) -> dict:
    """Pull site name, original notification year and the 1981 date."""
    name_m = SITE_NAME_RE.search(text)
    if name_m:
        site_name = name_m.group(1).strip()
    else:
        first = next((ln for ln in text.split("\n") if ln.strip()), "")
        fb = HEADER_FALLBACK_RE.match(first.strip())
        site_name = fb.group(1).strip() if fb else ""

    original_year, original_field = None, None
    original_field_seen = False
    for field_name, pat in ORIGINAL_FIELDS:
        m = pat.search(text)
        if not m:
            continue
        original_field_seen = True
        y = _year(_field_value(text, m.end()))
        if y is not None:
            original_year, original_field = y, field_name
            break

    renotified_year = None
    for pat in RENOTIFIED_FIELDS:
        m = pat.search(text)
        if m:
            y = _year(_field_value(text, m.end()))
            if y is not None:
                renotified_year = y
                break

    m = REVISION_FIELD.search(text)
    revision_year = _year(_field_value(text, m.end())) if m else None
    note_m = BOUNDARY_NOTE_RE.search(text)
    boundary_note = None
    if note_m:
        line_start = text.rfind("\n", 0, note_m.start()) + 1
        line_end = text.find("\n", note_m.end())
        boundary_note = text[line_start: line_end if line_end != -1 else None].strip()

    return {
        "citation_site_name": site_name,
        "first_notified_year": original_year,
        "original_field": original_field,
        "original_field_seen": original_field_seen,
        "renotified_year": renotified_year,
        "revision_year": revision_year,
        "boundary_note": boundary_note,
    }


def fetch_citation(hyperlink: str, cache_dir: Path, min_interval_s: float = MIN_INTERVAL_S) -> Path | None:
    """Download one citation PDF, cached. Returns None on failure."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{hyperlink}.pdf"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    req = urllib.request.Request(
        CITATION_URL.format(hyperlink), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    finally:
        time.sleep(min_interval_s)

    if not body.startswith(b"%PDF"):
        return None
    tmp = dest.with_suffix(".pdf.tmp")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def pdf_text(path: Path) -> str | None:
    try:
        r = subprocess.run(
            ["pdftotext", str(path), "-"], capture_output=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def row_for_site(site: Site, cache_dir: Path, min_interval_s: float = MIN_INTERVAL_S) -> dict:
    """One output row. Never raises: failures become reason codes.

    Reason codes follow the spec's scheme: `identity-unverified` when
    the citation cannot be proven to belong to this polygon (it may hold
    a sound date for somewhere else); `no-original-date` with a
    `reason_detail` sub-code (`no-text`, `original-field-blank`,
    `original-field-absent`, `renotification-only`) when no original
    date can be established; `boundary-history-unresolved` when a
    boundary-change indicator post-dates the original date.
    """
    base = {
        "ref_code": site.ref_code,
        "name": site.name,
        "hyperlink": site.hyperlink,
        "designation": site.designation,
        "citation_site_name": None,
        "first_notified_year": None,
        "original_field": None,
        "original_field_seen": None,
        "renotified_year": None,
        "revision_year": None,
        "boundary_note": None,
        "admitted_pre_1975": None,
        "reason": None,
        "reason_detail": None,
    }

    if not site.hyperlink:
        return {**base, "reason": "no-citation-key"}

    pdf = fetch_citation(site.hyperlink, cache_dir, min_interval_s)
    if pdf is None:
        return {**base, "reason": "fetch-failed"}

    text = pdf_text(pdf)
    if not text or not text.strip():
        return {**base, "reason": "no-original-date", "reason_detail": "no-text"}

    parsed = parse_citation(text)
    row = {**base, **parsed}

    if not names_match(site.name, parsed["citation_site_name"]):
        # Finding 9. A wrong-site citation is worse than no citation,
        # because its date is perfectly valid for the wrong place.
        return {**row, "first_notified_year": None, "original_field": None,
                "reason": "identity-unverified"}

    if parsed["first_notified_year"] is None:
        # Record what was OBSERVED, do not infer what it means. A blank
        # 1949-Act field probably means the site was first notified
        # under the 1981 Act, but it could equally be an unfilled field.
        # Deciding between those is the admission rule's job, not the
        # fetcher's, so both stay undetermined here and are counted
        # separately in the deposit.
        if parsed["original_field_seen"]:
            detail = "original-field-blank"
        elif parsed["renotified_year"] is not None:
            detail = "renotification-only"
        else:
            detail = "original-field-absent"
        return {**row, "reason": "no-original-date", "reason_detail": detail}

    # Boundary screen. A renotification alone never triggers this; a
    # dated revision after the original, or any predecessor-site /
    # extension / de-notification note (dated or not — undated IS
    # unresolved), means today's polygon may not be the 1949-Act one.
    revision_after = (
        parsed["revision_year"] is not None
        and parsed["revision_year"] > parsed["first_notified_year"]
    )
    if revision_after or parsed["boundary_note"]:
        return {**row, "reason": "boundary-history-unresolved"}

    return {
        **row,
        "admitted_pre_1975": parsed["first_notified_year"] < 1975,
        "reason": "ok",
    }


def main() -> None:
    import argparse
    from collections import Counter

    import pyarrow as pa
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("reference_sites_dir", type=Path,
                    help="dir holding sssi-england.geojson / nnr-england.geojson")
    ap.add_argument("cache_dir", type=Path, help="where citation PDFs are cached")
    ap.add_argument("out", type=Path, help="output parquet")
    ap.add_argument("--limit", type=int, default=None, help="pilot: first N sites")
    ap.add_argument("--min-interval", type=float, default=MIN_INTERVAL_S,
                    help="seconds between requests (politeness floor)")
    args = ap.parse_args()

    sites: list[Site] = []
    for fname, desig in (("sssi-england.geojson", "SSSI"), ("nnr-england.geojson", "NNR")):
        p = args.reference_sites_dir / fname
        if p.exists():
            sites.extend(sites_from_geojson(p, desig))
    if args.limit:
        sites = sites[: args.limit]
    if not sites:
        raise SystemExit(f"no England layers found in {args.reference_sites_dir}")

    rows, t0 = [], time.time()
    for i, s in enumerate(sites):
        rows.append(row_for_site(s, args.cache_dir, args.min_interval))
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"{i + 1}/{len(sites)} sites, {el:.0f}s elapsed", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.out)

    tally = Counter((r["reason"], r["reason_detail"]) for r in rows)
    admitted = sum(1 for r in rows if r["admitted_pre_1975"])
    print(f"{len(rows)} sites -> {args.out} ({time.time() - t0:.0f}s)")
    print(f"  pre-1975 admitted: {admitted}")
    for (reason, detail), n in tally.most_common():
        print(f"  {reason}{'/' + detail if detail else ''}: {n}")


if __name__ == "__main__":
    main()
