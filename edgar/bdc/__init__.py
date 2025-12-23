"""
BDC (Business Development Company) module for EdgarTools.

Business Development Companies (BDCs) are closed-end investment companies
that invest in small and mid-sized private companies. They are regulated
under the Investment Company Act of 1940 and file with the SEC using
file numbers starting with "814-".

Key Features:
- Access the authoritative SEC BDC Report listing all BDCs
- Check if a company is a BDC via CIK lookup
- Get lists of active BDCs

Example usage:
    >>> from edgar.bdc import get_bdc_list, is_bdc_cik
    >>> bdcs = get_bdc_list()
    >>> len(bdcs)
    176
    >>> is_bdc_cik(1287750)  # ARCC (Ares Capital)
    True
"""
from edgar.bdc.reference import (
    BDCEntities,
    BDCEntity,
    fetch_bdc_report,
    get_active_bdc_ciks,
    get_bdc_list,
    get_latest_bdc_report_year,
    is_bdc_cik,
)

__all__ = [
    'BDCEntities',
    'BDCEntity',
    'fetch_bdc_report',
    'get_active_bdc_ciks',
    'get_bdc_list',
    'get_latest_bdc_report_year',
    'is_bdc_cik',
]
