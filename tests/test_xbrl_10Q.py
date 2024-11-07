import asyncio

import pytest

from edgar import Filing
from edgar.xbrl.xbrldata import Statement, XBRLData, XBRLAttachments
from edgar.financials import Financials


@pytest.fixture(scope='module')
def netflix_xbrl():
    filing: Filing = Filing(company='NETFLIX INC', cik=1065280, form='10-Q', filing_date='2024-04-22',
                            accession_no='0001065280-24-000128')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.fixture(scope='module')
def netflix_filing_2010():
    filing: Filing = Filing(company='NETFLIX INC', cik=1065280, form='10-Q', filing_date='2010-10-26',
                            accession_no='0001193125-10-235785')
    return filing

@pytest.fixture(scope='module')
def netflix_xbrl_2010():
    filing: Filing = Filing(company='NETFLIX INC', cik=1065280, form='10-Q', filing_date='2010-10-26',
                            accession_no='0001193125-10-235785')
    return asyncio.run(XBRLData.from_filing(filing))


@pytest.mark.parametrize('concept,values',
                         [('us-gaap_CashAndCashEquivalentsAtCarryingValue', ['7024766000', '7116913000']),
                          ('us-gaap_Liabilities', ['27462311000', '28143679000']),
                          ('nflx:ContentLiabilitiesCurrent', ['4436021000', '4466470000']),
                          ('us-gaap_CashAndCashEquivalentsAtCarryingValue', ['7024766000', '7116913000']),
                          ('us-gaap_ShortTermInvestments', ['20973000', '20973000']),
                          ('us-gaap_OtherAssetsCurrent', ['2,875,574,000', '2,780247000']),
                          ('us-gaap_AssetsCurrent', ['9,921,313,000', '9,918,133,000']),
                          ('us-gaap_Assets', ['48,827,721,000', '48,731,992,000']),
                          ('us-gaap_LiabilitiesAndStockholdersEquity', ['48,827,721,000', '48,731,992,000']),
                          ('us-gaap_StockholdersEquity', ['21,365,410,000', '20,588,313,000']),
                          ('us-gaap_Liabilities', ['27462311000', '28143679000']),
                          ('us-gaap_PropertyPlantAndEquipmentNet', ['1,501,168,000', '1,491,444,000']),
                          ('us-gaap_AccountsPayableCurrent', ['607,348,000', '747,412,000']),
                          ('us-gaap_ShortTermBorrowings', ['799,000,000', '399,844,000']),
                          ('us-gaap_AccruedLiabilitiesCurrent', ['1,977,428,000', '1,803,960,000']),
                          ('us-gaap_LongTermDebtNoncurrent', ['13,217,038,000', '14,143,417,000']),
                          ('us-gaap_RetainedEarningsAccumulatedDeficit', ['24,921,495,000', '22,589,286,000']),
                          ])
def test_netflix_10Q_balance_sheet(netflix_xbrl, concept, values):
    balance_sheet: Statement = Financials(netflix_xbrl).get_balance_sheet()
    values = [v.replace(',', '') for v in values]
    assert balance_sheet.get_concept(concept).values == values


@pytest.mark.parametrize('concept,values',
                         [('us-gaap_AssetsCurrent', ['492247000','411013000']),
                          ('us-gaap_Assets', ['770283000', '679734000']),
                          ('nflx_ContentLibraryNetNoncurrent', ['120,047,000', '108,810,000']),
                          ('us-gaap_DeferredTaxAssetsNetNoncurrent', ['19,219,000',	'15,958,000']),
                          ('us-gaap_CommonStockValue', ['52,000',	'53,000'])
                          ]
                         )
def test_netflix_10Q_balance_sheet_2010(netflix_xbrl_2010, concept, values):
    balance_sheet: Statement = netflix_xbrl_2010.get_statement('StatementOfFinancialPositionClassified')
    values = [v.replace(',', '') for v in values]
    assert balance_sheet.get_concept(concept).values == values


def test_get_statement_from_old_filings(netflix_xbrl_2010):
    balance_sheet: Statement = netflix_xbrl_2010.get_statement('StatementOfFinancialPositionClassified')
    assert balance_sheet is not None


def test_statement_files_exist_for_old_filings(netflix_filing_2010):
    documents: XBRLAttachments =XBRLAttachments(netflix_filing_2010.attachments)
    assert sorted(list(documents._documents.keys())) == ['calculation', 'definition', 'instance', 'label', 'presentation', 'schema']


def test_column_formating():
    filing = Filing(form='10-Q', filing_date='2024-07-25', company='AMEDISYS INC', cik=896262, accession_no='0000896262-24-000042')
    xbrl_data = XBRLData.extract(filing)
    financials = Financials(xbrl_data)
    income_statement = financials.get_income_statement()
    assert income_statement
    income_repr = repr(income_statement)
    assert income_repr
    print(income_repr)
    assert not ",000.0" in income_repr

def test_quarterly_filing_with_no_income_statement():
    filing = Filing(form='10-Q', filing_date='2024-07-25', company='VISTEON CORP', cik=1111335, accession_no='0001111335-24-000121')
    xbrl_data:XBRLData = XBRLData.extract(filing)
    financials: Financials = Financials(xbrl_data)
    assert not financials.get_income_statement()
    assert financials.get_statement_of_comprehensive_income()


def test_correct_value_with_same_label_for_two_concepts():
    filing = Filing(form='10-Q', filing_date='2024-08-02', company='Apple Inc.', cik=320193, accession_no='0000320193-24-000081')
    financials = Financials(filing.xbrl())
    balance_sheet = financials.get_balance_sheet()
    print(balance_sheet.data[['concept']])
    assert balance_sheet.get_concept(label='Cash and cash equivalents').values == ['25565000000', '29965000000']
    assert balance_sheet.get_concept(label='Accounts receivable, net').values == ['22795000000',  '29508000000']



