from edgar._xbrl import FilingXbrl
from pathlib import Path
import pandas as pd
from rich import print


def test_filing_xbrl_parse():
    xbrl_text = Path('data/crr.xbrl.xml').read_text()
    filing_xbrl: FilingXbrl = FilingXbrl.parse(xbrl_text)
    assert filing_xbrl
    assert not filing_xbrl.facts.empty
    pd.options.display.max_columns = 7


def test_filing_xbrl_properties():
    filing_xbrl: FilingXbrl = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
    assert filing_xbrl.company_name == 'CARBO CERAMICS INC'
    assert filing_xbrl.cik == int('0001009672')
    assert filing_xbrl.form_type == '10-K'


def test_xbrl_repr():
    filing_xbrl: FilingXbrl = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
    print(filing_xbrl)
    print(filing_xbrl.facts)
