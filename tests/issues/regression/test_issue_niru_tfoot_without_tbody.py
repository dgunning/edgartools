"""Regression test for edgartools-niru: tfoot rows are processed exactly once.

When a table had a ``<tfoot>`` but no ``<tbody>``, the row scan ran over the
table element itself, so the footer rows were read once as body rows and again
into ``table.footer``. The rich and HTML renderers then showed the total twice.

Fixing that exposed the other half: markdown, ``text()`` and ``to_dataframe()``
read only ``table.rows`` and never the footer, so a table written with both a
tbody and a tfoot already lost its total row in those outputs. Every output now
carries the footer once, after the body.
"""

import pytest

from edgar.documents import parse_html
from edgar.documents.nodes import NodeType
from edgar.documents.renderers.markdown import MarkdownRenderer

BODY_ROWS = "<tr><td>Revenue</td><td>100</td></tr><tr><td>Cost</td><td>40</td></tr>"
LAYOUTS = {
    "no-tbody": BODY_ROWS,
    "tbody": f"<tbody>{BODY_ROWS}</tbody>",
}


def _table(body):
    html = (
        "<html><body><table><thead><tr><th>Item</th><th>2025</th></tr></thead>"
        f"{body}<tfoot><tr><td>Total</td><td>140</td></tr></tfoot></table></body></html>"
    )
    tables = [node for node in parse_html(html).root.walk() if node.type == NodeType.TABLE]
    assert len(tables) == 1
    return tables[0]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_footer_rows_are_not_also_body_rows(layout):
    table = _table(LAYOUTS[layout])
    assert [[c.text() for c in row.cells] for row in table.rows] == [["Revenue", "100"], ["Cost", "40"]]
    assert [[c.text() for c in row.cells] for row in table.footer] == [["Total", "140"]]


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("table_format", ["pipe", "grid", "simple"])
def test_markdown_shows_the_total_once(layout, table_format):
    renderer = MarkdownRenderer()
    renderer.table_format = table_format
    rendered = renderer._render_table(_table(LAYOUTS[layout]))
    assert rendered.count("Total") == 1
    assert rendered.count("140") == 1
    assert rendered.index("Cost") < rendered.index("Total")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_text_shows_the_total_once(layout):
    text = _table(LAYOUTS[layout]).text()
    assert text.count("Total") == 1
    assert text.index("Cost") < text.index("Total")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_dataframe_ends_with_the_total(layout):
    df = _table(LAYOUTS[layout]).to_dataframe()
    assert list(df.index) == ["Revenue", "Cost", "Total"]
    assert df.iloc[-1, 0] == 140.0
