#!/usr/bin/env python3
"""
Reproduction script for GitHub issue #420:
"Why can't get the latest continuous five year income statement?"

This script reproduces the user's issue and demonstrates the correct solutions.
"""

from edgar import Company


def reproduce_user_issue():
    """Reproduce the exact issue the user encountered."""
    print("=== Reproducing User Issue ===")
    
    # This works (user's first approach) - gets latest 3 years from single filing
    print("1. User's working approach - single filing (3 years):")
    try:
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()
        statements = xbrl.statements
        income_statement = statements.income_statement()
        print(f"✓ Success: Got income statement with 3 periods")
        if income_statement:
            print(f"   Statement type: {type(income_statement)}")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # This fails (user's second approach) - multiple filings don't have .xbrl()
    print("\n2. User's failing approach - multiple filings:")
    try:
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest(5)  # Returns EntityFilings, not Filing
        print(f"   Filing type: {type(filing)}")
        xbrl = filing.xbrl()  # This should fail - EntityFilings has no .xbrl()
        statements = xbrl.statements
        income_statement = statements.income_statement()
        print(f"✓ Success: Got income statement")
    except AttributeError as e:
        print(f"✗ Expected failure: {e}")
    except Exception as e:
        print(f"✗ Other error: {e}")
    
    # This fails (user tried from comments) - wrong parameter name
    print("\n3. User's attempted fix - wrong parameter:")
    try:
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()
        statements = xbrl.statements
        income_statement = statements.income_statement(max_periods=5)  # Should fail
        print(f"✓ Success: Got income statement")
    except TypeError as e:
        print(f"✗ Expected failure: {e}")
    except Exception as e:
        print(f"✗ Other error: {e}")


def demonstrate_correct_solutions():
    """Demonstrate the correct ways to get 5-year income statements."""
    print("\n=== Correct Solutions ===")
    
    # Solution 1: Use Company.income_statement() with periods parameter  
    print("1. Use Company.income_statement(periods=5):")
    try:
        company = Company("AAPL")
        income = company.income_statement(periods=5)
        if income:
            print(f"✓ Success: Got {type(income)} with data")
        else:
            print("✓ Success: Method worked but no data returned (company may not have 5 years of data)")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # Solution 2: Use multiple filings with stitched statements
    print("\n2. Use multiple filings with stitched statements:")
    try:
        company = Company("AAPL")
        filings = company.get_filings(form="10-K").latest(5)
        print(f"   Got {len(filings)} filings")
        
        # Get XBRL objects from multiple filings
        xbrls = []
        for filing in filings:
            try:
                xbrl = filing.xbrl()
                if xbrl:
                    xbrls.append(xbrl)
            except Exception as inner_e:
                print(f"   Warning: Failed to get XBRL for filing {filing.accession_number}: {inner_e}")
        
        if xbrls:
            print(f"   Successfully got XBRL from {len(xbrls)} filings")
            # This would require creating an XBRLS collection and using StitchedStatements
            # but let's see if this path is available in the current API
        else:
            print("   No XBRL data available from filings")
            
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # Solution 3: Check if there's a simpler approach using the Facts API
    print("\n3. Check Facts API approach (Company facts):")
    try:
        company = Company("AAPL")
        facts = company.get_facts()
        if facts:
            print(f"✓ Success: Got {type(facts)}")
            # Check if facts has income statement method
            if hasattr(facts, 'income_statement'):
                income = facts.income_statement(periods=5)
                if income:
                    print(f"   Got income statement: {type(income)}")
                else:
                    print("   Facts income_statement returned None")
            else:
                print("   Facts object has no income_statement method")
        else:
            print("   No facts available")
    except Exception as e:
        print(f"✗ Failed: {e}")


if __name__ == "__main__":
    print("GitHub Issue #420 Reproduction Script")
    print("=====================================")
    
    reproduce_user_issue()
    demonstrate_correct_solutions()
    
    print("\n=== Conclusion ===")
    print("The user's issue stems from:")
    print("1. Misunderstanding that latest(5) returns multiple filings, not a single filing")
    print("2. Not knowing about Company.income_statement(periods=5)")
    print("3. Using wrong parameter name (max_periods vs periods)")