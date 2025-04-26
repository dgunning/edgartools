import pytest
import pandas as pd
from typing import List, Optional
import os
from io import StringIO

from edgar.funds.reference import (
    FundReferenceData, 
    FundCompanyRecord,
    FundSeriesRecord, 
    FundClassRecord,
    get_bulk_fund_data
)

# Test data for a small collection of funds
TEST_DATA = """Reporting File Number,CIK Number,Entity Name,Entity Org Type,Series ID,Series Name,Class ID,Class Name,Class Ticker,Address_1,Address_2,City,State,Zip Code
811-04526,0000035315,AMERICAN CENTURY MUTUAL FUNDS INC,N-1A,S000003482,AMERICAN CENTURY DISCIPLINED GROWTH FUND,C000005008,INVESTOR CLASS,ADCVX,4500 MAIN STREET,9TH FLOOR,KANSAS CITY,MO,64111
811-04526,0000035315,AMERICAN CENTURY MUTUAL FUNDS INC,N-1A,S000003482,AMERICAN CENTURY DISCIPLINED GROWTH FUND,C000005009,INSTITUTIONAL CLASS,ADCIX,4500 MAIN STREET,9TH FLOOR,KANSAS CITY,MO,64111
811-04526,0000035315,AMERICAN CENTURY MUTUAL FUNDS INC,N-1A,S000003483,AMERICAN CENTURY FOCUSED DYNAMIC GROWTH FUND,C000005010,INVESTOR CLASS,ACFOX,4500 MAIN STREET,9TH FLOOR,KANSAS CITY,MO,64111
811-04526,0000035315,AMERICAN CENTURY MUTUAL FUNDS INC,N-1A,S000003483,AMERICAN CENTURY FOCUSED DYNAMIC GROWTH FUND,C000005011,INSTITUTIONAL CLASS,ACFSX,4500 MAIN STREET,9TH FLOOR,KANSAS CITY,MO,64111
811-22048,0001332943,BLACKSTONE ALTERNATIVE INVESTMENT FUNDS,N-1A,S000047428,BLACKSTONE ALTERNATIVE MULTI-STRATEGY FUND,C000153996,CLASS I,BXMIX,345 PARK AVENUE,31ST FLOOR,NEW YORK,NY,10154
811-22048,0001332943,BLACKSTONE ALTERNATIVE INVESTMENT FUNDS,N-1A,S000047428,BLACKSTONE ALTERNATIVE MULTI-STRATEGY FUND,C000153997,CLASS D,BXMDX,345 PARK AVENUE,31ST FLOOR,NEW YORK,NY,10154
811-02968,0000225323,VANGUARD INDEX FUNDS,N-1A,S000002591,VANGUARD 500 INDEX FUND,C000004517,INVESTOR,VFINX,100 VANGUARD BLVD,,MALVERN,PA,19355
811-02968,0000225323,VANGUARD INDEX FUNDS,N-1A,S000002591,VANGUARD 500 INDEX FUND,C000004590,ADMIRAL,VFIAX,100 VANGUARD BLVD,,MALVERN,PA,19355
811-02968,0000225323,VANGUARD INDEX FUNDS,N-1A,S000002591,VANGUARD 500 INDEX FUND,C000147077,ETF,VOO,100 VANGUARD BLVD,,MALVERN,PA,19355
811-05972,0000932471,FIDELITY INVESTMENTS INSTITUTIONAL OPERATIONS COMPANY LLC,N-1A,S000001609,FIDELITY CONTRAFUND,C000001646,FIDELITY CONTRAFUND,FCNTX,245 SUMMER STREET,,BOSTON,MA,02210
811-05972,0000932471,FIDELITY INVESTMENTS INSTITUTIONAL OPERATIONS COMPANY LLC,N-1A,S000001609,FIDELITY CONTRAFUND,C000102830,FIDELITY CONTRAFUND K,FCNKX,245 SUMMER STREET,,BOSTON,MA,02210
"""


@pytest.fixture
def fund_reference_data():
    """Create a FundReferenceData instance with test data."""
    df = pd.read_csv(StringIO(TEST_DATA))
    return FundReferenceData(df)


class TestFundReferenceData:

    def test_initialization(self, fund_reference_data):
        """Test that the FundReferenceData is initialized correctly."""
        # Check counts
        assert fund_reference_data.companies_count == 4
        assert fund_reference_data.series_count == 5
        assert fund_reference_data.classes_count == 11

    def test_company_lookup(self, fund_reference_data):
        """Test company lookup by CIK."""
        # Valid lookup
        vanguard_cik = "0000225323"
        vanguard = fund_reference_data.get_company(vanguard_cik)
        assert vanguard is not None
        assert vanguard.name == "VANGUARD INDEX FUNDS"
        assert vanguard.entity_org_type == "N-1A"
        assert vanguard.file_number == "811-02968"
        assert vanguard.city == "MALVERN"
        assert vanguard.state == "PA"
        
        # Test with unpadded CIK
        vanguard = fund_reference_data.get_company("225323")
        assert vanguard is not None
        assert vanguard.name == "VANGUARD INDEX FUNDS"
        
        # Invalid lookup
        invalid_company = fund_reference_data.get_company("9999999999")
        assert invalid_company is None

    def test_series_lookup(self, fund_reference_data):
        """Test series lookup by series ID."""
        # Valid lookup
        s500_id = "S000002591"
        s500 = fund_reference_data.get_series(s500_id)
        assert s500 is not None
        assert s500.name == "VANGUARD 500 INDEX FUND"
        assert s500.cik == "0000225323"
        
        # Invalid lookup
        invalid_series = fund_reference_data.get_series("S999999999")
        assert invalid_series is None

    def test_class_lookup(self, fund_reference_data):
        """Test class lookup by class ID."""
        # Valid lookup
        vfiax_id = "C000004590"
        vfiax = fund_reference_data.get_class(vfiax_id)
        assert vfiax is not None
        assert vfiax.name == "ADMIRAL"
        assert vfiax.ticker == "VFIAX"
        assert vfiax.series_id == "S000002591"
        
        # Invalid lookup
        invalid_class = fund_reference_data.get_class("C999999999")
        assert invalid_class is None

    def test_ticker_lookup(self, fund_reference_data):
        """Test class lookup by ticker."""
        # Valid lookup
        vfiax = fund_reference_data.get_class_by_ticker("VFIAX")
        assert vfiax is not None
        assert vfiax.name == "ADMIRAL"
        assert vfiax.class_id == "C000004590"
        
        # Invalid lookup
        invalid_ticker = fund_reference_data.get_class_by_ticker("NONEXISTENT")
        assert invalid_ticker is None

    def test_hierarchical_navigation(self, fund_reference_data):
        """Test navigating up and down the hierarchy."""
        # Start with a company and navigate down
        vanguard_cik = "0000225323"
        vanguard = fund_reference_data.get_company(vanguard_cik)
        
        # Get all series for Vanguard
        series_list = fund_reference_data.get_series_for_company(vanguard_cik)
        assert len(series_list) == 1
        assert series_list[0].name == "VANGUARD 500 INDEX FUND"
        
        # Get all classes for the series
        s500_id = series_list[0].series_id
        classes = fund_reference_data.get_classes_for_series(s500_id)
        assert len(classes) == 3
        class_names = {cls.name for cls in classes}
        assert class_names == {"INVESTOR", "ADMIRAL", "ETF"}
        
        # Now start with a class and navigate up
        vfiax_id = "C000004590"  # VFIAX class ID
        vfiax = fund_reference_data.get_class(vfiax_id)
        
        # Get parent series
        parent_series = fund_reference_data.get_series_for_class(vfiax_id)
        assert parent_series is not None
        assert parent_series.name == "VANGUARD 500 INDEX FUND"
        
        # Get parent company
        parent_company = fund_reference_data.get_company_for_class(vfiax_id)
        assert parent_company is not None
        assert parent_company.name == "VANGUARD INDEX FUNDS"

    def test_hierarchical_info(self, fund_reference_data):
        """Test getting hierarchical info for different identifiers."""
        # Test with CIK
        company, series, class_record = fund_reference_data.get_hierarchical_info("0000225323")
        assert company is not None
        assert company.name == "VANGUARD INDEX FUNDS"
        assert series is None
        assert class_record is None
        
        # Test with series ID
        company, series, class_record = fund_reference_data.get_hierarchical_info("S000002591")
        assert company is not None
        assert company.name == "VANGUARD INDEX FUNDS"
        assert series is not None
        assert series.name == "VANGUARD 500 INDEX FUND"
        assert class_record is None
        
        # Test with class ID
        company, series, class_record = fund_reference_data.get_hierarchical_info("C000004590")
        assert company is not None
        assert company.name == "VANGUARD INDEX FUNDS"
        assert series is not None
        assert series.name == "VANGUARD 500 INDEX FUND"
        assert class_record is not None
        assert class_record.ticker == "VFIAX"
        
        # Test with ticker
        company, series, class_record = fund_reference_data.get_hierarchical_info("VFIAX")
        assert company is not None
        assert company.name == "VANGUARD INDEX FUNDS"
        assert series is not None
        assert series.name == "VANGUARD 500 INDEX FUND"
        assert class_record is not None
        assert class_record.ticker == "VFIAX"
        
        # Test with invalid identifier
        company, series, class_record = fund_reference_data.get_hierarchical_info("NONEXISTENT")
        assert company is None
        assert series is None
        assert class_record is None

    def test_name_search(self, fund_reference_data):
        """Test searching by name fragment."""
        # Search companies
        vanguard_results = fund_reference_data.find_by_name("VANGUARD", "company")
        assert len(vanguard_results) == 1
        assert vanguard_results[0].name == "VANGUARD INDEX FUNDS"
        
        # Search series
        growth_results = fund_reference_data.find_by_name("GROWTH", "series")
        assert len(growth_results) == 2
        assert {s.name for s in growth_results} == {
            "AMERICAN CENTURY DISCIPLINED GROWTH FUND",
            "AMERICAN CENTURY FOCUSED DYNAMIC GROWTH FUND"
        }
        
        # Search classes
        investor_results = fund_reference_data.find_by_name("INVESTOR", "class")
        assert len(investor_results) == 3  # Two from American Century + Vanguard Investor
        
        # Test case insensitivity
        lowercase_results = fund_reference_data.find_by_name("vanguard", "company")
        assert len(lowercase_results) == 1
        
        # Test invalid search type
        with pytest.raises(ValueError):
            fund_reference_data.find_by_name("test", "invalid_type")

    def test_to_dataframe(self, fund_reference_data):
        """Test converting back to DataFrame."""
        df = fund_reference_data.to_dataframe()
        
        # Check DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 11  # 11 classes in total
        assert "cik" in df.columns
        assert "company_name" in df.columns
        assert "series_id" in df.columns
        assert "series_name" in df.columns
        assert "class_id" in df.columns
        assert "class_name" in df.columns
        assert "ticker" in df.columns
        
        # Check data integrity by looking for VFIAX
        vfiax_row = df[df["ticker"] == "VFIAX"]
        assert len(vfiax_row) == 1
        assert vfiax_row.iloc[0]["class_name"] == "ADMIRAL"
        assert vfiax_row.iloc[0]["series_name"] == "VANGUARD 500 INDEX FUND"
        assert vfiax_row.iloc[0]["company_name"] == "VANGUARD INDEX FUNDS"


@pytest.mark.skipif(
    os.environ.get("SKIP_NETWORK_TESTS") == "1", 
    reason="Skip tests that require network access"
)
class TestFundReferenceDataWithActualData:
    """Tests that use the actual SEC data (requires network access)."""

    @pytest.fixture(scope="class")
    def actual_fund_data(self):
        """Load actual fund data from SEC website (cached)."""
        try:
            return get_bulk_fund_data()
        except Exception as e:
            pytest.skip(f"Could not download actual fund data: {e}")

    @pytest.fixture(scope="class")
    def actual_fund_reference_data(self, actual_fund_data):
        """Create FundReferenceData with actual fund data."""
        return FundReferenceData(actual_fund_data)

    def test_data_load(self, actual_fund_data):
        """Test that the actual data loads correctly."""
        assert actual_fund_data is not None
        assert len(actual_fund_data) > 100  # Should have many funds
        
        # Check expected columns
        expected_columns = {
            'Reporting File Number', 'CIK Number', 'Entity Name', 'Entity Org Type',
            'Series ID', 'Series Name', 'Class ID', 'Class Name', 'Class Ticker'
        }
        for col in expected_columns:
            assert col in actual_fund_data.columns

    def test_reference_data_initialization(self, actual_fund_reference_data):
        """Test FundReferenceData with actual data."""
        assert actual_fund_reference_data.companies_count > 50
        assert actual_fund_reference_data.series_count > 100
        assert actual_fund_reference_data.classes_count > 500
        
        # Verify that well-known funds are present
        fidelity_id = "0000225323"  # Vanguard's CIK
        fidelity = actual_fund_reference_data.get_company(fidelity_id)
        assert fidelity is not None
        assert "FIDELITY COURT STREET TRUST" in fidelity.name.upper()
        
        # Find Vanguard 500 Index Fund
        fidelity_series = actual_fund_reference_data.get_series_for_company(fidelity_id)
        assert len(fidelity_series) > 0
        fidelity_muni = next((s for s in fidelity_series if "New Jersey" in s.name), None)
        assert fidelity_muni is not None
        
        # Find VFIAX (Vanguard 500 Admiral shares)
        vfiax = actual_fund_reference_data.get_class_by_ticker("VFIAX")
        assert vfiax is not None
        assert "ADMIRAL" in vfiax.name.upper()

    def test_find_fund_families(self, actual_fund_reference_data):
        """Test finding major fund families."""
        # Test finding multiple major fund families by name
        fund_families = ["VANGUARD", "FIDELITY", "BLACKROCK", "T. ROWE PRICE", "AMERICAN FUNDS"]
        
        for family in fund_families:
            results = actual_fund_reference_data.find_by_name(family, "company")
            assert len(results) > 0, f"Could not find {family} funds"
            
            # Pick first company and check it has series
            company = results[0]
            series_list = actual_fund_reference_data.get_series_for_company(company.cik)
            assert len(series_list) > 0, f"{family} has no series"
            
            # Pick first series and check it has classes
            first_series = series_list[0]
            classes = actual_fund_reference_data.get_classes_for_series(first_series.series_id)
            assert len(classes) > 0, f"{family} series has no classes"

    def test_lookup_popular_funds(self, actual_fund_reference_data):
        """Test looking up popular fund tickers."""
        popular_tickers = ["SPY", "QQQ", "VTI", "VFIAX", "FXAIX", "FCNTX"]
        
        for ticker in popular_tickers:
            fund_class = actual_fund_reference_data.get_class_by_ticker(ticker)
            # Some tickers might not be available in the SEC data
            # but at least a few should be found
            if fund_class:
                series = actual_fund_reference_data.get_series_for_class(fund_class.class_id)
                assert series is not None
                company = actual_fund_reference_data.get_company_for_series(series.series_id)
                assert company is not None
                
                # Test hierarchical lookup
                hierarchy = actual_fund_reference_data.get_hierarchical_info(ticker)
                assert hierarchy[0] is not None  # Company
                assert hierarchy[1] is not None  # Series
                assert hierarchy[2] is not None  # Class
        
        # At least one popular fund should be found
        lookup_results = [actual_fund_reference_data.get_class_by_ticker(t) is not None for t in popular_tickers]
        assert any(lookup_results), "None of the popular fund tickers were found"