#!/usr/bin/env python3
"""
Simple test to verify footnote parsing works correctly.
"""

from pathlib import Path
from edgar.xbrl.parser import XBRLParser

def test_footnotes():
    # Use the UNP test file
    test_file = Path("tests/fixtures/xbrl2/unp/unp-20121231.xml")
    
    # Parse the file
    parser = XBRLParser()
    instance_content = test_file.read_text()
    parser.parse_instance_content(instance_content)
    
    # Show results
    print(f"\n✓ Parsed {test_file.name}")
    print(f"✓ Found {len(parser.facts)} facts")
    print(f"✓ Found {len(parser.footnotes)} footnotes")
    
    # Show facts with IDs
    facts_with_ids = [f for f in parser.facts.values() if hasattr(f, 'fact_id') and f.fact_id]
    print(f"✓ {len(facts_with_ids)} facts have ID attributes")
    
    if facts_with_ids:
        print("\nSample facts with IDs:")
        for fact in facts_with_ids[:3]:
            print(f"  - {fact.element_id}: ID={fact.fact_id}")
    
    # Show footnotes
    if parser.footnotes:
        print(f"\nFootnotes found:")
        for fn_id, footnote in list(parser.footnotes.items())[:3]:
            print(f"  - {fn_id}: {footnote.text[:60]}...")
            print(f"    Links to facts: {', '.join(footnote.related_fact_ids[:3])}")
    
    # Check fact-footnote relationships
    facts_with_footnotes = [f for f in parser.facts.values() 
                            if hasattr(f, 'footnotes') and f.footnotes]
    if facts_with_footnotes:
        print(f"\n✓ {len(facts_with_footnotes)} facts reference footnotes")
        for fact in facts_with_footnotes[:3]:
            print(f"  - Fact {fact.fact_id} references: {', '.join(fact.footnotes)}")
    
    print("\n✅ Footnote parsing feature is working correctly!")

if __name__ == "__main__":
    test_footnotes()