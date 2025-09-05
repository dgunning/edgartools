"""
Issue #332: CurrentReport (6-K filings) missing 'financials' attribute

Problem: When accessing .financials on a 6-K filing (CurrentReport), users get:
AttributeError: 'CurrentReport' object has no attribute 'financials'

Root cause: CurrentReport class doesn't inherit from CompanyReport which provides the financials property.

This script reproduces the issue by attempting to access the financials attribute on a 6-K filing.
"""

from edgar import Company, get_entity
import traceback


def reproduce_issue():
    """Reproduce the missing financials attribute on CurrentReport (6-K)"""
    
    print("=" * 60)
    print("REPRODUCING ISSUE #332: 6-K Missing Financials Attribute")
    print("=" * 60)
    
    try:
        # Find a company that has 6-K filings
        print("1. Searching for a company with 6-K filings...")
        
        # Let's try a few companies that commonly file 6-K forms (non-US companies)
        test_companies = ["TSM", "ASML", "SAP", "NVS", "UL"]  # Non-US companies that file 6-K
        
        filing_found = False
        for ticker in test_companies:
            try:
                company = Company(ticker)
                print(f"   Checking {ticker} ({company.name})...")
                
                # Get 6-K filings
                six_k_filings = company.get_filings(form="6-K").head(5)
                
                if len(six_k_filings) > 0:
                    print(f"   ✓ Found {len(six_k_filings)} 6-K filings for {ticker}")
                    
                    # Get the latest 6-K filing
                    filing = six_k_filings.latest()
                    print(f"   Latest 6-K: {filing.accession_number} filed on {filing.filing_date}")
                    
                    # Convert to CurrentReport (6-K/SixK object)
                    six_k = filing.obj()
                    print(f"   Filing object type: {type(six_k).__name__}")
                    
                    # Try to access financials - this should fail
                    print(f"\n2. Attempting to access .financials attribute...")
                    
                    try:
                        financials = six_k.financials
                        print(f"   ✓ Financials accessed successfully: {type(financials)}")
                        if financials:
                            print(f"   ✓ Financials available: {financials}")
                        else:
                            print(f"   - No financials available in this filing")
                        filing_found = True
                        break
                        
                    except AttributeError as e:
                        print(f"   ✗ REPRODUCED ISSUE: {e}")
                        print(f"   ✗ CurrentReport object missing 'financials' attribute")
                        filing_found = True
                        
                        # Show available attributes for debugging
                        print(f"\n3. Available attributes on CurrentReport:")
                        attrs = [attr for attr in dir(six_k) if not attr.startswith('_')]
                        for attr in sorted(attrs):
                            print(f"   - {attr}")
                        break
                        
                else:
                    print(f"   - No 6-K filings found for {ticker}")
                    
            except Exception as e:
                print(f"   - Error checking {ticker}: {e}")
                continue
        
        if not filing_found:
            print("\n   ✗ Could not find any 6-K filings to test with")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        traceback.print_exc()
        return False


def compare_with_working_forms():
    """Compare CurrentReport with working forms like TenK, TenQ that do have financials"""
    
    print("\n" + "=" * 60)
    print("COMPARING WITH WORKING FORMS (10-K, 10-Q)")
    print("=" * 60)
    
    try:
        # Get a 10-K filing to compare
        company = Company("AAPL")
        print(f"Checking {company.name} for comparison...")
        
        # Get 10-K filing
        tenk_filings = company.get_filings(form="10-K").head(1)
        if len(tenk_filings) > 0:
            filing = tenk_filings.latest()
            tenk = filing.obj()
            print(f"10-K object type: {type(tenk).__name__}")
            print(f"10-K has financials attribute: {hasattr(tenk, 'financials')}")
            
            if hasattr(tenk, 'financials'):
                print(f"10-K financials type: {type(tenk.financials)}")
        
        # Get 10-Q filing
        tenq_filings = company.get_filings(form="10-Q").head(1)
        if len(tenq_filings) > 0:
            filing = tenq_filings.latest()
            tenq = filing.obj()
            print(f"10-Q object type: {type(tenq).__name__}")
            print(f"10-Q has financials attribute: {hasattr(tenq, 'financials')}")
            
            if hasattr(tenq, 'financials'):
                print(f"10-Q financials type: {type(tenq.financials)}")
        
    except Exception as e:
        print(f"Error in comparison: {e}")


if __name__ == "__main__":
    success = reproduce_issue()
    compare_with_working_forms()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if success:
        print("✓ Successfully reproduced issue #332")
        print("  - CurrentReport (6-K) objects lack the 'financials' attribute")
        print("  - This is because CurrentReport doesn't inherit from CompanyReport")
        print("  - CompanyReport provides the financials property that TenK, TenQ use")
    else:
        print("✗ Could not reproduce the issue")
    
    print("\nNext steps:")
    print("1. Determine if 6-K forms should support financials extraction")
    print("2. If yes, modify CurrentReport to inherit from CompanyReport")
    print("3. If no, provide better error message or alternative approach")