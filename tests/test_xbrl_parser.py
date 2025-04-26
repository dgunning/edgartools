from edgar.xbrl import XBRL
from edgar.xbrl.parser import XBRLParser
from pathlib import Path


def test_parse_instance_content():
    instance_content = Path("data/xbrl/datafiles/gahc/Form10q_htm.xml").read_text()
    #print(instance_content)
    parser = XBRLParser()
    parser.parse_instance_content(instance_content)
    facts = parser.facts

    # Count returns a tuple: (unique_facts_count, total_fact_instances)
    unique_count, total_instances = parser.count_facts(instance_content)
    
    # Verify we have the right number of unique facts
    assert len(facts) == unique_count
    
    # Verify total instances matches the SEC site count (899)
    assert total_instances == 899  # This is the count shown on the SEC site