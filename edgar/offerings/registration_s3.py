"""
S-3 Registration Statement data object.

Handles S-3, S-3/A, and S-3ASR shelf registration statements.
S-3 filings are typically short (50-200K chars) because they incorporate
financials by reference from existing 10-K/10-Q filings.

Key data:
  - Fee table (total offering capacity, per-security breakdowns)
  - Cover page (filer category, state of incorporation, EIN)
  - Offering type classification (universal shelf / resale / S-3ASR)
  - Forward navigation to 424B takedowns
"""

from __future__ import annotations

import logging
import re
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

__all__ = ['RegistrationS3', 'S3OfferingType', 'S3CoverPage']

# ---------------------------------------------------------------------------
# Offering Type
# ---------------------------------------------------------------------------

class S3OfferingType(str, Enum):
    """Classification of S-3 registration types."""
    UNIVERSAL_SHELF = "universal_shelf"
    RESALE = "resale"
    DEBT = "debt"
    AUTO_SHELF = "auto_shelf"  # S-3ASR
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return {
            "universal_shelf": "Universal Shelf",
            "resale": "Resale Registration",
            "debt": "Debt Offering",
            "auto_shelf": "Automatic Shelf (S-3ASR)",
            "unknown": "Unknown",
        }[self.value]


# ---------------------------------------------------------------------------
# Cover Page Model
# ---------------------------------------------------------------------------

class S3CoverPage(BaseModel):
    """Extracted cover page fields from an S-3 filing."""
    company_name: str
    registration_number: Optional[str] = None
    state_of_incorporation: Optional[str] = None
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
    is_rule_462e: bool = False  # Auto-shelf

    # Extraction confidence
    confidence: str = "low"  # low, medium, high


# ---------------------------------------------------------------------------
# Cover Page Extraction
# ---------------------------------------------------------------------------

# Unicode check marks: ☒ (checked) = \u2612, ☑ = \u2611, ✓, ✔, ☐ (unchecked) = \u2610
_CHECKED = re.compile(r'[\u2611\u2612\u2713\u2714]|&#9746;|&#9745;')
_UNCHECKED = re.compile(r'[\u2610]|&#9744;')


def _is_checked(text: str, label: str) -> Optional[bool]:
    """Check if a labeled checkbox is checked or unchecked in cover page text.

    SEC filings place checkmarks either before or after the label, often
    separated by HTML tags.  We search a 200-char window in both directions.
    """
    pattern = re.compile(re.escape(label), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    # Look 200 chars after the label (checkmark often follows, separated by HTML)
    after_region = text[match.end():match.end() + 200]
    # Look 200 chars before the label
    before_region = text[max(0, match.start() - 200):match.start()]

    # Find the nearest checkmark in either direction
    after_checked = _CHECKED.search(after_region)
    after_unchecked = _UNCHECKED.search(after_region)
    before_checked = _CHECKED.search(before_region)
    before_unchecked = _UNCHECKED.search(before_region)

    # Prefer the closest mark to the label
    # After-label marks
    after_pos = None
    after_val = None
    if after_checked:
        after_pos = after_checked.start()
        after_val = True
    if after_unchecked and (after_pos is None or after_unchecked.start() < after_pos):
        after_pos = after_unchecked.start()
        after_val = False

    # Before-label marks (distance from end of before_region = closer to label)
    before_pos = None
    before_val = None
    if before_checked:
        before_pos = len(before_region) - before_checked.end()
        before_val = True
    if before_unchecked:
        dist = len(before_region) - before_unchecked.end()
        if before_pos is None or dist < before_pos:
            before_pos = dist
            before_val = False

    # Return whichever mark is closest to the label
    if after_pos is not None and before_pos is not None:
        return after_val if after_pos <= before_pos else before_val
    if after_pos is not None:
        return after_val
    if before_pos is not None:
        return before_val
    return None


def _extract_s3_cover_page(filing: 'Filing', html: str) -> S3CoverPage:
    """Extract cover page fields from S-3 HTML."""
    cover_text = html[:25000]

    # Company name from filing metadata
    company_name = filing.company

    # Registration number: 333-XXXXXX
    reg_match = re.search(r'333-(\d{5,7})', cover_text)
    registration_number = f"333-{reg_match.group(1)}" if reg_match else None

    # State of incorporation — appears in a table cell above "(State or other jurisdiction..."
    # Pattern: look for text content in the same column, just before the jurisdiction label
    state_of_incorporation = None
    state_label_match = re.search(
        r'State\s+or\s+other\s+jurisdiction',
        cover_text, re.IGNORECASE
    )
    if state_label_match:
        # Look backwards in the HTML for a text value (state name)
        before = cover_text[max(0, state_label_match.start() - 500):state_label_match.start()]
        # Find bold text content (typically <B>Delaware</B>) or plain text between tags
        state_candidates = re.findall(r'<[Bb]>([A-Z][A-Za-z\s]{2,30}?)</[Bb]>', before)
        if not state_candidates:
            # Try plain text between closing and opening tags
            state_candidates = re.findall(r'>([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)<', before)
        if state_candidates:
            # Take the last one (closest to the label)
            state_of_incorporation = state_candidates[-1].strip()

    # EIN
    ein_match = re.search(r'(\d{2}-\d{7})', cover_text)
    ein = ein_match.group(1) if ein_match else None

    # Filer category checkboxes
    # SEC filings use &nbsp; (\xa0), normal spaces, or HTML entity &nbsp; interchangeably.
    # Try all three variants for each label.
    def _check_label(text, label):
        """Try a label with normal spaces, \xa0, and &nbsp;."""
        result = _is_checked(text, label)
        if result is None:
            result = _is_checked(text, label.replace(' ', '\xa0'))
        if result is None:
            result = _is_checked(text, label.replace(' ', '&nbsp;'))
        return result

    is_large_accelerated = _check_label(cover_text, 'Large accelerated filer')
    is_accelerated = _check_label(cover_text, 'Accelerated filer')
    is_non_accelerated = _check_label(cover_text, 'Non-accelerated filer')
    is_smaller_reporting = _check_label(cover_text, 'Smaller reporting company')
    is_egc = _check_label(cover_text, 'Emerging growth company')

    # Rule checkboxes
    is_rule_415 = bool(_check_label(cover_text, 'Rule 415'))
    is_rule_462b = bool(_check_label(cover_text, 'Rule 462(b)'))
    is_rule_462e = bool(_check_label(cover_text, 'Rule 462(e)')) or 'S-3ASR' in filing.form

    # Confidence
    fields_found = sum(1 for v in [registration_number, state_of_incorporation, ein,
                                    is_large_accelerated, is_smaller_reporting] if v is not None)
    confidence = "high" if fields_found >= 4 else "medium" if fields_found >= 2 else "low"

    return S3CoverPage(
        company_name=company_name,
        registration_number=registration_number,
        state_of_incorporation=state_of_incorporation,
        ein=ein,
        is_large_accelerated_filer=is_large_accelerated,
        is_accelerated_filer=is_accelerated,
        is_non_accelerated_filer=is_non_accelerated,
        is_smaller_reporting_company=is_smaller_reporting,
        is_emerging_growth_company=is_egc,
        is_rule_415=is_rule_415,
        is_rule_462b=is_rule_462b,
        is_rule_462e=is_rule_462e,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Offering Type Classification
# ---------------------------------------------------------------------------

def _classify_s3_offering(filing: 'Filing', fee_table, html: Optional[str] = None) -> S3OfferingType:
    """Classify the S-3 offering type."""
    # S-3ASR is always auto-shelf
    if 'ASR' in filing.form:
        return S3OfferingType.AUTO_SHELF

    # Check fee table for clues
    if fee_table and fee_table.fee_deferred:
        return S3OfferingType.AUTO_SHELF

    # Check HTML for resale indicators
    if html is None:
        html = filing.html()
    if html:
        cover = html[:30000].lower()
        if 'resale' in cover or 'selling stockholder' in cover or 'selling securityholder' in cover:
            return S3OfferingType.RESALE
        if 'debt securities' in cover and 'common stock' not in cover and 'preferred stock' not in cover:
            return S3OfferingType.DEBT

    return S3OfferingType.UNIVERSAL_SHELF


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RegistrationS3:
    """
    Data object for S-3 registration statement filings.

    Handles S-3, S-3/A, and S-3ASR forms. S-3 filings are short shelf
    registrations that incorporate financials by reference from 10-K/10-Q.

    Construction via from_filing() or filing.obj():
        filing = find("S-3 accession number")
        s3 = filing.obj()  # Returns RegistrationS3
        s3 = RegistrationS3.from_filing(filing)

    Key properties:
        s3.cover_page          -> S3CoverPage
        s3.offering_type       -> S3OfferingType enum
        s3.fee_table           -> RegistrationFeeTable | None
        s3.total_offering      -> float | None (total registered amount)
        s3.takedowns           -> Filings (424B filings under this shelf)
    """

    def __init__(self, filing: 'Filing', cover_page: S3CoverPage,
                 offering_type: S3OfferingType, fee_table=None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._fee_table = fee_table

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'RegistrationS3':
        """Primary entry point. Extracts cover page, fee table, and offering type."""
        from edgar.offerings._fee_table import extract_registration_fee_table

        # Extract fee table first (used by classifier)
        try:
            fee_table = extract_registration_fee_table(filing)
        except Exception:
            fee_table = None

        # Extract cover page
        html = filing.html()
        cover_page = _extract_s3_cover_page(filing, html) if html else S3CoverPage(
            company_name=filing.company
        )

        # Classify offering type (reuse html to avoid second network call)
        offering_type = _classify_s3_offering(filing, fee_table, html=html)

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
    def cover_page(self) -> S3CoverPage:
        return self._cover_page

    @property
    def offering_type(self) -> S3OfferingType:
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
    def is_auto_shelf(self) -> bool:
        return 'ASR' in self._filing.form or self._offering_type == S3OfferingType.AUTO_SHELF

    @property
    def registration_number(self) -> Optional[str]:
        return self._cover_page.registration_number

    @property
    def state_of_incorporation(self) -> Optional[str]:
        return self._cover_page.state_of_incorporation

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
    def fee_deferred(self) -> bool:
        """Whether fees are deferred (S-3ASR pattern)."""
        if self._fee_table:
            return self._fee_table.fee_deferred
        return False

    @property
    def securities(self) -> List:
        """Per-security breakdowns from the fee table."""
        if self._fee_table:
            return self._fee_table.securities
        return []

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

    @cached_property
    def takedowns(self) -> Optional['Filings']:
        """424B filings issued under this shelf registration.

        Navigates forward from S-3 → 424B takedowns using the
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
            # Filter to only 424B forms
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

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        cp = self._cover_page
        lines = [
            f"REGISTRATION STATEMENT: {self.company} ({self.form})",
            "",
            f"Filed: {self.filing_date}",
            f"Offering Type: {self._offering_type.display_name}",
        ]

        if cp.registration_number:
            lines.append(f"Registration No.: {cp.registration_number}")
        if cp.state_of_incorporation:
            lines.append(f"State: {cp.state_of_incorporation}")
        if cp.ein:
            lines.append(f"EIN: {cp.ein}")

        flags = []
        if self.is_auto_shelf:
            flags.append("AUTO-SHELF")
        if self.is_amendment:
            flags.append("AMENDMENT")
        if cp.is_rule_415:
            flags.append("Rule 415")
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
            if self.fee_deferred:
                lines.append("  Fee Status: Deferred (S-3ASR)")
            for sec in self.securities[:5]:
                title = sec.security_title or sec.security_type or "Security"
                amt = f"${sec.max_aggregate_amount:,.2f}" if sec.max_aggregate_amount else "TBD"
                lines.append(f"  - {title}: {amt}")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .cover_page -> S3CoverPage (filer info, checkboxes)")
            lines.append("  - .fee_table -> RegistrationFeeTable (offering capacity)")
            lines.append("  - .total_offering -> float (total registered amount)")
            lines.append("  - .takedowns -> Filings (424B filings under this shelf)")
            lines.append("  - .related_filings -> Filings (all filings, same file number)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self._offering_type.display_name}"

        # Cover page table
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
        if cp.ein:
            t.add_row("EIN", cp.ein)

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
        if self.is_auto_shelf:
            flags.append("[green]AUTO-SHELF[/green]")
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
            if self.fee_deferred:
                ft.add_row("Fee Status", "Deferred")
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
            f"RegistrationS3("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"offering_type={self._offering_type.value!r}, "
            f"date={self.filing_date!r})"
        )
