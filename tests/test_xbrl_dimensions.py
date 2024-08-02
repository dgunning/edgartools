import pytest
import asyncio
from edgar import Filing
from edgar.xbrl.xbrldata import XBRLData, XBRLInstance
from edgar.xbrl.dimensions import Dimensions, DimensionValue, Dimension


@pytest.fixture(scope='module')
def apple_xbrl():
    filing: Filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2023-11-03',
                            accession_no='0000320193-23-000106')
    return asyncio.run(XBRLData.from_filing(filing))


def test_list_xbrl_dimensions(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions:Dimensions = instance.dimensions
    assert len(dimensions) == 75


def test_get_dimension_by_index(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimension_value: DimensionValue = instance.dimensions[0]
    print(dimension_value)
    assert dimension_value.dimension == 'ecd:IndividualAxis'
    assert dimension_value.value == 'aapl:DeirdreOBrienMember'


def test_get_dimension_by_name(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimension:Dimension = instance.dimensions['ecd:IndividualAxis']
    assert dimension.name == 'ecd:IndividualAxis'
    assert dimension.values ==['aapl:DeirdreOBrienMember', 'aapl:JeffWilliamsMember']


def test_get_dimension_value(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.dimensions
    dimension_value: DimensionValue = dimensions['ecd:IndividualAxis']['aapl:DeirdreOBrienMember']
    assert dimension_value.dimension == 'ecd:IndividualAxis'
    assert dimension_value.value == 'aapl:DeirdreOBrienMember'


def test_get_dimension_facts(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.dimensions
    dimension_value: DimensionValue = dimensions['ecd:IndividualAxis']['aapl:DeirdreOBrienMember']
    facts = dimension_value.get_facts()
    assert len(facts) == 6


def test_query_facts_from_dimension(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.dimensions
    facts = dimensions['srt:ProductOrServiceAxis'].get_facts()
    assert len(facts) == 24