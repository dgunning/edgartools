# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
from typing import Optional, Union, List

from fastcore.basics import listify

from edgar._companies import (Company,
                              CompanyData,
                              CompanyFacts,
                              CompanySearchResults,
                              CompanyFilings,
                              CompanyFiling,
                              find_company,
                              get_company,
                              get_company_facts,
                              get_company_tickers,
                              get_company_submissions,
                              get_ticker_to_cik_lookup)
from edgar._filings import (Filing,
                            Filings,
                            get_filings,
                            get_filing_by_accession_number,
                            get_funds,
                            get_fund_filings,
                            FilingHomepage)
from edgar._xbrl import FilingXbrl
from edgar.core import (edgar_mode,
                        CRAWL,
                        CAUTION,
                        NORMAL,
                        get_identity,
                        set_identity)
from edgar.effect import Effect
from edgar.fundreports import FundReport
from edgar.offerings import Offering
from edgar.ownership import Ownership
from edgar.forms import EightK, TenK, TenQ
from edgar.form144 import Form144
from edgar.muniadvisors import MunicipalAdvisorForm
from edgar.fundreports import ThirteenF, THIRTEENF_FORMS


def matches_form(sec_filing: Filing,
                 form: Union[str, List[str]]) -> bool:
    """Check if the filing matches the forms"""
    form_list = listify(form)
    if sec_filing.form in form_list + [f"{f}/A" for f in form_list]:
        return True
    return False


def obj(sec_filing: Filing) -> Optional[object]:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing but it can also come from the extracted xbrl
    :param sec_filing: The filing
    :return:
    """
    if matches_form(sec_filing, "8-K"):
        return EightK(sec_filing)
    elif matches_form(sec_filing, "10-Q"):
        return TenQ(sec_filing)
    elif matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif matches_form(sec_filing, THIRTEENF_FORMS):
        return ThirteenF(sec_filing)
    elif matches_form(sec_filing, "144"):
        return Form144.from_filing(sec_filing)
    elif matches_form(sec_filing, "MA-I"):
        return MunicipalAdvisorForm.from_filing(sec_filing)
    elif matches_form(sec_filing, ["3", "4", "5"]):
        xml = sec_filing.xml()
        if xml:
            return Ownership.from_xml(xml)
    elif matches_form(sec_filing, "EFFECT"):
        xml = sec_filing.xml()
        if xml:
            return Effect.from_xml(xml)
    elif matches_form(sec_filing, "D"):
        xml = sec_filing.xml()
        if xml:
            return Offering.from_xml(xml)
    elif matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
        xml = sec_filing.xml()
        if xml:
            return FundReport.from_xml(xml)

    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl
