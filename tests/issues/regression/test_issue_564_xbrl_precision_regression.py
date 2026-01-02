"""
Regression test for Issue #564: XBRL Assets values incorrectly rounded

This test ensures that when multiple facts exist for the same concept and context
with different precision (decimals attribute), the most precise fact is selected.

The issue manifested as:
- PFE 2017: Total Assets showed $172,000M (rounded) instead of $171,797M (precise)
- PFE 2018: Total Assets showed $159,000M instead of $159,422M
- ZTS 2018: Total Assets showed $10,800M instead of $10,777M

Root cause: When duplicate facts exist in the same context with different decimals
values (e.g., -9 for billions precision, -6 for millions precision), the code was
selecting the first fact encountered rather than the most precise one.

Fix: Modified _find_facts_for_element() in xbrl.py to use get_facts_by_key() and
select the fact with the highest decimals value (most precise).

Reporter: @mpreiss9
"""

import pytest
from edgar import Company
from edgar.xbrl.xbrl import XBRL


@pytest.fixture(scope="module")
def pfizer_10k_2017():
    """Pfizer 10-K for fiscal year 2017 (filed 2018-02-22)."""
    company = Company("PFE")
    filing = company.get_filings(accession_number="0000078003-18-000027").latest()
    return XBRL.from_filing(filing)


@pytest.fixture(scope="module")
def pfizer_10k_2018():
    """Pfizer 10-K for fiscal year 2018 (filed 2019-02-28)."""
    company = Company("PFE")
    filing = company.get_filings(accession_number="0000078003-19-000015").latest()
    return XBRL.from_filing(filing)


@pytest.fixture(scope="module")
def zoetis_10k_2018():
    """Zoetis 10-K for fiscal year 2018 (filed 2019-02-14)."""
    company = Company("ZTS")
    filing = company.get_filings(accession_number="0001555280-19-000041").latest()
    return XBRL.from_filing(filing)


class TestIssue564XBRLPrecisionSelection:
    """Test that XBRL facts with highest precision are selected when duplicates exist."""

    def test_pfizer_2017_total_assets_precise(self, pfizer_10k_2017):
        """Test that Pfizer 2017 Total Assets shows precise value, not rounded."""
        stmt = pfizer_10k_2017.statements.balance_sheet()
        raw_data = stmt.get_raw_data()

        # Find Total Assets (case-insensitive)
        total_assets_item = None
        for item in raw_data:
            if item.get('label', '').lower() == 'total assets':
                total_assets_item = item
                break

        assert total_assets_item is not None, "Total Assets not found in balance sheet"

        values = total_assets_item.get('values', {})
        decimals = total_assets_item.get('decimals', {})

        # 2017-12-31 value should be precise (171,797M), not rounded (172,000M)
        value_2017 = values.get('instant_2017-12-31')
        assert value_2017 is not None, "2017-12-31 value not found"
        assert value_2017 == pytest.approx(171797000000.0), \
            f"Expected 171,797,000,000, got {value_2017}"

        # Decimals should be -6 (millions precision), not -9 (billions)
        dec_2017 = decimals.get('instant_2017-12-31')
        assert dec_2017 == -6, f"Expected decimals=-6, got {dec_2017}"

    def test_pfizer_2018_total_assets_precise(self, pfizer_10k_2018):
        """Test that Pfizer 2018 Total Assets shows precise value, not rounded."""
        stmt = pfizer_10k_2018.statements.balance_sheet()
        raw_data = stmt.get_raw_data()

        # Find Total Assets (case-insensitive)
        total_assets_item = None
        for item in raw_data:
            if item.get('label', '').lower() == 'total assets':
                total_assets_item = item
                break

        assert total_assets_item is not None, "Total Assets not found in balance sheet"

        values = total_assets_item.get('values', {})

        # 2018-12-31 value should be precise (159,422M), not rounded (159,000M)
        value_2018 = values.get('instant_2018-12-31')
        assert value_2018 is not None, "2018-12-31 value not found"
        assert value_2018 == pytest.approx(159422000000.0), \
            f"Expected 159,422,000,000, got {value_2018}"

    def test_zoetis_2018_total_assets_precise(self, zoetis_10k_2018):
        """Test that Zoetis 2018 Total Assets shows precise value, not rounded."""
        stmt = zoetis_10k_2018.statements.balance_sheet()
        raw_data = stmt.get_raw_data()

        # Find Total Assets (case-insensitive)
        total_assets_item = None
        for item in raw_data:
            if item.get('label', '').lower() == 'total assets':
                total_assets_item = item
                break

        assert total_assets_item is not None, "Total Assets not found in balance sheet"

        values = total_assets_item.get('values', {})

        # 2018-12-31 value should be precise (10,777M), not rounded (10,800M)
        value_2018 = values.get('instant_2018-12-31')
        assert value_2018 is not None, "2018-12-31 value not found"
        assert value_2018 == pytest.approx(10777000000.0), \
            f"Expected 10,777,000,000, got {value_2018}"

    def test_balance_sheet_equation_balances(self, pfizer_10k_2017):
        """Test that Assets = Liabilities + Equity (balance sheet equation)."""
        stmt = pfizer_10k_2017.statements.balance_sheet()
        raw_data = stmt.get_raw_data()

        # Find Total Assets and Total Liabilities and Stockholders' Equity (case-insensitive)
        total_assets = None
        total_liab_equity = None

        for item in raw_data:
            label = item.get('label', '').lower()
            if label == 'total assets':
                total_assets = item.get('values', {}).get('instant_2017-12-31')
            elif 'total liabilities and' in label and 'equity' in label:
                total_liab_equity = item.get('values', {}).get('instant_2017-12-31')

        assert total_assets is not None, "Total Assets not found"
        assert total_liab_equity is not None, "Total Liabilities and Equity not found"

        # They should be equal (accounting equation)
        assert total_assets == pytest.approx(total_liab_equity), \
            f"Balance sheet doesn't balance: Assets={total_assets}, L+E={total_liab_equity}"
