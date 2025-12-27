"""
Filing metadata extraction utilities.

Shared helpers for extracting and formatting filing metadata (form, CIK,
company, dates, etc.) used across to_context() implementations and llm.py.
"""
from typing import Dict, Optional

__all__ = ['extract_filing_metadata']


def extract_filing_metadata(
    filing,
    *,
    include_ticker: bool = True,
    include_period: bool = False,
    include_cik_padded: bool = False
) -> Dict[str, Optional[str]]:
    """
    Extract common filing metadata fields.

    Args:
        filing: Filing object with metadata attributes
        include_ticker: Lookup ticker symbol from CIK (default: True)
        include_period: Include period_of_report if available (default: False)
        include_cik_padded: Include 10-digit zero-padded CIK (default: False)

    Returns:
        Dictionary with metadata fields:
        - form: Form type (e.g., '10-K', '10-Q')
        - accession_no: Accession number
        - filing_date: Filing date string
        - company: Company name
        - cik: CIK as string
        - ticker: Stock symbol (if include_ticker=True)
        - period: Period of report (if include_period=True)
        - cik_padded: 10-digit CIK (if include_cik_padded=True)

    Example:
        >>> from edgar import Filing
        >>> from edgar.filing_metadata import extract_filing_metadata
        >>> filing = Filing(form='10-K', cik=320193, ...)
        >>> metadata = extract_filing_metadata(filing)
        >>> print(metadata['ticker'])  # 'AAPL'
    """
    # Core metadata (always present)
    metadata = {
        'form': getattr(filing, 'form', None),
        'accession_no': getattr(filing, 'accession_no', None),
        'filing_date': getattr(filing, 'filing_date', None),
        'company': filing.company if hasattr(filing, 'company') else None,
        'cik': str(filing.cik) if hasattr(filing, 'cik') else None,
    }

    # Optional: Ticker lookup
    if include_ticker and hasattr(filing, 'cik'):
        try:
            from edgar.reference.tickers import find_ticker
            ticker = find_ticker(filing.cik)
            # Fall back to filing.ticker if find_ticker returns empty or None
            if not ticker:
                ticker = getattr(filing, 'ticker', None)
            metadata['ticker'] = ticker
        except Exception:
            # Fallback to direct ticker attribute if it exists
            metadata['ticker'] = getattr(filing, 'ticker', None)

    # Optional: Period of report
    if include_period:
        metadata['period'] = getattr(filing, 'period_of_report', None)

    # Optional: Zero-padded CIK (used in SGML)
    if include_cik_padded and hasattr(filing, 'cik'):
        metadata['cik_padded'] = str(filing.cik).zfill(10)

    return metadata
