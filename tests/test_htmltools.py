"""HTML table helpers and Filing.text()/html()/sections() on awkward filings.

What is left of this file after 6.0 removed the legacy ``edgar.files`` parser:
the ``ChunkedDocument`` and ``html_sections`` tests went with it.
"""
import pandas as pd
from rich import print

from edgar import Filing
from edgar.datatools import table_html_to_dataframe

pd.options.display.max_columns = 12
pd.options.display.max_colwidth = 100
pd.options.display.width = 1000


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


def test_html_sections_from_html_with_table_with_no_tbody():
    filing = Filing(form='3', filing_date='2023-10-10', company='BAM Partners Trust', cik=1861643,
                    accession_no='0001104659-23-108367')
    filing.html()
    sections = filing.sections()
    assert sections


def test_filing_with_pdf_primary_document():
    filing = Filing(form='APP NTC',
                    filing_date='2024-01-29',
                    company='AMG Pantheon Credit Solutions Fund',
                    cik=1995940,
                    accession_no='9999999997-24-000210')
    # This filing has a PDF filing document, so the fix is that html returns None
    html = filing.html()
    assert html is None


def test_html_text_works_with_no_failures():
    # This used to fail because of a bug in the html_to_text function
    filing = Filing(form='10-K', filing_date='2024-01-31', company='ADVANCED MICRO DEVICES INC', cik=2488,
                    accession_no='0000002488-24-000012')
    assert filing.text()
