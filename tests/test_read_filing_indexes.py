from edgar.httprequests import download_file
from edgar._filings import  read_index_file, read_form_index_file, read_company_index_file
import pandas as pd
from pathlib import Path


def test_read_index_file():
    text = Path("data/badform.idx.txt").read_text()
    table = read_index_file(text)
    assert len(table) == 9
    df = table.to_pandas()
    assert df.iloc[5].company == "UNITED PLANNERS' FINANCIAL SERVICES OF AMERICA A LIMITED PARTNER"


def test_read_form_index_file():
    text = Path("data/form.2020QTR1.idx").read_text()
    table = read_form_index_file(text)
    df = table.to_pandas()
    united_planner_rows = df.query("cik==820694")
    assert len(united_planner_rows) == 2


def test_read_company_index_file():
    text = Path("data/company.2020QTR1.idx").read_text()
    table = read_company_index_file(text)
    df = table.to_pandas()
    united_planner_rows = df.query("cik==820694")
    assert len(united_planner_rows) == 2


def test_read_quarterly_filing_index():
    "https://www.sec.gov/Archives/edgar/full-index/{}/QTR{}/{}.{}"
    table = read_index_file(Path("data/form.2024QTR4.idx").read_text())
    df = table.to_pandas()
    boa_ciks = [1652031, 1673542, 1694649]
    boa_records = df[df.cik.isin(boa_ciks)][['cik', 'company', 'form']]
    assert len(boa_records) == 8
    assert boa_records.iloc[0].company == 'Bank of America Merrill Lynch Commercial Mortgage Trust 2015-UBS7'

def test_forms_with_spaces_are_read_correctly():
    table = read_index_file(Path("data/form.2024QTR4.idx").read_text())
    df = table.to_pandas()
    form_1A_POS = df[df.form == "1-A POS"]
    assert len(form_1A_POS) > 0

