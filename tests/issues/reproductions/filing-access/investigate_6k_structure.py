"""
Investigation script to understand 6-K filing structure and determine if they should support financials
"""

from edgar import Company, Financials
import traceback


def investigate_6k_financials():
    """Investigate if 6-K forms contain financial data that could be extracted"""
    
    print("=" * 70)
    print("INVESTIGATING 6-K FILING STRUCTURE FOR FINANCIAL DATA")
    print("=" * 70)
    
    try:
        # Test with Taiwan Semiconductor (TSM) - known to file 6-K
        company = Company("TSM")
        print(f"Company: {company.name}")
        
        # Get recent 6-K filings
        six_k_filings = company.get_filings(form="6-K").head(5)
        print(f"Found {len(six_k_filings)} recent 6-K filings")
        
        for i, filing in enumerate(six_k_filings):
            print(f"\n--- 6-K Filing #{i+1} ---")
            print(f"Accession: {filing.accession_number}")
            print(f"Filed: {filing.filing_date}")
            
            # Get the filing object
            six_k = filing.obj()
            
            # Check what items are available
            print(f"Available items: {six_k.items}")
            
            # Check if it has exhibits
            print(f"Number of exhibits: {len(filing.exhibits) if hasattr(filing, 'exhibits') else 'N/A'}")
            
            # Try direct financials extraction
            print(f"\nTesting direct Financials.extract()...")
            try:
                financials = Financials.extract(filing)
                if financials:
                    print(f"  ✓ Financials extracted successfully: {type(financials)}")
                    print(f"  ✓ Has income statement: {financials.income_statement() is not None}")
                    print(f"  ✓ Has balance sheet: {financials.balance_sheet() is not None}")
                    print(f"  ✓ Has cash flow: {financials.cashflow_statement() is not None}")
                    
                    if financials.income_statement():
                        print(f"  ✓ Income statement preview:")
                        income_stmt = financials.income_statement()
                        print(f"    Shape: {income_stmt.to_dataframe().shape if hasattr(income_stmt, 'to_dataframe') else 'N/A'}")
                else:
                    print(f"  - No financials available")
            except Exception as e:
                print(f"  ✗ Financials extraction failed: {e}")
            
            # Check for XBRL data  
            print(f"\nTesting XBRL data...")
            try:
                xbrl = filing.xbrl()
                if xbrl:
                    print(f"  ✓ XBRL data available")
                    statements = xbrl.statements if hasattr(xbrl, 'statements') else None
                    if statements:
                        print(f"  ✓ XBRL statements available")
                        print(f"  ✓ Income statement: {statements.income_statement() is not None}")
                        print(f"  ✓ Balance sheet: {statements.balance_sheet() is not None}")
                        print(f"  ✓ Cash flow: {statements.cashflow_statement() is not None}")
                else:
                    print(f"  - No XBRL data")
            except Exception as e:
                print(f"  - XBRL extraction failed: {e}")
            
            # Only check first few for detailed analysis
            if i >= 2:
                break
                
    except Exception as e:
        print(f"Error in investigation: {e}")
        traceback.print_exc()


def compare_forms_architecture():
    """Compare the architecture of different form types"""
    
    print("\n" + "=" * 70)
    print("COMPARING FORM ARCHITECTURES")
    print("=" * 70)
    
    try:
        company = Company("AAPL")
        
        # Test different form types
        forms_to_test = [
            ("10-K", "TenK"),
            ("10-Q", "TenQ"), 
            ("8-K", "CurrentReport"),
        ]
        
        for form, expected_class in forms_to_test:
            try:
                filings = company.get_filings(form=form).head(1)
                if len(filings) > 0:
                    filing = filings.latest()
                    obj = filing.obj()
                    
                    print(f"\n{form} Filing:")
                    print(f"  Class: {type(obj).__name__}")
                    print(f"  Expected: {expected_class}")
                    print(f"  Has financials attribute: {hasattr(obj, 'financials')}")
                    print(f"  Inherits from CompanyReport: {'CompanyReport' in [c.__name__ for c in type(obj).__mro__]}")
                    print(f"  MRO: {[c.__name__ for c in type(obj).__mro__]}")
                    
                    # Check if financials work
                    if hasattr(obj, 'financials'):
                        try:
                            financials = obj.financials
                            print(f"  Financials work: {financials is not None}")
                        except Exception as e:
                            print(f"  Financials error: {e}")
                            
            except Exception as e:
                print(f"  Error testing {form}: {e}")
        
        # Test 6-K specifically
        print(f"\n6-K Filing (using TSM):")
        tsm = Company("TSM")
        six_k_filings = tsm.get_filings(form="6-K").head(1)
        if len(six_k_filings) > 0:
            filing = six_k_filings.latest()
            obj = filing.obj()
            
            print(f"  Class: {type(obj).__name__}")
            print(f"  Has financials attribute: {hasattr(obj, 'financials')}")
            print(f"  Inherits from CompanyReport: {'CompanyReport' in [c.__name__ for c in type(obj).__mro__]}")
            print(f"  MRO: {[c.__name__ for c in type(obj).__mro__]}")
            
    except Exception as e:
        print(f"Error in architecture comparison: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    investigate_6k_financials()
    compare_forms_architecture()
    
    print("\n" + "=" * 70)
    print("CONCLUSIONS")
    print("=" * 70)
    print("Based on this investigation:")
    print("1. Check if 6-K forms contain extractable financial data")
    print("2. Understand why CurrentReport was designed differently")
    print("3. Determine the best approach to fix the issue")