"""
Reproduction script for GitHub issue #434
Issue: S-4 filing not extracting target company (Kodiak Robotics) financials

The user reports that when extracting financial data from an S-4 filing,
only one company's data (Ares Acquisition Corp) is returned, not the target
company's data (Kodiak Robotics).

Filing URL: https://www.sec.gov/Archives/edgar/data/1747286/000119312525119920/
HTML Filing: https://www.sec.gov/Archives/edgar/data/1747286/000119312525119920/d948047ds4.htm
"""

from edgar import Company, set_identity
import sys
import traceback


def reproduce_issue_434():
    """Reproduce the S-4 financial extraction issue."""
    
    print("=== Issue #434 Reproduction: S-4 Financial Extraction ===")
    print("Testing extraction of financials from S-4 filing...")
    print("Expected: Should extract both Ares Acquisition Corp AND Kodiak Robotics financials")
    print("Observed: Only Ares Acquisition Corp financials are extracted")
    print()
    
    try:
        
        # Get company and filings
        company = Company("0001747286")  # Ares Acquisition Corp IV
        print(f"Company: {company.name} (CIK: {company.cik})")
        
        filings = company.get_filings(form="S-4", amendments=False)
        print(f"Found {len(filings)} S-4 filings")
        
        for i, filing in enumerate(filings):
            print(f"\n--- Filing {i+1}: {filing} ---")
            print(f"Primary document: {filing.primary_document}")
            print(f"Is XBRL: {filing.is_xbrl}")
            print(f"Is inline XBRL: {filing.is_inline_xbrl}")
            
            if not filing.is_xbrl:
                print("Filing is not XBRL - skipping XBRL analysis")
                continue
            
            # Get XBRL data
            print("\nExtracting XBRL data...")
            xbrl = filing.xbrl()
            
            # Analyze entities in the filing
            print("\n=== Analyzing Entities ===")
            if hasattr(xbrl, 'entity') and xbrl.entity:
                print(f"Primary entity: {xbrl.entity}")
            
            # Check for multiple entities in facts
            if hasattr(xbrl, 'facts') and xbrl.facts:
                entities = set()
                facts_list = xbrl.facts.get_facts()[:100]  # Sample first 100 facts
                for fact in facts_list:
                    if 'entity_identifier' in fact:
                        entities.add(fact['entity_identifier'])
                    elif 'entity_scheme' in fact:
                        entities.add(fact['entity_scheme'])
                
                print(f"Entities found in facts: {entities}")
            
            # Try to get statements
            statements = xbrl.statements
            print(f"\n=== Available Statements ===")
            print(f"Statements object: {statements}")
            
            # Check if we can get income statement
            try:
                income_statement = statements.income_statement()
                if income_statement:
                    print("\n=== Income Statement Analysis ===")
                    print(f"Income statement: {income_statement}")
                    
                    # Convert to dataframe and analyze
                    df = income_statement.to_dataframe()
                    print(f"Dataframe shape: {df.shape}")
                    print(f"Columns: {list(df.columns)}")
                    
                    if not df.empty:
                        print("\n=== Sample Data ===")
                        print(df.head().to_string())
                        
                        # Check for any company name references in the data
                        print("\n=== Company Name Analysis ===")
                        for col in df.columns:
                            if isinstance(col, str):
                                if 'kodiak' in col.lower() or 'robotics' in col.lower():
                                    print(f"Found Kodiak/Robotics reference in column: {col}")
                                if 'ares' in col.lower() or 'acquisition' in col.lower():
                                    print(f"Found Ares/Acquisition reference in column: {col}")
                    else:
                        print("Dataframe is empty")
                else:
                    print("No income statement found")
            except Exception as e:
                print(f"Error extracting income statement: {e}")
                traceback.print_exc()
            
            # Check balance sheet
            try:
                balance_sheet = statements.balance_sheet()
                if balance_sheet:
                    print(f"\n=== Balance Sheet Available ===")
                    bs_df = balance_sheet.to_dataframe()
                    print(f"Balance sheet shape: {bs_df.shape}")
            except Exception as e:
                print(f"Error extracting balance sheet: {e}")
            
            # Check cash flow
            try:
                cash_flow = statements.cash_flow_statement()
                if cash_flow:
                    print(f"\n=== Cash Flow Statement Available ===")
                    cf_df = cash_flow.to_dataframe()
                    print(f"Cash flow shape: {cf_df.shape}")
            except Exception as e:
                print(f"Error extracting cash flow: {e}")
            
            print("\n" + "="*60)
            
    except Exception as e:
        print(f"Error during reproduction: {e}")
        traceback.print_exc()
        return False
    
    return True


def analyze_filing_structure():
    """Analyze the structure of the S-4 filing to understand entity handling."""
    
    print("\n=== Detailed Filing Structure Analysis ===")
    
    try:
        company = Company("0001747286")
        filings = company.get_filings(form="S-4", amendments=False)
        
        if not filings:
            print("No S-4 filings found")
            return
            
        filing = filings[0]  # Get the first S-4 filing
        print(f"Analyzing filing: {filing}")
        
        if not filing.is_xbrl:
            print("Filing is not XBRL")
            return
            
        xbrl = filing.xbrl()
        
        # Deep dive into XBRL structure
        print("\n=== XBRL Deep Analysis ===")
        
        # Check contexts
        if hasattr(xbrl, 'contexts'):
            print(f"Contexts available: {len(xbrl.contexts) if xbrl.contexts else 0}")
            if xbrl.contexts:
                for i, context in enumerate(list(xbrl.contexts)[:5]):  # First 5 contexts
                    print(f"Context {i+1}: {context}")
        
        # Check units
        if hasattr(xbrl, 'units'):
            print(f"Units available: {len(xbrl.units) if xbrl.units else 0}")
        
        # Check facts in detail
        if hasattr(xbrl, 'facts') and xbrl.facts:
            print(f"Total facts: {len(xbrl.facts)}")
            
            # Sample facts to understand structure
            sample_facts = xbrl.facts.get_facts()[:20]
            print("\n=== Sample Facts Analysis ===")
            for i, fact in enumerate(sample_facts):
                print(f"Fact {i+1}:")
                print(f"  Concept: {fact.get('concept', 'N/A')}")
                print(f"  Value: {fact.get('value', 'N/A')}")
                print(f"  Entity ID: {fact.get('entity_identifier', 'N/A')}")
                print(f"  Period Type: {fact.get('period_type', 'N/A')}")
                print(f"  Period Start: {fact.get('period_start', 'N/A')}")
                print(f"  Period End: {fact.get('period_end', 'N/A')}")
                print()
                
    except Exception as e:
        print(f"Error during structure analysis: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting Issue #434 Reproduction")
    print("="*50)
    
    # Run basic reproduction
    success = reproduce_issue_434()
    
    # Run detailed analysis
    analyze_filing_structure()
    
    print("\n" + "="*50)
    print("Reproduction completed")
    
    if not success:
        sys.exit(1)