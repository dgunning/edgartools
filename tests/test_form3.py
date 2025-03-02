from edgar import Filing
from edgar.ownership import Form3


def test_form3_initial_holdings():
    f = Filing(form='3', filing_date='2025-02-28', company='Almeida Prado Claudio', cik=2058644,
               accession_no='0001562180-25-001814')
    form3: Form3 = f.obj()
    print()
    print(form3)
    assert form3
    ownership_summary = form3.get_ownership_summary()
    assert ownership_summary.position == 'Executive Vice President'
    assert ownership_summary.total_shares == 50257.0
