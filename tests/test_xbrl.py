from edgar._xbrl import FilingXbrl
from pathlib import Path
import pandas as pd
from rich import print

CARBO_CERAMICS_FILING_XBRL = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
def test_filing_xbrl_parse():
    xbrl_text = Path('data/crr.xbrl.xml').read_text()
    filing_xbrl: FilingXbrl = FilingXbrl.parse(xbrl_text)
    assert filing_xbrl
    assert not filing_xbrl.facts.empty
    pd.options.display.max_columns = 7


def test_filing_xbrl_properties():
    filing_xbrl: FilingXbrl = CARBO_CERAMICS_FILING_XBRL
    assert filing_xbrl.company_name == 'CARBO CERAMICS INC'
    assert filing_xbrl.cik == int('0001009672')
    assert filing_xbrl.form_type == '10-K'
    assert filing_xbrl.fiscal_year_end_date == '2017-12-31'
    assert len(filing_xbrl.gaap) > 100

    print(filing_xbrl)
    print(filing_xbrl.facts)


def test_default_gaap_dimension():
    filing_xbrl: FilingXbrl = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
    assert filing_xbrl._default_gaap_dimension() == "{'us-gaap:ConsolidationItemsAxis': 'us-gaap:OperatingSegmentsMember', 'us-gaap:StatementBusinessSegmentsAxis': 'crr:OilfieldTechnologiesAndServicesSegmentMember'}"

def test_period_enddates():
    filing_xbrl: FilingXbrl = CARBO_CERAMICS_FILING_XBRL
    assert filing_xbrl.fiscal_year_end_date == filing_xbrl.period_end_date == '2017-12-31'