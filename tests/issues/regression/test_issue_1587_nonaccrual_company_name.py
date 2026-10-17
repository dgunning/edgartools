"""Regression: the non-accrual roster names the borrower as ``from_xbrl`` does.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1587

``_extract_from_footnotes`` parsed each flagged identifier with no member
candidates, while ``PortfolioInvestments.from_xbrl`` bounds the company name by
the filing's own taxonomy members (``_get_investment_member_candidates``). On
labels that carry headings or an industry before the company, the roster then
named the borrower by the whole label: all 4 rows of Hercules' 10-Q for
2026-06-30 (0001280784-26-000042) read "Debt Investments, Application Software,
Annex Cloud, Senior Secured, ...". Re-parsing 37 BDC filings, 130 of 415
non-accrual rows across 14 filings changed name, and 408 of 415 now match
``from_xbrl``'s name for the same identifier (285 before); the other 7 have no
``from_xbrl`` row to compare with.
"""
from decimal import Decimal

import pytest


@pytest.mark.network
@pytest.mark.vcr
def test_hercules_non_accruals_are_named_by_company():
    """Ground truth: Hercules Capital 10-Q for 2026-06-30, accession 0001280784-26-000042."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001280784-26-000042'))
    assert result.extraction_method == 'footnote'
    assert sorted((i.company_name, i.investment_type, i.fair_value) for i in result.investments) == [
        ('Annex Cloud', 'Senior Secured', Decimal('0.0')),
        ('Annex Cloud', 'Senior Secured', Decimal('0.0')),
        ('Annex Cloud', 'Senior Secured', Decimal('3325000.0')),
        ('Simon Data, Inc.', 'Senior Secured', Decimal('2194000.0')),
    ]
