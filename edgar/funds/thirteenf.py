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
            log.info(f"Filing {filing.accession_no} does not have an information table")
            return pd.DataFrame()
            
        # Extract the information table
        infotable = thirteenf.infotable
        if infotable is None:
            log.warning(f"Could not extract information table from filing {filing.accession_no}")
            return pd.DataFrame()
            
        # Convert to DataFrame
        df = pd.DataFrame(infotable)
        
        # Clean up and organize data
        if not df.empty:
            # Update column names for consistency
            if 'nameOfIssuer' in df.columns:
                df = df.rename(columns={
                    'nameOfIssuer': 'name',
                    'titleOfClass': 'title',
                    'cusip': 'cusip',
                    'value': 'value_usd',
                    'sshPrnamt': 'shares',
                    'sshPrnamtType': 'share_type',
                    'investmentDiscretion': 'investment_discretion',
                    'votingAuthority': 'voting_authority'
                })
                
            # Add ticker mapping if possible
            try:
                from edgar.reference import cusip_ticker_mapping
                cusip_map = cusip_ticker_mapping(allow_duplicate_cusips=False)
                df['ticker'] = df['cusip'].map(cusip_map.Ticker)
            except Exception as e:
                log.warning(f"Error adding ticker mappings: {e}")
                df['ticker'] = None
            
            # Calculate percent of portfolio
            if 'value_usd' in df.columns:
                total_value = df['value_usd'].sum()
                if total_value > 0:
                    df['pct_value'] = df['value_usd'] / total_value * 100
                else:
                    df['pct_value'] = 0
                    
            # Sort by value
            df = df.sort_values('value_usd', ascending=False).reset_index(drop=True)
            
        return df
            
    except Exception as e:
        log.warning(f"Error extracting holdings from 13F filing: {e}")
    
    # Return empty DataFrame if extraction failed
    return pd.DataFrame()

# Functions for export
__all__ = [
    'ThirteenF',
    'THIRTEENF_FORMS',
    'get_thirteenf_portfolio',
]