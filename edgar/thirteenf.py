from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Union, List

import pandas as pd
import pyarrow.compute as pc
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column

from edgar._party import Address
from edgar._rich import repr_rich
from edgar.sgml import stream_documents
from edgar.core import log
from edgar._xml import find_element, child_text

__all__ = [
    'ThirteenF',
    "THIRTEENF_FORMS",
]

THIRTEENF_FORMS = ['13F-HR', "13F-HR/A", "13F-NT", "13F-NT/A", "13F-CTR", "13F-CTR/A"]


def format_date(date: Union[str, datetime]) -> str:
    if isinstance(date, str):
        return date
    return date.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class FilingManager:
    name: str
    address: Address


@dataclass(frozen=True)
class OtherManager:
    cik: str
    name: str
    file_number: str


@dataclass(frozen=True)
class CoverPage:
    report_calendar_or_quarter: str
    report_type: str
    filing_manager: FilingManager
    other_managers: List[OtherManager]


@dataclass(frozen=True)
class SummaryPage:
    other_included_managers_count: int
    total_value: Decimal
    total_holdings: int


@dataclass(frozen=True)
class Signature:
    name: str
    title: str
    phone: str
    signature: str
    city: str
    state_or_country: str
    date: str


@dataclass(frozen=True)
class PrimaryDocument13F:
    report_period: datetime
    cover_page: CoverPage
    summary_page: SummaryPage
    signature: Signature
    additional_information: str


class ThirteenF:
    """
    A 13F-HR is a quarterly report filed by institutional investment managers that have over $100 million in qualifying
    assets under management. The report is filed with the Securities & Exchange Commission (SEC) and discloses all
    the firm's equity holdings that it held at the end of the quarter. The report is due within 45 days of the end
    of the quarter. The 13F-HR is a public document that is available on the SEC's website.
    """

    def __init__(self, filing, use_latest_period_of_report=False):
        assert filing.form in THIRTEENF_FORMS, f"Form {filing.form} is not a valid 13F form"
        # The filing might not be the filing for the current period. We need to use the related filing filed on the same
        # date as the current filing that has the latest period of report
        self._related_filings = filing.related_filings().filter(filing_date=filing.filing_date, form=filing.form)
        self._actual_filing = filing  # The filing passed in
        if use_latest_period_of_report:
            # Use the last related filing.
            # It should also be the one that has the CONFORMED_PERIOD_OF_REPORT closest to filing_date
            self.filing = self._related_filings[-1]
        else:
            # Use the exact filing that was passed in
            self.filing = self._actual_filing
        self.primary_form_information = ThirteenF.parse_primary_document_xml(self.filing.xml())

    def has_infotable(self):
        return self.filing.form in ['13F-HR', "13F-HR/A"]

    @property
    def form(self):
        return self.filing.form

    @property
    @lru_cache(maxsize=1)
    def infotable_xml(self):
        if self.has_infotable():
            infotable_content = self._get_infotable_from_attachment()
            if "informationTable" in infotable_content:
                return infotable_content
            log.warning("Could not find infotable in attachment. Trying to get it from SGML")
            return self._get_infotable_from_sgml()

    def _get_infotable_from_sgml(self):
        """
        Use the SGML parser to get the infotable file
        """
        if self.has_infotable():
            for document in stream_documents(self.filing.text_url):
                if document.type == "INFORMATION TABLE":
                    return document.text_content
    def _get_infotable_from_attachment(self):
        """
        Use the filing homepage to get the infotable file
        """
        from edgar._filings import Attachment
        if self.has_infotable():
            matching_files = self.filing.homepage.get_matching_files(
                "Type=='INFORMATION TABLE' & (Document.str.endswith('.xml') | Document.str.endswith('.XML'))")
            return Attachment.from_dataframe_row(matching_files.iloc[0]).download()

    @property
    @lru_cache(maxsize=1)
    def infotable_html(self):
        from edgar._filings import Attachment
        if self.has_infotable():
            matching_files = self.filing.homepage.get_matching_files(
                "Type=='INFORMATION TABLE' & Document.str.endswith('html')")
            return Attachment.from_dataframe_row(matching_files.iloc[0]).download()

    @property
    @lru_cache(maxsize=1)
    def infotable(self):
        if self.has_infotable():
            return ThirteenF.parse_infotable_xml(self.infotable_xml)

    @property
    def accession_number(self):
        return self.filing.accession_no

    @property
    def total_value(self):
        return self.primary_form_information.summary_page.total_value

    @property
    def total_holdings(self):
        return self.primary_form_information.summary_page.total_holdings

    @property
    def report_period(self):
        return format_date(self.primary_form_information.report_period)

    @property
    def filing_date(self):
        return format_date(self.filing.filing_date)

    @property
    def investment_manager(self):
        # This is really the firm e.g. Spark Growth Management Partners II, LLC
        return self.primary_form_information.cover_page.filing_manager

    @property
    def signer(self):
        # This is the person who signed the filing. Could be the Reporting Manager but could be someone else
        # like the CFO
        return self.primary_form_information.signature.name

    @lru_cache(maxsize=8)
    def previous_holding_report(self):
        if len(self.report_period) == 1:
            return None
        # Look in the related filings data for the row with this accession number
        idx = pc.equal(self._related_filings.data['accession_number'], self.accession_number).index(True).as_py()
        if idx == 0:
            return None
        previous_filing = self._related_filings[idx - 1]
        return ThirteenF(previous_filing, use_latest_period_of_report=False)

    @staticmethod
    @lru_cache(maxsize=8)
    def parse_primary_document_xml(primary_document_xml: str):
        root = find_element(primary_document_xml, "edgarSubmission")
        # Header data
        header_data = root.find("headerData")
        filer_info = header_data.find("filerInfo")
        report_period = datetime.strptime(child_text(filer_info, "periodOfReport"), "%m-%d-%Y")

        # Form Data
        form_data = root.find("formData")
        cover_page_el = form_data.find("coverPage")

        report_calendar_or_quarter = child_text(form_data, "reportCalendarOrQuarter")
        report_type = child_text(cover_page_el, "reportType")

        # Filing Manager
        filing_manager_el = cover_page_el.find("filingManager")

        # Address
        address_el = filing_manager_el.find("address")
        address = Address(
            street1=child_text(address_el, "street1"),
            street2=child_text(address_el, "street2"),
            city=child_text(address_el, "city"),
            state_or_country=child_text(address_el, "stateOrCountry"),
            zipcode=child_text(address_el, "zipCode")
        )
        filing_manager = FilingManager(name=child_text(filing_manager_el, "name"), address=address)
        # Other managers
        other_manager_info_el = cover_page_el.find("otherManagersInfo")
        other_managers = [
            OtherManager(
                cik=child_text(other_manager_el, "cik"),
                name=child_text(other_manager_el, "name"),
                file_number=child_text(other_manager_el, "form13FFileNumber")
            )
            for other_manager_el in other_manager_info_el.find_all("otherManager")
        ] if other_manager_info_el else []

        # Summary Page
        summary_page_el = form_data.find("summaryPage")
        other_included_managers_count = int(child_text(summary_page_el,
                                                       "otherIncludedManagersCount")) if summary_page_el else None
        total_holdings = int(child_text(summary_page_el, "tableEntryTotal")) if summary_page_el else None
        total_value = Decimal(child_text(summary_page_el, "tableValueTotal")) if summary_page_el else None

        # Signature Block
        signature_block_el = form_data.find("signatureBlock")
        signature = Signature(
            name=child_text(signature_block_el, "name"),
            title=child_text(signature_block_el, "title"),
            phone=child_text(signature_block_el, "phone"),
            city=child_text(signature_block_el, "city"),
            signature=child_text(signature_block_el, "signature"),
            state_or_country=child_text(signature_block_el, "stateOrCountry"),
            date=child_text(signature_block_el, "signatureDate")
        )

        parsed_primary_doc = PrimaryDocument13F(
            report_period=report_period,
            cover_page=CoverPage(
                filing_manager=filing_manager,
                report_calendar_or_quarter=report_calendar_or_quarter,
                report_type=report_type,
                other_managers=other_managers
            ),
            signature=signature,
            summary_page=SummaryPage(

                other_included_managers_count=other_included_managers_count,
                total_holdings=total_holdings,
                total_value=total_value
            ),
            additional_information=child_text(cover_page_el, "additionalInformation")
        )

        return parsed_primary_doc

    @staticmethod
    def parse_infotable_xml(infotable_xml: str):
        root = find_element(infotable_xml, "informationTable")
        rows = []
        shares_or_principal = {"SH": "Shares", "PRN": "Principal"}
        for info_tag in root.find_all("infoTable"):
            info_table = dict()

            info_table['Issuer'] = child_text(info_tag, "nameOfIssuer")
            info_table['Class'] = child_text(info_tag, "titleOfClass")
            info_table['Cusip'] = child_text(info_tag, "cusip")
            info_table['Value'] = int(child_text(info_tag, "value"))

            # Shares or principal
            shares_tag = info_tag.find("shrsOrPrnAmt")
            info_table['SharesPrnAmount'] = child_text(shares_tag, "sshPrnamt")

            # Shares or principal
            ssh_prnamt_type = child_text(shares_tag, "sshPrnamtType")
            info_table['Type'] = shares_or_principal.get(ssh_prnamt_type)

            info_table["PutCall"] = child_text(shares_tag, "putCall")
            info_table['InvestmentDiscretion'] = child_text(info_tag, "investmentDiscretion")

            # Voting authority
            voting_auth_tag = info_tag.find("votingAuthority")
            info_table['SoleVoting'] = int(child_text(voting_auth_tag, "Sole"))
            info_table['SharedVoting'] = int(child_text(voting_auth_tag, "Shared"))
            info_table['NonVoting'] = int(child_text(voting_auth_tag, "None"))
            rows.append(info_table)

        table = pd.DataFrame(rows)
        return table

    def _infotable_summary(self):
        if self.has_infotable():
            return (self.infotable
                    .filter(['Issuer', 'Class', 'Value', 'SharesPrnAmount', 'Type',
                             'SoleVoting', 'SharedVoting', 'NonVoting'])
                    .rename(columns={'SharesPrnAmount': 'Shares'})
                    .assign(Value=lambda df: df.Value,
                            Type=lambda df: df.Type.fillna('-'))
                    .sort_values(['Value'], ascending=False)
                    )

    def __rich__(self):
        title = f"{self.form} Holding Report for {self.filing.company} for period {self.report_period}"
        summary = Table(
            "Report Period",
            Column("Investment Manager", style="bold deep_sky_blue1"),
            "Signed By",
            "Holdings",
            "Value",
            "Accession Number",
            "Filed",
            box=box.SIMPLE)

        summary.add_row(
            self.report_period,
            self.investment_manager.name,
            self.signer,
            str(self.total_holdings or "-"),
            f"${self.total_value:,.0f}" if self.total_value else "-",
            self.filing.accession_no,
            self.filing_date
        )

        content = [summary]

        # info table
        if self.has_infotable():
            table = Table("", "Issuer", "Class", "Value", "Type", "Shares", "Voting", "Non Voting", "Shared Voting",
                          row_styles=["bold", ""],
                          box=box.SIMPLE)
            for index, row in enumerate(self._infotable_summary().itertuples()):
                table.add_row(str(index),
                              row.Issuer,
                              row.Class,
                              f"${row.Value:,.0f}",
                              row.Type,
                              f"{int(row.Shares):,.0f}",
                              f"{int(row.SoleVoting):,.0f}",
                              f"{int(row.NonVoting):,.0f}",
                              f"{int(row.SharedVoting):,.0f}"
                              )
            content.append(table)

        return Panel(
            Group(*content), title=title, subtitle=title
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
