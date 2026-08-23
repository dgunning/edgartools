"""Golden-file characterization of R-file report rendering (edgartools-07lk.11.6).

`report_render_baseline.json` is the rendered text of every R-file in the tracked
AAPL corpus, generated while `filing_summary.py` still ran on BeautifulSoup and
committed unchanged. The bs4 -> lxml port re-derives it and compares.

The RENDERED TEXT is the golden value rather than any intermediate object,
because that is what the reader sees: a translation that drops a tail or loses a
separator shows up here and nowhere in the object graph.

The corpus covers both branches of `_build_renderable` -- 12 of the 42 reports
take the embedded-table path added for issue #755, the other 30 the ordinary
single-table path.

WHAT THE CORPUS DOES *NOT* COVER, and why the second half of this file exists.
Mutating each risky translation to a deliberately wrong version showed only one
of them was actually exercised by 42 real reports:

    _joined_text -> text_content()                CAUGHT (12/42 reports differ)
    tail handling in _text_outside_tables         not caught
    tostring(with_tail=False) -> True             not caught
    class token match -> substring match          not caught

Three defences with no coverage are three defences that rot. The shapes below
supply it, and their expected values were read off the BeautifulSoup
implementation rather than reasoned about -- `get_text(' ', strip=True)` on a
copy with every nested table decomposed.

That exercise was worth doing for its own sake: it caught a bug in the port. The
obvious lxml translation of `decompose()` -- remove the table, splice its tail
back so it is not deleted along with it -- MERGES two of bs4's separate strings
into one text node, and the separator `get_text(' ')` put between them is then
never inserted. "Lead-in.<table/>Trailing." came back "Lead-in.Trailing.". The
whitespace variants below are the ones that pin it.
"""
import json
import pathlib

import pytest

import edgar.sgml.filing_summary as filing_summary
from edgar.richtools import rich_to_text
from edgar.sgml.filing_summary import Report

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
RFILES = REPO / "tests" / "fixtures" / "attachments" / "aapl" / "20250329"
BASELINE = REPO / "tests" / "fixtures" / "filing_summary" / "report_render_baseline.json"


class _FixtureReport(Report):
    """A Report whose content comes from a file rather than an SGML archive.

    A subclass rather than a patched `Report.content`: patching a class
    attribute and deleting it afterwards takes any real override with it, and
    the damage only shows up on the second test in the file.
    """

    def __init__(self, html: str, **kwargs):
        super().__init__(**kwargs)
        self._html = html

    @property
    def content(self):
        return self._html


def _report(path: pathlib.Path) -> _FixtureReport:
    return _FixtureReport(
        html=path.read_text(),
        instance=None, is_default=False, has_embedded_reports=False,
        long_name=f"Long name for {path.stem}", short_name=path.stem,
        menu_category="Notes", position=0, html_file_name=path.name,
        report_type="Sheet", role=None,
    )


def _rfiles():
    return sorted(RFILES.glob("R*.htm"), key=lambda p: int(p.stem[1:]))


def _render(path: pathlib.Path):
    renderable = _report(path)._build_renderable(500)
    return rich_to_text(renderable, width=500) if renderable is not None else None


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


def test_every_rfile_is_in_the_baseline(baseline):
    """An R-file added without regenerating the baseline proves nothing."""
    assert sorted(baseline) == sorted(p.name for p in _rfiles())


@pytest.mark.parametrize("path", _rfiles(), ids=lambda p: p.stem)
def test_the_render_matches_the_bs4_baseline(path, baseline):
    assert _render(path) == baseline[path.name]["rendered"]


def test_the_baseline_is_not_vacuous(baseline):
    """A baseline of empty renders would compare equal to a parser that found
    nothing at all."""
    rendered = [v["rendered"] for v in baseline.values()]
    assert all(r for r in rendered), "every report must render to something"
    assert sum(len(r) for r in rendered) > 150_000


def test_both_render_branches_are_covered():
    """12 reports take the issue #755 embedded-table path, 30 the plain one.
    If the corpus ever drifts to all-one-branch the baseline stops proving the
    thing it exists to prove."""
    embedded = 0
    for path in _rfiles():
        root = filing_summary._parse_report_html(path.read_text())
        report = filing_summary._first_by_class(root, "table", "report")
        assert report is not None, f"{path.name} has no table.report"
        if Report._has_embedded_tables(report):
            embedded += 1
    assert embedded == 12
    assert len(_rfiles()) - embedded == 30


# ------------------------------------------------------------------ narrative
#
# Expected values read off the BeautifulSoup implementation, not reasoned about.

NARRATIVE_CASES = [
    ("no whitespace", 'Lead-in.<table><tr><td>1</td></tr></table>Trailing.', "Lead-in. Trailing."),
    ("spaced", 'A <table><tr><td>1</td></tr></table> B', "A B"),
    ("newlines", 'A\n  <table><tr><td>1</td></tr></table>\n  B', "A B"),
    ("nested div", 'A<div>C<table><tr><td>1</td></tr></table>D</div>B', "A C D B"),
    ("table only", '<table><tr><td>1</td></tr></table>', ""),
    ("two tables", 'A<table><tr><td>1</td></tr></table>B<table><tr><td>2</td></tr></table>C', "A B C"),
    ("whitespace tail", 'A<table><tr><td>1</td></tr></table>   ', "A"),
    ("nested table", 'A<table><tr><td>x<table><tr><td>y</td></tr></table></td></tr></table>B', "A B"),
]


@pytest.mark.parametrize("name,inner,expected", NARRATIVE_CASES, ids=[c[0] for c in NARRATIVE_CASES])
def test_narrative_text_skips_tables_without_gluing_words(name, inner, expected):
    """The text around a nested table, exactly as bs4's decompose + get_text
    produced it. `spaced` and `newlines` are the two that fail if the tail is
    spliced onto its predecessor instead of kept as its own chunk."""
    html = f'<table class="report"><tr><td class="text">{inner}</td></tr></table>'
    root = filing_summary._parse_report_html(html)
    cell = filing_summary._first_by_class(root, "td", "text")
    assert filing_summary._text_outside_tables(cell) == expected


def test_joined_text_separates_what_text_content_would_glue():
    """lxml's text_content() concatenates descendants with no separator, where
    bs4's get_text(' ') put a space between them."""
    # Wrapped in a real table: libxml2 discards a <td> that is not inside one,
    # where bs4 kept the bare fragment.
    root = filing_summary._parse_report_html(
        '<table><tr><td class="pl"><span>Note 5</span><span>Inventories</span></td></tr></table>')
    cell = filing_summary._first_by_class(root, "td", "pl")
    assert cell.text_content() == "Note 5Inventories"      # what NOT to use
    assert filing_summary._joined_text(cell) == "Note 5 Inventories"


def test_a_class_is_matched_by_token_not_by_substring():
    """`class` is a token list: `class="text foo"` must match and
    `class="textbox"` must not, which is what bs4's class_= did."""
    root = filing_summary._parse_report_html(
        '<table class="report"><tr>'
        '<td class="textbox">no</td><td class="text foo">yes</td>'
        '</tr></table>')
    found = filing_summary._by_class(root, "td", "text")
    assert [filing_summary._joined_text(td) for td in found] == ["yes"]


def test_serializing_a_cell_does_not_swallow_the_next_cell():
    """lxml's tostring appends the element's tail by default -- the text that
    FOLLOWS the cell. bs4's str(td) never did, and the embedded table is parsed
    from this string, so a tail would leak one cell's text into another."""
    import lxml.html

    root = filing_summary._parse_report_html(
        '<table class="report"><tr>'
        '<td class="text">Cell A<table><tr><td>x</td></tr></table></td>'
        'TAIL-TEXT<td class="text">Cell B</td>'
        '</tr></table>')
    cell = filing_summary._first_by_class(root, "td", "text")
    assert "TAIL-TEXT" not in lxml.html.tostring(cell, encoding="unicode", with_tail=False)
    assert "TAIL-TEXT" in lxml.html.tostring(cell, encoding="unicode", with_tail=True)


# ---------------------------------------------------------------- edge inputs


@pytest.mark.parametrize("content", ["", "   \n\t ", "<html><body>no report here</body></html>"])
def test_content_with_no_report_table_falls_back_rather_than_raising(content):
    """bs4 built an empty soup for blank input; lxml raises ParserError. Blank
    or unparseable content has always fallen through to the ordinary
    single-table render, and still does."""
    report = _FixtureReport(
        html=content,
        instance=None, is_default=False, has_embedded_reports=False,
        long_name="x", short_name="x", menu_category="Notes", position=0,
        html_file_name="R1.htm", report_type="Sheet", role=None,
    )
    assert report._build_renderable(500) is None


def test_blank_content_parses_to_none_rather_than_raising():
    assert filing_summary._parse_report_html("") is None
    assert filing_summary._parse_report_html("   \n ") is None
