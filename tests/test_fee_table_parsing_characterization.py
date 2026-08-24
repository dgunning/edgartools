r"""Characterization of the fee-table parser's bs4 -> lxml port
(edgartools-07lk.11.9.2).

`fee_table_parsing_baseline.json` is what `_parse_fee_table_html()` and
`_parse_inline_fee_table()` returned for each input below, captured while
`edgar/offerings/prospectus/_fee_table/parsing.py` still ran on BeautifulSoup.

THE CORPUS IS THE HTML THE PARSERS ACTUALLY RECEIVED. The eighteen files in
`tests/fixtures/fee_tables/` were harvested by instrumenting
`extract_registration_fee_table()` over every accession the existing fee-table
verification uses, and each is stored under the accession that produced it:

  * fourteen `_exhibit` files -- EX-FILING FEES (Exhibit 107) attachments,
    2022-2025, including TWO genuine inline-XBRL exhibits that open with
    `<?xml version='1.0' encoding='ASCII'?>` and carry `ix:`, `link:`,
    `xbrli:` and `xbrldi:` prefixed elements. Those two are the reason the
    original wrapped its parse in an `XMLParsedAsHTMLWarning` suppression, and
    they are why the port must hand lxml BYTES: lxml refuses a `str` with an
    encoding declaration outright.
  * four `_inline` files -- whole pre-EX-107 registration statements,
    2018-2021, 200KB to 570KB each. `_parse_inline_fee_table` runs
    `soup.get_text(' ')` across the ENTIRE document to look for deferral
    markers, which makes it the single riskiest call in the file, and only a
    real multi-hundred-KB filing exercises it.

WHAT THE PORT HAS TO GET RIGHT. This module uses two of bs4's three text
behaviours, and neither is `text_content()`:

  * `get_text(separator=' ')` -- NO strip. Every string is joined with a
    space, whitespace-only ones included. `_table_text` and the deferral-marker
    scan use this. `text_content()` joins with nothing, so a header typeset as
    `<font>Security</font><font>Type</font>` collapses to "securitytype" and
    stops matching "security type" -- which is the ONLY thing `_find_fee_table`
    looks for, so the whole extraction returns empty.
  * `get_text(separator=' ', strip=True)` -- strip each string, drop the
    empties, join with a space. The per-cell reads use this.

Plus the constructs shared with every other file in this phase: bs4's
`get_text()` leaves `<script>`, `<style>` and `<template>` text out where
`text_content()` and `itertext()` put it in; `find_all` searches
descendant-or-self once the document IS the element; and `find_all(['td','th'])`
returns ONE list in document order, not the tds followed by the ths.

MUTATION PROBE, 2026-08-24: 20 mistranslations, 18 killed. The two survivors
are EQUIVALENT mutants, and provably so rather than by inspection:

  * making `_all_text` strip each chunk and drop the empties. Both call sites
    pass the result through `re.sub(r'\s+', ' ', ...)`, which collapses the
    runs of spaces the unstripped join leaves behind; `_table_text` then
    `.strip()`s, and the deferral scan only ever asks `marker in doc_text`, so
    a leading or trailing space cannot change an answer.
  * making `_cell_text` keep the chunks that strip to empty. Same argument one
    level down: every consumer normalises with the same `re.sub`, and
    `_join_dollar_cells` `.strip()`s each cell before anything reads it.

Both stop being equivalent the moment a consumer compares cell text exactly.

The eighteen real files killed 9 of the 20 on their own. The other 9 needed an
edge input, and six of those were written only after a first probe round left
the mutant alive -- the shapes that matter here are a style block whose TAIL is
the amount, an inner table inside the Total row's label cell, a `$` cell
followed by a `<th>` holding the number, and rows inside a `<tbody>`.
"""
import json
import pathlib

import pytest

from edgar.offerings.prospectus._fee_table.parsing import (
    _parse_fee_table_html,
    _parse_inline_fee_table,
)

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "fee_table_parsing_baseline.json"
CORPUS = FIX / "fee_tables"


# The form of the filing each `_inline` fixture came from. It is an input to
# `_parse_inline_fee_table`, which treats an ASR as deferred when it finds no
# dollar amount at all, so running the corpus under the wrong form would mask
# the document-wide marker scan.
CORPUS_FORMS = {
    "0001047469-18-007293_inline": "S-3",       # PLUG POWER INC, 2018-11-16
    "0001104659-20-040593_inline": "S-3",       # KINGOLD JEWELRY, INC., 2020-03-30
    "0001193125-20-310765_inline": "S-3ASR",    # SCHWAB CHARLES CORP, 2020-12-04
    "0001654954-21-007440_inline": "S-3/A",     # DYNATRONICS CORP, 2021-06-30
}


def _corpus() -> dict:
    """fixture name -> (parser kind, form, html)."""
    out = {}
    for path in sorted(CORPUS.glob("*.html")):
        inline = path.stem.endswith("_inline")
        kind = "inline" if inline else "exhibit"
        form = CORPUS_FORMS[path.stem] if inline else None
        out[path.stem] = (kind, form, path.read_text(encoding="utf-8"))
    return out


def _fee_row(cells, tag="td"):
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def _fee_table(rows, header="Security Type"):
    """The minimum shape `_find_fee_table` will accept, plus `rows`."""
    return (
        "<table>"
        + _fee_row([header, "Amount Registered", "Fee Rate", "Amount of Registration Fee"], tag="th")
        + "".join(rows)
        + "</table>"
    )


_EQUITY = _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00", "$10,000,000", "$0.00014760", "$1,476.00"])

EDGE = {
    # --- degenerate --------------------------------------------------------
    "empty": "",
    "whitespace": "   \n\t  ",
    "no-table": "<html><body><p>No fee table in this exhibit.</p></body></html>",
    "table-without-the-header-words": "<table><tr><td>Something else</td></tr></table>",
    # --- fragment rooting --------------------------------------------------
    # The document IS the table. `.//table` finds nothing here.
    "table-is-the-root": _fee_table([_EQUITY]),
    # --- separator=' ' with NO strip (the _table_text read) -----------------
    # bs4 joins every string with a space, so these two <font>s read
    # "Security Type". text_content() glues them into "SecurityType" and
    # _find_fee_table never matches.
    "header-split-across-inline-tags": _fee_table([_EQUITY], header="<font>Security</font><font>Type</font>"),
    "header-split-by-a-nonbreaking-space": _fee_table([_EQUITY], header="Security\xa0Type"),
    "header-split-across-nested-spans": _fee_table(
        [_EQUITY], header="<span><b>Security</b></span><span><i>Type</i></span>"
    ),
    # bs4's get_text() left <script>/<style>/<template> out; lxml puts them in.
    "header-table-has-a-script": _fee_table([_EQUITY], header="Security Type<script>var x='carry forward securities';</script>"),
    "header-table-has-a-style": _fee_table([_EQUITY], header="Security Type<style>.c{content:'Fees Previously Paid'}</style>"),
    # A <style> block in a DIFFERENT table that would make it match first.
    "earlier-table-matches-only-via-its-style": (
        "<html><body>"
        "<table><tr><td>Cover page<style>.x{content:'security type'}</style></td></tr></table>"
        + _fee_table([_EQUITY])
        + "</body></html>"
    ),
    # --- the per-cell read: separator=' ', strip=True ------------------------
    "cell-text-split-across-fonts": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                  "<font>$10,000,</font><font>000</font>", "$0.00014760", "$1,476.00"])
    ]),
    "cell-text-padded-with-whitespace": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                  "\n   $10,000,000   \n", "$0.00014760", "$1,476.00"])
    ]),
    # The dollar sign in a cell of its own -- what _join_dollar_cells exists for.
    "dollar-sign-in-its-own-cell": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$", "10.00", "$", "10,000,000", "$", "1,476.00"])
    ]),
    "cell-has-a-comment-inside-a-number": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                  "$10,000<!-- sep -->,000", "$0.00014760", "$1,476.00"])
    ]),
    "cell-has-a-script": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                  "$10,000,000<script>var v='$99,999,999';</script>", "$0.00014760", "$1,476.00"])
    ]),
    # --- find_all(['td','th']) is ONE list in DOCUMENT order ------------------
    # A <th> row label followed by <td> figures. Collecting the tds and then the
    # ths puts the label last and every column shifts.
    "row-mixes-th-then-td": _fee_table([
        "<tr><th>Equity</th><td>Common Stock</td><td>1,000,000</td><td>$10.00</td>"
        "<td>$10,000,000</td><td>$0.00014760</td><td>$1,476.00</td></tr>"
    ]),
    "row-mixes-td-then-th": _fee_table([
        "<tr><td>Equity</td><td>Common Stock</td><td>1,000,000</td><td>$10.00</td>"
        "<td>$10,000,000</td><td>$0.00014760</td><th>$1,476.00</th></tr>"
    ]),
    # --- rows, totals and sections ------------------------------------------
    "carry-forward-section": _fee_table([
        _fee_row(["Newly Registered Securities"]),
        _EQUITY,
        _fee_row(["Carry Forward Securities"]),
        _fee_row(["Equity", "Common Stock", "500,000", "", "$5,000,000", "", ""]),
        _fee_row(["Total Offering Amounts", "", "$15,000,000", "", "$1,476.00"]),
    ]),
    "totals-row": _fee_table([
        _EQUITY,
        _fee_row(["Total Offering Amounts", "", "$10,000,000", "", "$1,476.00"]),
        _fee_row(["Total Fees Previously Paid", "", "", "", "$100.00"]),
        _fee_row(["Net Fee Due", "", "", "", "$1,376.00"]),
    ]),
    # find_all('tr') is recursive: an inner table's rows are the outer's rows too.
    "nested-table-inside-a-cell": _fee_table([
        "<tr><td><table><tr><td>Equity</td><td>$99,999,999</td></tr></table></td>"
        "<td>Common Stock</td><td>1,000,000</td><td>$10.00</td>"
        "<td>$10,000,000</td><td>$0.00014760</td><td>$1,476.00</td></tr>"
    ]),
    # --- the legacy fallback branch of _find_fee_table ------------------------
    "legacy-registration-fee-header": (
        "<table><tr><th>Title of Securities</th><th>Amount Being Registered</th>"
        "<th>Proposed Maximum Aggregate Offering Price</th>"
        "<th>Amount of Registration Fee</th></tr>"
        "<tr><td>Common Stock</td><td>1,000,000</td><td>$10,000,000</td><td>$1,476.00</td></tr></table>"
    ),
    # The DISCRIMINATING text is the style block's TAIL, not the cell's own
    # text. strip_elements(..., with_tail=True) would delete the amount.
    "amount-follows-a-style-block": _fee_table([
        _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                  "<style>.a{color:red}</style>$10,000,000", "$0.00014760", "$1,476.00"])
    ]),
    # An inner table inside the Total row's label cell. find_all(['td','th'])
    # was recursive, so the inner cell lands at index 1 and shifts every column.
    "nested-table-inside-the-total-row": _fee_table([
        _EQUITY,
        "<tr><td>Total Offering Amounts<table><tr><td>$99,999,999</td></tr></table></td>"
        "<td></td><td>$10,000,000</td><td></td><td>$1,476.00</td></tr>"
    ]),
    # 300 nested <div>s -- see edgartools-xqvr.
    "table-nested-300-deep": "<div>" * 300 + _fee_table([_EQUITY]) + "</div>" * 300,
    # --- parser leniency and encoding -----------------------------------------
    "unclosed-tags": "<table><tr><th>Security Type<th>Amount<tr><td>Equity<td>$10,000,000",
    # An XML declaration naming ASCII, with a character ASCII cannot hold. lxml
    # would honour the declaration and mangle it; the parser's own encoding must win.
    "xml-declaration-says-ascii-but-text-is-not": (
        "<?xml version='1.0' encoding='ASCII'?><html><body>"
        + _fee_table([
            _fee_row(["Equity", "Common Stock — Class A", "1,000,000", "$10.00",
                      "$10,000,000", "$0.00014760", "$1,476.00"])
        ])
        + "</body></html>"
    ),
    "ixbrl-namespaced-wrapper": (
        "<?xml version='1.0' encoding='ASCII'?>"
        "<html xmlns:ix='http://www.xbrl.org/2013/inlineXBRL'><body>"
        "<ix:header><ix:hidden><ix:nonNumeric name='dei:EntityRegistrantName'>ACME"
        "</ix:nonNumeric></ix:hidden></ix:header>"
        + _fee_table([
            _fee_row(["Equity", "Common Stock", "1,000,000", "$10.00",
                      "<ix:nonFraction>$10,000,000</ix:nonFraction>", "$0.00014760", "$1,476.00"])
        ])
        + "</body></html>"
    ),
}

# `_parse_inline_fee_table` reads the whole document for deferral markers, so it
# gets its own inputs.
EDGE_INLINE = {
    # Each entry is (form, html). The form matters: an ASR with no dollar
    # amount anywhere is deferred by definition, which would mask the
    # document-wide marker scan, so all but one of these are plain S-3s.
    "inline-empty": ("S-3", ""),
    "inline-no-table": ("S-3", "<html><body><p>Nothing here.</p></body></html>"),
    "inline-largest-dollar-wins": ("S-3", _fee_table([
        _fee_row(["Common Stock", "1,000,000", "$10.00", "$10,000,000", "$1,476.00"]),
        _fee_row(["Warrants", "500,000", "$2.00", "$1,000,000", "$147.60"]),
    ])),
    # No dollar amount anywhere -> an indeterminate Rule 457(r) shelf. The
    # marker is found by get_text(' ') over the WHOLE document, outside the
    # table -- reading only the fee table would miss it.
    "inline-deferral-marker-outside-the-table": ("S-3", (
        "<html><body>"
        + _fee_table([_fee_row(["Common Stock", "1,000,000", "", "", ""])])
        + "<p>Registration fees to be paid on a deferred basis pursuant to Rule 457(r).</p>"
        "</body></html>"
    )),
    "inline-no-marker-anywhere": ("S-3", (
        "<html><body>"
        + _fee_table([_fee_row(["Common Stock", "1,000,000", "", "", ""])])
        + "</body></html>"
    )),
    # An ASR is deferred whether or not the marker is present.
    "inline-asr-without-a-marker": ("S-3ASR", (
        "<html><body>"
        + _fee_table([_fee_row(["Common Stock", "1,000,000", "", "", ""])])
        + "</body></html>"
    )),
    # The marker split across inline tags. get_text(' ') keeps the words apart;
    # text_content() glues them and the marker stops matching.
    "inline-deferral-marker-split-across-tags": ("S-3", (
        "<html><body>"
        + _fee_table([_fee_row(["Common Stock", "1,000,000", "", "", ""])])
        + "<p><font>deferred</font><font>basis</font></p>"
        "</body></html>"
    )),
    # bs4 never saw <style> text. lxml does, and a stylesheet naming a marker
    # would flip an ordinary shelf to deferred.
    "inline-deferral-marker-only-in-a-style-block": ("S-3", (
        "<html><head><style>.x{content:'to be paid on a deferred basis'}</style></head><body>"
        + _fee_table([_fee_row(["Common Stock", "1,000,000", "", "", ""])])
        + "</body></html>"
    )),
    "inline-implausibly-large-amount": ("S-3", _fee_table([
        _fee_row(["Common Stock", "1,000,000", "$10.00", "$2,000,000,000,000", "$1,476.00"])
    ])),
    # A '$' cell followed by a <th> holding the number. find_all(['td','th'])
    # returned ONE list in document order, so _join_dollar_cells could stitch
    # them; collecting the tds and then the ths pulls them apart.
    "inline-dollar-cell-then-th-number": ("S-3",
        "<table>" + _fee_row(["Security Type", "Amount"], tag="th")
        + "<tr><th>$</th><td>25,000,000</td><td>Common Stock</td></tr></table>"),
    # Rows inside a <tbody> are not direct children of the <table>.
    "inline-rows-inside-a-tbody": ("S-3",
        "<table><thead>" + _fee_row(["Security Type", "Amount"], tag="th")
        + "</thead><tbody>" + _fee_row(["Common Stock", "$42,000,000"]) + "</tbody></table>"),
    # 300 nested <div>s. libxml2 discards below depth 256 unless huge_tree is
    # on; bs4's html.parser had no such limit. See edgartools-xqvr.
    "inline-table-nested-300-deep": ("S-3", "<div>" * 300 + _fee_table([
        _fee_row(["Common Stock", "1,000,000", "$10.00", "$77,000,000"])]) + "</div>" * 300),
}


def _run(kind: str, form, html: str):
    if kind == "inline":
        return _parse_inline_fee_table(html, form=form)
    return _parse_fee_table_html(html, exhibit_url="https://example.org/ex107.htm")


def _cases() -> dict:
    """name -> (kind, form, html), every input in one table."""
    cases = dict(_corpus())
    cases.update({f"EDGE-{k}": ("exhibit", None, v) for k, v in EDGE.items()})
    cases.update({f"EDGE-{k}": ("inline", form, v) for k, (form, v) in EDGE_INLINE.items()})
    return cases


@pytest.mark.parametrize("name", list(_cases()))
def test_fee_table_parsing_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    kind, form, html = _cases()[name]
    assert _run(kind, form, html) == baseline[name]


def test_baseline_covers_every_case():
    """A case dropped from the corpus must not sit unnoticed in the baseline."""
    assert set(json.loads(BASELINE.read_text())) == set(_cases())
