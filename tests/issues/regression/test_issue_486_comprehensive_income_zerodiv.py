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

from edgar import Filing, Company
from edgar.xbrl.exceptions import StatementNotFound


class TestComprehensiveIncomeZeroDivision:
    """Test cases for comprehensive income access without ZeroDivisionError"""

    @pytest.mark.network
    def test_comprehensive_income_no_zerodiv_error(self):
        """Test that accessing comprehensive income does not raise ZeroDivisionError.

        The original bug was ZeroDivisionError when weight_map sums to zero.
        This test verifies the fix by attempting to access comprehensive income
        on multiple filings - even if the statement doesn't exist, it should
        NOT raise ZeroDivisionError (it may raise StatementNotFound instead).
        """
        # Test with Apple which has comprehensive income
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest(1)
        xb = filing.xbrl()

        # This should NOT raise ZeroDivisionError
        try:
            ci = xb.statements.comprehensive_income()
            if ci is not None:
                # If found, should be renderable
                df = ci.to_dataframe()
                assert df is not None
        except ZeroDivisionError as e:
            pytest.fail(f"ZeroDivisionError raised: {e}. Bug #486 not fixed.")
        except StatementNotFound:
            # Statement not found is OK - we're testing that ZeroDivisionError doesn't occur
            pass

    @pytest.mark.network
    def test_comprehensive_income_bracket_notation_no_zerodiv(self):
        """Test bracket notation doesn't raise ZeroDivisionError"""
        company = Company("MSFT")
        filing = company.get_filings(form="10-K").latest(1)
        xb = filing.xbrl()

        # Bracket notation should NOT raise ZeroDivisionError
        try:
            ci_br = xb.statements['ComprehensiveIncome']
            if ci_br is not None:
                df = ci_br.to_dataframe()
                assert df is not None
        except ZeroDivisionError as e:
            pytest.fail(f"ZeroDivisionError raised: {e}. Bug #486 not fixed.")
        except (StatementNotFound, KeyError):
            # Statement not found is OK - we're testing that ZeroDivisionError doesn't occur
            pass

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
