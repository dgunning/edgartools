import json
from pathlib import Path

import pyarrow.compute as pc
from rich import print

from edgar.company import *
from edgar.company import parse_company_submissions
from edgar.filing import Filing


def test_parse_company_submission_json():
    # Company.parse_company_json()
    with Path('docs/company_submission.json').open("r") as f:
        cjson = json.load(f)
    # print(cjson)
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
    tenk_filings = company.get_filings('10-K')
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
    company_filings = company.get_filings('10-K', '10-Q', '8-K')
    print(company_filings)
    form_list = pc.unique(company_filings.filing_index['form']).tolist()
    assert sorted(form_list) == ['10-K', '10-Q', '8-K']


def test_company_filings_repr():
    company: Company = Company.for_ticker("EXPE")
    expe_filings = company.get_filings()
    # filings_repr = str(filings)


def test_get_latest_10K_10Q():
    company = Company.for_ticker('NVDA')
    filings = company.get_filings("10-K", "10-Q")
    print(filings)
