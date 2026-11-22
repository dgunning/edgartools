"""Base class for company report filings."""
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
from edgar.exceptions import LowConfidenceSectionError, SectionNotFoundError, ValidationError
from edgar.financials import Financials
from edgar.richtools import repr_rich

__all__ = ['CompanyReport', 'section_not_found', 'report_lookup_miss', 'text_only_section']


# True while we are inside `.get()`, where a missing item is the documented
# answer rather than something to complain about. A ContextVar rather than a
# parameter because `__getitem__` has a fixed signature, and rather than a
# plain global because it must not leak across threads or concurrent tasks.
_absence_is_expected: "ContextVar[bool]" = ContextVar("_absence_is_expected", default=False)


def section_not_found(report, item_or_part: str) -> SectionNotFoundError:
    """The error for `report[item]` when the filing has no such item.

    Shared by every report `__getitem__`, because the answer to "why did I get
    None?" should not depend on which form the user happened to be holding.
    Returns the error rather than raising it, so `report_lookup_miss` can stay
    quiet under `.get()`.

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
    return error


def report_lookup_miss(report, item_or_part: str) -> None:
    """`report[item]` found nothing: raise `SectionNotFoundError`.

    Except under `.get()`, which promises its default rather than a raise, and
    marks that with `_absence_is_expected`. In 5.x this warned and returned
    None (edgartools-07lk.10).
    """
    if _absence_is_expected.get():
        return
    raise section_not_found(report, item_or_part)


def text_only_section(name: str, title: str, text: str, *, detection_method: str,
                      confidence: float, warnings=(), part=None, item=None):
    """A `Section` for text a report found WITHOUT a detected section.

    Some lookups end in a fallback that reads text directly: the 10-K Cross
    Reference Index, the 8-K text-pattern scan of legacy filings, the 40-F AIF
    heading scan. `report.section()` must still return a Section for those,
    with a `detection_method` that says where the text came from and the
    confidence of the detector it is equivalent to, rather than pretending it
    was found in the table of contents. The text is already extracted, so the
    extractor hands it back unchanged.
    """
    from edgar.documents.document import Section
    from edgar.documents.nodes import SectionNode

    class _TextOnlySection(Section):
        # Section.text() runs boundary cleanup over what its extractor returns.
        # This text is already final (it is what `report[item]` returned), so
        # skip it: section(x).text() must equal report[x].
        def text(self, **kwargs) -> str:
            return text

    return _TextOnlySection(
        name=name,
        title=title,
        node=SectionNode(section_name=name),
        confidence=confidence,
        detection_method=detection_method,
        part=part,
        item=item,
        warnings=list(warnings),
        _text_extractor=lambda _name, **_kwargs: text,
    )


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

    @property
    def trading_symbols(self) -> List[dict]:
        """The securities this filing's cover registers, from its dei:TradingSymbol facts.

        One dict per symbol, in document order: ``symbol``, ``class_of_stock``
        (the member QName naming the security, such as
        ``'us-gaap:CommonStockMember'``, or None) and ``context_ref``. The
        first is the filing's ``ticker``. A filing without XBRL has none, so
        the list is empty.

        ``Company.tickers`` is SEC's current ticker list for the company; this
        is what the filing itself registered.

        Examples:
            >>> tenk.trading_symbols[0]
            {'symbol': 'JPM', 'class_of_stock': 'us-gaap:CommonStockMember', 'context_ref': 'c-2'}
        """
        if not self.financials or not self.financials.xb:
            return []
        return [dict(symbol) for symbol in self.financials.xb.entity_info.get('trading_symbols') or []]

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
    def financials(self) -> Optional[Financials]:
        """The financials for this filing, or None when it carries no XBRL."""
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
        return self._item_text(item_or_part)

    # Lookup is split in two so that `report[item]` and `report.section(item)`
    # resolve through the SAME rules: subclasses override `_resolve_section`
    # only. Two copies of a lookup cascade would drift, and the item that
    # `report['Item 8']` returns must be the one whose confidence
    # `report.section('Item 8')` reports.
    def _resolve_section(self, item_or_part: str):
        """Find the section for `item_or_part`.

        Returns `(section, text)`, or None when the filing has no such item.
        `text` is the section's text when the lookup already had to extract it
        (a cascade that skips empty sections reads it to decide), so a caller
        that wants text does not extract twice; otherwise it is None.
        """
        # Exact key first, then the flexible item lookup ("Item 1", "1", ...).
        section = self.document.sections.get(item_or_part)
        if section is None:
            section = self.document.sections.get_item(item_or_part)
        return (section, None) if section is not None else None

    def _item_text(self, item_or_part: str):
        found = self._resolve_section(item_or_part)
        if found is not None:
            section, text = found
            return text if text is not None else section.text()
        report_lookup_miss(self, item_or_part)
        return None

    def section(self, item_or_part: str, *, strict: bool = False, min_confidence: float = 0.8):
        """Get an item as a `Section`, with how reliably it was located.

        `report[item]` returns only the text. This returns the section itself,
        found by exactly the same lookup, so the caller can see what the text
        alone hides:

        - `.confidence`: 0.0-1.0. Sections located from the filing's table of
          contents score 0.95; fallback detectors score lower, and a section a
          size guardrail flagged (e.g. an incorporation-by-reference stub)
          drops to 0.5.
        - `.warnings`: why a section was flagged, as plain sentences.
        - `.detection_method`: which detector found it ('toc', 'index',
          'pattern', ...).
        - `.text()` and `.markdown()`: the content, as from `report[item]`.

        Args:
            item_or_part: Any spelling `report[item]` accepts ("Item 7", "7",
                "mda", "Part II, Item 1A" for a 10-Q, ...).
            strict: When True, raise `LowConfidenceSectionError` instead of
                returning a section located with confidence below
                `min_confidence`. Use it in pipelines that would rather stop
                than ingest a doubtful slice.
            min_confidence: The threshold `strict` applies, 0.0-1.0. The
                default 0.8 accepts table-of-contents and cross-reference-index
                sections and refuses pattern-fallback and guardrail-flagged ones.

        Returns:
            Section

        Raises:
            SectionNotFoundError: the filing has no such item.
            LowConfidenceSectionError: `strict=True` and the section's
                confidence is below `min_confidence`.
            ValidationError: `min_confidence` is outside 0.0-1.0.

        Examples:
            >>> item8 = tenk.section("Item 8")
            >>> item8.confidence, item8.warnings
            >>> tenk.section("Item 7", strict=True).text()
        """
        if (isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float))
                or not 0.0 <= min_confidence <= 1.0):
            raise ValidationError(
                f"min_confidence must be a number from 0.0 to 1.0, got {min_confidence!r}")
        found = self._resolve_section(item_or_part)
        if found is None:
            report_lookup_miss(self, item_or_part)
            return None
        section = found[0]
        if strict and section.confidence < min_confidence:
            raise LowConfidenceSectionError(
                f"{item_or_part!r} was located with confidence {section.confidence:.2f}, "
                f"below min_confidence={min_confidence} (detected by {section.detection_method!r})",
                context={"warnings": list(section.warnings)} if section.warnings else None,
                suggestions=["Read it anyway with strict=False and check .warnings",
                             "Lower min_confidence if this detector is good enough for you"],
                item=item_or_part,
                confidence=section.confidence,
                min_confidence=min_confidence,
                warnings=section.warnings,
                detection_method=section.detection_method,
            )
        return section

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
