"""Golden-file characterization of the filing-homepage parse (edgartools-07lk.11.5).

Generated while ``attachments.py`` still ran on BeautifulSoup, so that the
bs4 -> lxml port could be proved to change nothing. ``homepage_baseline.json``
is the committed output of the bs4 implementation over every fixture in
``tests/fixtures/homepages``; the tests below re-derive it through lxml and
compare, so the parse output is identical rather than merely "the assertions
still pass".

WHY A GOLDEN FILE AND NOT FIELD ASSERTIONS. ``test_jrmw_filing_homepage_filers``
already asserts ground truth on the filer fields, which is the right shape for a
bug fix. A parser swap is different: it can move anything -- a stripped space, a
dropped tail, a None where a string used to be -- and field assertions only
catch what someone thought to name. Three of this file's translations are
exactly the invisible kind:

  * ``.text`` -> ``.text_content()``. lxml's ``.text`` is only a node's own
    leading text; bs4's was every descendant's. The wrong one still returns a
    string, and for a single-text-node cell it returns the RIGHT string, so it
    fails only on the nested cells.
  * ``br.replace_with("\\n")`` -> splice-and-remove. Dropping an element in lxml
    deletes its tail, which is the text between this <br> and the next, so a
    naive translation silently glues the identification lines together. Same
    family as hxtd and 2h2s.
  * ``child.get("class")`` returned a token LIST in bs4 and returns the raw
    string in lxml, so ``"info" in classes`` quietly became a substring test.
"""
import json
import pathlib

import pytest

from edgar.attachments import Attachments, FilingHomepage, parse_homepage_html

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
HOMEPAGE_DIR = REPO / "tests" / "fixtures" / "homepages"
BASELINE = HOMEPAGE_DIR / "homepage_baseline.json"


def _fixtures():
    return sorted(HOMEPAGE_DIR.glob("*.html"))


def _attachment_dump(attachment):
    return {
        "sequence_number": attachment.sequence_number,
        "description": attachment.description,
        "document": attachment.document,
        "ixbrl": attachment.ixbrl,
        "path": attachment.path,
        "document_type": attachment.document_type,
        "size": attachment.size,
        "purpose": attachment.purpose,
    }


def _parse(path: pathlib.Path):
    root = parse_homepage_html(path.read_bytes())
    attachments = Attachments.load(root)
    return FilingHomepage(f"file://{path}", root, attachments), attachments


def _capture(path: pathlib.Path):
    homepage, attachments = _parse(path)
    return {
        "documents": [_attachment_dump(a) for a in (attachments.documents or [])],
        "data_files": [_attachment_dump(a) for a in (attachments.data_files or [])],
        "primary_documents": [_attachment_dump(a) for a in (attachments.primary_documents or [])],
        "filers": [f.model_dump() for f in homepage.get_filers()],
        "filing_dates": list(homepage.get_filing_dates() or []),
    }


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


def test_every_fixture_is_in_the_baseline(baseline):
    """A fixture added without regenerating the baseline would otherwise be
    parsed by nothing and prove nothing."""
    assert sorted(baseline) == [p.name for p in _fixtures()]


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.stem)
def test_the_parse_matches_the_bs4_baseline(path, baseline):
    assert _capture(path) == baseline[path.name]


def test_the_baseline_is_not_vacuous(baseline):
    """A baseline of empty lists would compare equal to a parser that found
    nothing at all -- which is the bug jrmw just fixed."""
    assert sum(len(f["documents"]) for f in baseline.values()) > 50
    assert sum(len(f["filers"]) for f in baseline.values()) >= 6
    assert all(f["filing_dates"][0] for f in baseline.values())


# --------------------------------------------------------------- edge inputs
#
# The three inputs where lxml does not behave as bs4 did, pinned here because
# `FilingHomepage.load` feeds it whatever the SEC returned.


@pytest.mark.parametrize("html", ["", "   \n\t  ", b""])
def test_empty_input_yields_an_empty_document_rather_than_raising(html):
    """bs4 built an empty soup for these; lxml raises ParserError. A truncated
    or blank response has always produced a homepage with nothing on it, and
    still does."""
    root = parse_homepage_html(html)
    assert Attachments.load(root).documents == []
    assert FilingHomepage("http://example/x", root, Attachments.load(root)).get_filers() == []


def test_an_encoding_declaration_does_not_raise():
    """``lxml.html.fromstring`` refuses a *str* that opens with an encoding
    declaration -- SEC markup carries them routinely, so the parse takes bytes."""
    html = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<html><body><div class="filerDiv">x</div></body></html>')
    assert len(parse_homepage_html(html).xpath('//div[@class="filerDiv"]')) == 1


def test_sec_error_pages_parse_to_nothing_rather_than_crashing():
    """SEC answers a bad accession with a 200 and an apology page."""
    root = parse_homepage_html("<html><body><h1>File Unavailable</h1></body></html>")
    homepage = FilingHomepage("http://example/x", root, Attachments.load(root))
    assert homepage.get_filers() == []
    assert homepage.get_filing_dates() is None


def test_a_class_is_matched_by_token_not_by_substring():
    """The xpath translation of bs4's ``class_=`` has to match whole tokens:
    ``contains(@class, "mailer")`` would also match ``class="mailerAddress"``,
    and ``@class="mailer"`` would miss ``class="mailer extra"``."""
    root = parse_homepage_html(
        '<html><body>'
        '<div class="filerDiv extra"><div class="companyInfo">'
        '<span class="companyName">Widget Co (Filer) CIK: 0000000001</span>'
        '<p class="identInfo">SIC: 1234</p></div>'
        '<div class="mailerAddress">not an address</div>'
        '</div></body></html>')
    filers = FilingHomepage("http://example/x", root, None).get_filers()
    assert len(filers) == 1, "class='filerDiv extra' must still match"
    assert filers[0].company_name == "Widget Co"
    assert filers[0].addresses == [], "class='mailerAddress' must not match 'mailer'"


def test_a_soup_is_still_accepted_and_says_so():
    """`FilingHomepage` and `Attachments` are exported from `edgar`, and took a
    BeautifulSoup until this release. The old call keeps working through 5.x."""
    from bs4 import BeautifulSoup

    html = (HOMEPAGE_DIR / "aapl-10k-2024.html").read_text()
    soup = BeautifulSoup(html, "html.parser")

    with pytest.warns(DeprecationWarning, match="removed in v6.0"):
        attachments = Attachments.load(soup)
    with pytest.warns(DeprecationWarning, match="removed in v6.0"):
        homepage = FilingHomepage("http://example/x", soup, attachments)
    with pytest.warns(DeprecationWarning, match="soup="):
        FilingHomepage(url="http://example/x", soup=soup, attachments=attachments)

    # And produces the same answer as the supported call, not a degraded one.
    assert [f.model_dump() for f in homepage.get_filers()] == \
        _capture(HOMEPAGE_DIR / "aapl-10k-2024.html")["filers"]
