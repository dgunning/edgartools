"""
SEC Correspondence (CORRESP / UPLOAD) parser.

CORRESP filings are company-to-SEC letters (comment responses, acceleration requests).
UPLOAD filings are SEC-to-company letters (comment letters, review-complete notices).

Both contain a "Re:" block with file numbers, referenced forms, and dates that enable
conversation thread reconstruction.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from rich import box
from rich.console import Group, Text
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['Correspondence', 'CorrespondenceThread', 'CorrespondenceType']

# Forms handled by this module
CORRESPONDENCE_FORMS = ['CORRESP', 'UPLOAD']


# ---------------------------------------------------------------------------
# Correspondence Type Enum
# ---------------------------------------------------------------------------

class CorrespondenceType(str, Enum):
    """Classification of correspondence filing types."""
    COMPANY_RESPONSE = "company_response"
    ACCELERATION_REQUEST = "acceleration_request"
    SEC_COMMENT = "sec_comment"
    REVIEW_COMPLETE = "review_complete"
    NO_REVIEW = "no_review"
    COMPANY_LETTER = "company_letter"
    SEC_LETTER = "sec_letter"

    @property
    def display_name(self) -> str:
        return {
            "company_response": "Company Response",
            "acceleration_request": "Acceleration Request",
            "sec_comment": "SEC Comment Letter",
            "review_complete": "Review Complete",
            "no_review": "No Review Notice",
            "company_letter": "Company Letter",
            "sec_letter": "SEC Letter",
        }[self.value]


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

# Regex patterns for extracting metadata from the Re: block
_FILE_NUMBER_PATTERN = re.compile(
    r'File\s*No\.?\s*:?\s*(\d{3}-\d+)',
    re.IGNORECASE
)
# Fallback requires "File" or "No" prefix to avoid matching phone numbers
_FILE_NUMBER_FALLBACK = re.compile(r'(?:File|No\.?)\s*:?\s*(\d{3}-\d{4,})', re.IGNORECASE)

_REFERENCED_FORM_PATTERN = re.compile(
    r'(?:Form|Registration\s+Statement\s+on\s+Form)\s+([\w-]+(?:/[\w]+)?)',
    re.IGNORECASE
)
_RESPONSE_DATE_PATTERN = re.compile(
    r'Response\s+dated\s+(.+?)(?:\n|$)',
    re.IGNORECASE
)
_FISCAL_YEAR_PATTERN = re.compile(
    r'(?:fiscal\s+year|year)\s+ended\s+(.+?)(?:\n|$)',
    re.IGNORECASE
)

# Classification patterns
_ACCELERATION_PATTERNS = [
    re.compile(r'rule\s*461', re.IGNORECASE),
    re.compile(r'request.*(?:accelerat|effective\s*date)', re.IGNORECASE),
    re.compile(r'accelerat.*(?:effective|registration)', re.IGNORECASE),
]
_REVIEW_COMPLETE_PATTERNS = [
    re.compile(r'completed\s+our\s+review', re.IGNORECASE),
    re.compile(r'no\s+further\s+comments', re.IGNORECASE),
]
_NO_REVIEW_PATTERNS = [
    re.compile(r'have\s+not\s+reviewed\s+and\s+will\s+not\s+review', re.IGNORECASE),
    re.compile(r'will\s+not\s+review\s+your\s+registration', re.IGNORECASE),
]
_RESPONSE_PATTERNS = [
    re.compile(r'(?:in\s+)?response\s+to\s+(?:your|the)\s+(?:comment|letter|staff)', re.IGNORECASE),
    re.compile(r'provides?\s+the\s+following\s+response', re.IGNORECASE),
    re.compile(r'response\s+(?:letter|to\s+comments)', re.IGNORECASE),
]


def _extract_re_block(text: str) -> str:
    """Extract the Re: block from correspondence text. Returns the block or full text."""
    # Look for "Re:" followed by content up to "Dear" or double newline
    match = re.search(
        r'Re:\s*(.+?)(?=Dear\s|Ladies\s+and\s+Gentlemen)',
        text, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1)
    return text[:2000]  # Use first 2000 chars as fallback


def _extract_file_number(text: str) -> Optional[str]:
    """Extract SEC file number from text (e.g., '001-36743', '333-293459')."""
    match = _FILE_NUMBER_PATTERN.search(text)
    if match:
        return match.group(1)
    # Fallback: look for any NNN-NNNNN pattern in the Re: block
    re_block = _extract_re_block(text)
    match = _FILE_NUMBER_FALLBACK.search(re_block)
    if match:
        return match.group(1)
    return None


def _extract_referenced_form(text: str) -> Optional[str]:
    """Extract the referenced form type (e.g., '10-K', 'S-3', 'F-1')."""
    re_block = _extract_re_block(text)
    match = _REFERENCED_FORM_PATTERN.search(re_block)
    if match:
        return match.group(1).strip()
    return None


def _extract_response_date(text: str) -> Optional[str]:
    """Extract 'Response dated ...' from the Re: block."""
    re_block = _extract_re_block(text)
    match = _RESPONSE_DATE_PATTERN.search(re_block)
    if match:
        return match.group(1).strip()
    return None


def _extract_fiscal_year_end(text: str) -> Optional[str]:
    """Extract 'fiscal year ended ...' from the Re: block."""
    re_block = _extract_re_block(text)
    match = _FISCAL_YEAR_PATTERN.search(re_block)
    if match:
        return match.group(1).strip()
    return None


def _classify_correspondence(form: str, text: str) -> CorrespondenceType:
    """Classify the correspondence type based on form and text content."""
    if form == 'UPLOAD':
        # SEC-to-company
        for pattern in _REVIEW_COMPLETE_PATTERNS:
            if pattern.search(text):
                return CorrespondenceType.REVIEW_COMPLETE
        for pattern in _NO_REVIEW_PATTERNS:
            if pattern.search(text):
                return CorrespondenceType.NO_REVIEW
        # Check if it has numbered comments (indicates an actual comment letter)
        if re.search(r'^\s*\d+\.\s', text, re.MULTILINE):
            return CorrespondenceType.SEC_COMMENT
        # Check for question language
        if re.search(r'(?:please\s+(?:explain|describe|expand|provide|tell\s+us))', text, re.IGNORECASE):
            return CorrespondenceType.SEC_COMMENT
        return CorrespondenceType.SEC_LETTER
    else:
        # Company-to-SEC (CORRESP)
        for pattern in _ACCELERATION_PATTERNS:
            if pattern.search(text):
                return CorrespondenceType.ACCELERATION_REQUEST
        for pattern in _RESPONSE_PATTERNS:
            if pattern.search(text):
                return CorrespondenceType.COMPANY_RESPONSE
        return CorrespondenceType.COMPANY_LETTER


# ---------------------------------------------------------------------------
# Correspondence
# ---------------------------------------------------------------------------

class Correspondence:
    """A parsed CORRESP or UPLOAD filing with extracted metadata.

    Construction via from_filing() or filing.obj():

        >>> filing = Filing(...)  # A CORRESP or UPLOAD filing
        >>> corresp = filing.obj()  # Returns Correspondence
        >>> corresp = Correspondence.from_filing(filing)

    Properties:
        >>> corresp.correspondence_type   # CorrespondenceType enum
        >>> corresp.referenced_file_number  # e.g., '001-36743'
        >>> corresp.referenced_form         # e.g., '10-K'
        >>> corresp.sender                  # 'company' or 'sec'
        >>> corresp.body                    # Full text content
    """

    def __init__(
        self,
        filing: 'Filing',
        body: Optional[str],
        correspondence_type: CorrespondenceType,
        referenced_file_number: Optional[str] = None,
        referenced_form: Optional[str] = None,
        response_date: Optional[str] = None,
        fiscal_year_end: Optional[str] = None,
    ):
        self._filing = filing
        self._body = body
        self._correspondence_type = correspondence_type
        self._referenced_file_number = referenced_file_number
        self._referenced_form = referenced_form
        self._response_date = response_date
        self._fiscal_year_end = fiscal_year_end

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'Correspondence':
        """Parse a CORRESP or UPLOAD filing into a Correspondence object."""
        text = None
        try:
            text = filing.text()
        except Exception:
            log.warning("Could not extract text from %s filing %s",
                        filing.form, filing.accession_no)

        if not text:
            text = None

        # Extract metadata from text
        file_number = None
        referenced_form = None
        response_date = None
        fiscal_year_end = None
        correspondence_type = (
            CorrespondenceType.SEC_LETTER if filing.form == 'UPLOAD'
            else CorrespondenceType.COMPANY_LETTER
        )

        if text:
            file_number = _extract_file_number(text)
            referenced_form = _extract_referenced_form(text)
            response_date = _extract_response_date(text)
            fiscal_year_end = _extract_fiscal_year_end(text)
            correspondence_type = _classify_correspondence(filing.form, text)

        return cls(
            filing=filing,
            body=text,
            correspondence_type=correspondence_type,
            referenced_file_number=file_number,
            referenced_form=referenced_form,
            response_date=response_date,
            fiscal_year_end=fiscal_year_end,
        )

    # -- Core properties -------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        """The underlying Filing object."""
        return self._filing

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def cik(self) -> int:
        return self._filing.cik

    @property
    def filing_date(self) -> str:
        return self._filing.filing_date

    @property
    def accession_no(self) -> str:
        return self._filing.accession_no

    @property
    def correspondence_type(self) -> CorrespondenceType:
        """The classified type of this correspondence."""
        return self._correspondence_type

    @property
    def sender(self) -> str:
        """Who sent this letter: 'company' or 'sec'."""
        if self._filing.form == 'UPLOAD':
            return 'sec'
        return 'company'

    @property
    def referenced_file_number(self) -> Optional[str]:
        """SEC file number referenced in the letter (e.g., '001-36743')."""
        return self._referenced_file_number

    @property
    def referenced_form(self) -> Optional[str]:
        """Form type being discussed (e.g., '10-K', 'S-1')."""
        return self._referenced_form

    @property
    def response_date(self) -> Optional[str]:
        """The 'Response dated ...' reference, if present."""
        return self._response_date

    @property
    def fiscal_year_end(self) -> Optional[str]:
        """The fiscal year end mentioned in the Re: block, if present."""
        return self._fiscal_year_end

    @property
    def body(self) -> Optional[str]:
        """Full text content of the correspondence."""
        return self._body

    @cached_property
    def thread(self) -> Optional['CorrespondenceThread']:
        """Lazily reconstruct the correspondence thread this filing belongs to."""
        return CorrespondenceThread.from_correspondence(self)

    # -- Display ---------------------------------------------------------------

    def _summary_table(self) -> Table:
        """Build a Rich table summarizing this correspondence."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Form", self.form)
        table.add_row("Date", str(self.filing_date))
        table.add_row("Company", self.company)
        table.add_row("Sender", self.sender.upper())
        table.add_row("Type", self.correspondence_type.display_name)
        if self.referenced_form:
            table.add_row("Re: Form", self.referenced_form)
        if self.referenced_file_number:
            table.add_row("File No.", self.referenced_file_number)
        if self.response_date:
            table.add_row("Response Date", self.response_date)
        if self.fiscal_year_end:
            table.add_row("Fiscal Year End", self.fiscal_year_end)

        return table

    def __rich__(self):
        title = self.correspondence_type.display_name
        subtitle = f"{self.company} | {self.filing_date}"
        return Panel(
            self._summary_table(),
            title=title,
            subtitle=subtitle,
            border_style="bold" if self.sender == 'sec' else "dim",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return (
            f"Correspondence({self.form}, {self.company}, {self.filing_date}, "
            f"type={self.correspondence_type.value})"
        )

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string."""
        lines = [
            f"CORRESPONDENCE: {self.company}",
            f"Form: {self.form}",
            f"Date: {self.filing_date}",
            f"Sender: {self.sender}",
            f"Type: {self.correspondence_type.display_name}",
        ]
        if self.referenced_form:
            lines.append(f"Re: Form {self.referenced_form}")
        if self.referenced_file_number:
            lines.append(f"File No: {self.referenced_file_number}")

        if detail == 'minimal':
            return "\n".join(lines)

        if self.response_date:
            lines.append(f"Response Date: {self.response_date}")
        if self.fiscal_year_end:
            lines.append(f"Fiscal Year End: {self.fiscal_year_end}")

        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .body                     Full text of the letter")
        lines.append("  .thread                   Reconstructed correspondence thread")
        lines.append("  .filing                   The underlying Filing object")
        lines.append("  .correspondence_type      Classification of this letter")

        if detail == 'full' and self._body:
            lines.append("")
            lines.append("BODY (first 1000 chars):")
            lines.append(self._body[:1000])

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CorrespondenceThread
# ---------------------------------------------------------------------------

class CorrespondenceThread:
    """A reconstructed conversation thread between a company and the SEC.

    Groups related CORRESP and UPLOAD filings by file number and referenced form.

    Usage:
        >>> thread = corresp.thread
        >>> thread.entries            # List[Correspondence] in chronological order
        >>> thread.is_resolved        # True if last entry is review_complete
        >>> thread.file_number        # The file number linking the thread
        >>> thread.referenced_form    # The form under review (e.g., '10-K')
    """

    def __init__(
        self,
        file_number: str,
        entries: List[Correspondence],
        referenced_form: Optional[str] = None,
    ):
        self._file_number = file_number
        # Sort entries chronologically
        self._entries = sorted(entries, key=lambda c: str(c.filing_date))
        self._referenced_form = referenced_form

    @classmethod
    def from_correspondence(cls, corresp: Correspondence) -> Optional['CorrespondenceThread']:
        """Build a thread from a Correspondence object by finding related filings.

        Finds all CORRESP/UPLOAD filings for the same company that share the same
        file number, then filters to those referencing the same form.
        """
        if not corresp.referenced_file_number:
            return None

        try:
            from edgar import Company
            company = Company(corresp.cik)

            # Fetch all correspondence filings for this company
            all_entries = []
            for form in CORRESPONDENCE_FORMS:
                filings = company.get_filings(form=form)
                if filings:
                    for filing in filings:
                        entry = Correspondence.from_filing(filing)
                        # Match on file number
                        if entry.referenced_file_number == corresp.referenced_file_number:
                            # If we know the referenced form, filter on it too
                            if corresp.referenced_form and entry.referenced_form:
                                if entry.referenced_form != corresp.referenced_form:
                                    continue
                            all_entries.append(entry)

            if not all_entries:
                return None

            return cls(
                file_number=corresp.referenced_file_number,
                entries=all_entries,
                referenced_form=corresp.referenced_form,
            )
        except Exception:
            log.warning("Could not reconstruct thread for %s", corresp.accession_no, exc_info=True)
            return None

    # -- Properties ------------------------------------------------------------

    @property
    def file_number(self) -> str:
        """The SEC file number linking this thread."""
        return self._file_number

    @property
    def referenced_form(self) -> Optional[str]:
        """The form under review (e.g., '10-K', 'S-1')."""
        return self._referenced_form

    @property
    def entries(self) -> List[Correspondence]:
        """All correspondence entries in chronological order."""
        return list(self._entries)

    @property
    def is_resolved(self) -> bool:
        """True if the thread ends with a review-complete notice."""
        if not self._entries:
            return False
        return self._entries[-1].correspondence_type == CorrespondenceType.REVIEW_COMPLETE

    @property
    def duration_days(self) -> Optional[int]:
        """Days between first and last entry."""
        if len(self._entries) < 2:
            return None
        try:
            from datetime import date
            first = self._entries[0].filing_date
            last = self._entries[-1].filing_date
            if isinstance(first, str):
                first = date.fromisoformat(first)
            if isinstance(last, str):
                last = date.fromisoformat(last)
            return (last - first).days
        except Exception:
            return None

    @property
    def comment_count(self) -> int:
        """Number of SEC comment letters in the thread."""
        return sum(1 for e in self._entries if e.correspondence_type == CorrespondenceType.SEC_COMMENT)

    @property
    def response_count(self) -> int:
        """Number of company responses in the thread."""
        return sum(1 for e in self._entries
                   if e.correspondence_type in (CorrespondenceType.COMPANY_RESPONSE,
                                                 CorrespondenceType.ACCELERATION_REQUEST))

    def __len__(self) -> int:
        return len(self._entries)

    # -- Display ---------------------------------------------------------------

    def __rich__(self):
        title = "Correspondence Thread"
        if self._entries:
            subtitle = f"{self._entries[0].company} | File No. {self._file_number}"
        else:
            subtitle = f"File No. {self._file_number}"

        table = Table(box=box.SIMPLE_HEAVY, padding=(0, 1))
        table.add_column("#", style="dim", width=3)
        table.add_column("Date", width=12)
        table.add_column("Form", width=10)
        table.add_column("Sender", width=10)
        table.add_column("Type", min_width=20)

        for i, entry in enumerate(self._entries, 1):
            sender_style = "bold red" if entry.sender == "sec" else "bold blue"
            table.add_row(
                str(i),
                str(entry.filing_date),
                entry.form,
                Text(entry.sender.upper(), style=sender_style),
                entry.correspondence_type.display_name,
            )

        # Summary line
        summary_parts = []
        if self.referenced_form:
            summary_parts.append(f"Re: Form {self.referenced_form}")
        summary_parts.append(f"{len(self._entries)} entries")
        if self.duration_days is not None:
            summary_parts.append(f"{self.duration_days} days")
        if self.is_resolved:
            summary_parts.append("RESOLVED")
        else:
            summary_parts.append("OPEN")

        summary = Text(" | ".join(summary_parts), style="dim")

        return Panel(
            Group(table, summary),
            title=title,
            subtitle=subtitle,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        status = "resolved" if self.is_resolved else "open"
        return (
            f"CorrespondenceThread(file_no={self._file_number}, "
            f"entries={len(self._entries)}, status={status})"
        )

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string."""
        lines = [
            f"CORRESPONDENCE THREAD: File No. {self._file_number}",
        ]
        if self._entries:
            lines.append(f"Company: {self._entries[0].company}")
        if self.referenced_form:
            lines.append(f"Re: Form {self.referenced_form}")
        lines.append(f"Entries: {len(self._entries)}")
        lines.append(f"Status: {'Resolved' if self.is_resolved else 'Open'}")
        if self.duration_days is not None:
            lines.append(f"Duration: {self.duration_days} days")
        lines.append(f"SEC Comments: {self.comment_count}")
        lines.append(f"Company Responses: {self.response_count}")

        if detail == 'minimal':
            return "\n".join(lines)

        lines.append("")
        lines.append("TIMELINE:")
        for i, entry in enumerate(self._entries, 1):
            lines.append(f"  {i}. {entry.filing_date} | {entry.sender.upper()} | "
                         f"{entry.correspondence_type.display_name}")

        return "\n".join(lines)
