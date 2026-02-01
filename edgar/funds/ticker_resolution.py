"""
Ticker resolution service for ETF/Fund holdings.

This module provides services for resolving ticker symbols from various identifiers
like CUSIP, ISIN, and company names, addressing GitHub issue #418.

Performance: Uses dict-based CUSIP lookups (~31x faster than the previous
DataFrame.loc approach). Placeholder CUSIPs like '000000000' are skipped
without logging since they are normal for foreign-domiciled securities.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from edgar.reference.tickers import get_ticker_from_cusip

__all__ = ['TickerResolutionResult', 'TickerResolutionService']

# CUSIPs that are known placeholders (not real identifiers)
_PLACEHOLDER_CUSIPS = frozenset({'000000000', '0' * 6, 'N/A', ''})


@dataclass
class TickerResolutionResult:
    """Result of ticker resolution attempt"""
    ticker: Optional[str]
    method: str  # 'direct', 'cusip', 'failed'
    confidence: float  # 0.0 to 1.0
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.ticker is not None and self.confidence > 0.0


# Pre-allocate the common "failed" result to avoid repeated object creation
_FAILED_RESULT = TickerResolutionResult(
    ticker=None,
    method='failed',
    confidence=0.0,
    error_message='No resolution methods succeeded'
)


class TickerResolutionService:
    """Centralized service for resolving tickers from various identifiers"""

    CONFIDENCE_SCORES = {
        'direct': 1.0,      # Direct from NPORT-P
        'cusip': 0.85,      # High confidence - official identifier
        'isin': 0.75,       # Good confidence - international identifier
        'name': 0.5,        # Lower confidence - fuzzy matching
        'failed': 0.0       # No resolution
    }

    @staticmethod
    @lru_cache(maxsize=4096)
    def resolve_ticker(ticker: Optional[str] = None,
                      cusip: Optional[str] = None,
                      isin: Optional[str] = None,
                      company_name: Optional[str] = None) -> TickerResolutionResult:
        """
        Main resolution entry point.

        Args:
            ticker: Direct ticker from NPORT-P
            cusip: CUSIP identifier
            isin: ISIN identifier (future use)
            company_name: Company name (future use)

        Returns:
            TickerResolutionResult with ticker and metadata
        """
        # 1. Direct ticker resolution
        if ticker and ticker.strip():
            return TickerResolutionResult(
                ticker=ticker.strip().upper(),
                method='direct',
                confidence=1.0
            )

        # 2. CUSIP-based resolution
        if cusip:
            resolved_ticker = TickerResolutionService._resolve_via_cusip(cusip)
            if resolved_ticker:
                return TickerResolutionResult(
                    ticker=resolved_ticker,
                    method='cusip',
                    confidence=0.85
                )

        return _FAILED_RESULT

    @staticmethod
    def _resolve_via_cusip(cusip: str) -> Optional[str]:
        """Resolve ticker using CUSIP dict lookup."""
        if not cusip or len(cusip.strip()) < 8:
            return None

        cusip = cusip.strip().upper()

        # Skip known placeholders (foreign-domiciled securities, N/A entries)
        if cusip in _PLACEHOLDER_CUSIPS:
            return None

        try:
            ticker = get_ticker_from_cusip(cusip)
            if ticker:
                return ticker.upper()
        except Exception:
            pass
        return None
