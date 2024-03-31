from edgar.reference import cusip_ticker_mapping, get_ticker_from_cusip
from edgar import *


def test_cusip_ticker_mapping():
    data = cusip_ticker_mapping()
    assert data.loc['15101T102'].SYMBOL == 'CLXX'


def test_get_ticker_from_cusip():
    assert get_ticker_from_cusip('000307108') == 'AACH'
    assert get_ticker_from_cusip('74349L108') == 'PGUCY'
    assert get_ticker_from_cusip('037833100') == 'AAPL'
    assert get_ticker_from_cusip('59021J679') == 'MNK'

def test_augment_13f_hr():
    filing = Filing(form='13F-HR', filing_date='2024-03-29', company='ADIRONDACK TRUST CO', cik=1054257, accession_no='0001054257-24-000002')
    thirteenf:ThirteenF = filing.obj()
    data = thirteenf.infotable[['Issuer', 'Cusip', 'Type', 'Value']]
    print()
    print(data)

    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    data['Symbol'] = data.Cusip.map(cusip_mapping.SYMBOL)
    print(data)

