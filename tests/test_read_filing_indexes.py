from edgar.httprequests import download_text, download_file
from edgar._filings import  read_index_file, read_form_index_file, read_company_index_file
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
