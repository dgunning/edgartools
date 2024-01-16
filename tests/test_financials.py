import pandas as pd
from rich import print

from edgar import *
from edgar.financials import Financials, format_currency
from edgar.company_reports import TenK

pd.options.display.max_colwidth = 50


def test_format_currency():
    assert format_currency("1000000").lstrip() == "1,000,000"
    assert format_currency(100000).lstrip() == "100,000"


def test_microsoft_financials():
    company = Company("MSFT")
    tenk = company.get_filings(form="10-K", accession_number="0001564590-22-026876").latest()
    print(tenk.accession_no)
    financials = Financials.from_xbrl(tenk.xbrl())
    assert financials.balance_sheet
    assert "13,931,000,000" in repr(financials.balance_sheet)
    assert "84,281,000,000" in repr(financials.balance_sheet)
    assert financials.income_statement
    print(financials.income_statement)
    assert "198,270,000,000" in repr(financials.income_statement)
    assert "72,738,000,000" in repr(financials.income_statement)
    assert financials.cash_flow_statement
    print(financials.cash_flow_statement)
    assert "72,738,000,000" in repr(financials.cash_flow_statement)
    assert "-30,311,000,000" in repr(financials.cash_flow_statement)

    assert financials.balance_sheet.end_date == '2022-06-30'



def test_apple_financials_to_dataframe():
    company = Company("AAPL")
    filing = company.get_filings(form="10-K", accession_number="0000320193-22-000108").latest()
    tenk = TenK(filing)

    # Income Statement
    income_statement = tenk.income_statement

    assert income_statement.get_fact_value('RevenueFromContractWithCustomerExcludingAssessedTax') == '394328000000'
    assert income_statement.get_fact_value('CostOfGoodsAndServicesSold') == '223546000000'
    assert income_statement.get_fact_value('ResearchAndDevelopmentExpense') == '26251000000'
    assert income_statement.get_fact_value('SellingGeneralAndAdministrativeExpense') == '25094000000'
    assert income_statement.get_fact_value('OperatingIncomeLoss') == '119437000000'
    assert income_statement.get_fact_value('IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest') == '119103000000'
    assert income_statement.get_fact_value('IncomeTaxExpenseBenefit') == '19300000000'
    assert income_statement.get_fact_value('NetIncomeLoss') == '99803000000'
    assert income_statement.get_fact_value('EarningsPerShareBasic') == '6.15'
    assert income_statement.get_fact_value('InterestExpense') == '2931000000'

    # Balance Sheet
    balance_sheet = tenk.balance_sheet
    assert balance_sheet.end_date == '2022-09-24'
    print(balance_sheet)
    assert balance_sheet.get_fact_value('CashAndCashEquivalentsAtCarryingValue') == '23646000000'
    assert balance_sheet.get_fact_value('ShortTermInvestments') is None
    assert balance_sheet.get_fact_value('InventoriesNet') is None
    assert balance_sheet.get_fact_value('OtherAssetsCurrent') == '21223000000'
    assert balance_sheet.get_fact_value('AssetsCurrent') == '135405000000'
    assert balance_sheet.get_fact_value('OtherAssetsNoncurrent') == '54428000000'
    assert balance_sheet.get_fact_value('Assets') == '352755000000'
    assert balance_sheet.get_fact_value('LiabilitiesCurrent') == '153982000000'
    assert balance_sheet.get_fact_value('LiabilitiesNoncurrent') == '148101000000'
    assert balance_sheet.get_fact_value('Liabilities') == '302083000000'
    assert balance_sheet.get_fact_value('CommitmentsAndContingencies') is None
    assert balance_sheet.get_fact_value('StockholdersEquity') == '50672000000'
    assert balance_sheet.get_fact_value('LiabilitiesAndStockholdersEquity') == '352755000000'

    # Cash Flow
    cash_flow = tenk.cash_flow_statement
    assert cash_flow.end_date == '2022-09-24'
    print(cash_flow)
    assert cash_flow.get_fact_value('NetIncomeLoss') == '99803000000'
    assert cash_flow.get_fact_value("DepreciationDepletionAndAmortization") == '11104000000'
    assert cash_flow.get_fact_value("ShareBasedCompensation") == '9038000000'


def test_10K_with_empty_facts():
    filing = Filing(form='10-K', filing_date='2023-04-19', company='Aurora Technology Acquisition Corp.', cik=1883788, accession_no='0001193125-23-105389')
    tenk = filing.obj()
    assert tenk.financials


def test_fiscal_gaap_for_10K_with_no_empty_dimensions():
    # the gaap data for this 10K has no empty dimensions for us-gaap
    filing = Filing(form='10-K', filing_date='2023-04-06', company='Frontier Masters Fund', cik=1450722,
                    accession_no='0001213900-23-028058')

    # Get the company financials
    financials = Financials.from_xbrl(filing.xbrl())
    balance_sheet = financials.balance_sheet

    assert balance_sheet.get_fact_value('CashAndCashEquivalentsAtCarryingValue') == '430193'


def test_10Q_financials():
    filing = Filing(form='10-Q', filing_date='2023-04-06', company='NIKE, Inc.', cik=320187,
                    accession_no='0000320187-23-000013')
    xbrl = filing.xbrl()
    facts = xbrl.facts
    with open('data/nike_10Q_facts.csv', 'w') as f:
        f.write(facts.data.to_csv(index=False))

