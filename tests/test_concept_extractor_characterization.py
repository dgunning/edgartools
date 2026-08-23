"""Characterization of the R*.htm concept extractor's bs4 -> lxml port
(edgartools-07lk.11.9).

`concept_extractor_baseline.json` is what `extract_concepts_from_report`
produced over the repo's 44 real R*.htm fixtures -- 42 AAPL 10-Q reports plus
the ADI and ADSK 10-K reports kept for GH #812 and #818 -- captured while the
module still ran on BeautifulSoup. Every field of every one of the 646 rows is
pinned, along with the title, the period headers and the two scaling factors.

REAL FILINGS ARE NOT ENOUGH HERE, and this file exists mostly to say why.
Mutating each translated construct in turn, the 44-file corpus caught only 6
of 26 plausible mistranslations. The R*.htm files the SEC generates are
machine-written and uniform: the label anchor is always a direct child, the
header <div> is always a direct child, no cell contains a nested table, no
document carries a comment or an encoding declaration. Every one of those is a
construct where lxml and bs4 disagree, and the corpus is silent on all of them.

The EDGE inputs below close that gap: with them the same probe kills 23 of 26.
Each is written to fail one specific mistranslation, and the docstring on each
says which. The three that survive are equivalent mutants, not gaps:

  * ``td != label_cell`` -- lxml defines no ``__eq__``, so ``!=`` on elements
    already IS identity. (bs4's ``!=`` was structural, which is the reason the
    port says ``is not``.)
  * ``if not report_table`` instead of ``is None`` -- a childless <table> is
    falsy, but a <table> with no rows produces an empty report down either
    path, so no output can distinguish them.
  * ``if not label_cell`` instead of ``is None`` -- a childless label cell has
    no <a>, so the concept-id lookup drops the row a line later regardless.

TWO ACCEPTED DIFFERENCES. Both are libxml2's error recovery disagreeing with
html.parser's on markup that is already broken, not translation errors, and
neither shape occurs in an R*.htm file:

  * ``<a>L<table>..</table></a>`` -- html.parser nests the table inside the
    anchor; libxml2 closes the anchor first. The old label was "Linner".
  * ``<th><strong>T</strong><td>Q1`` with nothing closed -- html.parser nests
    the <td> inside the <th>; libxml2 makes it a sibling, so it becomes a
    period column.

They are asserted explicitly at the bottom, so a future parser change that
moves either one is a test failure rather than a surprise.
"""
import json
import pathlib
from dataclasses import asdict

import pytest

from edgar.sgml.concept_extractor import extract_concepts_from_report

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "concept_extractor_baseline.json"
CORPUS = sorted(
    list((FIX / "attachments" / "aapl" / "20250329").glob("R*.htm"))
    + list((FIX / "issues" / "regression" / "issue_818").glob("*.htm"))
)


EDGE = {
    "empty": "",
    "whitespace": "   \n  ",
    "no-table": "<html><body><p>No table</p></body></html>",
    "table-not-report": "<html><body><table class='other'><tr><td>x</td></tr></table></body></html>",
    "bare-table-fragment": '<table class="report"><tr><th class="tl"><strong>Title<br>$ in Millions</strong></th><th class="th">Dec. 31, 2024</th></tr>'
                           '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_us-gaap_Assets\', window)">Assets</a></td>'
                           '<td class="nump">$ 1,234</td></tr></table>',
    "unclosed-tags": '<html><body><table class="report"><tr><th class="tl"><strong>T</strong><td class="th">Q1</table>',
    "nested-table": '<html><body><table class="report"><tr class="re"><td class="pl">'
                    '<a onclick="Show.showAR(this, \'defref_x_Y\', window)">L<table><tr><td>inner</td></tr></table></a></td>'
                    '<td class="nump">5</td></tr></table></body></html>',
    "tbody-present": '<html><body><table class="report"><tbody><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
                     '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td><td class="nump">1</td></tr>'
                     '</tbody></table></body></html>',
    "multiple-report-tables": '<html><body><table class="report"><tr><th class="tl"><strong>First</strong></th></tr></table>'
                              '<table class="report"><tr><th class="tl"><strong>Second</strong></th></tr></table></body></html>',
    "class-substring": '<html><body><table class="reporting"><tr><th class="tl"><strong>NotAReport</strong></th></tr></table></body></html>',
    "multi-class-report": '<html><body><table class="foo report bar"><tr><th class="tl"><strong>Multi</strong></th><th>Q1</th></tr>'
                          '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td><td class="nump">7</td></tr>'
                          '</table></body></html>',
    "entities-and-nbsp": '<html><body><table class="report"><tr><th class="tl"><strong>T&amp;C</strong></th><th>Q1</th></tr>'
                         '<tr class="re"><td class="pl" style="padding-left:36px"><a onclick="Show.showAR(this, \'defref_a_B\', window)">A&nbsp;&amp;&nbsp;B</a></td>'
                         '<td class="nump"> $ 9​</td></tr></table></body></html>',
    "row-class-list": '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
                      '<tr class="re foo"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td><td class="nump">1</td></tr>'
                      '</table></body></html>',
    "no-onclick-anchor": '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
                         '<tr class="re"><td class="pl"><a>NoOnclick</a></td><td class="nump">1</td></tr></table></body></html>',
}

# Inputs added after the first mutation probe: every one of them exists to kill
# a specific mistranslation the 44-file corpus left alive.
EDGE.update({
    # `if not report_table` -- an lxml element with no children is falsy.
    "empty-report-table": '<html><body><table class="report"></table></body></html>',
    # `if a_tag:` on the label anchor -- same trap, and the fall-through
    # silently swallows the text outside the anchor.
    "label-text-outside-anchor":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a> extra</td>'
        '<td class="nump">1</td></tr></table></body></html>',
    # find('a') vs find('.//a') on both the concept id and the label.
    "anchor-nested-in-span":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
        '<tr class="re"><td class="pl"><span><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></span> extra</td>'
        '<td class="nump">1</td></tr></table></body></html>',
    # `./tr`, `./td` and `./th|./td` vs their descendant forms.
    "nested-table-in-cells":
        '<html><body><table class="report">'
        '<tr><th class="tl"><strong>T</strong></th><th><table><tr><th>Inner</th></tr></table>Q1</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1<table><tr><td class="num">99</td></tr></table></td></tr></table></body></html>',
    # A tail between an element child and the <br> in the title cell.
    "title-with-tail":
        '<html><body><table class="report"><tr><th class="tl"><strong><span>A</span> tail <br/>rest</strong></th>'
        '<th>Q1</th></tr></table></body></html>',
    # A comment inside the title cell. bs4 skipped it in get_text() but the
    # children walk emitted it, because Comment subclasses str.
    "title-with-comment":
        '<html><body><table class="report"><tr><th class="tl"><strong>A<!-- hidden -->B<br>x</strong></th>'
        '<th>Q1</th></tr></table></body></html>',
    # A comment splitting a value cell: dropping it at parse time merges the
    # text either side into one node, which changes get_text(strip=True).
    "comment-in-value-cell":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1 <!-- c --> 2</td></tr></table></body></html>',
    # Title falls back to the whole header, where text_content() and
    # get_text(strip=True) genuinely disagree.
    "title-fallback-to-full-header":
        '<html><body><table class="report"><tr><th class="tl"><strong> <br/>Cash <i>and</i> Equivalents</strong></th>'
        '<th>Q1</th></tr></table></body></html>',
    # th.find('div') vs th.find('.//div').
    "th-div-nested":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th>'
        '<th><span><div>Q1</div></span>ignored</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1</td></tr></table></body></html>',
    # A header row whose FIRST cell is a <td>: the header section ends there.
    "header-row-td-first":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
        '<tr><td>x</td><th>Q2</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1</td></tr></table></body></html>',
    # An encoding declaration: lxml refuses to parse this from a str.
    "xml-prolog":
        '<?xml version="1.0" encoding="utf-8"?>'
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1</td></tr></table></body></html>',
    # An inner <td> that falls inside a real period column, so `.//td` for the
    # value cells shifts every later value by one.
    "nested-td-shifts-columns":
        '<html><body><table class="report"><tr><th class="tl"><strong>T</strong></th><th>Q1</th><th>Q2</th></tr>'
        '<tr class="re"><td class="pl"><a onclick="Show.showAR(this, \'defref_a_B\', window)">L</a></td>'
        '<td class="nump">1<table><tr><td class="num">99</td></tr></table></td>'
        '<td class="nump">2</td></tr></table></body></html>',
})


def serialize(report):
    return {
        "title": report.title,
        "period_headers": report.period_headers,
        "currency": report.currency,
        "currency_scaling": report.currency_scaling,
        "shares_scaling": report.shares_scaling,
        "rows": [asdict(r) for r in report.rows],
    }


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


# ------------------------------------------------------------- golden file


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_real_reports_match_the_bs4_baseline(path, baseline):
    report = extract_concepts_from_report(path.read_text())
    assert serialize(report) == baseline[f"{path.parent.name}/{path.name}|form=None"]


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_annual_primary_period_matches_the_bs4_baseline(path, baseline):
    """``form`` reaches only _pick_primary_period; pin what it picks."""
    report = extract_concepts_from_report(path.read_text(), form="10-K")
    got = {
        "primary_period": report.rows[0].primary_period if report.rows else None,
        "period_headers": report.period_headers,
    }
    assert got == baseline[f"{path.parent.name}/{path.name}|form=10-K"]


@pytest.mark.parametrize("name", sorted(EDGE), ids=lambda n: n)
@pytest.mark.parametrize("form", [None, "10-K"], ids=["no-form", "10-K"])
def test_edge_inputs_match_the_bs4_baseline(name, form, baseline):
    key = f"EDGE:{name}|form={form}"
    if name in ("nested-table", "unclosed-tags"):
        pytest.skip("libxml2 recovery differs here on purpose; see the two tests below")
    assert serialize(extract_concepts_from_report(EDGE[name], form=form)) == baseline[key]


def test_the_baseline_is_not_vacuous(baseline):
    """An extractor that returned empty reports would match a baseline of them."""
    rows = sum(len(v.get("rows", [])) for v in baseline.values())
    assert rows == 646
    assert len(CORPUS) == 44


# ------------------------------------------- differences we chose to accept


def test_a_table_inside_the_label_anchor_no_longer_swallows_the_inner_text():
    """html.parser nested the table in the <a>; libxml2 closes the <a> first.

    The bs4 label here was "Linner" -- the inner table's text glued onto the
    label. No R*.htm file puts a table inside a label anchor.
    """
    report = extract_concepts_from_report(EDGE["nested-table"])
    assert [r.label for r in report.rows] == ["L"]


def test_an_unclosed_th_now_ends_the_header_cell():
    """html.parser nested the stray <td> inside the <th>; libxml2 does not.

    bs4 therefore found no period column at all; lxml finds "Q1". Nothing in
    an R*.htm file leaves a <th> unclosed.
    """
    report = extract_concepts_from_report(EDGE["unclosed-tags"])
    assert report.title == "T"
    assert report.period_headers == ["Q1"]


# ----------------------------------------------- the traps, stated directly


def test_class_matching_is_by_token_not_substring():
    """bs4's ``class_="report"`` matched a class TOKEN. A naive lxml
    ``contains(@class, 'report')`` would match ``class="reporting"``."""
    assert extract_concepts_from_report(EDGE["class-substring"]).title == ""
    assert extract_concepts_from_report(EDGE["multi-class-report"]).title == "Multi"


def test_a_document_that_is_nothing_but_the_table_still_parses():
    """lxml roots a single-element fragment AT that element, so a
    descendant-only search for the table finds nothing."""
    report = extract_concepts_from_report(EDGE["bare-table-fragment"])
    assert report.title == "Title"
    assert report.currency_scaling == 1_000_000
    assert [r.concept_id for r in report.rows] == ["us-gaap_Assets"]


def test_label_text_outside_the_anchor_is_ignored():
    """``if a_tag:`` would be False for an <a> with no ELEMENT children, and
    the fall-through would return the whole cell's text instead."""
    report = extract_concepts_from_report(EDGE["label-text-outside-anchor"])
    assert [r.label for r in report.rows] == ["L"]


def test_an_encoding_declaration_does_not_raise():
    """lxml refuses a str carrying an encoding declaration; the reader
    normalises to bytes first."""
    report = extract_concepts_from_report(EDGE["xml-prolog"])
    assert report.title == "T"
    assert [r.values for r in report.rows] == [{"Q1": "1"}]


def test_rows_inside_a_tbody_are_invisible():
    """Preserved bs4 behaviour, not a new limitation: ``find_all('tr',
    recursive=False)`` skipped them too, and neither parser invents a
    <tbody> the markup does not have."""
    report = extract_concepts_from_report(EDGE["tbody-present"])
    assert report.title == "T"
    assert report.rows == []
