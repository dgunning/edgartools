from pathlib import Path

import pytest
from rich import print

from edgar import *
from edgar.xbrl2.statements import Statement
from edgar.xbrl2.xbrl import XBRL


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

def test_get_statement_by_short_name(tsla_xbrl):

    # Get the cover statement.
    # Statements currently return a list of dicts. Maybe in the future return a StatementDefinition object.
    statement_lst:List = tsla_xbrl.get_statement('Cover')
    assert statement_lst
    assert statement_lst[0]['concept'] == 'dei_CoverAbstract'

    # Use the Statements class to get the statement
    statements = tsla_xbrl.statements
    statement:Statement = statements['Cover']
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
    print(balance_sheet)

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
    cashflow_statement:Statement = aapl_xbrl.statements.cash_flow_statement()
    print()
    print(cashflow_statement)
    df = cashflow_statement.to_dataframe()
    assert all(col in df.columns for col in ['2020-09-26', '2021-09-25', '2022-09-24'])

def test_non_financial_statement():
    f = Filing(company='SOUTHERN COPPER CORP/', cik=1001838, form='10-K', filing_date='2025-03-03', accession_no='0001558370-25-002017')
    xbrl:XBRL = XBRL.from_filing(f)

    print()
    #print(xbrl.statements)

    statement = xbrl.statements["DisclosureSegmentAndRelatedInformationSalesDetails"]
    assert statement
    print(statement)

    statement = xbrl.statements['DisclosureProperty']
    print(statement)
