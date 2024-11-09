from functools import lru_cache
from pathlib import Path

import humanize
import orjson as json
import pyarrow.compute as pc
from rich import print

from edgar._filings import Filing, get_filings
from edgar.core import default_page_size
from edgar.entities import *
from edgar.entities import (parse_entity_submissions, CompanyConcept, CompanyFiling, preprocess_company,
                            _parse_cik_lookup_data)


@lru_cache(maxsize=16)
def get_test_company(company_identifier):
    return get_entity(company_identifier)


def test_company_repr():
    company = get_test_company("NVDA")
    print()
    repr_ = repr(company)
    assert 'NVDA' in repr_
    assert 'Large accelerated' in company.__repr__()
    assert '1045810' in company.__repr__()
    assert 'Semiconductors' in company.__repr__()


def test_ticker_display_for_company_with_multiple_tickers():
    company = get_test_company(310522)
    assert "FNMA" in company.tickers
    assert "FNMA" in repr(company)


def test_parse_company_submission_json():
    with Path('data/company_submission.json').open("r") as f:
        cjson = json.loads(f.read())
    company = parse_entity_submissions(cjson)
    assert company.cik == 1318605


def test_get_company_submissions():
    company: CompanyData = get_entity_submissions(1318605)
    assert company
    assert company.cik == 1318605
    filings = company.get_filings()
    assert len(filings) > 1000

    # We can get the earliest filing for TESLA and it is a REGDEX
    filing = filings[-1]
    assert filing.form == "REGDEX"


def test_no_company_for_cik():
    company = Company(-1)
    assert company is None


def test_get_company_with_no_filings():
    company = Company("0000350001")
    assert company.name == "Company Name Three `!#$(),:;=.-;\\|@/{}&'\\WA\\"
    assert company.filings is not None
    assert len(company.filings) == 0


def test_get_company_facts():
    company_facts: CompanyFacts = get_company_facts(1318605)
    assert company_facts
    assert len(company_facts) > 100
    assert "1318605" in str(company_facts)


def test_company_get_facts():
    company = get_test_company("TSLA")
    facts = company.get_facts()
    assert facts
    assert len(facts) > 100


def test_company_get_facts_repr():
    company = get_test_company(1318605)
    facts = company.get_facts()
    facts_repr = str(facts)
    assert 'Tesla' in facts_repr


def test_company_for_cik():
    company: CompanyData = CompanyData.for_cik(1318605)
    assert company
    assert company.cik == 1318605


def test_company_for_ticker():
    company: CompanyData = CompanyData.for_ticker("EXPE")
    assert company
    assert company.cik == 1324424
    assert company.tickers == ['EXPE']


def test_get_company_tickers():
    company_tickers = get_company_tickers()
    assert company_tickers is not None


def test_get_cik_lookup_data():
    cik_lookup = get_cik_lookup_data()
    assert cik_lookup[cik_lookup.cik == 1448632].name.item() == 'ZZIF 2008 INVESTMENT LLC'


def test_parse_cik_lookup_data():
    with Path('data/cik_lookup_data.txt').open(
            "r",
            encoding="utf-8",
            errors="surrogateescape"
    ) as f:
        content = f.read()
    cik_lookups = _parse_cik_lookup_data(content)
    company = cik_lookups[1000]
    print(company)
    assert company
    assert company['cik'] == 1463262
    assert company['name'] == '11:11 CAPITAL CORP.'


def test_company_get_filings():
    company: CompanyData = CompanyData.for_ticker("EXPE")
    company_filings = company.get_filings()
    assert len(company_filings) == len(company.filings)


def test_company_filings_filter_by_date():
    expe = get_test_company("EXPE")
    filings = expe.filings
    filtered_filings = filings.filter(filing_date="2023-01-04:")
    assert not filtered_filings.empty
    assert len(filtered_filings) < len(expe.filings)


def test_company_filter_with_no_results_returns_filings():
    expe = get_test_company("EXPE")
    filings = expe.filings.filter(form="NOTHING")
    assert filings is not None
    assert len(filings) == 0
    latest = filings.latest()
    assert not latest


def test_company_get_filings_for_form():
    company: CompanyData = CompanyData.for_ticker("EXPE")
    tenk_filings: CompanyFilings = company.get_filings(form='10-K')
    assert pc.all(pc.equal(tenk_filings.data['form'], '10-K'))
    filing: CompanyFiling = tenk_filings[0]
    assert filing
    assert filing.form == '10-K'
    assert filing.cik == 1324424
    assert isinstance(filing.accession_no, str)


def test_company_get_form_by_date():
    company: CompanyData = CompanyData.for_ticker("EXPE")
    filings = company.get_filings(filing_date="2022-11-01:2023-01-20")
    assert not filings.empty
    assert len(filings) < len(company.get_filings())

    filings_10k = company.get_filings(filing_date="2022-11-01:2023-01-20", form="10-Q")
    assert len(filings_10k) == 1


def test_company_get_filings_for_multiple_forms():
    company: CompanyData = CompanyData.for_ticker("EXPE")
    company_filings = company.get_filings(form=['10-K', '10-Q', '8-K'])
    form_list = pc.unique(company_filings.data['form']).tolist()
    assert sorted(form_list) == ['10-K', '10-Q', '8-K']


def test_get_company_for_ticker_lowercase():
    company: CompanyData = Company("expe")
    assert company
    assert company.tickers == ["EXPE"]


def test_company_filings_repr():
    company: CompanyData = Company("EXPE")
    expe_filings: CompanyFilings = company.get_filings()
    filings_repr = str(expe_filings)
    assert "Expedia" in filings_repr


def test_get_latest_10k_10q():
    company = Company('NVDA')
    filings: CompanyFilings = company.get_filings(form=["10-K", "10-Q"])
    latest_filings = filings.latest(4)
    assert len(latest_filings) == 4
    print(latest_filings.to_pandas())


def test_filings_latest_one():
    company = Company('NVDA')
    filing = company.get_filings(form='10-Q').latest()
    assert filing.form == '10-Q'
    assert isinstance(filing, Filing)


def test_company_filings_to_pandas():
    company = Company(886744)
    company_filings = company.get_filings()
    filings_df = company_filings.to_pandas()
    print(filings_df.columns)
    assert all(col in filings_df for col in ['form', 'fileNumber', 'items', 'size', 'isXBRL', 'isInlineXBRL'])
    filings_df = company_filings.to_pandas("form", "size")
    assert filings_df.columns.tolist() == ["form", "size"]


def test_company_get_filings_by_file_number():
    company = Company(886744)
    filings_for_file: CompanyFilings = company.get_filings(file_number='333-225184')
    assert filings_for_file
    print(filings_for_file.to_pandas("form", "accessionNumber"))
    filings_df = filings_for_file.to_pandas("filingDate", "form", "fileNumber", "accessionNumber")
    assert 'S-3' in filings_df.form.tolist()
    assert '424B5' in filings_df.form.tolist()


def test_company_get_filings_by_assession_number():
    company = Company(886744)
    filings_for_file: CompanyFilings = company.get_filings(accession_number='0001206774-18-001992')
    assert len(filings_for_file) == 1


def test_get_filings_xbrl():
    company = Company("SNOW")
    xbrl_filings = company.get_filings(is_xbrl=True)
    assert xbrl_filings.to_pandas("isXBRL").isXBRL.all()
    assert company.get_filings(is_xbrl=False).to_pandas().isXBRL.drop_duplicates().tolist() == [False]


def test_get_filings_inline_xbrl():
    company = CompanyData.for_ticker("SNOW")
    xbrl_filings = company.get_filings(is_inline_xbrl=True)
    assert xbrl_filings.to_pandas("isInlineXBRL").isInlineXBRL.all()
    assert company.get_filings(is_xbrl=False).to_pandas().isInlineXBRL.drop_duplicates().tolist() == [False]


def test_get_filings_multiple_filters():
    company = CompanyData.for_ticker("SNOW")
    filings = company.get_filings(form=["10-Q", "10-K"], is_inline_xbrl=True)
    filings_df = filings.to_pandas("form", "filingDate", 'isXBRL', "isInlineXBRL")
    assert filings_df.isInlineXBRL.all()
    assert set(filings_df.form.tolist()) == {"10-Q", "10-K"}


def test_company_filing_get_related_filings():
    company = CompanyData.for_cik(1841925)
    filings = company.get_filings(form=["S-1", "S-1/A"], is_inline_xbrl=True)
    filing = filings[0]
    print(filing)
    related_filings = filing.related_filings()
    assert len(related_filings) > 8
    # They all have the same fileNumber
    file_numbers = list(set(related_filings.data['fileNumber'].to_pylist()))
    assert len(file_numbers) == 1
    assert file_numbers[0] == filing.file_number


def test_get_company_by_cik():
    company = get_entity(1554646)
    assert company.name == 'NEXPOINT SECURITIES, INC.'

    company = Company(1554646)
    assert company.cik == 1554646


def test_get_company_by_ticker():
    company = Company("SNOW")
    assert company.cik == 1640147


def test_get_company_concept():
    concept = get_concept(1640147,
                          taxonomy="us-gaap",
                          concept="AccountsPayableCurrent")
    latest = concept.latest()
    assert len(latest) == 1
    print(latest)
    data = [CompanyConcept.create_fact(row) for row in latest.itertuples()]
    assert len(data) == 1
    assert data[0].form in ['10-Q', '10-K']


def test_get_company_concept_with_taxonomy_missing():
    concept = get_concept(1640147,
                          taxonomy="not-gap",
                          concept="AccountsPayableCurrent")
    assert concept.failure
    assert concept.error == ("not-gap:AccountsPayableCurrent does not exist for company Snowflake Inc. [1640147]. "
                             "See https://fasb.org/xbrl")


def test_get_company_concept_with_concept_missing():
    concept = get_concept(1640147,
                          taxonomy="us-gaap",
                          concept="AccountsPayableDoesNotExist")
    assert concept.failure
    assert concept.error == ("us-gaap:AccountsPayableDoesNotExist does not exist for company Snowflake Inc. [1640147]. "
                             "See https://fasb.org/xbrl")


def test_company_filings_test_company_get_facts_repr():
    company = get_test_company(1318605)
    filings = company.get_filings()
    print(filings)


def test_read_company_filing_index_year_and_quarter():
    company_filings = get_filings(year=2022, quarter=2, index="company")
    assert company_filings
    assert company_filings.data
    assert 500000 > len(company_filings) > 200000

    df = company_filings.to_pandas()
    assert len(df) == len(company_filings) == len(company_filings.data)
    assert company_filings.data.column_names == ['company', 'form', 'cik', 'filing_date', 'accession_number']
    print(company_filings.data.schema)

    print('Bytes', humanize.naturalsize(company_filings.data.nbytes, binary=True))


def test_filings_get_by_index_or_accession_number():
    expe = get_test_company("EXPE")
    filings = expe.filings

    filing: Filing = filings.get("0001225208-23-000231")

    assert int(filing.cik) == int(expe.cik)
    assert filing.accession_no == "0001225208-23-000231"

    # Invalid accession number
    assert filings.get("0001225208-23-") is None

    filing_one_hundred = filings.get(100)
    filing_100 = filings.get("100")
    assert filing_100.accession_no == filing_one_hundred.accession_no


def test_filings_next_and_previous():
    # Get company filings
    company = get_test_company(1318605)
    company_filings = company.get_filings()

    print()
    # Get the next page
    next_page = company_filings.next()
    assert len(next_page) == default_page_size
    print(next_page)

    # Get the next page again
    page3 = company_filings.next()
    print(page3)

    # Get the previous page
    page2_again = company_filings.previous()
    print(page2_again)

    assert next_page[0].accession_no == page2_again[0].accession_no
    # assert filings.previous()
    # assert not filings.previous()

    # Filter the company filings
    eightk_filings = company_filings.filter(form=["8-K"])
    print(eightk_filings.previous())
    print(eightk_filings.previous())
    print(eightk_filings.previous())
    print(eightk_filings.previous())

    print(eightk_filings.next())
    print(eightk_filings.next())
    print(eightk_filings.next())
    print(eightk_filings.next())


def test_preprocess_company():
    assert preprocess_company('Tesla Inc') == 'tesla'
    assert preprocess_company('Apple Hospitality REIT, Inc.') == 'apple hospitality reit'
    assert preprocess_company('ModivCare Inc') == 'modivcare'
    assert preprocess_company('Coliseum Capital Partners II, L.P') == 'coliseum capital partners ii'
    assert preprocess_company('Hartree Partners, LP') == 'hartree partners'
    assert preprocess_company('James River Group Holdings, Ltd.') == 'james river group holdings'
    assert preprocess_company('BANK OF MONTREAL /CAN/') == 'bank of montreal'
    assert preprocess_company('AGCO CORP /DE') == 'agco corp'
    assert preprocess_company('OSHKOSH CORP') == 'oshkosh'
    assert preprocess_company('SEALED AIR CORP/DE') == 'sealed air corp'
    assert preprocess_company('MARINE PRODUCTS CORP') == 'marine products'
    assert preprocess_company('BARCLAYS BANK PLC') == 'barclays bank'
    assert preprocess_company('SIGNATURE SECURITIES GROUP CORPORATION') == 'signature securities group'
    assert preprocess_company('UBS AG') == 'ubs'
    assert preprocess_company('GRABAG') == 'grabag'


def test_company_financials():
    company = Company('AAPL')
    financials = company.financials
    assert financials
    assert financials.get_balance_sheet()
    assert financials.get_income_statement()
    assert financials.get_cash_flow_statement()
    assert financials.get_statement_of_changes_in_equity()


def test_company_with_no_latest_10k_has_no_financials():
    company = Company('TD')
    financials = company.financials
    assert financials is None


def test_iterate_company_filings():
    company = Company('AAPL')
    filings: CompanyFilings = company.get_filings(form='10-K')
    assert isinstance(filings, CompanyFilings)

    # Works even when we call head
    filings = filings.head(4)
    assert isinstance(filings, CompanyFilings)

    # Works even when we call sample
    filings = filings.sample(4)
    assert isinstance(filings, CompanyFilings)

    for filing in filings:
        assert filing


def test_company_to_dict():
    company = Company(1012605)
    company_dict = company.to_dict()
    print(type(company_dict))
    assert company_dict.get('cik') == 1012605
    assert company_dict.get('name') == 'INTEGRINAUTICS'
    assert company_dict.get('display_name') == 'Integrinautics'
    assert 'filings' not in company_dict
    print(company_dict)

    assert 'filings' in company.to_dict(include_filings=True)
