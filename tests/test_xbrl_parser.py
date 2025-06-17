from edgar.xbrl import XBRL
from edgar.xbrl.parser import XBRLParser
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

def test_number_of_facts_in_xbrl():

    filing = Filing(form='10-Q', filing_date='2024-02-01', company='SPIRE ALABAMA INC', cik=3146, accession_no='0001437749-24-002776')
    xb = filing.xbrl()
    num_facts = len(xb.facts)
    print(num_facts)

def test_instance_parsing_xoxo():
    filing = Filing(form='10-Q', filing_date='2020-05-11', company='ATLANTIC AMERICAN CORP', cik=8177, accession_no='0001140361-20-011243')
    xb = filing.xbrl()
    assert xb