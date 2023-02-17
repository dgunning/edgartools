# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
from typing import Optional, Union, List

from fastcore.basics import listify

from edgar._companies import (Company,
                              CompanyData,
                              CompanyFacts,
                              CompanyFilings,
                              get_company,
                              get_company_facts,
                              get_company_tickers,
                              get_company_submissions,
                              get_ticker_to_cik_lookup)
from edgar._filings import (Filing,
                            Filings,
                            get_filings,
                            get_funds,
                            get_fund_filings,
                            FilingHomepage)
from edgar._xbrl import FilingXbrl
from edgar.core import (get_identity,
                        set_identity)
from edgar.forms.effect import Effect
from edgar.forms.fund_reports import FundReport
from edgar.forms.offerings import Offering
from edgar.forms.ownership import Ownership


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
    xml = sec_filing.xml()
    if xml:
        if matches_form(sec_filing, ["3", "4", "5"]):
            return Ownership.from_xml(xml)
        elif matches_form(sec_filing, "EFFECT"):
            return Effect.from_xml(xml)
        elif matches_form(sec_filing, "D"):
            return Offering.from_xml(xml)
        elif matches_form(sec_filing, ["NPORT-P", "NPORT-EX"]):
            return FundReport.from_xml(xml)
    else:
        filing_xbrl = sec_filing.xbrl()
        if filing_xbrl:
            return filing_xbrl

