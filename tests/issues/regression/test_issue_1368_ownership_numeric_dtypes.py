"""Pandas extension dtypes must not crash ownership numeric checks.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1368

The reported Arnaboldi Form 4 has a footnoted UnderlyingShares value. These
offline tests add that same XML shape to the checked-in Snowflake Form 4 and
exercise Form4.parse_xml, its derived column, and the public value helpers.
"""

from pathlib import Path

import pandas as pd
import pytest
from lxml import etree

import edgar.ownership.owners as owners_module
from edgar.ownership.core import compute_total_value, is_numeric
from edgar.ownership.forms import Form4
from edgar.xmltools import parse_xml


@pytest.fixture
def offline_owners(monkeypatch):
    """Keep the filing parse offline; only the reporting-owner lookup fetches."""
    class StubEntity:
        def __init__(self, cik):
            self.data = type("Data", (), {"is_company": False})()

    monkeypatch.setattr(owners_module, "Entity", StubEntity)


@pytest.mark.parametrize(('values', 'dtype', 'expected'), [
    ([1.0, 2.0], 'float64', True),
    ([1, pd.NA], 'Int64', True),
    ([1.5, pd.NA], 'Float64', True),
    (['1', '2'], 'object', True),
    (['1', '2'], 'string', True),
    (['1', pd.NA], 'string', True),
    (['0 [F1]', '2'], 'object', False),
    (['0 [F1]', '2'], 'string', False),
])
def test_is_numeric_preserves_values_and_handles_extension_dtypes(values, dtype, expected):
    assert is_numeric(pd.Series(values, dtype=dtype)) is expected


def test_footnoted_underlying_shares_from_form4_do_not_raise(offline_owners):
    root = parse_xml(Path('data/form4.snow.xml').read_text())
    shares = root.find('.//derivativeTransaction/underlyingSecurity/underlyingSecurityShares')
    assert shares is not None
    etree.SubElement(shares, 'footnoteId', id='F1')
    form4 = Form4.parse_xml(etree.tostring(root, encoding='unicode'))
    transactions = form4.derivative_table.transactions.data
    assert transactions is not None
    underlying = transactions['UnderlyingShares']

    assert underlying.iloc[0] == '200000.0 [F1]'
    assert is_numeric(underlying) is False
    assert compute_total_value(underlying, pd.Series([8.88])) is None


def test_unreadable_market_shares_from_form4_are_not_zero(offline_owners):
    root = parse_xml(Path('data/form4.snow.xml').read_text())
    sale = next((transaction for transaction in root.findall('.//nonDerivativeTransaction')
                 if transaction.findtext('./transactionCoding/transactionCode') == 'S'), None)
    assert sale is not None
    shares = sale.find('./transactionAmounts/transactionShares/value')
    assert shares is not None
    shares.text = 'unknown'
    form4 = Form4.parse_xml(etree.tostring(root, encoding='unicode'))

    trades = form4.market_trades
    assert trades is not None
    assert len(trades) == 5
    assert trades.Shares.iloc[0] == 'unknown'
    assert form4.shares_traded is None


def test_numeric_market_shares_from_form4_still_sum(offline_owners):
    form4 = Form4.parse_xml(Path('data/form4.snow.xml').read_text())

    trades = form4.market_trades
    assert trades is not None
    assert len(trades) == 5
    assert form4.shares_traded == 200_000
