"""
Bulk Preload: Pre-download all data needed for offline auto-eval.

Downloads SEC bulk metadata and filing documents for a cohort of companies,
enabling the auto-eval pipeline to run without any network requests.

Usage:
    python -m edgar.xbrl.standardization.tools.bulk_preload
    # Or from Python:
    from edgar.xbrl.standardization.tools.bulk_preload import preload_cohort
    preload_cohort(["AAPL", "JPM", "XOM", "WMT", "JNJ"])
"""

import logging
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def preload_cohort(
    tickers: List[str],
    years: int = 3,
    forms: Optional[List[str]] = None,
    include_metadata: bool = True,
    compress: bool = True,
    disable_progress: bool = False,
) -> dict:
    """
    Download all 10-K/10-Q filings for a cohort of companies.

    Args:
        tickers: Company tickers to download.
        years: Number of years of filings to download (default 3).
        forms: Filing forms to download (default: ['10-K', '10-Q']).
        include_metadata: Also download submissions, facts, reference data.
        compress: Compress downloaded filings to save disk space.
        disable_progress: Suppress progress bars.

    Returns:
        dict with download statistics.
    """
    from edgar import Company, set_identity
    from edgar.storage._local import (
        download_edgar_data,
        download_filings,
        is_using_local_storage,
        use_local_storage,
    )

    if forms is None:
        forms = ['10-K', '10-Q']

    # Ensure local storage is enabled
    if not is_using_local_storage():
        use_local_storage(True)

    set_identity("Dev Gunning developer-gunning@gmail.com")

    stats = {
        'tickers_requested': len(tickers),
        'tickers_downloaded': 0,
        'filings_downloaded': 0,
        'errors': [],
        'metadata_downloaded': False,
        'duration_seconds': 0,
    }
    start_time = time.time()

    # Step 1: Download bulk metadata (submissions, facts, reference)
    if include_metadata:
        logger.info("Downloading bulk metadata (submissions, facts, reference)...")
        try:
            download_edgar_data(
                submissions=True,
                facts=True,
                reference=True,
                disable_progress=disable_progress,
            )
            stats['metadata_downloaded'] = True
            logger.info("Bulk metadata download complete")
        except Exception as e:
            logger.error(f"Failed to download metadata: {e}")
            stats['errors'].append(f"metadata: {e}")

    # Step 2: Download filings for each company
    max_filings = years * 5  # ~5 filings per year (annual + quarterly)

    for ticker in tickers:
        logger.info(f"Downloading filings for {ticker}...")
        try:
            company = Company(ticker)
            filings = company.get_filings(form=forms)[:max_filings]

            if len(filings) == 0:
                logger.warning(f"No filings found for {ticker}")
                continue

            download_filings(
                filings=filings,
                compress=compress,
                disable_progress=disable_progress,
            )

            stats['tickers_downloaded'] += 1
            stats['filings_downloaded'] += len(filings)
            logger.info(f"Downloaded {len(filings)} filings for {ticker}")

        except Exception as e:
            logger.error(f"Failed to download filings for {ticker}: {e}")
            stats['errors'].append(f"{ticker}: {e}")

    stats['duration_seconds'] = time.time() - start_time
    logger.info(
        f"Preload complete: {stats['tickers_downloaded']}/{stats['tickers_requested']} companies, "
        f"{stats['filings_downloaded']} filings, {stats['duration_seconds']:.0f}s"
    )
    return stats


def verify_offline_readiness(
    tickers: List[str],
    forms: Optional[List[str]] = None,
) -> dict:
    """
    Verify that all required data exists locally for offline evaluation.

    Args:
        tickers: Company tickers to verify.
        forms: Filing forms to check (default: ['10-K']).

    Returns:
        dict with readiness status per ticker and overall readiness.
    """
    from edgar import Company, set_identity
    from edgar.storage._local import (
        is_using_local_storage,
        local_filing_path,
        use_local_storage,
    )

    if forms is None:
        forms = ['10-K']

    if not is_using_local_storage():
        use_local_storage(True)

    set_identity("Dev Gunning developer-gunning@gmail.com")

    readiness = {
        'overall_ready': True,
        'tickers': {},
    }

    for ticker in tickers:
        ticker_status = {
            'ready': False,
            'filings_found': 0,
            'filings_local': 0,
            'missing': [],
        }

        try:
            company = Company(ticker)
            filings = list(company.get_filings(form=forms))[:3]
            ticker_status['filings_found'] = len(filings)

            for filing in filings:
                local_path = local_filing_path(filing.filing_date, filing.accession_no)
                if local_path.exists():
                    ticker_status['filings_local'] += 1
                else:
                    ticker_status['missing'].append(filing.accession_no)

            ticker_status['ready'] = (
                ticker_status['filings_local'] > 0
                and ticker_status['filings_local'] == ticker_status['filings_found']
            )

        except Exception as e:
            ticker_status['error'] = str(e)

        if not ticker_status['ready']:
            readiness['overall_ready'] = False

        readiness['tickers'][ticker] = ticker_status

    return readiness


# Cohort definitions (imported from auto_eval for consistency)
def _get_cohorts():
    from edgar.xbrl.standardization.tools.auto_eval import (
        QUICK_EVAL_COHORT,
        VALIDATION_COHORT,
    )
    return QUICK_EVAL_COHORT, VALIDATION_COHORT


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    quick, validation = _get_cohorts()

    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        logger.info("Full preload: validation cohort (20 companies)")
        preload_cohort(validation, years=3)
    else:
        logger.info("Quick preload: eval cohort (5 companies)")
        preload_cohort(quick, years=3)

    # Verify readiness
    readiness = verify_offline_readiness(quick)
    for ticker, status in readiness['tickers'].items():
        state = "READY" if status['ready'] else "MISSING"
        logger.info(f"  {ticker}: {state} ({status['filings_local']}/{status['filings_found']} local)")

    if readiness['overall_ready']:
        logger.info("All companies ready for offline evaluation")
    else:
        logger.warning("Some companies missing local data — run preload again")
