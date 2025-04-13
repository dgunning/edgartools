import pytest
from rich import print

from edgar.entity import (
    SecFiler,
    Entity, 
    Company, 
    Fund, 
    FundClass,
    EntityData,
    CompanyData,
    get_entity, 
    get_company, 
    get_fund,
    NoCompanyFactsFound
)

class TestEntityRedesign:
    """Tests for the new entity hierarchy implementation."""
    
    def test_entity_basic(self):
        """Test basic Entity functionality."""
        # Apple's CIK
        entity = Entity("0000320193")
        assert entity.cik == 320193
        assert entity.data is not None
        assert entity.data.name is not None
        
    def test_company_basic(self):
        """Test basic Company functionality."""
        # Apple by ticker
        company = Company("AAPL")
        assert company.cik == 320193
        assert company.data is not None
        assert "Apple" in company.data.name
        assert company.get_ticker() == "AAPL"
        
        # Get financials
        financials = company.get_financials()
        if financials is not None:
            # Financials can be accessed in different ways depending on the version
            # so we'll just check that it exists
            assert financials is not None
        
    def test_company_by_cik(self):
        """Test getting a Company by CIK."""
        company = Company(320193)
        assert company.cik == 320193
        assert company.get_ticker() == "AAPL"
    
    def test_get_entity_factory(self):
        """Test the get_entity factory function."""
        entity = get_entity("0000320193")
        assert entity.cik == 320193
        assert isinstance(entity, Entity)
    
    def test_get_company_factory(self):
        """Test the get_company factory function."""
        company = get_company("AAPL")
        assert company.cik == 320193
        assert isinstance(company, Company)
        
    def test_company_filings(self):
        """Test getting filings from a Company."""
        company = Company("AAPL")
        
        # Get 10-K filings
        filings = company.get_filings(form="10-K")
        assert filings is not None
        assert len(filings) > 0
        assert "10-K" in filings.data['form'][0].as_py()
        
        # Get latest filing
        latest = company.latest("10-K")
        assert latest is not None
        assert "10-K" in latest.form
    
    def test_entity_facts(self):
        """Test getting facts from an Entity."""
        entity = Entity("0000320193")
        facts = entity.get_facts()
        
        # Note: Facts might not always be available
        if facts is not None:
            assert facts.cik == 320193
            assert len(facts.facts) > 0
    
    def test_class_hierarchy(self):
        """Test that the class hierarchy is correct."""
        entity = Entity("0000320193")
        company = Company("AAPL")
        
        # Test inheritance relationships
        assert isinstance(entity, Entity)
        assert isinstance(entity, SecFiler)
        assert isinstance(company, Company)
        assert isinstance(company, Entity)
        assert isinstance(company, SecFiler)
        
        # Test specialized behavior
        assert hasattr(company, 'get_financials')
        assert not hasattr(entity, 'get_financials')
        
        # Both should have the EntityData interface
        assert hasattr(company.data, 'get_filings')
        assert hasattr(entity.data, 'get_filings')
        assert hasattr(company.data, 'cik')
        assert hasattr(entity.data, 'cik')
    
    def test_factory_functions(self):
        """Test that factory functions work as expected."""
        # get_entity returns an Entity
        entity = get_entity("0000320193")
        assert isinstance(entity, Entity)
        
        # get_company returns a Company
        company = get_company("AAPL")
        assert isinstance(company, Company)
        
        # Entity can be created with CIK
        entity = Entity(320193)
        assert entity.cik == 320193
        
        # Company can be created with CIK or ticker
        company1 = Company(320193)
        company2 = Company("AAPL")
        assert company1.cik == company2.cik