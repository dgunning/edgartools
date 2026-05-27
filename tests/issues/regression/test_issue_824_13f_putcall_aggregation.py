"""Regression test for #824 — 13F-HR holdings merged Put/Call rows into equity."""

import pytest

from edgar import Filing
from edgar.thirteenf import ThirteenF


SG_CAPITAL_13F_HR_A = {
    "form": "13F-HR/A",
    "filing_date": "2024-06-07",
    "company": "SG Capital Management LLC",
    "cik": 1510099,
    "accession_no": "0001172661-24-002551",
}


def _sg_capital_thirteenf() -> ThirteenF:
    return ThirteenF(Filing(**SG_CAPITAL_13F_HR_A))


@pytest.mark.network
def test_holdings_preserves_put_call_rows_separately():
    thirteenf = _sg_capital_thirteenf()
    holdings = thirteenf.holdings
    assert holdings is not None
    puts = holdings.query("PutCall == 'Put'")
    assert len(puts) == 3
    # Puts must reference distinct CUSIPs from any aggregated equity rows (they're separate positions)
    put_cusips = set(puts["Cusip"])
    assert len(put_cusips) == 3


@pytest.mark.network
def test_holdings_putcall_values_use_title_case():
    thirteenf = _sg_capital_thirteenf()
    holdings = thirteenf.holdings
    putcall_values = set(holdings["PutCall"].dropna().astype(str))
    # SEC XML emits 'Put' / 'Call' title case; categorical must accept those (not uppercase)
    assert putcall_values.issubset({"", "Put", "Call"})
    assert "Put" in putcall_values


@pytest.mark.network
def test_infotable_unchanged_baseline():
    """Ensure the raw infotable still shows 3 Puts (issue's stated ground truth)."""
    thirteenf = _sg_capital_thirteenf()
    puts = thirteenf.infotable.query("PutCall == 'Put'")
    assert len(puts) == 3


@pytest.mark.network
def test_putcall_column_position_preserved():
    """PutCall must remain immediately after Ticker, not get bumped by groupby.

    pandas groupby(['Cusip', 'PutCall'], as_index=False) places PutCall right
    after Cusip in the output — which silently shifts the column layout. Any
    positional column access (iloc, hardcoded notebook indices) and the table
    rendering order depend on PutCall sitting after Ticker. Reviewed in #828.
    """
    thirteenf = _sg_capital_thirteenf()
    holdings = thirteenf.holdings
    cols = list(holdings.columns)
    assert "PutCall" in cols
    assert "Ticker" in cols
    # PutCall must sit immediately after Ticker (contract, not just "somewhere later")
    assert cols.index("PutCall") == cols.index("Ticker") + 1, (
        f"PutCall position regressed: expected immediately after Ticker, got cols={cols}"
    )
