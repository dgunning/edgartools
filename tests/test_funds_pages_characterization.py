"""Pin `_resolve_company_cik` and `_parse_series_table` before the lxml port.

edgartools-07lk.11.11. Both read browse-edgar pages that only exist over the
network, so the corpus is committed as real HTML rather than fingerprinted: the
local HTTP cache serves before a cassette does, so a cassette-driven gate would
prove nothing about CI.

WHAT ACTUALLY CONSUMES THESE. Instrumenting all four bs4 surfaces in
`edgar/funds/data.py` and driving every public fund entry point shows these two
firing for `find_fund(<class id>)` -> `get_fund_object`, which resolves the
identifier to a company CIK and then reads that company's series listing.

THE TRAP THAT DOMINATES THIS PAIR is `.text`. On a BeautifulSoup Tag it is
`get_text()` -- every string in the subtree. On an lxml element it is the text
BEFORE THE FIRST CHILD and nothing else, so `tag.text.split('CIK')[0]` silently
returns a prefix instead of the name the moment a filer's markup puts the name
in a child tag. It raises nothing; it just returns less.
"""
import json
import pathlib

import pytest

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
PAGES = REPO / "tests" / "fixtures" / "funds_pages"
BASELINE = REPO / "tests" / "fixtures" / "funds_pages_baseline.json"


# --- hand-written inputs, one per way the two spellings can disagree ---------
RESOLVE_EDGE = {
    "no-company-span": "<html><body><p>No matching companies.</p></body></html>",
    # An lxml element with no ELEMENT children is falsy, so `if not tag` reads a
    # text-only span as "not found". bs4's Tag was truthy either way.
    "span-with-text-but-no-link": (
        "<span class='companyName'>Kinetics Mutual Funds Inc CIK#0001083387</span>"
    ),
    # `.text` on lxml stops at the first child.
    "name-split-across-child-tags": (
        "<span class='companyName'>Kinetics <b>Mutual</b> Funds Inc "
        "<a href='/x'>0001083387 (see all company filings)</a></span>"
    ),
    # bs4 matched class_= against the multi-valued class list.
    "companyName-among-several-classes": (
        "<span class='big companyName highlight'>Acme Funds "
        "<a href='/x'>0000012345 (see all)</a></span>"
    ),
    # find('a') was recursive.
    "link-nested-inside-bold": (
        "<span class='companyName'>Acme Funds "
        "<b><a href='/x'>0000012345 (see all)</a></b></span>"
    ),
    # ... and the link's own text can be split too.
    "link-text-split-across-tags": (
        "<span class='companyName'>Acme Funds <a href='/x'>"
        "<span>0000012345</span> (see all)</a></span>"
    ),
    "comment-inside-the-span": (
        "<span class='companyName'>Acme <!-- filer note --> Funds "
        "<a href='/x'>0000012345 (see all)</a></span>"
    ),
    "second-span-is-the-company-one": (
        "<span class='otherName'>Ignore me</span>"
        "<span class='companyName'>Acme Funds <a href='/x'>0000012345 (see all)</a></span>"
    ),
    "no-cik-marker-in-the-text": (
        "<span class='companyName'>Acme Funds <a href='/x'>0000012345 (see all)</a></span>"
    ),
    # bs4 left <style>/<script> text out of get_text() and lxml puts it in --
    # and the text FOLLOWING one is an ordinary string that must survive, which
    # is what `with_tail=False` is for.
    "style-inside-the-span": (
        "<span class='companyName'>Acme <style>.x{color:red}</style>Funds "
        "<a href='/x'>0000012345 (see all)</a></span>"
    ),
    "cik-link-split-so-lxml-text-is-empty": (
        "<span class='companyName'>Acme Funds "
        "<a href='/x'><b>0000</b>012345 (see all)</a></span>"
    ),
}

_ROW = ("<tr><td></td><td><a href='/s'>S000009184</a></td>"
        "<td><a href='/n'>Kinetics Paradigm Fund</a></td></tr>")
_CLASS_ROW = ("<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
              "<td>No Load Class</td><td>WWNPX</td></tr>")

SERIES_EDGE = {
    "no-tables": "<html><body><p>Nothing here.</p></body></html>",
    "empty-table": "<table></table>",
    "company-series-and-class": (
        "<table><tr><td><a href='/c'>0001083387</a></td>"
        "<td><a href='/n'>KINETICS MUTUAL FUNDS INC</a></td></tr>"
        + _ROW + _CLASS_ROW + "</table>"
    ),
    # find_all('td') was recursive, so a nested table shifts the cell count and
    # changes which branch the row takes.
    "nested-table-shifts-the-cell-count": (
        "<table>" + _ROW.replace(
            "<td><a href='/n'>Kinetics Paradigm Fund</a></td>",
            "<td><table><tr><td>x</td></tr></table>"
            "<a href='/n'>Kinetics Paradigm Fund</a></td>")
        + "</table>"
    ),
    # a.text: lxml stops at the first child.
    "series-link-text-split-across-tags": (
        "<table><tr><td></td><td><a href='/s'><b>S000</b>009184</a></td>"
        "<td><a href='/n'>Kinetics Paradigm Fund</a></td></tr></table>"
    ),
    "series-name-split-across-tags": (
        "<table><tr><td></td><td><a href='/s'>S000009184</a></td>"
        "<td><a href='/n'>Kinetics <i>Paradigm</i> Fund</a></td></tr></table>"
    ),
    # no <a> in the name cell -> get_text(strip=True), a different code path
    "series-name-without-a-link": (
        "<table><tr><td></td><td><a href='/s'>S000009184</a></td>"
        "<td>  Kinetics Paradigm Fund  </td></tr></table>"
    ),
    "class-name-and-ticker-split-across-tags": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No <b>Load</b> Class</td><td><b>WW</b>NPX</td></tr></table>"
    ),
    "class-row-with-four-cells-has-no-ticker": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No Load Class</td></tr></table>"
    ),
    "class-row-before-any-series-is-dropped": (
        "<table>" + _CLASS_ROW + "</table>"
    ),
    "row-with-too-many-cells-is-skipped": (
        "<table><tr>" + "<td>x</td>" * 11 + "</tr>" + _ROW + "</table>"
    ),
    "cik-that-does-not-match-the-pattern": (
        "<table><tr><td><a href='/c'>1083387</a></td>"
        "<td><a href='/n'>KINETICS</a></td></tr>" + _ROW + "</table>"
    ),
    "comment-inside-a-cell": (
        "<table><tr><td></td><td><a href='/s'>S000<!-- x -->009184</a></td>"
        "<td><a href='/n'>Kinetics Paradigm Fund</a></td></tr></table>"
    ),
    "second-table-is-ignored": (
        "<table><tr><td></td><td><a href='/s'>S000000001</a></td>"
        "<td><a href='/n'>First Table Series</a></td></tr></table>"
        "<table>" + _ROW + "</table>"
    ),
    "unclosed-tags": (
        "<table><tr><td><td><a href='/s'>S000009184</a><td>"
        "<a href='/n'>Kinetics Paradigm Fund</a>"
    ),
    "th-cells-are-not-td-cells": (
        "<table><tr><th></th><th><a href='/s'>S000009184</a></th>"
        "<th><a href='/n'>Kinetics Paradigm Fund</a></th></tr>" + _ROW + "</table>"
    ),
    "nested-300-deep": "<div>" * 300 + (
        "<table>" + _ROW + _CLASS_ROW + "</table>") + "</div>" * 300,
    # --- inputs that exist to kill a specific mistranslation ------------------
    # `a.text` in lxml is the text BEFORE the first child, so a link whose id is
    # split across tags reads as empty and the row stops matching its pattern.
    "company-link-split-so-lxml-text-is-empty": (
        "<table><tr><td><a href='/c'><b>0001</b>083387</a></td>"
        "<td><a href='/n'>KINETICS MUTUAL FUNDS INC</a></td></tr>" + _ROW + "</table>"
    ),
    "class-link-split-so-lxml-text-is-empty": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'><b>C000</b>032628</a></td>"
        "<td>No Load Class</td><td>WWNPX</td></tr></table>"
    ),
    # `get_text(strip=True)` strips each string and joins with NOTHING, so bs4
    # answered "WWNPX" where `text_content().strip()` answers "WW NPX". The
    # whitespace between the tags is the whole point of these three.
    "ticker-split-with-whitespace-between-the-tags": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No Load Class</td><td><b>WW</b> NPX</td></tr></table>"
    ),
    "series-name-split-and-without-a-link": (
        "<table><tr><td></td><td><a href='/s'>S000009184</a></td>"
        "<td>Kinetics <i>Paradigm</i> Fund</td></tr></table>"
    ),
    "company-name-split-and-without-a-link": (
        "<table><tr><td><a href='/c'>0001083387</a></td>"
        "<td>KINETICS <b>MUTUAL</b> FUNDS</td></tr>" + _ROW + "</table>"
    ),
    # A comment interrupts the matched string rather than sitting beside it:
    # removing it merges the two strings either side, so the joined-with-nothing
    # answer gains a space it never had.
    "comment-inside-a-class-name-cell": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No <!-- footnote --> Load Class</td><td>WWNPX</td></tr></table>"
    ),
    # bs4 gave a string its own class from its DIRECT parent only, so the <b>
    # inside a <template> still contributed text. Carrying the container flag
    # down the subtree instead would silently drop it.
    "template-wrapping-an-element-with-text": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No <template><b>hidden</b></template> Load Class</td>"
        "<td>WWNPX</td></tr></table>"
    ),
    "style-inside-a-class-name-cell": (
        "<table>" + _ROW +
        "<tr><td></td><td></td><td><a href='/c'>C000032628</a></td>"
        "<td>No <style>.x{color:red}</style>Load Class</td><td>WWNPX</td></tr></table>"
    ),
}


def _corpus(prefix: str) -> dict:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(PAGES.glob(f"{prefix}*.html"))}


def _run_resolve(html: str):
    """`_resolve_company_cik` with the download stubbed out."""
    from unittest.mock import patch

    import edgar.funds.data as D
    with patch.object(D, "download_text", return_value=html):
        result = D._resolve_company_cik("IGNORED")
    return list(result) if result is not None else None


def _run_series(html: str):
    import edgar.funds.data as D
    cik, name, series = D._parse_series_table(html)
    return [cik, name, series]


def _resolve_cases() -> dict:
    cases = dict(_corpus("resolve-"))
    cases.update({f"EDGE-{k}": v for k, v in RESOLVE_EDGE.items()})
    return cases


def _series_cases() -> dict:
    cases = dict(_corpus("series-"))
    cases.update({f"EDGE-{k}": v for k, v in SERIES_EDGE.items()})
    return cases


# The port deliberately changes the answer here. Filled in by the port commit;
# an empty dict means it changed nothing.
DIVERGES_FROM_BS4 = {}


@pytest.mark.parametrize("name", list(_resolve_cases()))
def test_resolve_company_cik_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    key = f"RESOLVE-{name}"
    assert key in baseline, f"{key} is missing from the baseline -- recapture it"
    assert _run_resolve(_resolve_cases()[name]) == DIVERGES_FROM_BS4.get(key, baseline[key])


@pytest.mark.parametrize("name", list(_series_cases()))
def test_parse_series_table_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    key = f"SERIES-{name}"
    assert key in baseline, f"{key} is missing from the baseline -- recapture it"
    assert _run_series(_series_cases()[name]) == DIVERGES_FROM_BS4.get(key, baseline[key])


@pytest.mark.parametrize("key", list(DIVERGES_FROM_BS4))
def test_recorded_divergences_really_diverge(key):
    """A divergence that stopped diverging is an entry to delete, not to keep."""
    baseline = json.loads(BASELINE.read_text())
    assert DIVERGES_FROM_BS4[key] != baseline[key]


def test_baseline_covers_every_case():
    expected = ({f"RESOLVE-{k}" for k in _resolve_cases()}
                | {f"SERIES-{k}" for k in _series_cases()})
    assert set(json.loads(BASELINE.read_text())) == expected


def test_the_corpus_is_still_there():
    """A fixture that goes missing must fail loudly, not shrink the gate."""
    assert len(_corpus("resolve-")) == 6
    assert len(_corpus("series-")) == 6
