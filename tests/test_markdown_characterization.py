r"""Characterization of `edgar/markdown.py`'s bs4 -> lxml port
(edgartools-07lk.11.11).

WHY THIS FILE EXISTS AT ALL. The bead names
`tests/test_markdown_parity_ratchet.py` as the acceptance gate for this port.
It is not one. That ratchet compares `edgar.files.markdown.to_markdown`
(legacy) against `edgar.documents`' HTMLParser, which is what `Filing.markdown()`
runs; instrumenting `edgar.markdown.process_content`, `html_to_json` and
`create_markdown_table` across a full `measure_markdown()` run over the tracked
corpus records **zero** calls into this module. The ratchet would stay green
however badly this file were broken.

WHAT ACTUALLY CONSUMES IT. `edgar/xbrl/notes.py` calls `process_content` to
build the LLM-optimised text of a note -- `note.to_context()` and
`notes.to_markdown()` with `optimize_for_llm`. That is the RAG-facing surface
the bead is worried about, so the corpus is the sixteen real XBRL note
TextBlocks already tracked in `tests/fixtures/notes_html/` (2.3MB of Apple,
JPMorgan and Coca-Cola disclosures), and the golden is the rendered markdown
**in full**, one `.md` file per fixture, asserted character for character.
Committing the output rather than a fingerprint is deliberate: when this breaks,
the diff has to show which line of a disclosure changed, not merely that
something did.

WHAT THE PORT HAS TO GET RIGHT. Beyond the usual text behaviours, this file
does three things none of the earlier ports did:

  * **It MUTATES the tree.** `preprocess_currency_cells` and
    `preprocess_percent_cells` rewrite a cell's contents, bump its `colspan`,
    and delete the neighbouring cell. `next_cell.string = value` REPLACES every
    child with one string; `cell.decompose()` removes a tag and, because bs4
    has no notion of a tail, leaves the text around it untouched -- where
    lxml's `remove()` takes the tail with it.
  * **It deep-copies by re-parsing.** `html_to_json` does
    `BeautifulSoup(str(table_soup), 'html.parser')` to get a tree it can mutate
    without disturbing the caller's.
  * **It counts a parent's children the way bs4 did**, where a `Comment` is a
    `str` subclass and so counts as a text child rather than an element child.

`find_all('span', recursive=False)`, `find_parent('table')` and `element.name`
all appear too.
"""
import json
import pathlib

import pytest

from edgar.markdown import process_content

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
NOTES = FIX / "notes_html"
GOLDEN = FIX / "markdown_golden"
EDGE_BASELINE = FIX / "markdown_edge_baseline.json"


_TABLE = (
    "<table>"
    "<tr><th>Item</th><th>2024</th><th>2023</th></tr>"
    "<tr><td>Revenue</td><td>$1,000</td><td>$900</td></tr>"
    "<tr><td>Net income</td><td>$100</td><td>$90</td></tr>"
    "</table>"
)

EDGE = {
    # --- degenerate and non-HTML ---------------------------------------------
    "empty": "",
    "whitespace": "   \n\t  ",
    "plain-text-passthrough": "This is not HTML at all, just a sentence.",
    "text-that-mentions-a-tag": "See the <table> of contents for details.",
    "simple-table": _TABLE,
    # --- fragment rooting ------------------------------------------------------
    # The document IS the element. bs4's find_all searched from the soup, which
    # is the document rather than the element, so both were found.
    "document-is-a-table": _TABLE,
    "document-is-a-div": "<div>A standalone paragraph of prose in a div.</div>",
    "document-is-a-paragraph": "<p>A standalone paragraph of prose.</p>",
    # --- the currency merge ----------------------------------------------------
    # A '$' alone in its cell is merged into the next cell, whose colspan grows
    # by one and whose entire contents are REPLACED by the merged string.
    "currency-symbol-in-its-own-cell": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>1,000</td></tr></table>"
    ),
    "currency-cell-with-markup-inside-the-value": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td><b>1,</b><i>000</i></td></tr></table>"
    ),
    "currency-cell-already-has-a-colspan": (
        "<table><tr><th>Item</th><th>Amount</th><th>Prior</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td colspan='2'>1,000</td></tr></table>"
    ),
    "two-currency-symbols-in-a-row": (
        "<table><tr><th>Item</th><th>A</th><th>B</th></tr>"
        "<tr><td>Revenue</td><td>$</td><td>1,000</td><td>$</td><td>900</td></tr></table>"
    ),
    "currency-symbol-is-the-last-cell": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue</td><td>$</td></tr></table>"
    ),
    # --- the percent merge -----------------------------------------------------
    "percent-symbol-in-its-own-cell": (
        "<table><tr><th>Item</th><th>Rate</th></tr>"
        "<tr><td>Margin</td><td>42.5</td><td>%</td></tr></table>"
    ),
    "percent-close-paren-variant": (
        "<table><tr><th>Item</th><th>Rate</th></tr>"
        "<tr><td>Change</td><td>(3.2</td><td>%)</td></tr></table>"
    ),
    "pts-variant": (
        "<table><tr><th>Item</th><th>Change</th></tr>"
        "<tr><td>Spread</td><td>15</td><td>pts</td></tr></table>"
    ),
    "percent-with-nothing-before-it": (
        "<table><tr><th>Item</th><th>Rate</th></tr>"
        "<tr><td></td><td>%</td></tr></table>"
    ),
    # --- the whitespace BETWEEN cells, which lxml calls a tail -------------------
    # `decompose()` removed the tag and left the text around it alone. Deleting
    # an element in lxml takes its tail with it.
    "cells-separated-by-newlines": (
        "<table>\n<tr>\n<th>Item</th>\n<th>Amount</th>\n</tr>\n"
        "<tr>\n<td>Revenue</td>\n<td>$</td>\n<td>1,000</td>\n</tr>\n</table>"
    ),
    "text-between-cells": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue</td>stray<td>$</td>text<td>1,000</td>more</tr></table>"
    ),
    # A table with no usable rows. All three of these raise today -- see _run.
    "empty-table-element": "<p>Prose.</p><table></table>",
    "table-with-only-a-tbody": "<p>Prose.</p><table><tbody></tbody></table>",
    "table-of-only-layout-rows": (
        "<p>Prose.</p><table><tr>"
        + "".join("<td style='width:10px'></td>" for _ in range(8))
        + "</tr></table>"
    ),
    "table-with-cells-but-no-row": "<p>Prose.</p><table><td>x</td></table>",
    # --- layout rows -------------------------------------------------------------
    "width-grid-layout-row": (
        "<table>"
        "<tr>" + "".join("<td style='width:10px'></td>" for _ in range(8)) + "</tr>"
        "<tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue</td><td>$1,000</td></tr>"
        "</table>"
    ),
    # --- tables that are skipped --------------------------------------------------
    "nested-table-is-skipped": (
        "<table><tr><td><table><tr><td>Inner</td><td>1</td></tr></table></td></tr></table>"
    ),
    "xbrl-metadata-namespace-prefix": (
        "<table><tr><td>Namespace Prefix</td><td>us-gaap</td></tr>"
        "<tr><td>Data Type</td><td>xbrli:stringItemType</td></tr></table>"
    ),
    "us-gaap-table-with-dollars-and-years-is-kept": (
        "<table><tr><td>us-gaap_Revenues</td><td>2024</td></tr>"
        "<tr><td>Revenue</td><td>$1,000</td></tr></table>"
    ),
    "duplicate-tables": f"<div>{_TABLE}{_TABLE}</div>",
    # --- titles --------------------------------------------------------------------
    "table-with-a-caption": (
        "<table><caption>Segment Results</caption>"
        "<tr><th>Item</th><th>2024</th></tr><tr><td>Revenue</td><td>$1,000</td></tr></table>"
    ),
    "table-with-a-spanning-title-row": (
        "<table><tr><td colspan='3'>Summary of Significant Accounting Policies</td></tr>"
        "<tr><th>Item</th><th>2024</th><th>2023</th></tr>"
        "<tr><td>Revenue</td><td>$1,000</td><td>$900</td></tr></table>"
    ),
    # --- headings and the subsection detector -----------------------------------------
    "html-headings": "<h1>Top</h1><h2>Second</h2><h3>Third</h3><p>Body text here.</p>",
    "bold-span-subsection": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Revenue Recognition</span></div>"
        "<p>The Company recognises revenue when control transfers.</p>"
    ),
    "italic-span-subsection": (
        "<div style='margin-top:10pt'><span style='font-style:italic'>Deferred Revenue</span></div>"
        "<p>Deferred revenue is recorded when cash is received in advance.</p>"
    ),
    # A div holding exactly one span is treated as that span. Two spans is not.
    "div-with-one-span": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Inventories</span></div>"
    ),
    "div-with-two-spans": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Inv</span>"
        "<span style='font-weight:700'>entories</span></div>"
    ),
    # bs4's Comment is a str subclass, so a comment sitting beside the span
    # counted as a second child and disqualified the heading.
    "span-with-a-comment-sibling": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Inventories</span>"
        "<!-- filer note --></div>"
    ),
    "span-with-a-whitespace-sibling": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Inventories</span>   </div>"
    ),
    "span-with-a-text-sibling": (
        "<div style='margin-top:10pt'><span style='font-weight:700'>Inventories</span> and supplies</div>"
    ),
    "span-without-a-margin-top-parent": (
        "<div><span style='font-weight:700'>Inventories</span></div>"
    ),
    "centered-span-is-not-a-subsection": (
        "<div style='margin-top:10pt;text-align:center'>"
        "<span style='font-weight:700'>Inventories</span></div>"
    ),
    # --- lists ------------------------------------------------------------------------
    "unordered-list": "<ul><li>First item</li><li>Second item</li><li>   </li></ul>",
    "ordered-list": "<ol><li>Step one</li><li>Step two</li></ol>",
    "list-item-split-across-tags": "<ul><li>First <b>item</b> here</li></ul>",
    # --- script/style/head/meta removal -------------------------------------------------
    "script-and-style-are-dropped": (
        "<html><head><meta name='x' content='y'><style>.a{content:'GHOST'}</style></head>"
        "<body><script>var g='GHOST';</script><p>Real prose only.</p></body></html>"
    ),
    "style-inside-a-table-cell": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Revenue<style>.a{color:red}</style></td><td>$1,000</td></tr></table>"
    ),
    "text-follows-a-style-block": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td><style>.a{color:red}</style>Revenue</td><td>$1,000</td></tr></table>"
    ),
    # --- comments -------------------------------------------------------------------------
    "comment-inside-a-cell": (
        "<table><tr><th>Item</th><th>Amount</th></tr>"
        "<tr><td>Rev<!-- x -->enue</td><td>$1,000</td></tr></table>"
    ),
    "comment-between-paragraphs": "<p>First.</p><!-- a note --><p>Second.</p>",
    # --- parser leniency, encoding and depth ------------------------------------------------
    "unclosed-tags": "<table><tr><th>Item<th>Amount<tr><td>Revenue<td>$1,000",
    "encoding-declaration": (
        "<?xml version='1.0' encoding='ASCII'?><html><body>"
        "<p>Revenue — recognised on transfer of control.</p>" + _TABLE + "</body></html>"
    ),
    # 300 nested <div>s -- see edgartools-xqvr.
    "nested-300-deep": "<div>" * 300 + _TABLE + "</div>" * 300,
}

# `track_filtered=True` returns a (markdown, metadata) tuple and counts what was
# dropped, so it needs its own cases.
EDGE_TRACKED = {
    "tracked-xbrl-metadata": (
        "<table><tr><td>Namespace Prefix</td><td>us-gaap</td></tr></table>" + _TABLE
    ),
    "tracked-duplicate-tables": f"<div>{_TABLE}{_TABLE}</div>",
    "tracked-plain-text": "Just a sentence, no markup.",
}


def _notes() -> dict:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(NOTES.glob("*.html"))}


@pytest.mark.parametrize("name", list(_notes()))
def test_note_markdown_is_byte_identical(name):
    """The RAG-facing surface, pinned character for character."""
    expected = (GOLDEN / f"{name}.md").read_text(encoding="utf-8")
    assert process_content(_notes()[name]) == expected


def _run(html, track_filtered=False):
    """What `process_content` produced -- the exception included.

    Exceptions are captured rather than allowed to propagate because a crash is
    behaviour too, and a port must not change one silently. Five of the inputs
    below DID crash when this golden was first captured: `html_to_json` handed
    back `None` for its text blocks whenever a table yielded no usable rows and
    `process_content` iterated it unconditionally, so `<table></table>` -- or a
    table of nothing but width-grid layout rows, or prose that merely mentions
    `<table>` -- raised `TypeError: 'NoneType' object is not iterable` from
    `note.to_context()`. That is fixed (edgartools-1qbe, PR #1126), and their
    baselines here were recaptured on top of the fix. The capture stays, so the
    next crash shows up as a changed baseline rather than a red traceback with
    no reference point.
    """
    try:
        result = process_content(html, track_filtered=track_filtered)
    except Exception as exc:  # noqa: BLE001 -- the exception IS the behaviour
        return f"{type(exc).__name__}: {exc}"
    return list(result) if track_filtered else result


@pytest.mark.parametrize("name", list(EDGE))
def test_edge_markdown_matches_baseline(name):
    baseline = json.loads(EDGE_BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    assert _run(EDGE[name]) == baseline[name]


@pytest.mark.parametrize("name", list(EDGE_TRACKED))
def test_tracked_markdown_matches_baseline(name):
    baseline = json.loads(EDGE_BASELINE.read_text())
    key = f"TRACKED-{name}"
    assert key in baseline, f"{key} is missing from the baseline -- recapture it"
    assert _run(EDGE_TRACKED[name], track_filtered=True) == baseline[key]


def test_golden_covers_every_note():
    """A golden file that lost its fixture must not sit unnoticed."""
    assert {p.stem for p in GOLDEN.glob("*.md")} == set(_notes())


def test_baseline_covers_every_edge_case():
    baseline = set(json.loads(EDGE_BASELINE.read_text()))
    assert baseline == set(EDGE) | {f"TRACKED-{k}" for k in EDGE_TRACKED}
