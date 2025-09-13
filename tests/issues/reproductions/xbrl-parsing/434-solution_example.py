"""
Issue #434 Solution: How to properly extract financial data for both companies 
involved in an S-4 business combination filing.

This script demonstrates:
1. How S-4 XBRL works (registrant data only)  
2. How to get target company financial data from their separate filings
3. How to examine S-4 exhibits for target company information
"""

from edgar import Company, set_identity
import sys


def demonstrate_s4_data_access():
    """Demonstrate the correct way to access financial data for S-4 business combinations."""
    
    print("=== S-4 Filing Financial Data Access Guide ===")
    print("Issue #434: Understanding S-4 filing structure\n")
    
    try:
        
        print("1. S-4 Filing XBRL Data (Registrant Only)")
        print("=" * 50)
        
        # Get the S-4 filing (filed under Kodiak's CIK but contains Ares data)
        kodiak_cik_company = Company("0001747286")  # This is Kodiak's CIK
        s4_filings = kodiak_cik_company.get_filings(form="S-4", amendments=False)
        
        if s4_filings:
            s4_filing = s4_filings[0]
            print(f"S-4 Filing: {s4_filing}")
            print(f"Filing Company: {s4_filing.company}")
            
            if s4_filing.is_xbrl:
                xbrl = s4_filing.xbrl()
                print(f"XBRL Entity: {xbrl.entity_name}")
                
                # Get entity from facts
                facts = xbrl.facts.get_facts()
                if facts:
                    entity_id = facts[0].get('entity_identifier', 'Unknown')
                    print(f"Entity CIK: {entity_id}")
                
                # This will show Ares Acquisition Corp's financial statements
                statements = xbrl.statements
                income_statement = statements.income_statement()
                
                print("\nS-4 XBRL Income Statement (Registrant: Ares Acquisition Corp):")
                print(income_statement)
                
                print("\nNote: This shows Ares Acquisition Corp's financials, not Kodiak's.")
                print("This is expected behavior for S-4 filings.")
        
        print(f"\n2. Target Company Financial Data (Separate Filings)")
        print("=" * 50)
        
        # To get Kodiak Robotics' actual financial data, look for their separate filings
        print("To get Kodiak Robotics' financial statements, access their own filings:")
        
        try:
            # Try to find Kodiak's separate filings
            kodiak_company = Company("Kodiak Robotics")
            print(f"Kodiak Robotics found: {kodiak_company.name} (CIK: {kodiak_company.cik})")
            
            # Get their most recent 10-K or 10-Q filings
            kodiak_filings = kodiak_company.get_filings(form=["10-K", "10-Q"], amendments=False)
            
            if kodiak_filings:
                print(f"Found {len(kodiak_filings)} Kodiak filings")
                
                # Show the most recent filing with financial data
                for filing in kodiak_filings[:3]:
                    print(f"\nKodiak Filing: {filing}")
                    if filing.is_xbrl:
                        try:
                            xbrl = filing.xbrl()
                            statements = xbrl.statements
                            income_statement = statements.income_statement()
                            
                            print("Kodiak Income Statement Sample:")
                            df = income_statement.to_dataframe()
                            print(df.head(3).to_string())
                            break
                        except:
                            print("Could not extract financial statements from this filing")
            else:
                print("No recent 10-K/10-Q filings found for Kodiak")
                
        except Exception as e:
            print(f"Could not find Kodiak Robotics as a separate company: {e}")
            print("This may indicate Kodiak is a private company without separate SEC filings")
        
        print(f"\n3. S-4 Exhibits (Target Company Narrative Data)")  
        print("=" * 50)
        
        # Show how to examine S-4 exhibits for Kodiak information
        print("S-4 exhibits may contain Kodiak financial data in narrative form:")
        
        attachments = s4_filing.attachments
        kodiak_exhibits = []
        
        for attachment in attachments:
            if attachment.document_type.startswith('EX-99'):
                # These are common exhibits for additional information
                kodiak_exhibits.append(attachment)
        
        print(f"Found {len(kodiak_exhibits)} EX-99 exhibits that may contain target company data")
        
        for exhibit in kodiak_exhibits[:3]:  # Show first 3
            print(f"  - {exhibit.document}: {exhibit.description}")
            
        print(f"\nTo examine exhibit content:")
        print("exhibit = s4_filing.attachments[n]")
        print("content = exhibit.content")
        print("# Search for financial data in HTML/text format")
        
        print(f"\n=== Key Takeaways ===")
        print("1. S-4 XBRL contains only the REGISTRANT's financial statements")
        print("2. For target company financials, check their separate SEC filings")
        print("3. Target company data in S-4 is typically in exhibits (HTML format)")
        print("4. EdgarTools is working correctly - this is expected S-4 behavior")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
        
    return True


if __name__ == "__main__":
    success = demonstrate_s4_data_access()
    if not success:
        sys.exit(1)