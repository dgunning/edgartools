"""
Regression test for GH #811: ``FundReport.options_data()`` raises
``TypeError: bad operand type for abs(): 'NoneType'`` when a nested forward
contract has ``currency_purchased`` (or ``currency_sold``) set to ``'USD'``
but the corresponding ``amount_*`` field is ``None``.

Reporter (HristoRaykov) hit this on a GOF NPORT-P filing with the call
``Company('GOF').get_filings(form=['N-PORT','NPORT-P'])[0].obj().options_data()``.

Root cause (``edgar/funds/reports.py:1011-1012``)::

    sold_usd      = abs(fwd.amount_sold)      if fwd.currency_sold      == 'USD' else None
    purchased_usd = abs(fwd.amount_purchased) if fwd.currency_purchased == 'USD' else None

The currency check passes but ``amount_*`` can still be ``None`` in valid
N-PORT XBRL, and ``abs(None)`` raises. The fix adds a null guard to both
assignments. The test constructs the failure mode deterministically by
mutating a parsed Sample 7 forward — no SEC filing dependency.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from edgar.funds.reports import FundReport


NPORT_SAMPLE_7 = Path(__file__).resolve().parents[3] / 'data' / 'nport' / 'samples' / 'NPORT Sample 7.xml'


@pytest.fixture(scope='module')
def fund_report() -> FundReport:
    """Real parsed FundReport with 90+ options-on-forwards. All forwards in
    this sample have populated amounts, so the fixture is mutated per-test
    to trigger the null-amount bug path."""
    xml = NPORT_SAMPLE_7.read_text()
    return FundReport(**FundReport.parse_fund_xml(xml))


def _first_nested_forward_option(fund_report: FundReport):
    """Return the first investment whose option_derivative has a nested
    forward. Used to find a mutation target for the null-amount tests."""
    for inv in fund_report.investments:
        if (inv.derivative_info
                and inv.derivative_info.option_derivative
                and inv.derivative_info.option_derivative.nested_forward):
            return inv
    raise AssertionError("Sample 7 must contain at least one option with a nested forward")


class TestNullAmountDoesNotCrash:
    """The GH #811 contract: options_data() must tolerate null ``amount_*``
    fields on a USD-denominated forward leg and return ``None`` for the
    derived ``*_usd`` columns rather than raising."""

    def test_null_amount_purchased_does_not_crash(self, fund_report):
        # Mutate one nested forward to the bug shape: USD currency, null amount.
        inv = _first_nested_forward_option(fund_report)
        fwd = inv.derivative_info.option_derivative.nested_forward
        try:
            original = (fwd.currency_purchased, fwd.amount_purchased)
            fwd.currency_purchased = 'USD'
            fwd.amount_purchased = None
            # Pre-fix: this raised TypeError on edgar/funds/reports.py:1012.
            df = fund_report.options_data()
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
        finally:
            fwd.currency_purchased, fwd.amount_purchased = original

    def test_null_amount_sold_does_not_crash(self, fund_report):
        # The sibling line at 1011 has the same antipattern for the sold leg.
        inv = _first_nested_forward_option(fund_report)
        fwd = inv.derivative_info.option_derivative.nested_forward
        try:
            original = (fwd.currency_sold, fwd.amount_sold)
            fwd.currency_sold = 'USD'
            fwd.amount_sold = None
            df = fund_report.options_data()
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
        finally:
            fwd.currency_sold, fwd.amount_sold = original

    def test_both_amounts_null_does_not_crash(self, fund_report):
        # Pathological case: both legs in USD with null amounts.
        inv = _first_nested_forward_option(fund_report)
        fwd = inv.derivative_info.option_derivative.nested_forward
        try:
            original = (
                fwd.currency_sold, fwd.amount_sold,
                fwd.currency_purchased, fwd.amount_purchased,
            )
            fwd.currency_sold = 'USD'
            fwd.amount_sold = None
            fwd.currency_purchased = 'USD'
            fwd.amount_purchased = None
            df = fund_report.options_data()
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
        finally:
            (fwd.currency_sold, fwd.amount_sold,
             fwd.currency_purchased, fwd.amount_purchased) = original


class TestNullAmountReturnsNone:
    """Ensure the guard returns ``None`` rather than zero or a garbage value
    in the derived columns when an amount is null. Use unique mutation
    markers so we can identify the affected row in the output DataFrame."""

    def test_null_amount_purchased_row_has_none_in_derived_columns(self, fund_report):
        inv = _first_nested_forward_option(fund_report)
        fwd = inv.derivative_info.option_derivative.nested_forward

        # Stash and override. Mark the investment with a unique name so we can
        # find its row in the resulting DataFrame.
        marker = 'GH-811-null-amount-purchased-marker'
        original_name = inv.name
        original_purchased = (fwd.currency_purchased, fwd.amount_purchased)
        original_sold = (fwd.currency_sold, fwd.amount_sold)
        try:
            inv.name = marker
            fwd.currency_purchased = 'USD'
            fwd.amount_purchased = None
            fwd.currency_sold = 'EUR'  # non-USD so sold_usd is also None
            fwd.amount_sold = None
            df = fund_report.options_data()
            row = df[df['name'] == marker]
            assert len(row) == 1, "marker row must be present exactly once"
            r = row.iloc[0]
            assert r['nested_derivative_type'] == 'Forward'
            # The derived USD columns must be None/NaN, not zero or junk.
            assert pd.isna(r['primary_exposure_usd']), (
                f"primary_exposure_usd should be NaN when both legs are null/"
                f"non-USD, got {r['primary_exposure_usd']!r}"
            )
        finally:
            inv.name = original_name
            fwd.currency_purchased, fwd.amount_purchased = original_purchased
            fwd.currency_sold, fwd.amount_sold = original_sold

    def test_usd_purchased_with_real_amount_still_populates(self, fund_report):
        # Inverse control: the non-bug path must still produce the USD amount.
        # We expect the sample to already contain at least one forward with a
        # real USD-denominated purchased leg.
        df = fund_report.options_data()
        fwd_rows = df[df['nested_derivative_type'] == 'Forward']
        assert len(fwd_rows) > 0, "Sample 7 must yield forward rows"

        # At least one row should have a populated primary_exposure_usd —
        # this confirms we did not over-guard and break the happy path.
        populated = fwd_rows['primary_exposure_usd'].notna()
        assert populated.any(), (
            "no nested-forward row has a populated primary_exposure_usd; "
            "the null guard may be returning None even for valid USD amounts"
        )
