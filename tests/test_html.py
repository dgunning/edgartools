from edgar.htmltools import extract_elements, table_html_to_dataframe, html_to_text, get_table_elements, get_text_elements,html_sections
from pathlib import Path
from rich import print
import pandas as pd
from edgar import Filing

pd.options.display.max_columns = 12

Nvidia_2021_10k = Path("data/Nvidia.10-K.html").read_text()


def test_html2df():
    table_html = """
    <table>
  <thead>
    <tr>
        <td>id</td><td>name</td><td>age</td>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>1</td><td>John</td><td>20</td>
    </tr>
    <tr>
        <td>2</td><td>Smith</td><td>30</td>
    </tr>
  </tbody>
</table>
    """
    df = table_html_to_dataframe(table_html)
    assert len(df) == 3
    print(df)


def test_tricky_table_html2_dataframe():
    table_html = """<table><br><tbody><br><tr><td></td><td></td><td>Item 5.02</td><td></td><td></td><td></td><td>Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements of Certain Officers.</td><td></td><td></td></tr><br></tbody><br></table>"""
    df = table_html_to_dataframe(table_html)
    print(df)

def test_extract_elements():
    elements = extract_elements(Nvidia_2021_10k)

    table_elements = get_table_elements(elements)
    assert all([e.table is not None for e in table_elements])

    text_elements = get_text_elements(elements)
    assert all([e.type == "text" for e in text_elements])

    assert len(table_elements) + len(text_elements) == len(elements)


def test_html2text():
    tenk_text = html_to_text(Nvidia_2021_10k)

    # Include tables
    tenk_text_with_tables = html_to_text(Nvidia_2021_10k, ignore_tables=False)

    assert len(tenk_text_with_tables) > len(tenk_text)
    print(tenk_text_with_tables)


def test_get_table_elements():
    filing = Filing(company='Tesla, Inc.', cik=1318605, form='10-K',
                    filing_date='2023-01-31', accession_no='0000950170-23-001409')
    elements = extract_elements(filing.html())
    table_elements = get_table_elements(elements)
    assert len(table_elements) > 50
    print(len(table_elements))


def test_html_sections_includes_all_tables():
    filing = Filing(form='8-K', filing_date='2023-10-10', company='ACELRX PHARMACEUTICALS INC', cik=1427925,
                    accession_no='0001437749-23-027971')
    html_text = filing.html()
    sections = html_sections(html_text)
    for section in sections:
        if "Item" in section:
            print(section)


def test_html_sections_from_difficult_html():
    filing = Filing(form='3', filing_date='2023-10-10', company='BAM Partners Trust', cik=1861643,
           accession_no='0001104659-23-108367')
    sections = filing.sections()
    assert sections