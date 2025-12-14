"""
Form 10-D Asset-Backed Securities Distribution Report.

Form 10-D is an Asset-Backed Issuer Distribution Report required by Sections 13 and 15(d)
of the Securities Exchange Act of 1934. It discloses distribution and pool performance
data for publicly offered asset-backed securities (ABS).

Filing Categories:
- CMBS (Commercial Mortgage-Backed Securities) - includes XML asset data in EX-102
- Auto Loan/Lease ABS - asset data in separate ABS-EE filings
- Credit Card ABS - HTML-only distribution reports
- RMBS (Residential Mortgage-Backed Securities)
- Student Loan ABS
- Utility Securitizations
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import cached_property
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

__all__ = ['TenD', 'ABSType', 'ABSEntity', 'DistributionPeriod']


class ABSType(Enum):
    """Types of Asset-Backed Securities."""
    CMBS = "CMBS"  # Commercial Mortgage-Backed Securities
    AUTO = "AUTO"  # Auto Loan/Lease
    CREDIT_CARD = "CREDIT_CARD"
    RMBS = "RMBS"  # Residential Mortgage-Backed Securities
    STUDENT_LOAN = "STUDENT_LOAN"
    UTILITY = "UTILITY"
    OTHER = "OTHER"


@dataclass
class ABSEntity:
    """Entity involved in an ABS transaction (issuer, depositor, or sponsor)."""
    name: str
    cik: Optional[str] = None
    file_number: Optional[str] = None

    def __str__(self):
        return self.name


@dataclass
class DistributionPeriod:
    """Distribution period for the 10-D filing."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def __str__(self):
        if self.start_date and self.end_date:
            return f"{self.start_date.strftime('%b %d, %Y')} to {self.end_date.strftime('%b %d, %Y')}"
        return "Unknown period"


class TenD:
    """
    Form 10-D Asset-Backed Securities Distribution Report.

    Provides access to ABS distribution report data including:
    - Issuing entity, depositor, and sponsor information
    - Distribution period dates
    - Security class registrations
    - ABS type detection (CMBS, Auto, Credit Card, etc.)

    For CMBS filings, provides access to:
    - EX-102 XML asset-level loan and property data
    - EX-103 XML comments/notes

    Example:
        >>> from edgar import Filing
        >>> filing = Filing(form='10-D', cik=2032772, accession_number='0001888524-25-020550')
        >>> ten_d = filing.obj()
        >>> ten_d.issuing_entity
        ABSEntity(name='BANK5 2024-5YR9', cik='0002032772')
        >>> ten_d.abs_type
        <ABSType.CMBS: 'CMBS'>
    """

    def __init__(self, filing):
        """
        Initialize TenD from a Filing object.

        Args:
            filing: A Filing object for a 10-D form
        """
        if filing.form not in ('10-D', '10-D/A'):
            raise ValueError(f"Expected 10-D filing, got {filing.form}")
        self._filing = filing
        self._soup = None
        self._header_parsed = False
        self._issuing_entity: Optional[ABSEntity] = None
        self._depositor: Optional[ABSEntity] = None
        self._sponsors: List[ABSEntity] = []
        self._distribution_period: Optional[DistributionPeriod] = None
        self._security_classes: List[str] = []

    @property
    def filing(self):
        """The underlying Filing object."""
        return self._filing

    @property
    def form(self) -> str:
        """Form type (10-D or 10-D/A)."""
        return self._filing.form

    @property
    def company(self) -> str:
        """Company name from the filing."""
        return self._filing.company

    @property
    def filing_date(self) -> date:
        """Filing date."""
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        """Accession number."""
        return self._filing.accession_number

    @cached_property
    def _parsed_html(self) -> BeautifulSoup:
        """Parse the main HTML document."""
        html = self._filing.html()
        return BeautifulSoup(html, 'html.parser')

    def _ensure_header_parsed(self):
        """Parse the header section of the 10-D to extract entity info."""
        if self._header_parsed:
            return

        soup = self._parsed_html
        text = soup.get_text(separator='\n')

        # Extract issuing entity
        self._issuing_entity = self._extract_issuing_entity(text, soup)

        # Extract depositor
        self._depositor = self._extract_depositor(text, soup)

        # Extract sponsors
        self._sponsors = self._extract_sponsors(text, soup)

        # Extract distribution period
        self._distribution_period = self._extract_distribution_period(text)

        # Extract security classes
        self._security_classes = self._extract_security_classes(soup)

        self._header_parsed = True

    def _extract_issuing_entity(self, text: str, soup: BeautifulSoup) -> Optional[ABSEntity]:
        """Extract issuing entity information from the filing header."""
        name = None
        cik = None
        file_number = None

        # Look for issuing entity CIK pattern
        cik_match = re.search(
            r'Central Index Key Number of issuing entity[:\s]*(\d+)',
            text,
            re.IGNORECASE
        )
        if cik_match:
            cik = cik_match.group(1).lstrip('0') or '0'

        # Look for commission file number
        file_match = re.search(
            r'Commission File Number of issuing entity[:\s]*([\d-]+)',
            text,
            re.IGNORECASE
        )
        if file_match:
            file_number = file_match.group(1)

        # Look for issuing entity name (appears after CIK, before "(Exact name...")
        name_match = re.search(
            r'Central Index Key Number of issuing entity[:\s]*\d+\s*([^\(]+?)\s*\(Exact name of issuing entity',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if name_match:
            name = name_match.group(1).strip()
            # Clean up any leftover whitespace/newlines
            name = ' '.join(name.split())

        if name:
            return ABSEntity(name=name, cik=cik, file_number=file_number)
        return None

    def _extract_depositor(self, text: str, soup: BeautifulSoup) -> Optional[ABSEntity]:
        """Extract depositor information from the filing header."""
        name = None
        cik = None
        file_number = None

        # Look for depositor CIK pattern
        cik_match = re.search(
            r'Central Index Key Number of depositor[:\s]*(\d+)',
            text,
            re.IGNORECASE
        )
        if cik_match:
            cik = cik_match.group(1).lstrip('0') or '0'

        # Look for commission file number
        file_match = re.search(
            r'Commission File Number of depositor[:\s]*([\d-]+)',
            text,
            re.IGNORECASE
        )
        if file_match:
            file_number = file_match.group(1)

        # Look for depositor name
        name_match = re.search(
            r'Central Index Key Number of depositor[:\s]*\d+\s*([^\(]+?)\s*\(Exact name of depositor',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if name_match:
            name = name_match.group(1).strip()
            name = ' '.join(name.split())

        if name:
            return ABSEntity(name=name, cik=cik, file_number=file_number)
        return None

    def _extract_sponsors(self, text: str, soup: BeautifulSoup) -> List[ABSEntity]:
        """Extract sponsor information from the filing header."""
        sponsors = []

        # Find all sponsor CIK patterns and their names
        sponsor_pattern = re.compile(
            r'Central Index Key Number of sponsor[^:]*[:\s]*(\d+)\s*([^\(]+?)\s*\(Exact name of sponsor',
            re.IGNORECASE | re.DOTALL
        )

        for match in sponsor_pattern.finditer(text):
            cik = match.group(1).lstrip('0') or '0'
            name = match.group(2).strip()
            name = ' '.join(name.split())
            if name:
                sponsors.append(ABSEntity(name=name, cik=cik))

        return sponsors

    def _extract_distribution_period(self, text: str) -> Optional[DistributionPeriod]:
        """Extract distribution period dates from the filing header."""
        # Pattern: "For the monthly distribution period from: October 21, 2025 to November 18, 2025"
        period_match = re.search(
            r'distribution period from[:\s]*([A-Za-z]+\s+\d+,?\s+\d{4})\s*to\s*([A-Za-z]+\s+\d+,?\s+\d{4})',
            text,
            re.IGNORECASE
        )

        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)

            start_date = self._parse_date_string(start_str)
            end_date = self._parse_date_string(end_str)

            return DistributionPeriod(start_date=start_date, end_date=end_date)

        return None

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """Parse a date string in formats like 'October 21, 2025' or 'October 21 2025'."""
        from datetime import datetime

        # Normalize the date string
        date_str = date_str.strip()

        # Try common formats
        formats = [
            '%B %d, %Y',  # October 21, 2025
            '%B %d %Y',   # October 21 2025
            '%b %d, %Y',  # Oct 21, 2025
            '%b %d %Y',   # Oct 21 2025
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _extract_security_classes(self, soup: BeautifulSoup) -> List[str]:
        """Extract registered security classes from the filing."""
        classes = []

        # Look for the security class table
        tables = soup.find_all('table')
        for table in tables:
            header_row = table.find('tr')
            if header_row:
                header_text = header_row.get_text(separator=' ').lower()
                if 'title of class' in header_text:
                    # Found the security class table
                    rows = table.find_all('tr')[1:]  # Skip header
                    for row in rows:
                        cells = row.find_all('td')
                        if cells:
                            class_name = cells[0].get_text(strip=True)
                            if class_name and class_name not in classes:
                                classes.append(class_name)
                    break

        return classes

    @property
    def issuing_entity(self) -> Optional[ABSEntity]:
        """The issuing entity for the ABS."""
        self._ensure_header_parsed()
        return self._issuing_entity

    @property
    def depositor(self) -> Optional[ABSEntity]:
        """The depositor for the ABS."""
        self._ensure_header_parsed()
        return self._depositor

    @property
    def sponsors(self) -> List[ABSEntity]:
        """List of sponsors for the ABS."""
        self._ensure_header_parsed()
        return self._sponsors

    @property
    def distribution_period(self) -> Optional[DistributionPeriod]:
        """The distribution period covered by this filing."""
        self._ensure_header_parsed()
        return self._distribution_period

    @property
    def security_classes(self) -> List[str]:
        """List of security classes registered in this filing."""
        self._ensure_header_parsed()
        return self._security_classes

    @cached_property
    def abs_type(self) -> ABSType:
        """
        Detect the type of ABS based on filing characteristics.

        Detection logic:
        - CMBS: Has EX-102 XML asset data file
        - AUTO: Company name contains auto/vehicle/lease keywords
        - CREDIT_CARD: Company name contains credit card/receivables keywords
        - STUDENT_LOAN: Company name contains student loan keywords
        - UTILITY: Company name contains utility/restoration keywords
        """
        # Check for CMBS by looking for EX-102 asset data
        attachments = self._filing.attachments
        for attachment in attachments:
            if attachment.document_type and 'EX-102' in attachment.document_type.upper():
                return ABSType.CMBS

        # Check company name for keywords
        company_lower = self.company.lower() if self.company else ''
        issuer_lower = self.issuing_entity.name.lower() if self.issuing_entity else ''
        combined = f"{company_lower} {issuer_lower}"

        if any(kw in combined for kw in ['auto', 'vehicle', 'car', 'motor', 'fleet', 'lease receivable']):
            return ABSType.AUTO

        if any(kw in combined for kw in ['credit card', 'card receivable', 'charge card']):
            return ABSType.CREDIT_CARD

        if any(kw in combined for kw in ['student loan', 'education loan']):
            return ABSType.STUDENT_LOAN

        if any(kw in combined for kw in ['mortgage', 'rmbs', 'residential']):
            return ABSType.RMBS

        if any(kw in combined for kw in ['utility', 'restoration', 'securitization funding', 'ratepayer']):
            return ABSType.UTILITY

        return ABSType.OTHER

    @cached_property
    def has_asset_data(self) -> bool:
        """Check if this filing has XML asset-level data (typically CMBS)."""
        attachments = self._filing.attachments
        for attachment in attachments:
            if attachment.document_type and 'EX-102' in attachment.document_type.upper():
                return True
        return False

    def _get_exhibit(self, exhibit_type: str) -> Optional[str]:
        """Get the content of a specific exhibit type."""
        attachments = self._filing.attachments
        for attachment in attachments:
            if attachment.document_type and exhibit_type.upper() in attachment.document_type.upper():
                return attachment.text()
        return None

    def __str__(self):
        issuer_name = self.issuing_entity.name if self.issuing_entity else self.company
        return f"TenD('{issuer_name}')"

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Rich console representation."""
        self._ensure_header_parsed()

        # Build title
        title = Text.assemble(
            (self.issuing_entity.name if self.issuing_entity else self.company, "bold deep_sky_blue1"),
            (" ", ""),
            (f"Form {self.form}", "bold"),
        )

        # Create info table
        info_table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        info_table.add_column("Label", style="grey70")
        info_table.add_column("Value")

        # ABS Type
        info_table.add_row("ABS Type", Text(self.abs_type.value, style="bold cyan"))

        # Distribution Period
        if self.distribution_period:
            info_table.add_row("Distribution Period", str(self.distribution_period))

        # Filing Date
        info_table.add_row("Filing Date", self.filing_date.strftime("%B %d, %Y"))

        # Depositor
        if self.depositor:
            depositor_text = Text.assemble(
                (self.depositor.name, ""),
                (f" (CIK: {self.depositor.cik})" if self.depositor.cik else "", "dim"),
            )
            info_table.add_row("Depositor", depositor_text)

        # Sponsors
        if self.sponsors:
            for i, sponsor in enumerate(self.sponsors):
                label = "Sponsor" if i == 0 else ""
                sponsor_text = Text.assemble(
                    (sponsor.name, ""),
                    (f" (CIK: {sponsor.cik})" if sponsor.cik else "", "dim"),
                )
                info_table.add_row(label, sponsor_text)

        # Security Classes (limit display)
        if self.security_classes:
            classes_display = ", ".join(self.security_classes[:5])
            if len(self.security_classes) > 5:
                classes_display += f" (+{len(self.security_classes) - 5} more)"
            info_table.add_row("Security Classes", classes_display)

        # Asset Data indicator
        if self.has_asset_data:
            info_table.add_row("Asset Data", Text("Available (EX-102)", style="green"))

        panel = Panel(
            Group(info_table),
            title=title,
            box=box.ROUNDED,
        )
        return panel
