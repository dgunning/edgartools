"""
Ticker resolution service for ETF/Fund holdings.

This module provides services for resolving ticker symbols from various identifiers
like CUSIP, ISIN, and company names, addressing GitHub issue #418.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from edgar.core import log
from edgar.reference.tickers import get_ticker_from_cusip

__all__ = ['TickerResolutionResult', 'TickerResolutionService']


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
    @lru_cache(maxsize=1000)
    def resolve_ticker(ticker: Optional[str] = None,
                      cusip: Optional[str] = None,
                      isin: Optional[str] = None,
                      company_name: Optional[str] = None) -> TickerResolutionResult:
        """
        Main resolution entry point

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
                confidence=TickerResolutionService.CONFIDENCE_SCORES['direct']
            )

        # 2. CUSIP-based resolution
        if cusip:
            resolved_ticker = TickerResolutionService._resolve_via_cusip(cusip)
            if resolved_ticker:
                return TickerResolutionResult(
                    ticker=resolved_ticker,
                    method='cusip',
                    confidence=TickerResolutionService.CONFIDENCE_SCORES['cusip']
                )

        # 3. Future: ISIN-based resolution
        # if isin:
        #     resolved_ticker = TickerResolutionService._resolve_via_isin(isin)
        #     ...

        # 4. Future: Name-based resolution
        # if company_name:
        #     resolved_ticker = TickerResolutionService._resolve_via_name(company_name)
        #     ...

        return TickerResolutionResult(
            ticker=None,
            method='failed',
            confidence=0.0,
            error_message='No resolution methods succeeded'
        )

    @staticmethod
    def _resolve_via_cusip(cusip: str) -> Optional[str]:
        """Resolve ticker using CUSIP mapping"""
        try:
            if not cusip or len(cusip.strip()) < 8:
                return None

            cusip = cusip.strip().upper()
            ticker = get_ticker_from_cusip(cusip)
            if ticker:
                return ticker.upper()

        except Exception as e:
            log.warning(f"CUSIP ticker resolution failed for {cusip}: {e}")

        return None