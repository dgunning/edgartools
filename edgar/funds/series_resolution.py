"""
Series resolution service for ETF/Fund ticker-to-series mapping.

This module provides services for resolving ticker symbols to series IDs,
addressing GitHub issue #417.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from edgar.core import log

__all__ = ['SeriesInfo', 'TickerSeriesResolver']


@dataclass
class SeriesInfo:
    """Information about a fund series"""
    series_id: str
    series_name: Optional[str]
    ticker: str
    class_id: Optional[str] = None
    class_name: Optional[str] = None


class TickerSeriesResolver:
    """Handles ticker to series ID resolution with caching."""

    @staticmethod
    @lru_cache(maxsize=1000)
    def resolve_ticker_to_series(ticker: str) -> List[SeriesInfo]:
        """Resolve ticker to all associated series with ETF fallback."""
        if not ticker:
            return []

        try:
            # First try mutual fund data (original behavior)
            from edgar.reference.tickers import get_mutual_fund_tickers
            mf_data = get_mutual_fund_tickers()

            # Find all matches for this ticker
            matches = mf_data[mf_data['ticker'].str.upper() == ticker.upper()]

            series_list = []
            for _, row in matches.iterrows():
                series_info = SeriesInfo(
                    series_id=row['seriesId'],
                    series_name=None,  # Not available in the ticker data
                    ticker=row['ticker'],
                    class_id=row['classId']
                )
                series_list.append(series_info)

            # If found in mutual fund data, return those results
            if series_list:
                return series_list

            # NEW: Fallback to company ticker data for ETFs
            log.debug(f"Ticker {ticker} not found in mutual fund data, trying company data...")

            from edgar.reference.tickers import find_cik, get_company_tickers
            cik = find_cik(ticker)

            if cik:
                # Found as company ticker - likely an ETF
                company_data = get_company_tickers()
                company_matches = company_data[
                    (company_data['ticker'].str.upper() == ticker.upper()) &
                    (company_data['cik'] == cik)
                ]

                if len(company_matches) > 0:
                    company_match = company_matches.iloc[0]
                    # Create synthetic series info for ETF
                    etf_series = SeriesInfo(
                        series_id=f"ETF_{cik}",  # Synthetic series ID for ETFs
                        series_name=company_match['company'],  # Company name as series name
                        ticker=company_match['ticker'],
                        class_id=f"ETF_CLASS_{cik}"  # Synthetic class ID
                    )
                    log.debug(f"Resolved {ticker} as ETF company with CIK {cik}")
                    return [etf_series]

            log.debug(f"Ticker {ticker} not found in either mutual fund or company data")
            return []

        except Exception as e:
            log.warning(f"Error resolving ticker {ticker} to series: {e}")
            return []

    @staticmethod
    def get_primary_series(ticker: str) -> Optional[str]:
        """Get the primary/most relevant series for a ticker."""
        series_list = TickerSeriesResolver.resolve_ticker_to_series(ticker)

        if not series_list:
            return None

        # If only one series, return it
        if len(series_list) == 1:
            return series_list[0].series_id

        # If multiple series, return the first one (could be enhanced with better logic)
        return series_list[0].series_id

    @staticmethod
    def has_multiple_series(ticker: str) -> bool:
        """Check if a ticker maps to multiple series."""
        series_list = TickerSeriesResolver.resolve_ticker_to_series(ticker)
        return len(series_list) > 1