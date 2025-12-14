"""
Tests for Form 10-D Asset-Backed Securities Distribution Report.
"""
import pytest
from datetime import date

from edgar.abs import TenD
from edgar.abs.ten_d import ABSType, ABSEntity, DistributionPeriod


class TestTenDDataclasses:
    """Test the supporting dataclasses."""

    def test_abs_entity_creation(self):
        """Test ABSEntity dataclass creation."""
        entity = ABSEntity(name="Test Entity", cik="123456", file_number="333-123456")
        assert entity.name == "Test Entity"
        assert entity.cik == "123456"
        assert entity.file_number == "333-123456"
        assert str(entity) == "Test Entity"

    def test_abs_entity_optional_fields(self):
        """Test ABSEntity with optional fields."""
        entity = ABSEntity(name="Test Entity")
        assert entity.name == "Test Entity"
        assert entity.cik is None
        assert entity.file_number is None

    def test_distribution_period_creation(self):
        """Test DistributionPeriod dataclass creation."""
        period = DistributionPeriod(
            start_date=date(2025, 10, 21),
            end_date=date(2025, 11, 18)
        )
        assert period.start_date == date(2025, 10, 21)
        assert period.end_date == date(2025, 11, 18)
        assert str(period) == "Oct 21, 2025 to Nov 18, 2025"

    def test_distribution_period_unknown(self):
        """Test DistributionPeriod with unknown dates."""
        period = DistributionPeriod()
        assert str(period) == "Unknown period"


class TestABSType:
    """Test ABSType enum."""

    def test_abs_types(self):
        """Test all ABS type values."""
        assert ABSType.CMBS.value == "CMBS"
        assert ABSType.AUTO.value == "AUTO"
        assert ABSType.CREDIT_CARD.value == "CREDIT_CARD"
        assert ABSType.RMBS.value == "RMBS"
        assert ABSType.STUDENT_LOAN.value == "STUDENT_LOAN"
        assert ABSType.UTILITY.value == "UTILITY"
        assert ABSType.OTHER.value == "OTHER"


@pytest.fixture(scope="module")
def cmbs_ten_d():
    """Get a CMBS 10-D filing for testing."""
    from edgar import find
    # BANK5 2024-5YR9 - a CMBS filing with full XML exhibits
    filing = find('0001888524-25-020550')
    return filing.obj()


@pytest.fixture(scope="module")
def credit_card_ten_d():
    """Get a Credit Card 10-D filing for testing."""
    from edgar import Company
    # Find a Chase Issuance Trust 10-D filing
    try:
        company = Company(1174821)  # Chase Issuance Trust
        filings = company.get_filings(form='10-D')
        if filings and len(filings) > 0:
            return filings[0].obj()
    except Exception:
        pass
    return None


class TestTenDBasic:
    """Basic tests for TenD class."""

    def test_ten_d_creation_wrong_form(self):
        """Test TenD raises error for non-10-D filing."""
        from edgar import get_filings

        # Get a 10-K filing
        filings = get_filings(form='10-K')
        if filings:
            filing = filings[0]
            with pytest.raises(ValueError, match="Expected 10-D filing"):
                TenD(filing)

    def test_ten_d_from_filing(self, cmbs_ten_d):
        """Test TenD creation from filing."""
        assert cmbs_ten_d is not None
        assert isinstance(cmbs_ten_d, TenD)
        assert cmbs_ten_d.form in ('10-D', '10-D/A')


class TestTenDHeaderExtraction:
    """Tests for header extraction."""

    def test_issuing_entity_extraction(self, cmbs_ten_d):
        """Test issuing entity is extracted correctly."""
        issuer = cmbs_ten_d.issuing_entity
        assert issuer is not None
        assert isinstance(issuer, ABSEntity)
        assert issuer.name == "BANK5 2024-5YR9"
        assert issuer.cik is not None

    def test_depositor_extraction(self, cmbs_ten_d):
        """Test depositor is extracted correctly."""
        depositor = cmbs_ten_d.depositor
        assert depositor is not None
        assert isinstance(depositor, ABSEntity)
        assert "J.P. Morgan" in depositor.name or "JPMorgan" in depositor.name
        assert depositor.cik is not None

    def test_sponsors_extraction(self, cmbs_ten_d):
        """Test sponsors are extracted correctly."""
        sponsors = cmbs_ten_d.sponsors
        assert sponsors is not None
        assert len(sponsors) > 0
        for sponsor in sponsors:
            assert isinstance(sponsor, ABSEntity)
            assert sponsor.name
            assert sponsor.cik is not None

    def test_distribution_period_extraction(self, cmbs_ten_d):
        """Test distribution period is extracted correctly."""
        period = cmbs_ten_d.distribution_period
        assert period is not None
        assert isinstance(period, DistributionPeriod)
        assert period.start_date is not None
        assert period.end_date is not None
        assert period.start_date < period.end_date

    def test_security_classes_extraction(self, cmbs_ten_d):
        """Test security classes are extracted correctly."""
        classes = cmbs_ten_d.security_classes
        assert classes is not None
        assert len(classes) > 0
        # CMBS typically has many tranches
        assert len(classes) > 5


class TestTenDABSTypeDetection:
    """Tests for ABS type detection."""

    def test_cmbs_detection(self, cmbs_ten_d):
        """Test CMBS type is detected correctly."""
        assert cmbs_ten_d.abs_type == ABSType.CMBS
        # CMBS filings have EX-102 asset data
        assert cmbs_ten_d.has_asset_data is True


class TestTenDRichDisplay:
    """Tests for rich display."""

    def test_str_representation(self, cmbs_ten_d):
        """Test string representation."""
        result = str(cmbs_ten_d)
        assert "TenD" in result
        assert "BANK5" in result

    def test_rich_representation(self, cmbs_ten_d):
        """Test rich console representation."""
        rich_output = cmbs_ten_d.__rich__()
        assert rich_output is not None


class TestTenDFilingIntegration:
    """Integration tests with filing system."""

    def test_filing_obj_returns_ten_d(self):
        """Test filing.obj() returns TenD for 10-D filings."""
        from edgar import find

        filing = find('0001888524-25-020550')
        assert filing.form == '10-D'
        obj = filing.obj()
        assert isinstance(obj, TenD)

    def test_filing_properties_accessible(self, cmbs_ten_d):
        """Test filing properties are accessible through TenD."""
        assert cmbs_ten_d.filing is not None
        assert cmbs_ten_d.accession_number is not None
        assert cmbs_ten_d.filing_date is not None
        assert cmbs_ten_d.company is not None


class TestTenDDateParsing:
    """Tests for date parsing functionality."""

    def test_parse_date_with_comma(self):
        """Test parsing date with comma."""
        ten_d_class = TenD.__new__(TenD)
        result = ten_d_class._parse_date_string("October 21, 2025")
        assert result == date(2025, 10, 21)

    def test_parse_date_without_comma(self):
        """Test parsing date without comma."""
        ten_d_class = TenD.__new__(TenD)
        result = ten_d_class._parse_date_string("October 21 2025")
        assert result == date(2025, 10, 21)

    def test_parse_date_abbreviated_month(self):
        """Test parsing date with abbreviated month."""
        ten_d_class = TenD.__new__(TenD)
        result = ten_d_class._parse_date_string("Oct 21, 2025")
        assert result == date(2025, 10, 21)

    def test_parse_date_invalid(self):
        """Test parsing invalid date returns None."""
        ten_d_class = TenD.__new__(TenD)
        result = ten_d_class._parse_date_string("not a date")
        assert result is None


class TestCMBSAssetData:
    """Tests for CMBS asset data parsing."""

    def test_asset_data_available(self, cmbs_ten_d):
        """Test asset_data is available for CMBS filings."""
        assert cmbs_ten_d.has_asset_data is True
        assert cmbs_ten_d.asset_data is not None

    def test_loans_dataframe(self, cmbs_ten_d):
        """Test loans property returns DataFrame."""
        import pandas as pd

        loans = cmbs_ten_d.loans
        assert isinstance(loans, pd.DataFrame)
        assert len(loans) > 0

        # Check key columns exist
        expected_columns = ['loan_id', 'originator', 'original_amount', 'actual_balance',
                           'maturity_date', 'current_rate', 'payment_status']
        for col in expected_columns:
            assert col in loans.columns, f"Missing column: {col}"

    def test_properties_dataframe(self, cmbs_ten_d):
        """Test properties property returns DataFrame."""
        import pandas as pd

        props = cmbs_ten_d.properties
        assert isinstance(props, pd.DataFrame)
        assert len(props) > 0

        # Check key columns exist
        expected_columns = ['loan_id', 'name', 'city', 'state', 'property_type',
                           'valuation', 'occupancy_securitization']
        for col in expected_columns:
            assert col in props.columns, f"Missing column: {col}"

    def test_loans_data_types(self, cmbs_ten_d):
        """Test loan data types are correctly parsed."""
        loans = cmbs_ten_d.loans
        if len(loans) > 0:
            first_loan = loans.iloc[0]

            # Check numeric types
            assert isinstance(first_loan['original_amount'], float)
            assert isinstance(first_loan['actual_balance'], float)
            assert isinstance(first_loan['current_rate'], float)

            # Check date types
            from datetime import date as date_type
            if first_loan['maturity_date'] is not None:
                assert isinstance(first_loan['maturity_date'], date_type)

    def test_properties_data_types(self, cmbs_ten_d):
        """Test property data types are correctly parsed."""
        props = cmbs_ten_d.properties
        if len(props) > 0:
            first_prop = props.iloc[0]

            # Check string types
            assert isinstance(first_prop['name'], str)

            # Check numeric types where available
            if first_prop['valuation'] is not None:
                assert isinstance(first_prop['valuation'], float)
            if first_prop['occupancy_securitization'] is not None:
                assert isinstance(first_prop['occupancy_securitization'], float)

    def test_asset_data_summary(self, cmbs_ten_d):
        """Test asset_data.summary() returns valid summary."""
        from edgar.abs.cmbs import CMBSSummary

        summary = cmbs_ten_d.asset_data.summary()
        assert isinstance(summary, CMBSSummary)

        assert summary.num_loans > 0
        assert summary.num_properties >= 0
        assert summary.total_loan_balance > 0
        assert summary.total_original_loan_amount > 0

        # Check property types dict
        assert isinstance(summary.property_types, dict)
        assert isinstance(summary.states, dict)

    def test_asset_data_rich_display(self, cmbs_ten_d):
        """Test asset_data has rich display."""
        rich_output = cmbs_ten_d.asset_data.__rich__()
        assert rich_output is not None

    def test_asset_data_str(self, cmbs_ten_d):
        """Test asset_data string representation."""
        result = str(cmbs_ten_d.asset_data)
        assert "CMBSAssetData" in result
        assert "loans" in result
        assert "properties" in result


class TestCMBSAssetDataStandalone:
    """Tests for CMBSAssetData class using sample XML file."""

    @pytest.fixture
    def sample_xml(self):
        """Load sample CMBS XML from data directory."""
        import os
        xml_path = os.path.join(os.path.dirname(__file__), '..', 'data', '10-D', 'exh_102.xml')
        if os.path.exists(xml_path):
            with open(xml_path, 'r') as f:
                return f.read()
        return None

    def test_parse_sample_xml(self, sample_xml):
        """Test parsing sample XML file."""
        if sample_xml is None:
            pytest.skip("Sample XML not available")

        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData(sample_xml)
        assert len(cmbs) > 0
        assert len(cmbs.properties) > 0

    def test_loans_have_required_fields(self, sample_xml):
        """Test loans have all required fields."""
        if sample_xml is None:
            pytest.skip("Sample XML not available")

        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData(sample_xml)
        loans = cmbs.loans

        # Check first loan has data
        first_loan = loans.iloc[0]
        assert first_loan['loan_id'] is not None
        assert first_loan['originator'] is not None
        assert first_loan['original_amount'] is not None

    def test_properties_have_required_fields(self, sample_xml):
        """Test properties have all required fields."""
        if sample_xml is None:
            pytest.skip("Sample XML not available")

        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData(sample_xml)
        props = cmbs.properties

        # Find a property with actual data (not NA)
        for _, prop in props.iterrows():
            if prop['name'] and prop['name'] != 'NA':
                assert prop['loan_id'] is not None
                break

    def test_summary_calculations(self, sample_xml):
        """Test summary statistics are calculated correctly."""
        if sample_xml is None:
            pytest.skip("Sample XML not available")

        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData(sample_xml)
        summary = cmbs.summary()

        # Verify summary matches raw data
        loans = cmbs.loans
        assert summary.num_loans == len(loans)

        # Total balance should match sum
        if 'actual_balance' in loans.columns:
            expected_balance = loans['actual_balance'].sum()
            assert abs(summary.total_loan_balance - expected_balance) < 1  # Allow small floating point diff

    def test_empty_xml(self):
        """Test handling of empty/invalid XML."""
        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData("<assetData></assetData>")
        assert len(cmbs) == 0
        assert len(cmbs.properties) == 0

    def test_invalid_xml(self):
        """Test handling of invalid XML."""
        from edgar.abs.cmbs import CMBSAssetData

        cmbs = CMBSAssetData("not xml at all")
        # Should not raise, just return empty data
        assert len(cmbs) == 0


class TestTenDWithoutAssetData:
    """Tests for 10-D filings without CMBS asset data."""

    def test_loans_empty_for_non_cmbs(self, credit_card_ten_d):
        """Test loans is empty for non-CMBS filings."""
        import pandas as pd

        if credit_card_ten_d is None:
            pytest.skip("Credit card filing not available")

        loans = credit_card_ten_d.loans
        assert isinstance(loans, pd.DataFrame)
        # Credit card filings don't have XML asset data
        if credit_card_ten_d.abs_type != ABSType.CMBS:
            assert len(loans) == 0

    def test_properties_empty_for_non_cmbs(self, credit_card_ten_d):
        """Test properties is empty for non-CMBS filings."""
        import pandas as pd

        if credit_card_ten_d is None:
            pytest.skip("Credit card filing not available")

        props = credit_card_ten_d.properties
        assert isinstance(props, pd.DataFrame)
        if credit_card_ten_d.abs_type != ABSType.CMBS:
            assert len(props) == 0

    def test_asset_data_none_for_non_cmbs(self, credit_card_ten_d):
        """Test asset_data is None for non-CMBS filings."""
        if credit_card_ten_d is None:
            pytest.skip("Credit card filing not available")

        if credit_card_ten_d.abs_type != ABSType.CMBS:
            assert credit_card_ten_d.asset_data is None
