r"""Characterization of the 497K table extractors' bs4 -> lxml port
(edgartools-07lk.11.9.1).

`prospectus_497k_baseline.json` is what `extract_fee_tables()`,
`extract_performance_table()` and `extract_fund_metadata()` returned for each
input below, captured while `edgar/funds/_497k_tables.py` still ran on
BeautifulSoup.

THE CORPUS is seventeen real 497K summary prospectuses in
`tests/fixtures/prospectus_497k/`, harvested across 2012, 2016, 2020, 2023 and
2025 from seventeen different fund families -- Vanguard, Fidelity, American
Funds, Invesco, AllianceBernstein, Columbia, Alger, American Century, Bitwise
and others. Fund families each have their own prospectus typesetter, so the
family spread matters more here than the year spread: between them these
documents produce fee tables, expense examples, multi-year performance tables
and best/worst-quarter tables, and one produces nothing at all.

`Prospectus497K.from_filing()` passes `filing.html()` straight into all three
functions, so the fixtures are exactly what the extractors see in production.

WHAT THE PORT HAS TO GET RIGHT:

  * `_get_cell_text` is `get_text(separator=' ', strip=True)` -- strip each
    string, drop the empties, join with a SPACE. `text_content()` joins with
    nothing, which turns `<font>Management</font><font>Fee</font>` into
    "ManagementFee" and `_is_fee_label` stops recognising the row.
  * `table.find_all('tr')` is recursive and `tr.find_all(['td','th'])` returns
    ONE list in document order -- not the tds followed by the ths. Every
    extractor here is positional, so a reordered row shifts every column.
  * `soup.find_all('table')` searches descendant-or-self once the document IS
    the table.
  * bs4's `get_text()` left `<script>`, `<style>` and `<template>` text out;
    `itertext()` puts it in, and a stylesheet inside a fee table is enough to
    change how `_classify_table` labels it.

The three `BeautifulSoup(html, 'lxml')` sites already ran on libxml2, so this
port removes a wrapper rather than swapping a parser; the speed-up is bs4's
tree construction, not the parse.

MUTATION PROBE, 2026-08-24: 18 mistranslations, 18 killed. No equivalent
mutants and no survivors -- the only file in this phase where that happened.

The seventeen real prospectuses killed 14 on their own. The last two needed an
input each, and both are the same lesson: the mistranslation has to change a
NUMBER, not a label. `remove_comments=True` survives every comment that
interrupts a label, because `_normalize` collapses the doubled space it leaves
behind; it dies on a comment inside a percentage (`0.<!-- fn -->50%`), where
merging the strings turns an unparseable "0. 50%" into a parseable "0.50%".
A direct-children cell walk survives a nested table that only adds a column at
the end; it dies on one that shifts the class columns, so each figure lands
under a different share class.
"""
import json
import pathlib

import pytest

from edgar.funds._497k_tables import (
    extract_fee_tables,
    extract_fund_metadata,
    extract_performance_table,
)

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "prospectus_497k_baseline.json"
CORPUS = FIX / "prospectus_497k"


def _row(cells, tag="td"):
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


_FEE_TABLE = (
    "<table>"
    + _row(["", "Class A", "Class C"], tag="th")
    + _row(["Management Fee", "0.50%", "0.50%"])
    + _row(["Distribution (12b-1) Fees", "0.25%", "1.00%"])
    + _row(["Other Expenses", "0.15%", "0.15%"])
    + _row(["Total Annual Fund Operating Expenses", "0.90%", "1.65%"])
    + "</table>"
)

_PERF_TABLE = (
    "<table>"
    + _row(["", "1 Year", "5 Years", "10 Years"], tag="th")
    + _row(["Return Before Taxes", "10.00%", "8.00%", "6.00%"])
    + _row(["Return After Taxes on Distributions", "9.00%", "7.00%", "5.00%"])
    + "</table>"
)

_QUARTER_TABLE = (
    "<table>"
    + _row(["Highest Quarterly Return", "12.34%", "June 30, 2020"])
    + _row(["Lowest Quarterly Return", "-9.87%", "March 31, 2020"])
    + "</table>"
)

_METADATA_TEXT = (
    "<p>Investment Objective</p>"
    "<p>The Fund seeks long-term capital appreciation. It invests broadly.</p>"
    "<p>Portfolio Turnover: the Fund's portfolio turnover rate was 42% of the "
    "average value of its portfolio.</p>"
    "<p>Minimum initial investment: $2,500</p>"
)

EDGE = {
    # --- degenerate ---------------------------------------------------------
    "empty": "",
    "whitespace": "   \n\t  ",
    "no-tables": "<html><body><p>A prospectus with no tables at all.</p></body></html>",
    "table-with-no-rows": "<html><body><table></table></body></html>",
    # --- the three shapes, alone and together --------------------------------
    "fee-table-only": f"<html><body>{_FEE_TABLE}</body></html>",
    "performance-table-only": f"<html><body>{_PERF_TABLE}</body></html>",
    "quarter-table-only": f"<html><body>{_QUARTER_TABLE}</body></html>",
    "metadata-only": f"<html><body>{_METADATA_TEXT}</body></html>",
    "everything": f"<html><body>{_METADATA_TEXT}{_FEE_TABLE}{_PERF_TABLE}{_QUARTER_TABLE}</body></html>",
    # --- fragment rooting ----------------------------------------------------
    # The document IS the table. `.//table` finds nothing here.
    "fee-table-is-the-root": _FEE_TABLE,
    "performance-table-is-the-root": _PERF_TABLE,
    # --- _get_cell_text: strip each, join with a SPACE ------------------------
    # text_content() gives "ManagementFee" and _is_fee_label stops matching.
    "fee-label-split-across-inline-tags": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td><font>Management</font><font>Fee</font></td><td>0.50%</td></tr>"
        + _row(["Total Annual Fund Operating Expenses", "0.90%"])
        + "</table>"
    ),
    "fee-label-padded-with-whitespace": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + _row(["\n   Management Fee   \n", "0.50%"])
        + "</table>"
    ),
    "percentage-split-across-tags": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td>Management Fee</td><td>0.<font>50</font>%</td></tr>"
        + "</table>"
    ),
    # bs4's Comment subclasses str but get_text() still excluded it, and
    # remove_comments=True would merge the strings either side.
    "fee-label-interrupted-by-a-comment": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td>Management <!-- note --> Fee</td><td>0.50%</td></tr>"
        + "</table>"
    ),
    # bs4 never saw <script>/<style> text; lxml does.
    "fee-cell-has-a-style": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td>Management Fee<style>.a{content:'Return Before Taxes'}</style></td>"
          "<td>0.50%</td></tr>"
        + "</table>"
    ),
    # The DISCRIMINATING text is the style block's TAIL.
    "fee-label-follows-a-style-block": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td><style>.a{color:red}</style>Management Fee</td><td>0.50%</td></tr>"
        + "</table>"
    ),
    "performance-label-follows-a-script": (
        "<table>"
        + _row(["", "1 Year"], tag="th")
        + "<tr><td><script>var x=1;</script>Return Before Taxes</td><td>10.00%</td></tr>"
        + "</table>"
    ),
    # --- row and cell order ---------------------------------------------------
    # Every extractor here is positional. find_all(['td','th']) returned ONE
    # list in document order; tds-then-ths shifts every column.
    "row-mixes-th-label-with-td-figures": (
        "<table>"
        + _row(["", "Class A", "Class C"], tag="th")
        + "<tr><th>Management Fee</th><td>0.50%</td><td>0.60%</td></tr>"
        + "</table>"
    ),
    "row-ends-with-a-th": (
        "<table>"
        + _row(["", "Class A", "Class C"], tag="th")
        + "<tr><td>Management Fee</td><td>0.50%</td><th>0.60%</th></tr>"
        + "</table>"
    ),
    "rows-inside-a-tbody": (
        "<table><thead>"
        + _row(["", "Class A"], tag="th")
        + "</thead><tbody>"
        + _row(["Management Fee", "0.50%"])
        + _row(["Total Annual Fund Operating Expenses", "0.90%"])
        + "</tbody></table>"
    ),
    # find_all('tr') was recursive, so an inner table's rows are the outer's too.
    "nested-table-inside-a-fee-row": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td><table><tr><td>Management Fee</td><td>9.99%</td></tr></table></td>"
          "<td>0.50%</td></tr>"
        + "</table>"
    ),
    # A comment INSIDE a number. bs4 kept the strings either side separate, so
    # the cell reads "0. 50%" and the percentage does not parse; parsing with
    # remove_comments=True merges them into "0.50%" and it does. The faithful
    # answer is the one that fails.
    "comment-inside-a-percentage": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + "<tr><td>Management Fee</td><td>0.<!-- fn -->50%</td></tr>"
        + "</table>"
    ),
    # The inner table's cell lands at index 1 in a RECURSIVE walk and vanishes
    # from a direct-children one, so the two disagree about which class column
    # each figure belongs to.
    "nested-cell-shifts-the-class-columns": (
        "<table>"
        + _row(["", "Class A", "Class C"], tag="th")
        + "<tr><td>Management Fee</td>"
          "<td><table><tr><td>9.99%</td></tr></table></td>"
          "<td>0.50%</td></tr>"
        + _row(["Total Annual Fund Operating Expenses", "0.90%", "1.65%"])
        + "</table>"
    ),
    # --- classification boundaries --------------------------------------------
    "expense-example-dollars": (
        "<table>"
        + _row(["", "1 Year", "3 Years", "5 Years", "10 Years"], tag="th")
        + _row(["Class A", "$92", "$287", "$498", "$1,108"])
        + "</table>"
    ),
    "shareholder-fees": (
        "<table>"
        + _row(["", "Class A"], tag="th")
        + _row(["Maximum Sales Charge (Load) Imposed on Purchases", "5.75%"])
        + _row(["Redemption Fee", "None"])
        + "</table>"
    ),
    "bar-chart-years": (
        "<table>"
        + _row(["2020", "2021", "2022", "2023", "2024"], tag="th")
        + _row(["10.1%", "-3.2%", "14.7%", "8.8%", "2.4%"])
        + "</table>"
    ),
    # --- the metadata text scan ------------------------------------------------
    "turnover-split-across-tags": (
        "<html><body><p>Portfolio <b>Turnover</b>: the rate was 3<i>7</i>% of the "
        "average value.</p></body></html>"
    ),
    "turnover-only-in-a-style-block": (
        "<html><head><style>.x{content:'portfolio turnover 99%'}</style></head>"
        "<body><p>Nothing else here.</p></body></html>"
    ),
    "objective-runs-into-the-fee-heading": (
        "<html><body><p>Investment Objective</p><p>Seeks income.</p>"
        "<p>Fees and Expenses</p></body></html>"
    ),
    "two-minimum-investments": (
        "<html><body><p>Minimum initial investment: $2,500</p>"
        "<p>Minimum investment for retirement accounts: $1,000</p></body></html>"
    ),
    # --- parser leniency, encoding and depth ------------------------------------
    "unclosed-tags": "<table><tr><th><th>Class A<tr><td>Management Fee<td>0.50%",
    "encoding-declaration": (
        "<?xml version='1.0' encoding='ASCII'?><html><body>"
        "<p>Portfolio Turnover — the rate was 42% of the average value.</p>"
        f"{_FEE_TABLE}</body></html>"
    ),
    # 300 nested <div>s -- libxml2 drops below depth 256 without huge_tree.
    # See edgartools-xqvr.
    "nested-300-deep": "<div>" * 300 + _FEE_TABLE + "</div>" * 300,
}

# `extract_fee_tables` also takes the SGML header's class_info. The reorder it
# drives reads the raw HTML string rather than the tree, so the port cannot
# touch it -- pinned so that stays true.
CLASS_INFO = {
    "class-info-reordered-by-html": (
        f"<html><body>{_FEE_TABLE}</body></html>",
        [{"name": "Class C Shares", "ticker": "CCCCX"},
         {"name": "Class A Shares", "ticker": "AAAAX"}],
    ),
}


def _corpus() -> dict:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(CORPUS.glob("*.html"))}


def _cases() -> dict:
    """name -> (html, class_info)."""
    cases = {k: (v, None) for k, v in _corpus().items()}
    cases.update({f"EDGE-{k}": (v, None) for k, v in EDGE.items()})
    cases.update({f"EDGE-{k}": (html, ci) for k, (html, ci) in CLASS_INFO.items()})
    return cases


def _jsonable(value):
    """Decimals and tuples, flattened so JSON can hold them."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)


def _run(html: str, class_info=None) -> dict:
    perf, best, worst = extract_performance_table(html)
    return _jsonable({
        "fee_tables": extract_fee_tables(html, class_info=class_info),
        "performance": perf,
        "best_quarter": best,
        "worst_quarter": worst,
        "metadata": extract_fund_metadata(html),
    })


@pytest.mark.parametrize("name", list(_cases()))
def test_497k_extraction_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    html, class_info = _cases()[name]
    assert _run(html, class_info) == baseline[name]


def test_baseline_covers_every_case():
    assert set(json.loads(BASELINE.read_text())) == set(_cases())
