import pytest

from edgar.entity import get_entity_submissions, Entity, Company
from edgar.entity.data import parse_entity_submissions, CompanyData
from edgar.company_reports import TenK, TenQ
from datetime import datetime
from pathlib import Path
import json


@pytest.fixture
def tsla():
    return Company("TSLA")


def test_parse_entity_submissions():
    with Path("data/company_submission.json").open('r') as f:
        tsla_submissions = json.load(f)
    data:CompanyData = parse_entity_submissions(tsla_submissions)
    assert data
    assert data.industry == 'Motor Vehicles & Passenger Car Bodies'
    assert data.sic == '3711'
    assert data.fiscal_year_end == '1231'

@pytest.mark.network
def test_entity_is_company():

    # Taneja Vaibhav at TSLA
    assert Entity(1771340).is_individual

    # &VEST Domestic Fund II LP
    assert Entity(1800903).is_company

    # Siemens AG
    assert Entity(940418).is_company

    # SIEMENS ENERGY AG/ADR
    assert Entity(1830056).is_company

    # SIEVERT STEPHANIE A
    assert not Entity(1718179).is_company

    assert Entity(1911716).is_company

    # NVC Holdings, LLC
    assert Entity(1940261).is_company

    # FANNIE MAE
    assert Entity(310522).is_company

    # Berkshire Hathaway
    assert Entity(1067983).is_company

    # ORBIMED Advisors LLC
    assert Entity(1055951).is_company

    # 360 Funds
    assert Entity(1319067).is_company

    # Jeronimo Martins
    assert Entity(1438077).is_company

    # Elon Musk
    assert Entity(1494730).is_individual

    # Reed Hastings
    assert Entity('1033331').is_individual

@pytest.mark.network
def test_warren_buffett():
    # Warren Buffett
    warren_buffet = Entity(315090)
    assert warren_buffet.is_individual

@pytest.mark.network
def test_reed_hastings():
    # Reed Hastings
    reed_hastings = Entity('1033331')
    assert reed_hastings.is_individual

@pytest.mark.network
def test_display_name():
    assert Entity(1318605).display_name == "Tesla, Inc."

    assert Entity(1830610).name == 'Michaels Lisa Anne'
    assert Entity(1830610).display_name == "Lisa Anne Michaels"

    assert Entity(1718179).name == "Sievert Stephanie A"
    assert Entity(1718179).display_name == "Stephanie A Sievert"

@pytest.mark.network
def test_ticker_icon():
    entity: Company = Company(320193)
    assert entity.tickers[0] == "AAPL"
    icon = entity.get_icon()
    assert icon is not None
    assert isinstance(icon, bytes)
    assert icon[:8] == b"\x89PNG\r\n\x1a\n"

    entity: Company = Company(1465740)
    assert entity.tickers[0] == "TWO"
    icon = entity.get_icon()
    assert icon is None

@pytest.mark.network
def test_get_entity_by_ticker():
    # Activision was acquired by Microsoft so possibly this ticker will be removed in the future
    c = Company("AAPL")
    assert c.cik == 320193
    assert c.industry == "Electronic Computers"
    assert c.data.sic == "3571"
    assert c.sic == "3571"

@pytest.mark.network
def test_get_entity_by_ticker_with_stock_class():
    assert Company("BRK.B").cik == 1067983
    assert Company("BRK-B").cik == 1067983
    assert Company("BRK").cik == 1067983
    assert Company("AAPL").cik == 320193
    assert Company("ETI.P").cik == 1427437

@pytest.mark.network
def test_getting_company_financials_does_not_load_additional_filings():
    c = Company("KO")
    f = c.get_financials()
    assert f
    assert not c._data._loaded_all_filings

@pytest.mark.network
def test_get_latest_company_reports():
    c = Company(1318605)
    tenk = c.latest_tenk
    assert tenk
    assert isinstance(tenk, TenK)
    tenq = c.latest_tenq
    assert tenq
    assert isinstance(tenq, TenQ)

@pytest.mark.network
def test_company_repr():
    c= Company(789019)
    c_repr = repr(c)
    print()
    print(c_repr)
    assert "MICROSOFT CORP" in c_repr
    assert 'MSFT' in c_repr  # Ticker should be displayed
    assert 'Industry' in c_repr  # Industry section

@pytest.mark.network
def test_individual_repr():
    i = Entity(1771340)
    i_repr = repr(i)
    print()
    print(i_repr)
    assert "Vaibhav" in i_repr

@pytest.mark.network
def test_filter_by_accession_number():
    # A TSLA filing
    c = Company(1318605)
    filing = c.get_filings().filter(accession_number="0002007317-24-000625")
    assert filing

@pytest.mark.network
def test_company_filing_acceptance_datetime():
    c = Company(1318605)
    assert c.get_filings().data['acceptanceDateTime']
    acceptance_datetime = c.get_filings().data['acceptanceDateTime'][0].as_py()
    assert isinstance(acceptance_datetime, datetime)

@pytest.mark.network
def test_filter_by_year(tsla):
    filings = tsla.get_filings(year=2024)
    assert len(filings) > 0
    assert all(filing.filing_date.year == 2024 for filing in filings)

@pytest.mark.network
def test_filter_by_quarter(tsla):
    filings = tsla.get_filings(year=2024, quarter=1)
    assert len(filings) > 0
    assert all(filing.filing_date.year == 2024 and filing.filing_date.month in [1, 2, 3] for filing in filings)
