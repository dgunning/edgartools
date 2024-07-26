import asyncio

import pytest

from edgar import Filing
from edgar.xbrl import XBRLData, XBRLInstance, StatementData, Statements, Financials


@pytest.fixture(scope='module')
def apple_xbrl():
    filing: Filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2023-11-03',
                            accession_no='0000320193-23-000106')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def netflix_xbrl():
    filing: Filing = Filing(company='NETFLIX INC', cik=1065280, form='10-Q', filing_date='2024-04-22',
                            accession_no='0001065280-24-000128')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def crowdstrike_xbrl():
    filing = Filing(company='CrowdStrike Holdings, Inc.', cik=1535527, form='10-K', filing_date='2024-03-07',
                    accession_no='0001535527-24-000007')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def orcl_xbrl():
    filing = Filing(company='ORACLE CORP', cik=1341439, form='10-K', filing_date='2024-06-20',
                    accession_no='0000950170-24-075605')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def msft_xbrl():
    filing = Filing(company='MICROSOFT CORP', cik=789019, form='10-K', filing_date='2023-07-27',
                    accession_no='0000950170-23-035122')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.mark.asyncio
async def test_get_shareholder_equity_statement_for_10K(apple_xbrl):
    statement: StatementData = Financials(apple_xbrl).get_statement_of_changes_in_equity()
    assert statement
    assert len(statement.data) == 18


@pytest.mark.asyncio
def test_get_statement_name(apple_xbrl):
    financials = Financials(apple_xbrl)
    statement: StatementData = financials.get_cash_flow_statement()
    assert statement.get_statement_name() == 'CONSOLIDATED STATEMENTS OF CASH FLOWS'
    assert financials.get_statement_of_changes_in_equity().get_statement_name() == 'CONSOLIDATED STATEMENTS OF SHAREHOLDERS EQUITY'


@pytest.mark.asyncio
async def test_statement_get_concept_value(apple_xbrl):
    statement: StatementData = Financials(apple_xbrl).get_statement_of_changes_in_equity()
    concept = statement.get_concept('us-gaap_NetIncomeLoss')
    assert concept.value.get('2023') == '96995000000'
    assert concept.value.get('2022') == '99803000000'
    assert concept.value.get('2021') == '94680000000'
    assert concept.label == 'Net income'
    # try with "NetIncomeLoss"
    concept = statement.get_concept('NetIncomeLoss')
    assert concept


def test_get_balance_sheet(apple_xbrl):
    balance_sheet: StatementData = Financials(apple_xbrl).get_balance_sheet()
    assert balance_sheet.periods == ['2023', '2022']


def test_cover_page_aapl(apple_xbrl):
    cover_page = apple_xbrl.get_statement('CoverPage')
    assert cover_page is not None
    assert cover_page.get_concept(label='Entity Registrant Name').values == ['Apple Inc.']


def test_get_concept_using_label(apple_xbrl):
    cover_page: StatementData = apple_xbrl.get_statement('CoverPage', include_concept=True)
    assert cover_page is not None
    fact = cover_page.get_concept(label='Entity Registrant Name')
    assert fact.value['2023'] == 'Apple Inc.'
    assert fact.name == 'dei_EntityRegistrantName'


def test_statements_property(apple_xbrl):
    statements: Statements = apple_xbrl.statements
    assert len(statements) == 78
    assert 'CoverPage' in statements


def test_10Q_filings_have_quarterly_dates(netflix_xbrl):
    balance_sheet: StatementData = Financials(netflix_xbrl).get_balance_sheet()
    assert balance_sheet.periods == ['Q1 2024', 'Q4 2023']
    for name in netflix_xbrl.list_statements():
        print(name)


@pytest.mark.asyncio
async def test_labels_for_orcl_10K(orcl_xbrl):
    financials: Financials = Financials(orcl_xbrl)
    balance_sheet = financials.get_balance_sheet()
    print(balance_sheet.labels)
    assert not balance_sheet.labels[0].startswith('us-gaap_')


@pytest.mark.asyncio
async def test_labels_for_msft_10K(msft_xbrl):
    financials: Financials = Financials(msft_xbrl)
    balance_sheet = financials.get_balance_sheet()
    print(balance_sheet.display_name)
    first_label = balance_sheet.data.index[0]
    assert first_label == 'Statement of Financial Position [Abstract]'
    assert not '_' in balance_sheet.labels[0]


def test_get_all_dimensions(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.get_all_dimensions()
    assert {
               'us-gaap:AwardTypeAxis',
               'us-gaap:ConcentrationRiskByTypeAxis',
               'us-gaap:LongtermDebtTypeAxis',
               'us-gaap:FairValueByFairValueHierarchyLevelAxis',
               'us-gaap:AntidilutiveSecuritiesExcludedFromComputationOfEarningsPerShareByAntidilutiveSecuritiesAxis',
           } & dimensions


def test_get_dimension_values(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    values = instance.get_dimension_values('us-gaap:LongtermDebtTypeAxis')
    assert values == ['aapl:FixedRateNotesMember']
    assert not instance.get_dimension_values('us-gaap:NonExisting')


def test_query_facts(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    facts = instance.query_facts(dimensions={'ecd:IndividualAxis': 'aapl:DeirdreOBrienMember'})
    print(facts)


def test_get_facts_by_dimension(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    assert instance.facts.dim.has_dimensions()
    deidre_facts = instance.facts.dim.value('ecd:IndividualAxis', 'aapl:DeirdreOBrienMember')
    print(deidre_facts)
    assert len(deidre_facts) > 0


def test_multi_dimension_facts(apple_xbrl):
    facts = apple_xbrl.instance.facts
    multi_dim_df = facts.dim.match({
        'us-gaap:StatementScenarioAxis': 'us-gaap:ScenarioForecastMember',
        'us-gaap:StatementClassOfStockAxis': 'us-gaap:CommonStockMember'
    })
    print(multi_dim_df)

    # List all dimensions
    all_dimensions = facts.dim.list_dimensions()
    assert 'us-gaap:StatementBusinessSegmentsAxis' in all_dimensions

    # Get all values for a specific dimension


# scenario_values = facts.dim.get_values('us-gaap:StatementScenarioAxis')


def test_xbrl_instance_dimensions(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    print(instance.dimensions)


def test_xbrl_presentation_role_with_almost_duplicate_name(apple_xbrl):
    statement = apple_xbrl.statements.get('RevenueDeferredRevenueExpectedTimingofRealizationDetails_1')
    assert statement is None


@pytest.mark.asyncio
async def test_xbrl_financials_using_non_standard_filing_like_crowdstrike(crowdstrike_xbrl):
    financials: Financials = Financials(crowdstrike_xbrl)

    balance_sheet = financials.get_balance_sheet()
    assert balance_sheet

    comprehensive_income_statement = financials.get_statement_of_comprehensive_income()
    assert comprehensive_income_statement

    cashflow_statement = financials.get_cash_flow_statement()
    assert cashflow_statement

    equity_statement = financials.get_statement_of_changes_in_equity()
    assert equity_statement

    cover_page = financials.get_cover_page()
    assert cover_page

    income_statement = financials.get_income_statement()
    assert income_statement


def test_extract_financials_from_filing():
    filing = Filing(company='GENERAL DYNAMICS CORP', cik=40533, form='10-Q', filing_date='2024-07-24',
                    accession_no='0000040533-24-000035')
    financials: Financials = Financials.extract(filing)
    assert financials
