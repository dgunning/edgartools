"""Regression: only a footnote about its own holding flags it as non-accrual.

Bead: edgartools-t75ot

``_classify_nonaccrual_footnote`` flagged any short linked footnote that
mentioned non-accrual, and any footnote with an affirmative sentence anywhere
in it. Policy notes, portfolio-level counts and bundles of numbered notes
passed, and every holding linked to them was counted:

- Logan Ridge FY2024: "All debt investments are income producing except for
  non-accrual investments" flagged 30 holdings, $102.6M of a $172M book.
- AGL Private Credit Income Fund 2025-09-30: "the Company had one portfolio
  company investment on non-accrual status" flagged 82 holdings, 96.6%.
- Runway Growth Finance 2026-09-30: a 943-word block of numbered notes holding
  "(22) Investment is on non-accrual status" flagged 126 holdings, 98.8%.

Measured on the 332 distinct footnote texts edgartools flagged across 830 BDC
filings (2023 Q4 to 2026 Q3): the new rule keeps all 319 that state the holding
is on non-accrual, plus two liquidation notes that say so in a later sentence,
and drops 11 texts, 941 flagged rows and $4.21B of fair value.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _classify_nonaccrual_footnote

NOT_FLAGS = [
    # Logan Ridge, policy
    "All debt investments are income producing except for non-accrual investments. "
    "Equity and warrant investments are non-income producing, unless otherwise noted.",
    # Oxford Square, policy
    "Cost value reflects accretion of original issue discount or market discount, or amortization of premium. "
    "No income from accretion is recognized on non-accrual investments.",
    # AGL, a portfolio-level count
    "As of September 30, 2025, the Company had one portfolio company investment on non-accrual status "
    "with a fair value of $20,350.",
    # A bundle of numbered notes
    "(1) Disclosures of interest rates on notes include cash interest rates and payment-in-kind interest rates. "
    "(2) Investment is held through a wholly owned subsidiary. (22) Investment is on non-accrual status.",
    # A note on another subject with a numbered marker buried in it
    "Included in the total is an amount of $3,865 held for collateral to meet requirements associated with "
    "the Secured Loan Facility. Please refer to Note 6.(18)Investment is on non-accrual status.",
    "Positions may be placed on non-accrual status when payment is doubtful.",
]

FLAGS = [
    "Non-accrual investment.",
    "(14)Loan was on non-accrual status as of December 31, 2024.",
    "As of March 31, 2026, this investment was on non-accrual status and no interest income is recognized.",
    # The statement about the holding comes second (Sundance, CIK 1747172).
    "Portfolio company is in a liquidation process and, as such, the maturity date of our debt investment in "
    "this portfolio company will not be finally determined until such process is complete. Our debt investment "
    "in this portfolio company is on non-accrual status.",
]


@pytest.mark.parametrize("text", NOT_FLAGS)
def test_a_footnote_not_about_its_holding_is_not_a_flag(text):
    assert _classify_nonaccrual_footnote(text.lower(), linked_to_investments=True) is False


@pytest.mark.parametrize("text", FLAGS)
def test_a_footnote_about_its_holding_is_a_flag(text):
    assert _classify_nonaccrual_footnote(text.lower(), linked_to_investments=True) is True


@pytest.mark.network
@pytest.mark.vcr
def test_agl_portfolio_count_flags_only_the_marked_loan():
    """AGL Private Credit Income Fund 10-Q for 2025-09-30 (0001193125-25-269116).

    The filing: "one portfolio company investment on non-accrual status with a
    fair value of $20,350" (thousands).
    """
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001193125-25-269116'))
    assert result.num_nonaccrual == 1
    assert result.nonaccrual_fair_value == Decimal('20350000')
