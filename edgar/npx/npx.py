"""
N-PX Filing support for SEC proxy voting record filings.

Form N-PX is filed annually by registered investment companies (mutual funds) to report
how they voted on proxy matters for securities they held during the most recent 12-month
period ending June 30.

This module provides the main NPX class that integrates N-PX parsing with the Filing system.
"""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

from .models import (
    IncludedManager,
    PrimaryDoc,
    ProxyTable,
    ReportSeriesClassInfo,
    SeriesReport,
)
from .parsing import (
    PrimaryDocExtractor,
    ProxyVoteTableExtractor,
)

if TYPE_CHECKING:
    from edgar._filings import Filing

log = logging.getLogger(__name__)

__all__ = ['NPX', 'ProxyVotes', 'IncludedManager', 'ReportSeriesClassInfo', 'SeriesReport']


@dataclass
class ProxyVotes:
    """Container for proxy voting data with convenience methods."""

    proxy_tables: List[ProxyTable]

    def __len__(self) -> int:
        return len(self.proxy_tables)

    def __iter__(self):
        return iter(self.proxy_tables)

    def __getitem__(self, item):
        return self.proxy_tables[item]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert proxy vote data to a pandas DataFrame.

        Returns a DataFrame with one row per vote record, including all fields
        from the ProxyTable and VoteRecord dataclasses:

        ProxyTable fields:
        - issuer_name: Company that held the shareholder meeting
        - cusip: CUSIP security identifier
        - isin: ISIN security identifier
        - figi: FIGI security identifier
        - meeting_date: Date of shareholder meeting
        - vote_description: Description of the vote matter
        - other_vote_description: Additional vote description details
        - total_shares_voted: Total number of shares voted on this matter
        - shares_on_loan: Number of shares on loan
        - vote_source: Source of the vote
        - vote_series: Series information for the vote
        - vote_other_info: Additional vote information
        - vote_categories: Categories of the vote (comma-separated)
        - other_managers: Other managers involved (comma-separated)

        VoteRecord fields (one row per vote record):
        - how_voted: How the fund voted (FOR, AGAINST, ABSTAIN, etc.)
        - shares_voted: Number of shares voted in this record
        - management_recommendation: Management's recommendation
        """
        records = []
        for proxy_table in self.proxy_tables:
            # Build base record with all ProxyTable fields
            base_record = {
                # Required fields
                'issuer_name': proxy_table.issuer_name,
                'meeting_date': proxy_table.meeting_date,
                'vote_description': proxy_table.vote_description,
                'total_shares_voted': proxy_table.shares_voted,
                'shares_on_loan': proxy_table.shares_on_loan,
                # Optional identifier fields
                'cusip': proxy_table.cusip,
                'isin': proxy_table.isin,
                'figi': proxy_table.figi,
                # Optional descriptive fields
                'other_vote_description': proxy_table.other_vote_description,
                'vote_source': proxy_table.vote_source,
                'vote_series': proxy_table.vote_series,
                'vote_other_info': proxy_table.vote_other_info,
                # Flattened list fields
                'vote_categories': ', '.join(vc.category_type for vc in proxy_table.vote_categories) if proxy_table.vote_categories else None,
                'other_managers': ', '.join(proxy_table.other_managers) if proxy_table.other_managers else None,
            }

            if proxy_table.vote_records:
                for vote_record in proxy_table.vote_records:
                    record = base_record.copy()
                    record.update({
                        'how_voted': vote_record.how_voted,
                        'shares_voted': vote_record.shares_voted,
                        'management_recommendation': vote_record.management_recommendation,
                    })
                    records.append(record)
            else:
                # No vote records, still include the proxy table info
                # Add empty vote record fields for consistency
                base_record.update({
                    'how_voted': None,
                    'shares_voted': None,
                    'management_recommendation': None,
                })
                records.append(base_record)

        return pd.DataFrame(records)

    def filter_by_issuer(self, issuer_name: str) -> 'ProxyVotes':
        """Filter votes by issuer name (case-insensitive partial match)."""
        issuer_lower = issuer_name.lower()
        filtered = [pt for pt in self.proxy_tables if issuer_lower in pt.issuer_name.lower()]
        return ProxyVotes(proxy_tables=filtered)

    def filter_by_vote(self, how_voted: str) -> 'ProxyVotes':
        """Filter to proxy tables containing votes matching the specified vote type.

        Args:
            how_voted: Vote type to filter by (FOR, AGAINST, ABSTAIN, WITHHOLD, etc.)

        Returns:
            ProxyVotes containing only matters with matching vote records.
        """
        how_voted_upper = how_voted.upper()
        filtered = [
            pt for pt in self.proxy_tables
            if any(vr.how_voted.upper() == how_voted_upper for vr in pt.vote_records)
        ]
        return ProxyVotes(proxy_tables=filtered)

    def filter_by_category(self, category: str) -> 'ProxyVotes':
        """Filter votes by vote category (case-insensitive partial match).

        Args:
            category: Category to filter by. Common categories include:
                - DIRECTOR ELECTIONS
                - SECTION 14A SAY-ON-PAY VOTES
                - AUDIT-RELATED
                - COMPENSATION
                - ENVIRONMENT OR CLIMATE
                - CORPORATE GOVERNANCE
                - OTHER

        Returns:
            ProxyVotes containing only matters matching the category.

        Example:
            >>> climate_votes = npx.proxy_votes.filter_by_category("CLIMATE")
            >>> esg_votes = npx.proxy_votes.filter_by_category("ENVIRONMENT")
        """
        category_lower = category.lower()
        filtered = [
            pt for pt in self.proxy_tables
            if any(category_lower in vc.category_type.lower() for vc in pt.vote_categories)
        ]
        return ProxyVotes(proxy_tables=filtered)

    def against_management(self) -> 'ProxyVotes':
        """Filter to proxy tables where votes went against management recommendation.

        Returns proxy tables containing at least one vote record where how_voted
        differs from management_recommendation.

        Returns:
            ProxyVotes containing only matters with votes against management.

        Example:
            >>> dissent_votes = npx.proxy_votes.against_management()
            >>> print(f"Fund voted against management {len(dissent_votes)} times")
        """
        filtered = []
        for pt in self.proxy_tables:
            for vr in pt.vote_records:
                # Normalize for comparison (handle FOR vs FOR, AGAINST vs AGAINST, etc.)
                how_voted = vr.how_voted.upper() if vr.how_voted else ""
                mgmt_rec = vr.management_recommendation.upper() if vr.management_recommendation else ""

                # Skip if either is empty or "NONE"
                if not how_voted or not mgmt_rec or mgmt_rec == "NONE":
                    continue

                # Check for mismatch
                if how_voted != mgmt_rec:
                    filtered.append(pt)
                    break  # Only need one dissenting vote to include this proxy table

        return ProxyVotes(proxy_tables=filtered)

    def management_alignment_rate(self) -> float:
        """Calculate the rate at which votes align with management recommendations.

        Returns:
            Float between 0.0 and 1.0 representing the alignment rate.
            Returns 1.0 if there are no vote records with management recommendations.

        Example:
            >>> alignment = npx.proxy_votes.management_alignment_rate()
            >>> print(f"Fund aligned with management {alignment:.1%} of the time")
        """
        aligned_count = 0
        total_count = 0

        for pt in self.proxy_tables:
            for vr in pt.vote_records:
                how_voted = vr.how_voted.upper() if vr.how_voted else ""
                mgmt_rec = vr.management_recommendation.upper() if vr.management_recommendation else ""

                # Skip if either is empty or management has no recommendation
                if not how_voted or not mgmt_rec or mgmt_rec == "NONE":
                    continue

                total_count += 1
                if how_voted == mgmt_rec:
                    aligned_count += 1

        if total_count == 0:
            return 1.0  # No votes with recommendations = 100% alignment (vacuously true)

        return aligned_count / total_count

    def summary_by_category(self) -> pd.DataFrame:
        """Get a summary of voting patterns grouped by vote category.

        Returns a DataFrame with columns:
        - category: The vote category type
        - total_votes: Number of vote records in this category
        - for_votes: Number of FOR votes
        - against_votes: Number of AGAINST votes
        - abstain_votes: Number of ABSTAIN votes
        - other_votes: Number of other vote types (WITHHOLD, etc.)
        - with_management: Votes aligned with management
        - against_management: Votes against management

        Example:
            >>> summary = npx.proxy_votes.summary_by_category()
            >>> print(summary)
        """
        category_stats = {}

        for pt in self.proxy_tables:
            # Get categories for this proxy table
            categories = [vc.category_type for vc in pt.vote_categories] if pt.vote_categories else ["UNCATEGORIZED"]

            for category in categories:
                if category not in category_stats:
                    category_stats[category] = {
                        'total_votes': 0,
                        'for_votes': 0,
                        'against_votes': 0,
                        'abstain_votes': 0,
                        'other_votes': 0,
                        'with_management': 0,
                        'against_management': 0,
                    }

                stats = category_stats[category]

                for vr in pt.vote_records:
                    stats['total_votes'] += 1

                    how_voted = vr.how_voted.upper() if vr.how_voted else ""
                    mgmt_rec = vr.management_recommendation.upper() if vr.management_recommendation else ""

                    # Count by vote type
                    if how_voted == "FOR":
                        stats['for_votes'] += 1
                    elif how_voted == "AGAINST":
                        stats['against_votes'] += 1
                    elif how_voted == "ABSTAIN":
                        stats['abstain_votes'] += 1
                    else:
                        stats['other_votes'] += 1

                    # Count management alignment
                    if mgmt_rec and mgmt_rec != "NONE":
                        if how_voted == mgmt_rec:
                            stats['with_management'] += 1
                        else:
                            stats['against_management'] += 1

        # Convert to DataFrame
        records = [
            {'category': cat, **stats}
            for cat, stats in sorted(category_stats.items(), key=lambda x: -x[1]['total_votes'])
        ]

        return pd.DataFrame(records) if records else pd.DataFrame(columns=[
            'category', 'total_votes', 'for_votes', 'against_votes',
            'abstain_votes', 'other_votes', 'with_management', 'against_management'
        ])

    def summary(self) -> pd.DataFrame:
        """Get a summary of voting patterns.

        Returns a DataFrame with vote counts by how_voted type.
        """
        vote_counts = {}
        for proxy_table in self.proxy_tables:
            for vote_record in proxy_table.vote_records:
                vote_type = vote_record.how_voted.upper()
                vote_counts[vote_type] = vote_counts.get(vote_type, 0) + 1

        return pd.DataFrame([
            {'vote_type': k, 'count': v}
            for k, v in sorted(vote_counts.items(), key=lambda x: -x[1])
        ])

    def __rich__(self):
        if not self.proxy_tables:
            return Text("No proxy votes found", style="dim")

        table = Table(
            title=f"Proxy Votes ({len(self.proxy_tables)} matters)",
            box=box.SIMPLE,
            show_header=True,
        )
        table.add_column("Issuer", style="bold", max_width=30, overflow="ellipsis", no_wrap=True)
        table.add_column("CUSIP", style="dim")
        table.add_column("Meeting Date")
        table.add_column("Description", max_width=35, overflow="ellipsis", no_wrap=True)
        table.add_column("Votes", justify="right")

        for pt in self.proxy_tables[:20]:  # Show first 20
            vote_summary = ", ".join(
                f"{vr.how_voted}: {vr.shares_voted:,.0f}"
                for vr in pt.vote_records[:2]  # Show first 2 vote records
            )
            if len(pt.vote_records) > 2:
                vote_summary += f" (+{len(pt.vote_records) - 2} more)"

            # Get security identifier (prefer CUSIP, fallback to ISIN or FIGI)
            security_id = pt.cusip or pt.isin or pt.figi or ""

            table.add_row(
                pt.issuer_name,
                security_id,
                pt.meeting_date,
                pt.vote_description,
                vote_summary or f"{pt.shares_voted:,.0f} shares",
            )

        if len(self.proxy_tables) > 20:
            table.add_row("", "", "", f"... and {len(self.proxy_tables) - 20} more", "")

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class NPX:
    """
    Form N-PX - Annual Report of Proxy Voting Record.

    N-PX filings are submitted by registered investment companies (mutual funds)
    to report their proxy voting record for the 12-month period ending June 30.

    The filing contains:
    - Primary document: Fund information, reporting period, signatures
    - Proxy vote table: Individual voting records for each security/matter voted on

    Usage:
        >>> filing = Company("VANGUARD").get_filings(form="N-PX")[0]
        >>> npx = filing.obj()
        >>> npx.fund_name
        'Vanguard Index Funds'
        >>> npx.proxy_votes.to_dataframe()
        # DataFrame with all voting records
    """

    def __init__(
        self,
        primary_doc: PrimaryDoc,
        proxy_votes: Optional[ProxyVotes] = None,
        filing: Optional['Filing'] = None
    ):
        self._primary_doc = primary_doc
        self._proxy_votes = proxy_votes
        self._filing = filing

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['NPX']:
        """
        Create an NPX instance from a Filing object.

        Args:
            filing: An SEC Filing object for an N-PX form

        Returns:
            NPX instance or None if parsing fails
        """
        # Get primary document XML
        primary_xml = filing.xml()
        if not primary_xml:
            log.warning("No primary XML found in N-PX filing %s", filing.accession_no)
            return None

        try:
            # Parse primary document
            primary_doc_extractor = PrimaryDocExtractor(primary_xml.encode('utf-8'))
            primary_doc = primary_doc_extractor.extract()
        except (ValueError, Exception) as e:
            log.error("Failed to parse N-PX primary document: %s", e)
            return None

        # Try to find and parse proxy vote table
        proxy_votes = cls._extract_proxy_votes(filing)

        return cls(
            primary_doc=primary_doc,
            proxy_votes=proxy_votes,
            filing=filing,
        )

    @classmethod
    def _extract_proxy_votes(cls, filing: 'Filing') -> Optional[ProxyVotes]:
        """Extract proxy vote table from filing attachments."""
        try:
            attachments = filing.attachments

            # Look for proxy vote table XML in attachments
            # Common patterns: infotable.xml, *table*.xml, or XML files in data_files
            proxy_xml_content = None

            # Check data_files first (where info tables typically are)
            if attachments.data_files:
                for attachment in attachments.data_files:
                    doc_lower = attachment.document.lower()
                    if attachment.display_extension == '.xml':
                        # Look for info table patterns
                        if any(pattern in doc_lower for pattern in ['infotable', 'table', 'proxy']):
                            content = attachment.content
                            if content and 'proxyVoteTable' in content:
                                proxy_xml_content = content
                                break

            # If not found in data_files, check regular documents
            if not proxy_xml_content:
                for attachment in attachments.documents:
                    if attachment.display_extension == '.xml':
                        doc_lower = attachment.document.lower()
                        # Skip the primary doc
                        if 'primary' in doc_lower:
                            continue
                        content = attachment.content
                        if content and 'proxyVoteTable' in content:
                            proxy_xml_content = content
                            break

            if proxy_xml_content:
                if isinstance(proxy_xml_content, str):
                    proxy_xml_content = proxy_xml_content.encode('utf-8')

                extractor = ProxyVoteTableExtractor(proxy_xml_content)
                proxy_vote_table = extractor.extract()
                return ProxyVotes(proxy_tables=proxy_vote_table.proxy_tables)

        except Exception as e:
            log.warning("Failed to extract proxy vote table: %s", e)

        return None

    # Primary document properties
    @property
    def fund_name(self) -> Optional[str]:
        """Name of the reporting fund."""
        return self._primary_doc.fund_name

    @property
    def cik(self) -> str:
        """CIK (Central Index Key) of the filer."""
        return self._primary_doc.cik

    @property
    def period_of_report(self) -> str:
        """Reporting period end date."""
        return self._primary_doc.period_of_report

    @property
    def report_calendar_year(self) -> str:
        """Calendar year of the report."""
        return self._primary_doc.report_calendar_year

    @property
    def submission_type(self) -> str:
        """Form type (N-PX or N-PX/A for amendments)."""
        return self._primary_doc.submission_type

    @property
    def is_amendment(self) -> bool:
        """Whether this is an amendment filing."""
        return self._primary_doc.is_amendment or False

    @property
    def signer_name(self) -> str:
        """Name of the person who signed the filing."""
        return self._primary_doc.signer_name

    @property
    def signer_title(self) -> str:
        """Title of the person who signed the filing."""
        return self._primary_doc.signer_title

    @property
    def signature_date(self) -> str:
        """Date the filing was signed."""
        return self._primary_doc.signature_date

    @property
    def address(self) -> str:
        """Formatted address of the reporting person."""
        parts = [self._primary_doc.street1]
        if self._primary_doc.street2:
            parts.append(self._primary_doc.street2)
        parts.append(f"{self._primary_doc.city}, {self._primary_doc.state} {self._primary_doc.zip_code}")
        return "\n".join(parts)

    @property
    def agent_for_service_name(self) -> Optional[str]:
        """Name of the agent for service."""
        return self._primary_doc.agent_for_service_name

    @property
    def agent_for_service_address(self) -> Optional[str]:
        """Formatted address of the agent for service."""
        if not self._primary_doc.agent_for_service_address_street1:
            return None

        parts = [self._primary_doc.agent_for_service_address_street1]
        if self._primary_doc.agent_for_service_address_street2:
            parts.append(self._primary_doc.agent_for_service_address_street2)

        city_state_zip = []
        if self._primary_doc.agent_for_service_address_city:
            city_state_zip.append(self._primary_doc.agent_for_service_address_city)
        if self._primary_doc.agent_for_service_address_state_country:
            city_state_zip.append(self._primary_doc.agent_for_service_address_state_country)
        if self._primary_doc.agent_for_service_address_zip_code:
            city_state_zip.append(self._primary_doc.agent_for_service_address_zip_code)

        if city_state_zip:
            parts.append(", ".join(city_state_zip))

        return "\n".join(parts)

    @property
    def agent_for_service_address_street1(self) -> Optional[str]:
        """Street 1 of agent for service address."""
        return self._primary_doc.agent_for_service_address_street1

    @property
    def agent_for_service_address_street2(self) -> Optional[str]:
        """Street 2 of agent for service address."""
        return self._primary_doc.agent_for_service_address_street2

    @property
    def agent_for_service_address_city(self) -> Optional[str]:
        """City of agent for service address."""
        return self._primary_doc.agent_for_service_address_city

    @property
    def agent_for_service_address_state_country(self) -> Optional[str]:
        """State or country of agent for service address."""
        return self._primary_doc.agent_for_service_address_state_country

    @property
    def agent_for_service_address_zip_code(self) -> Optional[str]:
        """ZIP code of agent for service address."""
        return self._primary_doc.agent_for_service_address_zip_code

    @property
    def phone_number(self) -> Optional[str]:
        """Phone number of the reporting person."""
        return self._primary_doc.phone_number

    @property
    def crd_number(self) -> Optional[str]:
        """CRD (Central Registration Depository) number."""
        return self._primary_doc.crd_number

    @property
    def filer_sec_file_number(self) -> Optional[str]:
        """SEC file number of the filer."""
        return self._primary_doc.filer_sec_file_number

    @property
    def lei_number(self) -> Optional[str]:
        """LEI (Legal Entity Identifier) number."""
        return self._primary_doc.lei_number

    @property
    def report_type(self) -> Optional[str]:
        """Type of report (FUND VOTING REPORT, MANAGER VOTING REPORT, etc.)."""
        return self._primary_doc.report_type

    @property
    def confidential_treatment(self) -> Optional[str]:
        """Confidential treatment flag (Y/N)."""
        return self._primary_doc.confidential_treatment

    @property
    def notice_explanation(self) -> Optional[str]:
        """Notice explanation text."""
        return self._primary_doc.notice_explanation

    @property
    def npx_file_number(self) -> Optional[str]:
        """N-PX file number."""
        return self._primary_doc.npx_file_number

    @property
    def explanatory_choice(self) -> Optional[str]:
        """Explanatory choice flag."""
        return self._primary_doc.explanatory_choice

    @property
    def other_included_managers_count(self) -> Optional[str]:
        """Count of other included managers."""
        return self._primary_doc.other_included_managers_count

    @property
    def tx_printed_signature(self) -> Optional[str]:
        """Printed signature text."""
        return self._primary_doc.tx_printed_signature

    @property
    def amendment_no(self) -> Optional[str]:
        """Amendment number if this is an amendment filing."""
        return self._primary_doc.amendment_no

    @property
    def amendment_type(self) -> Optional[str]:
        """Type of amendment."""
        return self._primary_doc.amendment_type

    @property
    def de_novo_request_choice(self) -> Optional[str]:
        """De novo request choice."""
        return self._primary_doc.de_novo_request_choice

    @property
    def year_or_quarter(self) -> Optional[str]:
        """Year or quarter indicator (YEAR or QUARTER)."""
        return self._primary_doc.year_or_quarter

    @property
    def conf_denied_expired(self) -> Optional[str]:
        """Confidential treatment denied/expired flag."""
        return self._primary_doc.conf_denied_expired

    @property
    def registrant_type(self) -> Optional[str]:
        """Registrant type (RMIC, IA, etc.)."""
        return self._primary_doc.registrant_type

    @property
    def live_test_flag(self) -> Optional[str]:
        """Live/Test flag (LIVE or TEST)."""
        return self._primary_doc.live_test_flag

    @property
    def contact_name(self) -> Optional[str]:
        """Contact person name."""
        return self._primary_doc.contact_name

    @property
    def contact_phone_number(self) -> Optional[str]:
        """Contact phone number."""
        return self._primary_doc.contact_phone_number

    @property
    def contact_email_address(self) -> Optional[str]:
        """Contact email address."""
        return self._primary_doc.contact_email_address

    @property
    def investment_company_type(self) -> Optional[str]:
        """Investment company type (N-1A, N-2, etc.)."""
        return self._primary_doc.investment_company_type

    @property
    def series_count(self) -> Optional[str]:
        """Number of series in the filing."""
        return self._primary_doc.series_count

    @property
    def included_managers(self) -> List['IncludedManager']:
        """List of other investment managers included in this filing."""
        return self._primary_doc.included_managers

    @property
    def report_series_class_infos(self) -> List['ReportSeriesClassInfo']:
        """List of series/class information for reporting."""
        return self._primary_doc.report_series_class_infos

    @property
    def series_reports(self) -> List['SeriesReport']:
        """List of series report details."""
        return self._primary_doc.series_reports

    @property
    def proxy_votes(self) -> Optional[ProxyVotes]:
        """Proxy voting records from the filing."""
        return self._proxy_votes

    @property
    def primary_doc(self) -> PrimaryDoc:
        """Raw primary document data."""
        return self._primary_doc

    @property
    def filing(self) -> Optional['Filing']:
        """The source Filing object."""
        return self._filing

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the primary document data to a pandas DataFrame.

        Returns a DataFrame with one row containing all metadata fields from the N-PX filing.
        For proxy vote data, use `npx.proxy_votes.to_dataframe()` instead.
        """
        data = {
            'cik': self.cik,
            'fund_name': self.fund_name,
            'period_of_report': self.period_of_report,
            'report_calendar_year': self.report_calendar_year,
            'submission_type': self.submission_type,
            'is_amendment': self.is_amendment,
            'report_type': self.report_type,
            'npx_file_number': self.npx_file_number,
            'lei_number': self.lei_number,
            'crd_number': self.crd_number,
            'investment_company_type': self.investment_company_type,
            'year_or_quarter': self.year_or_quarter,
            'signer_name': self.signer_name,
            'signer_title': self.signer_title,
            'signature_date': self.signature_date,
            'address': self.address,
            'phone_number': self.phone_number,
            'agent_for_service_name': self.agent_for_service_name,
            'agent_for_service_address': self.agent_for_service_address,
            'contact_name': self.contact_name,
            'contact_phone_number': self.contact_phone_number,
            'contact_email_address': self.contact_email_address,
            'confidential_treatment': self.confidential_treatment,
            'other_included_managers_count': self.other_included_managers_count,
            'series_count': self.series_count,
            'proxy_vote_count': len(self._proxy_votes) if self._proxy_votes else 0,
        }
        return pd.DataFrame([data])

    def __str__(self) -> str:
        vote_count = len(self._proxy_votes) if self._proxy_votes else 0
        amendment = " (Amendment)" if self.is_amendment else ""
        fund_display = self.fund_name or "Unknown Fund"
        return f"N-PX{amendment}: {fund_display} - {self.period_of_report} ({vote_count} votes)"

    def __rich__(self):
        # Header panel
        title = Text()
        title.append("Form N-PX", style="bold blue")
        if self.is_amendment:
            title.append(" (Amendment)", style="yellow")
        title.append(f" - {self.fund_name or 'Unknown Fund'}", style="bold")

        # Info table
        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Field", style="dim")
        info_table.add_column("Value")

        info_table.add_row("CIK", self.cik)
        info_table.add_row("Period", self.period_of_report)
        info_table.add_row("Calendar Year", self.report_calendar_year)
        if self.report_type:
            info_table.add_row("Report Type", self.report_type)
        if self.npx_file_number:
            info_table.add_row("File Number", self.npx_file_number)
        if self.lei_number:
            info_table.add_row("LEI", self.lei_number)
        if self.investment_company_type:
            info_table.add_row("Company Type", self.investment_company_type)
        info_table.add_row("Signed By", f"{self.signer_name} ({self.signer_title})")
        info_table.add_row("Signature Date", self.signature_date)

        if self._proxy_votes:
            info_table.add_row("Proxy Votes", f"{len(self._proxy_votes):,} matters")

        # Show included managers count if present
        if self.other_included_managers_count and self.other_included_managers_count != "0":
            info_table.add_row("Other Managers", self.other_included_managers_count)

        # Show series count if present
        if self.series_count and self.series_count != "0":
            info_table.add_row("Series", self.series_count)

        header_panel = Panel(
            info_table,
            title=title,
            border_style="blue",
        )

        # Proxy votes summary
        elements = [header_panel]

        if self._proxy_votes and len(self._proxy_votes) > 0:
            elements.append(Text())  # Spacer
            elements.append(self._proxy_votes.__rich__())

        return Group(*elements)

    def __repr__(self):
        return repr_rich(self.__rich__())
