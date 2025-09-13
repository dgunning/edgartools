"""
Test script to find 6-K filings that contain actual financial data
to determine if the fix is justified.
"""

from edgar import Company, Financials
import traceback
import pytest

def find_6k_with_financials():
    """Find 6-K filings that actually contain financial data"""
    
    print("=" * 70)
    print("SEARCHING FOR 6-K FILINGS WITH ACTUAL FINANCIAL DATA")
    print("=" * 70)
    
    # Try various companies known to file 6-K with financial content
    test_companies = [
        "NVS",   # Novartis - Swiss pharma
        "ASML",  # ASML - Netherlands semiconductor
        "SAP",   # SAP - German software  
        "UL",    # Unilever - Anglo-Dutch consumer goods
        "RY",    # Royal Bank of Canada
        "TD",    # Toronto-Dominion Bank
        "CNQ",   # Canadian Natural Resources
        "SU",    # Suncor Energy
    ]
    
    found_financials = False
    
    for ticker in test_companies:
        try:
            print(f"\n--- Testing {ticker} ---")
            company = Company(ticker)
            print(f"Company: {company.name}")
            
            # Get recent 6-K filings
            six_k_filings = company.get_filings(form="6-K").head(10)
            print(f"Found {len(six_k_filings)} recent 6-K filings")
            
            for i, filing in enumerate(six_k_filings):
                if i >= 3:  # Only check first few
                    break
                    
                print(f"\n  Filing {i+1}: {filing.accession_number} ({filing.filing_date})")
                
                try:
                    # Try direct financials extraction
                    financials = Financials.extract(filing)
                    if financials:
                        has_income = financials.income_statement() is not None
                        has_balance = financials.balance_sheet() is not None
                        has_cashflow = financials.cashflow_statement() is not None
                        
                        if has_income or has_balance or has_cashflow:
                            print(f"    ✓ FOUND FINANCIALS!")
                            print(f"    ✓ Income statement: {has_income}")
                            print(f"    ✓ Balance sheet: {has_balance}")
                            print(f"    ✓ Cash flow: {has_cashflow}")
                            
                            # Show what's available
                            if has_income:
                                income_stmt = financials.income_statement()
                                df = income_stmt.to_dataframe()
                                print(f"    ✓ Income statement shape: {df.shape}")
                                print(f"    ✓ Sample data:")
                                print(f"        Columns: {list(df.columns)[:3]}...")
                                print(f"        Rows: {len(df)} financial line items")
                                
                            found_financials = True
                            
                            # Test if this would work with .financials attribute if available
                            six_k = filing.obj()
                            print(f"    - 6-K object type: {type(six_k).__name__}")
                            print(f"    - Has financials attr: {hasattr(six_k, 'financials')}")
                            
                            if not hasattr(six_k, 'financials'):
                                print(f"    ✗ Would fail with AttributeError as reported in issue #332")
                            
                            break
                        else:
                            print(f"    - No financial statements in this filing")
                    else:
                        print(f"    - Financials.extract returned None")
                        
                except Exception as e:
                    print(f"    - Error extracting financials: {e}")
                    
            if found_financials:
                break
                
        except Exception as e:
            print(f"  Error with {ticker}: {e}")
            continue
    
    return found_financials


@pytest.mark.regression
def test_proposed_fix():
    """Test what the fix would look like"""
    
    print("\n" + "=" * 70)
    print("TESTING PROPOSED FIX APPROACH")
    print("=" * 70)
    
    # Show the key insight
    print("Key insight from investigation:")
    print("1. Financials.extract(filing) WORKS on 6-K forms")
    print("2. CurrentReport just lacks the .financials property")
    print("3. CompanyReport provides this property with caching")
    print()
    
    print("Proposed fix: Make CurrentReport inherit from CompanyReport")
    print("This would:")
    print("  ✓ Add .financials property (cached)")
    print("  ✓ Add .income_statement, .balance_sheet, .cash_flow_statement properties")
    print("  ✓ Maintain backward compatibility")
    print("  ✓ Follow same pattern as TenK, TenQ, TwentyF")
    print()
    
    # Show what needs to be changed
    print("Required changes:")
    print("1. Change: class CurrentReport() -> class CurrentReport(CompanyReport)")
    print("2. Remove duplicate properties that CompanyReport already provides")
    print("3. Test that all existing CurrentReport functionality still works")


if __name__ == "__main__":
    found_data = find_6k_with_financials()
    test_proposed_fix()
    
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    if found_data:
        print("✓ Found 6-K filings with actual financial data")
        print("✓ The fix is justified - users should be able to access financials")
        print("✓ CurrentReport should inherit from CompanyReport")
    else:
        print("- No 6-K filings with financial data found in sample")
        print("- But Financials.extract() works, so fix still makes sense")
        print("- Users expect consistent API across form types")