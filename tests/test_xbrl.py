from edgar.xbrl import FilingXbrl
from pathlib import Path
import pandas as pd


def test_filing_xbrl_parse():
    xbrl_text = Path('docs/crr.xbrl.xml').read_text()
    filing_xbrl: FilingXbrl = FilingXbrl.parse(xbrl_text)
    assert filing_xbrl
    assert not filing_xbrl.facts.empty
    print()
    pd.options.display.max_columns = 7
    print(filing_xbrl.facts)
