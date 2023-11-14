import pandas as pd
from rich import print

from edgar import *
from edgar.financials import Financials, format_currency
from edgar.company_reports import TenK


def test_format_currency():
    assert format_currency("1000000").lstrip() == "$1,000,000"
    assert format_currency(100000).lstrip() == "$100,000"


def test_balance_sheet():
    """
    filing = Filing(company='Snowflake Inc.', cik=1640147, form='10-K', filing_date='2023-03-29',
                    accession_no='0001640147-23-000030')
    gaap = filing.xbrl().fiscal_gaap
    gaap.to_csv('data/snowflake_gaap.csv', index=False)

    filing = Filing(company='MICROSOFT CORP', cik=789019, form='10-K', filing_date='2022-07-28',
                    accession_no='0001564590-22-026876')
    gaap = filing.xbrl().fiscal_gaap
    gaap.to_csv('data/microsoft_gaap.csv', index=False)
    """

    gaap = pd.read_csv('data/snowflake_gaap.csv')
    financials = Financials.from_gaap(gaap)
    print()
    print(financials)

    gaap = pd.read_csv('data/microsoft_gaap.csv')
    financials = Financials.from_gaap(gaap)
    print()
    print(financials)


def test_microsoft_financials():
    company = Company("MSFT")
    tenk = company.get_filings(form="10-K", accession_number="0001564590-22-026876").latest()
    print(tenk.accession_no)
    gaap = tenk.xbrl().gaap
    financials = Financials.from_gaap(gaap)
    print()
    print(financials)

    # Balance Sheet data
    balance_sheet = financials.balance_sheet

    print(balance_sheet.asset_dataframe)
    print(balance_sheet.liability_equity_dataframe)


def test_apple_financials():
    company = Company("AAPL")
    tenk = TenK(company.get_filings(form="10-K", accession_number="0000320193-22-000108").latest())

    gaap = tenk._filing.xbrl().gaap
    gaap.to_csv('data/apple_gaap.csv', index=False)

    # Income Statement
    income_statement = tenk.income_statement

    assert income_statement.revenue == "$394,328,000,000"
    assert income_statement.cost_of_revenue == "$223,546,000,000"
    assert income_statement.gross_profit == "$170,782,000,000"
    assert income_statement.research_and_development_expenses == "$26,251,000,000"
    assert income_statement.selling_general_and_administrative_expenses == "$25,094,000,000"
    assert income_statement.operating_income == "$119,437,000,000"
    assert income_statement.income_before_tax == "$119,103,000,000"
    assert income_statement.income_tax_expense == "$19,300,000,000"
    assert income_statement.net_income == "$99,803,000,000"
    assert income_statement.depreciation_and_amortization == "$11,104,000,000"
    assert income_statement.earnings_per_share == "6.15"
    assert income_statement.interest_expense == "$2,931,000,000"
    assert income_statement.interest_and_dividend_incoms == "$2,825,000,000"

    # Balance Sheet
    balance_sheet = tenk.balance_sheet
    assert balance_sheet.cash_and_cash_equivalents == "$23,646,000,000"
    assert balance_sheet.short_term_investments == "$24,658,000,000"
    assert balance_sheet.long_term_investments == "$120,805,000,000"
    assert balance_sheet.inventories == "$4,946,000,000"
    assert balance_sheet.other_current_assets == "$21,223,000,000"
    assert balance_sheet.total_current_assets == "$135,405,000,000"
    assert balance_sheet.other_non_current_assets == "$54,428,000,000"
    assert balance_sheet.total_non_current_assets == "$217,350,000,000"
    assert balance_sheet.property_plant_and_equipment == "$42,117,000,000"
    assert balance_sheet.goodwill is None
    assert balance_sheet.total_assets == "$352,755,000,000"

    # Cash Flow
    cash_flow = tenk.cash_flow_statement
    assert cash_flow.net_income == "$99,803,000,000"
    assert cash_flow.depreciation_and_amortization == "$11,104,000,000"
    assert cash_flow.other_non_cash_items == "$-111,000,000"
    assert cash_flow.net_cash_provided_by_operating_activities == "$122,151,000,000"

    print(tenk.financials)

def test_10K_with_empty_facts():
    filing = Filing(form='10-K', filing_date='2023-04-19', company='Aurora Technology Acquisition Corp.', cik=1883788, accession_no='0001193125-23-105389')
    tenk = filing.obj()
    assert tenk.financials


def test_fiscal_gaap_for_10K_with_no_empty_dimensions():
    # the gaap data for this 10K has no empty dimensions for us-gaap
    filing = Filing(form='10-K', filing_date='2023-04-06', company='Frontier Masters Fund', cik=1450722,
                    accession_no='0001213900-23-028058')

    gaap: pd.DataFrame = filing.xbrl().gaap
    assert len(gaap) > 0

    # Get the company financials
    financials = Financials.from_gaap(gaap)
    balance_sheet = financials.balance_sheet

    assert balance_sheet.cash_and_cash_equivalents == "$430,193"


def test_10Q_financials():
    filing = Filing(form='10-Q', filing_date='2023-04-06', company='NIKE, Inc.', cik=320187,
                    accession_no='0000320187-23-000013')
    xbrl = filing.xbrl()
    facts = xbrl.facts
    with open('data/nike_10Q_facts.csv', 'w') as f:
        f.write(facts.data.to_csv(index=False))

