"""
Regression test for GitHub issue #403: Support standard=True in stitched statements

This test ensures that the 'standard' parameter support in stitched statements 
doesn't regress in future changes.

Issue URL: https://github.com/dgunning/edgartools/issues/403
"""

import pytest
from unittest.mock import MagicMock
from edgar.xbrl.statements import StitchedStatements
from edgar.xbrl.stitching.xbrls import XBRLS


@pytest.mark.regression
class TestIssue403Regression:
    """Regression test for standard parameter in stitched statements."""
    
    def setup_method(self):
        """Set up mock objects for testing."""
        self.mock_xbrls = MagicMock(spec=XBRLS)
        self.statements = StitchedStatements(self.mock_xbrls)
        
    def test_all_statement_methods_accept_standard_parameter(self):
        """
        Regression test: All statement methods must accept 'standard' parameter.
        
        This prevents accidental removal of the standard parameter in future changes.
        """
        # List of all statement methods that should accept 'standard' parameter
        statement_methods = [
            'income_statement',
            'balance_sheet', 
            'cashflow_statement',
            'statement_of_equity',
            'comprehensive_income'
        ]
        
        # Test that each method accepts standard=True without raising TypeError
        for method_name in statement_methods:
            method = getattr(self.statements, method_name)
            
            # This should not raise TypeError
            try:
                method(standard=True)
                method(standard=False)
            except TypeError as e:
                if "unexpected keyword argument 'standard'" in str(e):
                    pytest.fail(f"Method {method_name} does not accept 'standard' parameter: {e}")
                # Other TypeErrors might be expected (e.g., from mocked dependencies)
            except Exception:
                # Other exceptions are fine - we're only testing parameter acceptance
                pass
                
    def test_standard_parameter_works(self):
        """
        Regression test: 'standard' parameter works correctly.
        
        This ensures the standard parameter continues to work.
        """
        from unittest.mock import patch
        
        # Test with income_statement as representative
        with patch('edgar.xbrl.statements.StitchedStatement') as mock_stitched:
            # Test standard parameter works
            self.statements.income_statement(standard=True)
            
            # Verify the call was made with standard=True
            args, kwargs = mock_stitched.call_args
            standard_value = args[3]  # standard is 4th positional arg
            
            assert standard_value == True, "standard parameter should work correctly"
            
    def test_standard_false_works(self):
        """
        Test: 'standard=False' parameter works correctly.
        
        This ensures standard=False continues to work.
        """
        from unittest.mock import patch
        
        with patch('edgar.xbrl.statements.StitchedStatement') as mock_stitched:
            # Test standard=False
            self.statements.income_statement(standard=False)
            
            # Verify the call was made correctly
            args, kwargs = mock_stitched.call_args
            standard_value = args[3]  # standard is 4th positional arg
            
            assert standard_value == False, "standard=False parameter should work correctly"
            
    def test_parameter_defaults_regression(self):
        """
        Regression test: Parameter defaults must be maintained.
        
        This ensures default behavior doesn't change.
        """
        import inspect
        
        # Check parameter defaults for all methods
        statement_methods = [
            'income_statement',
            'balance_sheet', 
            'cashflow_statement',
            'statement_of_equity',
            'comprehensive_income'
        ]
        
        for method_name in statement_methods:
            method = getattr(self.statements, method_name)
            sig = inspect.signature(method)
            
            # Verify defaults
            assert sig.parameters['standard'].default == True, \
                f"{method_name}: standard default should be True"


def test_issue_403_does_not_regress():
    """
    Meta regression test: Ensure the original issue does not regress.
    
    This test simulates the original user's problem and ensures it stays fixed.
    """
    # Create a mock scenario like the original issue
    mock_xbrls = MagicMock(spec=XBRLS)
    statements = mock_xbrls.statements = StitchedStatements(mock_xbrls)
    
    # The original issue: This should not raise TypeError
    try:
        stmt = statements.income_statement(standard=True)
        # Test passes if no exception is raised
    except TypeError as e:
        if "unexpected keyword argument 'standard'" in str(e):
            pytest.fail(f"Issue #403 has regressed: {e}")
        # Re-raise other TypeErrors that might be legitimate
        raise


if __name__ == "__main__":
    print("Running regression tests for issue #403...")
    pytest.main([__file__, "-v"])