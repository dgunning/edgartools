"""Regression: an N-PORT "Yes" to a securities-lending question reads "Y", with its amount.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1585

Item C.12 states a No as an element, ``<isCashCollateral>N</isCashCollateral>``, and
a Yes as attributes of another element, ``<cashCollateralCondition
isCashCollateral="Y" cashCollateralVal="..."/>``. Non-cash collateral and loans by
the fund take the same two shapes (``SECURITY_LENDING_GROUP`` in
``data/nport/schema/eis_NPORT_Filer.xsd``). ``SecurityLending.from_xml`` read only
the elements, so every Yes read None, the same as an unanswered item, and the
amount was lost. On SGOV's NPORT-P for 2026-05-31 (0002071691-26-016719) that was
1 of 24 cash-collateral answers and 2 of 24 loan answers; on IVV's
(0002071691-26-019760), 1 and 59 of 508.
"""
from collections import Counter
from decimal import Decimal

import pytest
from lxml import etree

from edgar.funds.reports import SecurityLending


@pytest.mark.fast
def test_a_yes_condition_reads_y_with_its_amount():
    # SGOV's BlackRock Funds III holding, CUSIP 066922477, verbatim.
    lending = SecurityLending.from_xml(etree.fromstring(
        b'<securityLending>'
        b'<cashCollateralCondition cashCollateralVal="441347500.00000000" isCashCollateral="Y"/>'
        b'<isNonCashCollateral>N</isNonCashCollateral>'
        b'<isLoanByFund>N</isLoanByFund>'
        b'</securityLending>'))
    assert (lending.is_cash_collateral, lending.cash_collateral_value) == ('Y', Decimal('441347500.00000000'))
    assert (lending.is_non_cash_collateral, lending.non_cash_collateral_value) == ('N', None)
    assert (lending.is_loan_by_fund, lending.loan_value) == ('N', None)


@pytest.mark.fast
def test_every_yes_condition_in_the_schema_is_read():
    # The three Yes shapes from data/nport/samples/N-PORT Sample 3.xml.
    lending = SecurityLending.from_xml(etree.fromstring(
        b'<securityLending>'
        b'<cashCollateralCondition isCashCollateral="Y" cashCollateralVal="-5.55"/>'
        b'<nonCashCollateralCondition isNonCashCollateral="Y" nonCashCollateralVal="5.55"/>'
        b'<loanByFundCondition isLoanByFund="Y" loanVal="5.55"/>'
        b'</securityLending>'))
    assert (lending.is_cash_collateral, lending.cash_collateral_value) == ('Y', Decimal('-5.55'))
    assert (lending.is_non_cash_collateral, lending.non_cash_collateral_value) == ('Y', Decimal('5.55'))
    assert (lending.is_loan_by_fund, lending.loan_value) == ('Y', Decimal('5.55'))


@pytest.mark.network
@pytest.mark.vcr
def test_sgov_states_one_cash_collateral_yes_and_two_loans():
    """Ground truth: SGOV's NPORT-P for 2026-05-31, accession 0002071691-26-016719."""
    from edgar import find
    from edgar.funds.reports import FundReport

    report = FundReport.from_filing(find('0002071691-26-016719'))
    lending = [(i.cusip, i.security_lending) for i in report.investments]
    assert len(lending) == 24
    assert Counter(sl.is_cash_collateral for _, sl in lending) == Counter({'N': 23, 'Y': 1})
    assert Counter(sl.is_loan_by_fund for _, sl in lending) == Counter({'N': 22, 'Y': 2})
    assert [(cusip, sl.cash_collateral_value) for cusip, sl in lending if sl.is_cash_collateral == 'Y'] == [
        ('066922477', Decimal('441347500.00000000'))]
    assert sorted((cusip, sl.loan_value) for cusip, sl in lending if sl.is_loan_by_fund == 'Y') == [
        ('912797TN7', Decimal('124435125.00000000')), ('912797TU1', Decimal('307969200.00000000'))]
