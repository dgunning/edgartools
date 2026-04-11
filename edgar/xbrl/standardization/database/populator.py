"""
Batch populator for the standardized financial database.

Extracts standardized metrics from SEC filings and stores them in SQLite.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from edgar.xbrl.standardization.database.schema import _FinancialDB, _derive_fiscal_period

log = logging.getLogger(__name__)


@dataclass
class PopulationTickerResult:
    """Result of populating a single ticker."""
    ticker: str
    filings_extracted: int = 0
    filings_skipped: int = 0
    filings_failed: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class PopulationResult:
    """Result of a batch population run."""
    tickers_attempted: int = 0
    filings_extracted: int = 0
    filings_skipped: int = 0
    filings_failed: int = 0
    errors: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def __str__(self):
        return (
            f"PopulationResult("
            f"{self.tickers_attempted} tickers | "
            f"{self.filings_extracted} extracted | "
            f"{self.filings_skipped} skipped | "
            f"{self.filings_failed} failed | "
            f"{self.elapsed_seconds:.1f}s)"
        )

    def __repr__(self):
        return self.__str__()


def populate_ticker(
    ticker: str,
    db: _FinancialDB,
    n_annual: int = 10,
    n_quarterly: int = 4,
    progress_callback=None,
) -> PopulationTickerResult:
    """
    Extract and store standardized metrics for a single company.

    Args:
        ticker: Company ticker symbol.
        db: Database instance.
        n_annual: Number of annual filings (10-K) to process.
        n_quarterly: Number of quarterly filings (10-Q) to process.
        progress_callback: Optional callable(filing_idx, total, ticker, status_msg).

    Returns:
        PopulationTickerResult with counts and errors.
    """
    from edgar import Company
    from edgar.standardized_financials import extract_standardized_financials

    result = PopulationTickerResult(ticker=ticker)

    # Collect filings to process
    filings = []
    try:
        company = Company(ticker)
    except Exception as e:
        result.errors.append(f"{ticker}: Company lookup failed: {e}")
        result.filings_failed += 1
        return result

    # Annual filings
    if n_annual > 0:
        try:
            annual = company.get_filings(form='10-K', amendments=False)
            if annual is not None and len(annual) > 0:
                annual_latest = annual.latest(n_annual)
                # latest() returns single Filing if n=1
                if hasattr(annual_latest, '__iter__') and not isinstance(annual_latest, str):
                    filings.extend(annual_latest)
                else:
                    filings.append(annual_latest)
        except Exception as e:
            result.errors.append(f"{ticker}: 10-K fetch failed: {e}")

    # Quarterly filings
    if n_quarterly > 0:
        try:
            quarterly = company.get_filings(form='10-Q', amendments=False)
            if quarterly is not None and len(quarterly) > 0:
                quarterly_latest = quarterly.latest(n_quarterly)
                if hasattr(quarterly_latest, '__iter__') and not isinstance(quarterly_latest, str):
                    filings.extend(quarterly_latest)
                else:
                    filings.append(quarterly_latest)
        except Exception as e:
            result.errors.append(f"{ticker}: 10-Q fetch failed: {e}")

    total = len(filings)
    for idx, filing in enumerate(filings):
        accession = filing.accession_number

        # Skip already-known filings
        if db.is_filing_known(accession):
            result.filings_skipped += 1
            if progress_callback:
                progress_callback(idx + 1, total, ticker, 'skipped')
            continue

        try:
            sf = extract_standardized_financials(filing, ticker)
            if sf is None:
                result.filings_failed += 1
                result.errors.append(f"{ticker}/{accession}: No XBRL data")
                if progress_callback:
                    progress_callback(idx + 1, total, ticker, 'no xbrl')
                continue

            fiscal_period = _derive_fiscal_period(filing)
            form_type = getattr(filing, 'form', '10-K')
            filing_date = getattr(filing, 'filing_date', '')
            period_of_report = getattr(filing, 'period_of_report', '') or ''
            company_name = sf.company_name

            # Count metrics with values
            metric_list = list(sf)
            mapped_count = sum(1 for m in metric_list if m.has_value)

            # Record filing
            db.record_filing(
                accession_number=accession,
                ticker=ticker,
                form_type=form_type,
                filing_date=str(filing_date),
                period_of_report=str(period_of_report),
                fiscal_period=fiscal_period,
                company_name=company_name,
                metric_count=mapped_count,
            )

            # Record metrics
            db.record_metrics(
                accession_number=accession,
                ticker=ticker,
                fiscal_period=fiscal_period,
                form_type=form_type,
                metrics=metric_list,
            )

            result.filings_extracted += 1
            if progress_callback:
                progress_callback(idx + 1, total, ticker, f'{mapped_count} metrics')

        except Exception as e:
            result.filings_failed += 1
            result.errors.append(f"{ticker}/{accession}: {e}")
            log.warning("Failed to extract %s/%s: %s", ticker, accession, e)
            if progress_callback:
                progress_callback(idx + 1, total, ticker, f'error: {e}')

    return result
