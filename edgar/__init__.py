# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
import logging
import re
import warnings
from functools import lru_cache, partial
from typing import List, Optional, Union

from edgar.__about__ import __version__

from edgar._filings import (
    Attachment,
    Attachments,
    Filing,
    FilingHeader,
    FilingHomepage,
    Filings,
    get_by_accession_number,
    get_by_accession_number_enriched,
    get_filings,
)
from edgar.context import HasContext, compose_context
from edgar.core import listify
from edgar.settings import CAUTION, CRAWL, NORMAL, edgar_mode, get_identity, set_identity
from edgar.exceptions import (
    AttachmentNotFoundError,
    CompanyFactsNotFoundError,
    CompanyNotFoundError,
    DataObjectError,
    EdgarError,
    FilingNotFoundError,
    IdentityNotSetError,
    NotFoundError,
    ParsingError,
    SectionNotFoundError,
    StatementNotFoundError,
    TooManyRequestsError,
    TransportError,
    ValidationError,
    warn_will_raise,
)
from edgar.current_filings import CurrentFilings, get_all_current_filings, get_current_filings, iter_current_filings_pages

# SSL diagnostic function
from edgar.diagnose_ssl import diagnose_ssl
from edgar.entity import (
    Company,
    CompanyData,
    CompanyFiling,
    CompanyFilings,
    CompanyNotFoundError,
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
from edgar.entity.entity_facts import clear_company_facts_cache
from edgar.files import detect_page_breaks, mark_page_breaks
from edgar.files.html import Document
from edgar.filesystem import is_cloud_storage_enabled, sync_to_cloud, use_cloud_storage
from edgar.financials import Financials, MultiFinancials
from edgar.funds import Fund, FundClass, FundCompany, FundSeries, find_fund, find_funds
from edgar.funds.ncen import NCEN_FORMS, FundCensus
from edgar.funds.ncsr import NCSR_FORMS, FundShareholderReport
from edgar.funds.nmfp3 import MONEY_MARKET_FORMS, NMFP2_FORMS, NMFP3_FORMS, MoneyMarketFund
from edgar.funds.prospectus497k import PROSPECTUS497K_FORMS, Prospectus497K
from edgar.funds.reports import NPORT_FORMS, FundReport
from edgar.ats import (
    ATS_N_ALL_FORMS,
    ATS_N_AMENDMENT_FORMS,
    ATS_N_FORMS,
    ATS_N_WITHDRAWAL_FORMS,
    AlternativeTradingSystem,
    AlternativeTradingSystemWithdrawal,
)
from edgar.bdc import BDCEntities, BDCEntity, get_bdc_list, get_active_bdc_ciks, is_bdc_cik

# HTTP configuration functions for runtime SSL/proxy configuration
from edgar.httpclient import configure_http, get_http_config
from edgar.npx import NPX
from edgar.paths import (
    get_anchor_cache_directory,
    get_cache_directory,
    get_claude_skills_directory,
    get_data_directory,
    get_search_cache_directory,
    get_test_directory,
    set_cache_directory,
    set_claude_skills_directory,
    set_data_directory,
    set_test_directory,
)
from edgar.proxy import PROXY_FORMS, ProxyContests, ProxyStatement, proxy_contests
from edgar.storage import (
    StorageAnalysis,
    StorageInfo,
    analyze_storage,
    availability_summary,
    check_filing,
    check_filings_batch,
    cleanup_storage,
    clear_cache,
    download_edgar_data,
    download_filings,
    is_using_datamule_storage,
    is_using_local_storage,
    optimize_storage,
    set_local_storage_path,
    storage_info,
    use_datamule_storage,
    use_local_storage,
)
from edgar.correspondence import CORRESPONDENCE_FORMS, Correspondence, CorrespondenceThread, CorrespondenceType
from edgar.search.efts import EFTSResult, EFTSSearch, search_filings
from edgar.thirteenf import THIRTEENF_FORMS, ThirteenF
from edgar.xbrl import XBRL

# Attach a NullHandler to the package-root logger so that edgartools never emits
# log output unless the application configures logging itself, per the Python
# logging HOWTO guidance for libraries (#856).  Without it, library warnings have
# no handler in their ancestry and fall back to logging.lastResort (stderr),
# which is especially harmful in MCP / stdio environments.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# One-time cache clears on first import (#457 locale-corrupted entries, #672 stale
# empty responses). Run as a single migration pass so the cache is wiped at most
# once, with markers kept outside the cache directory — one clear can never delete
# another's marker (#1051).
try:
    from edgar.httpclient import _run_import_time_cache_migrations
    _run_import_time_cache_migrations()
except Exception:
    # Silently continue if cache clearing fails - it's not critical
    pass

# Another name for get_current_filings
get_latest_filings = get_current_filings
latest_filings = get_current_filings
current_filings = get_current_filings

# Fund portfolio report filings
get_fund_portfolio_filings = partial(get_filings, form=NPORT_FORMS)

# Money market fund filings
get_money_market_filings = partial(get_filings, form=MONEY_MARKET_FORMS)

# Restricted stock sales
get_restricted_stock_filings = partial(get_filings, form=[144])

# Insider transaction filings
get_insider_transaction_filings = partial(get_filings, form=[3, 4, 5])

# 13F filings - portfolio holdings
get_portfolio_holding_filings = partial(get_filings, form=THIRTEENF_FORMS)


# ---------------------------------------------------------------------------
# The public API
# ---------------------------------------------------------------------------
#
# This list is the supported surface of `edgar`: the names covered by the
# deprecation policy, and the ones a release may not break without saying so in
# docs/upgrade/. Until it existed there was no answer to "is this part of the
# API?" other than whether the import happened to work, which made every
# removal a guess about who might be relying on what (bead edgartools-07lk.5).
#
# WHAT BEING ABSENT FROM THIS LIST MEANS TODAY. Nothing breaks. Every name that
# was importable before still is; `__all__` only governs `from edgar import *`.
# What it does say is that a name outside this list is internal, and 6.0 may
# make it private (bead edgartools-07lk.23 stages the declaration in 5.x and
# the enforcement in 6.0). If something you depend on is missing here, that is
# worth an issue before 6.0 rather than after.
#
# THREE THINGS DELIBERATELY LEFT OUT. (No count here on purpose — this line used
# to say "of 141 public names on 2026-08-10" and was 153 eleven days later, with
# nothing to catch it. `tests/issues/regression/test_public_api_surface.py`
# derives the current figures; run it with `-s` to see them.)
#
#   1. `List`, `Optional`, `Union`, `lru_cache`, `partial` — imported above for
#      annotations and never API. `from edgar import Optional` works today and
#      is an accident.
#   2. `Document`, `detect_page_breaks`, `mark_page_breaks` — these come from
#      `edgar.files`, which 6.0 removes (bead edgartools-07lk.3). `edgar.Document`
#      is the LEGACY parser and a different class from `edgar.documents.Document`;
#      no documentation teaches `from edgar import Document`, and the name
#      collides with its own replacement.
#   3. Filesystem/config plumbing (`edgar.paths`), the internal cache-clearing
#      helpers behind `clear_cache`, and lower-level variants of supported entry
#      points (`get_by_accession_number_enriched`, `get_entity_submissions`,
#      `get_cik_lookup_data`, `get_ticker_to_cik_lookup`).
#
# Submodules are not listed. `from edgar.xbrl import XBRL` works regardless of
# `__all__`; this governs the top-level namespace only.
#
# Keep it grouped rather than sorted — the grouping is the documentation of what
# the library is for, and a flat alphabetical list is not.
__all__ = [
    # -- Entry points --------------------------------------------------------
    "find", "obj",
    "get_filings", "get_by_accession_number",
    "get_current_filings", "get_all_current_filings", "iter_current_filings_pages",
    "get_latest_filings", "latest_filings", "current_filings",
    "search_filings",
    "get_entity", "find_company", "get_company_facts",
    "get_company_tickers", "get_icon_from_ticker",

    # -- Core objects --------------------------------------------------------
    "Filing", "Filings", "CurrentFilings",
    "Company", "CompanyData", "CompanyFiling", "CompanyFilings",
    "CompanySearchResults", "Entity", "EntityData",
    "Attachment", "Attachments", "FilingHomepage", "FilingHeader",
    # -- Errors (edgar.exceptions) -------------------------------------------
    # The four branches plus the concretes users need by name. Everything else
    # in the tree is importable from edgar.exceptions.
    "EdgarError",
    "TransportError", "TooManyRequestsError", "IdentityNotSetError",
    "NotFoundError", "CompanyNotFoundError", "FilingNotFoundError",
    "CompanyFactsNotFoundError", "StatementNotFoundError",
    "SectionNotFoundError", "AttachmentNotFoundError",
    "ParsingError", "DataObjectError",
    "ValidationError",
    "DataObjectException",  # deprecated alias, removed in 6.0

    # -- Financial statements ------------------------------------------------
    "Financials", "MultiFinancials", "XBRL",

    # -- Funds ---------------------------------------------------------------
    "Fund", "FundCompany", "FundClass", "FundSeries",
    "FundReport", "FundCensus", "FundShareholderReport",
    "MoneyMarketFund", "Prospectus497K",
    "find_fund", "find_funds",
    "get_fund_portfolio_filings", "get_money_market_filings",
    "get_portfolio_holding_filings",

    # -- Form-specific data objects ------------------------------------------
    "ThirteenF", "NPX",
    "ProxyStatement", "ProxyContests", "proxy_contests",
    "Correspondence", "CorrespondenceThread", "CorrespondenceType",
    "AlternativeTradingSystem", "AlternativeTradingSystemWithdrawal",
    "get_insider_transaction_filings", "get_restricted_stock_filings",

    # -- Business development companies --------------------------------------
    "BDCEntity", "BDCEntities", "get_bdc_list", "get_active_bdc_ciks", "is_bdc_cik",

    # -- Full-text search ----------------------------------------------------
    "EFTSSearch", "EFTSResult",

    # -- Identity, HTTP and diagnostics --------------------------------------
    "set_identity", "get_identity",
    "NORMAL", "CAUTION", "CRAWL",
    "configure_http", "get_http_config", "diagnose_ssl",

    # -- Local and cloud storage ---------------------------------------------
    "use_local_storage", "is_using_local_storage", "set_local_storage_path",
    "download_edgar_data", "download_filings",
    "use_cloud_storage", "is_cloud_storage_enabled", "sync_to_cloud",
    "use_datamule_storage", "is_using_datamule_storage",
    "storage_info", "StorageInfo", "analyze_storage", "StorageAnalysis",
    "cleanup_storage", "optimize_storage", "clear_cache",
    "availability_summary", "check_filing", "check_filings_batch",

    # -- Form constants ------------------------------------------------------
    "ATS_N_FORMS", "ATS_N_ALL_FORMS", "ATS_N_AMENDMENT_FORMS", "ATS_N_WITHDRAWAL_FORMS",
    "CORRESPONDENCE_FORMS", "MONEY_MARKET_FORMS",
    "NCEN_FORMS", "NCSR_FORMS", "NMFP2_FORMS", "NMFP3_FORMS", "NPORT_FORMS",
    "PROSPECTUS497K_FORMS", "PROXY_FORMS", "THIRTEENF_FORMS",
]


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
    elif re.match(r"^[A-Z]{4}X$", search_id):  # Mutual Fund Ticker
        # Checked before the ordinary-ticker branch below.  The five-letter
        # trailing X is the mutual fund convention, so it wins over the more
        # general ticker shape it would otherwise also match.
        return find_fund(search_id)
    elif re.match(r"^[A-Z]{1,5}([.-][A-Z])?$", search_id):  # Ticker (including dot or hyphenated)
        try:
            return Entity(search_id)
        except CompanyNotFoundError:
            return find_company(search_id)
    elif re.match(r"^[CS]\d+$", search_id):
        return find_fund(search_id)
    elif re.match(r"^\d{6,}-", search_id):
        # It looks like an accession number and is not one. Every other branch
        # above answers a well-formed identifier; this one only fires on input
        # that is malformed, so None here means "you typed it wrong" — which is
        # the one thing a return value cannot say.
        malformed = ValidationError(
            f"'{search_id}' is not a valid accession number.",
            parameter="search_id",
            invalid_value=search_id,
            suggestions=[
                "the format is 10 digits, 2 digits, 6 digits: 0000320193-23-000106",
                "dashes are optional — 000032019323000106 also works",
            ],
        )
        # The offending value stays on the error — which strict mode raises and
        # 6.0 will raise — but must stay out of the warning, or a script
        # validating a list of accessions warns once per bad entry.
        malformed.warning_summary = (
            "find() was given something shaped like an accession number that is "
            "not a valid accession number. The format is 10 digits, 2 digits, "
            "6 digits: 0000320193-23-000106; dashes are optional."
        )
        warn_will_raise(malformed)
        return None
    else:
        return find_company(search_id)


def matches_form(sec_filing: Filing,
                 form: Union[str, List[str]]) -> bool:
    """Check if the filing matches the forms"""
    form_list = listify(form)
    if sec_filing.form in form_list + [f"{f}/A" for f in form_list if not f.endswith("/A")]:
        return True
    return False


class DataObjectException(DataObjectError):
    """Deprecated: use edgar.exceptions.DataObjectError. Removed in 6.0.

    Kept as a subclass rather than a plain alias because this one takes a
    Filing, and DataObjectError takes primitives — edgar.exceptions imports
    nothing from edgar. It was never raised anywhere, so the constructor is
    almost certainly unused, but a name in __all__ gets the full treatment.
    """

    def __init__(self, filing: Filing):
        warnings.warn(
            "DataObjectException is deprecated and will be removed in v6.0. "
            "Use DataObjectError instead (from edgar.exceptions import DataObjectError).",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(form=filing.form, accession_no=filing.accession_no)


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
        '10-D': ('TenD', 'ABS distribution report'),
        '20-F': ('TwentyF', 'foreign issuer annual report'),
        '40-F': ('FortyF', 'Canadian MJDS annual report'),
        '13F-HR': ('ThirteenF', 'institutional holdings'),
        '13F-HR/A': ('ThirteenF', 'institutional holdings'),
        'SCHEDULE 13D': ('Schedule13D', 'beneficial ownership report (5%+ stake, active)'),
        'SC 13D': ('Schedule13D', 'beneficial ownership report (5%+ stake, active)'),
        'SCHEDULE 13G': ('Schedule13G', 'beneficial ownership report (5%+ stake, passive)'),
        'SC 13G': ('Schedule13G', 'beneficial ownership report (5%+ stake, passive)'),
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
        'N-MFP2': ('MoneyMarketFund', 'money market fund portfolio holdings'),
        'N-MFP3': ('MoneyMarketFund', 'money market fund portfolio holdings'),
        'N-CEN': ('FundCensus', 'registered investment company annual census'),
        'N-CSR': ('FundShareholderReport', 'fund shareholder report'),
        'N-CSRS': ('FundShareholderReport', 'fund shareholder report'),
        'N-PX': ('NPX', 'annual proxy voting record'),
        'DEF 14A': ('ProxyStatement', 'proxy statement with executive compensation'),
        'DEFA14A': ('ProxyStatement', 'additional proxy soliciting materials'),
        'DEFM14A': ('ProxyStatement', 'merger-related proxy statement'),
        'DEFC14A': ('ProxyStatement', 'contested proxy statement'),
        'DEFN14A': ('ProxyStatement', 'non-management definitive proxy'),
        'DFAN14A': ('ProxyStatement', 'non-management additional proxy materials'),
        'DEFR14A': ('ProxyStatement', 'revised definitive proxy'),
        'DFRN14A': ('ProxyStatement', 'revised non-management proxy'),
        'PRE 14A': ('ProxyStatement', 'preliminary proxy statement'),
        'PREC14A': ('ProxyStatement', 'preliminary contested proxy'),
        'PREN14A': ('ProxyStatement', 'preliminary non-management proxy'),
        'PREM14A': ('ProxyStatement', 'preliminary merger proxy'),
        'S-1': ('RegistrationS1', 'S-1 registration statement'),
        'S-1/A': ('RegistrationS1', 'S-1 registration statement (amendment)'),
        'F-1': ('RegistrationS1', 'F-1 foreign registration statement'),
        'F-1/A': ('RegistrationS1', 'F-1 foreign registration statement (amendment)'),
        'S-3': ('RegistrationS3', 'shelf registration statement'),
        'S-3/A': ('RegistrationS3', 'shelf registration statement (amendment)'),
        'S-3ASR': ('RegistrationS3', 'automatic shelf registration'),
        'S-3ASR/A': ('RegistrationS3', 'automatic shelf registration (amendment)'),
        'S-3D': ('RegistrationS3', 'shelf registration statement'),
        'S-3DPOS': ('RegistrationS3', 'shelf registration statement'),
        'F-3': ('RegistrationS3', 'F-3 foreign shelf registration'),
        'F-3/A': ('RegistrationS3', 'F-3 foreign shelf registration (amendment)'),
        'F-3ASR': ('RegistrationS3', 'F-3 automatic shelf registration'),
        'F-3ASR/A': ('RegistrationS3', 'F-3 automatic shelf registration (amendment)'),
        'S-4': ('RegistrationS4', 'business-combination registration statement'),
        'S-4/A': ('RegistrationS4', 'business-combination registration statement (amendment)'),
        'F-4': ('RegistrationS4', 'foreign business-combination registration statement'),
        'F-4/A': ('RegistrationS4', 'foreign business-combination registration statement (amendment)'),
        '424B1': ('Prospectus424B', 'prospectus (exchange offer / IPO)'),
        '424B2': ('Prospectus424B', 'prospectus (structured note / debt)'),
        '424B3': ('Prospectus424B', 'prospectus (resale / rights offering)'),
        '424B4': ('Prospectus424B', 'prospectus (priced IPO / shelf takedown)'),
        '424B5': ('Prospectus424B', 'prospectus (shelf takedown / ATM / PIPE)'),
        '424B7': ('Prospectus424B', 'prospectus (WKSI base update)'),
        '424B8': ('Prospectus424B', 'prospectus supplement'),
        'CORRESP': ('Correspondence', 'company-to-SEC correspondence'),
        'UPLOAD': ('Correspondence', 'SEC-to-company correspondence'),
        'DRS': ('DraftRegistrationStatement', 'draft registration statement'),
        'DRS/A': ('DraftRegistrationStatement', 'draft registration statement (amendment)'),
        'X-17A-5': ('XmlFiling', 'broker-dealer financial report'),
        'TA-1': ('XmlFiling', 'transfer agent registration'),
        'TA-2': ('XmlFiling', 'transfer agent annual report'),
        'TA-W': ('XmlFiling', 'transfer agent withdrawal'),
        'MA': ('XmlFiling', 'municipal advisor firm registration'),
        'MA-W': ('XmlFiling', 'municipal advisor withdrawal'),
        'CFPORTAL': ('XmlFiling', 'crowdfunding portal registration'),
        'SBSE': ('XmlFiling', 'security-based swap entity registration'),
        'SBSE-A': ('XmlFiling', 'security-based swap entity registration (annual)'),
        'SBSE-W': ('XmlFiling', 'security-based swap entity withdrawal'),
        'ATS-N-C': ('XmlFiling', 'ATS cessation of operations'),
        'ATS-N': ('AlternativeTradingSystem', 'alternative trading system disclosure'),
        'ATS-N-W': ('AlternativeTradingSystemWithdrawal', 'alternative trading system withdrawal'),
        '24F-2NT': ('FundFeeNotice', 'annual notice of securities sold'),
        '497K': ('Prospectus497K', 'fund summary prospectus with fees and performance'),
    }

    if base_form in form_map:
        class_name, description = form_map[base_form]
        return (True, class_name, description)

    # Forms not in map might still have XBRL
    return (False, None, None)


def _no_xml_to_parse(sec_filing: Filing) -> DataObjectError:
    """The error for a form we model whose XML we could not get.

    Built as a value rather than raised, so `warn_will_raise` can decide. It is
    also why this is not a function that *does* the warning: an extra frame
    between the warning and the user would land the `stacklevel` on our own
    source instead of on the line the reader has to change.
    """
    error = DataObjectError(
        f"Form {sec_filing.form} filing {sec_filing.accession_no} has no XML document, "
        f"so there is nothing to build a data object from. This is a property of "
        f"the filing, not of the form — ownership forms filed before roughly 2003 "
        f"predate the XML requirement.",
        form=sec_filing.form,
        accession_no=sec_filing.accession_no,
    )
    # Stable across filings so a walk through a company's whole ownership
    # history warns once, not once per pre-2003 filing — see warn_will_raise.
    error.warning_summary = (
        f"Form {sec_filing.form} filings without an XML document cannot build a "
        f"data object. This is a property of the filing, not of the form — "
        f"ownership forms filed before roughly 2003 predate the XML requirement."
    )
    return error


def obj(sec_filing: Filing) -> Optional[object]:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing, but it can also come from the extracted xbrl

    Returns:
        The data object for the filing, or `None` for a form edgartools does not
        model and whose filing carries no XBRL either. That is the only meaning
        `None` has here, and it is a statement about our coverage rather than
        about the filing.

        It is NOT how failure is reported. A form we *do* model whose data we
        could not read is a `DataObjectError` — today that path emits a
        `FutureWarning` and still returns `None`, and in 6.0 it raises. Set
        `EDGARTOOLS_STRICT_ERRORS=1` to get the 6.0 behaviour now.

    :param sec_filing: The filing
    :return:
    """
    from edgar.beneficial_ownership import Schedule13D, Schedule13G
    from edgar.company_reports import CurrentReport, EightK, SixK, TenK, TenQ, TwentyF
    from edgar.offerings.effect import Effect
    from edgar.ownership.form144 import Form144
    from edgar.muniadvisors import MunicipalAdvisorForm
    from edgar.offerings import FormC, FormD
    from edgar.ownership import Form3, Form4, Form5, Ownership

    if matches_form(sec_filing, "6-K"):
        return SixK(sec_filing)
    if matches_form(sec_filing, "8-K"):
        return EightK(sec_filing)
    elif matches_form(sec_filing, "10-Q"):
        return TenQ(sec_filing)
    elif matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif matches_form(sec_filing, "10-D"):
        # Only return TenD for CMBS filings (have EX-102 XML asset data)
        # Non-CMBS 10-D filings don't have structured data worth extracting
        attachments = sec_filing.attachments
        has_cmbs_data = any(
            a.document_type and 'EX-102' in a.document_type.upper()
            for a in attachments
        )
        if has_cmbs_data:
            from edgar.abs import TenD
            return TenD(sec_filing)
    elif matches_form(sec_filing, "20-F"):
        return TwentyF(sec_filing)
    elif matches_form(sec_filing, "40-F"):
        from edgar.company_reports import FortyF
        return FortyF(sec_filing)
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
        warn_will_raise(_no_xml_to_parse(sec_filing), stacklevel=4)
    elif matches_form(sec_filing, "4"):
        xml = sec_filing.xml()
        if xml:
            return Form4(**Ownership.parse_xml(xml))
        warn_will_raise(_no_xml_to_parse(sec_filing), stacklevel=4)
    elif matches_form(sec_filing, "5"):
        xml = sec_filing.xml()
        if xml:
            return Form5(**Ownership.parse_xml(xml))
        warn_will_raise(_no_xml_to_parse(sec_filing), stacklevel=4)
    elif matches_form(sec_filing, ["SCHEDULE 13D", "SC 13D"]):
        return Schedule13D.from_filing(sec_filing)
    elif matches_form(sec_filing, ["SCHEDULE 13G", "SC 13G"]):
        return Schedule13G.from_filing(sec_filing)
    elif matches_form(sec_filing, "EFFECT"):
        xml = sec_filing.xml()
        if xml:
            return Effect.from_xml(xml)
        warn_will_raise(_no_xml_to_parse(sec_filing), stacklevel=4)
    elif matches_form(sec_filing, "D"):
        xml = sec_filing.xml()
        if xml:
            return FormD.from_xml(xml)
        warn_will_raise(_no_xml_to_parse(sec_filing), stacklevel=4)
    elif matches_form(sec_filing, ["C", "C-U", "C-AR", "C-TR"]):
        return FormC.from_filing(sec_filing)

    elif matches_form(sec_filing, "DRS"):
        from edgar.offerings.drs import DraftRegistrationStatement
        return DraftRegistrationStatement.from_filing(sec_filing)

    elif matches_form(sec_filing, ['S-1', 'F-1']):
        from edgar.offerings.registration_s1 import RegistrationS1
        return RegistrationS1.from_filing(sec_filing)

    elif matches_form(sec_filing, ['S-3', 'S-3ASR', 'S-3D', 'S-3DPOS', 'F-3', 'F-3ASR']):
        from edgar.offerings.registration_s3 import RegistrationS3
        return RegistrationS3.from_filing(sec_filing)

    elif matches_form(sec_filing, ['S-4', 'F-4']):
        from edgar.offerings.registration_s4 import RegistrationS4
        return RegistrationS4.from_filing(sec_filing)

    elif matches_form(sec_filing, ['424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8']):
        from edgar.offerings.prospectus import Prospectus424B
        return Prospectus424B.from_filing(sec_filing)

    elif matches_form(sec_filing, PROSPECTUS497K_FORMS):
        return Prospectus497K.from_filing(sec_filing)

    elif matches_form(sec_filing, NCEN_FORMS):
        return FundCensus.from_filing(sec_filing)

    elif matches_form(sec_filing, NCSR_FORMS):
        return FundShareholderReport.from_filing(sec_filing)

    elif matches_form(sec_filing, MONEY_MARKET_FORMS):
        return MoneyMarketFund.from_filing(sec_filing)

    elif matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
        return FundReport.from_filing(sec_filing)

    elif matches_form(sec_filing, ["N-PX"]):
        return NPX.from_filing(sec_filing)

    elif matches_form(sec_filing, PROXY_FORMS):
        return ProxyStatement.from_filing(sec_filing)

    elif matches_form(sec_filing, CORRESPONDENCE_FORMS):
        return Correspondence.from_filing(sec_filing)

    elif matches_form(sec_filing, "24F-2NT"):
        from edgar.funds.twentyfourf import FundFeeNotice
        return FundFeeNotice.from_filing(sec_filing)

    elif matches_form(sec_filing, ATS_N_WITHDRAWAL_FORMS):
        return AlternativeTradingSystemWithdrawal.from_filing(sec_filing)

    elif matches_form(sec_filing, ATS_N_FORMS + ATS_N_AMENDMENT_FORMS):
        return AlternativeTradingSystem.from_filing(sec_filing)

    else:
        from edgar.xmlfiling import XML_FILING_FORMS, XmlFiling
        if sec_filing.form in XML_FILING_FORMS:
            return XmlFiling.from_filing(sec_filing)

    # XBRL is the backstop for everything that fell through: a form we do not
    # model may still carry financial data worth handing back.
    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl

    # And this is the one legitimate None. Explicit rather than implicit,
    # because a function whose absence behaviour is a falling-off-the-end has no
    # way to say which of its several endings a caller reached. Every path that
    # means "we failed" warned above on its way here.
    return None
