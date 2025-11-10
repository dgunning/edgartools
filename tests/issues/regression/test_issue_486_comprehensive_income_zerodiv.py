"""
Regression test for GitHub issue #486: ZeroDivisionError in comprehensive income access

This test ensures that comprehensive income statements can be accessed without
ZeroDivisionError, even when weight_map is empty or sums to zero.

The bug was in edgar/xbrl/statement_resolver.py:626 where division by
sum(weight_map.values()) occurred without checking if it was zero.

Root cause: total_weight > 0 but sum(weight_map.values()) == 0, causing
ZeroDivisionError and blocking access to legitimate financial data.

Affected ~9.5% of filings (~2,038 filings, 28+ companies).
"""

import pytest

from edgar import Filing


class TestComprehensiveIncomeZeroDivision:
    """Test cases for comprehensive income access without ZeroDivisionError"""

    @pytest.mark.network
    def test_nsp_comprehensive_income_primary_method(self):
        """Test primary method for NSP (CIK 1000753) - main reproduction case"""
        # NSP 2024 10-K from GitHub issue #486
        filing = Filing(company='INSPERITY INC', cik=1000753, form='10-K',
                       filing_date='2024-02-12', accession_no='0001000753-24-000012')

        xb = filing.xbrl()

        # Primary method should work without ZeroDivisionError
        ci = xb.statements.comprehensive_income()

        # Should return a statement (not None)
        assert ci is not None, "Comprehensive income statement should be found"

        # Should be renderable
        assert ci.to_dataframe() is not None
        assert len(ci.to_dataframe()) > 0

    @pytest.mark.network
    def test_nsp_comprehensive_income_bracket_notation(self):
        """Test bracket notation and to_dataframe() for NSP - crash scenario from issue"""
        # NSP 2024 10-K from GitHub issue #486
        filing = Filing(company='INSPERITY INC', cik=1000753, form='10-K',
                       filing_date='2024-02-12', accession_no='0001000753-24-000012')

        xb = filing.xbrl()

        # Bracket notation should find the statement
        ci_br = xb.statements['ComprehensiveIncome']
        assert ci_br is not None, "Bracket notation should find statement"

        # to_dataframe() should NOT raise ZeroDivisionError
        try:
            df = ci_br.to_dataframe()
            assert df is not None
            assert len(df) > 0
            # Success - the bug is fixed
        except ZeroDivisionError as e:
            pytest.fail(f"ZeroDivisionError raised: {e}. Bug #486 not fixed.")

    @pytest.mark.network
    def test_comprehensive_income_multiple_affected_companies(self):
        """Test a sample of other affected companies from the issue"""
        # Test a few companies from the list of 28+ affected CIKs
        test_ciks = [
            1001601,  # Another affected company
            1009829,  # Another affected company
        ]

        for cik in test_ciks:
            try:
                from edgar import Company
                company = Company(str(cik))
                filing = company.get_filings(form="10-K").latest(1)

                if filing:
                    xb = filing.xbrl()

                    # Try both methods - should not crash
                    ci_primary = xb.statements.comprehensive_income()
                    ci_bracket = xb.statements.get('ComprehensiveIncome')

                    # If bracket notation finds something, to_dataframe() should work
                    if ci_bracket:
                        df = ci_bracket.to_dataframe()
                        assert df is not None

            except ZeroDivisionError as e:
                pytest.fail(f"ZeroDivisionError for CIK {cik}: {e}. Bug #486 not fixed.")
            except Exception:
                # Other exceptions are OK (e.g., network issues, no filings)
                # We're only testing for ZeroDivisionError
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
