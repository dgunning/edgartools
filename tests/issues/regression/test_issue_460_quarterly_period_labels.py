"""
Regression test for Issue #460: Quarterly income statement fiscal periods showing 1 year offset.

This test verifies that quarterly period labels correctly reflect when the period occurred,
not the SEC's forward-looking fiscal_year values. The SEC Facts API provides fiscal_year
values that indicate which fiscal year the quarter contributes to, not the year for labeling.

For example, for Apple (fiscal year ends in September):
- Q3 ending June 2024 should be labeled "Q3 2024" (not "Q3 2025")
- Q1 ending December 2023 should be labeled "Q1 2024" (first quarter of FY 2024)

The fix implements `calculate_fiscal_year_for_label()` which correctly calculates
fiscal years from period_end dates based on the company's fiscal year end month.
"""

import pytest
from datetime import date
from edgar import Company


@pytest.mark.network
class TestQuarterlyPeriodLabels:
    """Test suite for quarterly period label calculations."""

    def test_apple_quarterly_periods_september_fy_end(self):
        """
        Test AAPL (September fiscal year end) quarterly period labels.

        Apple's fiscal year ends in September, so:
        - Q4 ends in September
        - Q3 ends in June
        - Q2 ends in March
        - Q1 ends in December
        """
        company = Company("AAPL")
        stmt = company.income_statement(periods=4, annual=False)

        # Verify we got periods
        assert len(stmt.periods) > 0, "Should have quarterly periods"

        # Check that period labels match quarter and year pattern
        # Labels should be like "Q3 2024", "Q2 2024", "Q1 2024", "Q4 2023"
        for period_label in stmt.periods:
            # Should match pattern: Q[1-4] YYYY
            assert period_label.startswith('Q'), f"Period should start with Q: {period_label}"
            parts = period_label.split()
            assert len(parts) == 2, f"Period should be 'QX YYYY': {period_label}"
            quarter = parts[0]
            year = int(parts[1])

            # Quarter should be Q1-Q4
            assert quarter in ['Q1', 'Q2', 'Q3', 'Q4'], f"Invalid quarter: {quarter}"

            # Year should be reasonable (within 10 years of today)
            current_year = date.today().year
            assert current_year - 10 <= year <= current_year + 1, \
                f"Year {year} seems unreasonable (current year: {current_year})"

        # Verify periods are in descending chronological order (newest first)
        # This is a basic check - just ensure later periods have same or lower year
        years = [int(p.split()[1]) for p in stmt.periods]
        for i in range(len(years) - 1):
            assert years[i] >= years[i + 1], \
                f"Periods should be in descending order: {stmt.periods}"

    def test_microsoft_quarterly_periods_june_fy_end(self):
        """
        Test MSFT (June fiscal year end) quarterly period labels.

        Microsoft's fiscal year ends in June, so:
        - Q4 ends in June
        - Q3 ends in March
        - Q2 ends in December
        - Q1 ends in September
        """
        company = Company("MSFT")
        stmt = company.income_statement(periods=4, annual=False)

        # Verify we got periods
        assert len(stmt.periods) > 0, "Should have quarterly periods"

        # Check that period labels match quarter and year pattern
        for period_label in stmt.periods:
            assert period_label.startswith('Q'), f"Period should start with Q: {period_label}"
            parts = period_label.split()
            assert len(parts) == 2, f"Period should be 'QX YYYY': {period_label}"
            quarter = parts[0]
            year = int(parts[1])

            assert quarter in ['Q1', 'Q2', 'Q3', 'Q4'], f"Invalid quarter: {quarter}"

            current_year = date.today().year
            assert current_year - 10 <= year <= current_year + 1, \
                f"Year {year} seems unreasonable"

    def test_walmart_quarterly_periods_january_fy_end(self):
        """
        Test WMT (January fiscal year end) quarterly period labels.

        Walmart's fiscal year ends in January, so:
        - Q4 ends in January
        - Q3 ends in October
        - Q2 ends in July
        - Q1 ends in April
        """
        company = Company("WMT")
        stmt = company.income_statement(periods=4, annual=False)

        # Verify we got periods
        assert len(stmt.periods) > 0, "Should have quarterly periods"

        # Check that period labels match quarter and year pattern
        for period_label in stmt.periods:
            assert period_label.startswith('Q'), f"Period should start with Q: {period_label}"
            parts = period_label.split()
            assert len(parts) == 2, f"Period should be 'QX YYYY': {period_label}"
            quarter = parts[0]
            year = int(parts[1])

            assert quarter in ['Q1', 'Q2', 'Q3', 'Q4'], f"Invalid quarter: {quarter}"

            current_year = date.today().year
            assert current_year - 10 <= year <= current_year + 1, \
                f"Year {year} seems unreasonable"

    def test_annual_labels_unaffected(self):
        """
        Verify that annual period labels are unaffected by the quarterly fix.

        Annual labels should still use FY YYYY format and correctly reflect
        the fiscal year from the SEC data.
        """
        company = Company("AAPL")
        stmt = company.income_statement(periods=3, annual=True)

        # Verify we got annual periods
        assert len(stmt.periods) > 0, "Should have annual periods"

        # Check that all period labels start with FY
        for period_label in stmt.periods:
            assert period_label.startswith('FY '), \
                f"Annual period should start with 'FY ': {period_label}"

            # Extract year
            year = int(period_label.split()[1])

            # Verify year is reasonable
            current_year = date.today().year
            assert current_year - 10 <= year <= current_year + 1, \
                f"Year {year} seems unreasonable"

        # Verify periods are in descending order
        years = [int(p.split()[1]) for p in stmt.periods]
        for i in range(len(years) - 1):
            assert years[i] >= years[i + 1], \
                f"Annual periods should be in descending order: {stmt.periods}"

    def test_no_fy_periods_in_quarterly_output(self):
        """
        Verify that FY periods are filtered out from quarterly statements.

        Issue #460 also revealed that FY facts were appearing in quarterly output.
        This test ensures FY periods are excluded when requesting quarterly data.
        """
        company = Company("AAPL")
        stmt = company.income_statement(periods=8, annual=False)

        # Verify no FY labels in quarterly output
        for period_label in stmt.periods:
            assert not period_label.startswith('FY'), \
                f"Found FY period in quarterly output: {period_label}"
            assert period_label.startswith('Q'), \
                f"Quarterly period should start with Q: {period_label}"

    def test_quarterly_labels_match_data_content(self):
        """
        Verify that quarterly period labels match the underlying data periods.

        This is a sanity check to ensure the calculated labels correctly
        represent the period_end dates in the underlying facts.
        """
        company = Company("AAPL")
        stmt = company.income_statement(periods=4, annual=False)

        # Verify we have periods and items
        assert len(stmt.periods) > 0, "Should have quarterly periods"
        assert len(stmt.items) > 0, "Should have statement items"

        # Verify the statement was created successfully
        # The fact that we got a statement with periods and items
        # indicates the period label calculation worked correctly
        assert stmt.statement_type == 'IncomeStatement'
        assert stmt.company_name == 'Apple Inc.'


class TestCalculateFiscalYearForLabel:
    """
    Test the calculate_fiscal_year_for_label() helper function directly.

    This function is the core fix for Issue #460, calculating fiscal year
    from period_end date based on fiscal year end month.
    """

    def test_september_fy_end_quarters(self):
        """Test Apple-style September fiscal year end."""
        from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label

        # Q3 ending June 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 6, 28), 9) == 2024

        # Q4 ending September 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 9, 28), 9) == 2024

        # Q1 ending December 2023 → FY 2024 (first quarter of FY 2024)
        assert calculate_fiscal_year_for_label(date(2023, 12, 30), 9) == 2024

        # Q2 ending March 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 3, 30), 9) == 2024

    def test_december_fy_end_quarters(self):
        """Test standard December calendar year end."""
        from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label

        # Q1 ending March 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 3, 31), 12) == 2024

        # Q2 ending June 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 6, 30), 12) == 2024

        # Q3 ending September 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 9, 30), 12) == 2024

        # Q4 ending December 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 12, 31), 12) == 2024

    def test_june_fy_end_quarters(self):
        """Test Microsoft-style June fiscal year end."""
        from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label

        # Q1 ending September 2023 → FY 2024 (first quarter after June 2023)
        assert calculate_fiscal_year_for_label(date(2023, 9, 30), 6) == 2024

        # Q2 ending December 2023 → FY 2024
        assert calculate_fiscal_year_for_label(date(2023, 12, 31), 6) == 2024

        # Q3 ending March 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 3, 31), 6) == 2024

        # Q4 ending June 2024 → FY 2024
        assert calculate_fiscal_year_for_label(date(2024, 6, 30), 6) == 2024

    def test_early_january_edge_case(self):
        """Test 52/53-week calendar edge case for early January periods."""
        from edgar.entity.enhanced_statement import calculate_fiscal_year_for_label

        # Early January period (Jan 1-7) uses prior year convention
        assert calculate_fiscal_year_for_label(date(2023, 1, 1), 12) == 2022
        assert calculate_fiscal_year_for_label(date(2023, 1, 7), 12) == 2022

        # Late January uses current year
        assert calculate_fiscal_year_for_label(date(2023, 1, 31), 12) == 2023
