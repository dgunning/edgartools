"""
First-class Note and Notes objects for XBRL financial statement notes.

Notes are the real substance of a filing — they contain the detail behind every
financial statement line item. This module provides hierarchical, AI-native access
to notes built from FilingSummary.xml metadata and XBRL presentation data.

Usage:
    >>> tenk = filing.obj()
    >>> tenk.notes                        # Notes collection
    >>> tenk.notes['Debt']                # Single Note by title
    >>> tenk.notes[5]                     # By position
    >>> tenk.notes['Debt'].tables         # Sub-tables within the note
    >>> tenk.notes['Debt'].to_context()   # AI-optimized context
"""
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.text import Text

from edgar.core import log
from edgar.richtools import repr_rich

if TYPE_CHECKING:
    from edgar.xbrl.xbrl import XBRL
    from edgar.xbrl.statements import Statement

__all__ = ['Note', 'Notes']


class Note:
    """
    A single note to the financial statements.

    Represents one note (e.g., "Note 5 - Debt") with its child tables,
    policies, and details organized hierarchically from FilingSummary.xml.
    """

    def __init__(self,
                 number: int,
                 title: str,
                 short_name: str,
                 role: str,
                 statement: Optional['Statement'] = None,
                 tables: Optional[List['Statement']] = None,
                 policies: Optional[List['Statement']] = None,
                 details: Optional[List['Statement']] = None,
                 menu_category: str = 'Notes',
                 xbrl: Optional['XBRL'] = None):
        self.number = number
        self.title = title
        self.short_name = short_name
        self.role = role
        self.statement = statement
        self.tables = tables or []
        self.policies = policies or []
        self.details = details or []
        self.menu_category = menu_category
        self._xbrl = xbrl

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    @property
    def children(self) -> List['Statement']:
        """All child statements (tables + policies + details)."""
        return self.tables + self.policies + self.details

    @property
    def text(self) -> Optional[str]:
        """Full narrative text from TextBlock XBRL tags."""
        if self.statement:
            return self.statement.text()
        return None

    @property
    def html(self) -> Optional[str]:
        """Raw HTML content from TextBlock XBRL tags."""
        if self.statement:
            return self.statement.text(raw_html=True)
        return None

    def _get_expands_data(self) -> List[tuple]:
        """Cached computation of (concept_id, label) pairs shared with statements."""
        if not hasattr(self, '_expands_cache'):
            self._expands_cache = _compute_expands(self, self._xbrl)
        return self._expands_cache

    @property
    def expands(self) -> List[str]:
        """Financial statement line items this note breaks down.

        Returns human-readable labels for concepts that appear in both this note
        (including its children) and a core financial statement.

        Example:
            >>> note = tenk.notes['Debt']
            >>> note.expands
            ['Commercial paper', 'Long-term debt, non-current', 'Long-term debt, current']
        """
        return [label for _, label in self._get_expands_data()]

    @property
    def expands_concepts(self) -> List[str]:
        """Raw concept IDs that appear in both this note and a core financial statement."""
        return [concept for concept, _ in self._get_expands_data()]

    @property
    def expands_statements(self) -> List[str]:
        """Which statement types contain the overlapping concepts (e.g. ['BalanceSheet'])."""
        xbrl = self._xbrl
        if not xbrl:
            return []
        # Reuse the cached concept IDs from _get_expands_data to avoid
        # re-scanning presentation trees
        concept_ids = set(self.expands_concepts)
        if not concept_ids:
            return []
        stmt_map = _get_statement_concepts(xbrl)
        stmt_types = set()
        for stmt_type, stmt_info in stmt_map.items():
            if concept_ids & stmt_info['concepts']:
                stmt_types.add(stmt_type)
        return sorted(stmt_types)

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string for this note.

        Args:
            detail: 'minimal' (~50 tokens), 'standard' (~200 tokens), 'full' (~500+ tokens)
        """
        lines = []
        lines.append(f"NOTE {self.number}: {self.title}")

        if detail == 'minimal':
            if self.tables:
                table_names = [_extract_table_name(t, self.short_name) for t in self.tables]
                lines.append(f"Tables: {', '.join(table_names)}")
            return "\n".join(lines)

        # === STANDARD ===
        lines.append("")

        # Statement line items this note expands
        expands = self.expands
        if expands:
            lines.append(f"EXPANDS: {', '.join(expands)}")
            lines.append("")

        # Tables with key line items
        if self.tables:
            lines.append("TABLES:")
            for table_stmt in self.tables:
                table_name = _extract_table_name(table_stmt, self.short_name)
                lines.append(f"  {table_name}")
                if detail == 'full':
                    _append_statement_lines(lines, table_stmt, indent=4, max_items=8)

        # Narrative excerpt
        note_text = self.text
        if note_text:
            excerpt = note_text[:500].strip()
            if len(note_text) > 500:
                excerpt += "..."
            lines.append("")
            lines.append("NARRATIVE:")
            lines.append(f"  {excerpt}")

        if detail == 'full':
            # Policies
            if self.policies:
                lines.append("")
                lines.append("POLICIES:")
                for policy_stmt in self.policies:
                    policy_text = policy_stmt.text()
                    if policy_text:
                        excerpt = policy_text[:300].strip()
                        if len(policy_text) > 300:
                            excerpt += "..."
                        lines.append(f"  {excerpt}")

            # Details count
            if self.details:
                lines.append("")
                lines.append(f"DETAIL BREAKDOWNS: {len(self.details)}")
                for detail_stmt in self.details[:5]:
                    detail_name = _extract_table_name(detail_stmt, self.short_name)
                    lines.append(f"  {detail_name}")
                if len(self.details) > 5:
                    lines.append(f"  ... and {len(self.details) - 5} more")

        return "\n".join(lines)

    def __rich__(self):
        parts = []

        # Title
        title_text = Text.assemble(
            (f"Note {self.number}", "bold"),
            (" — ", "dim"),
            (self.title, "bold"),
        )
        parts.append(title_text)

        # Tables
        if self.tables:
            parts.append(Text(""))
            parts.append(Text("Tables:", style="dim bold"))
            for table_stmt in self.tables:
                table_name = _extract_table_name(table_stmt, self.short_name)
                parts.append(Text(f"  • {table_name}"))

        # Policies
        if self.policies:
            parts.append(Text(""))
            parts.append(Text("Policies:", style="dim bold"))
            for policy_stmt in self.policies:
                policy_name = _extract_table_name(policy_stmt, self.short_name)
                parts.append(Text(f"  • {policy_name}"))

        # Details summary
        if self.details:
            parts.append(Text(""))
            parts.append(Text(f"Details: {len(self.details)} breakdowns", style="dim"))

        return Panel(
            Group(*parts),
            title=f"Note {self.number}",
            expand=False,
            border_style="dim",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        tables_str = f", tables={self.table_count}" if self.tables else ""
        return f"Note({self.number}, '{self.short_name}'{tables_str})"


class Notes:
    """
    Collection of notes to the financial statements.

    Provides table-of-contents navigation, indexing by number/name,
    and AI-optimized context generation.
    """

    def __init__(self, notes: List[Note], entity_name: str = "", form: str = "",
                 period: str = ""):
        self._notes = notes
        self._by_number: Dict[int, Note] = {n.number: n for n in notes}
        self._by_name: Dict[str, Note] = {n.short_name.lower(): n for n in notes}
        self.entity_name = entity_name
        self.form = form
        self.period = period

    @classmethod
    def from_xbrl(cls, xbrl: 'XBRL', filing_summary=None) -> 'Notes':
        """
        Build Notes from XBRL data + FilingSummary.xml.

        Args:
            xbrl: Parsed XBRL object
            filing_summary: Optional FilingSummary for hierarchy (ParentRole)
        """
        from edgar.xbrl.statements import Statement, Statements

        all_stmts = xbrl.get_all_statements()

        # Get entity info for display
        entity_name = ""
        form = ""
        period = ""
        try:
            entity = xbrl.entity_info
            entity_name = entity.get('entity_name', '')
            form = entity.get('form_type', '')
            period = entity.get('period_of_report', '')
        except Exception:
            pass

        # If we have FilingSummary, use it for authoritative hierarchy
        if filing_summary:
            result = cls._build_from_filing_summary(xbrl, filing_summary, all_stmts,
                                                     entity_name, form, period)
        else:
            # Fallback: build flat list from XBRL classification
            result = cls._build_from_xbrl_only(xbrl, all_stmts, entity_name, form, period)

        # Cache on XBRL so the reverse index can reuse it
        xbrl._notes_cache = result
        return result

    @classmethod
    def _build_from_filing_summary(cls, xbrl, filing_summary, all_stmts,
                                    entity_name, form, period) -> 'Notes':
        """Build hierarchical notes using FilingSummary.xml ParentRole."""
        from edgar.xbrl.statements import Statement

        stmt_roles = {s['role'] for s in all_stmts}

        # Single pass: classify all reports into buckets
        note_reports = []
        children_by_parent = {}       # parent_role → [report, ...]
        detail_reports = []           # Details without parent_role (need name-prefix matching)

        for report in filing_summary.reports:
            cat = report.menu_category
            if cat == 'Notes' and not report.parent_role:
                note_reports.append(report)
            elif cat in ('Tables', 'Policies', 'Details') and report.parent_role:
                children_by_parent.setdefault(report.parent_role, []).append(report)
            elif cat == 'Details' and not report.parent_role:
                detail_reports.append(report)

        # Sort notes by position
        note_reports.sort(key=lambda r: int(r.position) if r.position and str(r.position).isdigit() else 999)

        # Build notes with children
        notes = []
        for idx, report in enumerate(note_reports, start=1):
            if not report.role:
                continue

            statement = Statement(xbrl, report.role) if report.role in stmt_roles else None
            if statement:
                statement._report = report

            # Children linked via ParentRole
            tables, policies, details = [], [], []
            for child in children_by_parent.get(report.role, []):
                if child.role not in stmt_roles:
                    continue
                child_stmt = Statement(xbrl, child.role)
                child_stmt._report = child  # Link to FilingSummary Report for HTML access
                if child.menu_category == 'Tables':
                    tables.append(child_stmt)
                elif child.menu_category == 'Policies':
                    policies.append(child_stmt)
                elif child.menu_category == 'Details':
                    details.append(child_stmt)

            # Orphan Details matched by name prefix
            if report.short_name:
                prefix = report.short_name.lower()
                linked_roles = {c.role for c in children_by_parent.get(report.role, [])
                                if c.menu_category == 'Details'}
                for dr in detail_reports:
                    if (dr.role and dr.role not in linked_roles
                            and dr.short_name
                            and dr.short_name.lower().startswith(prefix)
                            and dr.role in stmt_roles
                            and dr.role != report.role):
                        detail_stmt = Statement(xbrl, dr.role)
                        detail_stmt._report = dr
                        details.append(detail_stmt)

            notes.append(Note(
                number=idx,
                title=report.short_name or '',
                short_name=report.short_name or '',
                role=report.role,
                statement=statement,
                tables=tables,
                policies=policies,
                details=details,
                menu_category='Notes',
                xbrl=xbrl,
            ))

        return cls(notes, entity_name=entity_name, form=form, period=period)

    @classmethod
    def _build_from_xbrl_only(cls, xbrl, all_stmts, entity_name, form, period) -> 'Notes':
        """Fallback: build flat notes list from XBRL classification only."""
        from edgar.xbrl.statements import Statement, Statements

        notes = []
        idx = 1
        for stmt in all_stmts:
            category = Statements.classify_statement(stmt)
            if category == 'note' and stmt.get('type') == 'Notes':
                # Only top-level notes (not Tables/Policies)
                statement = Statement(xbrl, stmt['role'])
                definition = stmt.get('definition', '')
                # Try to extract a clean name from definition
                short_name = _extract_short_name(definition)
                note = Note(
                    number=idx,
                    title=short_name,
                    short_name=short_name,
                    role=stmt['role'],
                    statement=statement,
                    menu_category='Notes',
                    xbrl=xbrl,
                )
                notes.append(note)
                idx += 1

        return cls(notes, entity_name=entity_name, form=form, period=period)

    def __len__(self):
        return len(self._notes)

    def __iter__(self):
        return iter(self._notes)

    def __contains__(self, key) -> bool:
        """Support 'in' operator: 'Debt' in notes."""
        if isinstance(key, int):
            return key in self._by_number
        if isinstance(key, str):
            return key.lower() in self._by_name
        return False

    def __getitem__(self, key) -> Optional[Note]:
        """
        Look up a note by number or exact title.

        Args:
            key: int (note number, 1-based) or str (exact title, case-insensitive)

        Returns:
            Note if found, None otherwise.
            For fuzzy/partial matching, use .search() instead.

        Examples:
            >>> notes[9]                    # By number
            >>> notes['Debt']               # Exact title match
            >>> notes['debt']               # Case-insensitive
        """
        if isinstance(key, int):
            return self._by_number.get(key)

        if isinstance(key, str):
            return self._by_name.get(key.lower())

        return None

    def search(self, keyword: str) -> List[Note]:
        """
        Search notes by keyword. Returns all matches, best first.

        Ranking: exact title > title starts with keyword > word match > substring match.

        Args:
            keyword: Search term (case-insensitive). Single word or phrase.

        Returns:
            List of matching Notes, best match first.

        Examples:
            >>> notes.search('share')       # → [Share-Based Comp, Shareholders' Equity, Earnings Per Share]
            >>> notes.search('debt')        # → [Debt]
            >>> notes.search('balance')     # → [Consolidated Financial Statement Details, ...]
        """
        if not keyword or not keyword.strip():
            return []

        key = keyword.strip().lower()

        # Score each note
        scored = []
        for note in self._notes:
            title = note.short_name.lower()
            words = [w.rstrip("',;:-") for w in title.split()]

            if title == key:
                scored.append((0, note))  # Exact title
            elif title.startswith(key):
                scored.append((1, note))  # Title starts with
            elif any(w == key for w in words):
                scored.append((2, note))  # Exact word match
            elif any(w.startswith(key) for w in words):
                scored.append((3, note))  # Word-start match
            elif key in title:
                scored.append((4, note))  # Substring
            else:
                # Multi-word AND search
                key_words = key.split()
                if len(key_words) > 1 and all(kw in title for kw in key_words):
                    scored.append((5, note))

        scored.sort(key=lambda x: x[0])
        return [note for _, note in scored]

    @property
    def with_tables(self) -> List[Note]:
        """Notes that have child tables."""
        return [n for n in self._notes if n.has_tables]

    def to_context(self, detail: str = 'standard', focus: Optional[List[str]] = None) -> str:
        """
        AI-optimized context string for all notes.

        Args:
            detail: 'minimal', 'standard', or 'full'
            focus: Optional list of note titles to include (case-insensitive)
        """
        lines = []

        # Header
        header_parts = ["NOTES TO FINANCIAL STATEMENTS"]
        if self.entity_name:
            header_parts.append(self.entity_name)
        if self.form:
            header_parts.append(self.form)
        if self.period:
            header_parts.append(self.period)
        lines.append(" · ".join(header_parts))
        lines.append(f"Total: {len(self._notes)} notes")
        lines.append("")

        # Filter by focus if specified
        notes_to_include = self._notes
        if focus:
            focus_lower = [f.lower() for f in focus]
            notes_to_include = [
                n for n in self._notes
                if any(f in n.short_name.lower() or f in n.title.lower() for f in focus_lower)
            ]

        for note in notes_to_include:
            lines.append(note.to_context(detail=detail))
            lines.append("")

        return "\n".join(lines)

    def __rich__(self):
        table = RichTable(
            show_header=True,
            header_style="bold",
            box=box.SIMPLE_HEAVY,
            border_style="dim",
            pad_edge=False,
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Note", min_width=40)
        table.add_column("Tables", justify="center", width=7)
        table.add_column("Policies", justify="center", width=9)
        table.add_column("Details", justify="center", width=8)

        for note in self._notes:
            tables_str = str(note.table_count) if note.tables else ""
            policies_str = str(len(note.policies)) if note.policies else ""
            details_str = str(len(note.details)) if note.details else ""

            table.add_row(
                str(note.number),
                note.title,
                tables_str,
                policies_str,
                details_str,
            )

        # Title
        title_parts = ["Notes to Financial Statements"]
        if self.entity_name:
            title_parts = [self.entity_name] + title_parts
        if self.form and self.period:
            subtitle = f"{self.form} · {self.period}"
        elif self.form:
            subtitle = self.form
        else:
            subtitle = None

        return Panel(
            table,
            title=" · ".join(title_parts),
            subtitle=subtitle,
            expand=False,
            border_style="bold",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"Notes({len(self._notes)} notes)"

    def __bool__(self):
        return len(self._notes) > 0


# === Helpers ===

def _extract_short_name(definition: str) -> str:
    """Extract a clean short name from a definition string.

    Handles formats like:
    - "9952165 - Disclosure - Balance Sheet Detail"
    - "BalanceSheetDetail" (URI slug)
    - "Note 5 - Balance Sheet Detail"
    """
    # Strip leading number + category prefix: "9952165 - Disclosure - Foo" → "Foo"
    match = re.match(r'^\d+\s*-\s*\w+\s*-\s*(.+)$', definition)
    if match:
        return match.group(1).strip()

    # Strip "Note N - " prefix
    match = re.match(r'^Note\s+\d+\s*[-–—]\s*(.+)$', definition, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # CamelCase split for URI slugs
    if ' ' not in definition and len(definition) > 0:
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', definition)
        return spaced

    return definition.strip()


def _extract_table_name(statement: 'Statement', parent_short_name: str) -> str:
    """Extract a clean table name, removing the parent note prefix."""
    try:
        rendered = statement.render()
        name = rendered.title if rendered else statement.role_or_type
    except Exception:
        name = statement.role_or_type

    # Clean up common suffixes first
    for sfx in [' (Tables)', ' (Policies)', ' (Details)']:
        if name.endswith(sfx):
            name = name[:-len(sfx)]

    # Remove parent prefix: "Balance Sheet Detail - Inventories" → "Inventories"
    if parent_short_name:
        if name.lower().startswith(parent_short_name.lower()):
            suffix = name[len(parent_short_name):].lstrip(' -–—')
            if suffix:
                return suffix

    # Try to extract from role URI
    if name.startswith('http'):
        name = name.split('/')[-1]
        # CamelCase split
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

    return name.strip()


def _append_statement_lines(lines: list, statement: 'Statement', indent: int = 4,
                             max_items: int = 5):
    """Append key line items from a statement to context lines."""
    try:
        rendered = statement.render()
        if not rendered or not rendered.rows:
            return
        count = 0
        prefix = " " * indent
        for row in rendered.rows:
            if count >= max_items:
                break
            if row.is_abstract:
                continue
            cell_vals = [c for c in (row.cells or []) if c and c.value is not None]
            if not cell_vals:
                continue
            label = row.label or ''
            val_str = cell_vals[0].get_formatted_value()
            if label:
                lines.append(f"{prefix}{label}: {val_str}")
                count += 1
    except Exception as e:
        log.debug(f"Failed to render statement lines for {statement.role_or_type}: {e}")


# Suffixes for structural XBRL concepts (not real financial data)
_STRUCTURAL_SUFFIXES = ('Abstract', 'Axis', 'Domain', 'Member', 'LineItems', 'Table',
                        'TextBlock')


def _is_data_concept(concept_id: str) -> bool:
    """Check if a concept ID represents real financial data (not structural XBRL metadata)."""
    return not any(concept_id.endswith(sfx) for sfx in _STRUCTURAL_SUFFIXES)


def _collect_note_concepts(note: 'Note', xbrl: 'XBRL') -> set:
    """Collect all data-bearing concept IDs from a note and its children."""
    concepts = set()
    roles = [note.role]
    # Include children (tables, details) — that's where the real data lives
    for child_stmt in note.children:
        roles.append(child_stmt.role_or_type)

    for role in roles:
        tree = xbrl.presentation_trees.get(role)
        if tree:
            for element_id in tree.all_nodes:
                if _is_data_concept(element_id):
                    concepts.add(element_id)
    return concepts


def _get_statement_concepts(xbrl: 'XBRL') -> Dict[str, Dict[str, set]]:
    """Build a map of statement_type -> {role, concepts} for core financial statements.

    Cached on the XBRL instance to avoid re-scanning presentation trees per note.

    Returns:
        Dict mapping statement_type (e.g. 'BalanceSheet') to dict with 'role' and 'concepts'
    """
    # Return cached result if available
    if xbrl._statement_concepts_cache is not None:
        return xbrl._statement_concepts_cache

    from edgar.xbrl.statements import Statements

    result = {}
    for stmt in xbrl.get_all_statements():
        category = Statements.classify_statement(stmt)
        if category != 'statement':
            continue
        stmt_type = stmt.get('type', '')
        if 'Parenthetical' in stmt_type:
            continue
        tree = xbrl.presentation_trees.get(stmt['role'])
        if not tree:
            continue
        concepts = {eid for eid in tree.all_nodes if _is_data_concept(eid)}
        result[stmt_type] = {'role': stmt['role'], 'concepts': concepts}

    xbrl._statement_concepts_cache = result
    return result


def _get_concept_label(concept_id: str, xbrl: 'XBRL') -> str:
    """Get the human-readable label for a concept from the XBRL label linkbase."""
    # Try the element catalog for a label
    catalog_entry = xbrl.parser.element_catalog.get(concept_id)
    if catalog_entry and catalog_entry.labels:
        # Prefer standard label
        for label_role, label_text in catalog_entry.labels.items():
            if 'label' in label_role.lower() or 'standard' in label_role.lower():
                return label_text
        # Any label
        return next(iter(catalog_entry.labels.values()))

    # Fallback: convert concept ID to readable form
    # "us-gaap_LongTermDebtNoncurrent" → "Long Term Debt Noncurrent"
    name = concept_id.split('_', 1)[-1] if '_' in concept_id else concept_id
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', name)


def _compute_expands(note: 'Note', xbrl: Optional['XBRL']) -> List[tuple]:
    """Compute (concept_id, label) pairs for concepts shared between note and statements."""
    if not xbrl:
        return []

    note_concepts = _collect_note_concepts(note, xbrl)
    if not note_concepts:
        return []

    stmt_map = _get_statement_concepts(xbrl)
    overlapping = set()
    for stmt_info in stmt_map.values():
        overlapping |= (note_concepts & stmt_info['concepts'])

    if not overlapping:
        return []

    # Get labels and sort
    result = [(cid, _get_concept_label(cid, xbrl)) for cid in overlapping]
    result.sort(key=lambda x: x[1])
    return result


def _compute_expands_with_statements(note: 'Note', xbrl: 'XBRL') -> tuple:
    """Compute expands data plus which statement types are involved.

    Returns:
        Tuple of ([(concept_id, label), ...], {statement_type, ...})
    """
    note_concepts = _collect_note_concepts(note, xbrl)
    if not note_concepts:
        return [], set()

    stmt_map = _get_statement_concepts(xbrl)
    all_overlapping = []
    stmt_types = set()

    for stmt_type, stmt_info in stmt_map.items():
        overlap = note_concepts & stmt_info['concepts']
        if overlap:
            stmt_types.add(stmt_type)
            for cid in overlap:
                all_overlapping.append((cid, _get_concept_label(cid, xbrl)))

    # Deduplicate
    seen = set()
    unique = []
    for item in all_overlapping:
        if item[0] not in seen:
            seen.add(item[0])
            unique.append(item)
    unique.sort(key=lambda x: x[1])

    return unique, stmt_types


# ── Reverse index: concept → notes ──────────────────────────────────────────

def _build_concept_to_notes_index(notes: 'Notes', xbrl: 'XBRL') -> Dict[str, List['Note']]:
    """Build a reverse index mapping concept_id → list of Notes that cover it.

    Each Note's concepts (from its own role + children's roles) are collected
    and inverted so a statement line item can find its related notes.
    """
    index: Dict[str, List[Note]] = {}
    for note in notes:
        concepts = _collect_note_concepts(note, xbrl)
        for concept_id in concepts:
            if concept_id not in index:
                index[concept_id] = []
            index[concept_id].append(note)
    return index


def _get_concept_to_notes_index(xbrl: 'XBRL') -> Dict[str, List['Note']]:
    """Get or lazily build the concept→notes reverse index, cached on XBRL."""
    if xbrl._concept_to_notes_cache is not None:
        return xbrl._concept_to_notes_cache

    # Build Notes if not already cached — use FilingSummary if available
    # for rich hierarchy (tables/policies/details as children)
    notes = xbrl._notes_cache
    if notes is None:
        notes = Notes.from_xbrl(xbrl, filing_summary=xbrl._filing_summary)

    index = _build_concept_to_notes_index(notes, xbrl)
    xbrl._concept_to_notes_cache = index
    return index


def get_notes_for_concept(concept_id: str, xbrl: 'XBRL') -> List['Note']:
    """Get all Notes that contain a given concept, ranked by specificity.

    The most specific note (fewest total concepts) is returned first.
    """
    index = _get_concept_to_notes_index(xbrl)
    notes = index.get(concept_id, [])
    if len(notes) <= 1:
        return notes
    return _rank_notes_for_concept(notes, concept_id, xbrl)


def _rank_notes_for_concept(notes: List['Note'], concept_id: str, xbrl: 'XBRL') -> List['Note']:
    """Rank notes by relevance to a specific concept.

    Scoring (lower = better):
    1. Fewer total concepts in the note → more specific
    2. Concept label appears in note title → direct match
    3. Lower note number → earlier in filing, more likely primary
    """
    concept_label = _get_concept_label(concept_id, xbrl).lower()
    label_words = set(concept_label.split())

    # Pre-compute concept counts using the already-built index to avoid
    # re-scanning presentation trees per note
    index = xbrl._concept_to_notes_cache or {}
    # Count how many index entries each note appears in (= its concept breadth)
    note_concept_counts: Dict[int, int] = {}
    for concept_notes in index.values():
        for n in concept_notes:
            note_concept_counts[id(n)] = note_concept_counts.get(id(n), 0) + 1

    scored = []
    for note in notes:
        # Specificity: fewer concepts = more focused note
        specificity = note_concept_counts.get(id(note), 0)

        # Title match: does the note title overlap with concept label?
        title_words = set(note.short_name.lower().split())
        title_overlap = len(label_words & title_words)
        title_bonus = -100 * title_overlap  # Negative = better

        # Position: earlier notes are usually more primary
        position = note.number

        scored.append((title_bonus + specificity + position, note))

    scored.sort(key=lambda x: x[0])
    return [note for _, note in scored]
