from edgar import *
from edgar.ownership import Form4
import pytest

@pytest.mark.network
def test_form4_with_derivatives():
    filing = Filing(company='VERTEX PHARMACEUTICALS INC / MA',
                    cik=875320,
                    form='4',
                    filing_date='2020-10-19',
                    accession_no='0001209191-20-055264')
    form4:Form4 = filing.obj()
    print()
    _repr = repr(form4)
    assert _repr
    activities = form4.get_transaction_activities()
    assert len(activities) == 1
    activity = activities[0]
    assert activity.transaction_type == 'derivative_purchase'
    assert activity.value == 43750.08036
    assert activity.shares == 196.356
    assert activity.security_title == 'Deferred Stock Units'
    assert activity.underlying_security == 'Common Stock'

    # Data
    df = form4.to_dataframe()
    print(df)

@pytest.mark.network
def test_create_form4_with_non_numeric_underlying():
    filing = Filing(form='4', filing_date='2024-10-02', company='Arnaboldi Nicole S', cik=1950032, accession_no='0001062993-24-017232')
    form4:Form4 = filing.obj()
    assert form4
    print()
    print(form4)

@pytest.mark.network
def test_detailed_transaction_counts():
    filing = Filing(form='4', filing_date='2025-03-07', company='DYADIC INTERNATIONAL INC', cik=1213809, accession_no='0001437749-25-006667')
    form4 = filing.obj()
    df = form4.to_dataframe(detailed=False)
    print()
    print(df.columns)
    assert df['Tax Shares'][0] == 27517

    assert not df.empty
