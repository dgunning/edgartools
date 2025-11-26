"""
Tests for Schedule 13D and Schedule 13G beneficial ownership reports.

Tests XML parsing, dataclass creation, amendment tracking, and Rich rendering
for both Schedule 13D (active ownership) and Schedule 13G (passive ownership).
"""
import pytest
from pathlib import Path
from unittest.mock import Mock
from datetime import date

from edgar.beneficial_ownership import (
    Schedule13D,
    Schedule13G,
    ReportingPerson,
    IssuerInfo,
    SecurityInfo
)
from edgar.beneficial_ownership.amendments import (
    AmendmentInfo,
    OwnershipComparison,
    get_amendment_info,
    compare_to_previous
)


# Test data paths
TEST_DATA_DIR = Path(__file__).parent / 'data' / 'beneficial_ownership'
SCHEDULE_13D_XML_PATH = TEST_DATA_DIR / 'schedule13d.xml'
SCHEDULE_13G_XML_PATH = TEST_DATA_DIR / 'schedule13g.xml'


@pytest.mark.fast
def test_parse_schedule13d_xml():
    """Test parsing Schedule 13D from local XML file"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()
    result = Schedule13D.parse_xml(xml_content)

    # Verify issuer info
    assert result['issuer_info'].name == 'Aadi Bioscience, Inc.'
    assert result['issuer_info'].cik == '0001422142'
    assert result['issuer_info'].cusip == '00032Q104'

    # Verify security info
    assert result['security_info'].title == 'Common stock, par value $0.0001 per share'
    assert result['security_info'].cusip == '00032Q104'

    # Verify date
    assert result['date_of_event'] == '12/31/2024'
    assert result['previously_filed'] is True

    # Verify reporting persons (should be 2)
    assert len(result['reporting_persons']) == 2

    # First reporting person
    person1 = result['reporting_persons'][0]
    assert person1.name == 'BML Investment Partners, L.P.'
    assert person1.cik == '0001373604'
    assert person1.percent_of_class == 8.5
    assert person1.aggregate_amount == 2100000
    assert person1.sole_voting_power == 0
    assert person1.shared_voting_power == 2100000
    assert person1.type_of_reporting_person == 'PN'

    # Second reporting person
    person2 = result['reporting_persons'][1]
    assert person2.name == 'Leonard Braden Michael'
    assert person2.cik == '0001373603'
    assert person2.percent_of_class == 9.9
    assert person2.aggregate_amount == 2435000
    assert person2.sole_voting_power == 335000
    assert person2.shared_voting_power == 2100000

    # Verify Items
    assert result['items'] is not None
    assert result['items'].item1_security_title == 'Common stock, par value $0.0001 per share'
    assert result['items'].item1_issuer_name == 'Aadi Bioscience, Inc.'
    assert result['items'].item3_source_of_funds is not None
    assert 'working capital' in result['items'].item3_source_of_funds.lower()
    assert result['items'].item4_purpose_of_transaction is not None
    assert 'investment purposes' in result['items'].item4_purpose_of_transaction.lower()

    # Verify signatures
    assert len(result['signatures']) == 2
    assert result['signatures'][0].reporting_person == 'BML Investment Partners, L.P.'
    assert result['signatures'][0].signature == 'Braden M Leonard'
    assert result['signatures'][0].date == '12/31/2024'


@pytest.mark.fast
def test_schedule13d_from_xml():
    """Test creating Schedule13D instance from XML"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    # Create mock filing
    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13D.from_filing(filing)

    assert schedule is not None
    assert isinstance(schedule, Schedule13D)
    assert schedule.issuer_info.name == 'Aadi Bioscience, Inc.'
    assert len(schedule.reporting_persons) == 2
    assert schedule.date_of_event == '12/31/2024'
    assert schedule.items.item4_purpose_of_transaction is not None
    assert schedule.filing_date == date(2024, 12, 31)
    assert schedule.is_amendment is False


@pytest.mark.fast
def test_schedule13d_properties():
    """Test Schedule13D computed properties"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13D.from_filing(filing)

    # Test total_shares
    assert schedule.total_shares == 2100000 + 2435000  # Sum of both persons
    assert schedule.total_shares == 4535000

    # Test total_percent
    assert schedule.total_percent == pytest.approx(8.5 + 9.9, rel=0.01)

    # Test is_amendment
    assert schedule.is_amendment is False


@pytest.mark.fast
def test_parse_schedule13g_xml():
    """Test parsing Schedule 13G from local XML file"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()
    result = Schedule13G.parse_xml(xml_content)

    # Verify issuer info
    assert result['issuer_info'].name == 'Jushi Holdings Inc.'
    assert result['issuer_info'].cik == '0001909747'
    assert result['issuer_info'].cusip == '48213Y107'

    # Verify security info
    assert result['security_info'].title == 'Subordinate Voting Shares, no par value'
    assert result['security_info'].cusip == '48213Y107'

    # Verify event date
    assert result['event_date'] == '11/19/2025'

    # Verify rule designation
    assert result['rule_designation'] == 'Rule 13d-1(c)'

    # Verify reporting persons (should be 2)
    assert len(result['reporting_persons']) == 2

    # First reporting person
    person1 = result['reporting_persons'][0]
    assert person1.name == 'Marex Securities Products Inc.'
    assert person1.percent_of_class == 5.1
    assert person1.aggregate_amount == 10000000
    assert person1.sole_voting_power == 10000000
    assert person1.type_of_reporting_person == 'CO'

    # Second reporting person
    person2 = result['reporting_persons'][1]
    assert person2.name == 'Marex Group plc'
    assert person2.type_of_reporting_person == 'OO'

    # Verify signatures
    assert len(result['signatures']) == 2


@pytest.mark.fast
def test_schedule13g_from_xml():
    """Test creating Schedule13G instance from XML"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()

    # Create mock filing
    filing = Mock()
    filing.form = 'SCHEDULE 13G'
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13G.from_filing(filing)

    assert schedule is not None
    assert isinstance(schedule, Schedule13G)
    assert schedule.issuer_info.name == 'Jushi Holdings Inc.'
    assert len(schedule.reporting_persons) == 2
    assert schedule.event_date == '11/19/2025'
    assert schedule.is_passive_investor is True
    assert schedule.is_amendment is False


@pytest.mark.fast
def test_schedule13g_properties():
    """Test Schedule13G computed properties"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()

    filing = Mock()
    filing.form = 'SCHEDULE 13G'
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13G.from_filing(filing)

    # Test total_shares (both persons have same shares - not additive)
    assert schedule.total_shares == 10000000 + 10000000  # Sum reported
    assert schedule.total_shares == 20000000

    # Test total_percent
    assert schedule.total_percent == pytest.approx(5.1 + 5.1, rel=0.01)

    # Test passive investor flag
    assert schedule.is_passive_investor is True


@pytest.mark.fast
def test_amendment_detection():
    """Test amendment detection"""
    # Original filing
    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=SCHEDULE_13D_XML_PATH.read_text())

    original = Schedule13D.from_filing(filing)
    assert original.is_amendment is False

    # Amendment
    filing_amend = Mock()
    filing_amend.form = 'SCHEDULE 13D/A'
    filing_amend.filing_date = date(2025, 1, 15)
    filing_amend.xml = Mock(return_value=SCHEDULE_13D_XML_PATH.read_text())

    amendment = Schedule13D.from_filing(filing_amend)
    assert amendment.is_amendment is True


@pytest.mark.fast
def test_amendment_info():
    """Test AmendmentInfo dataclass"""
    # Original filing
    filing = Mock()
    filing.form = 'SCHEDULE 13D'

    info = AmendmentInfo.from_filing(filing)
    assert info.is_amendment is False
    assert info.amendment_number is None

    # First amendment
    filing_amend = Mock()
    filing_amend.form = 'SCHEDULE 13D/A'

    info_amend = AmendmentInfo.from_filing(filing_amend)
    assert info_amend.is_amendment is True
    assert info_amend.amendment_number == 1


@pytest.mark.fast
def test_ownership_comparison():
    """Test OwnershipComparison for tracking changes"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    # Create original filing
    filing1 = Mock()
    filing1.form = 'SCHEDULE 13D'
    filing1.filing_date = date(2024, 12, 1)
    filing1.xml = Mock(return_value=xml_content)
    original = Schedule13D.from_filing(filing1)

    # Create modified version (same data for test)
    filing2 = Mock()
    filing2.form = 'SCHEDULE 13D/A'
    filing2.filing_date = date(2024, 12, 31)
    filing2.xml = Mock(return_value=xml_content)
    amended = Schedule13D.from_filing(filing2)

    # Compare (should show no change since using same XML)
    comparison = OwnershipComparison(current=amended, previous=original)

    assert comparison.shares_change == 0
    assert comparison.percent_change == pytest.approx(0.0)
    assert comparison.is_unchanged is True
    assert comparison.is_accumulating is False
    assert comparison.is_liquidating is False

    # Test summary
    summary = comparison.get_summary()
    assert 'shares_change' in summary
    assert 'percent_change' in summary
    assert summary['is_unchanged'] is True


@pytest.mark.fast
def test_reporting_person_properties():
    """Test ReportingPerson computed properties"""
    person = ReportingPerson(
        cik='0001234567',
        name='Test Investor',
        citizenship='US',
        sole_voting_power=1000000,
        shared_voting_power=500000,
        sole_dispositive_power=1200000,
        shared_dispositive_power=300000,
        aggregate_amount=1500000,
        percent_of_class=7.5,
        type_of_reporting_person='IN'
    )

    assert person.total_voting_power == 1500000  # 1M + 500K
    assert person.total_dispositive_power == 1500000  # 1.2M + 300K


@pytest.mark.fast
def test_rich_rendering_schedule13d():
    """Test Rich console rendering for Schedule 13D"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13D.from_filing(filing)
    rich_output = schedule.__rich__()

    # Verify it returns a Rich renderable
    from rich.panel import Panel
    assert isinstance(rich_output, Panel)


@pytest.mark.fast
def test_rich_rendering_schedule13g():
    """Test Rich console rendering for Schedule 13G"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()

    filing = Mock()
    filing.form = 'SCHEDULE 13G'
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13G.from_filing(filing)
    rich_output = schedule.__rich__()

    # Verify it returns a Rich renderable
    from rich.panel import Panel
    assert isinstance(rich_output, Panel)


@pytest.mark.fast
def test_invalid_xml():
    """Test handling of invalid XML"""
    with pytest.raises(ValueError, match="missing <edgarSubmission>"):
        Schedule13D.parse_xml("<invalid>xml</invalid>")

    with pytest.raises(ValueError, match="missing <edgarSubmission>"):
        Schedule13G.parse_xml("<invalid>xml</invalid>")


@pytest.mark.fast
def test_missing_xml():
    """Test handling when filing has no XML"""
    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.xml = Mock(return_value=None)

    result = Schedule13D.from_filing(filing)
    assert result is None


@pytest.mark.fast
def test_form_assertion():
    """Test that from_filing asserts correct form type"""
    filing = Mock()
    filing.form = '10-K'  # Wrong form
    filing.xml = Mock(return_value=SCHEDULE_13D_XML_PATH.read_text())

    with pytest.raises(AssertionError, match="Expected SCHEDULE 13D"):
        Schedule13D.from_filing(filing)

    with pytest.raises(AssertionError, match="Expected SCHEDULE 13G"):
        Schedule13G.from_filing(filing)
