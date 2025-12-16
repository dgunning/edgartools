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

    # Test total_shares - both persons have same shares (joint filers)
    # Should return unique count, not sum
    assert schedule.total_shares == 10000000  # Not summed!

    # Verify they're actually joint filers (same shares)
    assert len(schedule.reporting_persons) == 2
    assert schedule.reporting_persons[0].aggregate_amount == 10000000
    assert schedule.reporting_persons[1].aggregate_amount == 10000000

    # Test total_percent - should be unique percentage, not sum
    assert schedule.total_percent == pytest.approx(5.1, rel=0.01)  # Not 10.2%!

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
def test_accepts_both_form_name_conventions():
    """Test that both 'SC 13D' and 'SCHEDULE 13D' form names are accepted"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    # Test SC 13D convention
    filing_sc = Mock()
    filing_sc.form = 'SC 13D'
    filing_sc.filing_date = date(2024, 12, 31)
    filing_sc.xml = Mock(return_value=xml_content)

    schedule_sc = Schedule13D.from_filing(filing_sc)
    assert schedule_sc is not None
    assert schedule_sc.issuer_info.name == 'Aadi Bioscience, Inc.'

    # Test SC 13D/A convention
    filing_sc_a = Mock()
    filing_sc_a.form = 'SC 13D/A'
    filing_sc_a.filing_date = date(2024, 12, 31)
    filing_sc_a.xml = Mock(return_value=xml_content)

    schedule_sc_a = Schedule13D.from_filing(filing_sc_a)
    assert schedule_sc_a is not None
    assert schedule_sc_a.is_amendment is True

    # Test SCHEDULE 13D convention
    filing_schedule = Mock()
    filing_schedule.form = 'SCHEDULE 13D'
    filing_schedule.filing_date = date(2024, 12, 31)
    filing_schedule.xml = Mock(return_value=xml_content)

    schedule_schedule = Schedule13D.from_filing(filing_schedule)
    assert schedule_schedule is not None

    # Test SCHEDULE 13D/A convention
    filing_schedule_a = Mock()
    filing_schedule_a.form = 'SCHEDULE 13D/A'
    filing_schedule_a.filing_date = date(2024, 12, 31)
    filing_schedule_a.xml = Mock(return_value=xml_content)

    schedule_schedule_a = Schedule13D.from_filing(filing_schedule_a)
    assert schedule_schedule_a is not None


@pytest.mark.fast
def test_schedule13g_accepts_both_form_name_conventions():
    """Test that both 'SC 13G' and 'SCHEDULE 13G' form names are accepted"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()

    # Test SC 13G convention
    filing_sc = Mock()
    filing_sc.form = 'SC 13G'
    filing_sc.filing_date = date(2025, 11, 26)
    filing_sc.xml = Mock(return_value=xml_content)

    schedule_sc = Schedule13G.from_filing(filing_sc)
    assert schedule_sc is not None
    assert schedule_sc.issuer_info.name == 'Jushi Holdings Inc.'

    # Test SC 13G/A convention
    filing_sc_a = Mock()
    filing_sc_a.form = 'SC 13G/A'
    filing_sc_a.filing_date = date(2025, 11, 26)
    filing_sc_a.xml = Mock(return_value=xml_content)

    schedule_sc_a = Schedule13G.from_filing(filing_sc_a)
    assert schedule_sc_a is not None
    assert schedule_sc_a.is_amendment is True

    # Test SCHEDULE 13G convention
    filing_schedule = Mock()
    filing_schedule.form = 'SCHEDULE 13G'
    filing_schedule.filing_date = date(2025, 11, 26)
    filing_schedule.xml = Mock(return_value=xml_content)

    schedule_schedule = Schedule13G.from_filing(filing_schedule)
    assert schedule_schedule is not None

    # Test SCHEDULE 13G/A convention
    filing_schedule_a = Mock()
    filing_schedule_a.form = 'SCHEDULE 13G/A'
    filing_schedule_a.filing_date = date(2025, 11, 26)
    filing_schedule_a.xml = Mock(return_value=xml_content)

    schedule_schedule_a = Schedule13G.from_filing(filing_schedule_a)
    assert schedule_schedule_a is not None


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
def test_joint_filers_vs_separate_positions():
    """Test that joint filers (same shares) are handled differently from separate positions"""

    # Test 1: Schedule13D with SEPARATE positions (different share counts)
    # This is the existing test data - 2 persons with different shares
    xml_13d = SCHEDULE_13D_XML_PATH.read_text()
    filing_13d = Mock()
    filing_13d.form = 'SCHEDULE 13D'
    filing_13d.filing_date = date(2024, 12, 31)
    filing_13d.xml = Mock(return_value=xml_13d)

    schedule_13d = Schedule13D.from_filing(filing_13d)

    # Person 1: 2,100,000 shares (8.5%)
    # Person 2: 2,435,000 shares (9.9%)
    # These are DIFFERENT, so should be summed
    assert schedule_13d.total_shares == 2100000 + 2435000
    assert schedule_13d.total_shares == 4535000
    assert schedule_13d.total_percent == pytest.approx(8.5 + 9.9, rel=0.01)

    # Test 2: Schedule13G with JOINT filers (same share count)
    # This is the existing test data - 2 persons with same shares
    xml_13g = SCHEDULE_13G_XML_PATH.read_text()
    filing_13g = Mock()
    filing_13g.form = 'SCHEDULE 13G'
    filing_13g.filing_date = date(2025, 11, 26)
    filing_13g.xml = Mock(return_value=xml_13g)

    schedule_13g = Schedule13G.from_filing(filing_13g)

    # Person 1: 10,000,000 shares (5.1%)
    # Person 2: 10,000,000 shares (5.1%)
    # These are SAME (joint filers), so should NOT be summed
    assert schedule_13g.total_shares == 10000000  # Not doubled!
    assert schedule_13g.total_percent == pytest.approx(5.1, rel=0.01)  # Not 10.2%!


@pytest.mark.fast
def test_form_assertion():
    """Test that from_filing asserts correct form type"""
    filing = Mock()
    filing.form = '10-K'  # Wrong form
    filing.xml = Mock(return_value=SCHEDULE_13D_XML_PATH.read_text())

    with pytest.raises(AssertionError, match="Expected Schedule 13D form"):
        Schedule13D.from_filing(filing)

    with pytest.raises(AssertionError, match="Expected Schedule 13G form"):
        Schedule13G.from_filing(filing)


@pytest.mark.fast
def test_amendment_number_extraction():
    """Test extraction of amendment numbers from form names"""
    from edgar.beneficial_ownership.schedule13 import extract_amendment_number

    # Test non-amendment forms
    assert extract_amendment_number('SCHEDULE 13D') is None
    assert extract_amendment_number('SC 13G') is None
    assert extract_amendment_number('SCHEDULE 13G') is None

    # Test amendment without number
    assert extract_amendment_number('SCHEDULE 13D/A') is None
    assert extract_amendment_number('SC 13D/A') is None

    # Test "Amendment No. X" pattern
    assert extract_amendment_number('SCHEDULE 13D/A Amendment No. 9') == 9
    assert extract_amendment_number('SC 13G/A Amendment No. 12') == 12
    assert extract_amendment_number('SCHEDULE 13D/A amendment no. 3') == 3

    # Test "/A #X" pattern
    assert extract_amendment_number('SCHEDULE 13D/A #5') == 5
    assert extract_amendment_number('SC 13D/A#8') == 8
    assert extract_amendment_number('SCHEDULE 13G/A #15') == 15


@pytest.mark.fast
def test_amendment_number_field():
    """Test that amendment_number field is set correctly"""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()

    # Original filing - no amendment number
    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13D.from_filing(filing)
    assert schedule.amendment_number is None
    assert schedule.is_amendment is False

    # Amendment without number (typical case)
    filing_amend2 = Mock()
    filing_amend2.form = 'SCHEDULE 13D/A'
    filing_amend2.filing_date = date(2025, 1, 20)
    filing_amend2.xml = Mock(return_value=xml_content)

    amendment2 = Schedule13D.from_filing(filing_amend2)
    assert amendment2.amendment_number is None  # No number in form name
    assert amendment2.is_amendment is True


@pytest.mark.fast
def test_amendment_number_field_13g():
    """Test that amendment_number field is set correctly for Schedule 13G"""
    xml_content = SCHEDULE_13G_XML_PATH.read_text()

    # Original filing
    filing = Mock()
    filing.form = 'SC 13G'
    filing.filing_date = date(2025, 11, 26)
    filing.xml = Mock(return_value=xml_content)

    schedule = Schedule13G.from_filing(filing)
    assert schedule.amendment_number is None
    assert schedule.is_amendment is False

    # Amendment (typical case - no number in form name)
    filing_amend = Mock()
    filing_amend.form = 'SC 13G/A'
    filing_amend.filing_date = date(2025, 11, 30)
    filing_amend.xml = Mock(return_value=xml_content)

    amendment = Schedule13G.from_filing(filing_amend)
    assert amendment.amendment_number is None  # No number in standard form name
    assert amendment.is_amendment is True


@pytest.mark.fast
def test_reporting_person_new_boolean_fields():
    """Test new boolean fields on ReportingPerson"""
    # Test default values
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

    assert person.is_aggregate_exclude_shares is False
    assert person.no_cik is False

    # Test with explicit values
    person2 = ReportingPerson(
        cik='',
        name='No CIK Person',
        citizenship='US',
        sole_voting_power=100000,
        shared_voting_power=0,
        sole_dispositive_power=100000,
        shared_dispositive_power=0,
        aggregate_amount=100000,
        percent_of_class=1.0,
        type_of_reporting_person='IN',
        is_aggregate_exclude_shares=True,
        no_cik=True
    )

    assert person2.is_aggregate_exclude_shares is True
    assert person2.no_cik is True


@pytest.mark.fast
def test_excluded_shares_not_aggregated():
    """Test that shares with is_aggregate_exclude_shares=True are not counted in total_shares"""
    # Create a mock Schedule13D with reporting persons where some have excluded shares
    from edgar.beneficial_ownership.models import Schedule13DItems
    from unittest.mock import Mock

    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)

    # Person 1: 1,000,000 shares - INCLUDED
    person1 = ReportingPerson(
        cik='0001',
        name='Person 1',
        citizenship='US',
        sole_voting_power=1000000,
        shared_voting_power=0,
        sole_dispositive_power=1000000,
        shared_dispositive_power=0,
        aggregate_amount=1000000,
        percent_of_class=5.0,
        type_of_reporting_person='IN',
        is_aggregate_exclude_shares=False
    )

    # Person 2: 500,000 shares - EXCLUDED
    person2 = ReportingPerson(
        cik='0002',
        name='Person 2',
        citizenship='US',
        sole_voting_power=500000,
        shared_voting_power=0,
        sole_dispositive_power=500000,
        shared_dispositive_power=0,
        aggregate_amount=500000,
        percent_of_class=2.5,
        type_of_reporting_person='IN',
        is_aggregate_exclude_shares=True  # EXCLUDED
    )

    # Person 3: 2,000,000 shares - INCLUDED
    person3 = ReportingPerson(
        cik='0003',
        name='Person 3',
        citizenship='US',
        sole_voting_power=2000000,
        shared_voting_power=0,
        sole_dispositive_power=2000000,
        shared_dispositive_power=0,
        aggregate_amount=2000000,
        percent_of_class=10.0,
        type_of_reporting_person='IN',
        is_aggregate_exclude_shares=False
    )

    schedule = Schedule13D(
        filing=filing,
        issuer_info=IssuerInfo(cik='0001234', name='Test Corp', cusip='123456789'),
        security_info=SecurityInfo(title='Common Stock', cusip='123456789'),
        reporting_persons=[person1, person2, person3],
        items=Schedule13DItems(),
        signatures=[],
        date_of_event='12/31/2024'
    )

    # Total should be 1,000,000 + 2,000,000 = 3,000,000
    # Person 2's 500,000 shares should be excluded
    assert schedule.total_shares == 3000000
    assert schedule.total_percent == pytest.approx(15.0, rel=0.01)  # 5.0% + 10.0%


@pytest.mark.fast
def test_all_excluded_shares_returns_zero():
    """Test that total_shares returns 0 when all shares are excluded"""
    from edgar.beneficial_ownership.models import Schedule13DItems
    from unittest.mock import Mock

    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2024, 12, 31)

    # All persons have excluded shares
    person1 = ReportingPerson(
        cik='0001',
        name='Person 1',
        citizenship='US',
        sole_voting_power=1000000,
        shared_voting_power=0,
        sole_dispositive_power=1000000,
        shared_dispositive_power=0,
        aggregate_amount=1000000,
        percent_of_class=5.0,
        type_of_reporting_person='IN',
        is_aggregate_exclude_shares=True
    )

    schedule = Schedule13D(
        filing=filing,
        issuer_info=IssuerInfo(cik='0001234', name='Test Corp', cusip='123456789'),
        security_info=SecurityInfo(title='Common Stock', cusip='123456789'),
        reporting_persons=[person1],
        items=Schedule13DItems(),
        signatures=[],
        date_of_event='12/31/2024'
    )

    assert schedule.total_shares == 0
    assert schedule.total_percent == pytest.approx(0.0)


@pytest.mark.fast
def test_undeclared_joint_filers_detection():
    """
    Test detection of joint filers when member_of_group is None but all
    reporting persons have identical share amounts and percentages.

    This handles real-world cases like Sora Vision Ltd (0001213900-25-121883)
    where the XML doesn't specify member_of_group but all persons report
    the same position.
    """
    from edgar.beneficial_ownership.models import Schedule13DItems

    # Create mock filing
    filing = Mock()
    filing.form = 'SCHEDULE 13D/A'
    filing.filing_date = date(2025, 12, 16)

    # Four reporting persons with identical values, member_of_group=None
    # This simulates the Sora Vision Ltd case
    persons = [
        ReportingPerson(
            name="Sora Ventures Global Limited",
            cik="",
            citizenship="Cayman Islands",
            aggregate_amount=14450000,
            percent_of_class=58.1,
            sole_voting_power=0,
            shared_voting_power=14450000,
            sole_dispositive_power=0,
            shared_dispositive_power=14450000,
            member_of_group=None,  # Not declared in XML
            type_of_reporting_person="CO"
        ),
        ReportingPerson(
            name="JASON KIN HOI FANG",
            cik="",
            citizenship="Hong Kong",
            aggregate_amount=14450000,
            percent_of_class=58.1,
            sole_voting_power=0,
            shared_voting_power=14450000,
            sole_dispositive_power=0,
            shared_dispositive_power=14450000,
            member_of_group=None,  # Not declared in XML
            type_of_reporting_person="IN"
        ),
        ReportingPerson(
            name="Sora Vision Limited",
            cik="0002070153",
            citizenship="Cayman Islands",
            aggregate_amount=14450000,
            percent_of_class=58.1,
            sole_voting_power=0,
            shared_voting_power=14450000,
            sole_dispositive_power=0,
            shared_dispositive_power=14450000,
            member_of_group=None,  # Not declared in XML
            type_of_reporting_person="CO"
        ),
        ReportingPerson(
            name="Sora Ventures II Master Fund",
            cik="",
            citizenship="Cayman Islands",
            aggregate_amount=14450000,
            percent_of_class=58.1,
            sole_voting_power=0,
            shared_voting_power=14450000,
            sole_dispositive_power=0,
            shared_dispositive_power=14450000,
            member_of_group=None,  # Not declared in XML
            type_of_reporting_person="OO"
        ),
    ]

    schedule = Schedule13D(
        filing=filing,
        issuer_info=IssuerInfo(name="Sora Vision Ltd", cik="2070153", cusip="000000000"),
        security_info=SecurityInfo(title="Common Stock", cusip="000000000"),
        reporting_persons=persons,
        items=Schedule13DItems(),
        signatures=[],
        date_of_event='12/16/2025'
    )

    # With undeclared joint filers, should detect identical values and not sum
    # Should return 14,450,000 (58.1%) not 57,800,000 (232.4%)
    assert schedule.total_shares == 14450000, \
        "Should detect undeclared joint filers and return unique count"
    assert schedule.total_percent == pytest.approx(58.1, rel=0.01), \
        "Should detect undeclared joint filers and return unique percentage"

    # Verify there are actually multiple persons
    assert len(schedule.reporting_persons) == 4


@pytest.mark.fast
def test_separate_filers_with_different_values():
    """
    Test that separate filers with different share amounts are correctly summed.
    This ensures the joint filer detection doesn't break normal separate filer cases.
    """
    from edgar.beneficial_ownership.models import Schedule13DItems

    filing = Mock()
    filing.form = 'SCHEDULE 13D'
    filing.filing_date = date(2025, 12, 16)

    # Three reporting persons with DIFFERENT values (separate filers)
    persons = [
        ReportingPerson(
            name="Investor A",
            cik="0001111111",
            citizenship="US",
            aggregate_amount=5000000,
            percent_of_class=10.0,
            sole_voting_power=5000000,
            shared_voting_power=0,
            sole_dispositive_power=5000000,
            shared_dispositive_power=0,
            member_of_group=None,
            type_of_reporting_person="IN"
        ),
        ReportingPerson(
            name="Investor B",
            cik="0002222222",
            citizenship="US",
            aggregate_amount=3000000,
            percent_of_class=6.0,
            sole_voting_power=3000000,
            shared_voting_power=0,
            sole_dispositive_power=3000000,
            shared_dispositive_power=0,
            member_of_group=None,
            type_of_reporting_person="IN"
        ),
        ReportingPerson(
            name="Investor C",
            cik="0003333333",
            citizenship="Delaware",
            aggregate_amount=2000000,
            percent_of_class=4.0,
            sole_voting_power=2000000,
            shared_voting_power=0,
            sole_dispositive_power=2000000,
            shared_dispositive_power=0,
            member_of_group=None,
            type_of_reporting_person="CO"
        ),
    ]

    schedule = Schedule13D(
        filing=filing,
        issuer_info=IssuerInfo(name="Test Company", cik="9999999", cusip="999999999"),
        security_info=SecurityInfo(title="Common Stock", cusip="999999999"),
        reporting_persons=persons,
        items=Schedule13DItems(),
        signatures=[],
        date_of_event='12/16/2025'
    )

    # Separate filers should be summed
    assert schedule.total_shares == 5000000 + 3000000 + 2000000
    assert schedule.total_shares == 10000000
    assert schedule.total_percent == pytest.approx(10.0 + 6.0 + 4.0, rel=0.01)
    assert schedule.total_percent == pytest.approx(20.0, rel=0.01)
