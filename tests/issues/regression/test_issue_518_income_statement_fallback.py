"""
Regression test for Issue #518: find_statement() incorrectly returns CashFlowStatement
when IncomeStatement not found.

This test ensures that when a filing has ComprehensiveIncome but no separate IncomeStatement,
the system correctly returns ComprehensiveIncome as a fallback instead of returning a
completely wrong statement type like CashFlowStatement.
"""

import pytest
from edgar import Company


class TestIssue518IncomeStatementFallback:
    """Test suite for Issue #518 - IncomeStatement fallback behavior."""

    def test_cort_2018_income_statement_fallback(self):
        """
        Test CORT 2018 10-K: Should return ComprehensiveIncome when IncomeStatement requested.

        This filing has ComprehensiveIncome but no separate IncomeStatement.
        Previously returned CashFlowStatement (wrong!), should now return ComprehensiveIncome.
        """
        # Get CORT 2018 10-K filing
        company = Company("CORT")
        filings = company.get_filings(form="10-K")
        filing = [f for f in filings if '2019-0' in str(f.filing_date)][0]

        assert filing.accession_no == "0001628280-19-001879"

        xbrl = filing.xbrl()

        # Test find_statement
        matching_statements, found_role, actual_statement_type = xbrl.find_statement('IncomeStatement')

        # Should find exactly one statement
        assert len(matching_statements) == 1, "Should find one statement"

        # Should be ComprehensiveIncome, NOT CashFlowStatement
        matched_type = matching_statements[0].get('type')
        assert matched_type == 'ComprehensiveIncome', \
            f"Expected ComprehensiveIncome but got {matched_type}"

        # Should NOT be CashFlowStatement
        assert matched_type != 'CashFlowStatement', \
            "Must not return CashFlowStatement when IncomeStatement is requested"

        # Issue #518 Accuracy Fix: Tuple type must match dict type (no misrepresentation)
        assert actual_statement_type == matched_type, \
            f"Type mismatch: tuple says '{actual_statement_type}' but dict says '{matched_type}'"

        # Users should be able to detect fallback by comparing requested vs actual
        assert actual_statement_type == 'ComprehensiveIncome', \
            f"Should return honest type 'ComprehensiveIncome', not '{actual_statement_type}'"

        # Test get_statement returns correct data
        statement_data = xbrl.get_statement('IncomeStatement')

        # Should have multiple line items (ComprehensiveIncome has ~20-30 lines)
        assert len(statement_data) > 15, \
            f"Expected >15 line items but got {len(statement_data)}"

        # Should contain income statement concepts
        concepts = [item.get('concept', '') for item in statement_data]

        # Check for income statement concepts (Revenue, Operating Income, etc.)
        has_revenue = any('Revenue' in c for c in concepts)
        has_operating_income = any('OperatingIncome' in c for c in concepts)

        assert has_revenue, "Should have Revenue concept"
        assert has_operating_income, "Should have OperatingIncome concept"

        # Should NOT have cash flow concepts
        has_operating_cash_flow = any('OperatingActivities' in c and 'Cash' in c for c in concepts)
        assert not has_operating_cash_flow, \
            "Should not have Operating Cash Flow concepts in Income Statement"

    def test_filing_with_separate_income_statement_still_works(self):
        """
        Test that filings with actual IncomeStatement continue to work correctly.

        This ensures the fallback logic doesn't break normal IncomeStatement retrieval.
        """
        # Use Apple 10-K which has a proper IncomeStatement
        company = Company("AAPL")
        filings = company.get_filings(form="10-K")
        filing = filings.latest(1)

        xbrl = filing.xbrl()

        # Test find_statement
        matching_statements, found_role, actual_statement_type = xbrl.find_statement('IncomeStatement')

        # Should find a statement
        assert len(matching_statements) > 0, "Should find income statement"

        # For filings with actual IncomeStatement, should return IncomeStatement
        # (not ComprehensiveIncome)
        matched_type = matching_statements[0].get('type')

        # Should be a valid income-related statement
        assert matched_type in ['IncomeStatement', 'ComprehensiveIncome'], \
            f"Expected IncomeStatement or ComprehensiveIncome but got {matched_type}"

        # Definitely should NOT be CashFlowStatement or BalanceSheet
        assert matched_type not in ['CashFlowStatement', 'BalanceSheet'], \
            f"Must not return {matched_type} when IncomeStatement is requested"

        # Issue #518 Accuracy Fix: Tuple type must match dict type
        assert actual_statement_type == matched_type, \
            f"Type mismatch: tuple says '{actual_statement_type}' but dict says '{matched_type}'"

    def test_statement_type_validation_prevents_wrong_types(self):
        """
        Test that type validation prevents returning completely wrong statement types.

        This ensures the fix in _match_by_content and xbrl.find_statement that validates
        statement types is working correctly.
        """
        company = Company("CORT")
        filings = company.get_filings(form="10-K")
        filing = [f for f in filings if '2019-0' in str(f.filing_date)][0]

        xbrl = filing.xbrl()

        # Request each major financial statement type
        for statement_type in ['IncomeStatement', 'BalanceSheet', 'CashFlowStatement']:
            matching_statements, _, actual_statement_type, *_ = xbrl.find_statement(statement_type)

            if matching_statements:
                matched_type = matching_statements[0].get('type')

                # Issue #518 Accuracy Fix: Verify tuple type matches dict type
                assert actual_statement_type == matched_type, \
                    f"Type mismatch for {statement_type}: tuple says '{actual_statement_type}' but dict says '{matched_type}'"

                # For each statement type, verify we didn't get a completely wrong type
                financial_types = {'BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                                   'ComprehensiveIncome', 'StatementOfEquity'}

                # If requesting IncomeStatement, ComprehensiveIncome is acceptable
                if statement_type == 'IncomeStatement':
                    assert matched_type in ['IncomeStatement', 'ComprehensiveIncome'], \
                        f"IncomeStatement request returned {matched_type}"
                else:
                    # For other types, should get exact match or compatible type
                    # But definitely not a completely different financial statement
                    assert matched_type == statement_type or matched_type not in financial_types, \
                        f"{statement_type} request returned wrong type: {matched_type}"
