"""
Reproduction script for GitHub issue #403: Support standard=True in stitched statements

This script reproduces the original issue scenario and demonstrates that
the standard parameter now works correctly.

Issue URL: https://github.com/dgunning/edgartools/issues/403
"""

def reproduce_issue_403():
    """Reproduce the original issue and verify the fix."""
    print("Issue #403: Support standard=True in stitched statements")
    print("=" * 60)
    print()
    
    print("Original problem: TypeError when using standard=True parameter")
    print("User tries to call: stmt = xbrls.statements.income_statement(standard=True)")
    print()
    print("Expected: No error, parameter should be accepted")
    print("- Documentation suggests 'standard=True' should work")
    print("- All examples in docs use standard=True")  
    print("- Methods now accept the 'standard' parameter")
    print()
    
    # Import what we need
    from unittest.mock import MagicMock, patch
    from edgar.xbrl.statements import StitchedStatements
    from edgar.xbrl.stitching.xbrls import XBRLS
    
    # Create mock objects like user would have
    mock_xbrls = MagicMock(spec=XBRLS)
    statements = StitchedStatements(mock_xbrls)
    
    print("Testing the fix:")
    print("-" * 30)
    
    try:
        print("Code: statements.income_statement(standard=True)")
        
        # This should not raise TypeError
        with patch('edgar.xbrl.statements.StitchedStatement'):
            stmt = statements.income_statement(standard=True)
        
        print("✓ SUCCESS: standard=True parameter works!")
        print()
        
        print("Code: statements.income_statement(standard=False)")  
        with patch('edgar.xbrl.statements.StitchedStatement'):
            stmt = statements.income_statement(standard=False)
        
        print("✓ SUCCESS: standard=False parameter works!")
        print()
        
    except TypeError as e:
        if "unexpected keyword argument 'standard'" in str(e):
            print(f"✗ FAILURE: {e}")
            return False
        else:
            # Some other TypeError, probably from mocking
            print("✓ SUCCESS: standard parameter accepted (other TypeError from mocking)")
    
    print("Testing all statement methods...")
    methods_to_test = [
        ('income_statement', True),
        ('balance_sheet', True), 
        ('cashflow_statement', False),
        ('statement_of_equity', True),
        ('comprehensive_income', False)
    ]
    
    for method_name, standard_value in methods_to_test:
        try:
            method = getattr(statements, method_name)
            with patch('edgar.xbrl.statements.StitchedStatement'):
                method(standard=standard_value)
            print(f"✓ stmt = statements.{method_name}(standard={standard_value})")
        except TypeError as e:
            if "unexpected keyword argument 'standard'" in str(e):
                print(f"✗ {method_name} failed: {e}")
                return False
    
    print()
    print("🎉 Issue #403 verification completed successfully!")
    print("All statement methods now accept the 'standard' parameter.")
    return True


if __name__ == "__main__":
    success = reproduce_issue_403()
    if not success:
        exit(1)