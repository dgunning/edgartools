"""
Entity module for the EdgarTools library.

This module provides the Entity, Company, Fund, and related classes
for working with SEC filers.
"""
# Import for backward compatibility
from edgar.entity.constants import COMPANY_FORMS
from edgar.entity.core import (
    Company,
    CompanyNotFoundError,
    Entity,
    PredecessorHistoryWarning,
    SecFiler,
    get_company,
    get_entity,
    public_companies,
)
from edgar.entity.data import Address, CompanyData, EntityData, parse_entity_submissions
from edgar.entity.entity_facts import (
    EntityFacts,
    CompanyFactsNotFoundError,
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
from edgar.entity.utils import has_company_filings, normalize_cik

# FundData and FundSeries live in edgar.funds and are re-exported here on first
# access (PEP 562), not imported at module level. edgar.funds.core needs
# edgar.entity.core.Entity to define its classes, so a cold `import edgar.funds`
# loads this package mid-way through edgar.funds; an eager import of edgar.funds
# here then read the half-built module and raised ImportError. The package
# init's eager imports hid that until 6.1 made `import edgar` lazy (edgartools-y4puq.5).
_FUNDS_REEXPORTS = ('FundData', 'FundSeries')


def __getattr__(name):
    if name in _FUNDS_REEXPORTS:
        import edgar.funds
        value = getattr(edgar.funds, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Aliases for backward compatibility
CompanyFiling = EntityFiling
CompanyFilings = EntityFilings

__all__ = [
    # Core classes
    'SecFiler',
    'Entity',
    'Company',
    'PredecessorHistoryWarning',
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
    'parse_entity_submissions',

    # Fact functions
    'get_company_facts',

    # Exceptions
    'CompanyNotFoundError',
    'CompanyFactsNotFoundError',

    # Constants and utilities
    'COMPANY_FORMS',
    'has_company_filings',
    'normalize_cik',

    # Backwards compatibility
    'CompanyFiling',
    'CompanyFilings',
]
