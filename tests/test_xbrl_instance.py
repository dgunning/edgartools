from edgar.xbrl.instance import XBRLInstance
from pathlib import Path
import pytest


@pytest.fixture()
def apple_instance():
    instance_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text()
    return XBRLInstance.parse(instance_xml)

def test_query_facts_by_concept(apple_instance):
   facts = apple_instance.query_facts(concept="ecd:Rule10b51ArrAdoptedFlag")
   assert len(facts) == 2
   assert all(concept == "ecd:Rule10b51ArrAdoptedFlag" for concept in facts.concept)

def test_query_facts_by_member(apple_instance):
    facts = apple_instance.query_facts(dimensions={"ecd:IndividualAxis": "aapl:DeirdreOBrienMember"})
    assert len(facts) == 6
    assert facts["ecd:IndividualAxis"].drop_duplicates().tolist() == ["aapl:DeirdreOBrienMember"]

def test_query_facts_by_concept_and_member(apple_instance):
    facts = apple_instance.query_facts(concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                             dimensions={"srt:ProductOrServiceAxis": "aapl:IPadMember"})
    assert facts.concept.drop_duplicates().tolist() == ['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax']
    assert facts['srt:ProductOrServiceAxis'].drop_duplicates().tolist() == ['aapl:IPadMember']

def test_query_facts_by_axis(apple_instance):
    facts = apple_instance.query_facts(axis="srt:ProductOrServiceAxis")
    print(facts)
    assert facts['srt:ProductOrServiceAxis'].notnull().all()

def test_query_facts_by_concept_and_axis(apple_instance):
    facts = apple_instance.query_facts(concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                                       axis="srt:ProductOrServiceAxis")
    #print(facts)
    assert facts['srt:ProductOrServiceAxis'].notnull().all()
    assert facts.concept.drop_duplicates()[0] == 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'

def test_query_facts_by_schema(apple_instance):
    facts = apple_instance.query_facts(schema="us-gaap")
    assert all(facts.concept.str.startswith("us-gaap"))

def test_get_document_type(apple_instance):
    facts = apple_instance.query_facts(concept="dei:DocumentType")
    value = facts.value.item()
    assert value == '10-K'

def test_get_single_value_not_found(apple_instance):
    value = apple_instance._get_single_value('dei:DocumentTypeNotPresent')
    assert value is None

def test_facts_are_not_duplicated():
    instance_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text()
    instance = XBRLInstance.parse(instance_xml)
    # print(instance.facts)
    values = instance.query_facts(concept='us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                                      dimensions={'srt:ProductOrServiceAxis': 'aapl:IPadMember'})
    assert len(values) == 3

def test_instance_contains_dimensioned_facts_like_ipad():
    instance_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text()
    instance = XBRLInstance.parse(instance_xml)
    facts = instance.facts
    print()
    print(facts)

