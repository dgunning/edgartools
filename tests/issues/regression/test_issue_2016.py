"""Physical HTML cells preserve filed Inline XBRL fact identities.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2016
"""

import pytest
from lxml import etree, html

from edgar.documents import ParserConfig, parse_html
from edgar.documents.strategies.table_processing import TableProcessor
from edgar.documents.table_nodes import Cell
from tests.paths import FIXTURES_DIR

pytestmark = pytest.mark.fast

ORACLE_FIXTURE = FIXTURES_DIR / "html/orcl/orcl-20260831-emea-footnote.htm"
ORACLE_EMEA = {
    "3,726": ("F_e5ad0eec-ea21-4999-af73-6f88d9d58b39", "3726000000"),
    "3,481": ("F_cace6d6c-edc2-44eb-a621-7294332f6c6a", "3481000000"),
}
EMEA_FOOTNOTE = "FNT_12dd46b5-2e60-4de4-841f-82be60a2a99e"


def find_cell(table, row_label, cell_text):
    return next(
        cell
        for row in table.rows
        if row.cells[0].text() == row_label
        for cell in row.cells
        if cell.text() == cell_text
    )


def test_oracle_emea_cells_lead_to_their_filed_footnote():
    """Oracle Form 10-Q, accession 0001193125-26-389274, Note 9."""
    doc = parse_html(ORACLE_FIXTURE.read_text(encoding="utf-8"))
    note_table, _ = doc.tables
    facts = {fact.fact_id: fact for fact in doc.xbrl_facts}

    for display, (fact_id, value) in ORACLE_EMEA.items():
        cell = find_cell(note_table, "EMEA(1)", display)
        assert cell.numeric_value == float(display.replace(",", ""))
        assert cell.xbrl_fact_ids == (fact_id,)

        fact = facts[cell.xbrl_fact_ids[0]]
        assert fact.value == value
        assert fact.footnotes == [EMEA_FOOTNOTE]
        assert doc.xbrl_footnotes[fact.footnotes[0]].text == (
            "Comprises Europe, the Middle East and Africa"
        )


def test_oracle_markers_and_untagged_repeat_do_not_borrow_fact_ids():
    doc = parse_html(ORACLE_FIXTURE.read_text(encoding="utf-8"))
    note_table, mda_table = doc.tables

    assert find_cell(note_table, "EMEA(1)", "EMEA(1)").xbrl_fact_ids == ()
    assert find_cell(mda_table, "EMEA(1)", "EMEA(1)").xbrl_fact_ids == ()
    for display in ORACLE_EMEA:
        assert find_cell(mda_table, "EMEA(1)", display).xbrl_fact_ids == ()

    # A real fact can belong to a cell without having any filed footnote.
    americas = find_cell(note_table, "Americas", "13,711")
    assert len(americas.xbrl_fact_ids) == 1
    americas_fact, = (
        fact for fact in doc.xbrl_facts if fact.fact_id == americas.xbrl_fact_ids[0]
    )
    assert americas_fact.value == "13711000000"
    assert americas_fact.footnotes == []


@pytest.mark.parametrize("table_extraction", [True, False], ids=["advanced", "basic"])
def test_cell_keeps_its_own_inline_fact_ids_in_source_order(table_extraction):
    markup = """<html><body><ix:nonNumeric id="ancestor" name="t:TextBlock">
      <table><tr>
        <td><span><ix:nonFraction id="b" name="t:Amount">7</ix:nonFraction></span>
          <ix:nonNumeric id="a" name="t:Label">label</ix:nonNumeric>
          <ix:nonFraction id="b" name="t:Other">8</ix:nonFraction>
          <ix:fraction id="fraction" name="t:Fraction"><ix:numerator>1</ix:numerator>
            <ix:denominator>2</ix:denominator></ix:fraction>
          <ix:nonFraction name="t:NoID">9</ix:nonFraction>
          <ix:nonFraction id="" name="t:EmptyID">9</ix:nonFraction>
          <ix:nonFraction id=" " name="t:BlankID">9</ix:nonFraction>
          <ix:footnote id="resource">note resource</ix:footnote>
          <ix:continuation id="continued">continuation</ix:continuation>
          <ix:hidden><ix:nonFraction id="hidden" name="t:Amount">10</ix:nonFraction></ix:hidden>
          <table><tr><td><ix:nonFraction id="nested" name="t:Amount">11</ix:nonFraction></td></tr></table>
        </td>
      </tr></table></ix:nonNumeric></body></html>"""
    doc = parse_html(markup, ParserConfig(table_extraction=table_extraction))
    cell = doc.tables[0].rows[0].cells[0]

    # The enclosing fact and the nested cell's fact belong to different elements.
    assert cell.xbrl_fact_ids == ("b", "a", "b", "fraction")


def test_manual_cell_keeps_existing_rendering_and_equality():
    cell = Cell("3,726", xbrl_fact_ids=("fact",))
    plain = Cell("3,726")

    assert plain.xbrl_fact_ids == ()
    assert cell == plain
    assert repr(cell) == repr(plain)
    assert cell.text() == "3,726"
    assert cell.html() == "<td>3,726</td>"
    assert cell.numeric_value == 3726


def test_toc_section_tables_keep_distinct_facts_with_equal_displayed_values():
    """NIKE Form 10-K, accession 0000320187-25-000047, Item 8."""
    fixture = FIXTURES_DIR / "html/nke/10k/nke-10-k-2025-07-17.html"
    doc = parse_html(fixture.read_bytes(), ParserConfig(form="10-K"))
    section = doc.sections["part_ii_item_8"]
    assert section.detection_method == "toc"

    ids = [
        cell.xbrl_fact_ids
        for table in section.tables()
        for row in table.rows
        if row.cells[0].text() == "Net income"
        for cell in row.cells
        if cell.text() == "3,219"
    ]
    assert ids == [("f-101",), ("f-185",), ("f-365",), ("f-366",)]


def test_cell_keeps_fact_in_namespace_aware_inline_child():
    table = html.fromstring("<table><tr><td>Example</td><td></td></tr></table>")
    value_cell = table.xpath(".//td")[1]
    namespace = "{http://www.xbrl.org/2013/inlineXBRL}"
    etree.SubElement(value_cell, namespace + "nonFraction", id="visible").text = "7"
    hidden = etree.SubElement(value_cell, namespace + "hidden")
    etree.SubElement(hidden, namespace + "nonFraction", id="hidden").text = "8"

    parsed = TableProcessor(ParserConfig()).process(table)
    assert parsed.rows[0].cells[1].xbrl_fact_ids == ("visible",)
