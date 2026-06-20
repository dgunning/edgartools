"""
13F filing module for investment funds.

This module provides classes and functions for working with 13F filings
that report investment fund portfolio holdings.
"""
import logging

import pandas as pd

# Define constants
THIRTEENF_FORMS = ['13F-HR', "13F-HR/A", "13F-NT", "13F-NT/A", "13F-CTR", "13F-CTR/A"]

log = logging.getLogger(__name__)

# We'll define these functions without directly importing them at the module level
# to avoid circular imports

def get_ThirteenF():
    """Dynamically import ThirteenF to avoid circular imports."""
    from edgar.thirteenf import ThirteenF as OriginalThirteenF
    return OriginalThirteenF

# Create property-like functions that provide lazy loading
def ThirteenF():
    """Get the ThirteenF class, dynamically importing it to avoid circular imports."""
    return get_ThirteenF()

def get_thirteenf_portfolio(filing) -> pd.DataFrame:
    """
    Extract portfolio holdings from a 13F filing.

    Args:
        filing: The 13F filing to extract data from

    Returns:
        DataFrame containing portfolio holdings
    """
    try:
        # Create a ThirteenF from the filing
        thirteenf_class = get_ThirteenF()
        thirteenf = thirteenf_class(filing, use_latest_period_of_report=True)

        # Check if the filing has an information table
        if not thirteenf.has_infotable():
            log.info("Filing %s does not have an information table", filing.accession_no)
            return pd.DataFrame()

        # Extract the information table
        infotable = thirteenf.infotable
        if infotable is None:
            log.warning("Could not extract information table from filing %s", filing.accession_no)
            return pd.DataFrame()

        # Convert to DataFrame. The infotable already uses the canonical PascalCase
        # schema (Issuer, Class, Cusip, Value, SharesPrnAmount, ..., Ticker) for
        # every parse path (XML and legacy TXT) — see edgar/thirteenf/parsers/.
        # There is a single canonical schema; do not re-alias columns. (edgartools-i5wx)
        df = pd.DataFrame(infotable)

        if not df.empty and 'Value' in df.columns:
            # Percent of portfolio, then sort by value (most concentrated first).
            total_value = df['Value'].sum()
            df['pct_value'] = (df['Value'] / total_value * 100) if total_value > 0 else 0
            df = df.sort_values('Value', ascending=False).reset_index(drop=True)

        return df

    except Exception as e:
        log.warning("Error extracting holdings from 13F filing: %s", e)

    # Return empty DataFrame if extraction failed
    return pd.DataFrame()

# Functions for export
__all__ = [
    'ThirteenF',
    'THIRTEENF_FORMS',
    'get_thirteenf_portfolio',
]
