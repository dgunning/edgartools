"""Regression tests for TOC links that target <a name="..."> anchors."""

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


HTML_WITH_NAMED_ANCHORS = """
<html>
  <body>
    <table>
      <tr>
        <td>Item 1.</td>
        <td><a href="#ITEM_1_BUSINESS">Business</a></td>
        <td>3</td>
      </tr>
      <tr>
        <td>Item 1A.</td>
        <td><a href="#ITEM_1A_RISK_FACTORS">Risk Factors</a></td>
        <td>17</td>
      </tr>
      <tr>
        <td>Item 2.</td>
        <td><a href="#ITEM_2_PROPERTIES">Properties</a></td>
        <td>29</td>
      </tr>
    </table>

    <p><a name="ITEM_1_BUSINESS"></a>ITEM 1. BUSINESS</p>
    <p>Business section text.</p>

    <p><a name="ITEM_1A_RISK_FACTORS"></a>ITEM 1A. RISK FACTORS</p>
    <p>Risk section text.</p>

    <p><a name="ITEM_2_PROPERTIES"></a>ITEM 2. PROPERTIES</p>
    <p>Properties section text.</p>
  </body>
</html>
"""


def test_toc_analyzer_resolves_name_anchors():
    """TOC analyzer should map sections when targets are name anchors."""
    analyzer = TOCAnalyzer()
    mapping = analyzer.analyze_toc_structure(HTML_WITH_NAMED_ANCHORS)

    # Keys are the canonical part-prefixed form; the 10-K schema infers the part
    # from the item number when the TOC has no explicit Part headers (3usf).
    assert mapping.get("part_i_item_1") == "ITEM_1_BUSINESS"
    assert mapping.get("part_i_item_1a") == "ITEM_1A_RISK_FACTORS"
    assert mapping.get("part_i_item_2") == "ITEM_2_PROPERTIES"


def test_parser_uses_toc_with_name_anchors():
    """Parser should expose item sections from TOC when using name anchors.

    Stored keys are canonical (part_i_item_1), but membership and indexing accept
    the bare 'Item 1' form too — Sections.__contains__/__getitem__ resolve it, so
    the part-prefix change is backward compatible (edgartools-3usf)."""
    parser = HTMLParser(ParserConfig(form="10-K"))
    doc = parser.parse(HTML_WITH_NAMED_ANCHORS)

    # Canonical stored keys
    assert "part_i_item_1" in doc.sections
    assert "part_i_item_1a" in doc.sections
    # Backward-compatible bare-form membership and indexing still resolve
    assert "Item 1" in doc.sections
    assert "Item 1A" in doc.sections
    assert "Item 2" in doc.sections
    assert doc.sections["Item 1"] is doc.sections["part_i_item_1"]
