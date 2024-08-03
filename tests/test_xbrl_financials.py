import asyncio

import pandas as pd
import pytest

from edgar import Filing
from edgar.xbrl import XBRLData, XBRLInstance, StatementData, Statements, Financials
from edgar.xbrl.xbrldata import get_primary_units


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


@pytest.fixture(scope='module')
def gd_xbrl():
    filing = Filing(company='GENERAL DYNAMICS CORP', cik=40533, form='10-Q', filing_date='2024-07-24',
                    accession_no='0000040533-24-000035')
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
    assert balance_sheet.periods == ['Mar 31, 2024', 'Dec 31, 2023']
    for name in netflix_xbrl.list_statement_definitions():
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


def test_list_standard_statements(apple_xbrl):
    financials: Financials = Financials(apple_xbrl)
    statements = financials.list_standard_statements()
    assert statements == ['Cover Page', 'Consolidated Balance Sheets', 'Income Statements',
                          'Consolidated Statement of Cash Flows', 'Consolidated Statement of Shareholders Equity',
                          'Comprehensive Income Statement']
    print()
    print(financials)


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


def test_extract_financials_from_filing(gd_xbrl):
    financials: Financials = Financials(gd_xbrl)
    assert financials


def test_quarterly_data_extracted_correctly(gd_xbrl):
    assert gd_xbrl
    financials: Financials = Financials(gd_xbrl)
    income_statement: StatementData = financials.get_income_statement()
    data = income_statement.data
    concept = income_statement.get_concept('us-gaap:CostOfGoodsAndServicesSold')
    assert list(concept.value.keys()) == ['Jun 30, 2024', 'Jul 02, 2023']
    assert concept.value['Jun 30, 2024'] == '6127000000'
    assert concept.value['Jul 02, 2023'] == '4915000000'


def test_get_concepts_for_label(gd_xbrl):
    concept = 'us-gaap_OperatingIncomeLoss'
    assert gd_xbrl.get_concept_for_label("Operating Income (Loss)") == concept
    assert gd_xbrl.get_concept_for_label("Operating Earnings") == concept
    assert gd_xbrl.get_concept_for_label("Operating earnings") == concept

    assert gd_xbrl.get_labels_for_concept(concept) == {"label": "Operating Income (Loss)",
                                                       "terseLabel": "Operating Earnings",
                                                       'totalLabel': "Operating earnings"}

    roles = ['http://www.generaldynamics.com/role/ConsolidatedStatementofEarningsUnaudited',
             'http://www.generaldynamics.com/role/RevenueImpactofAdjustmentsinContractEstimatesDetails',
             'http://www.generaldynamics.com/role/SegmentInformationSummaryofFinancialInformationDetails']
    # Roles for label
    assert gd_xbrl.get_roles_for_label("Operating Income (Loss)") == roles
    statements = gd_xbrl.list_statements_for_label("Operating Income (Loss)")
    print(statements)

    statement = gd_xbrl.get_statement(statements[0])
    assert statement


def test_handle_financials_with_only_document_and_entity_definition():
    # This filing only has 'DocumentAndEntityInformation'
    filing = Filing(form='10-K/A', filing_date='2024-07-26', company='Swiftmerge Acquisition Corp.',
                    cik=1845123, accession_no='0001013762-24-001580')
    xbrl_data: XBRLData = XBRLData.extract(filing)
    statement_definitions = xbrl_data.list_statement_definitions()
    assert statement_definitions == ['DocumentAndEntityInformation']
    financials = Financials(xbrl_data)
    assert financials
    assert financials.get_cover_page()
    assert not financials.get_balance_sheet()
    assert not financials.get_income_statement()
    assert not financials.get_cash_flow_statement()
    assert not financials.get_statement_of_changes_in_equity()
    assert not financials.get_statement_of_comprehensive_income()
    assert financials.get_cover_page()


def test_get_dataframe_from_statement(apple_xbrl):
    financials: Financials = Financials(apple_xbrl)
    balance_sheet = financials.get_balance_sheet()
    assert balance_sheet.get_dataframe().columns.tolist() == ['2023', '2022']
    assert balance_sheet.get_dataframe(include_concept=True).columns.tolist() == ['2023', '2022', 'concept']
    assert balance_sheet.get_dataframe(include_format=True).columns.tolist() == ['2023', '2022', 'level', 'abstract',
                                                                                 'units', 'decimals']
    assert balance_sheet.get_dataframe(include_concept=True, include_format=True).columns.tolist() == ['2023', '2022',
                                                                                                       'concept',
                                                                                                       'level',
                                                                                                       'abstract',
                                                                                                       'units',
                                                                                                       'decimals']


def test_get_primary_units():
    # Test case with -6 as the most common decimals value
    data1 = {'decimals': ['-6', '-6', '-6', '-3', '-3', 'INF', '0']}
    df1 = pd.DataFrame(data1)
    assert get_primary_units(df1, 'decimals') == "Millions"

    # Test case with -3 as the most common decimals value
    data2 = {'decimals': ['-3', '-3', '-3', '-6', '-6', 'INF', '0']}
    df2 = pd.DataFrame(data2)
    assert get_primary_units(df2, 'decimals') == "Thousands"

    # Test case with -5 as the most common decimals value
    data3 = {'decimals': ['-5', '-5', '-5', '-3', '-3', 'INF', '0']}
    df3 = pd.DataFrame(data3)
    assert get_primary_units(df3, 'decimals') == "Hundreds of Thousands"

    # Test case with -2 as the most common decimals value
    data4 = {'decimals': ['-2', '-2', '-2', '-6', '-6', 'INF', '0']}
    df4 = pd.DataFrame(data4)
    assert get_primary_units(df4, 'decimals') == "Hundreds"

    # Test case with -1 as the most common decimals value
    data5 = {'decimals': ['-1', '-1', '-1', '-6', '-6', 'INF', '0']}
    df5 = pd.DataFrame(data5)
    assert get_primary_units(df5, 'decimals') == "Tens"

    # Test case with INF as the most common decimals value
    data6 = {'decimals': ['INF', 'INF', 'INF', '-6', '-6', '-1', '0']}
    df6 = pd.DataFrame(data6)
    assert get_primary_units(df6, 'decimals') == "Units"

    # Test case with mixed decimals values where no specific case is dominant
    data7 = {'decimals': ['0', '0', '0', '-6', '-3', '-1', 'INF']}
    df7 = pd.DataFrame(data7)
    assert get_primary_units(df7, 'decimals') == "Units"


def test_get_primary_units_for_statement(apple_xbrl):
    financials: Financials = Financials(apple_xbrl)
    balance_sheet = financials.get_balance_sheet()
    assert balance_sheet.get_primary_units() == "Millions"
