"""
Entity module for the EdgarTools library.

This module provides the Entity, Company, Fund, and related classes
for working with SEC filers.
"""
from edgar.entity.core import (
    SecFiler,
    Entity, 
    Company,
    get_entity, 
    get_company,
)

from edgar.entity.data import (
    Address,
    EntityData,
    CompanyData
)

# Import from the funds package instead of entity.funds
from edgar.funds import (
    FundData,
    FundSeries
)

from edgar.entity.filings import (
    EntityFiling,
    EntityFilings
)

from edgar.entity.facts import (
    EntityFacts,
    CompanyFacts,
    NoCompanyFactsFound,
    Fact,
    Concept,
    CompanyConcept,
    get_company_facts,
    get_concept
)

from edgar.entity.search import (
    find_company,
    CompanySearchResults,
    CompanySearchIndex
)

from edgar.entity.tickers import (
    get_icon_from_ticker,
    get_company_tickers,
    get_ticker_to_cik_lookup,
    get_cik_lookup_data,
    find_cik,
    find_ticker
)

from edgar.entity.submissions import (
    get_entity_submissions,
    download_entity_submissions_from_sec,
    create_entity_from_submissions_json,
    create_entity_from_file,
    create_company_from_file
)

# Import for backward compatibility
from edgar.entity.core import public_companies

# Aliases for backward compatibility
CompanyFiling = EntityFiling
CompanyFilings = EntityFilings

__all__ = [
    # Core classes
    'SecFiler',
    'Entity',
    'Company',
    'FundSeries',
    
    # Data classes
    'EntityData',
    'CompanyData',
    'FundData',
    'Address',
    
    # Filing classes
    'EntityFiling',
    'EntityFilings',
    'EntityFacts',
    
    # Fact classes
    'Fact',
    'Concept',
    'CompanyConcept',
    
    # Factory functions
    'get_entity',
    'get_company',
    'public_companies',
    
    # Search functions
    'find_company',
    'CompanySearchResults',
    'CompanySearchIndex',
    
    # Ticker functions
    'get_icon_from_ticker',
    'get_company_tickers',
    'get_ticker_to_cik_lookup',
    'get_cik_lookup_data',
    'find_cik',
    'find_ticker',
    
    # Submission functions
    'get_entity_submissions',
    'download_entity_submissions_from_sec',
    'create_entity_from_submissions_json',
    'create_entity_from_file',
    'create_company_from_file',
    
    # Fact functions
    'get_company_facts',
    'get_concept',
    
    # Exceptions
    'NoCompanyFactsFound',
    
    # Backwards compatibility
    'CompanyFiling',
    'CompanyFilings',
    'CompanyFacts'
]