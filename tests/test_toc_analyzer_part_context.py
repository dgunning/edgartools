from pathlib import Path

import pytest

from edgar.documents import ParserConfig, parse_html
from edgar.documents.utils.toc_analyzer import TOCAnalyzer


def test_infers_part_from_standalone_rows_in_toc():
    html = """
    <html><body>
      <table>
        <tr><td>PART I</td></tr>
        <tr><td>Item 1.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>Item 1A.</td><td><a href="#i1a">Risk Factors</a></td></tr>
        <tr><td>Item 2.</td><td><a href="#i2">Properties</a></td></tr>
        <tr><td>Item 3.</td><td><a href="#i3">Legal Proceedings</a></td></tr>
        <tr><td>Item 4.</td><td><a href="#i4">Mine Safety Disclosures</a></td></tr>
        <tr><td>PART II</td></tr>
        <tr><td>Item 5.</td><td><a href="#i5">Market for Registrant's Common Equity</a></td></tr>
      </table>
      <h2 id="i1">ITEM 1. BUSINESS</h2>
      <h2 id="i1a">ITEM 1A. RISK FACTORS</h2>
      <h2 id="i2">ITEM 2. PROPERTIES</h2>
      <h2 id="i3">ITEM 3. LEGAL PROCEEDINGS</h2>
      <h2 id="i4">ITEM 4. MINE SAFETY DISCLOSURES</h2>
      <h2 id="i5">ITEM 5. MARKET FOR REGISTRANT'S COMMON EQUITY</h2>
    </body></html>
    """

    mapping = TOCAnalyzer().analyze_toc_structure(html)

    assert "part_i_item_1" in mapping
    assert "part_i_item_4" in mapping
    assert "part_ii_item_5" in mapping


def test_infers_part_when_part_row_has_page_number_cell():
    html = """
    <html><body>
      <table>
        <tr><td>PART I</td><td>3</td></tr>
        <tr><td>Item 1.</td><td><a href="#i1">Business</a></td><td>4</td></tr>
        <tr><td>PART II</td><td>20</td></tr>
        <tr><td>Item 5.</td><td><a href="#i5">Market for Registrant's Common Equity</a></td><td>21</td></tr>
      </table>
      <h2 id="i1">ITEM 1. BUSINESS</h2>
      <h2 id="i5">ITEM 5. MARKET FOR REGISTRANT'S COMMON EQUITY</h2>
    </body></html>
    """

    mapping = TOCAnalyzer().analyze_toc_structure(html)

    assert "part_i_item_1" in mapping
    assert "part_ii_item_5" in mapping


def test_msft_10k_fixture_part_metadata_end_to_end():
    fixture_path = Path("tests/fixtures/html/msft/10k/msft-10-k-2025-07-30.html")
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    html = fixture_path.read_text(encoding="utf-8")
    doc = parse_html(html, config=ParserConfig(form="10-K", detect_sections=True))

    assert "part_i_item_1" in doc.sections
    assert doc.sections["part_i_item_1"].part == "I"
    assert "part_ii_item_5" in doc.sections
    assert doc.sections["part_ii_item_5"].part == "II"
