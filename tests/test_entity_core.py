"""
Consolidated entity core functionality tests.

This file consolidates tests from:
- test_entity.py 
- test_entity_hierarchy.py
- test_entity_redesign.py
- test_entity_package.py

Focus: Basic entity operations, class hierarchy, factory functions, and core functionality.
"""

import pytest
from functools import lru_cache
from pathlib import Path
import json
from datetime import datetime

from edgar.entity import (
    Entity,
    Company,
    SecFiler,
    get_entity,
    get_company,
    find_company,
    get_company_tickers,
    get_icon_from_ticker,
    get_entity_submissions,
    get_ticker_to_cik_lookup,
    get_cik_lookup_data,
    CompanySearchResults,
    NoCompanyFactsFound
)
from edgar.entity.data import parse_entity_submissions, CompanyData
from edgar.entity.constants import _classify_is_individual, _name_suggests_company


@pytest.fixture
@lru_cache(maxsize=16)
def apple_company():
    """Cached Apple company fixture for faster tests"""
    return Company("AAPL")


@pytest.fixture
@lru_cache(maxsize=16)
def apple_entity():
    """Cached Apple entity fixture for faster tests"""
    return Entity("0000320193")


class TestEntityHierarchy:
    """Test entity class hierarchy and inheritance relationships"""
    
    @pytest.mark.fast
    def test_class_inheritance_structure(self, apple_entity, apple_company):
        """Test that the class hierarchy is correct"""
        # Test inheritance relationships
        assert isinstance(apple_entity, Entity)
        assert isinstance(apple_entity, SecFiler)
        assert isinstance(apple_company, Company)
        assert isinstance(apple_company, Entity)
        assert isinstance(apple_company, SecFiler)
        
        # Test method resolution order
        entity_mro = Entity.__mro__
        company_mro = Company.__mro__
        assert SecFiler in entity_mro
        assert Entity in company_mro
        assert SecFiler in company_mro
    
    @pytest.mark.fast 
    def test_entity_vs_company_capabilities(self, apple_entity, apple_company):
        """Test specialized behavior differences between Entity and Company"""
        # Company-specific methods
        assert hasattr(apple_company, 'get_financials')
        assert hasattr(apple_company, 'get_ticker')
        
        # Entity doesn't have Company-specific methods
        assert not hasattr(apple_entity, 'get_financials')
        assert not hasattr(apple_entity, 'get_ticker')
        
        # Both should have common EntityData interface
        for obj in [apple_company, apple_entity]:
            assert hasattr(obj.data, 'get_filings')
            assert hasattr(obj.data, 'cik')
            assert hasattr(obj.data, 'name')


class TestEntityCreation:
    """Test entity and company creation patterns"""
    
    @pytest.mark.network
    def test_entity_creation_by_cik(self):
        """Test Entity creation with different CIK formats"""
        # String CIK with leading zeros
        entity1 = Entity("0000320193")
        assert entity1.cik == 320193

        # Integer CIK
        entity2 = Entity(320193)
        assert entity2.cik == 320193

        # Both should reference same entity
        assert entity1.cik == entity2.cik

    @pytest.mark.network
    def test_company_creation_patterns(self):
        """Test Company creation with ticker and CIK"""
        # By ticker
        company1 = Company("AAPL")
        assert company1.cik == 320193
        assert company1.get_ticker() == "AAPL"

        # By CIK
        company2 = Company(320193)
        assert company2.cik == 320193
        assert company2.get_ticker() == "AAPL"

        # Both should be equivalent
        assert company1.cik == company2.cik

    @pytest.mark.fast
    def test_entity_data_validation(self, apple_entity):
        """Test that entity data is properly populated"""
        assert apple_entity.data is not None
        assert apple_entity.data.name is not None
        assert apple_entity.data.cik == 320193
        assert "Apple" in apple_entity.data.name

    @pytest.mark.fast
    def test_company_data_validation(self, apple_company):
        """Test that company data is properly populated"""
        assert apple_company.data is not None
        assert "Apple" in apple_company.data.name
        assert apple_company.cik == 320193


class TestEntityClassification:
    """Test entity type classification logic"""
    
    @pytest.mark.fast
    @pytest.mark.vcr
    @pytest.mark.parametrize("cik,is_individual,is_company", [
        (1771340, True, False),   # Taneja Vaibhav at TSLA (individual)
        (1800903, False, True),   # &VEST Domestic Fund II LP (company)
        (940418, False, True),    # Siemens AG (company)
        (1830056, False, True),   # SIEMENS ENERGY AG/ADR (company)
        (1718179, True, False),   # SIEVERT STEPHANIE A (individual)
        (1911716, False, True),   # Company
        (1940261, False, True),   # NVC Holdings, LLC (company)
        (310522, False, True),    # FANNIE MAE (company)
    ])
    def test_entity_classification(self, cik, is_individual, is_company):
        """Test entity classification as individual vs company"""
        entity = Entity(cik)
        assert entity.is_individual == is_individual, f"CIK {cik} individual classification failed"
        assert entity.is_company == is_company, f"CIK {cik} company classification failed"


class TestFactoryFunctions:
    """Test factory functions for entity creation"""
    
    @pytest.mark.fast
    def test_factory_function_existence(self):
        """Test that factory functions exist and are callable"""
        functions = [
            get_entity, get_company, find_company, get_company_tickers,
            get_icon_from_ticker, get_entity_submissions, get_ticker_to_cik_lookup,
            get_cik_lookup_data
        ]
        for func in functions:
            assert callable(func), f"{func.__name__} should be callable"
    
    @pytest.mark.network
    def test_get_entity_factory(self):
        """Test the get_entity factory function"""
        entity = get_entity("0000320193")
        assert entity.cik == 320193
        assert isinstance(entity, Entity)

    @pytest.mark.network
    def test_get_company_factory(self):
        """Test the get_company factory function"""
        company = get_company("AAPL")
        assert company.cik == 320193
        assert isinstance(company, Company)

    @pytest.mark.network
    def test_company_search_factory(self):
        """Test that company search works"""
        results = find_company("Apple")
        assert isinstance(results, CompanySearchResults)
        assert len(results) > 0


class TestEntitySubmissions:
    """Test entity submissions functionality"""
    
    def test_parse_entity_submissions(self):
        """Test parsing entity submissions data"""
        # This test uses fixture data - mark as fast since it's local
        fixture_path = Path("data/company_submission.json")
        if fixture_path.exists():
            with fixture_path.open('r') as f:
                tsla_submissions = json.load(f)
            data: CompanyData = parse_entity_submissions(tsla_submissions)
            assert data
            assert data.industry == 'Motor Vehicles & Passenger Car Bodies'
            assert data.sic == '3711'
            assert data.fiscal_year_end == '1231'
        else:
            pytest.skip("Test fixture not available")
    
    @pytest.mark.network
    @pytest.mark.slow
    def test_get_company_submissions(self):
        """Test getting company submissions via API"""
        company_data: CompanyData = get_entity_submissions(1318605)  # Tesla
        assert company_data
        assert company_data.cik == 1318605
        
        filings = company_data.get_filings()
        assert len(filings) > 1000
        
        # Check earliest filing
        earliest_filing = filings[-1]
        assert earliest_filing.form == "REGDEX"


class TestEntityFilingIntegration:
    """Test entity-filing integration functionality"""
    
    @pytest.mark.network
    @pytest.mark.slow
    def test_company_filings_access(self, apple_company):
        """Test getting filings from a Company"""
        # Get 10-K filings
        filings = apple_company.get_filings(form="10-K")
        assert filings is not None
        assert len(filings) > 0
        assert "10-K" in filings.data['form'][0].as_py()
        
        # Get latest filing
        latest = apple_company.latest("10-K")
        assert latest is not None
        assert "10-K" in latest.form
        
    @pytest.mark.network
    def test_entity_facts_access(self, apple_entity):
        """Test getting facts from an Entity"""
        facts = apple_entity.get_facts()
        
        # Note: Facts might not always be available
        if facts is not None:
            assert facts.cik == 320193
            assert len(facts) > 0


class TestEntityLegacyCompatibility:
    """Test compatibility with legacy entity patterns"""
    
    @pytest.mark.network
    def test_tsla_fixture_pattern(self):
        """Test Tesla fixture pattern from legacy tests"""
        # This mimics the pattern from the original test_entity.py
        tsla = Company("TSLA")
        assert tsla is not None
        assert tsla.cik == 1318605  # Tesla's CIK

    @pytest.mark.network
    def test_no_company_for_invalid_cik(self):
        """Test handling of invalid/non-existent CIK"""
        # This should handle gracefully or raise appropriate exception
        try:
            entity = Entity(999999999)  # Invalid CIK
            # If it doesn't raise, check it handles gracefully
            assert entity.cik == 999999999
        except (ValueError, NoCompanyFactsFound):
            # These are acceptable exceptions for invalid CIKs
            pass


# Representative subset of _classify_is_individual tests (consolidated from test_is_individual.py)
# 18 cases covering all 9 signal priorities + 4 realistic profiles
CLASSIFICATION_UNIT_TESTS = [
    # Signal 1: issuer flag (strongest → company)
    ("issuer_flag_overrides_owner",
     dict(insider_transaction_for_issuer_exists=True,
          insider_transaction_for_owner_exists=True, entity_type="other"),
     False),
    # Signal 2: tickers/exchanges → company
    ("single_ticker", dict(tickers=["AAPL"]), False),
    # Signal 3: state of incorporation → company
    ("state_de", dict(state_of_incorporation="DE"), False),
    # Signal 4: entity_type → company
    ("entity_type_operating", dict(entity_type="operating"), False),
    ("entity_type_fund", dict(entity_type="fund"), False),
    # Signal 5: forms → company
    ("form_10k", dict(forms=["10-K"]), False),
    ("form_20f", dict(forms=["20-F"]), False),
    # Signal 6: EIN → company
    ("valid_ein", dict(ein="942404110"), False),
    # Signal 7: name heuristics
    ("name_corporation", dict(name="MICROSOFT CORPORATION"), False),
    ("name_co_whole_word", dict(name="STANDARD OIL CO"), False),
    ("name_co_not_substring", dict(name="SCOTT JOHNSON"), True),
    ("name_plain_individual", dict(name="JOHN SMITH"), True),
    # Signal 8: owner flag (weak → individual)
    ("owner_flag_alone", dict(insider_transaction_for_owner_exists=True), True),
    # Signal 9: default (no signals → individual)
    ("no_signals_at_all", dict(), True),
    # Realistic profiles
    ("real_apple",
     dict(name="APPLE INC", entity_type="operating", tickers=["AAPL"],
          exchanges=["Nasdaq"], state_of_incorporation="CA", ein="942404110",
          insider_transaction_for_issuer_exists=True,
          forms=["10-K", "10-Q", "8-K", "DEF 14A"], cik=320193),
     False),
    ("real_insider_individual",
     dict(name="COOK TIMOTHY D", entity_type="other",
          insider_transaction_for_owner_exists=True,
          insider_transaction_for_issuer_exists=False,
          forms=["3", "4"], cik=1214156),
     True),
    ("real_warren_buffett",
     dict(name="BUFFETT WARREN E", entity_type="other", ein="470539396",
          insider_transaction_for_owner_exists=True,
          forms=["3", "4", "SC 13D", "SC 13D/A"], cik=315090),
     True),
    ("real_holding_company_owner",
     dict(name="BLACKROCK CAPITAL MANAGEMENT", entity_type="other",
          insider_transaction_for_owner_exists=True,
          forms=["SC 13D", "SC 13G"]),
     False),
]


@pytest.mark.parametrize("test_id, kwargs, expected",
                         CLASSIFICATION_UNIT_TESTS,
                         ids=[t[0] for t in CLASSIFICATION_UNIT_TESTS])
def test_classify_is_individual(test_id, kwargs, expected):
    """Unit tests for _classify_is_individual covering all 9 signal priorities."""
    result = _classify_is_individual(**kwargs)
    assert result is expected, (
        f"{test_id}: expected is_individual={expected}, got {result} with {kwargs}"
    )


class TestNameSuggestsCompany:
    """Unit tests for _name_suggests_company helper (consolidated from test_is_individual.py)."""

    def test_none_name(self):
        assert _name_suggests_company(None) is False

    def test_empty_name(self):
        assert _name_suggests_company("") is False

    def test_loose_keyword(self):
        assert _name_suggests_company("ACME CORPORATION") is True

    def test_strict_keyword_co(self):
        assert _name_suggests_company("STANDARD OIL CO") is True

    def test_strict_keyword_not_substring(self):
        assert _name_suggests_company("SCOTT JOHNSON") is False

    def test_sec_suffix(self):
        assert _name_suggests_company("TOYOTA MOTOR CORP /ADR/") is True

    def test_individual_name(self):
        assert _name_suggests_company("JOHN SMITH") is False

    def test_case_insensitive(self):
        assert _name_suggests_company("acme inc") is True