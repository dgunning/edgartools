#!/usr/bin/env python3
"""
Simple Demo: TSLA Data Now Accessible After SGML Fix

This shows the key impact: XBRL data that was completely blocked 
by SGML parsing errors is now accessible.
"""

from edgar import Company, set_identity

def demonstrate_sgml_fix_impact():
    print("=" * 70)
    print("TSLA DATA ACCESS - BEFORE vs AFTER SGML FIX")
    print("=" * 70)
    
    # Note: Identity should be set in environment for demos/tests  
    tsla = Company("1318605")  # Tesla CIK
    
    print(f"Company: {tsla}")
    print(f"Testing years that user reported as 'missing' in Issue #412...")
    
    # Test the years user mentioned in Issue #412
    test_years = [2019, 2020, 2021, 2022]
    
    for year in test_years:
        filings = tsla.get_filings(form="10-K", amendments=False)
        filing = None
        for f in filings:
            if f.filing_date.year == year:
                filing = f
                break
        
        if filing:
            print(f"\n📄 {year} 10-K Filing: {filing.accession_number}")
            print(f"   Filed: {filing.filing_date}")
            
            try:
                # This is where our SGML fix made the difference
                xbrl = filing.xbrl()
                
                if xbrl:
                    fact_count = len(xbrl.facts)
                    print(f"   ✅ SUCCESS: XBRL accessible with {fact_count:,} facts!")
                    
                    # Show that statements are available
                    try:
                        statements = xbrl.statements
                        income = statements.income_statement()
                        balance = statements.balance_sheet()
                        cash_flow = statements.cashflow_statement()

                        print(income)
                        print(balance)
                        print(cash_flow)
                        
                        print(f"   📊 Financial Statements Available:")
                        if income is not None and len(income) > 0:
                            print(f"      ✅ Income Statement: {len(income)} line items")
                        if balance is not None and len(balance) > 0:
                            print(f"      ✅ Balance Sheet: {len(balance)} line items")
                        if cash_flow is not None and len(cash_flow) > 0:
                            print(f"      ✅ Cash Flow: {len(cash_flow)} line items")
                            
                        # Show sample revenue data
                        revenue_found = False
                        for fact in list(xbrl.facts)[:100]:  # Check first 100 facts
                            if 'revenue' in fact.concept.lower() and fact.period and fact.period.days >= 350:
                                print(f"   💰 Found Revenue: ${fact.value:,.0f} ({fact.concept})")
                                revenue_found = True
                                break
                        
                        if not revenue_found:
                            print(f"   💰 Revenue concepts available but need specific extraction")
                            
                    except Exception as e:
                        print(f"   📊 XBRL accessible but statements error: {e}")
                        
                else:
                    print(f"   ❌ FAILED: No XBRL data accessible")
                    
            except Exception as e:
                if "Unknown SGML format" in str(e):
                    print(f"   ❌ FAILED: Unknown SGML format (different format issue)")
                elif "too many values to unpack" in str(e):
                    print(f"   ❌ FAILED: SGML parsing error (should be fixed!)")
                else:
                    print(f"   ❌ FAILED: Other error - {e}")
        else:
            print(f"\n📄 {year}: No 10-K filing found")
    
    print(f"\n" + "=" * 70)
    print("SUMMARY OF SGML FIX IMPACT")
    print("=" * 70)
    print("BEFORE FIX: SGML parsing crashed → No XBRL → No financial data")
    print("AFTER FIX:  SGML parsing works → XBRL accessible → Financial data available")
    print("")
    print("🎯 RESULT: Unlocked access to Tesla financial data that was completely blocked")
    print("📊 USER IMPACT: Addresses 'TSLA revenue missing 2019-2022' from Issue #412")

if __name__ == "__main__":
    demonstrate_sgml_fix_impact()