"""
Entity module for the EdgarTools library.

This module provides the Entity, Company, Fund, and related classes
for working with SEC filers.
"""
# Import for backward compatibility
from edgar.entity.constants import COMPANY_FORMS
from edgar.entity.core import (
    Company,
    Entity,
    SecFiler,
    get_company,
    get_entity,
    public_companies,
)
from edgar.entity.utils import has_company_filings, normalize_cik
from edgar.entity.data import Address, CompanyData, EntityData
from edgar.entity.entity_facts import (
    EntityFacts,
    NoCompanyFactsFound,
    get_company_facts,
)
from edgar.entity.filings import EntityFiling, EntityFilings
from edgar.entity.search import CompanySearchIndex, CompanySearchResults, find_company
from edgar.entity.submissions import (
    create_company_from_file,
    create_entity_from_file,
    create_entity_from_submissions_json,
    download_entity_submissions_from_sec,
    get_entity_submissions,
)
from edgar.entity.tickers import find_cik, find_ticker, get_cik_lookup_data, get_company_tickers, get_icon_from_ticker, get_ticker_to_cik_lookup

# Import from the funds package instead of entity.funds
from edgar.funds import FundData, FundSeries

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

    # Exceptions
    'NoCompanyFactsFound',

    # Constants and utilities
    'COMPANY_FORMS',
    'has_company_filings',
    'normalize_cik',

    # Backwards compatibility
    'CompanyFiling',
    'CompanyFilings',
]
