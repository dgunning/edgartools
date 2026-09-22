"""Base class for company report filings."""
import warnings
from contextvars import ContextVar
from functools import cached_property
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from edgar.search.grep import GrepResult
    from edgar.sgml.filing_summary import Reports

from rich import print
from rich.console import Group, Text
from rich.panel import Panel

from edgar.core import log
from edgar.documents import Document, HTMLParser
from edgar.exceptions import SectionNotFoundError, warn_will_raise
from edgar.files.htmltools import ChunkedDocument  # Keep for backwards compat
from edgar.financials import Financials
from edgar.richtools import repr_rich

__all__ = ['CompanyReport', 'section_not_found', 'report_lookup_miss']


# True while we are inside `.get()`, where a missing item is the documented
# answer rather than something to complain about. A ContextVar rather than a
# parameter because `__getitem__` has a fixed signature, and rather than a
# plain global because it must not leak across threads or concurrent tasks.
_absence_is_expected: "ContextVar[bool]" = ContextVar("_absence_is_expected", default=False)


def section_not_found(report, item_or_part: str) -> SectionNotFoundError:
    """The error for `report[item]` when the filing has no such item.

    Shared by every report `__getitem__`, because the answer to "why did I get
    None?" should not depend on which form the user happened to be holding.
    Returns the error rather than raising it — `report_lookup_miss` decides
    whether 5.x warns or strict raises.

    Listing what the filing DOES have is the whole value of the message. Items
    are optional in ways that surprise people: 10-K Item 16 is a summary a filer
    may simply omit, and a 10-Q's Item 1 exists in both parts.
    """
    try:
        available = sorted(report.items)
    except Exception:  # noqa: S110 - repr-guard: an error message must not raise
        available = []
    error = SectionNotFoundError(
        f"{type(report).__name__} filing {report._filing.accession_number} has no "
        f"'{item_or_part}'."
    )
    error.context = {"requested": item_or_part, "available": available}
    error.suggestions = [
        f"this filing has: {', '.join(available)}" if available
        else "no items were detected in this filing at all — check .document",
        f"use .get({item_or_part!r}) if an absent item is an acceptable answer",
    ]
    # The message above names the filing, and the suggestions name its items;
    # both vary between two filings that miss the same item on the same line.
    # The warning has to be the part that does not vary, or a loop over a corpus
    # warns once per filing — see warn_will_raise.
    error.warning_summary = (
        f"{type(report).__name__}[{item_or_part!r}] found no such item in this "
        f"filing. Items are optional and vary by filer, so this can be a "
        f"property of the filing rather than a mistake."
    )
    return error


def report_lookup_miss(report, item_or_part: str) -> None:
    """`report[item]` found nothing: warn now, raise in 6.0 — usually.

    The exception is `.get()`, which is the migration target we are telling
    people to move to. Warning there would mean the users who took our advice
    get the same noise as the users who ignored it, and the ones taking it are
    the ones who most need the output to stay clean. Under strict it stays
    silent for the same reason — `.get()` promises `default`, not a raise.
    """
    if _absence_is_expected.get():
        return
    warn_will_raise(section_not_found(report, item_or_part), stacklevel=4)


class CompanyReport:

    def __init__(self, filing):
        self._filing = filing
        self._parser = None  # Lazy init for new parser

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def form(self):
        return self._filing.form

    @property
    def company(self):
        return self._filing.company

    @property
    def income_statement(self):
        return self.financials.income_statement() if self.financials else None

    @property
    def balance_sheet(self):
        return self.financials.balance_sheet() if self.financials else None

    @property
    def cash_flow_statement(self):
        return self.financials.cash_flow_statement() if self.financials else None

    @cached_property
    def auditor(self):
        """Auditor information from XBRL DEI facts, if available."""
        from edgar.company_reports.auditor import extract_auditor_info
        if self.financials and self.financials.xb:
            return extract_auditor_info(self.financials.xb)
        return None

    @cached_property
    def notes(self):
        """Notes to the financial statements — hierarchical, first-class access.

        Returns:
            Notes: Collection of Note objects with tables, policies, and details.
                   Indexed by number or title: notes[5], notes['Debt']
        """
        from edgar.xbrl.notes import Notes
        if not self.financials or not self.financials.xb:
            return Notes([], entity_name=str(self.company))
        xbrl = self.financials.xb
        # Get FilingSummary for hierarchy (ParentRole)
        filing_summary = None
        try:
            filing_summary = self._filing.sgml().filing_summary
        except Exception as e:
            log.debug(f"Could not load FilingSummary for notes hierarchy: {e}")
        return Notes.from_xbrl(xbrl, filing_summary=filing_summary)

    def grep(self, pattern: str, *, regex: bool = False, document: Optional[str] = None) -> 'GrepResult':
        """
        Grep for exact text matches across the filing.

        Delegates to the underlying Filing.grep(). Case-insensitive.

        Args:
            pattern: Text to search for
            regex: If True, treat pattern as a regular expression
            document: Narrow to specific document ("primary", "EX-10.1", etc.)

        Returns:
            GrepResult with matches

        Examples:
            >>> tenk.grep("going concern")
            >>> tenk.grep("Level 3", document="primary")
        """
        return self._filing.grep(pattern, regex=regex, document=document)

    @cached_property
    def reports(self) -> Optional['Reports']:
        """The XBRL report pages from FilingSummary.xml (statements, notes, tables, details)."""
        return self._filing.reports

    @cached_property
    def financials(self):
        """Get the financials for this filing"""
        return Financials.extract(self._filing)

    @property
    def period_of_report(self):
        return self._filing.header.period_of_report

    @cached_property
    def document(self) -> Document:
        """
        Get the filing document using new parser (primary API).

        Returns:
            Document: Parsed document with sections, tables, and content extraction

        Examples:
            >>> report.document.sections  # Get all sections
            >>> report.document.text()    # Get full text
            >>> report.document.tables    # Get all tables
        """
        if self._parser is None:
            from edgar.documents.config import ParserConfig
            # Create parser with form type for better section detection
            config = ParserConfig(form=self._filing.form)
            self._parser = HTMLParser(config)
        return self._parser.parse(self._filing.html())

    @cached_property
    def _chunked_document(self):
        """Build the legacy chunked document, without warning anybody.

        This is what our own fallback paths read. `items` and `__getitem__` on
        several report classes try the new parser first and drop back to the old
        one when it finds nothing, and routing those through the public property
        told the user their code was deprecated when the choice was ours — a
        plain `twentyf.items` emitted a `chunked_document is deprecated` warning
        naming an attribute the caller had never mentioned.

        Subclasses override THIS to change construction (`TenQ` needs
        `prefix_src`, `CurrentReport` a decimal-aware `chunk_fn`). The
        deprecation lives once, on the public property below, so an override
        cannot accidentally drop it — which is exactly what happened before:
        `TenQ` and `CurrentReport` overrode `chunked_document` itself and
        silently lost the warning, so their users got no notice at all.
        """
        return ChunkedDocument(self._filing.html())

    @cached_property
    def chunked_document(self):
        """
        Get chunked document using old parser.

        .. deprecated:: 5.0
            Use :attr:`document` instead. This will be removed in v6.0.
        """
        warnings.warn(
            "chunked_document is deprecated and will be removed in v6.0. "
            "Use document property instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self._chunked_document

    @property
    def doc(self):
        """Get the filing document (returns new Document object)."""
        return self.document

    @property
    def items(self) -> List[str]:
        """
        Get list of items/sections in the filing.

        Returns:
            List[str]: List of section identifiers in "Item X" format

        Examples:
            >>> report.items
            ['Item 1', 'Item 1A', 'Item 1B', 'Item 2', ...]
        """
        # Convert section keys to "Item X" format for backwards compatibility
        items = []
        for name, section in self.document.sections.items():
            if section.item:
                # Format as "Item 1", "Item 1A", etc.
                items.append(f"Item {section.item}")
            elif name.startswith("Item "):
                # Section name is already in "Item X" format
                items.append(name)
            elif name.startswith("item_"):
                # Convert "item_1" to "Item 1"
                item_num = name.replace("item_", "").replace("_", "").upper()
                items.append(f"Item {item_num}")
            elif name.startswith("part_"):
                # Convert "part_i_item_1" to "Item 1"
                # Extract item number from name like "part_i_item_1a"
                parts = name.split("_")
                if len(parts) >= 4 and parts[2] == "item":
                    item_num = parts[3].upper()
                    items.append(f"Item {item_num}")
        return items

    @property
    def signatures(self) -> Optional[str]:
        """The Signatures section text, if present.

        Signatures is a *named* (non-Item) section, so it does not appear in
        :attr:`items`; this is its convenience accessor, parallel to the Item
        properties (``.business``, ``.risk_factors``, ...). Returns ``None`` when
        the filing exposes no detectable Signatures section.

        Examples:
            >>> tenk.signatures[:60]
            'Pursuant to the requirements of Section 13 or 15(d) ...'
        """
        section = self.document.sections.named("signatures")
        return section.text() if section else None

    def __getitem__(self, item_or_part: str):
        """
        Get item or part text from the filing.

        Args:
            item_or_part: Item identifier (e.g., "Item 1", "1", "1A", "Part I")

        Returns:
            str: Item text or None if not found

        Examples:
            >>> report["Item 1"]
            >>> report["1A"]
            >>> report["Part I"]  # For 10-Q
        """
        # Try to get section using new parser
        section = self.document.sections.get(item_or_part)
        if section:
            return section.text()

        # Try flexible item lookup (handles "Item 1", "1", etc.)
        section = self.document.sections.get_item(item_or_part)
        if section:
            return section.text()

        report_lookup_miss(self, item_or_part)
        return None

    def get(self, item_or_part: str, default=None):
        """Get item or part text, or `default` when the filing has no such item.

        The non-raising counterpart to `report[item]`, and the reason that one
        can start raising in 6.0: a lookup whose only form raises leaves the
        "I'll take it if it's there" caller writing a try/except around a
        one-liner. This ships in the same release as the warning on
        `__getitem__`, so there is somewhere to move to before the flip and not
        after it.

        Args:
            item_or_part: Item identifier (e.g. "Item 1", "1", "1A", "Part I")
            default: Returned when the item is absent. Defaults to None.

        Examples:
            >>> report.get("Item 1")
            >>> report.get("Item 16", "")     # 10-K summary is optional
        """
        token = _absence_is_expected.set(True)
        try:
            value = self[item_or_part]
        finally:
            _absence_is_expected.reset(token)
        return default if value is None else value

    def view(self, item_or_part: str):
        """Get the Item or Part from the filing document. e.g. Item 1 Business from 10-K or Part I from 10-Q"""
        item_text = self[item_or_part]
        if item_text:
            print(item_text)

    def _focused_context(self, focus, detail: str = 'standard') -> str:
        """Generate cross-cutting context for specific topic(s).

        Pulls statement line items, note content, and policies together.

        Args:
            focus: Topic or list of topics
            detail: 'minimal', 'standard', or 'full'
        """
        if isinstance(focus, str):
            focus = [focus]

        notes = self.notes

        form_label = self.form or 'Filing'
        lines = []
        topic_str = ', '.join(focus)
        lines.append(f"{form_label.upper()}: {self.company} · Focus: {topic_str}")

        try:
            period = self.period_of_report
            if period:
                lines.append(f"Period: {period}")
        except Exception:
            pass
        lines.append("")

        if not notes:
            lines.append("(No notes available)")
            return "\n".join(lines)

        for topic in focus:
            matched_notes = notes.search(topic)
            if not matched_notes:
                matched_notes = [n for n in notes if topic.lower() in n.title.lower()]

            if not matched_notes:
                lines.append(f"## {topic.title()}")
                lines.append("  (No matching note found)")
                lines.append("")
                continue

            for note in matched_notes:
                lines.append(f"## {note.title}")
                lines.append("")

                # Statement line items this note expands, with values
                if note.expands:
                    lines.append("FINANCIAL STATEMENT LINES:")
                    self._append_expands_with_values(lines, note)
                    lines.append("")

                # Note content
                lines.append(note.to_context(detail=detail))
                lines.append("")

        return "\n".join(lines)

    def _append_expands_with_values(self, lines: list, note):
        """Append expanded statement line items with their current values."""
        from edgar.display.formatting import format_currency_short

        if not self.financials or not self.financials.xb:
            for label in note.expands:
                lines.append(f"  {label}")
            return

        xbrl = self.financials.xb
        from edgar.xbrl.notes import _compute_expands_with_statements

        expands_data, stmt_types = _compute_expands_with_statements(note, xbrl)
        if not expands_data:
            return

        # Build concept → (label, value) from raw statement data
        # Keep first occurrence per concept (face value, not dimensional breakdowns)
        concept_values = {}
        for stmt_type in stmt_types:
            try:
                stmt = xbrl.statements.get(stmt_type)
                if stmt:
                    for item in stmt.get_raw_data():
                        concept = item.get('concept', '')
                        if item.get('is_abstract') or concept in concept_values:
                            continue
                        values = item.get('values', {})
                        if values:
                            val = next(iter(values.values()), None)
                            if val is not None:
                                label_text = item.get('label', concept)
                                try:
                                    val_num = float(val)
                                    cs = (self.financials.get_currency_symbol() if self.financials else '$') or '$'
                                    formatted = format_currency_short(val_num, cs)
                                except (ValueError, TypeError):
                                    formatted = str(val)
                                concept_values[concept] = (label_text, formatted)
            except Exception as e:
                log.debug(f"Failed to get raw data for {stmt_type}: {e}")

        for concept_id, label in expands_data:
            match = concept_values.get(concept_id)
            if match:
                stmt_label, value = match
                lines.append(f"  {stmt_label}: {value}")
            else:
                lines.append(f"  {label}")

    def __rich__(self):
        return Panel(
            Group(
                self._filing.__rich__(),
                self.financials or Text("No financial data available")
            )
        )

    def __repr__(self):
        return repr_rich(self.__rich__())
