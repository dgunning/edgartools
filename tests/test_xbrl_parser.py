import pytest
from edgar.xbrl import XBRL
from edgar.xbrl.parsers import XBRLParser
from pathlib import Path
from edgar import *


def test_parse_instance_content():
    instance_content = Path("data/xbrl/datafiles/gahc/Form10q_htm.xml").read_text()
    #print(instance_content)
    parser = XBRLParser()
    parser.parse_instance_content(instance_content)
    facts = parser.facts

    # Count returns a tuple: (unique_facts_count, total_fact_instances)
    unique_count, total_instances = parser.count_facts(instance_content)
    
    # Verify we have the right number of unique facts
    assert len(facts) == total_instances
    
    # Verify total instances matches the SEC site count (899)
    assert total_instances == 899  # This is the count shown on the SEC site


@pytest.mark.network
def test_instance_parsing_xoxo():
    filing = Filing(form='10-Q', filing_date='2020-05-11', company='ATLANTIC AMERICAN CORP', cik=8177, accession_no='0001140361-20-011243')
    xb = filing.xbrl()
    assert xb


@pytest.mark.slow
def test_extract_context_typed_member():
    """
    https://github.com/dgunning/edgartools/issues/364
    In parser.py the _extract_contexts method pulls only the child.tag for the typedMember segment.
    This is not always the useful part of the segment. For example the GBDC 10-Q has contexts like that below.
    The actually useful part of the segment is "Lacker Bidco Limited, One stop 2", not "InvestmentIdentifierAxis".
    
    Test validates that typed member parsing extracts the text content, not just the tag.
    """
    instance_content = Path("tests/fixtures/xbrl2/gbdc/gbdc-20250331_htm.xml").read_text()
    parser = XBRLParser()
    parser.parse_instance_content(instance_content)
    
    # Find the context c-689 which has the typed member
    context_689 = parser.contexts.get('c-689')
    
    assert context_689 is not None, "Context c-689 should exist"
    
    # Verify the typed member dimension is parsed correctly
    assert 'us-gaap:InvestmentIdentifierAxis' in context_689.dimensions
    
    # The dimension value should be the text content "Lacker Bidco Limited, One stop 2"
    # not the tag "us-gaap:InvestmentIdentifierAxis.domain"
    dimension_value = context_689.dimensions['us-gaap:InvestmentIdentifierAxis']
    assert dimension_value == "Lacker Bidco Limited, One stop 2", f"Expected 'Lacker Bidco Limited, One stop 2' but got '{dimension_value}'"