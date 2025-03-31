from pathlib import Path

import pytest
from rich import print

from edgar import *
from edgar.xbrl2.rendering import RenderedStatement
from edgar.xbrl2.statements import Statement
from edgar.xbrl2.xbrl import XBRL
import pandas as pd
pd.options.display.max_colwidth = 200


@pytest.fixture
def tsla_xbrl():
    # Quarterly statements
    data_dir = Path("data/xbrl/datafiles/tsla")

    # Parse the directory
    return XBRL.parse_directory(data_dir)


@pytest.fixture
def aapl_xbrl():
    data_dir = Path("data/xbrl/datafiles/aapl")

    # Parse the directory
    return XBRL.parse_directory(data_dir)

def test_dimensioned_statement(aapl_xbrl):
    statements = aapl_xbrl.statements
    role_definition = 'SegmentInformationandGeographicDataInformationbyReportableSegmentDetails'
    assert aapl_xbrl._is_dimension_display_statement(None, role_definition)
    statement = statements[role_definition]
    print()
    result = statement.render()
    print(result)


def test_get_statement_by_short_name(tsla_xbrl):
    # Get the cover statement.
    # Statements currently return a list of dicts. Maybe in the future return a StatementDefinition object.
    statement_lst: List = tsla_xbrl.get_statement('Cover')
    assert statement_lst
    assert statement_lst[0]['concept'] == 'dei_CoverAbstract'

    # Use the Statements class to get the statement
    statements = tsla_xbrl.statements
    statement: Statement = statements['Cover']
    assert isinstance(statement, Statement)
    assert statement.role_or_type == 'Cover'
    assert statement

    # Get the ConsolidatedBalanceSheetsParenthetical
    balance_sheet_lst = tsla_xbrl.get_statement('ConsolidatedBalanceSheetsParenthetical')
    assert balance_sheet_lst
    assert balance_sheet_lst[0]['concept'] == 'us-gaap_StatementOfFinancialPositionAbstract'

    balance_sheet = statements['ConsolidatedBalanceSheetsParenthetical']
    assert balance_sheet


def test_get_statement_by_type(tsla_xbrl):
    statement = tsla_xbrl.get_statement('BalanceSheet')
    assert statement
    assert statement[0]['concept'] == 'us-gaap_StatementOfFinancialPositionAbstract'


def test_statement_get_item_int(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements[0]
    assert statement


def test_statement_get_item_by_name(tsla_xbrl):
    statements = tsla_xbrl.statements
    print()
    statement = statements["Cover"]
    assert statement
    print(statement)

    # Get ConsolidatedBalanceSheetsParenthetical
    statement = statements["ConsolidatedBalanceSheetsParenthetical"]
    assert statement


def test_aapl_balance_sheet(aapl_xbrl):
    statements = aapl_xbrl.statements
    print()
    balance_sheet = statements['BalanceSheet']
    assert balance_sheet
    rendered_statement = balance_sheet.render()
    assert rendered_statement

    balance_sheet = statements.balance_sheet()
    print(balance_sheet)

    balance_sheet = statements['CONSOLIDATEDBALANCESHEETS']
    print(balance_sheet)


def test_get_income_statement(tsla_xbrl):
    statements = tsla_xbrl.statements
    print()
    statement = statements.income_statement()
    assert statement
    print(statement)


def test_statement_to_dataframe(aapl_xbrl):
    cashflow_statement: Statement = aapl_xbrl.statements.cash_flow_statement()
    print()
    # print(cashflow_statement)
    rendered_statement:RenderedStatement = cashflow_statement.render()
    df1 = rendered_statement.to_dataframe()
    print()
    print(df1[[ '2023-09-30']])
    df = cashflow_statement.to_dataframe()

    assert all(col in df.columns for col in ['2023-09-30', '2022-09-24', '2021-09-25'])


def test_non_financial_statement():
    f = Filing(company='SOUTHERN COPPER CORP/', cik=1001838, form='10-K', filing_date='2025-03-03',
               accession_no='0001558370-25-002017')
    xbrl: XBRL = XBRL.from_filing(f)

    print()
    # print(xbrl.statements)

    statement = xbrl.statements["DisclosureSegmentAndRelatedInformationSalesDetails"]
    assert statement
    print(statement)

    statement = xbrl.render_statement('DisclosureProperty')
    print(statement)


def test_render_segmented_statement(tsla_xbrl):
    statements = tsla_xbrl.statements
    statement = statements['SegmentReportingandInformationaboutGeographicAreas']
    assert statement
    print()
    print(statement)

    
def test_statement_lookup_optimizations(tsla_xbrl):
    """Test that our statement lookup optimizations work correctly"""
    # First call to build indices
    statements = tsla_xbrl.get_all_statements()
    
    # Ensure indices are properly built
    assert hasattr(tsla_xbrl, '_statement_by_standard_name')
    assert hasattr(tsla_xbrl, '_statement_by_primary_concept')
    assert hasattr(tsla_xbrl, '_statement_by_role_uri')
    assert hasattr(tsla_xbrl, '_statement_by_role_name')
    
    # Test lookup by standard name
    assert 'BalanceSheet' in tsla_xbrl._statement_by_standard_name
    
    # Get statement by standard name
    balance_sheet = tsla_xbrl.get_statement('BalanceSheet')
    assert balance_sheet
    
    # Get statement by role name
    for role, statement in tsla_xbrl._statement_by_role_uri.items():
        role_name = role.split('/')[-1].lower() if '/' in role else ''
        if role_name:
            # Try to get statement by role name
            stmt = tsla_xbrl.get_statement(role_name)
            assert stmt  # Statement should be found
    
    # Ensure cached result is returned (for performance)
    import time
    
    # Time the first call (should use cached indices)
    start = time.time()
    statements1 = tsla_xbrl.get_all_statements()
    elapsed1 = time.time() - start
    
    # Time the second call (should return cached result)
    start = time.time()
    statements2 = tsla_xbrl.get_all_statements()
    elapsed2 = time.time() - start
    
    # The second call should be extremely fast (effectively 0) because it's returning a cached result
    # Either the second call is faster OR both calls are extremely fast (less than 1ms)
    assert elapsed2 < elapsed1 or (elapsed1 < 0.001 and elapsed2 < 0.001)
    assert statements1 == statements2  # Same result


def test_cashflow_statement_totals():
    filing = Filing(company='Corsair Gaming, Inc.', cik=1743759, form='10-K',
                    filing_date='2025-02-26', accession_no='0000950170-25-027856')
    xbrl: XBRL = XBRL.from_filing(filing)
    cashflow_statement = xbrl.statements.cash_flow_statement()
    print()
    print(cashflow_statement)
    df = cashflow_statement.to_dataframe()
    main_concepts = ["us-gaap_NetCashProvidedByUsedInOperatingActivities",
                     "us-gaap_NetCashProvidedByUsedInInvestingActivities",
                     "us-gaap_NetCashProvidedByUsedInFinancingActivities"]
    idx = df.concept.isin(main_concepts)
    cols = ["concept", "label", "2024-12-31"]
    cash_totals = df[idx][cols]
    assert len(cash_totals) == 3
    print(cash_totals)

    cash_statement = filing.statements.cash_flow_statement
    print(cash_statement.view())


def test_get_statement_by_name_returns_correct_statement():
    filing = Filing(company='SOUTHERN COPPER CORP/', cik=1001838, form='10-Q', filing_date='2011-08-08', accession_no='0001104659-11-044725')
    xbrl: XBRL = XBRL.from_filing(filing)
    statement:Statement = xbrl.statements.income_statement()
    #assert statement.primary_concept == 'us-gaap:IncomeStatementAbstract'
    df = statement.to_dataframe()
    concepts = df.concept.tolist()
    assert concepts[0] == 'us-gaap_IncomeStatementAbstract'



def test_get_balance_sheet_with_few_concepts():
    filing = Filing(company='M-Tron Industries Inc', cik=1902314, form='10-K', filing_date='2024-03-27', accession_no="0001437749-25-009645")
    xbrl: XBRL = XBRL.from_filing(filing)
    balance_sheet = xbrl.statements.balance_sheet()
    print()
    print(balance_sheet)


def test_quarterly_statements():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-Q', filing_date='2025-01-31', accession_no='0000320193-25-000008')
    xbrl = XBRL.from_filing(filing)
    income_statement = xbrl.statements.income_statement()
    income_statement.render()
    print()
    print(income_statement)
