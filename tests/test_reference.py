from edgar.reference import cusip_ticker_mapping


def test_cusip_ticker_mapping():
    data = cusip_ticker_mapping()
    assert data[data.CUSIP == '15101T102'].SYMBOL.item() == 'CLXX'