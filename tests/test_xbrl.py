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
    df = db.execute("select fact, value, units, start_date, end_date from facts").df()
    assert ['fact', 'value', 'units', 'start_date', 'end_date'] == list(df.columns)
    assert len(df == 100)

    df = db.execute("""select fact, value, units, start_date, end_date from facts 
                        where fact == 'CommonStockSharesIssued' and end_date == '2017-12-31' """).df()
    assert df.iloc[0].value == '27133614'
    print('\n',df)
