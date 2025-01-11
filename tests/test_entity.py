from edgar.entities import get_entity_submissions, Entity, Company
from edgar.company_reports import TenK, TenQ
from datetime import datetime

def test_entity_is_company():
    # TSLA
    assert get_entity_submissions(1318605).is_company

    # Taneja Vaibhav at TSLA
    assert not get_entity_submissions(1771340).is_company

    # &VEST Domestic Fund II LP
    assert get_entity_submissions(1800903).is_company

    # Siemens AG
    assert get_entity_submissions(940418).is_company

    # SIEMENS ENERGY AG/ADR
    assert get_entity_submissions(1830056).is_company

    # SIEVERT STEPHANIE A
    assert not get_entity_submissions(1718179).is_company

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


def test_warren_buffett():
    # Warren Buffett
    warren_buffet = Entity(315090)
    assert warren_buffet.is_individual


def test_display_name():
    assert Entity(1318605).display_name == "Tesla, Inc."

    assert Entity(1830610).name == 'Michaels Lisa Anne'
    assert Entity(1830610).display_name == "Lisa Anne Michaels"

    assert Entity(1718179).name == "Sievert Stephanie A"
    assert Entity(1718179).display_name == "Stephanie A Sievert"


def test_insider_transaction_for_entity():
    entity: Entity = Entity(1940261)
    assert entity.name == "NVC Holdings, LLC"
    assert not entity.insider_transaction_for_issuer_exists
    assert entity.insider_transaction_for_owner_exists

    entity = Entity(1599916)
    assert not entity.is_company
    assert not entity.insider_transaction_for_issuer_exists
    assert entity.insider_transaction_for_owner_exists
    assert entity.name == "DeNunzio Jeffrey"

def test_ticker_icon():
    entity: Entity = Entity(320193)
    assert entity.tickers[0] == "AAPL"
    icon = entity.icon
    assert icon is not None
    assert isinstance(icon, bytes)
    assert icon[:8] == b"\x89PNG\r\n\x1a\n"

    entity: Entity = Entity(1465740)
    assert entity.tickers[0] == "TWO"
    icon = entity.icon
    assert icon is None


def test_get_entity_by_ticker():
    # Activision was acquired by Microsoft so possibly this ticker will be removed in the future
    assert Company("ATVI").cik == 718877
    assert Company("AAPL").cik == 320193


def test_get_entity_by_ticker_with_stock_class():
    assert Company("BRK.B").cik == 1067983
    assert Company("BRK-B").cik == 1067983
    assert Company("BRK").cik == 1067983
    assert Company("AAPL").cik == 320193
    assert Company("ETI.P").cik == 1427437


def test_getting_company_financials_does_not_load_additional_filings():
    c = Company("KO")
    f = c.financials
    assert f
    assert not c._loaded_all_filings


def test_get_latest_company_reports():
    c = Company(1318605)
    tenk = c.latest_tenk
    assert tenk
    assert isinstance(tenk, TenK)
    tenq = c.latest_tenq
    assert tenq
    assert isinstance(tenq, TenQ)


def test_company_repr():
    c= Company(789019)
    c_repr = repr(c)
    print()
    print(c_repr)
    assert "MICROSOFT CORP" in c_repr

def test_individual_repr():
    i = Entity(1771340)
    i_repr = repr(i)
    print()
    print(i_repr)
    assert "Vaibhav" in i_repr


def test_filter_by_accession_number():
    # A TSLA filing
    c = Company(1318605)
    filing = c.filings.filter(accession_number="0002007317-24-000625")
    assert filing

def test_company_filing_acceptance_datetime():
    c = Company(1318605)
    assert c.filings.data['acceptanceDateTime']
    acceptance_datetime = c.filings.data['acceptanceDateTime'][0].as_py()
    assert isinstance(acceptance_datetime, datetime)

def test_handle_empty_company_facts():
    c = Company('CGTL')
    facts = c.get_facts()
    assert not facts