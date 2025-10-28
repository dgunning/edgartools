from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import List, Union

import pandas as pd
import pyarrow.compute as pc
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table

from edgar._party import Address
from edgar.reference import cusip_ticker_mapping
from edgar.richtools import repr_rich
from edgar.xmltools import child_text, find_element

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

        # Parse primary document if XML is available (2013+ filings)
        # For older TXT-only filings (2012 and earlier), primary_form_information will be None
        primary_xml = self.filing.xml()
        self.primary_form_information = ThirteenF.parse_primary_document_xml(primary_xml) if primary_xml else None

    def has_infotable(self):
        return self.filing.form in ['13F-HR', "13F-HR/A"]

    @property
    def form(self):
        return self.filing.form

    @property
    @lru_cache(maxsize=1)
    def infotable_xml(self):
        """Returns XML content if available (2013+ filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'xml' and "informationTable" in result[0]:
                return result[0]
        return None

    def _get_infotable_from_attachment(self):
        """
        Use the filing homepage to get the infotable file.
        Returns a tuple of (content, format) where format is 'xml' or 'txt'.
        """
        if self.has_infotable():
            # Try XML format first (2013+)
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.xml')"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                return (attachments.get_by_index(0).download(), 'xml')

            # Fall back to TXT format (2012 and earlier)
            # The primary document itself contains the table in TXT format
            query = "description=='FORM 13F'"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                return (attachments.get_by_index(0).download(), 'txt')

            return (None, None)

    @property
    @lru_cache(maxsize=1)
    def infotable_txt(self):
        """Returns TXT content if available (pre-2013 filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'txt':
                return result[0]
        return None

    @property
    @lru_cache(maxsize=1)
    def infotable_html(self):
        if self.has_infotable():
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.html')"
            attachments = self.filing.attachments.query(query)
            return attachments[0].download()

    @property
    @lru_cache(maxsize=1)
    def infotable(self):
        """
        Returns the information table as a pandas DataFrame.
        Supports both XML format (2013+) and TXT format (2012 and earlier).
        """
        if self.has_infotable():
            # Try XML format first
            if self.infotable_xml:
                return ThirteenF.parse_infotable_xml(self.infotable_xml)
            # Fall back to TXT format
            elif self.infotable_txt:
                return ThirteenF.parse_infotable_txt(self.infotable_txt)
        return None

    @property
    def accession_number(self):
        return self.filing.accession_no

    @property
    def total_value(self):
        """Total value of holdings in thousands of dollars"""
        if self.primary_form_information:
            return self.primary_form_information.summary_page.total_value
        # For TXT-only filings, calculate from infotable
        infotable = self.infotable
        if infotable is not None and len(infotable) > 0:
            return Decimal(int(infotable['Value'].sum()))
        return None

    @property
    def total_holdings(self):
        """Total number of holdings"""
        if self.primary_form_information:
            return self.primary_form_information.summary_page.total_holdings
        # For TXT-only filings, count from infotable
        infotable = self.infotable
        if infotable is not None:
            return len(infotable)
        return None

    @property
    def report_period(self):
        """Report period end date"""
        if self.primary_form_information:
            return format_date(self.primary_form_information.report_period)
        # For TXT-only filings, use CONFORMED_PERIOD_OF_REPORT from filing header
        if hasattr(self.filing, 'period_of_report') and self.filing.period_of_report:
            return format_date(self.filing.period_of_report)
        return None

    @property
    def filing_date(self):
        return format_date(self.filing.filing_date)

    @property
    def investment_manager(self):
        # This is really the firm e.g. Spark Growth Management Partners II, LLC
        if self.primary_form_information:
            return self.primary_form_information.cover_page.filing_manager
        return None

    @property
    def signer(self):
        # This is the person who signed the filing. Could be the Reporting Manager but could be someone else
        # like the CFO
        if self.primary_form_information:
            return self.primary_form_information.signature.name
        return None

    # Enhanced manager name properties for better clarity
    @property
    def management_company_name(self) -> str:
        """
        The legal name of the investment management company that filed the 13F.

        This is the institutional entity (e.g., "Berkshire Hathaway Inc", "Vanguard Group Inc")
        that is legally responsible for managing the assets, not an individual person's name.

        Returns:
            str: The legal name of the management company, or company name from filing if not available

        Example:
            >>> thirteen_f.management_company_name
            'Berkshire Hathaway Inc'
        """
        if self.investment_manager:
            return self.investment_manager.name
        # For TXT-only filings, use company name from filing
        return self.filing.company

    @property 
    def filing_signer_name(self) -> str:
        """
        The name of the individual who signed the 13F filing.

        This is typically an administrative officer (CFO, CCO, Compliance Officer, etc.)
        rather than the famous portfolio manager. For example, Berkshire Hathaway's 13F
        is signed by "Marc D. Hamburg" (SVP), not Warren Buffett.

        Returns:
            str: The name of the person who signed the filing

        Example:
            >>> thirteen_f.filing_signer_name  
            'Marc D. Hamburg'
        """
        return self.signer

    @property
    def filing_signer_title(self) -> str:
        """
        The business title of the individual who signed the 13F filing.

        Common titles include: CFO, CCO, Senior Vice President, Chief Compliance Officer,
        Secretary, Treasurer, etc. This helps distinguish administrative signers from
        portfolio managers.

        Returns:
            str: The business title of the filing signer, or None if not available

        Example:
            >>> thirteen_f.filing_signer_title
            'Senior Vice President'
        """
        if self.primary_form_information:
            return self.primary_form_information.signature.title
        return None

    @property
    def manager_name(self) -> str:
        """
        DEPRECATED: Use management_company_name instead.

        Returns the management company name for backwards compatibility.
        This property name was misleading as it suggested an individual manager's name.

        Returns:
            str: The management company name

        Warning:
            This property is deprecated and may be removed in future versions.
            Use management_company_name for the company name, or see get_portfolio_managers()
            if you need information about individual portfolio managers.
        """
        import warnings
        warnings.warn(
            "manager_name is deprecated and misleading. Use management_company_name for the "
            "company name, or get_portfolio_managers() for individual manager information.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.management_company_name

    def get_portfolio_managers(self, include_approximate: bool = False) -> list[dict]:
        """
        Get information about the actual portfolio managers for this fund.

        Note: 13F filings do not contain individual portfolio manager names.
        This method provides a curated mapping for well-known funds based on
        public information. Results may not be current or complete.

        Args:
            include_approximate (bool): If True, includes approximate/historical 
                                      manager information even if not current

        Returns:
            list[dict]: List of portfolio manager information with keys:
                       'name', 'title', 'status', 'source', 'last_updated'

        Example:
            >>> thirteen_f.get_portfolio_managers()
            [
                {
                    'name': 'Warren Buffett', 
                    'title': 'Chairman & CEO',
                    'status': 'active',
                    'source': 'public_records',
                    'last_updated': '2024-01-01'
                }
            ]
        """
        return self._lookup_portfolio_managers(
            self.management_company_name, 
            include_approximate=include_approximate
        )

    def _lookup_portfolio_managers(self, company_name: str, include_approximate: bool = False) -> list[dict]:
        """
        Internal method to lookup portfolio managers for a given company.

        This uses a curated database of well-known fund managers loaded from an external JSON file.
        The data is compiled from public sources and may not be complete or current.
        """
        try:
            db = self._load_portfolio_manager_db()
            # Try CIK-based search first (more accurate)
            cik = getattr(self.filing, 'cik', None)
            if cik:
                managers = self._search_manager_database_by_cik(db, cik, include_approximate)
                if managers:
                    return managers

            # Fallback to name-based search
            return self._search_manager_database(db, company_name, include_approximate)
        except Exception as e:
            # Fallback to empty list if database loading fails
            import warnings
            warnings.warn(f"Could not load portfolio manager database: {e}")
            return []

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_portfolio_manager_db() -> dict:
        """
        Load the portfolio manager database from external JSON file.

        Returns:
            dict: The loaded database, or empty dict if file not found
        """
        import json
        from pathlib import Path

        # Try to load from external JSON file
        data_file = Path(__file__).parent / 'reference' / 'data' / 'portfolio_managers.json'

        if data_file.exists():
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                import warnings
                warnings.warn(f"Could not parse portfolio manager database: {e}")
                return {}
        else:
            # Fallback to basic hardcoded database for backwards compatibility
            return {
                "metadata": {
                    "version": "fallback",
                    "description": "Minimal fallback database",
                    "total_companies": 3,
                    "last_updated": "2024-12-01"
                },
                "managers": {
                    "berkshire_hathaway": {
                        "company_name": "Berkshire Hathaway Inc",
                        "match_patterns": ["berkshire hathaway", "brk", "berkshire"],
                        "managers": [
                            {
                                "name": "Warren Buffett",
                                "title": "Chairman & CEO",
                                "status": "active",
                                "confidence": "high",
                                "last_verified": "2024-12-01"
                            }
                        ]
                    }
                }
            }

    def _search_manager_database(self, db: dict, company_name: str, include_approximate: bool = False) -> list[dict]:
        """
        Search the manager database for a company.

        Args:
            db: The loaded database dictionary
            company_name: Company name to search for
            include_approximate: Whether to include non-active managers

        Returns:
            list[dict]: List of matching managers
        """
        if not db or 'managers' not in db:
            return []

        managers_data = db['managers']
        normalized_name = company_name.lower()

        # Search through all companies
        for company_key, company_data in managers_data.items():
            # Check match patterns
            match_patterns = company_data.get('match_patterns', [company_key])

            for pattern in match_patterns:
                if pattern.lower() in normalized_name:
                    managers = company_data.get('managers', [])

                    if include_approximate:
                        return managers
                    else:
                        # Only return active managers unless requested otherwise
                        return [m for m in managers if m.get('status') == 'active']

        # No matches found
        return []

    @staticmethod
    def _search_manager_database_by_cik(db: dict, cik: int, include_approximate: bool = False) -> list[dict]:
        """
        Search the manager database by CIK (more accurate than name matching).

        Args:
            db: The loaded database dictionary
            cik: The CIK to search for
            include_approximate: Whether to include non-active managers

        Returns:
            list[dict]: List of matching managers
        """
        if not db or 'managers' not in db:
            return []

        managers_data = db['managers']

        # Search through all companies for CIK match
        for _company_key, company_data in managers_data.items():
            company_cik = company_data.get('cik')
            if company_cik == cik:
                managers = company_data.get('managers', [])

                if include_approximate:
                    return managers
                else:
                    # Only return active managers unless requested otherwise
                    return [m for m in managers if m.get('status') == 'active']

        # No CIK matches found
        return []

    def get_manager_info_summary(self) -> dict:
        """
        Get a comprehensive summary of all available manager information.

        This provides a clear breakdown of what information is available from the 13F
        filing versus external sources, helping users understand the data limitations.

        Returns:
            dict: Summary with keys 'from_13f_filing', 'external_sources', 'limitations'

        Example:
            >>> thirteen_f.get_manager_info_summary()
            {
                'from_13f_filing': {
                    'management_company': 'Berkshire Hathaway Inc',
                    'filing_signer': 'Marc D. Hamburg',
                    'signer_title': 'Senior Vice President'
                },
                'external_sources': {
                    'portfolio_managers': [
                        {'name': 'Warren Buffett', 'title': 'Chairman & CEO', 'status': 'active'}
                    ]
                },
                'limitations': [
                    '13F filings do not contain individual portfolio manager names',
                    'External manager data may not be current or complete',
                    'Filing signer is typically an administrative officer, not the portfolio manager'
                ]
            }
        """
        portfolio_managers = self.get_portfolio_managers()

        return {
            'from_13f_filing': {
                'management_company': self.management_company_name,
                'filing_signer': self.filing_signer_name, 
                'signer_title': self.filing_signer_title,
                'form': self.form,
                'period_of_report': str(self.report_period)
            },
            'external_sources': {
                'portfolio_managers': portfolio_managers,
                'manager_count': len(portfolio_managers)
            },
            'limitations': [
                '13F filings do not contain individual portfolio manager names',
                'External manager data may not be current or complete', 
                'Filing signer is typically an administrative officer, not the portfolio manager',
                'Portfolio manager information is sourced from public records and may be outdated'
            ]
        }

    def is_filing_signer_likely_portfolio_manager(self) -> bool:
        """
        Determine if the filing signer is likely to be a portfolio manager.

        This uses heuristics based on the signer's title to assess whether they
        might be involved in investment decisions rather than just administrative functions.

        Returns:
            bool: True if signer appears to be investment-focused, False if administrative

        Example:
            >>> thirteen_f.is_filing_signer_likely_portfolio_manager()
            False  # For administrative titles like CFO, CCO, etc.
        """
        title = self.filing_signer_title.upper()

        # Investment-focused titles
        investment_titles = [
            'PORTFOLIO MANAGER', 'FUND MANAGER', 'INVESTMENT MANAGER',
            'CHIEF INVESTMENT OFFICER', 'CIO', 'MANAGING DIRECTOR', 
            'CHAIRMAN', 'CEO', 'PRESIDENT', 'FOUNDER'
        ]

        # Administrative titles
        admin_titles = [
            'CFO', 'CCO', 'COMPLIANCE', 'SECRETARY', 'TREASURER', 
            'VICE PRESIDENT', 'VP', 'ASSISTANT', 'COUNSEL'
        ]

        # Check for investment titles first
        for inv_title in investment_titles:
            if inv_title in title:
                return True

        # Check for administrative titles  
        for admin_title in admin_titles:
            if admin_title in title:
                return False

        # If unclear, err on the side of caution
        return False

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
        if summary_page_el:
            other_included_managers_count = child_text(summary_page_el,
                                                       "otherIncludedManagersCount")
            if other_included_managers_count:
                other_included_managers_count = int(other_included_managers_count)

            total_holdings = child_text(summary_page_el, "tableEntryTotal")
            if total_holdings:
                total_holdings = int(total_holdings)

            total_value = child_text(summary_page_el, "tableValueTotal")
            if total_value:
                total_value = Decimal(total_value)
        else:
            other_included_managers_count = 0
            total_holdings = 0
            total_value = 0

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
                other_included_managers_count=other_included_managers_count or 0,
                total_holdings=total_holdings or 0,
                total_value=total_value or 0
            ),
            additional_information=child_text(cover_page_el, "additionalInformation")
        )

        return parsed_primary_doc

    @staticmethod
    def parse_infotable_xml(infotable_xml: str) -> pd.DataFrame:
        """
        Parse the infotable xml and return a pandas DataFrame
        """
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

            info_table["PutCall"] = child_text(info_tag, "putCall") or ""
            info_table['InvestmentDiscretion'] = child_text(info_tag, "investmentDiscretion")

            # Voting authority
            voting_auth_tag = info_tag.find("votingAuthority")
            info_table['SoleVoting'] = int(float(child_text(voting_auth_tag, "Sole")))
            info_table['SharedVoting'] = int(float(child_text(voting_auth_tag, "Shared")))
            info_table['NonVoting'] = int(float(child_text(voting_auth_tag, "None")))
            rows.append(info_table)

        table = pd.DataFrame(rows)

        # Add the ticker symbol
        cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
        table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

        return table

    @staticmethod
    def parse_infotable_txt(infotable_txt: str) -> pd.DataFrame:
        """
        Parse the TXT format infotable (SGML table format used in 2012 and earlier).

        The TXT format uses SGML tags:
        - <TABLE> ... </TABLE> wraps each table
        - <CAPTION> contains column headers
        - First line has <S> and <C> tags marking column positions
        - Data rows have company names (may span 2 lines) followed by data fields

        Holdings data may be split across multiple tables. This parser combines all
        holdings tables after the "other managers" table.

        Returns a DataFrame with the same structure as parse_infotable_xml().
        """
        import re

        # Find the Form 13F Information Table section
        table_start = infotable_txt.find("Form 13F Information Table")
        if table_start == -1:
            return pd.DataFrame()

        # Extract all table content between <TABLE> and </TABLE> tags
        table_pattern = r'<TABLE>(.*?)</TABLE>'
        tables = re.findall(table_pattern, infotable_txt[table_start:], re.DOTALL)

        if len(tables) < 2:  # Need at least the managers table and one holdings table
            return pd.DataFrame()

        # Skip the first table (list of other managers) and process the rest
        # Holdings data may be split across multiple tables
        holdings_tables = tables[1:]  # Skip first table

        parsed_rows = []

        for holdings_table in holdings_tables:
            # Skip if this is the totals table (very short, < 200 chars)
            if len(holdings_table.strip()) < 200:
                continue

            # Reset pending issuer parts for each table
            pending_issuer_parts = []

            lines = holdings_table.split('\n')

            for line in lines:
                orig_line = line
                line = line.strip()

                # Skip empty lines, CAPTION lines, header rows
                if not line or '<CAPTION>' in line or '<S>' in line or '<C>' in line:
                    continue

                if line.startswith(('Total', 'Title', 'Name of Issuer', 'of', 'Market Value')):
                    continue

                # Try to parse as a data row
                # CUSIP is a reliable anchor - it's always 9 digits
                cusip_match = re.search(r'\b(\d{9})\b', line)

                if cusip_match:
                    # This line contains a CUSIP, so it has the main data
                    cusip = cusip_match.group(1)
                    cusip_pos = cusip_match.start()

                    # Everything before CUSIP is issuer name + class
                    before_cusip = line[:cusip_pos].strip()
                    # Everything after CUSIP is the numeric data
                    after_cusip = line[cusip_pos + 9:].strip()

                    # Split before_cusip into issuer parts
                    # Combine with any pending issuer parts from previous line
                    before_parts = before_cusip.split()

                    # If we have pending parts, this completes a multi-line company name
                    if pending_issuer_parts:
                        before_parts = pending_issuer_parts + before_parts
                        pending_issuer_parts = []

                    if len(before_parts) < 2:
                        # Not enough data, skip
                        continue

                    # Extract class and issuer name
                    # Common patterns:
                    # - "COMPANY NAME COM" → class="COM", issuer="COMPANY NAME"
                    # - "COMPANY NAME SPONSORED ADR" → class="SPONSORED ADR", issuer="COMPANY NAME"
                    # - "COMPANY NAME CL A" → class="CL A", issuer="COMPANY NAME"

                    if len(before_parts) >= 3 and before_parts[-2] == 'SPONSORED' and before_parts[-1] == 'ADR':
                        title_class = 'SPONSORED ADR'
                        issuer_parts = before_parts[:-2]
                    elif len(before_parts) >= 3 and before_parts[-2] == 'CL':
                        title_class = 'CL ' + before_parts[-1]
                        issuer_parts = before_parts[:-2]
                    elif len(before_parts) >= 5 and ' '.join(before_parts[-4:]).startswith('LIB CAP COM'):
                        # "LIBERTY MEDIA CORPORATION LIB CAP COM A"
                        title_class = ' '.join(before_parts[-4:])
                        issuer_parts = before_parts[:-4]
                    elif len(before_parts) >= 2:
                        # Default: last word/token is the class
                        title_class = before_parts[-1]
                        issuer_parts = before_parts[:-1]
                    else:
                        # Only one part - skip this row
                        continue

                    issuer_name = ' '.join(issuer_parts)

                    # Skip if issuer name is empty
                    if not issuer_name:
                        continue

                    # Parse the numeric data after CUSIP
                    # Expected format: VALUE SHARES DISCRETION MANAGERS SOLE SHARED NONE
                    # Example: "110,999     1,952,142 Shared-Defined 4           1,952,142       -   -"
                    data_parts = after_cusip.split()

                    if len(data_parts) < 7:
                        continue

                    try:
                        # Parse voting columns (always last 3 fields)
                        none_voting_str = data_parts[-1].replace(',', '')
                        shared_voting_str = data_parts[-2].replace(',', '')
                        sole_voting_str = data_parts[-3].replace(',', '')

                        non_voting = int(none_voting_str) if none_voting_str and none_voting_str != '-' else 0
                        shared_voting = int(shared_voting_str) if shared_voting_str and shared_voting_str != '-' else 0
                        sole_voting = int(sole_voting_str) if sole_voting_str and sole_voting_str != '-' else 0

                        # Find investment discretion by looking for non-numeric field
                        # It's typically "Shared-Defined", "Sole", "Defined", etc.
                        # Work backwards from position -4 (after voting columns)
                        discretion_idx = -4
                        for i in range(len(data_parts) - 4, -1, -1):
                            part = data_parts[i]
                            # Investment discretion contains letters (not just digits, commas, dashes)
                            if part and part not in ['-'] and not part.replace(',', '').isdigit():
                                discretion_idx = i
                                break

                        investment_discretion = data_parts[discretion_idx] if discretion_idx >= 0 else ''

                        # Value and Shares are the two fields before discretion
                        shares_idx = discretion_idx - 1
                        value_idx = discretion_idx - 2

                        if value_idx < 0 or shares_idx < 0:
                            continue  # Not enough fields

                        shares_str = data_parts[shares_idx].replace(',', '')
                        value_str = data_parts[value_idx].replace(',', '')

                        shares = int(shares_str) if shares_str and shares_str != '-' else 0
                        value = int(value_str) if value_str and value_str != '-' else 0

                        # Create row dict
                        row_dict = {
                            'Issuer': issuer_name,
                            'Class': title_class,
                            'Cusip': cusip,
                            'Value': value,
                            'SharesPrnAmount': shares,
                            'Type': 'Shares',
                            'PutCall': '',
                            'InvestmentDiscretion': investment_discretion,
                            'SoleVoting': sole_voting,
                            'SharedVoting': shared_voting,
                            'NonVoting': non_voting
                        }

                        parsed_rows.append(row_dict)

                    except (ValueError, IndexError):
                        # Skip rows that don't parse correctly
                        continue

                else:
                    # No CUSIP on this line - might be first part of a multi-line company name
                    # Store it for the next line
                    if line and not line.startswith(('Total', 'Title')):
                        pending_issuer_parts = line.split()

        # Create DataFrame
        if not parsed_rows:
            return pd.DataFrame()

        table = pd.DataFrame(parsed_rows)

        # Add ticker symbols using CUSIP mapping
        cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
        table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

        return table

    def _infotable_summary(self):
        if self.has_infotable():
            return (self.infotable
                    .filter(['Issuer', 'Class', 'Cusip', 'Ticker', 'Value', 'SharesPrnAmount', 'Type', 'PutCall',
                             'SoleVoting', 'SharedVoting', 'NonVoting'])
                    .rename(columns={'SharesPrnAmount': 'Shares'})
                    .assign(Value=lambda df: df.Value,
                            Type=lambda df: df.Type.fillna('-'),
                            Ticker=lambda df: df.Ticker.fillna(''))
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
            table = Table("", "Issuer", "Class", "Cusip", "Ticker", "Value", "Type", "Shares", "Put/Call",
                          row_styles=["bold", ""],
                          box=box.SIMPLE)
            for index, row in enumerate(self._infotable_summary().itertuples()):
                table.add_row(str(index),
                              row.Issuer,
                              row.Class,
                              row.Cusip,
                              row.Ticker,
                              f"${row.Value:,.0f}",
                              row.Type,
                              f"{int(row.Shares):,.0f}",
                              row.PutCall
                              )
            content.append(table)

        return Panel(
            Group(*content), title=title, subtitle=title
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
