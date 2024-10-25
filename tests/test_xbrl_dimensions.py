import pytest
import asyncio
from edgar import Filing
from edgar.xbrl.xbrldata import XBRLData, XBRLInstance
from edgar.xbrl.dimensions import Dimensions, Member, Axis


@pytest.fixture(scope='module')
def apple_xbrl():
    filing: Filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2023-11-03',
                            accession_no='0000320193-23-000106')
    return asyncio.run(XBRLData.from_filing(filing))


def test_list_xbrl_dimensions(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions:Dimensions = instance.dimensions
    assert len(dimensions) == 256


def test_get_dimension_by_index(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    member: Member = instance.dimensions[0]
    assert member.concept == 'aapl:DebtInstrumentMaturityYearRangeEnd'


def test_get_axis_by_name(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    axis:Axis = instance.dimensions['ecd:IndividualAxis']
    assert axis.name == 'ecd:IndividualAxis'
    assert axis.list_members() ==['aapl:DeirdreOBrienMember', 'aapl:JeffWilliamsMember']


def test_get_dimension_axis(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.dimensions
    individual_axis = dimensions['ecd:IndividualAxis']
    assert individual_axis.name == 'ecd:IndividualAxis'
    assert len(individual_axis) == 12



def test_dimension_facts(apple_xbrl):
    instance: XBRLInstance = apple_xbrl.instance
    dimensions = instance.dimensions
    facts = dimensions['srt:ProductOrServiceAxis'].facts
    assert len(facts) == 24