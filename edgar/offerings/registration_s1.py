"""
S-1 Registration Statement data object.

Handles S-1 and S-1/A registration statement filings.
S-1 filings are full registration statements used for IPOs, SPAC offerings,
resale registrations, and debt offerings. Unlike S-3 (which incorporates
financials by reference), S-1s often contain complete financial statements.

Key data:
  - Cover page (state of incorporation, EIN, SIC code, filer category)
  - Offering type classification (IPO / SPAC / Resale / Debt / Follow-On)
  - Fee table (total offering capacity, per-security breakdowns)
  - Table extraction (dilution, capitalization, selling stockholders, underwriting)
  - Forward navigation to 424B takedowns
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from pydantic import BaseModel
from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing, Filings
    from edgar.offerings.prospectus import (
        DilutionData, CapitalizationData, SellingStockholdersData, UnderwritingInfo,
    )

__all__ = ['RegistrationS1', 'S1OfferingType', 'S1CoverPage']

# ---------------------------------------------------------------------------
# Offering Type
# ---------------------------------------------------------------------------


class S1OfferingType(str, Enum):
    """Classification of S-1 registration sub-types."""
    IPO = "ipo"
    SPAC = "spac"
    RESALE = "resale"
    DEBT = "debt"
    FOLLOW_ON = "follow_on"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            "ipo": "Initial Public Offering",
            "spac": "SPAC IPO",
            "resale": "Resale Registration",
            "debt": "Debt Offering",
            "follow_on": "Follow-On Offering",
            "unknown": "Unknown",
        }[self.value]


# ---------------------------------------------------------------------------
# Cover Page Model
# ---------------------------------------------------------------------------


class S1CoverPage(BaseModel):
    """Extracted cover page fields from an S-1 filing."""
    company_name: str
    registration_number: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    sic_code: Optional[str] = None
    ein: Optional[str] = None

    # Filer category checkboxes
    is_large_accelerated_filer: Optional[bool] = None
    is_accelerated_filer: Optional[bool] = None
    is_non_accelerated_filer: Optional[bool] = None
    is_smaller_reporting_company: Optional[bool] = None
    is_emerging_growth_company: Optional[bool] = None

    # Rule checkboxes
    is_rule_415: bool = False
    is_rule_462b: bool = False
    is_rule_462e: bool = False

    # Security description from cover page
    security_description: Optional[str] = None

    # Extraction confidence
    confidence: str = "low"  # low, medium, high


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class RegistrationS1:
    """
    Data object for S-1 registration statement filings.

    Handles S-1 and S-1/A forms. S-1 filings are full registration
    statements used for IPOs, SPAC offerings, resale registrations,
    and debt offerings.

    Construction via from_filing() or filing.obj():
        filing = find("S-1 accession number")
        s1 = filing.obj()  # Returns RegistrationS1
        s1 = RegistrationS1.from_filing(filing)

    Key properties:
        s1.cover_page          -> S1CoverPage
        s1.offering_type       -> S1OfferingType enum
        s1.fee_table           -> RegistrationFeeTable | None
        s1.total_offering      -> float | None (total registered amount)
        s1.selling_stockholders -> SellingStockholdersData | None
        s1.dilution            -> DilutionData | None
        s1.capitalization      -> CapitalizationData | None
        s1.takedowns           -> Filings (424B filings under this shelf)
    """

    def __init__(self, filing: 'Filing', cover_page: S1CoverPage,
                 offering_type: S1OfferingType, fee_table=None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._fee_table = fee_table

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'RegistrationS1':
        """Primary entry point. Extracts cover page, fee table, and offering type."""
        from edgar.offerings._fee_table import extract_registration_fee_table
        from edgar.offerings._s1_cover import extract_s1_cover_page
        from edgar.offerings._s1_classifier import classify_s1_offering_type

        # Fetch HTML once
        html = filing.html() or ''

        # Extract fee table
        try:
            fee_table = extract_registration_fee_table(filing)
        except Exception:
            fee_table = None

        # Extract cover page
        cover_fields = extract_s1_cover_page(filing, html=html)
        cover_page = S1CoverPage(**cover_fields)

        # Classify offering type
        classification = classify_s1_offering_type(filing, html=html)
        try:
            offering_type = S1OfferingType(classification['type'])
        except ValueError:
            offering_type = S1OfferingType.UNKNOWN

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            fee_table=fee_table,
        )

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def cover_page(self) -> S1CoverPage:
        return self._cover_page

    @property
    def offering_type(self) -> S1OfferingType:
        return self._offering_type

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        return self._filing.accession_no

    @property
    def is_amendment(self) -> bool:
        return '/A' in self._filing.form

    @property
    def registration_number(self) -> Optional[str]:
        return self._cover_page.registration_number

    @property
    def state_of_incorporation(self) -> Optional[str]:
        return self._cover_page.state_of_incorporation

    @property
    def sic_code(self) -> Optional[str]:
        return self._cover_page.sic_code

    @property
    def ein(self) -> Optional[str]:
        return self._cover_page.ein

    # ------------------------------------------------------------------
    # Fee table
    # ------------------------------------------------------------------

    @property
    def fee_table(self):
        """Registration fee table from Exhibit 107."""
        return self._fee_table

    @property
    def total_offering(self) -> Optional[float]:
        """Total registered offering amount in dollars."""
        if self._fee_table:
            return self._fee_table.total_offering_amount
        return None

    @property
    def net_fee(self) -> Optional[float]:
        """Net registration fee due."""
        if self._fee_table:
            return self._fee_table.net_fee_due
        return None

    @property
    def securities(self) -> List:
        """Per-security breakdowns from the fee table."""
        if self._fee_table:
            return self._fee_table.securities
        return []

    # ------------------------------------------------------------------
    # Table extraction (lazy, reuses _424b_tables.py extractors)
    # ------------------------------------------------------------------

    @cached_property
    def _document(self):
        """Parsed document for table extraction."""
        try:
            return self._filing.parse()
        except Exception:
            return None

    @cached_property
    def _classified_tables(self) -> dict:
        """Classified tables from the filing document."""
        if self._document is None:
            return {}
        try:
            from edgar.offerings._424b_tables import classify_tables_in_document
            return classify_tables_in_document(self._document)
        except Exception:
            return {}

    @cached_property
    def selling_stockholders(self) -> Optional['SellingStockholdersData']:
        """Selling stockholders data (primarily for resale registrations)."""
        tables = self._classified_tables.get('selling_stockholders', [])
        if not tables:
            return None
        try:
            from edgar.offerings._424b_tables import extract_selling_stockholders_data
            return extract_selling_stockholders_data(tables[0])
        except Exception:
            return None

    @cached_property
    def dilution(self) -> Optional['DilutionData']:
        """Dilution data (primarily for IPO registrations)."""
        tables = self._classified_tables.get('dilution', [])
        if not tables:
            return None
        try:
            from edgar.offerings._424b_tables import extract_dilution_data
            return extract_dilution_data(tables[0])
        except Exception:
            return None

    @cached_property
    def capitalization(self) -> Optional['CapitalizationData']:
        """Capitalization data (primarily for IPO registrations)."""
        tables = self._classified_tables.get('capitalization', [])
        if not tables:
            return None
        try:
            from edgar.offerings._424b_tables import extract_capitalization_data
            return extract_capitalization_data(tables[0])
        except Exception:
            return None

    @cached_property
    def underwriting(self) -> Optional['UnderwritingInfo']:
        """Underwriting information."""
        if self._document is None:
            return None
        try:
            from edgar.offerings._424b_tables import extract_underwriting_from_tables
            from edgar.offerings.prospectus import UnderwritingInfo, UnderwriterEntry
            raw = extract_underwriting_from_tables(self._document)
            if not raw:
                return None
            # Build UnderwritingInfo from the raw extraction
            all_names = []
            for entry in raw:
                for name in entry.get('names', []):
                    all_names.append(UnderwriterEntry(name=name))
            if all_names:
                return UnderwritingInfo(underwriters=all_names)
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

    @cached_property
    def takedowns(self) -> Optional['Filings']:
        """424B filings issued under this registration.

        Navigates forward from S-1 -> 424B takedowns using the
        registration file number to link filings.
        """
        file_number = self._cover_page.registration_number
        if not file_number:
            return None

        try:
            from edgar.entity import Company
            company = Company(self._filing.cik)
            related = company.get_filings(
                file_number=file_number,
                sort_by=[("filing_date", "ascending")],
                trigger_full_load=False,
            )
            if related is None or related.empty:
                return None
            takedown_forms = ['424B1', '424B2', '424B3', '424B4', '424B5', '424B7', '424B8']
            takedowns = related.filter(form=takedown_forms)
            return takedowns if takedowns and not takedowns.empty else None
        except Exception as e:
            log.debug("Failed to get takedowns for %s: %s", self._filing.accession_no, e)
            return None

    @cached_property
    def related_filings(self) -> Optional['Filings']:
        """All filings under the same registration file number."""
        file_number = self._cover_page.registration_number
        if not file_number:
            return None

        try:
            from edgar.entity import Company
            company = Company(self._filing.cik)
            return company.get_filings(
                file_number=file_number,
                sort_by=[("filing_date", "ascending")],
                trigger_full_load=False,
            )
        except Exception as e:
            log.debug("Failed to get related filings for %s: %s", self._filing.accession_no, e)
            return None

    @cached_property
    def effective_date(self) -> Optional[str]:
        """Date the registration was declared effective (from EFFECT filing)."""
        related = self.related_filings
        if related is None:
            return None
        try:
            effects = related.filter(form='EFFECT')
            if effects and not effects.empty:
                return str(effects[0].filing_date)
        except Exception:
            pass
        return None

    @property
    def is_effective(self) -> bool:
        """Whether this registration has been declared effective."""
        return self.effective_date is not None

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        cp = self._cover_page
        lines = [
            f"S-1 REGISTRATION STATEMENT: {self.company} ({self.form})",
            "",
            f"Filed: {self.filing_date}",
            f"Offering Type: {self._offering_type.display_name}",
        ]

        if cp.registration_number:
            lines.append(f"Registration No.: {cp.registration_number}")
        if cp.state_of_incorporation:
            lines.append(f"State: {cp.state_of_incorporation}")
        if cp.sic_code:
            lines.append(f"SIC Code: {cp.sic_code}")
        if cp.ein:
            lines.append(f"EIN: {cp.ein}")
        if cp.security_description:
            lines.append(f"Securities: {cp.security_description}")

        flags = []
        if self.is_amendment:
            flags.append("AMENDMENT")
        if cp.is_rule_415:
            flags.append("Rule 415 (Delayed/Continuous)")
        if self.is_effective:
            flags.append(f"EFFECTIVE ({self.effective_date})")
        if flags:
            lines.append(f"Status: {' | '.join(flags)}")

        # Filer category
        categories = []
        if cp.is_large_accelerated_filer:
            categories.append("Large Accelerated Filer")
        if cp.is_accelerated_filer:
            categories.append("Accelerated Filer")
        if cp.is_non_accelerated_filer:
            categories.append("Non-Accelerated Filer")
        if cp.is_smaller_reporting_company:
            categories.append("Smaller Reporting Company")
        if cp.is_emerging_growth_company:
            categories.append("Emerging Growth Company")
        if categories:
            lines.append(f"Filer Category: {', '.join(categories)}")

        lines.append(f"Extraction Confidence: {cp.confidence}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Fee table
        if self._fee_table:
            lines.append("")
            lines.append("FEE TABLE:")
            if self.total_offering is not None:
                lines.append(f"  Total Offering: ${self.total_offering:,.2f}")
            if self.net_fee is not None:
                lines.append(f"  Net Fee: ${self.net_fee:,.2f}")
            for sec in self.securities[:5]:
                title = sec.security_title or sec.security_type or "Security"
                amt = f"${sec.max_aggregate_amount:,.2f}" if sec.max_aggregate_amount else "TBD"
                lines.append(f"  - {title}: {amt}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> S1CoverPage (filer info, checkboxes, SIC)")
            lines.append("  - .fee_table -> RegistrationFeeTable (offering capacity)")
            lines.append("  - .total_offering -> float (total registered amount)")
            lines.append("  - .offering_type -> S1OfferingType (ipo/spac/resale/debt)")
            lines.append("  - .selling_stockholders -> SellingStockholdersData")
            lines.append("  - .dilution -> DilutionData")
            lines.append("  - .capitalization -> CapitalizationData")
            lines.append("  - .underwriting -> UnderwritingInfo")
            lines.append("  - .takedowns -> Filings (424B filings under this registration)")
            lines.append("  - .related_filings -> Filings (all filings, same file number)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self._offering_type.display_name}"

        cp = self._cover_page
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Offering Type", self._offering_type.display_name)
        if cp.registration_number:
            t.add_row("Registration No.", cp.registration_number)
        if cp.state_of_incorporation:
            t.add_row("State", cp.state_of_incorporation)
        if cp.sic_code:
            t.add_row("SIC Code", cp.sic_code)
        if cp.ein:
            t.add_row("EIN", cp.ein)
        if cp.security_description:
            t.add_row("Securities", cp.security_description)

        # Filer category
        categories = []
        if cp.is_large_accelerated_filer:
            categories.append("Large Accelerated Filer")
        if cp.is_accelerated_filer:
            categories.append("Accelerated Filer")
        if cp.is_non_accelerated_filer:
            categories.append("Non-Accelerated Filer")
        if cp.is_smaller_reporting_company:
            categories.append("Smaller Reporting")
        if cp.is_emerging_growth_company:
            categories.append("EGC")
        if categories:
            t.add_row("Filer Category", ", ".join(categories))

        # Status flags
        flags = []
        if self.is_amendment:
            flags.append("[yellow]AMENDMENT[/yellow]")
        if cp.is_rule_415:
            flags.append("Rule 415")
        if flags:
            t.add_row("Status", " | ".join(flags))

        t.add_row("Confidence", cp.confidence)

        renderables = [t]

        # Fee table
        if self._fee_table:
            ft = Table(box=box.SIMPLE, padding=(0, 1), title="Fee Table")
            ft.add_column("Field", style="bold")
            ft.add_column("Value", justify="right", style="deep_sky_blue1")

            if self.total_offering is not None:
                ft.add_row("Total Offering", f"${self.total_offering:,.2f}")
            if self.net_fee is not None:
                ft.add_row("Net Fee", f"${self.net_fee:,.2f}")
            ft.add_row("Securities", str(len(self.securities)))

            renderables.append(Text(""))
            renderables.append(ft)

        return Panel(
            Group(*renderables),
            title=f"[bold]{title}[/bold]",
            subtitle=subtitle,
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return (
            f"RegistrationS1("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
