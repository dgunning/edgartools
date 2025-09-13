"""
Examine the content of specific exhibits to understand Kodiak Robotics financial data.
"""

from edgar import Company, set_identity
import re


def examine_kodiak_exhibits():
    """Examine specific exhibits for Kodiak financial data."""
    
    try:
        
        company = Company("0001747286")
        filings = company.get_filings(form="S-4", amendments=False)
        filing = filings[0]
        
        # Look at EX-99.2 which had multiple Kodiak mentions
        target_exhibits = ['d948047dex992.htm', 'd948047dex993.htm']
        
        for exhibit_doc in target_exhibits:
            print(f"\n=== Examining {exhibit_doc} ===")
            
            # Find the exhibit
            exhibit = None
            for attachment in filing.attachments:
                if attachment.document == exhibit_doc:
                    exhibit = attachment
                    break
            
            if not exhibit:
                print(f"Exhibit {exhibit_doc} not found")
                continue
                
            try:
                content = exhibit.content
                if content:
                    # Look for financial statement patterns
                    content_lower = content.lower()
                    
                    # Search for financial statement sections
                    financial_patterns = [
                        r'balance\s+sheet',
                        r'statement\s+of\s+operations',
                        r'income\s+statement',
                        r'cash\s+flow',
                        r'revenue\s*:?\s*\$?[\d,]+',
                        r'assets\s*:?\s*\$?[\d,]+',
                        r'liabilities\s*:?\s*\$?[\d,]+',
                        r'total\s+assets',
                        r'total\s+liabilities'
                    ]
                    
                    found_financial_data = False
                    for pattern in financial_patterns:
                        matches = re.findall(pattern, content_lower)
                        if matches:
                            found_financial_data = True
                            print(f"Found financial pattern '{pattern}': {len(matches)} matches")
                            # Show first few matches
                            for match in matches[:3]:
                                print(f"  Sample: {match}")
                    
                    if found_financial_data:
                        print("*** This exhibit contains financial data! ***")
                        
                        # Look for specific Kodiak financial numbers
                        kodiak_sections = []
                        lines = content.split('\n')
                        
                        for i, line in enumerate(lines):
                            if 'kodiak' in line.lower():
                                # Get context around this line (5 lines before and after)
                                start = max(0, i-5)
                                end = min(len(lines), i+6)
                                section = '\n'.join(lines[start:end])
                                kodiak_sections.append(section)
                        
                        print(f"Found {len(kodiak_sections)} sections mentioning Kodiak")
                        
                        # Show first section
                        if kodiak_sections:
                            print(f"\nSample Kodiak section:")
                            print("-" * 50)
                            print(kodiak_sections[0])
                            print("-" * 50)
                    else:
                        print("No financial data patterns found")
                        
                        # Just show where Kodiak is mentioned
                        kodiak_mentions = []
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if 'kodiak' in line.lower():
                                kodiak_mentions.append(f"Line {i}: {line.strip()}")
                        
                        print(f"Kodiak mentioned in {len(kodiak_mentions)} lines:")
                        for mention in kodiak_mentions[:5]:  # Show first 5
                            print(f"  {mention}")
                            
                else:
                    print("Could not retrieve exhibit content")
                    
            except Exception as e:
                print(f"Error examining exhibit: {e}")
        
        print(f"\n=== Final Assessment ===")
        print("The exhibits contain references to Kodiak Robotics, but these are likely")
        print("narrative descriptions or legal documents rather than structured financial")
        print("statements in XBRL format. The XBRL data in this S-4 filing only contains")
        print("Ares Acquisition Corp's financial statements, which is expected behavior.")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    examine_kodiak_exhibits()