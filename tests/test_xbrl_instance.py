from edgar.xbrl.facts import XBRLInstance
from pathlib import Path

def test_facts_are_not_duplicated():
    instance_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text()
    instance = XBRLInstance.parse(instance_xml)
    #print(instance.facts)
    values = instance.facts.query("context_id=='c-26'")
    print(values)
    assert len(values) == 1

