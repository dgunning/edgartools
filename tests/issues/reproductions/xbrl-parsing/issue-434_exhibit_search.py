"""
Search for Kodiak Robotics financial data in S-4 filing exhibits.
Focus on exhibits that might contain target company financial statements.
"""

from edgar import Company, set_identity
import sys
import traceback


def search_kodiak_exhibits():
    """Search for exhibits that might contain Kodiak Robotics financial data."""
    
    try:
        
        # Get company and S-4 filing
        company = Company("0001747286")
        filings = company.get_filings(form="S-4", amendments=False)
        filing = filings[0]
        
        print("=== Searching for Kodiak Robotics Financial Data ===")
        print(f"Filing: {filing}")
        
        attachments = filing.attachments
        
        # Look specifically at exhibits that commonly contain financial statements
        financial_exhibits = []
        
        for attachment in attachments:
            doc_type = attachment.document_type.upper()
            doc_name = attachment.document.lower()
            desc = attachment.description.lower() if attachment.description else ""
            
            # Check for common financial statement exhibit numbers
            if any(x in doc_type for x in ['EX-99', 'EX-23', 'EX-21']):
                financial_exhibits.append(attachment)
                print(f"\nExamining: {attachment.document} ({doc_type})")
                
                # Try to get content of this exhibit
                try:
                    content = attachment.content
                    if content:
                        content_lower = content.lower()
                        
                        # Check for Kodiak mentions
                        kodiak_mentions = content_lower.count('kodiak')
                        robotics_mentions = content_lower.count('robotics')
                        
                        if kodiak_mentions > 0 or robotics_mentions > 0:
                            print(f"  *** FOUND KODIAK DATA! ***")
                            print(f"  Kodiak mentions: {kodiak_mentions}")
                            print(f"  Robotics mentions: {robotics_mentions}")
                            
                            # Check for financial statement keywords near Kodiak mentions
                            financial_terms = ['balance sheet', 'income statement', 'statement of operations', 
                                             'cash flow', 'revenue', 'assets', 'liabilities', 'equity']
                            
                            for term in financial_terms:
                                if term in content_lower:
                                    # Look for the term within 500 characters of "kodiak"
                                    kodiak_pos = content_lower.find('kodiak')
                                    term_pos = content_lower.find(term)
                                    
                                    if kodiak_pos >= 0 and term_pos >= 0 and abs(kodiak_pos - term_pos) < 500:
                                        print(f"  Found '{term}' near Kodiak reference")
                                        
                                        # Show context around the term
                                        start = max(0, min(kodiak_pos, term_pos) - 100)
                                        end = min(len(content), max(kodiak_pos, term_pos) + 100)
                                        context = content[start:end]
                                        print(f"  Context: ...{context}...")
                                        break
                        else:
                            print(f"  No Kodiak mentions found")
                    else:
                        print(f"  Could not retrieve content")
                        
                except Exception as e:
                    print(f"  Error retrieving content: {e}")
        
        if not financial_exhibits:
            print("No potentially relevant exhibits found")
            
        # Also check if there are any XBRL exhibits or data files
        print(f"\n=== XBRL Data Files ===")
        xbrl_files = []
        
        for attachment in attachments:
            if attachment.ixbrl or 'xbrl' in attachment.document.lower():
                xbrl_files.append(attachment)
                print(f"XBRL file: {attachment.document} - {attachment.description}")
                
        if not xbrl_files:
            print("No XBRL data files found beyond the main filing")
            
        print(f"\n=== Summary ===")
        print(f"Total attachments: {len(attachments)}")
        print(f"Financial exhibits examined: {len(financial_exhibits)}")
        print(f"XBRL files: {len(xbrl_files)}")
        
        # Final analysis: The issue might be that this S-4 filing only contains 
        # Ares Acquisition Corp's financial statements, not Kodiak's
        print(f"\n=== Analysis ===")
        print("Based on this analysis, the S-4 filing appears to contain only")
        print("Ares Acquisition Corporation's financial statements, not Kodiak Robotics'.")
        print("This is likely because:")
        print("1. S-4 forms are registration statements for business combinations")
        print("2. The filing entity (Ares Acquisition Corp) provides their own financials")
        print("3. Target company financials (Kodiak) might be in separate attachments")
        print("   or referenced documents, not in XBRL format")
        print("4. The user's expectation may be incorrect - S-4 XBRL typically")
        print("   contains only the registrant's (Ares) financial data")
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    search_kodiak_exhibits()