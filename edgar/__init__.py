# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
import re
from functools import lru_cache
from functools import partial
from typing import Optional, Union, List

from edgar.entity import (
    Entity,
    EntityData,
    Company,
    CompanyData,
    CompanyFacts,
    CompanySearchResults,
    CompanyFilings,
    CompanyFiling,
    find_company,
    get_entity,
    get_company_facts,
    get_company_tickers,
    get_icon_from_ticker,
    get_entity_submissions,
    get_ticker_to_cik_lookup,
    get_cik_lookup_data
)
from edgar._filings import (Filing,
                            Filings,
                            FilingHeader,
                            CurrentFilings,
                            Attachment,
                            Attachments,
                            get_filings,
                            get_current_filings,
                            get_by_accession_number,
                            FilingHomepage)
from edgar.core import (edgar_mode,
                        CRAWL,
                        CAUTION,
                        NORMAL,
                        get_identity,
                        set_identity,
                        listify)
from edgar.funds.reports import FundReport, NPORT_FORMS
from edgar.funds import FundCompany, FundSeries,  FundClass, find_fund
from edgar.thirteenf import ThirteenF, THIRTEENF_FORMS
from edgar.xbrl import XBRL
from edgar.files.html import Document
from edgar.financials import Financials, MultiFinancials
from edgar.storage import use_local_storage, is_using_local_storage, download_edgar_data, download_filings

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
        return get_by_accession_number(search_id)
    elif re.match(r"^\d{18}$", search_id): # accession number with no dashes
        accession_number = search_id[:10] + "-" + search_id[10:12] + "-" + search_id[12:]
        return get_by_accession_number(accession_number)
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


def obj(sec_filing: Filing) -> Optional[object]:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing, but it can also come from the extracted xbrl
    :param sec_filing: The filing
    :return:
    """
    from edgar.company_reports import TenK, TenQ, TwentyF, EightK, CurrentReport
    from edgar.effect import Effect
    from edgar.offerings import FormC, FormD
    from edgar.ownership import Ownership, Form3, Form4, Form5
    from edgar.form144 import Form144
    from edgar.muniadvisors import MunicipalAdvisorForm

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
        if sec_filing.xml():
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
        xml = sec_filing.xml()
        if xml:
            return FormC.from_xml(xml, form=sec_filing.form)

    elif matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
        return FundReport.from_filing(sec_filing)

    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl
