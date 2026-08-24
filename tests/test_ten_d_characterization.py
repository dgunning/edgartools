r"""Characterization of the 10-D header parser's bs4 -> lxml port
(edgartools-07lk.11.9.4).

`ten_d_baseline.json` is what `TenD.issuing_entity`, `.depositor`, `.sponsors`,
`.distribution_period` and `.security_classes` produced for each input below,
captured while `edgar/abs/ten_d.py` still ran on BeautifulSoup.

THE CORPUS is nineteen real 10-D primary documents in
`tests/fixtures/ten_d/`, harvested across 2006, 2010, 2015, 2019, 2023 and
2025 -- CMBS trusts, auto lease and auto receivables trusts, an RMBS trust and
a structured-products trust. The spread is the point: the modern SEC cover page
(2019 onward) is the only era whose "Central Index Key Number of issuing
entity" labels the regexes match at all, and the 2006-2015 documents are the
ones that must keep returning `None` rather than half an entity.

The filing is stubbed rather than fetched. `TenD` reads exactly one thing from
it -- `filing.html()` -- so a stub isolates the parse from attachment
resolution and lets the whole corpus run in milliseconds.

WHAT THE PORT HAS TO GET RIGHT:

  * `soup.get_text(separator='\n')` -- bs4's separator form with NO strip,
    joined with a NEWLINE. Every entity regex in the file runs against that
    string, and several of them (`[^\(]+?` for the name) depend on the
    newlines being there. `text_content()` joins with nothing, which glues a
    label to the value that follows it and every match is lost.
  * `header_row.get_text(separator=' ')` for "title of class", and
    `cells[0].get_text(strip=True)` for each class name -- the second of
    bs4's three text behaviours, strip each and join with NOTHING.
  * `table.find('tr')` is the first `<tr>` ANYWHERE in the table, not its
    first child, and `table.find_all('tr')` is recursive, so an inner table's
    rows belong to the outer table too.
  * bs4's `get_text()` leaves `<script>`, `<style>` and `<template>` text out;
    `itertext()` puts it in. On a filer-generated cover page an inline
    stylesheet sits before the header text, so the whole entity block would be
    read out of CSS.

MUTATION PROBE, 2026-08-24: 19 mistranslations, 17 killed. Both survivors
change only the SEPARATOR the document text is joined with -- a space instead
of a newline, or stripping each chunk first -- and both are equivalent mutants,
provably rather than by inspection. Every one of the eight regexes that
consumes that string spells its gaps as `[:\s]*`, `\s*`, `\s+` or the negated
class `[^\(]+?`; none anchors on `^` or `$`, none is compiled with
`re.MULTILINE`, and every captured name is passed through
`' '.join(name.split())` before it is used. Any whitespace separator therefore
gives identical results. That stops being true the moment a regex here becomes
line-anchored.

The nineteen real filings killed 11 of the 19 on their own. Five more inputs
were written only after a first probe round left the mutant alive: a `<style>`
whose TAIL is the header word, one whose TAIL is the class name, a `<script>`
whose TAIL is the CIK line, a `<tr>` holding text but no cells (an lxml element
with no ELEMENT children is FALSY, so `if header_row` would skip the table),
and a class row whose only `<td>` is a descendant rather than a child.
"""
import json
import pathlib

import pytest

from edgar.abs.ten_d import TenD

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "ten_d_baseline.json"
CORPUS = FIX / "ten_d"


class StubFiling:
    """The whole of what `TenD` reads from a filing."""

    form = "10-D"
    company = "STUB TRUST"
    accession_number = "0000000000-00-000000"
    filing_date = None

    def __init__(self, html):
        self._html = html

    def html(self):
        return self._html


_MODERN_HEADER = """
<p>Central Index Key Number of issuing entity: 0001888524</p>
<p>ACME 2025-1 Trust</p>
<p>(Exact name of issuing entity as specified in its charter)</p>
<p>Commission File Number of issuing entity: 333-123456-01</p>
<p>Central Index Key Number of depositor: 0000876543</p>
<p>Acme Depositor LLC</p>
<p>(Exact name of depositor as specified in its charter)</p>
<p>Central Index Key Number of sponsor (if applicable): 0000112233</p>
<p>Acme Sponsor Bank</p>
<p>(Exact name of sponsor as specified in its charter)</p>
<p>For the monthly distribution period from: October 21, 2025 to November 18, 2025</p>
"""

_CLASS_TABLE = (
    "<table>"
    "<tr><th>Title of Class</th><th>Name of Exchange</th></tr>"
    "<tr><td>Class A-1</td><td>NYSE</td></tr>"
    "<tr><td>Class A-2</td><td>NYSE</td></tr>"
    "</table>"
)

EDGE = {
    # --- degenerate ---------------------------------------------------------
    "empty": "",
    "whitespace": "   \n\t  ",
    "no-header-no-table": "<html><body><p>Nothing to see.</p></body></html>",
    "header-only": f"<html><body>{_MODERN_HEADER}</body></html>",
    "table-only": f"<html><body>{_CLASS_TABLE}</body></html>",
    "header-and-table": f"<html><body>{_MODERN_HEADER}{_CLASS_TABLE}</body></html>",
    # --- fragment rooting ---------------------------------------------------
    # The document IS the table. `.//table` finds nothing here.
    "table-is-the-root": _CLASS_TABLE,
    # --- get_text(separator='\n') on the whole document ----------------------
    # Every entity regex runs against this string. Joining with nothing glues
    # the label to the CIK and to the name that follows.
    "label-and-value-in-separate-cells": (
        "<html><body><table>"
        "<tr><td>Central Index Key Number of issuing entity:</td><td>0001888524</td></tr>"
        "<tr><td>ACME 2025-1 Trust</td></tr>"
        "<tr><td>(Exact name of issuing entity as specified in its charter)</td></tr>"
        "</table></body></html>"
    ),
    "value-split-across-inline-tags": (
        "<html><body><p>Central Index Key Number of depositor: <b>000</b><b>876543</b></p>"
        "<p>Acme <i>Depositor</i> LLC</p>"
        "<p>(Exact name of depositor as specified in its charter)</p></body></html>"
    ),
    # bs4 never saw <style>/<script> text; lxml does, and the cover page's
    # stylesheet comes FIRST, so a CIK written into CSS would win.
    "stylesheet-names-another-entity": (
        "<html><head><style>.x{content:'Central Index Key Number of issuing entity: 0000000001 "
        "GHOST TRUST (Exact name of issuing entity'}</style></head><body>"
        f"{_MODERN_HEADER}</body></html>"
    ),
    "script-names-another-entity": (
        "<html><head><script>var s='Central Index Key Number of depositor: 0000000002 "
        "GHOST LLC (Exact name of depositor';</script></head><body>"
        f"{_MODERN_HEADER}</body></html>"
    ),
    # bs4's Comment subclasses str but get_text() still excluded it.
    "comment-interrupts-the-name": (
        "<html><body><p>Central Index Key Number of issuing entity: 0001888524</p>"
        "<p>ACME <!-- filer note --> 2025-1 Trust</p>"
        "<p>(Exact name of issuing entity as specified in its charter)</p></body></html>"
    ),
    # --- the class table: find('tr') and the header read ----------------------
    "class-table-header-in-a-thead": (
        "<table><thead><tr><th>Title of Class</th></tr></thead>"
        "<tbody><tr><td>Class A-1</td></tr><tr><td>Class A-2</td></tr></tbody></table>"
    ),
    "class-table-header-split-across-tags": (
        "<table><tr><th><font>Title</font><font>of</font><font>Class</font></th></tr>"
        "<tr><td>Class A-1</td></tr></table>"
    ),
    "class-table-header-has-a-style": (
        "<table><tr><th>Title of Class<style>.a{color:red}</style></th></tr>"
        "<tr><td>Class B-1</td></tr></table>"
    ),
    # cells[0].get_text(strip=True) joins with NOTHING.
    "class-name-split-across-tags": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td>Class <b>A</b>-1</td></tr></table>"
    ),
    "class-name-padded-with-whitespace": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td>\n   Class A-9   \n</td></tr></table>"
    ),
    "class-name-has-a-comment": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td>Class <!-- x --> C-1</td></tr></table>"
    ),
    "class-name-has-a-script": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td>Class D-1<script>var v='Class Z-9';</script></td></tr></table>"
    ),
    "duplicate-class-names": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td>Class A-1</td></tr><tr><td>Class A-1</td></tr>"
        "<tr><td>Class A-2</td></tr></table>"
    ),
    "class-rows-use-th-not-td": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><th>Class A-1</th></tr></table>"
    ),
    # An inner table's rows are the outer table's rows too, under find_all.
    "nested-table-inside-a-class-row": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td><table><tr><td>Inner Class</td></tr></table></td></tr>"
        "<tr><td>Class A-1</td></tr></table>"
    ),
    # The first table does not match; the second is the class table.
    "second-table-is-the-class-table": (
        "<html><body><table><tr><th>Something Else</th></tr><tr><td>x</td></tr></table>"
        f"{_CLASS_TABLE}</body></html>"
    ),
    # A table whose FIRST row is not its header row -- find('tr') is the first
    # <tr> anywhere, so a stray row above the header hides it.
    "stray-row-above-the-header": (
        "<table><tr><td>Filed pursuant to Rule 424</td></tr>"
        "<tr><th>Title of Class</th></tr><tr><td>Class A-1</td></tr></table>"
    ),
    # The DISCRIMINATING text is the style block's TAIL, not the cell's own
    # text. strip_elements(..., with_tail=True) would delete it.
    "style-tail-carries-the-class-header": (
        "<table><tr><th><style>.a{color:red}</style>Title of Class</th></tr>"
        "<tr><td>Class A-1</td></tr></table>"
    ),
    "style-tail-carries-the-class-name": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><td><style>.a{color:red}</style>Class E-1</td></tr></table>"
    ),
    "script-tail-carries-the-entity-cik": (
        "<html><body><p><script>var x=1;</script>Central Index Key Number of issuing entity: 0001888524</p>"
        "<p>TAIL TRUST</p><p>(Exact name of issuing entity as specified in its charter)</p></body></html>"
    ),
    # A <tr> holding text but no cells. An lxml element with no ELEMENT
    # children is FALSY, so `if header_row` skips the whole table.
    "header-row-has-text-but-no-cells": (
        "<table><tr>Title of Class</tr><tr><td>Class A-1</td></tr></table>"
    ),
    # The row's only <td> is a descendant, not a child. bs4's find_all was
    # recursive; ElementTree's findall/xpath('td') is not.
    "class-row-td-nested-in-a-div": (
        "<table><tr><th>Title of Class</th></tr>"
        "<tr><div><td>Divided Class</td></div></tr></table>"
    ),
    # --- parser leniency, encoding and depth ----------------------------------
    "unclosed-tags": "<table><tr><th>Title of Class<tr><td>Class A-1<tr><td>Class A-2",
    "encoding-declaration": (
        "<?xml version='1.0' encoding='ASCII'?><html><body>"
        "<p>Central Index Key Number of issuing entity: 0001888524</p>"
        "<p>ACME — 2025-1 Trust</p>"
        "<p>(Exact name of issuing entity as specified in its charter)</p>"
        f"{_CLASS_TABLE}</body></html>"
    ),
    # 300 nested <div>s -- libxml2 drops below depth 256 without huge_tree.
    # See edgartools-xqvr.
    "nested-300-deep": "<div>" * 300 + f"{_MODERN_HEADER}{_CLASS_TABLE}" + "</div>" * 300,
}


# The one place the port deliberately changes the answer. `html.parser` does not
# auto-close `<th>`/`<td>`/`<tr>`, so it nests a tag-soup table inside itself and
# the first class cell swallows the second row's text; libxml2 in recover mode
# closes them and reads the two classes the filer wrote. The new answer is the
# right one and no SEC 10-D looks like this, so it is recorded rather than
# preserved -- keeping the bs4 value in the baseline keeps that a faithful
# record of what BeautifulSoup did.
DIVERGES_FROM_BS4 = {
    "EDGE-unclosed-tags": {
        "issuing_entity": None,
        "depositor": None,
        "sponsors": [],
        "distribution_period": None,
        "security_classes": ["Class A-1", "Class A-2"],
    },
}


def _corpus() -> dict:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(CORPUS.glob("*.html"))}


def _cases() -> dict:
    cases = dict(_corpus())
    cases.update({f"EDGE-{k}": v for k, v in EDGE.items()})
    return cases


def _run(html: str) -> dict:
    """Every parsed field, in a form JSON can hold."""
    t = TenD(StubFiling(html))
    ie, dep = t.issuing_entity, t.depositor
    period = t.distribution_period
    return {
        "issuing_entity": None if ie is None else [ie.name, ie.cik, ie.file_number],
        "depositor": None if dep is None else [dep.name, dep.cik, dep.file_number],
        "sponsors": [[s.name, s.cik, s.file_number] for s in t.sponsors],
        "distribution_period": None if period is None else [
            period.start_date.isoformat() if period.start_date else None,
            period.end_date.isoformat() if period.end_date else None,
        ],
        "security_classes": t.security_classes,
    }


@pytest.mark.parametrize("name", list(_cases()))
def test_ten_d_parsing_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    assert _run(_cases()[name]) == DIVERGES_FROM_BS4.get(name, baseline[name])


@pytest.mark.parametrize("name", list(DIVERGES_FROM_BS4))
def test_recorded_divergences_really_diverge(name):
    """A divergence that stopped diverging is an entry to delete, not to keep."""
    baseline = json.loads(BASELINE.read_text())
    assert DIVERGES_FROM_BS4[name] != baseline[name]


def test_baseline_covers_every_case():
    assert set(json.loads(BASELINE.read_text())) == set(_cases())
