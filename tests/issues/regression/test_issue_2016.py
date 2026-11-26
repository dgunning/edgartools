"""Physical HTML cells preserve filed Inline XBRL fact identities.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2016
"""

import pytest
from lxml import etree, html

from edgar.documents import ParserConfig, parse_html
from edgar.documents.strategies.table_processing import TableProcessor
from edgar.documents.table_nodes import Cell
from tests.paths import FIXTURES_DIR, REPO_ROOT

pytestmark = pytest.mark.fast

# https://www.sec.gov/Archives/edgar/data/1341439/000095017024104905/orcl-20240831.htm
ORACLE_FIXTURE = REPO_ROOT / "data/html/Oracle.10-Q.html"
ORACLE_EMEA = {
    "3,228": ("F_b8604f4b-10f0-4509-8e6a-4b2044b63073", "3228000000"),
    "3,005": ("F_6c2fb952-8c5e-4ea5-a1c3-e998c3f20684", "3005000000"),
}
EMEA_FOOTNOTE = "FNT_101dfb5e-8641-4a4f-a4a3-578450fa445b"


@pytest.fixture(scope="module")
def oracle_document():
    return parse_html(ORACLE_FIXTURE.read_bytes(), ParserConfig(form="10-Q"))


def find_cell(table, row_label, cell_text):
    return next(
        cell
        for row in table.rows
        if row.cells[0].text() == row_label
        for cell in row.cells
        if cell.text() == cell_text
    )


def test_oracle_emea_cells_lead_to_their_filed_footnote(oracle_document):
    """Oracle Form 10-Q, filed September 10, 2024, accession 0000950170-24-104905, Note 7."""
    note_table = oracle_document.tables[17]
    facts = {fact.fact_id: fact for fact in oracle_document.xbrl_facts}

    for display, (fact_id, value) in ORACLE_EMEA.items():
        cell = find_cell(note_table, "EMEA(1)", display)
        assert cell.numeric_value == float(display.replace(",", ""))
        assert cell.xbrl_fact_ids == (fact_id,)

        fact = facts[cell.xbrl_fact_ids[0]]
        assert fact.value == value
        assert fact.footnotes == [EMEA_FOOTNOTE]
        assert oracle_document.xbrl_footnotes[fact.footnotes[0]].text == (
            "Comprised of Europe, the Middle East and Africa"
        )

        reverse_cell, = (
            candidate
            for table in oracle_document.tables
            for row_cells in table.headers + [row.cells for row in table.rows + table.footer]
            for candidate in row_cells
            if fact_id in candidate.xbrl_fact_ids
        )
        assert reverse_cell is cell


def test_oracle_markers_and_untagged_repeat_do_not_borrow_fact_ids(oracle_document):
    note_table = oracle_document.tables[17]
    mda_table = oracle_document.tables[21]

    assert find_cell(note_table, "EMEA(1)", "EMEA(1)").xbrl_fact_ids == ()
    assert find_cell(mda_table, "EMEA(1)", "EMEA(1)").xbrl_fact_ids == ()
    for display in ORACLE_EMEA:
        assert find_cell(mda_table, "EMEA(1)", display).xbrl_fact_ids == ()

    # A real fact can belong to a cell without having any filed footnote.
    americas = find_cell(note_table, "Americas", "8,372")
    assert len(americas.xbrl_fact_ids) == 1
    americas_fact, = (
        fact for fact in oracle_document.xbrl_facts if fact.fact_id == americas.xbrl_fact_ids[0]
    )
    assert americas_fact.value == "8372000000"
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


@pytest.mark.parametrize("nested_tag", ["td", "th"])
def test_basic_table_keeps_nested_cells_out_of_its_outer_grid(nested_tag):
    markup = f"""<table><tbody><tr>
      <td>Outer<ix:nonNumeric id="A" name="t:Label">a</ix:nonNumeric>
        <table><caption>Nested caption</caption><tr>
          <{nested_tag}>Inner<ix:nonNumeric id="B" name="t:Label">b</ix:nonNumeric></{nested_tag}>
        </tr></table>
      </td>
      <td>After<ix:nonNumeric id="C" name="t:Label">c</ix:nonNumeric></td>
    </tr></tbody></table>"""
    doc = parse_html(markup, ParserConfig(table_extraction=False))
    outer, = doc.tables

    rows = [[cell.xbrl_fact_ids for cell in row.cells] for row in outer.rows]
    reverse_matches = [
        cell for cells in [*outer.headers, *(row.cells for row in outer.rows)]
        for cell in cells if "B" in cell.xbrl_fact_ids
    ]
    assert (rows, len(reverse_matches)) == ([[("A",), ("C",)]], 0)
    assert not outer.headers
    assert outer.caption is None
    assert [" ".join(cell.text().split()) for cell in outer.rows[0].cells] == [
        "Outera Nested caption Innerb", "Afterc",
    ]
    assert [fact.fact_id for fact in doc.xbrl_facts] == ["A", "B", "C"]


@pytest.mark.parametrize(
    ("table_extraction", "expected_header", "rendered_header"),
    [
        (False, [("Period", ("period",)), ("Label", ("label",))],
         "<tr><td>Period</td><th>Label</th></tr>"),
        (True, [("Label", ("label",)), ("Period", ("period",))],
         "<tr><th>Label</th><th>Period</th></tr>"),
    ],
    ids=["basic", "advanced"],
)
def test_table_preserves_mixed_header_fact_ownership(
    table_extraction, expected_header, rendered_header
):
    markup = """<table><caption>Metrics</caption>
      <thead><tr>
        <th><ix:nonNumeric id="label" name="t:Label">Label</ix:nonNumeric></th>
        <td><ix:nonNumeric id="period" name="t:Period">Period</ix:nonNumeric></td>
      </tr></thead>
      <tbody><tr><td>Example</td><td>42</td></tr></tbody>
    </table>"""
    doc = parse_html(markup, ParserConfig(table_extraction=table_extraction))
    table, = doc.tables
    header, = table.headers

    assert table.caption == "Metrics"
    assert [(cell.text(), cell.xbrl_fact_ids) for cell in header] == expected_header
    assert table.rows[0].cells[1].numeric_value == 42
    assert rendered_header in table.html()
    assert "<tr><td>Example</td><td>42</td></tr>" in table.html()
