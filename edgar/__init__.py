# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
import functools
import logging
import re
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:  # annotations only; nothing is imported at runtime (see below)
    from edgar._filings import Filing
    from edgar.entity import CompanySearchResults, Entity
    from edgar.exceptions import DataObjectError
    from edgar.funds import FundClass, FundCompany, FundSeries

# ---------------------------------------------------------------------------
# `import edgar` imports no edgar submodule (GH #1325, bead edgartools-07lk.9).
#
# Every top-level name is served on first access by the module `__getattr__` at
# the bottom of this file (PEP 562), from the table below. This is a correctness
# rule, not only an import-cost one. A thread running
# `from edgar.reference import describe_form` takes the import lock of
# `edgar.reference` and then needs `edgar`. While this file imported its
# submodules eagerly, a second thread running `import edgar` held `edgar`'s lock
# and needed `edgar.reference`, and both imports failed (3 of 3). Ten modules
# reached during package init imported `edgar.reference`, so removing any one
# edge only moved the failure. With nothing imported here, the package lock is
# held for a few statements only, and the other thread simply waits for them.
#
# So do not add a module-level `from edgar.x import ...` to this file: add the
# name to _EXPORTS_BY_MODULE, and import inside any function defined here.
# tests/issues/regression/test_issue_1325.py pins this.
# ---------------------------------------------------------------------------
_EXPORTS_BY_MODULE = {
    "edgar.__about__": ("__version__",),
    "edgar._filings": (
        "Attachment", "Attachments", "Filing", "FilingHeader", "FilingHomepage", "Filings",
        "get_by_accession_number", "get_filings",
    ),
    "edgar.settings": ("get_identity", "set_identity"),
    "edgar.exceptions": (
        "AttachmentNotFoundError", "CompanyFactsNotFoundError", "CompanyNotFoundError",
        "DataObjectError", "EdgarError", "FilingNotFoundError", "IdentityNotSetError",
        "NotFoundError", "ParsingError", "SectionNotFoundError", "StatementNotFoundError",
        "TooManyRequestsError", "TransportError", "ValidationError",
    ),
    "edgar.current_filings": (
        "CurrentFilings", "get_all_current_filings", "get_current_filings", "iter_current_filings_pages",
    ),
    "edgar.diagnose_ssl": ("diagnose_ssl",),
    "edgar.entity": (
        "Company", "CompanyData", "CompanyFiling", "CompanyFilings", "CompanySearchResults",
        "Entity", "EntityData", "find_company", "get_company_facts", "get_company_tickers",
        "get_entity", "get_icon_from_ticker",
    ),
    "edgar.filesystem": ("is_cloud_storage_enabled", "sync_to_cloud", "use_cloud_storage"),
    "edgar.financials": ("Financials", "MultiFinancials"),
    "edgar.funds": ("Fund", "FundClass", "FundCompany", "FundSeries", "find_fund", "find_funds"),
    "edgar.funds.ncen": ("NCEN_FORMS", "FundCensus"),
    "edgar.funds.ncsr": ("NCSR_FORMS", "FundShareholderReport"),
    "edgar.funds.nmfp3": ("MONEY_MARKET_FORMS", "NMFP2_FORMS", "NMFP3_FORMS", "MoneyMarketFund"),
    "edgar.funds.prospectus497k": ("PROSPECTUS497K_FORMS", "Prospectus497K"),
    "edgar.funds.reports": ("NPORT_FORMS", "FundReport"),
    "edgar.ats": (
        "ATS_N_ALL_FORMS", "ATS_N_AMENDMENT_FORMS", "ATS_N_FORMS", "ATS_N_WITHDRAWAL_FORMS",
        "AlternativeTradingSystem", "AlternativeTradingSystemWithdrawal",
    ),
    "edgar.bdc": ("BDCEntities", "BDCEntity", "get_bdc_list", "get_active_bdc_ciks", "is_bdc_cik"),
    "edgar.httpclient": ("configure_http", "get_http_config"),
    "edgar.npx": ("NPX",),
    "edgar.proxy": ("PROXY_FORMS", "ProxyContests", "ProxyStatement", "proxy_contests"),
    "edgar.storage": (
        "StorageAnalysis", "StorageInfo", "analyze_storage", "availability_summary", "check_filing",
        "check_filings_batch", "cleanup_storage", "clear_cache", "download_edgar_data",
        "download_filings", "is_using_datamule_storage", "is_using_local_storage", "optimize_storage",
        "set_local_storage_path", "storage_info", "use_datamule_storage", "use_local_storage",
    ),
    "edgar.correspondence": (
        "CORRESPONDENCE_FORMS", "Correspondence", "CorrespondenceThread", "CorrespondenceType",
    ),
    "edgar.search.efts": ("EFTSResult", "EFTSSearch", "search_filings"),
    "edgar.thirteenf": ("THIRTEENF_FORMS", "ThirteenF"),
    "edgar.xbrl": ("XBRL",),
    # The ownership family was the first lazy group (bead edgartools-07lk.12.1.1):
    # edgar.Form4 is edgar.ownership.Form4, so isinstance agrees across spellings.
    "edgar.ownership": ("Form3", "Form4", "Form5"),
    "edgar.ownership.form144": ("Form144",),
    "edgar.beneficial_ownership": ("Schedule13D", "Schedule13G"),
}
_LAZY_EXPORTS = {name: module for module, names in _EXPORTS_BY_MODULE.items() for name in names}

# Other names for get_current_filings
_ALIASES = {
    "get_latest_filings": "get_current_filings",
    "latest_filings": "get_current_filings",
    "current_filings": "get_current_filings",
}

# get_filings() pre-filtered to a form family: name -> (module, constant), or a literal form list
_FORM_FILTERED_GET_FILINGS = {
    "get_fund_portfolio_filings": ("edgar.funds.reports", "NPORT_FORMS"),     # fund portfolio reports
    "get_money_market_filings": ("edgar.funds.nmfp3", "MONEY_MARKET_FORMS"),  # money market funds
    "get_restricted_stock_filings": [144],                                    # restricted stock sales
    "get_insider_transaction_filings": [3, 4, 5],                             # insider transactions
    "get_portfolio_holding_filings": ("edgar.thirteenf", "THIRTEENF_FORMS"),  # 13F holdings
}

# Attach a NullHandler to the package-root logger so that edgartools never emits
# log output unless the application configures logging itself, per the Python
# logging HOWTO guidance for libraries (#856).  Without it, library warnings have
# no handler in their ancestry and fall back to logging.lastResort (stderr),
# which is especially harmful in MCP / stdio environments.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# The one-time cache clears (#457, #672, #1051) used to run here. They run when
# edgar.httpclient is first imported, which every request goes through.


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
# WHAT BEING ABSENT FROM THIS LIST MEANS. Through 5.x a name outside this list
# was internal but still importable. 6.0 made those names private
# (edgartools-07lk.5): every non-module name reachable from `edgar` is now in
# `__all__`, and `tests/issues/regression/test_public_api_surface.py` fails if a
# new one appears without being listed. The names that went are in
# `_PRIVATE_IN_6_0` below, each with its supported replacement. If something you
# depend on is missing here, that is worth an issue.
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
    # The ownership family splits across three packages along the statute that
    # requires each form; see the docstrings of edgar.ownership (Section 16),
    # edgar.beneficial_ownership (Section 13(d)/(g)) and edgar.thirteenf
    # (Section 13(f)).
    "Form3", "Form4", "Form5", "Form144",
    "Schedule13D", "Schedule13G",
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


@functools.lru_cache(maxsize=16)
def find(search_id: str | int) -> "Filing | Entity | CompanySearchResults | FundCompany | FundClass | FundSeries | None":
    """This is an uber search function that can take a variety of search ids and return the appropriate object
        - accession number -> returns a Filing
        - CIK -> returns an Entity
        - Class/Contract ID -> returns a FundClass
        - Series ID -> returns a FundSeries
        - Ticker -> returns an Entity (use Company(ticker) for get_financials()); a ticker no company has falls back
          to a company-name search, and a mutual fund ticker (four uppercase letters then X) goes to find_fund()
        - Company name -> returns CompanySearchResults

    :type: object
    """
    from edgar._filings import get_by_accession_number_enriched as _get_by_accession_number_enriched
    from edgar.exceptions import CompanyNotFoundError, ValidationError

    # Through the package namespace, as the eager imports did, so that
    # monkeypatching edgar.Entity (or find_company, find_fund) still reaches find().
    Entity, find_company, find_fund = _public("Entity"), _public("find_company"), _public("find_fund")  # noqa: N806

    if isinstance(search_id, int):
        return Entity(search_id)
    elif re.match(r"\d{10}-\d{2}-\d{6}", search_id):
        return _get_by_accession_number_enriched(search_id)
    elif re.match(r"^\d{18}$", search_id): # accession number with no dashes
        accession_number = search_id[:10] + "-" + search_id[10:12] + "-" + search_id[12:]
        return _get_by_accession_number_enriched(accession_number)
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
        # that is malformed, and "you typed it wrong" is the one thing a return
        # value cannot say (edgartools-07lk.10: a FutureWarning and None in 5.x).
        raise ValidationError(
            f"'{search_id}' is not a valid accession number.",
            parameter="search_id",
            invalid_value=search_id,
            suggestions=[
                "the format is 10 digits, 2 digits, 6 digits: 0000320193-23-000106",
                "dashes are optional — 000032019323000106 also works",
            ],
        )
    else:
        return find_company(search_id)


def _matches_form(sec_filing: "Filing",
                  form: str | list[str]) -> bool:
    """Check if the filing matches the forms"""
    from edgar.core import listify as _listify

    form_list = _listify(form)
    if sec_filing.form in form_list + [f"{f}/A" for f in form_list if not f.endswith("/A")]:
        return True
    return False


def _get_obj_info(form: str) -> tuple[bool, str | None, str | None]:
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
        'SC 14D9': ('Schedule14D9', 'target company board recommendation on a tender offer'),
        'SC 14D9/A': ('Schedule14D9', 'target company board recommendation on a tender offer (amendment)'),
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


def _no_xml_to_parse(sec_filing: "Filing") -> "DataObjectError":
    """The error for a form we model whose XML we could not get.

    Raised by `obj()` for Form 3, 4, 5, EFFECT and D (edgartools-07lk.10); in
    5.x it was a `FutureWarning` and `None`.
    """
    from edgar.exceptions import DataObjectError

    error = DataObjectError(
        f"Form {sec_filing.form} filing {sec_filing.accession_no} has no XML document, "
        f"so there is nothing to build a data object from. This is a property of "
        f"the filing, not of the form — ownership forms filed before roughly 2003 "
        f"predate the XML requirement.",
        form=sec_filing.form,
        accession_no=sec_filing.accession_no,
    )
    return error


def obj(sec_filing: "Filing") -> object | None:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing, but it can also come from the extracted xbrl

    Returns:
        The data object for the filing, or `None` for a form edgartools does not
        model and whose filing carries no XBRL either. That is the only meaning
        `None` has here, and it is a statement about our coverage rather than
        about the filing.

        It is NOT how failure is reported. A form we *do* model whose data we
        could not read raises `DataObjectError`.

    :param sec_filing: The filing
    :return:
    """
    from edgar.ats import (
        ATS_N_AMENDMENT_FORMS,
        ATS_N_FORMS,
        ATS_N_WITHDRAWAL_FORMS,
        AlternativeTradingSystem,
        AlternativeTradingSystemWithdrawal,
    )
    from edgar.beneficial_ownership import Schedule13D, Schedule13G
    from edgar.company_reports import CurrentReport, EightK, SixK, TenK, TenQ, TwentyF
    from edgar.correspondence import CORRESPONDENCE_FORMS, Correspondence
    from edgar.funds.ncen import NCEN_FORMS, FundCensus
    from edgar.funds.ncsr import NCSR_FORMS, FundShareholderReport
    from edgar.funds.nmfp3 import MONEY_MARKET_FORMS, MoneyMarketFund
    from edgar.funds.prospectus497k import PROSPECTUS497K_FORMS, Prospectus497K
    from edgar.funds.reports import FundReport
    from edgar.muniadvisors import MunicipalAdvisorForm
    from edgar.npx import NPX
    from edgar.offerings import FormC, FormD
    from edgar.offerings.effect import Effect
    from edgar.ownership import Form3, Form4, Form5, Ownership
    from edgar.ownership.form144 import Form144
    from edgar.proxy import PROXY_FORMS, ProxyStatement
    from edgar.tender_offers import Schedule14D9
    from edgar.thirteenf import THIRTEENF_FORMS, ThirteenF

    if _matches_form(sec_filing, "6-K"):
        return SixK(sec_filing)
    if _matches_form(sec_filing, "8-K"):
        return EightK(sec_filing)
    elif _matches_form(sec_filing, "10-Q"):
        return TenQ(sec_filing)
    elif _matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif _matches_form(sec_filing, "10-D"):
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
    elif _matches_form(sec_filing, "20-F"):
        return TwentyF(sec_filing)
    elif _matches_form(sec_filing, "40-F"):
        from edgar.company_reports import FortyF
        return FortyF(sec_filing)
    elif _matches_form(sec_filing, THIRTEENF_FORMS):
        # ThirteenF can work with either XML (2013+) or TXT (2012 and earlier) format
        return ThirteenF(sec_filing)
    elif _matches_form(sec_filing, "144"):
        return Form144.from_filing(sec_filing)
    elif _matches_form(sec_filing, "MA-I"):
        return MunicipalAdvisorForm.from_filing(sec_filing)
    elif _matches_form(sec_filing, "3"):
        xml = sec_filing.xml()
        if xml:
            return Form3(**Ownership.parse_xml(xml))
        raise _no_xml_to_parse(sec_filing)
    elif _matches_form(sec_filing, "4"):
        xml = sec_filing.xml()
        if xml:
            return Form4(**Ownership.parse_xml(xml))
        raise _no_xml_to_parse(sec_filing)
    elif _matches_form(sec_filing, "5"):
        xml = sec_filing.xml()
        if xml:
            return Form5(**Ownership.parse_xml(xml))
        raise _no_xml_to_parse(sec_filing)
    elif _matches_form(sec_filing, ["SCHEDULE 13D", "SC 13D"]):
        return Schedule13D.from_filing(sec_filing)
    elif _matches_form(sec_filing, ["SCHEDULE 13G", "SC 13G"]):
        return Schedule13G.from_filing(sec_filing)
    elif _matches_form(sec_filing, "SC 14D9"):
        return Schedule14D9.from_filing(sec_filing)
    elif _matches_form(sec_filing, "EFFECT"):
        xml = sec_filing.xml()
        if xml:
            return Effect.from_xml(xml)
        raise _no_xml_to_parse(sec_filing)
    elif _matches_form(sec_filing, "D"):
        xml = sec_filing.xml()
        if xml:
            return FormD.from_xml(xml)
        raise _no_xml_to_parse(sec_filing)
    elif _matches_form(sec_filing, ["C", "C-U", "C-AR", "C-TR"]):
        return FormC.from_filing(sec_filing)

    elif _matches_form(sec_filing, "DRS"):
        from edgar.offerings.prospectus.drs import DraftRegistrationStatement
        return DraftRegistrationStatement.from_filing(sec_filing)

    elif _matches_form(sec_filing, ['S-1', 'F-1']):
        from edgar.offerings.prospectus.registration_s1 import RegistrationS1
        return RegistrationS1.from_filing(sec_filing)

    elif _matches_form(sec_filing, ['S-3', 'S-3ASR', 'S-3D', 'S-3DPOS', 'F-3', 'F-3ASR']):
        from edgar.offerings.prospectus.registration_s3 import RegistrationS3
        return RegistrationS3.from_filing(sec_filing)

    elif _matches_form(sec_filing, ['S-4', 'F-4']):
        from edgar.offerings.prospectus.registration_s4 import RegistrationS4
        return RegistrationS4.from_filing(sec_filing)

    elif _matches_form(sec_filing, ['424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8']):
        from edgar.offerings.prospectus import Prospectus424B
        return Prospectus424B.from_filing(sec_filing)

    elif _matches_form(sec_filing, PROSPECTUS497K_FORMS):
        return Prospectus497K.from_filing(sec_filing)

    elif _matches_form(sec_filing, NCEN_FORMS):
        return FundCensus.from_filing(sec_filing)

    elif _matches_form(sec_filing, NCSR_FORMS):
        return FundShareholderReport.from_filing(sec_filing)

    elif _matches_form(sec_filing, MONEY_MARKET_FORMS):
        return MoneyMarketFund.from_filing(sec_filing)

    elif _matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
        return FundReport.from_filing(sec_filing)

    elif _matches_form(sec_filing, ["N-PX"]):
        return NPX.from_filing(sec_filing)

    elif _matches_form(sec_filing, PROXY_FORMS):
        return ProxyStatement.from_filing(sec_filing)

    elif _matches_form(sec_filing, CORRESPONDENCE_FORMS):
        return Correspondence.from_filing(sec_filing)

    elif _matches_form(sec_filing, "24F-2NT"):
        from edgar.funds.twentyfourf import FundFeeNotice
        return FundFeeNotice.from_filing(sec_filing)

    elif _matches_form(sec_filing, ATS_N_WITHDRAWAL_FORMS):
        return AlternativeTradingSystemWithdrawal.from_filing(sec_filing)

    elif _matches_form(sec_filing, ATS_N_FORMS + ATS_N_AMENDMENT_FORMS):
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


# Names 6.0 removed from the top level along with the legacy `edgar.files`
# parser. They were never in `__all__`, but `from edgar import Document` worked
# for years, so the AttributeError says where to go instead of only "no attribute".
_REMOVED_IN_6_0 = {
    "Document": (
        "edgar.Document was the legacy HTML parser and was removed in edgartools 6.0. "
        "Use filing.parse() or edgar.documents.parse_html(html), which return "
        "edgar.documents.Document."
    ),
    "detect_page_breaks": (
        "edgar.detect_page_breaks was removed in edgartools 6.0 with the legacy "
        "edgar.files parser. It has no replacement: edgar.documents treats page "
        "breaks as print layout and drops them."
    ),
    "mark_page_breaks": (
        "edgar.mark_page_breaks was removed in edgartools 6.0 with the legacy "
        "edgar.files parser. It has no replacement: edgar.documents treats page "
        "breaks as print layout and drops them."
    ),
}


# Names that were importable from `edgar` through 5.x without being in
# `__all__`, made private in 6.0 (edgartools-07lk.5). `edgar.X` says where each
# one lives; `from edgar import X` cannot carry the message (Python replaces an
# AttributeError from a module `__getattr__` with a bare ImportError), so
# docs/upgrade/6.0.md carries the same table.
_PRIVATE_IN_6_0 = {
    **{name: "import it from typing" for name in ("List", "Optional", "Union")},
    **{name: "import it from functools" for name in ("lru_cache", "partial")},
    **{name: "import it from edgar.paths" for name in (
        "get_anchor_cache_directory", "get_cache_directory", "get_claude_skills_directory",
        "get_data_directory", "get_search_cache_directory", "get_test_directory",
        "set_cache_directory", "set_claude_skills_directory", "set_data_directory",
        "set_test_directory",
    )},
    **{name: "import it from edgar.context" for name in ("HasContext", "compose_context")},
    **{name: "import it from edgar.entity" for name in (
        "get_entity_submissions", "get_cik_lookup_data", "get_ticker_to_cik_lookup",
    )},
    "clear_company_facts_cache": "call edgar.clear_cache(), or import it from edgar.entity.entity_facts",
    "listify": "import it from edgar.core",
    "get_by_accession_number_enriched": "call edgar.find(accession_no), which uses it",
    "get_obj_info": "use Filing.obj_type, the class name filing.obj() would return, or None",
    "matches_form": "compare filing.form directly",
}


def _resolve(name: str):
    """The object a top-level name stands for, importing its module on first use."""
    import importlib

    if name in _LAZY_EXPORTS:
        return getattr(importlib.import_module(_LAZY_EXPORTS[name]), name)
    if name in _ALIASES:
        return _resolve(_ALIASES[name])
    forms = _FORM_FILTERED_GET_FILINGS[name]
    if isinstance(forms, tuple):
        forms = getattr(importlib.import_module(forms[0]), forms[1])
    return functools.partial(_resolve("get_filings"), form=forms)


def _submodule(name: str):
    """`edgar.xbrl` and the like, which eager imports used to leave on the package.

    None when there is no such submodule. A submodule that exists but fails to
    import raises its own error rather than a misleading AttributeError.
    """
    import importlib

    try:
        return importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as error:
        if error.name == f"{__name__}.{name}":
            return None
        raise


def _public(name: str):
    """A top-level name as `edgar.<name>` would give it, including a patched one."""
    return globals()[name] if name in globals() else __getattr__(name)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS or name in _ALIASES or name in _FORM_FILTERED_GET_FILINGS:
        value = _resolve(name)
        globals()[name] = value  # later lookups skip this hook
        return value
    if name in _REMOVED_IN_6_0:
        raise AttributeError(_REMOVED_IN_6_0[name])
    if name in _PRIVATE_IN_6_0:
        raise AttributeError(
            f"edgar.{name} is not part of the public API and was made private in "
            f"edgartools 6.0; {_PRIVATE_IN_6_0[name]}. See docs/upgrade/6.0.md."
        )
    if not name.startswith("__"):
        module = _submodule(name)
        if module is not None:
            return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY_EXPORTS) | set(_ALIASES) | set(_FORM_FILTERED_GET_FILINGS))
