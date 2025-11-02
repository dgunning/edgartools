"""Portfolio manager lookup functionality for 13F filings."""

import json
from functools import lru_cache
from pathlib import Path

__all__ = [
    'lookup_portfolio_managers',
    'is_filing_signer_likely_portfolio_manager',
]


def lookup_portfolio_managers(company_name: str, cik: int = None, include_approximate: bool = False) -> list[dict]:
    """
    Lookup portfolio managers for a given company.

    This uses a curated database of well-known fund managers loaded from an external JSON file.
    The data is compiled from public sources and may not be complete or current.

    Args:
        company_name: Company name to search for
        cik: Optional CIK for more accurate matching
        include_approximate: If True, includes non-active managers

    Returns:
        list[dict]: List of portfolio manager information
    """
    try:
        db = _load_portfolio_manager_db()

        # Try CIK-based search first (more accurate)
        if cik:
            managers = _search_manager_database_by_cik(db, cik, include_approximate)
            if managers:
                return managers

        # Fallback to name-based search
        return _search_manager_database(db, company_name, include_approximate)
    except Exception as e:
        # Fallback to empty list if database loading fails
        import warnings
        warnings.warn(f"Could not load portfolio manager database: {e}")
        return []


@lru_cache(maxsize=1)
def _load_portfolio_manager_db() -> dict:
    """
    Load the portfolio manager database from external JSON file.

    Returns:
        dict: The loaded database, or empty dict if file not found
    """
    # Try to load from external JSON file
    data_file = Path(__file__).parent.parent / 'reference' / 'data' / 'portfolio_managers.json'

    if data_file.exists():
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            import warnings
            warnings.warn(f"Could not parse portfolio manager database: {e}")
            return {}
    else:
        # Fallback to basic hardcoded database for backwards compatibility
        return {
            "metadata": {
                "version": "fallback",
                "description": "Minimal fallback database",
                "total_companies": 3,
                "last_updated": "2024-12-01"
            },
            "managers": {
                "berkshire_hathaway": {
                    "company_name": "Berkshire Hathaway Inc",
                    "match_patterns": ["berkshire hathaway", "brk", "berkshire"],
                    "managers": [
                        {
                            "name": "Warren Buffett",
                            "title": "Chairman & CEO",
                            "status": "active",
                            "confidence": "high",
                            "last_verified": "2024-12-01"
                        }
                    ]
                }
            }
        }


def _search_manager_database(db: dict, company_name: str, include_approximate: bool = False) -> list[dict]:
    """
    Search the manager database for a company.

    Args:
        db: The loaded database dictionary
        company_name: Company name to search for
        include_approximate: Whether to include non-active managers

    Returns:
        list[dict]: List of matching managers
    """
    if not db or 'managers' not in db:
        return []

    managers_data = db['managers']
    normalized_name = company_name.lower()

    # Search through all companies
    for company_key, company_data in managers_data.items():
        # Check match patterns
        match_patterns = company_data.get('match_patterns', [company_key])

        for pattern in match_patterns:
            if pattern.lower() in normalized_name:
                managers = company_data.get('managers', [])

                if include_approximate:
                    return managers
                else:
                    # Only return active managers unless requested otherwise
                    return [m for m in managers if m.get('status') == 'active']

    # No matches found
    return []


def _search_manager_database_by_cik(db: dict, cik: int, include_approximate: bool = False) -> list[dict]:
    """
    Search the manager database by CIK (more accurate than name matching).

    Args:
        db: The loaded database dictionary
        cik: The CIK to search for
        include_approximate: Whether to include non-active managers

    Returns:
        list[dict]: List of matching managers
    """
    if not db or 'managers' not in db:
        return []

    managers_data = db['managers']

    # Search through all companies for CIK match
    for _company_key, company_data in managers_data.items():
        company_cik = company_data.get('cik')
        if company_cik == cik:
            managers = company_data.get('managers', [])

            if include_approximate:
                return managers
            else:
                # Only return active managers unless requested otherwise
                return [m for m in managers if m.get('status') == 'active']

    # No CIK matches found
    return []


def is_filing_signer_likely_portfolio_manager(filing_signer_title: str) -> bool:
    """
    Determine if the filing signer is likely to be a portfolio manager.

    This uses heuristics based on the signer's title to assess whether they
    might be involved in investment decisions rather than just administrative functions.

    Args:
        filing_signer_title: The title of the person who signed the filing

    Returns:
        bool: True if signer appears to be investment-focused, False if administrative

    Example:
        >>> is_filing_signer_likely_portfolio_manager("Chief Financial Officer")
        False
        >>> is_filing_signer_likely_portfolio_manager("Portfolio Manager")
        True
    """
    if not filing_signer_title:
        return False

    title = filing_signer_title.upper()

    # Investment-focused titles
    investment_titles = [
        'PORTFOLIO MANAGER', 'FUND MANAGER', 'INVESTMENT MANAGER',
        'CHIEF INVESTMENT OFFICER', 'CIO', 'MANAGING DIRECTOR',
        'CHAIRMAN', 'CEO', 'PRESIDENT', 'FOUNDER'
    ]

    # Administrative titles
    admin_titles = [
        'CFO', 'CCO', 'COMPLIANCE', 'SECRETARY', 'TREASURER',
        'VICE PRESIDENT', 'VP', 'ASSISTANT', 'COUNSEL'
    ]

    # Check for investment titles first
    for inv_title in investment_titles:
        if inv_title in title:
            return True

    # Check for administrative titles
    for admin_title in admin_titles:
        if admin_title in title:
            return False

    # If unclear, err on the side of caution
    return False
