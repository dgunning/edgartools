import pytest
from edgar import *
from edgar.xbrl import *
from edgar.xbrl.standardization import StandardConcept
from edgar.xbrl.rendering import RenderedStatement
from edgar.xbrl.analysis.ratios import *
from edgar.xbrl.analysis.metrics import *
from rich import print

@pytest.fixture(scope="session")
def comcast_xbrl():
    filing = Filing(company='COMCAST CORP', cik=1166691, form='10-K', filing_date='2025-01-31', accession_no='0001166691-25-000011')
    return XBRL.from_filing(filing)

def test_get_ratio_data(comcast_xbrl):
    fr = FinancialRatios(comcast_xbrl)
    print()
    print(comcast_xbrl.statements.income_statement())
    print(fr.get_ratio_data('gross_margin'))
    #for category in ['current', 'operating_margin', 'return_on_assets', 'gross_margin', 'leverage']:
    #    print("Category: ", category)
    #    print(fr.get_ratio_data(category))


def test_ratio_with_equivalent(comcast_xbrl):
    fr = FinancialRatios(comcast_xbrl)
    df = fr.get_ratio_data('gross_margin')
    print()
    #print(df)
    gross_margin:RatioAnalysis = fr.calculate_gross_margin()
    print(gross_margin)
    leverage = fr.calculate_leverage_ratios()
    print(leverage)


def test_xb_income_statement(comcast_xbrl):
    income_statement = comcast_xbrl.statements.income_statement()
    df = (comcast_xbrl.query("IncomeStatement")
     .by_label("Costs").to_dataframe())
    print(df[['concept', 'label']])