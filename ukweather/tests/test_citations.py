"""Citation parsing guards (docs/designation-dates-2026-07-29.md).

The two that matter: the 1981-Act date must never satisfy the pre-1975
test, and a citation for the wrong site must be rejected outright.
"""

from __future__ import annotations

from ukweather.citations import (
    Site,
    names_match,
    normalise_name,
    parse_citation,
    row_for_site,
)

# Real text from designatedsites.naturalengland.org.uk, both templates.
EBSBURY = """COUNTY: WILTSHIRE

SITE NAME EBSBURY DOWN

Status: Site of Special Scientific Interest (SSSI) notified under Section 28 of the
Wildlife and Countryside Act 1981

Date Notified (Under 1949 Act): 1975

Date of Last Revision: Ð

Date Notified (Under 1981 Act): 1989
"""

ALLEN = """COUNTY: NORTHUMBERLAND

SITE NAME: ALLEN CONFLUENCE GRAVELS

Status: Site of Special Scientific Interest (SSSI) notified under Section 23 of the
Wildlife and Countryside Act 1981 as amended.

First Notified: 1968*

Date of Revision: 1988

Date of Renotification: 7 December 1988
"""

MODERN_ONLY = """COUNTY: KENT

SITE NAME: SOMEWHERE RECENT

Date Notified (Under 1949 Act): Ð

Date Notified (Under 1981 Act): 1992
"""


def test_parses_both_citation_templates():
    a = parse_citation(EBSBURY)
    assert a["first_notified_year"] == 1975
    assert a["original_field"] == "1949-act"
    assert a["renotified_year"] == 1989

    b = parse_citation(ALLEN)
    assert b["first_notified_year"] == 1968
    assert b["original_field"] == "first-notified"
    assert b["renotified_year"] == 1988


def test_1981_date_never_stands_in_for_the_original():
    # The whole point of finding 8: a site with only a 1981-Act date has
    # NO usable original date. It must not silently inherit 1992.
    p = parse_citation(MODERN_ONLY)
    assert p["first_notified_year"] is None
    assert p["renotified_year"] == 1992


def test_absent_date_dash_is_absence_not_a_year():
    assert parse_citation("SITE NAME: X\nFirst Notified: Ð\n")["first_notified_year"] is None


def test_value_on_the_following_line_is_still_the_value():
    """Moulsford Downs: pdftotext puts 1955 in a block below its label.
    Confining the value to the label's own line silently loses it."""
    wrapped = (
        "SITE NAME: MOULSFORD DOWNS\n"
        "Date Notified (Under 1949 Act):\n\n1955\n\n"
        "Date Notified (Under 1981 Act): 1986\n"
    )
    p = parse_citation(wrapped)
    assert p["first_notified_year"] == 1955
    assert p["renotified_year"] == 1986


def test_blank_field_does_not_borrow_the_next_fields_year():
    """The opposite failure: a genuinely blank 1949 field must not take
    the 1981 date sitting on the next line."""
    blank = (
        "SITE NAME: ALDERFORD COMMON\n"
        "Date Notified (Under 1949 Act):\n\n"
        "Date of Last Revision: –\n\n"
        "Date Notified (Under 1981 Act): 1986\n"
    )
    p = parse_citation(blank)
    assert p["first_notified_year"] is None
    assert p["renotified_year"] == 1986


def test_blank_and_missing_original_field_are_distinguished(tmp_path, monkeypatch):
    """A blank 1949-Act field is an observation; what it MEANS is the
    admission rule's call, so neither case is admitted or refused here.
    Both are `no-original-date`, sub-coded per the spec: blank stays
    blank, absent-with-a-renotification-date is `renotification-only`,
    absent with nothing at all is `original-field-absent`."""
    import ukweather.citations as c

    blank = "SITE NAME: ALDERFORD COMMON\nDate Notified (Under 1949 Act):\n\nDate Notified (Under 1981 Act): 1986\n"
    absent_renotified = "SITE NAME: ALDERFORD COMMON\nDate Notified (Under 1981 Act): 1986\n"
    absent_bare = "SITE NAME: ALDERFORD COMMON\nStatus: SSSI\n"

    assert parse_citation(blank)["original_field_seen"] is True
    assert parse_citation(absent_renotified)["original_field_seen"] is False

    site = Site(ref_code="1", name="Alderford Common SSSI", hyperlink="1000483",
                designation="SSSI")
    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")

    monkeypatch.setattr(c, "pdf_text", lambda p: blank)
    row = c.row_for_site(site, tmp_path)
    assert row["reason"] == "no-original-date"
    assert row["reason_detail"] == "original-field-blank"
    assert row["admitted_pre_1975"] is None

    monkeypatch.setattr(c, "pdf_text", lambda p: absent_renotified)
    row = c.row_for_site(site, tmp_path)
    assert row["reason"] == "no-original-date"
    assert row["reason_detail"] == "renotification-only"

    monkeypatch.setattr(c, "pdf_text", lambda p: absent_bare)
    row = c.row_for_site(site, tmp_path)
    assert row["reason"] == "no-original-date"
    assert row["reason_detail"] == "original-field-absent"


def test_header_without_a_site_name_label_still_yields_the_name():
    """Angram Bottoms: county and site share one line, no SITE NAME
    label. Without a fallback the site is rejected as a name mismatch."""
    angram = (
        "NORTH YORKSHIRE: ANGRAM BOTTOMS\n"
        "Status: Site of Special Scientific Interest (SSSI) notified under Section 28\n"
        "First Notified: 1988\n"
    )
    p = parse_citation(angram)
    assert p["citation_site_name"] == "ANGRAM BOTTOMS"
    assert names_match("Angram Bottoms SSSI", p["citation_site_name"])


def test_name_normalisation_ignores_case_and_designation_suffix():
    assert normalise_name("Allen Confluence Gravels SSSI") == "ALLEN CONFLUENCE GRAVELS"
    assert names_match("Allen Confluence Gravels SSSI", "ALLEN CONFLUENCE GRAVELS")
    assert names_match("Winterton Dunes (NNR)", "WINTERTON DUNES")
    assert not names_match("Allen Confluence Gravels SSSI", "EBSBURY DOWN")
    assert not names_match("Anything", "")


def test_wrong_site_citation_is_rejected_not_recorded(tmp_path, monkeypatch):
    """Finding 9: keying on ref_code returns a valid date for the wrong place."""
    import ukweather.citations as c

    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: EBSBURY)

    site = Site(ref_code="1003435", name="Allen Confluence Gravels SSSI",
                hyperlink="1003435", designation="SSSI")
    row = c.row_for_site(site, tmp_path)

    assert row["reason"] == "identity-unverified"
    assert row["first_notified_year"] is None
    assert row["admitted_pre_1975"] is None


def test_revision_after_the_original_date_abstains_the_site(tmp_path, monkeypatch):
    """The Allen Confluence trap: First Notified 1968 belongs to the
    predecessor site (Staward Woods); today's polygon dates from the
    1988 revision. A revision post-dating the original means the date
    cannot be pinned to the current boundary — abstain, never admit."""
    import ukweather.citations as c

    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: ALLEN)

    site = Site(ref_code="1003435", name="Allen Confluence Gravels SSSI",
                hyperlink="1005624", designation="SSSI")
    row = c.row_for_site(site, tmp_path)

    assert row["reason"] == "boundary-history-unresolved"
    assert row["first_notified_year"] == 1968  # kept for the record
    assert row["revision_year"] == 1988
    assert row["admitted_pre_1975"] is None


def test_predecessor_site_note_abstains_even_undated(tmp_path, monkeypatch):
    import ukweather.citations as c

    formerly = (
        "SITE NAME: SOMEWHERE OLD\n"
        "First Notified: 1962\n"
        "Other Information:\n"
        "This site was formerly notified as part of Bigger Moor SSSI.\n"
    )
    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: formerly)

    site = Site(ref_code="1", name="Somewhere Old SSSI", hyperlink="9",
                designation="SSSI")
    row = c.row_for_site(site, tmp_path)

    assert row["reason"] == "boundary-history-unresolved"
    assert "formerly notified" in row["boundary_note"]


def test_renotification_alone_never_triggers_the_boundary_screen(tmp_path, monkeypatch):
    """The 1981-Act renotification was near-universal; treating it as a
    boundary event empties the reference set. Ebsbury: original 1975,
    renotified 1989, revision blank — admitted on the date test alone
    (1975 is not pre-1975, so admitted_pre_1975 is False, reason ok)."""
    import ukweather.citations as c

    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: EBSBURY)

    site = Site(ref_code="2", name="Ebsbury Down SSSI", hyperlink="1003435",
                designation="SSSI")
    row = c.row_for_site(site, tmp_path)

    assert row["reason"] == "ok"
    assert row["renotified_year"] == 1989
    assert row["admitted_pre_1975"] is False


def test_matching_citation_admits_on_the_original_date(tmp_path, monkeypatch):
    import ukweather.citations as c

    clean = (
        "SITE NAME: MOULSFORD DOWNS\n"
        "Date Notified (Under 1949 Act): 1955\n"
        "Date of Last Revision: Ð\n"
        "Date Notified (Under 1981 Act): 1986\n"
    )
    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: clean)

    site = Site(ref_code="3", name="Moulsford Downs SSSI", hyperlink="7",
                designation="SSSI")
    row = c.row_for_site(site, tmp_path)

    assert row["reason"] == "ok"
    assert row["first_notified_year"] == 1955
    assert row["admitted_pre_1975"] is True


def test_failures_become_reason_codes_not_exceptions(tmp_path, monkeypatch):
    import ukweather.citations as c

    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: None)
    site = Site(ref_code="1", name="X SSSI", hyperlink="9", designation="SSSI")
    assert c.row_for_site(site, tmp_path)["reason"] == "fetch-failed"

    no_key = Site(ref_code="1", name="X SSSI", hyperlink="", designation="SSSI")
    assert c.row_for_site(no_key, tmp_path)["reason"] == "no-citation-key"


def test_scanned_citation_is_no_original_date_sub_no_text(tmp_path, monkeypatch):
    import ukweather.citations as c

    monkeypatch.setattr(c, "fetch_citation", lambda h, d, m=1.0: tmp_path / "x.pdf")
    monkeypatch.setattr(c, "pdf_text", lambda p: "")
    site = Site(ref_code="1", name="X SSSI", hyperlink="9", designation="SSSI")
    row = c.row_for_site(site, tmp_path)
    assert row["reason"] == "no-original-date"
    assert row["reason_detail"] == "no-text"
