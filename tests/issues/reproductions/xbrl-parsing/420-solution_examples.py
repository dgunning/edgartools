#!/usr/bin/env python3
"""
Solution examples for GitHub issue #420:
"Why can't get the latest continuous five year income statement?"

This script demonstrates the correct ways to get multi-year income statements.
"""

from edgar import Company


def solution_1_simple():
    """
    Solution 1: Use Company.income_statement() - SIMPLEST APPROACH
    
    This is the easiest and most direct way to get multi-year income statements.
    It uses the Company Facts API which aggregates data across multiple filings.
    """
    print("=== Solution 1: Company.income_statement() ===")
    print("This is the SIMPLEST approach - recommended for most users")
    print()
    
    company = Company("AAPL")
    
    # Get 5 years of annual income statement data
    income = company.income_statement(periods=5, annual=True)
    
    if income:
        print("✓ Successfully retrieved 5-year income statement:")
        print(income)
        print(f"\nData type: {type(income)}")
        print(f"Available periods: {income.periods if hasattr(income, 'periods') else 'Unknown'}")
    else:
        print("✗ No income statement data available")
    
    print("\nCode used:")
    print("```python")
    print("from edgar import Company")
    print("company = Company('AAPL')")
    print("income = company.income_statement(periods=5, annual=True)")
    print("print(income)")
    print("```")
    return income


def solution_2_xbrl_from_single_filing():
    """
    Solution 2: Get maximum periods from a single XBRL filing
    
    This approach gets data from a single 10-K filing, which typically contains 
    3 years of comparative data (current + 2 prior years).
    """
    print("\n=== Solution 2: Single XBRL Filing (3 years max) ===")
    print("This gets data from one 10-K filing (usually 3 years of data)")
    print()
    
    company = Company("AAPL")
    
    # Get the latest 10-K filing
    filing = company.get_filings(form="10-K").latest()
    
    if filing:
        print(f"Using filing: {filing.accession_number} from {filing.filing_date}")
        
        # Get XBRL data from the filing
        xbrl = filing.xbrl()
        
        if xbrl:
            # Get the income statement
            statements = xbrl.statements
            income_statement = statements.income_statement()
            
            if income_statement:
                print("✓ Successfully retrieved income statement from XBRL:")
                print(income_statement)
            else:
                print("✗ No income statement found in XBRL")
        else:
            print("✗ No XBRL data available in filing")
    else:
        print("✗ No 10-K filing found")
    
    print("\nCode used:")
    print("```python")
    print("from edgar import Company")
    print("company = Company('AAPL')")
    print("filing = company.get_filings(form='10-K').latest()")
    print("xbrl = filing.xbrl()")
    print("statements = xbrl.statements")
    print("income_statement = statements.income_statement()")
    print("print(income_statement)")
    print("```")


def solution_3_facts_api_detailed():
    """
    Solution 3: Using Facts API with detailed parameters
    
    This shows all the available parameters for customizing the output.
    """
    print("\n=== Solution 3: Facts API with Custom Parameters ===")
    print("This shows how to customize the output format and periods")
    print()
    
    company = Company("AAPL")
    
    # Example 1: Get as DataFrame for further analysis
    print("Example 3a: Get as pandas DataFrame")
    income_df = company.income_statement(periods=5, annual=True, as_dataframe=True)
    if income_df is not None:
        print("✓ Successfully retrieved as DataFrame:")
        print(f"   Shape: {income_df.shape}")
        print(f"   Columns: {list(income_df.columns)}")
        print("   First few rows:")
        print(income_df.head())
    else:
        print("✗ No data available as DataFrame")
    
    print("\nCode used:")
    print("```python")
    print("income_df = company.income_statement(periods=5, annual=True, as_dataframe=True)")
    print("print(income_df)")
    print("```")
    
    # Example 2: Get quarterly data instead of annual
    print("\n\nExample 3b: Get quarterly data (last 5 quarters)")
    quarterly_income = company.income_statement(periods=5, annual=False)
    if quarterly_income:
        print("✓ Successfully retrieved quarterly income statement:")
        print(quarterly_income)
    else:
        print("✗ No quarterly income statement data available")
    
    print("\nCode used:")
    print("```python")
    print("quarterly_income = company.income_statement(periods=5, annual=False)")
    print("print(quarterly_income)")
    print("```")


def solution_4_working_with_multiple_filings():
    """
    Solution 4: Understanding how to work with multiple filings
    
    This explains why the user's approach failed and shows the correct way 
    to work with multiple filings if needed.
    """
    print("\n=== Solution 4: Working with Multiple Filings ===")
    print("Understanding the difference between single filings and filing collections")
    print()
    
    company = Company("AAPL")
    
    # Show what the user was trying to do
    print("What the user tried (and why it failed):")
    filings = company.get_filings(form="10-K").latest(5)
    print(f"latest(5) returns: {type(filings)} with {len(filings)} filings")
    print("This is a COLLECTION of filings, not a single filing")
    print("Collections don't have .xbrl() method - only individual filings do")
    
    print("\nCorrect way to process multiple filings:")
    for i, filing in enumerate(filings):
        print(f"\nFiling {i+1}: {filing.accession_number} ({filing.filing_date})")
        try:
            xbrl = filing.xbrl()  # This works on individual filings
            if xbrl and xbrl.statements:
                stmt = xbrl.statements.income_statement()
                if stmt:
                    print(f"   ✓ Has income statement data")
                else:
                    print(f"   ✗ No income statement in this filing")
            else:
                print(f"   ✗ No XBRL data in this filing")
        except Exception as e:
            print(f"   ✗ Error processing filing: {e}")
    
    print("\nCode used:")
    print("```python")
    print("filings = company.get_filings(form='10-K').latest(5)")
    print("for filing in filings:")
    print("    xbrl = filing.xbrl()  # This works on individual filings")
    print("    if xbrl:")
    print("        stmt = xbrl.statements.income_statement()")
    print("        if stmt:")
    print("            print(stmt)")
    print("```")


def main():
    """Run all solution examples."""
    print("GitHub Issue #420 - Solution Examples")
    print("=====================================")
    print("How to get 5-year income statements in EdgarTools")
    print()
    
    try:
        # Run all solutions
        income = solution_1_simple()
        solution_2_xbrl_from_single_filing()
        solution_3_facts_api_detailed()
        solution_4_working_with_multiple_filings()
        
        print("\n" + "="*60)
        print("SUMMARY - Recommended approaches:")
        print("="*60)
        print()
        print("1. BEST FOR MOST USERS:")
        print("   company.income_statement(periods=5)")
        print()
        print("2. FOR SINGLE FILING (3 years max):")
        print("   filing = company.get_filings(form='10-K').latest()")
        print("   filing.xbrl().statements.income_statement()")
        print()
        print("3. FOR DATAFRAME OUTPUT:")
        print("   company.income_statement(periods=5, as_dataframe=True)")
        print()
        print("4. FOR QUARTERLY DATA:")
        print("   company.income_statement(periods=5, annual=False)")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()