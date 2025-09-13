"""
Deep analysis of the S-4 filing to understand where Kodiak Robotics financial data might be located.
This script will examine all attachments, exhibits, and documents in the filing.
"""

from edgar import Company, set_identity
import sys
import traceback


def analyze_s4_filing_structure():
    """Analyze the complete structure of the S-4 filing."""
    
    print("=== S-4 Filing Structure Analysis ===")
    
    try:
        
        # Get company and S-4 filing
        company = Company("0001747286")  # This is actually Kodiak Robotics' CIK
        filings = company.get_filings(form="S-4", amendments=False)
        
        if not filings:
            print("No S-4 filings found")
            return
            
        filing = filings[0]
        print(f"Filing: {filing}")
        print(f"Filing date: {filing.filing_date}")
        print(f"Accession number: {filing.accession_no}")
        
        # Check all attachments and documents
        print(f"\n=== Attachments Analysis ===")
        attachments = filing.attachments
        print(f"Number of attachments: {len(attachments)}")
        
        for i, attachment in enumerate(attachments):
            print(f"\nAttachment {i+1}:")
            print(f"  Document: {attachment.document}")
            print(f"  Description: {attachment.description}")
            print(f"  Document Type: {attachment.document_type}")
            print(f"  Size: {attachment.size}")
            print(f"  Sequence: {attachment.sequence_number}")
            print(f"  Is XBRL: {attachment.ixbrl if hasattr(attachment, 'ixbrl') else 'N/A'}")
            
            # Check if this attachment might contain Kodiak data
            doc_name = attachment.document.lower()
            desc = attachment.description.lower() if attachment.description else ""
            
            if 'kodiak' in doc_name or 'kodiak' in desc:
                print(f"  *** POTENTIAL KODIAK DOCUMENT ***")
            
            if 'robotics' in doc_name or 'robotics' in desc:
                print(f"  *** POTENTIAL ROBOTICS DOCUMENT ***")
                
            # Check for exhibit references
            if 'exhibit' in doc_name or 'exhibit' in desc:
                print(f"  *** EXHIBIT DOCUMENT ***")
        
        # Check the primary document content
        print(f"\n=== Primary Document Analysis ===")
        primary_doc = filing.primary_document
        print(f"Primary document: {primary_doc}")
        
        # Try to get the HTML content to search for mentions of Kodiak
        try:
            content = filing.html()
            if content and hasattr(content, 'text'):
                text_content = content.text.lower()
                kodiak_mentions = text_content.count('kodiak')
                robotics_mentions = text_content.count('robotics')
                
                print(f"Mentions of 'kodiak' in primary document: {kodiak_mentions}")
                print(f"Mentions of 'robotics' in primary document: {robotics_mentions}")
                
                # Look for financial statement references for Kodiak
                financial_keywords = ['balance sheet', 'income statement', 'cash flow', 'statement of operations']
                for keyword in financial_keywords:
                    if keyword in text_content and 'kodiak' in text_content[max(0, text_content.find(keyword)-200):text_content.find(keyword)+200]:
                        print(f"Found '{keyword}' near 'kodiak' references")
        except Exception as e:
            print(f"Error analyzing HTML content: {e}")
        
        # Examine XBRL data structure in detail
        print(f"\n=== XBRL Entity Analysis ===")
        if filing.is_xbrl:
            xbrl = filing.xbrl()
            
            # Check entity information
            print(f"XBRL Entity name: {xbrl.entity_name}")
            print(f"XBRL Entity CIK: {xbrl.entity}")
            
            # Check all entity identifiers in contexts
            entity_ids = set()
            if hasattr(xbrl, 'contexts') and xbrl.contexts:
                print(f"Number of contexts: {len(xbrl.contexts)}")
                
                for context_id, context in xbrl.contexts.items():
                    if hasattr(context, 'entity') and context.entity:
                        if hasattr(context.entity, 'identifier'):
                            entity_ids.add(context.entity.identifier)
                        elif isinstance(context.entity, dict) and 'identifier' in context.entity:
                            entity_ids.add(context.entity['identifier'])
                
                print(f"Unique entity identifiers in contexts: {entity_ids}")
                
                # Map entity IDs to company names if possible
                for entity_id in entity_ids:
                    print(f"Entity ID {entity_id}:")
                    # Try to look up this entity
                    try:
                        entity_company = Company(entity_id)
                        print(f"  Company name: {entity_company.name}")
                        print(f"  CIK: {entity_company.cik}")
                    except Exception as e:
                        print(f"  Could not resolve company name: {e}")
            
            # Check for any facts that might reference Kodiak
            facts_list = xbrl.facts.get_facts()
            print(f"\nTotal facts in XBRL: {len(facts_list)}")
            
            kodiak_facts = []
            robotics_facts = []
            
            for fact in facts_list:
                fact_str = str(fact).lower()
                if 'kodiak' in fact_str:
                    kodiak_facts.append(fact)
                if 'robotics' in fact_str:
                    robotics_facts.append(fact)
            
            print(f"Facts mentioning 'kodiak': {len(kodiak_facts)}")
            print(f"Facts mentioning 'robotics': {len(robotics_facts)}")
            
            if kodiak_facts:
                print("Sample Kodiak facts:")
                for fact in kodiak_facts[:3]:
                    print(f"  Concept: {fact.get('concept')}")
                    print(f"  Value: {fact.get('value')}")
            
        print(f"\n=== CIK Cross-Reference ===")
        # The user mentioned CIK 0001747286 for Kodiak Robotics
        # But let's check what company this actually resolves to
        try:
            cik_company = Company("0001747286")
            print(f"CIK 0001747286 resolves to: {cik_company.name}")
            print(f"Company ticker: {cik_company.ticker if hasattr(cik_company, 'ticker') else 'N/A'}")
        except Exception as e:
            print(f"Error resolving CIK 0001747286: {e}")
            
        # Try to find Kodiak Robotics by name
        try:
            kodiak_company = Company("Kodiak Robotics")
            print(f"Kodiak Robotics CIK: {kodiak_company.cik}")
            print(f"Kodiak Robotics name: {kodiak_company.name}")
        except Exception as e:
            print(f"Error finding Kodiak Robotics by name: {e}")
            
    except Exception as e:
        print(f"Error during analysis: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    analyze_s4_filing_structure()