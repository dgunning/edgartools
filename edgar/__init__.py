# SPDX-FileCopyrightText: 2022-present Dwight Gunning <dgunning@gmail.com>
#
# SPDX-License-Identifier: MIT
from typing import Optional, Union, List

from concurrent.futures import ThreadPoolExecutor
import importlib
import sys

from functools import partial

from edgar._companies import (Company,
                              CompanyData,
                              CompanyFacts,
                              CompanySearchResults,
                              CompanyFilings,
                              CompanyFiling,
                              Entity,
                              find_company,
                              get_entity,
                              get_company_facts,
                              get_company_tickers,
                              get_entity_submissions,
                              get_ticker_to_cik_lookup)
from edgar._filings import (Filing,
                            Filings,
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
                        set_identity)
from edgar.thirteenf import ThirteenF, THIRTEENF_FORMS
from edgar.fundreports import FundReport, NPORT_FORMS
from edgar.funds import Fund, get_fund

# Another name for get_current_filings
get_recent_filings = get_current_filings

# Fund portfolio report filings
get_fund_portfolio_filings = partial(get_filings, form=NPORT_FORMS)

# Restricted stock sales
get_restricted_stock_filings = partial(get_filings, form=[144])

# Insider transaction filings
get_insider_transaction_filings = partial(get_filings, form=[3, 4, 5])

# 13F filings - portfolio holdings
get_portfolio_holding_filings = partial(get_filings, form=THIRTEENF_FORMS)


def matches_form(sec_filing: Filing,
                 form: Union[str, List[str]]) -> bool:
    """Check if the filing matches the forms"""
    from fastcore.basics import listify
    form_list = listify(form)
    if sec_filing.form in form_list + [f"{f}/A" for f in form_list]:
        return True
    return False


def obj(sec_filing: Filing) -> Optional[object]:
    """
    Depending on the filing return the data object that contains the data for the filing

    This usually coms from the xml associated with the filing, but it can also come from the extracted xbrl
    :param sec_filing: The filing
    :return:
    """
    from edgar.forms import EightK, TenK, TenQ
    from edgar.effect import Effect
    from edgar.offerings import Offering
    from edgar.ownership import Ownership
    from edgar.form144 import Form144
    from edgar.muniadvisors import MunicipalAdvisorForm

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
        return FundReport.from_filing(sec_filing)

    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl


# Import some libraries on the background
background_modules = ['unstructured']


def do_import(module_name):
    thismodule = sys.modules[__name__]

    module = importlib.import_module(module_name)
    setattr(thismodule, module_name, module)


def long_running_import():
    from unstructured.partition.html import partition_html
    str(partition_html.__name__)  #


executor = ThreadPoolExecutor()
executor.submit(long_running_import)
