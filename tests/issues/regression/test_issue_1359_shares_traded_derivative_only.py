"""
Regression test for GitHub issue #1359: `shares_traded` on a derivative-only Form 4.

Vertex Pharmaceuticals Form 4 filed 2020-10-19 (accession 0001209191-20-055264)
reports one derivative transaction and no non-derivative table at all, so
`NonDerivativeTable.market_trades` is None. `Ownership.shares_traded` read
`.Shares` straight off it and raised `AttributeError: 'NoneType' object has no
attribute 'Shares'`, even though the filing parsed and `to_dataframe()` returned
the derivative transaction. Every neighbouring accessor already guarded None.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1359
"""
from pathlib import Path

import pandas as pd
import pytest

import edgar.ownership.owners as owners_module
from edgar.ownership.forms import Form4

# Vertex Pharmaceuticals Form 4, filed 2020-10-19, accession 0001209191-20-055264.
# One derivative transaction (196.356 deferred stock units), no <nonDerivativeTable>.
DERIVATIVE_ONLY = Path('data/ownership/VertexForm4.derivative-only.xml')
# 374Water Form 4: a non-derivative award (code A) and a derivative award, so the
# non-derivative table has transactions but none of them is a P/S market trade.
AWARDS_ONLY = Path('data/ownership/374WaterForm4.xml')
# Snowflake Form 4: five non-derivative sales, 200,000 shares in total.
MARKET_TRADES = Path('data/form4.snow.xml')
SNOW_SHARES_TRADED = 200_000


@pytest.fixture
def offline_owners(monkeypatch):
    """Stub the reporting-owner CIK lookup, the only fetch in this parse path.

    Same stub as `tests/ownership/test_insider_parse_contract.py`: it is what
    keeps an `Ownership.parse_xml` assertion in the pull-request gate instead of
    the post-merge network lane.
    """
    class StubEntity:
        def __init__(self, cik):
            self.data = type("Data", (), {"is_company": False})()

    monkeypatch.setattr(owners_module, "Entity", StubEntity)


def _form4(fixture: Path) -> Form4:
    return Form4.parse_xml(fixture.read_text())


def test_derivative_only_filing_reports_zero_shares_traded(offline_owners):
    """The reported AttributeError. 0 is the count of P/S market trades, and the
    derivative transaction has to remain reachable alongside it."""
    form4 = _form4(DERIVATIVE_ONLY)

    assert len(form4.non_derivative_table.transactions) == 0
    assert len(form4.derivative_table.transactions) == 1
    assert form4.market_trades is None

    assert form4.shares_traded == 0

    # 0 must not mean the filing was read as empty.
    df = form4.to_dataframe()
    assert len(df) == 1
    assert df.iloc[0].Shares == 196.356


def test_award_only_filing_still_reports_zero_shares_traded(offline_owners):
    """Control for the empty-frame half of the guard: this table has
    transactions, so `market_trades` is a frame, but no row is coded P or S."""
    form4 = _form4(AWARDS_ONLY)

    assert form4.non_derivative_table.has_transactions
    assert form4.market_trades is not None
    assert form4.market_trades.empty

    assert form4.shares_traded == 0


def test_market_trades_are_still_summed(offline_owners):
    """Control for the path the guard must not shadow."""
    form4 = _form4(MARKET_TRADES)

    assert len(form4.market_trades) == 5
    assert form4.shares_traded == SNOW_SHARES_TRADED


def test_nonnumeric_shares_are_not_reported_as_zero(offline_owners):
    """A nonempty frame whose Shares column is not numeric still falls through
    to None. Returning 0 there would report "no shares traded" for a filing that
    traded an amount we could not read, which is what the empty-frame branch
    must not be allowed to shadow.

    The column is forced to `object`, the dtype `np.issubdtype` is reached with
    on pandas 2; nothing here depends on how pandas 3 infers a string column.
    """
    form4 = _form4(MARKET_TRADES)
    unreadable = form4.market_trades.copy()
    unreadable['Shares'] = pd.Series(
        ['unknown'] * len(unreadable), index=unreadable.index, dtype=object)
    assert not unreadable.empty
    form4.__dict__['market_trades'] = unreadable

    assert form4.shares_traded is None
