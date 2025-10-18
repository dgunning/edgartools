"""Test XBRL footnote parsing functionality."""
import pytest
from pathlib import Path
from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.models import Footnote


def test_footnote_extraction_with_fact_ids():
    """Test that footnotes are correctly extracted and linked to facts."""
    # Use the UNP test file which has facts with ID attributes
    test_file = Path(__file__).parent / "fixtures" / "xbrl" / "unp" / "unp-20121231.xml"
    
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")
    
    # Parse the XBRL document
    parser = XBRLParser()
    instance_content = test_file.read_text()
    parser.parse_instance_content(instance_content)
    
    # Check that facts with IDs were captured
    facts_with_ids = [fact for fact in parser.facts.values() if fact.fact_id]
    assert len(facts_with_ids) > 0, "Expected to find facts with ID attributes"
    
    # Verify fact IDs match expected pattern (e.g., "ID_0", "ID_1", etc.)
    sample_fact = facts_with_ids[0]
    assert sample_fact.fact_id is not None
    assert sample_fact.fact_id.startswith("ID_"), f"Expected fact ID to start with 'ID_', got {sample_fact.fact_id}"
    
    # If footnotes exist, verify their structure
    if parser.footnotes:
        # Check footnote structure
        footnote_id, footnote = next(iter(parser.footnotes.items()))
        assert isinstance(footnote, Footnote)
        assert footnote.footnote_id == footnote_id
        assert isinstance(footnote.text, str)
        assert isinstance(footnote.related_fact_ids, list)
        
        # Check that footnotes are linked to facts
        if footnote.related_fact_ids:
            # Verify that related facts exist
            for fact_id in footnote.related_fact_ids:
                # Find the fact with this ID
                matching_facts = [f for f in parser.facts.values() if f.fact_id == fact_id]
                if matching_facts:
                    fact = matching_facts[0]
                    # Verify the fact references the footnote
                    assert footnote_id in fact.footnotes, f"Expected fact {fact_id} to reference footnote {footnote_id}"


def test_get_footnotes_for_fact():
    """Test the get_footnotes_for_fact method."""
    test_file = Path(__file__).parent / "fixtures" / "xbrl" / "unp" / "unp-20121231.xml"
    
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")
    
    from edgar.xbrl import XBRL
    xbrl = XBRL()
    instance_content = test_file.read_text()
    xbrl.parser.parse_instance_content(instance_content)
    
    # Find a fact with an ID
    facts_with_ids = [fact for fact in xbrl.parser.facts.values() if fact.fact_id]
    
    if facts_with_ids:
        test_fact = facts_with_ids[0]
        
        # Get footnotes for this fact
        footnotes = xbrl.get_footnotes_for_fact(test_fact.fact_id)
        
        # Verify the result is a list
        assert isinstance(footnotes, list)
        
        # If the fact has footnotes, verify they're returned correctly
        if test_fact.footnotes:
            assert len(footnotes) == len(test_fact.footnotes)
            for footnote in footnotes:
                assert isinstance(footnote, Footnote)
                assert test_fact.fact_id in footnote.related_fact_ids


def test_get_facts_with_footnotes():
    """Test the get_facts_with_footnotes method."""
    test_file = Path(__file__).parent / "fixtures" / "xbrl" / "unp" / "unp-20121231.xml"
    
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")
    
    from edgar.xbrl import XBRL
    xbrl = XBRL()
    instance_content = test_file.read_text()
    xbrl.parser.parse_instance_content(instance_content)
    
    # Get facts with footnotes
    facts_with_footnotes = xbrl.get_facts_with_footnotes()
    
    # Verify the result is a dictionary
    assert isinstance(facts_with_footnotes, dict)
    
    # All returned facts should have footnotes
    for fact_key, fact in facts_with_footnotes.items():
        assert len(fact.footnotes) > 0, f"Expected fact {fact_key} to have footnotes"
        assert fact.footnotes is not None
        assert isinstance(fact.footnotes, list)


def test_footnote_in_string_representation():
    """Test that footnotes are mentioned in the string representation when present."""
    test_file = Path(__file__).parent / "fixtures" / "xbrl" / "unp" / "unp-20121231.xml"
    
    if not test_file.exists():
        pytest.skip(f"Test file not found: {test_file}")
    
    from edgar.xbrl import XBRL
    xbrl = XBRL()
    instance_content = test_file.read_text()
    xbrl.parser.parse_instance_content(instance_content)
    
    # Get string representation
    str_repr = str(xbrl)
    
    # Check if footnotes are mentioned when they exist
    if xbrl.footnotes:
        assert "footnote" in str_repr.lower(), "Expected footnotes to be mentioned in string representation"
    else:
        # If no footnotes, they shouldn't be mentioned
        assert "footnote" not in str_repr.lower() or "0 footnotes" in str_repr.lower()


if __name__ == "__main__":
    # Run a basic test to verify the implementation works
    test_footnote_extraction_with_fact_ids()
    print("✓ Footnote extraction test passed")
    
    test_get_footnotes_for_fact() 
    print("✓ Get footnotes for fact test passed")
    
    test_get_facts_with_footnotes()
    print("✓ Get facts with footnotes test passed")
    
    test_footnote_in_string_representation()
    print("✓ String representation test passed")
    
    print("\nAll footnote tests passed!")