from edgar.xbrl import FilingXbrl
from pathlib import Path
import pandas as pd


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


def test_filing_xbrl_db():
    filing_xbrl: FilingXbrl = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
    db = filing_xbrl.to_duckdb()
    df = db.execute("select fact, value from facts").df()
    assert 'fact' in df
    assert 'value' in df
    assert len(df == 100)