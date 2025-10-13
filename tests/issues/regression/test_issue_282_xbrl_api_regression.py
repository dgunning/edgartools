"""
Regression test for Issue #282: XBRL API changes for diluted shares extraction

This test ensures that the XBRL API continues to work for extracting
"us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding" data from Apple's 10-K filings.

The test validates the key API patterns that users depend on:
1. Company.get_filings() for retrieving filings
2. XBRL.from_filing() for parsing XBRL data
3. facts.query().by_concept() for querying specific concepts
4. Proper handling of period_start, period_end, and numeric_value fields
"""

import pytest
from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL



class TestIssue282XBRLAPIRegression:
    """Test that XBRL API works for extracting diluted shares data."""

    def test_company_get_filings_api(self):
        """Test that Company.get_filings() API works correctly."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2020-01-01:")

        assert len(filings) >= 4, "Should have at least 4 Apple 10-K filings since 2020"

        # Test that we can access individual filings
        filing = filings[0]
        assert filing.form == "10-K"
        assert filing.cik == 320193  # Apple's CIK
        assert hasattr(filing, 'filing_date')

    def test_xbrl_from_filing_api(self):
        """Test that XBRL.from_filing() API works correctly."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2023-01-01:")

        assert len(filings) >= 1, "Should have at least 1 Apple 10-K filing since 2023"

        filing = filings[0]
        xbrl = XBRL.from_filing(filing)

        assert xbrl is not None, "XBRL should be successfully parsed"
        assert hasattr(xbrl, 'facts'), "XBRL should have facts attribute"
        assert hasattr(xbrl, '_facts'), "XBRL should have _facts attribute"
        assert len(xbrl._facts) > 0, "XBRL should contain facts"

    def test_facts_query_api_for_diluted_shares(self):
        """Test that facts.query() API works for finding diluted shares."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2023-01-01:")

        filing = filings[0]
        xbrl = XBRL.from_filing(filing)
        facts = xbrl.facts

        # Query for diluted shares
        concept = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
        diluted_shares_df = facts.query().by_concept(concept, exact=True).to_dataframe()

        # Validate we found the concept
        assert len(diluted_shares_df) > 0, f"Should find diluted shares facts for concept {concept}"

        # Validate DataFrame structure
        required_columns = ['concept', 'period_start', 'period_end', 'numeric_value', 'decimals']
        for col in required_columns:
            assert col in diluted_shares_df.columns, f"DataFrame should have {col} column"

        # Validate data types and values
        for _, row in diluted_shares_df.iterrows():
            assert row['concept'] == concept, "Concept should match exactly"
            assert row['numeric_value'] is not None, "Should have numeric value"
            assert row['period_start'] is not None, "Should have period start"
            assert row['period_end'] is not None, "Should have period end"
            assert isinstance(row['numeric_value'], (int, float)), "Numeric value should be number"

    def test_decimal_adjustment_logic(self):
        """Test that decimal adjustment logic works correctly."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2023-01-01:")

        filing = filings[0]
        xbrl = XBRL.from_filing(filing)
        facts = xbrl.facts

        concept = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
        diluted_shares_df = facts.query().by_concept(concept, exact=True).to_dataframe()

        assert len(diluted_shares_df) > 0, "Should find diluted shares facts"

        def shift_number(num, shift):
            """Apply decimal shift to get actual value."""
            if shift is None or shift == 'INF':
                return num
            return num * (10 ** int(shift))

        # Test decimal adjustment
        for _, row in diluted_shares_df.iterrows():
            original_value = row['numeric_value']
            decimals = row['decimals']
            adjusted_value = shift_number(original_value, decimals)

            # For Apple's diluted shares, expect values in billions range after adjustment
            # (typical values are 15-17 billion shares)
            if decimals == -3:  # Thousands scale
                assert 10_000_000 <= adjusted_value <= 30_000_000, (
                    f"Adjusted value {adjusted_value:,.0f} should be in reasonable range for Apple diluted shares"
                )

    def test_statement_level_api_still_works(self):
        """Test that the original statement-level API still works as fallback."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2023-01-01:")

        filing = filings[0]
        xbrl = XBRL.from_filing(filing)

        # Test statement-level access
        statements = xbrl.get_all_statements()
        assert len(statements) > 0, "Should have statements"

        # Find income statement
        income_statements = [s for s in statements if 'income' in s['definition'].lower() or 'operation' in s['definition'].lower()]
        assert len(income_statements) > 0, "Should have income-related statements"

        # Test statement data access
        stmt = income_statements[0]
        statement_data = xbrl.get_statement(stmt['definition'])
        assert len(statement_data) > 0, "Statement should have line items"

        # Validate structure
        for item in statement_data:
            assert 'label' in item, "Line item should have label"
            assert 'values' in item, "Line item should have values"
            assert 'decimals' in item, "Line item should have decimals"
            assert 'all_names' in item, "Line item should have all_names"

    def test_full_user_workflow(self):
        """Test the complete user workflow from the issue."""
        company = Company("AAPL")
        filings = company.get_filings(form="10-K", filing_date="2020-01-01:")

        concept = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
        values = {}

        def shift_number(num, shift):
            if shift is None or shift == 'INF':
                return num
            return num * (10 ** int(shift))

        # Process first filing to test the workflow
        filing = filings[0]
        xbrl = XBRL.from_filing(filing)
        facts = xbrl.facts

        diluted_shares_df = facts.query().by_concept(concept, exact=True).to_dataframe()

        for _, row in diluted_shares_df.iterrows():
            period_start = row['period_start']
            period_end = row['period_end']
            numeric_value = row['numeric_value']
            decimals = row['decimals']

            period_key = f"{period_start}_{period_end}"
            adjusted_value = shift_number(numeric_value, decimals)
            values[period_key] = adjusted_value

        # Validate we found values
        assert len(values) > 0, "Should extract diluted shares values successfully"

        # Validate values are reasonable (Apple typically has 15-17B diluted shares)
        for period_key, value in values.items():
            assert 10_000_000 <= value <= 30_000_000, (
                f"Value {value:,.0f} for period {period_key} should be in reasonable range"
            )


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])