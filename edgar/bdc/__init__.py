"""
BDC (Business Development Company) module for EdgarTools.

Business Development Companies (BDCs) are closed-end investment companies
that invest in small and mid-sized private companies. They are regulated
under the Investment Company Act of 1940 and file with the SEC using
file numbers starting with "814-".

Key Features:
- Access the authoritative SEC BDC Report listing all BDCs
- Search for BDCs by name or ticker with fuzzy matching
- Check if a company is a BDC via CIK lookup
- Get lists of active BDCs
- Parse individual portfolio investments from Schedule of Investments
- Access SEC DERA bulk data sets for cross-BDC analysis

Example usage:
    >>> from edgar.bdc import get_bdc_list, find_bdc, is_bdc_cik
    >>> bdcs = get_bdc_list()
    >>> len(bdcs)
    176
    >>> is_bdc_cik(1287750)  # ARCC (Ares Capital)
    True

    # Search for BDCs by name
    >>> results = find_bdc("Ares")
    >>> results[0].name
    'ARES CAPITAL CORP'

    # Search by ticker
    >>> results = find_bdc("MAIN")
    >>> results[0].name
    'MAIN STREET CAPITAL CORP'

    # Get portfolio investments
    >>> arcc = bdcs.get_by_ticker("ARCC")
    >>> investments = arcc.portfolio_investments()
    >>> len(investments)
    1256

    # Bulk analysis with DERA data sets
    >>> from edgar.bdc import fetch_bdc_dataset
    >>> dataset = fetch_bdc_dataset(2024, 3)
    >>> dataset.soi.groupby('industry')['fair_value'].sum()
"""
from edgar.bdc.datasets import (
    BDCDataset,
    ScheduleOfInvestmentsData,
    fetch_bdc_dataset,
    fetch_bdc_dataset_monthly,
    get_available_quarters,
    list_bdc_datasets,
)
from edgar.bdc.investments import (
    DataQuality,
    PortfolioInvestment,
    PortfolioInvestments,
)
from edgar.bdc.reference import (
    BDCEntities,
    BDCEntity,
    fetch_bdc_report,
    get_active_bdc_ciks,
    get_bdc_list,
    get_latest_bdc_report_year,
    is_bdc_cik,
)
from edgar.bdc.search import (
    BDCSearchIndex,
    BDCSearchResults,
    find_bdc,
)

__all__ = [
    # Data sets (DERA bulk extracts)
    'BDCDataset',
    'ScheduleOfInvestmentsData',
    'fetch_bdc_dataset',
    'fetch_bdc_dataset_monthly',
    'get_available_quarters',
    'list_bdc_datasets',
    # Reference data
    'BDCEntities',
    'BDCEntity',
    'fetch_bdc_report',
    'get_active_bdc_ciks',
    'get_bdc_list',
    'get_latest_bdc_report_year',
    'is_bdc_cik',
    # Investments
    'DataQuality',
    'PortfolioInvestment',
    'PortfolioInvestments',
    # Search
    'BDCSearchIndex',
    'BDCSearchResults',
    'find_bdc',
]
