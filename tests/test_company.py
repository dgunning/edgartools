import json
from pathlib import Path

import pyarrow.compute as pc
import pyarrow as pa
from rich import print

from edgar.company import *
from edgar.company import parse_company_submissions
from edgar.filing import Filing


def test_parse_company_submission_json():
    with Path('data/company_submission.json').open("r") as f:
        cjson = json.load(f)
    company = parse_company_submissions(cjson)
    print()
    print(company)


def test_get_company_submissions():
    company: Company = get_company_submissions(1318605)
    assert company
    assert company.cik == 1318605
    print(company)


def test_get_company_facts():
    company_facts: CompanyFacts = get_company_facts(1318605)
    assert company_facts
    assert len(company_facts) > 100
    assert "1318605" in str(company_facts)


def test_get_company_facts_db():
    company_facts: CompanyFacts = get_company_facts(1318605)
    db = company_facts.db()
    df = db.execute("""
    select * from facts
    """).df()
    print()
    print(df)
    assert not df.start.isnull().all()
    assert not df.end.isnull().all()


def test_company_for_cik():
    company: Company = Company.for_cik(1318605)
    assert company
    assert company.cik == 1318605


def test_company_for_ticker():
    company: Company = Company.for_ticker("EXPE")
    print(company)
    assert company
    assert company.cik == 1324424
    assert company.tickers == ['EXPE']


def test_get_company_tickers():
    company_tickers = get_company_tickers()
    print()
    print(company_tickers)


def test_company_get_filings():
    company: Company = Company.for_ticker("EXPE")
    company_filings = company.get_filings()
    assert len(company_filings) == len(company.filings)


def test_company_get_filings_for_form():
    company: Company = Company.for_ticker("EXPE")
    tenk_filings: CompanyFilings = company.get_filings(form='10-K')
    print(tenk_filings)
    assert pc.all(pc.equal(tenk_filings.filing_index['form'], '10-K'))
    filing: Filing = tenk_filings[0]
    assert filing
    assert filing.form == '10-K'
    assert filing.cik == 1324424
    assert isinstance(filing.date, str)
    assert isinstance(filing.accession_no, str)


def test_company_get_filings_for_multiple_forms():
    company: Company = Company.for_ticker("EXPE")
    company_filings = company.get_filings(form=['10-K', '10-Q', '8-K'])
    print(company_filings)
    form_list = pc.unique(company_filings.filing_index['form']).tolist()
    assert sorted(form_list) == ['10-K', '10-Q', '8-K']


def test_get_company_for_ticker_lowercase():
    company: Company = Company.for_ticker("expe")
    assert company
    assert company.tickers == ["EXPE"]


def test_company_filings_repr():
    company: Company = Company.for_ticker("EXPE")
    expe_filings: CompanyFilings = company.get_filings()
    filings_repr = str(expe_filings)
    assert "Expedia" in filings_repr


def test_get_latest_10k_10q():
    company = Company.for_ticker('NVDA')
    filings: CompanyFilings = company.get_filings(form=["10-K", "10-Q"])
    latest_filings = filings.latest(4)
    assert len(latest_filings) == 4
    print(latest_filings.to_pandas())


def test_filings_latest_one():
    company = Company.for_ticker('NVDA')
    filing = company.get_filings(form='10-Q').latest()
    assert filing.form == '10-Q'
    assert isinstance(filing, Filing)


def test_company_filings_to_pandas():
    company = Company.for_cik(886744)
    company_filings = company.get_filings()
    filings_df = company_filings.to_pandas()
    print(filings_df.columns)
    assert all(col in filings_df for col in ['form', 'fileNumber', 'items', 'size', 'isXBRL', 'isInlineXBRL'])
    filings_df = company_filings.to_pandas("form", "size")
    assert filings_df.columns.tolist() == ["form", "size"]


def test_company_get_filings_by_file_number():
    company = Company.for_cik(886744)
    filings_for_file: CompanyFilings = company.get_filings(file_number='333-225184')
    assert filings_for_file
    print(filings_for_file.to_pandas("form", "accessionNumber"))
    filings_df = filings_for_file.to_pandas("filingDate", "form", "fileNumber", "accessionNumber")
    assert 'S-3' in filings_df.form.tolist()
    assert '424B5' in filings_df.form.tolist()


def test_company_get_filings_by_assession_number():
    company = Company.for_cik(886744)
    filings_for_file: CompanyFilings = company.get_filings(accession_number='0001206774-18-001992')
    assert len(filings_for_file) == 1


def test_get_filings_xbrl():
    company = Company.for_ticker("SNOW")
    xbrl_filings = company.get_filings(is_xbrl=True)
    assert xbrl_filings.to_pandas("isXBRL").isXBRL.all()
    assert company.get_filings(is_xbrl=False).to_pandas().isXBRL.drop_duplicates().tolist() == [False]


def test_get_filings_inline_xbrl():
    company = Company.for_ticker("SNOW")
    xbrl_filings = company.get_filings(is_inline_xbrl=True)
    assert xbrl_filings.to_pandas("isInlineXBRL").isInlineXBRL.all()
    assert company.get_filings(is_xbrl=False).to_pandas().isInlineXBRL.drop_duplicates().tolist() == [False]


def test_get_filings_multiple_filters():
    company = Company.for_ticker("SNOW")
    filings = company.get_filings(form=["10-Q", "10-K"], is_inline_xbrl=True)
    filings_df = filings.to_pandas("form", "filingDate", 'isXBRL', "isInlineXBRL")
    assert filings_df.isInlineXBRL.all()
    assert set(filings_df.form.tolist()) == {"10-Q", "10-K"}