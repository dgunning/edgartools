"""
DRS Draft Registration Statement data object.

Handles DRS and DRS/A (Draft Registration Statement) filings.
DRS filings are confidential draft submissions to the SEC that become
publicly visible once the issuer proceeds with a public registration.

The EDGAR metadata only says "DRS" or "DRS/A" — the underlying form type
(S-1, F-1, S-3, S-4, 20-F, Form 10, etc.) must be detected from the
document cover page text.

Key data:
  - Underlying form type (S-1, F-1, S-3, S-4, 20-F, Form 10, etc.)
  - Amendment status and number
  - Registration number (377-XXXXXX prefix)
  - Delegation to underlying data object where available (e.g., RegistrationS1)
"""

from __future__ import annotations

import logging
import re
from typing import Optional, TYPE_CHECKING

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['DraftRegistrationStatement']

# ---------------------------------------------------------------------------
# Underlying form detection
# ---------------------------------------------------------------------------

# Ordered by specificity: check compound patterns before simple ones.
# S-4/F-4 before S-3/F-3 before S-1/F-1 to avoid prefix collisions.
_FORM_PATTERNS = [
    (r'FORM\s+S-4', 'S-4'),
    (r'FORM\s+F-4', 'F-4'),
    (r'FORM\s+S-3', 'S-3'),
    (r'FORM\s+F-3', 'F-3'),
    (r'FORM\s+F-1', 'F-1'),
    (r'FORM\s+S-1', 'S-1'),
    (r'FORM\s+20-F', '20-F'),
    (r'FORM\s+40-F', '40-F'),
    (r'GENERAL\s+FORM\s+FOR\s+REGISTRATION\s+OF\s+SECURITIES', 'Form 10'),
    (r'FORM\s+10\b', 'Form 10'),
]

_AMENDMENT_RE = re.compile(
    r'Amendment\s+No\.?\s*(\d+)',
    re.IGNORECASE,
)


def _detect_underlying_form(html: str) -> tuple[str, Optional[int]]:
    """Detect the underlying form type from DRS HTML content.

    Returns (form_type, amendment_number). form_type is 'Unknown' if
    detection fails. amendment_number is None if not an amendment or
    the number cannot be determined.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator=' ', strip=True)
    cover = text[:8000]

    # Detect form type
    form_type = 'Unknown'
    for pattern, form in _FORM_PATTERNS:
        if re.search(pattern, cover, re.IGNORECASE):
            form_type = form
            break

    # Detect amendment number
    amendment_number = None
    m = _AMENDMENT_RE.search(cover)
    if m:
        amendment_number = int(m.group(1))

    return form_type, amendment_number


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class DraftRegistrationStatement:
    """
    Data object for DRS (Draft Registration Statement) filings.

    Handles DRS and DRS/A forms. DRS filings are confidential draft
    submissions that become publicly visible on EDGAR once the company
    files a public registration statement.

    Construction via from_filing() or filing.obj():
        filing = find("DRS accession number")
        drs = filing.obj()  # Returns DraftRegistrationStatement
        drs = DraftRegistrationStatement.from_filing(filing)

    Key properties:
        drs.underlying_form     -> str ('S-1', 'F-1', 'S-4', etc.)
        drs.is_amendment        -> bool
        drs.amendment_number    -> int | None
        drs.registration_number -> str | None (377-XXXXXX)
        drs.underlying_object   -> RegistrationS1 | RegistrationS3 | None
    """

    def __init__(self, filing: 'Filing', underlying_form: str,
                 amendment_number: Optional[int] = None,
                 registration_number: Optional[str] = None,
                 underlying_object=None):
        self._filing = filing
        self._underlying_form = underlying_form
        self._amendment_number = amendment_number
        self._registration_number = registration_number
        self._underlying_object = underlying_object

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'DraftRegistrationStatement':
        """Primary entry point. Detects underlying form and delegates where possible."""
        html = filing.html() or ''

        # Detect underlying form type and amendment number
        underlying_form, amendment_number = _detect_underlying_form(html)

        # Extract registration number from filing header
        registration_number = None
        try:
            header = filing.header
            if hasattr(header, 'file_numbers') and header.file_numbers:
                for fn in header.file_numbers:
                    if fn.startswith('377-'):
                        registration_number = fn
                        break
        except Exception:
            pass

        # Fallback: extract registration number from HTML
        if not registration_number and html:
            m = re.search(r'377-\d{5,7}', html)
            if m:
                registration_number = m.group(0)

        # Build underlying data object for supported form types
        underlying_object = None
        if underlying_form in ('S-1', 'F-1'):
            try:
                from edgar.offerings.registration_s1 import RegistrationS1
                underlying_object = RegistrationS1.from_filing(filing)
            except Exception:
                log.debug("Failed to build RegistrationS1 for DRS %s", filing.accession_no)
        elif underlying_form in ('S-3',):
            try:
                from edgar.offerings.registration_s3 import RegistrationS3
                underlying_object = RegistrationS3.from_filing(filing)
            except Exception:
                log.debug("Failed to build RegistrationS3 for DRS %s", filing.accession_no)

        return cls(
            filing=filing,
            underlying_form=underlying_form,
            amendment_number=amendment_number,
            registration_number=registration_number,
            underlying_object=underlying_object,
        )

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def underlying_form(self) -> str:
        """The detected underlying form type (e.g., 'S-1', 'F-1', 'S-4')."""
        return self._underlying_form

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def company_name(self) -> str:
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
    def amendment_number(self) -> Optional[int]:
        """Amendment number (e.g., 2 for 'Amendment No. 2'), or None."""
        return self._amendment_number

    @property
    def registration_number(self) -> Optional[str]:
        """DRS registration number (377-XXXXXX prefix)."""
        return self._registration_number

    @property
    def underlying_object(self):
        """Delegated data object (RegistrationS1, RegistrationS3, or None)."""
        return self._underlying_object

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        lines = [
            f"DRS DRAFT REGISTRATION STATEMENT: {self.company} ({self.form})",
            "",
            f"Filed: {self.filing_date}",
            f"Underlying Form: {self._underlying_form}",
        ]

        if self._registration_number:
            lines.append(f"Registration No.: {self._registration_number}")

        flags = []
        if self.is_amendment:
            flag = "AMENDMENT"
            if self._amendment_number is not None:
                flag += f" No. {self._amendment_number}"
            flags.append(flag)
        if flags:
            lines.append(f"Status: {' | '.join(flags)}")

        if detail == 'minimal':
            return "\n".join(lines)

        # Include underlying object context if available
        if self._underlying_object and hasattr(self._underlying_object, 'to_context'):
            lines.append("")
            lines.append("UNDERLYING REGISTRATION DETAILS:")
            lines.append(self._underlying_object.to_context(detail='minimal'))

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  - .underlying_form -> str (detected form type)")
            lines.append("  - .underlying_object -> delegated data object (if available)")
            lines.append("  - .registration_number -> str (377-XXXXXX)")
            lines.append("  - .is_amendment -> bool")
            lines.append("  - .amendment_number -> int | None")
            if self._underlying_object:
                lines.append("  - .underlying_object.cover_page -> cover page details")
                lines.append("  - .underlying_object.offering_type -> offering classification")
                lines.append("  - .underlying_object.fee_table -> fee table (if available)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        amendment_label = ""
        if self.is_amendment:
            amendment_label = f"Amendment No. {self._amendment_number}" if self._amendment_number else "Amendment"
        subtitle = f"DRS  Draft {self._underlying_form}"
        if amendment_label:
            subtitle += f"  ({amendment_label})"

        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Underlying Form", self._underlying_form)
        if self._registration_number:
            t.add_row("Registration No.", self._registration_number)
        if self.is_amendment:
            label = f"No. {self._amendment_number}" if self._amendment_number else "Yes"
            t.add_row("Amendment", f"[yellow]{label}[/yellow]")

        renderables = [t]

        # Show underlying object summary if available
        if self._underlying_object:
            renderables.append(Text(""))
            ut = Table(box=box.SIMPLE, show_header=False, padding=(0, 1),
                       title="Underlying Registration")
            ut.add_column("field", style="bold", min_width=22)
            ut.add_column("value")

            if hasattr(self._underlying_object, 'offering_type'):
                ut.add_row("Offering Type", self._underlying_object.offering_type.display_name)
            if hasattr(self._underlying_object, 'cover_page'):
                cp = self._underlying_object.cover_page
                if cp.state_of_incorporation:
                    ut.add_row("State", cp.state_of_incorporation)
                if cp.sic_code:
                    ut.add_row("SIC Code", cp.sic_code)
                if cp.ein:
                    ut.add_row("EIN", cp.ein)

            renderables.append(ut)

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
            f"DraftRegistrationStatement("
            f"form={self.form!r}, "
            f"underlying={self._underlying_form!r}, "
            f"company={self.company!r}, "
            f"date={self.filing_date!r})"
        )
