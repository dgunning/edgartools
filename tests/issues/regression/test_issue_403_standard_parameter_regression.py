"""
Regression test for GitHub issue #403: Support standard=True in stitched statements

This test ensures that the 'standard' parameter support in stitched statements 
doesn't regress in future changes.

Issue URL: https://github.com/dgunning/edgartools/issues/403
"""

import inspect

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
            'cash_flow_statement',
            'statement_of_equity',
            'comprehensive_income'
        ]
        
        # Asserted against the SIGNATURE, not by calling and catching TypeError.
        #
        # The call-and-catch version ended in `except Exception: pass`, so any
        # failure that was not a TypeError -- including one raised by the
        # MagicMock standing in for XBRLS -- left the loop having proven
        # nothing, and the test reported green. The signature is the claim
        # anyway: "these methods accept a `standard` parameter" is a statement
        # about the interface, and nothing a mock does can mask it.
        for method_name in statement_methods:
            method = getattr(self.statements, method_name)
            params = inspect.signature(method).parameters
            assert 'standard' in params, (
                f"{method_name}() no longer accepts a 'standard' parameter; "
                f"its signature is ({', '.join(params)})"
            )
            assert params['standard'].kind is not inspect.Parameter.VAR_KEYWORD, (
                f"{method_name}() only absorbs 'standard' via **kwargs, which is "
                "not the same as supporting it"
            )
                
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
            'cash_flow_statement',
            'statement_of_equity',
            'comprehensive_income'
        ]
        
        for method_name in statement_methods:
            method = getattr(self.statements, method_name)
            sig = inspect.signature(method)

            # Verify defaults
            assert sig.parameters['standard'].default == True, \
                f"{method_name}: standard default should be True"

    # Ported here on 2026-08-10 from
    # tests/issues/reproductions/xbrl-parsing/test_issue_403_verification.py
    # (bead edgartools-07lk.24, Tier 2), which was listed for deletion as a
    # duplicate of this file and was not one. Everything above checks the other
    # four methods by INTROSPECTION only -- signature and default -- and the two
    # behavioural tests call income_statement alone. A method can carry a
    # correct `standard` parameter in its signature and still drop it on the
    # floor instead of forwarding it, which is issue #403 exactly, and for
    # balance_sheet, cash_flow_statement, statement_of_equity and
    # comprehensive_income nothing here would have caught that.
    @pytest.mark.parametrize("method_name", [
        'income_statement',
        'balance_sheet',
        'cash_flow_statement',
        'statement_of_equity',
        'comprehensive_income',
    ])
    @pytest.mark.parametrize("standard", [True, False])
    def test_standard_is_forwarded_by_every_method(self, method_name, standard):
        """Each statement method passes `standard` through to StitchedStatement."""
        from unittest.mock import patch

        with patch('edgar.xbrl.statements.StitchedStatement') as mock_stitched:
            getattr(self.statements, method_name)(standard=standard)

            mock_stitched.assert_called_once()
            args = mock_stitched.call_args[0]
            assert args[3] is standard, (
                f"{method_name}(standard={standard}) forwarded {args[3]!r} as the "
                "4th positional argument to StitchedStatement"
            )


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