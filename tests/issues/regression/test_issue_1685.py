"""Stitched balance sheet merged any two cash-bucket lines from different filings.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1685

Cash, cash and cash equivalents, cash plus short-term investments, due from
banks, available-for-sale and held-to-maturity securities all standardize to
CashAndMarketableSecurities. That bucket is in _EQUIVALENT_STANDARD_CONCEPTS
(GH #610), so the name-variant check was skipped and the only guard was "no
overlapping period disagrees". One-period stitched statements never overlap, so
any two such lines from different filings merged: a bank's 2022 cash component
(30) showed as its 2023 total's prior year, and 2023 cash (100) landed in the
available-for-sale row.

Now a pair in that bucket merges only when the filings report both lines for a
common period, comparative columns included, and the values agree.

Ground truth: IESC 10-K 0001048268-24-000134 tags CashAndCashEquivalentsAtCarrying
Value (2024-09-30 100,832,000; 2023-09-30 75,770,000) and 10-K
0001048268-23-000097 tags CashCashEquivalentsAndShortTermInvestments (2023-09-30
75,770,000). The shared 2023-09-30 amount is the evidence, so they still merge.
"""
import pytest

from edgar.xbrl.stitching.core import StatementStitcher


def _stmt(date, rows):
    pid = f"instant_{date}"
    return {"statement_type": "BalanceSheet",
            "periods": {pid: {"label": date}},
            "data": [{"concept": c, "label": label, "level": 1, "is_abstract": False,
                      "is_total": False, "values": {pid: v}, "decimals": {pid: 0}}
                     for c, label, v in rows]}


def _rows(statements):
    out = StatementStitcher().stitch_statements(statements)
    return {r["concept"]: r["values"] for r in out["statement_data"]}


@pytest.mark.fast
def test_bank_component_is_not_shown_as_prior_year_total():
    rows = _rows([
        _stmt("2023-12-31", [("us-gaap_CashAndCashEquivalentsAtCarryingValue", "Cash and cash equivalents", 120)]),
        _stmt("2022-12-31", [("us-gaap_CashAndDueFromBanks", "Cash and due from banks", 30),
                             ("us-gaap_InterestBearingDepositsInBanks", "Interest-bearing deposits in banks", 70)]),
    ])
    assert rows["us-gaap_CashAndCashEquivalentsAtCarryingValue"] == {"instant_2023-12-31": 120}
    assert rows["us-gaap_CashAndDueFromBanks"] == {"instant_2022-12-31": 30}
    assert rows["us-gaap_InterestBearingDepositsInBanks"] == {"instant_2022-12-31": 70}


@pytest.mark.fast
def test_cash_does_not_land_in_securities_row():
    rows = _rows([
        _stmt("2023-12-31", [("us-gaap_CashAndCashEquivalentsAtCarryingValue", "Cash and cash equivalents", 100)]),
        _stmt("2022-12-31", [("us-gaap_Cash", "Cash", 80),
                             ("us-gaap_AvailableForSaleSecurities", "Available-for-sale securities", 40)]),
    ])
    assert rows["us-gaap_AvailableForSaleSecurities"] == {"instant_2022-12-31": 40}
    assert rows["us-gaap_CashAndCashEquivalentsAtCarryingValue"] == {"instant_2023-12-31": 100}
    assert rows["us-gaap_Cash"] == {"instant_2022-12-31": 80}


@pytest.mark.fast
def test_agreeing_comparative_column_still_merges():
    # The later filing's comparative column reports the same amount as the
    # earlier filing's line: that is evidence they are one measure.
    later = _stmt("2024-09-30", [("us-gaap_CashAndCashEquivalentsAtCarryingValue", "Cash and cash equivalents", 100)])
    later["data"][0]["values"]["instant_2023-09-30"] = 75
    rows = _rows([
        later,
        _stmt("2023-09-30", [("us-gaap_CashCashEquivalentsAndShortTermInvestments", "Cash and short-term investments", 75)]),
    ])
    assert rows == {"us-gaap_CashAndCashEquivalentsAtCarryingValue":
                    {"instant_2024-09-30": 100, "instant_2023-09-30": 75}}



@pytest.mark.fast
def test_restated_comparative_keeps_two_rows():
    # Intended change: when the later filing restates the shared period, the two
    # lines are not shown to be the same amount, so they stay separate rows.
    later = _stmt("2024-09-30", [("us-gaap_CashAndCashEquivalentsAtCarryingValue", "Cash and cash equivalents", 100)])
    later["data"][0]["values"]["instant_2023-09-30"] = 72
    rows = _rows([
        later,
        _stmt("2023-09-30", [("us-gaap_CashCashEquivalentsAndShortTermInvestments", "Cash and short-term investments", 75)]),
    ])
    assert rows == {
        "us-gaap_CashAndCashEquivalentsAtCarryingValue": {"instant_2024-09-30": 100},
        "us-gaap_CashCashEquivalentsAndShortTermInvestments": {"instant_2023-09-30": 75},
    }


@pytest.mark.network
def test_iesc_concept_switch_merges_on_shared_amount():
    from edgar import find
    from edgar.xbrl.stitching import XBRLS

    xbrls = [find(a).xbrl() for a in ("0001048268-24-000134", "0001048268-23-000097")]
    df = XBRLS.from_xbrl_objects(xbrls).statements.balance_sheet().to_dataframe()
    cash = df[df["label"].str.contains("cash", case=False, na=False)]
    assert len(cash) == 1
    row = cash.iloc[0]
    assert row["2024-09-30"] == 100_832_000
    assert row["2023-09-30"] == 75_770_000
