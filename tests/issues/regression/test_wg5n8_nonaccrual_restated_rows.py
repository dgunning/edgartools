"""Regression: a non-accrual holding listed in two schedules is counted once.

Bead: edgartools-wg5n8

Logan Ridge's FY2024 10-K (0000950170-25-038761) lists MMI Holdings in its
schedule of investments (with cost) and again under "Affiliate investments"
(without cost), and links both to its "Non-accrual investment." footnote, so
``extract_nonaccrual()`` read 6 positions and $10,860,000. The filing: "debt
investments in three portfolio companies on non-accrual status with ... an
aggregate fair value of $7.9 million, which represented ... 4.6%".

The flagged rows now go through ``_exclude_restated_rows``, the rule
``PortfolioInvestments.from_xbrl`` already applies to the whole schedule. Across
the latest 10-K and 10-Q of 351 active BDCs it changed three filings, each a
cost-less copy of a flagged costed row (Logan Ridge twice, Barings BDC once).
"""
from decimal import Decimal

from edgar.bdc.nonaccrual import NonAccrualInvestment, _drop_restated


def _inv(identifier, fv, cost):
    return NonAccrualInvestment(identifier=identifier, company_name='', investment_type='',
                                fair_value=Decimal(fv), cost=None if cost is None else Decimal(cost),
                                footnote_text='Non-accrual investment.')


def test_a_costless_copy_of_a_flagged_row_is_dropped():
    original = _inv('Affiliated First Lien/Senior Secured Debt MMI Holdings, LLC', 2556000, 2600000)
    copy = _inv('Affiliate investments MMI Holdings, LLC First Lien Debt', 2556000, None)
    other = _inv('Subordinated Debt Lucky Bucks, LLC', 485000, 2229000)
    assert _drop_restated([original, copy, other]) == [original, other]


def test_a_copy_whose_original_is_not_flagged_is_kept():
    copy = _inv('Affiliate investments MMI Holdings, LLC First Lien Debt', 2556000, None)
    assert _drop_restated([copy]) == [copy]


def test_logan_ridge_counts_three_companies_once():
    """The six rows Logan Ridge's 10-K for 2024-12-31 (0000950170-25-038761) flags.

    The filing: three companies, $7.9 million, 4.6% of $172,290,000.
    """
    rows = [
        _inv('Investments in Non-Control, Non-Affiliate Portfolio Companies First Lien/Senior Secured Debt '
             'Sequoia Healthcare Management, LLC Healthcare Management Maturity 11/04/2023', 4529000, 11935000),
        _inv('Investments in Non-Control, Non-Affiliate Portfolio Companies Subordinated Debt '
             'Lucky Bucks, LLC Consumer Discretionary Maturity 05/29/2028', 485000, 2229000),
        _inv('Investments in Affiliated Portfolio Companies Second Lien/Senior Secured Debt '
             'MMI Holdings, LLC Medical Device Distributor Maturity 06/28/2024', 367000, 400000),
        _inv('Investments in Affiliated Portfolio Companies First Lien/Senior Secured Debt '
             'MMI Holdings, LLC Medical Device Distributor Maturity 06/28/2024', 2556000, 2600000),
        _inv('Affiliate investments MMI Holdings, LLC First Lien Debt', 2556000, None),
        _inv('Affiliate investments MMI Holdings, LLC Second Lien Debt', 367000, None),
    ]
    kept = _drop_restated(rows)
    assert kept == rows[:4]
    total = sum(inv.fair_value for inv in kept)
    assert total == Decimal('7937000')
    assert round(total / Decimal('172290000'), 3) == Decimal('0.046')
