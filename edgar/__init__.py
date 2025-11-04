# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
import re
from functools import lru_cache, partial
from typing import List, Optional, Union

from edgar._filings import Attachment, Attachments, Filing, FilingHeader, FilingHomepage, Filings, get_by_accession_number, get_by_accession_number_enriched, get_filings
from edgar.core import CAUTION, CRAWL, NORMAL, edgar_mode, get_identity, listify, set_identity
from edgar.current_filings import CurrentFilings, get_all_current_filings, get_current_filings, iter_current_filings_pages
from edgar.entity import (
    Company,
    CompanyData,
    CompanyFiling,
    CompanyFilings,
    CompanySearchResults,
    Entity,
    EntityData,
    find_company,
    get_cik_lookup_data,
    get_company_facts,
    get_company_tickers,
    get_entity,
    get_entity_submissions,
    get_icon_from_ticker,
    get_ticker_to_cik_lookup,
)
from edgar.files import detect_page_breaks, mark_page_breaks
from edgar.files.html import Document
from edgar.financials import Financials, MultiFinancials
from edgar.funds import FundClass, FundCompany, FundSeries, find_fund
from edgar.funds.reports import NPORT_FORMS, FundReport
from edgar.storage import download_edgar_data, download_filings, is_using_local_storage, set_local_storage_path, use_local_storage
from edgar.storage_management import (
    StorageAnalysis,
    StorageInfo,
    analyze_storage,
    availability_summary,
    check_filing,
    check_filings_batch,
    cleanup_storage,
    clear_cache,
    optimize_storage,
    storage_info,
)
from edgar.thirteenf import THIRTEENF_FORMS, ThirteenF
from edgar.xbrl import XBRL

# Fix for Issue #457: Clear locale-corrupted cache files on first import
# This is a one-time operation that only runs if the marker file doesn't exist
try:
    from edgar.httpclient import clear_locale_corrupted_cache
    clear_locale_corrupted_cache()
except Exception:
    # Silently continue if cache clearing fails - it's not critical
    pass

# Another name for get_current_filings
get_latest_filings = get_current_filings
latest_filings = get_current_filings
current_filings = get_current_filings

# Fund portfolio report filings
get_fund_portfolio_filings = partial(get_filings, form=NPORT_FORMS)

# Restricted stock sales
get_restricted_stock_filings = partial(get_filings, form=[144])

# Insider transaction filings
get_insider_transaction_filings = partial(get_filings, form=[3, 4, 5])

# 13F filings - portfolio holdings
get_portfolio_holding_filings = partial(get_filings, form=THIRTEENF_FORMS)


@lru_cache(maxsize=16)
def find(search_id: Union[str, int]) -> Optional[Union[Filing, Entity, CompanySearchResults, FundCompany, FundClass, FundSeries]]:
    """This is an uber search function that can take a variety of search ids and return the appropriate object
        - accession number -> returns a Filing
        - CIK -> returns an Entity
        - Class/Contract ID -> returns a FundClass
        - Series ID -> returns a FundSeries
        - Ticker -> returns a Company or a Fund if the ticker is a fund ticker
        - Company name -> returns CompanySearchResults

    :type: object
    """
    if isinstance(search_id, int):
        return Entity(search_id)
    elif re.match(r"\d{10}-\d{2}-\d{6}", search_id):
        return get_by_accession_number_enriched(search_id)
    elif re.match(r"^\d{18}$", search_id): # accession number with no dashes
        accession_number = search_id[:10] + "-" + search_id[10:12] + "-" + search_id[12:]
        return get_by_accession_number_enriched(accession_number)
    elif re.match(r"\d{4,10}$", search_id):
        return Entity(search_id)
    elif re.match(r"^[A-WYZ]{1,5}([.-][A-Z])?$", search_id):  # Ticker (including dot or hyphenated)
        return Entity(search_id)
    elif re.match(r"^[A-Z]{4}X$", search_id):  # Mutual Fund Ticker
        return find_fund(search_id)
    elif re.match(r"^[CS]\d+$", search_id):
        return find_fund(search_id)
    elif re.match(r"^\d{6,}-", search_id):
        # Probably an invalid accession number
        return None
    else:
        return find_company(search_id)


def matches_form(sec_filing: Filing,
                 form: Union[str, List[str]]) -> bool:
    """Check if the filing matches the forms"""
    form_list = listify(form)
    if sec_filing.form in form_list + [f"{f}/A" for f in form_list]:
        return True
    return False


class DataObjectException(Exception):

    def __init__(self, filing: Filing):
        self.message = f"Could not create a data object for Form {filing.form} filing: {filing.accession_no}"
        super().__init__(self.message)


def get_obj_info(form: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Get information about whether a form type has a structured data object.

    Args:
        form: The form type (e.g., '10-K', 'C', '8-K')

    Returns:
        Tuple of (has_obj, obj_type_name, description):
        - has_obj: Whether this form type has a structured data object
        - obj_type_name: The class name of the data object (e.g., 'TenK', 'FormC')
        - description: Brief description of what the object contains
    """
    # Normalize form to handle amendments (e.g., 'C/A' -> 'C')
    base_form = form.split('/')[0]

    # Map of form types to (class_name, description)
    form_map = {
        '6-K': ('CurrentReport', 'current report with event details'),
        '8-K': ('EightK', 'current report with event details'),
        '10-Q': ('TenQ', 'quarterly report with financials'),
        '10-K': ('TenK', 'annual report with financials'),
        '20-F': ('TwentyF', 'foreign issuer annual report'),
        '13F-HR': ('ThirteenF', 'institutional holdings'),
        '13F-HR/A': ('ThirteenF', 'institutional holdings'),
        '144': ('Form144', 'restricted stock sale notice'),
        'MA-I': ('MunicipalAdvisorForm', 'municipal advisor registration'),
        '3': ('Form3', 'initial insider ownership'),
        '4': ('Form4', 'insider transaction'),
        '5': ('Form5', 'annual insider transaction summary'),
        'EFFECT': ('Effect', 'effectiveness notice'),
        'D': ('FormD', 'private placement offering'),
        'C': ('FormC', 'crowdfunding offering details'),
        'C-U': ('FormC', 'crowdfunding progress update'),
        'C-AR': ('FormC', 'crowdfunding annual report'),
        'C-TR': ('FormC', 'crowdfunding termination'),
        'NPORT-P': ('FundReport', 'fund portfolio holdings'),
        'NPORT-EX': ('FundReport', 'fund portfolio holdings'),
    }

    if base_form in form_map:
        class_name, description = form_map[base_form]
        return (True, class_name, description)

    # Forms not in map might still have XBRL
    return (False, None, None)


def obj(sec_filing: Filing) -> Optional[object]:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing, but it can also come from the extracted xbrl
    :param sec_filing: The filing
    :return:
    """
    from edgar.company_reports import CurrentReport, EightK, TenK, TenQ, TwentyF
    from edgar.effect import Effect
    from edgar.form144 import Form144
    from edgar.muniadvisors import MunicipalAdvisorForm
    from edgar.offerings import FormC, FormD
    from edgar.ownership import Form3, Form4, Form5, Ownership

    if matches_form(sec_filing, "6-K"):
        return CurrentReport(sec_filing)
    if matches_form(sec_filing, "8-K"):
        return EightK(sec_filing)
    elif matches_form(sec_filing, "10-Q"):
        return TenQ(sec_filing)
    elif matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif matches_form(sec_filing, "20-F"):
        return TwentyF(sec_filing)
    elif matches_form(sec_filing, THIRTEENF_FORMS):
        # ThirteenF can work with either XML (2013+) or TXT (2012 and earlier) format
        return ThirteenF(sec_filing)
    elif matches_form(sec_filing, "144"):
        return Form144.from_filing(sec_filing)
    elif matches_form(sec_filing, "MA-I"):
        return MunicipalAdvisorForm.from_filing(sec_filing)
    elif matches_form(sec_filing, "3"):
        xml = sec_filing.xml()
        if xml:
            return Form3(**Ownership.parse_xml(xml))
    elif matches_form(sec_filing, "4"):
        xml = sec_filing.xml()
        if xml:
            return Form4(**Ownership.parse_xml(xml))
    elif matches_form(sec_filing, "5"):
        xml = sec_filing.xml()
        if xml:
            return Form5(**Ownership.parse_xml(xml))
    elif matches_form(sec_filing, "EFFECT"):
        xml = sec_filing.xml()
        if xml:
            return Effect.from_xml(xml)
    elif matches_form(sec_filing, "D"):
        xml = sec_filing.xml()
        if xml:
            return FormD.from_xml(xml)
    elif matches_form(sec_filing, ["C", "C-U", "C-AR", "C-TR"]):
        return FormC.from_filing(sec_filing)

    elif matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
        return FundReport.from_filing(sec_filing)

    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl
