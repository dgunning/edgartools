from pathlib import Path

from edgar.xbrl.calculations import CalculationLinkbase



def test_parse_calculations():
    aapl_calculation_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_cal.xml').read_text()
    calculation_linkbase = CalculationLinkbase.parse(aapl_calculation_xml)
    assert calculation_linkbase
    assert calculation_linkbase.get_calculations_for_role('http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS')

    balance_sheet_calculations = calculation_linkbase.get_calculations_for_role('http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS')
    assert balance_sheet_calculations[0].weight == 1.0
    assert balance_sheet_calculations[0].from_concept == 'us-gaap_LiabilitiesNoncurrent'



def test_parse_calculations_with_no_namespace():
    calculation_text = Path('data/xbrl/datafiles/radcq/rad-20230304_cal.xml').read_text()
    calculations = CalculationLinkbase.parse(calculation_text)
    assert calculations

