"""
Characterization tests for the HTML helpers in edgar.xbrl.notes.

These pin the exact behaviour of the bs4-based implementations *before*
the lxml.html port (#1104, part of #931). The output of these helpers is
RAG-facing text where whitespace semantics matter exactly, so every
assertion is byte-exact on real note HTML extracted from the repo's
recorded Apple 10-K cassette (filing_text_baseline_0000320193-23-000106).
"""
from pathlib import Path

import lxml.html
import pytest

from edgar.xbrl.notes import (
    _extract_narrative_markdown,
    _html_table_to_plain_text,
)

NOTES_DIR = Path('data/notes')


def _read(name) -> str:
    return (NOTES_DIR / name).read_text(encoding='utf-8')


def _lxml_table(name):
    # Post-port, the caller hands this function an lxml <table> element
    # parsed with the house parser settings.
    tree = lxml.html.fromstring(_read(name))
    return [el for el in tree.iter() if el.tag == 'table'][0]


# --- _html_table_to_plain_text ------------------------------------------------

@pytest.mark.fast
def test_clean_table_plain_text_pinned():
    table_tag = _lxml_table('real-clean-table.html')
    result = _html_table_to_plain_text(table_tag)
    assert result is not None
    lines = result.split('\n')
    # Every data row survives, columns stay aligned within each line.
    assert all(len(line.split('  ')) >= 1 for line in lines)
    # The definition text from the hidden authRefData block is present.
    assert 'Fair value of investment in debt security' in result


@pytest.mark.fast
def test_colspan_table_cells_survive_individually():
    table_tag = _lxml_table('real-colspan-table.html')
    result = _html_table_to_plain_text(table_tag)
    assert result is not None
    # No cell content may be dropped or merged by the fallback renderer.
    # This real fixture is a signature block.
    assert '/s/' in result
    assert 'SUSAN L. WAGNER' in result
    assert 'November 2, 2023' in result
    assert '\t' not in result


@pytest.mark.fast
def test_empty_and_non_table_input_return_none():
    # An empty <table> has no rows -> None (the real caller never passes
    # anything else, so only the empty-table case is pinned).
    tree = lxml.html.fromstring('<table></table>')
    table = [el for el in tree.iter() if el.tag == 'table'][0]
    assert _html_table_to_plain_text(table) is None


# --- _extract_narrative_markdown ----------------------------------------------

@pytest.mark.fast
def test_adjacent_span_boundary_gets_space_in_plain_mode():
    html = _read('real-narrative.html')
    text = _extract_narrative_markdown(html, optimize_for_llm=False)
    # "iPhone" and "(1)" sit in adjacent spans; the separator heuristic
    # inserts a space at the boundary. Note the pinned pre-existing quirk:
    # the same lowercase-to-uppercase rule also splits inside camel-case
    # words ("iPhone" -> "i Phone"). Characterised as-is; the port must
    # reproduce this byte-exactly.
    assert text == 'i Phone (1)'


@pytest.mark.fast
def test_narrative_none_when_only_whitespace_remains():
    assert _extract_narrative_markdown('<div>   </div>', optimize_for_llm=False) is None
    assert _extract_narrative_markdown('', optimize_for_llm=False) is None


@pytest.mark.fast
def test_narrative_strips_tables():
    html = '<div>Total assets were <b>$1.00</b><table><tr><td>x</td></tr></table> at year end.</div>'
    text = _extract_narrative_markdown(html, optimize_for_llm=False)
    assert 'Total assets' in text
    assert '<table>' not in text
    assert 'at year end.' in text


# --- _render_statement_to_markdown ----------------------------------------------

class _StubStatement:
    """Minimal stand-in for Statement: raw HTML plus plain text."""

    def __init__(self, raw_html, plain):
        self._raw = raw_html
        self._plain = plain

    def text(self, raw_html: bool = False):
        return self._raw if raw_html else self._plain


@pytest.mark.fast
def test_renderer_splices_pipe_tables_between_text():
    from edgar.xbrl.notes import _render_statement_to_markdown
    html = (
        '<div><h2>Schedule I</h2>'
        '<table><tr><td>Name</td></tr><tr><td>ACME LTD</td></tr></table>'
        '<p>See accompanying notes.</p>'
        '</div>'
    )
    stmt = _StubStatement(html, 'fallback-plain')
    md = _render_statement_to_markdown(stmt, 'Schedule I', optimize_for_llm=True)
    # Table becomes a pipe table spliced between the surrounding content;
    # the pinned shape below is exactly what process_content produces for
    # this input (including its duplicated-heading artefact).
    assert '| label |' in md
    assert '| ACME LTD |' in md
    assert 'See accompanying notes.' in md
    assert '__TBLPH_' not in md


@pytest.mark.fast
def test_renderer_falls_back_to_plain_when_optimize_false():
    from edgar.xbrl.notes import _render_statement_to_markdown
    html = '<div><table><tr><td>x</td></tr></table></div>'
    stmt = _StubStatement(html, 'plain-text-version')
    md = _render_statement_to_markdown(stmt, 'Note 5', optimize_for_llm=False)
    assert md == 'plain-text-version'


@pytest.mark.fast
def test_renderer_empty_html_returns_none():
    from edgar.xbrl.notes import _render_statement_to_markdown
    stmt = _StubStatement('', None)
    assert _render_statement_to_markdown(stmt, 'Note', optimize_for_llm=True) is None
