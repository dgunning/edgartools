"""
Regression test for Issue #440: Currency display for non-US companies

This test ensures that non-US companies show the correct currency symbols
in their financial statements (e.g., EUR for Deutsche Bank, not USD).

GitHub Issue: https://github.com/dgunning/edgartools/issues/440
"""

import pytest
from edgar import Company
import os


class TestCurrencyDisplay:
    """Tests for proper currency symbol display in financial statements."""

    @pytest.mark.data_quality
    @pytest.mark.slow
    def test_deutsche_bank_eur_currency_display(self):
        """Test that Deutsche Bank cash flow statement shows EUR symbols, not USD."""
        # Get Deutsche Bank company
        company = Company("DB")

        # Get latest 20-F filing
        filing = company.get_filings(form="20-F", amendments=False).latest()

        # Get XBRL and cash flow statement
        xbrl = filing.xbrl()
        cashflow = xbrl.statements.cashflow_statement()
        print(cashflow)

        # With the optimized version, currency is resolved on-demand, so we test directly
        # by checking if the XBRL instance can resolve currency correctly
        raw_data = cashflow.get_raw_data()

        # Find first monetary item with values
        monetary_item = None
        for item in raw_data:
            if item.get('has_values') and item.get('values'):
                # Test that currency can be resolved for this item
                element_name = item.get('name') or item.get('concept', '')
                if element_name:
                    for period_key in item['values'].keys():
                        currency = xbrl.get_currency_for_fact(element_name, period_key)
                        if currency:
                            monetary_item = item
                            monetary_item['test_currency'] = currency
                            break
                if monetary_item:
                    break

        assert monetary_item is not None, "Should find at least one monetary item with currency info"

        # Verify currency info contains EUR
        test_currency = monetary_item['test_currency']
        assert test_currency == 'iso4217:EUR', f"Expected EUR currency, got {test_currency}"

        # Check that rendered statement shows € symbols
        statement_str = str(cashflow)

        # Should contain euro symbols
        assert '€' in statement_str, "Cash flow statement should contain Euro symbols (€)"

        # Should NOT contain dollar symbols (except in descriptive text)
        lines = statement_str.split('\n')
        monetary_lines = [line for line in lines if any(char.isdigit() for char in line)]

        for line in monetary_lines:
            # Skip lines that are just headers or don't contain amounts
            if '€' in line or '$' in line:
                # If it's a monetary line, it should use € not $
                assert '€' in line, f"Monetary line should use € symbol: {line}"

    @pytest.mark.data_quality
    @pytest.mark.slow
    def test_us_company_usd_currency_display(self):
        """Test that US companies still show USD symbols correctly."""
        # Get Apple company
        company = Company("AAPL")

        # Get latest 10-K filing
        filing = company.get_filings(form="10-K", amendments=False).latest()

        # Get XBRL and cash flow statement
        xbrl = filing.xbrl()
        cashflow = xbrl.statements.cashflow_statement()

        # With the optimized version, test currency resolution directly
        raw_data = cashflow.get_raw_data()

        # Find first monetary item with values
        monetary_item = None
        for item in raw_data:
            if item.get('has_values') and item.get('values'):
                # Test that currency can be resolved for this item
                element_name = item.get('name') or item.get('concept', '')
                if element_name:
                    for period_key in item['values'].keys():
                        currency = xbrl.get_currency_for_fact(element_name, period_key)
                        if currency:
                            monetary_item = item
                            monetary_item['test_currency'] = currency
                            break
                if monetary_item:
                    break

        assert monetary_item is not None, "Should find at least one monetary item with currency info"

        # Verify currency info contains USD
        test_currency = monetary_item['test_currency']
        assert test_currency == 'iso4217:USD', f"Expected USD currency, got {test_currency}"

        # Check that rendered statement shows $ symbols
        statement_str = str(cashflow)

        # Should contain dollar symbols
        assert '$' in statement_str, "Cash flow statement should contain Dollar symbols ($)"

    def test_currency_symbol_mapping(self):
        """Test that currency symbol mapping function works correctly."""
        from edgar.xbrl.core import get_currency_symbol

        # Test common currencies
        assert get_currency_symbol('iso4217:USD') == '$'
        assert get_currency_symbol('iso4217:EUR') == '€'
        assert get_currency_symbol('iso4217:GBP') == '£'
        assert get_currency_symbol('iso4217:JPY') == '¥'
        assert get_currency_symbol('iso4217:CAD') == 'C$'

        # Test default fallback
        assert get_currency_symbol(None) == '$'
        assert get_currency_symbol('unknown:CURRENCY') == '$'

    def test_format_value_with_currency_symbol(self):
        """Test that format_value function works with currency symbols."""
        from edgar.xbrl.core import format_value

        test_value = 1000000  # 1 million

        # Test with different currency symbols
        assert format_value(test_value, True, -6, None, '$') == '$1'
        assert format_value(test_value, True, -6, None, '€') == '€1'
        assert format_value(test_value, True, -6, None, '£') == '£1'

        # Test negative values
        assert format_value(-test_value, True, -6, None, '€') == '€(1)'

        # Test default behavior (should still be $)
        assert format_value(test_value, True, -6, None) == '$1'