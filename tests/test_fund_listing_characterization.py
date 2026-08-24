"""Characterization of the fund-listing URL finder's bs4 -> lxml port
(edgartools-07lk.11.9.5).

`fund_listing_baseline.json` is what `_find_latest_fund_data_url()` returned --
or raised -- for each input below, captured while the module still ran on
BeautifulSoup.

WHY THE EDGE INPUTS OUTNUMBER THE REAL PAGE 20 TO 1. The function has exactly
one real input, the SEC listing page, and it is machine-generated and uniform:
every header is a bare word with no whitespace and no nested markup, every
Format cell is a bare `XML` or `CSV`, and every File cell holds one `<a href>`.
A golden over that page alone pins the answer and almost nothing else -- a port
that used `text_content()` everywhere, dropped the `href` guard, and searched
`.//table` instead of `descendant-or-self::table` would still return the right
URL for it. Each EDGE input below is aimed at one construct the translation
touches, and each was confirmed to kill at least one mutant.

THE FIXTURE. `tests/fixtures/funds/sec_fund_series_class_listing.html` is the
page as SEC served it on 2026-08-24, trimmed to its two `<table>` elements --
the field glossary, whose headers do not match and which must therefore be
skipped, and the download listing, whose XML row precedes its CSV row in every
one of the 17 years it lists. Trimmed, it is also a FRAGMENT rather than a
document, which is the point: `lxml.html.fromstring` roots a fragment at its
first element, so a `.//table` search would miss a table that IS the root.

THE TRAPS THIS PINS, in the order they appear in the function:

  * `soup.find_all('table')` searches the whole document including the root.
    `descendant-or-self::table`, not `.//table`.
  * `get_text(strip=True)` is bs4's SECOND text behaviour: strip each string,
    then join with NOTHING. `text_content()` joins the raw strings, so a
    Format cell reading `C <em>SV</em>` is "CSV" to bs4 and "C SV" to lxml.
  * bs4's `get_text()` leaves `<script>`, `<style>` and `<template>` text out.
    `text_content()` puts it in.
  * bs4's `Comment` is a `str` subclass, but `get_text()` still excludes it.
  * `if link_tag and 'href' in link_tag.attrs` -- an lxml element with no
    ELEMENT children is falsy, so a plain `<a>text</a>` fails `if link_tag`
    and the function silently returns nothing. Must be `is not None`.
  * `download_text` hands back `str`. lxml refuses a `str` that carries an
    encoding declaration, so the port must encode before parsing.

MUTATION PROBE, 2026-08-24: 18 mistranslations, 17 killed. The survivor --
dropping the `if chunk.strip()` filter from `_cell_text` -- is an EQUIVALENT
mutant and provably so: the chunks are joined with the empty string, so a chunk
that strips to `""` contributes nothing either way. It would stop being
equivalent the moment that join gained a separator.

The real page killed 6 of the 18 on its own. The other 11 needed an edge input.
"""
import json
import pathlib

import pytest

import edgar.funds.reference as reference
from edgar.funds.reference import _find_latest_fund_data_url

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "fund_listing_baseline.json"
LISTING = FIX / "funds" / "sec_fund_series_class_listing.html"


def _table(rows, headers=("File", "Format", "Size")):
    """A minimal listing table in the shape the SEC page uses."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


_CSV_ROW = ['<a href="/files/f.csv">2026</a>', "CSV", "1 MB"]
_XML_ROW = ['<a href="/files/f.xml">2026</a>', "XML", "1 MB"]

EDGE = {
    # --- degenerate documents -------------------------------------------
    "empty": "",
    "whitespace": "   \n\t  ",
    "no-table": "<html><body><p>No data sets here.</p></body></html>",
    "table-without-headers": "<table><tr><td>x</td></tr></table>",
    "headers-but-no-csv-row": _table([_XML_ROW]),
    # --- fragment rooting ------------------------------------------------
    # The document IS the table. `.//table` finds nothing here; the real
    # fixture below has the same shape once trimmed.
    "table-is-the-root": _table([_XML_ROW, _CSV_ROW]),
    "table-is-the-root-single-row": _table([_CSV_ROW]),
    # --- get_text(strip=True) on the Format cell -------------------------
    # bs4 strips each string then joins with '': "C" + "SV" == "CSV".
    # text_content() joins the raw strings: "C SV", which does not contain CSV.
    "format-split-by-inline-tag": _table([["<a href='/f.csv'>2026</a>", "C <em>SV</em>", "1 MB"]]),
    "format-padded-with-whitespace": _table([["<a href='/f.csv'>2026</a>", "\n  CSV  \n", "1 MB"]]),
    # bs4's get_text() excludes <script>/<style>; text_content() includes them,
    # which turns a decorative cell into a match (or a match into a miss).
    "format-cell-has-script": _table([
        ["<a href='/f.xml'>2026</a>", "XML<script>var f='CSV';</script>", "1 MB"],
        _CSV_ROW,
    ]),
    "format-cell-has-style": _table([
        ["<a href='/f.xml'>2026</a>", "XML<style>.a{content:'CSV'}</style>", "1 MB"],
        _CSV_ROW,
    ]),
    # bs4's Comment subclasses str but get_text() still leaves it out; lxml
    # parsed with remove_comments=True MERGES the text either side into one
    # node, which changes what strip=True produces.
    # "CS " and " V" strip to "CS" and "V" and join to "CSV" under bs4, so this
    # cell MATCHES. text_content() yields "CS  V", which does not.
    "format-cell-has-comment": _table([
        ["<a href='/commented.csv'>2026</a>", "CS <!-- note --> V", "1 MB"],
    ]),
    "format-cell-has-template": _table([
        ["<a href='/f.xml'>2026</a>", "XML<template>CSV</template>", "1 MB"],
        _CSV_ROW,
    ]),
    # 'CSV' in text is case-SENSITIVE today. Pinning that it stays so.
    "format-lowercase-csv": _table([["<a href='/f.csv'>2026</a>", "csv", "1 MB"]]),
    # --- get_text(strip=True) on the headers -----------------------------
    "headers-padded-with-whitespace": _table([_CSV_ROW], headers=("  File  ", " Format ", "Size\n")),
    "headers-wrapped-in-links": _table(
        [_CSV_ROW],
        headers=('<a href="?sort=asc">File</a>', "For<em>mat</em>", "Size"),
    ),
    "headers-with-script": _table([_CSV_ROW], headers=("File<script>x</script>", "Format", "Size")),
    # --- column order and index arithmetic --------------------------------
    "columns-reordered": _table(
        [["CSV", "1 MB", "<a href='/f.csv'>2026</a>"]],
        headers=("Format", "Size", "File"),
    ),
    "extra-column-before-file": _table(
        [["#", "<a href='/f.csv'>2026</a>", "CSV", "1 MB"]],
        headers=("Rank", "File", "Format", "Size"),
    ),
    # --- the `if link_tag` guard -----------------------------------------
    # An lxml <a> with no ELEMENT children is falsy. `if link_tag` drops it.
    "file-cell-link-is-plain-text": _table([["<a href='/plain.csv'>2026</a>", "CSV", "1 MB"]]),
    "file-cell-link-wraps-an-element": _table([["<a href='/wrapped.csv'><b>2026</b></a>", "CSV", "1 MB"]]),
    "file-cell-link-is-empty": _table([["<a href='/empty.csv'></a>", "CSV", "1 MB"]]),
    "file-cell-anchor-without-href": _table([["<a name='x'>2026</a>", "CSV", "1 MB"]]),
    "file-cell-has-no-anchor": _table([["2026", "CSV", "1 MB"]]),
    "file-cell-href-is-empty": _table([["<a href=''>2026</a>", "CSV", "1 MB"]]),
    "file-cell-href-is-absolute": _table([["<a href='https://example.org/f.csv'>2026</a>", "CSV", "1 MB"]]),
    "file-cell-has-two-anchors": _table([
        ["<a href='/first.csv'>2026</a> <a href='/second.csv'>alt</a>", "CSV", "1 MB"],
    ]),
    # The <a> is not a direct child of the cell. bs4's find() searched the whole
    # subtree; ElementTree's find() searches direct children only.
    "file-cell-link-is-nested-deeper": _table([
        ["<span><b><a href='/deep.csv'>2026</a></b></span>", "CSV", "1 MB"],
    ]),
    # The DISCRIMINATING content is the script's tail, not the cell's own text.
    # strip_elements(..., with_tail=True) would delete it.
    "format-cell-text-follows-a-script": _table([
        ["<a href='/tail.csv'>2026</a>", "<script>var f='XML';</script>CSV", "1 MB"],
    ]),
    "format-cell-text-follows-a-style": _table([
        ["<a href='/styletail.csv'>2026</a>", "<style>.a{color:red}</style>CSV", "1 MB"],
    ]),
    # 'File' is a SUBSTRING of 'Filename'. A header test done on the joined text
    # instead of on the list would accept this table.
    "headers-only-look-like-a-match": _table(
        [["<a href='/wrong.csv'>2026</a>", "CSV", "1 MB"]],
        headers=("Filename", "Formatting", "Sizes"),
    ),
    # Two headers match exactly and the third only as a substring. The header
    # test must be membership in the LIST, not a search of the joined text.
    "headers-two-exact-one-substring": _table(
        [["<a href='/plural.csv'>2026</a>", "CSV", "1 MB"]],
        headers=("File", "Format", "Sizes"),
    ),
    # 300 nested <div>s. libxml2 discards below depth 256 unless huge_tree is on;
    # bs4's html.parser had no such limit. See edgartools-xqvr.
    "table-nested-300-deep": "<div>" * 300 + _table([_CSV_ROW]) + "</div>" * 300,
    # --- multiple tables --------------------------------------------------
    "first-table-does-not-match": (
        "<html><body>"
        + _table([["a", "b"]], headers=("Field Name", "Field Description"))
        + _table([_XML_ROW, _CSV_ROW])
        + "</body></html>"
    ),
    "matching-table-has-no-csv-second-does": (
        "<html><body>" + _table([_XML_ROW]) + _table([_CSV_ROW]) + "</body></html>"
    ),
    # bs4's find_all is recursive, so an inner table's <td>s are also the
    # outer row's <td>s. Pinning whatever that produced.
    # bs4's find_all is recursive, so the inner table's <td>s are ALSO the outer
    # row's <td>s, and in document order they land in the middle. The outer row's
    # own Format cell reads XML; only the recursive walk finds a CSV here.
    # The inner <td> lands at index 1 in a RECURSIVE walk and vanishes from a
    # direct-children one, so the two disagree about which cell holds the Format.
    "nested-table-shifts-cell-indices": (
        "<table><thead><tr><th>File</th><th>Format</th><th>Size</th></tr></thead>"
        "<tbody><tr><td><table><tr><td>CSV</td></tr></table>"
        "<a href='/outer.csv'>2026</a></td>"
        "<td>XML</td><td>1 MB</td></tr></tbody></table>"
    ),
    "nested-table": (
        "<table><thead><tr><th>File</th><th>Format</th><th>Size</th></tr></thead>"
        "<tbody><tr><td><a href='/outer.xml'>outer</a></td>"
        "<td><table><tr><td><a href='/inner.csv'>inner</a></td>"
        "<td>CSV</td><td>2 MB</td></tr></table></td>"
        "<td>XML</td></tr></tbody></table>"
    ),
    # --- parser leniency ---------------------------------------------------
    "unclosed-tags": "<table><tr><th>File<th>Format<th>Size<tr><td><a href='/loose.csv'>2026<td>CSV<td>1 MB",
    "encoding-declaration": (
        '<?xml version="1.0" encoding="UTF-8"?><html><head>'
        '<meta charset="utf-8"></head><body>' + _table([_CSV_ROW]) + "</body></html>"
    ),
    "non-ascii-text": _table([["<a href='/f–dash.csv'>2026 — latest</a>", "CSV", "1 MB"]]),
    "uppercase-tags": "<TABLE><TR><TH>File</TH><TH>Format</TH><TH>Size</TH></TR>"
                      "<TR><TD><A HREF='/upper.csv'>2026</A></TD><TD>CSV</TD><TD>1 MB</TD></TR></TABLE>",
}


# The one place the port deliberately changes the answer. `html.parser` does not
# auto-close `<th>`/`<td>`/`<tr>`, so it nests a tag-soup table inside itself and
# the finder walks away empty-handed; libxml2 in recover mode closes them and
# finds the link. Nothing SEC serves looks like this -- the listing page is
# Drupal-generated and well-formed -- and the new answer is the right one, so
# this is recorded rather than preserved. Keeping the bs4 value here means the
# baseline stays a faithful record of what bs4 did.
DIVERGES_FROM_BS4 = {
    "unclosed-tags": "https://www.sec.gov/loose.csv",
}


def _run(html: str, monkeypatch) -> str:
    """Return what the finder produced for `html`, exception included."""
    monkeypatch.setattr(reference, "download_text", lambda _url: html)
    try:
        return _find_latest_fund_data_url()
    except Exception as exc:  # noqa: BLE001 -- the exception IS the behaviour
        return f"{type(exc).__name__}: {exc}"


def _cases() -> dict:
    return {"REAL-sec-listing-page": LISTING.read_text(encoding="utf-8"), **EDGE}


@pytest.mark.parametrize("name", list(_cases()))
def test_fund_listing_url_matches_baseline(name, monkeypatch):
    baseline = json.loads(BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    expected = DIVERGES_FROM_BS4.get(name, baseline[name])
    assert _run(_cases()[name], monkeypatch) == expected


@pytest.mark.parametrize("name", list(DIVERGES_FROM_BS4))
def test_recorded_divergences_really_diverge(name):
    """A divergence that stopped diverging is an entry to delete, not to keep."""
    baseline = json.loads(BASELINE.read_text())
    assert DIVERGES_FROM_BS4[name] != baseline[name]


def test_baseline_covers_every_case():
    """A case dropped from EDGE must not sit unnoticed in the baseline."""
    assert set(json.loads(BASELINE.read_text())) == set(_cases())
