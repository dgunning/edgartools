"""
Statement-level fidelity: the library's statements against the SEC's statement pages.

``compare_viewer_to_xbrl`` (``viewer_validation``) checks each numeric cell
of the SEC's rendered statement pages (``R*.htm``) against the XBRL fact it
shows. Users read statements, not facts: ``xbrl.statements.balance_sheet()``,
``Financials``, ``Statement.to_dataframe()``, the rendered table. This module
compares those with the same pages, row by row and cell by cell, and
reports what is on each side.

It reports observations, not verdicts. Every outcome has a kind named for
what was observed (``KINDS``), and each kind belongs to one family
(``FAMILIES``): a disagreement between the library and the page, a
presentation difference, or a cell, row or page that could not be compared.

Usage::

    viewer = filing.viewer
    results = compare_statements_to_viewer(viewer, filing.xbrl())
    results.value_rate('dataframe'), results.coverage('dataframe')
    results.counts()                 # outcomes by kind and surface
    results.to_dataframe()           # one row per outcome

How a page meets a library statement
------------------------------------
Each page in the filing's Statements menu is compared with the library
statement a user gets for the page's presentation role: the typed getter's
``Statement`` (``balance_sheet()``, ``income_statement(parenthetical=True)``
...) when a getter resolves to that role, as ``Financials`` does, and
``xbrl.statements[role]`` otherwise. ``StatementFidelityPage.access`` says
which.

Two surfaces are compared: ``'dataframe'`` (``Statement.to_dataframe()``)
and ``'rendered'`` (``Statement.render()``: the values of
``RenderedStatement.to_dataframe()`` and each cell's printed text). Each is
compared in its default view; a page period the default view leaves out is
requested with ``period_filter`` and reported as ``period_not_in_default_view``
beside the value outcome.

Rows
----
A page row is identified by its concept, its member context (the member
header above it, as the facts check reads it) and which of the page's rows
of that concept in that context it is (the facts check's ``row_occurrence``,
counted over every data row). A library row is identified the same way from
its concept and dimensions. A page row is aligned only when the facts check
matched at least one of its cells to a fact, so its context is established
by a fact and not by its position; a row that is not aligned keeps its
occurrence, so the rows after it are not renumbered. Rows on a
co-registrant's own statement (``XBRL._coregistrant_member``) are read as
the library shows them, with the member's facts in plain rows.

Cells
-----
Every cell is the facts check's own: its concept, period, dimensions, unit,
the fact it was paired with and the sign the page shows. A cell is compared
when the facts check matched it, its row is aligned and its column's own
period (``ComparisonResult.column_period_key``) is known. The library's value
under that period, as a user requesting it sees it, is compared with the
paired fact (same value) and with the page's displayed sign (same sign).
Nothing is decided by value alone: a unit outcome needs the measures
(currency or unit) to differ, and a duplicate outcome needs the facts
check's less-precise-duplicate note and a fact of the paired fact's unit
filed with the library's value.

Headline
--------
Per surface:

- ``compared_cells(surface)``: the page cells the facts check matched to a
  fact, whose row is aligned with a library row and whose column's period
  is known, less those whose library row shows the period in another
  measure (``unit_column_not_shown``) and those the page prints from a less
  precise duplicate fact (``less_precise_duplicate``). Each has exactly one
  of ``cell_matched``, ``value_not_shown``, ``value_differs``,
  ``sign_differs``, ``negative_zero``, ``row_missing_in_period_request`` or
  ``library_raised``. When the surface's own call on the page's statement
  raises (``statement_raised``), no library row can be aligned, so the page's
  cells that would have been looked up count as ``library_raised``: those the
  facts check matched, in a row whose context the facts check established,
  under a column whose own period is known.
- ``value_rate(surface)``: ``cell_matched`` over ``compared_cells``: the
  share the library shows, under the page column's own period (requested
  when the default view leaves it out), with the paired fact's value and
  the page's sign.
- ``coverage(surface)``: ``compared_cells`` over every numeric cell of the
  statement pages (``facts.total``), including pages that are not compared.

Everything else is reported beside the pair, never folded into it.

Limits
------
- Statement-of-equity pages (member columns, period blocks in rows) are not
  compared; their cells count in the coverage denominator.
- Abstract rows are compared only outside member headers; the page repeats
  them under every header and the library shows each once.
- ``Statement.to_dataframe()`` names only the first axis of a dimensional row;
  a DataFrame row with several axes cannot be identified.
"""
from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Tuple

from edgar.exceptions import ValidationError
from edgar.xbrl import viewer_validation as vv

if TYPE_CHECKING:
    from edgar.xbrl.viewer import FilingViewer
    from edgar.xbrl.xbrl import XBRL

__all__ = ['compare_statements_to_viewer', 'StatementFidelityResults', 'StatementFidelityResult',
           'StatementFidelityPage', 'KINDS', 'FAMILIES', 'DISAGREEMENT', 'PRESENTATION',
           'NOT_COMPARABLE', 'MATCHED', 'SURFACES']

SURFACES = ('dataframe', 'rendered')

# Families
DISAGREEMENT = 'disagreement'
PRESENTATION = 'presentation'
NOT_COMPARABLE = 'not_comparable'
MATCHED = 'matched'

#: Every outcome kind: (family, level, what was observed). The one place the
#: kinds are grouped into families.
KINDS: Dict[str, Tuple[str, str, str]] = {
    # Matched
    'row_matched': (MATCHED, 'row', "the page row has a library row: same concept, context and occurrence"),
    'abstract_row_matched': (MATCHED, 'row', "the page's heading row has a library heading row"),
    'cell_matched': (MATCHED, 'cell', "the library shows the paired fact's value with the page's sign"),
    # Disagreements
    'no_library_statement': (DISAGREEMENT, 'page', "the library has no statement for the page's role"),
    'statement_raised': (DISAGREEMENT, 'page',
                         "the surface's call (to_dataframe() or render()) raised on the page's statement; "
                         "reason has the exception"),
    'library_raised': (DISAGREEMENT, 'cell',
                       "the call a user makes for the cell's value raised: the surface's call on the page's "
                       "statement, or the request for the column's period alone; reason has the exception"),
    'getter_raised': (DISAGREEMENT, 'filing',
                      "a typed getter raised; its role is not known, so the page it would claim is compared "
                      "with the statement by role; reason has the exception"),
    'getter_outside_statements': (DISAGREEMENT, 'filing',
                                  "a typed getter resolves to a role that is not in the Statements menu"),
    'row_dropped': (DISAGREEMENT, 'row', "the page row has no library row"),
    'row_merged': (DISAGREEMENT, 'row',
                   "the page row has no library row: the library merged its concept's row into an adjacent row "
                   "of another concept with the same label (statements._merge_complementary_rows), which shows "
                   "its values"),
    'abstract_row_dropped': (DISAGREEMENT, 'row',
                             "the page's heading row has no library row, and the library's own hiding rule "
                             "does not hide it"),
    'duplicate_library_row': (DISAGREEMENT, 'row',
                              "a library row the page does not show, with values, for a concept and context "
                              "that already has a row aligned with the page"),
    'extra_row_outside_role': (DISAGREEMENT, 'row',
                               "a library row the page does not show, in a context whose axis or member "
                               "the role's presentation does not include"),
    'label_differs': (DISAGREEMENT, 'row', "the library row's label is not the page's"),
    'row_missing_in_period_request': (DISAGREEMENT, 'cell',
                                      "requesting the cell's period alone returns no row for it"),
    'value_not_shown': (DISAGREEMENT, 'cell', "the library row shows no value for the period"),
    'value_differs': (DISAGREEMENT, 'cell', "the library value is not the paired fact's"),
    'sign_differs': (DISAGREEMENT, 'cell', "the library value has the paired fact's magnitude and the "
                                          "opposite sign to the page"),
    'negative_zero': (DISAGREEMENT, 'cell', "the library value is -0.0 where the page shows 0"),
    'zero_rendered_blank': (DISAGREEMENT, 'cell', "the rendered table prints nothing where the page shows 0"),
    'rendered_text_blank': (DISAGREEMENT, 'cell',
                            "the rendered table prints nothing where the page shows a non-zero value"),
    'rendered_text_sign_differs': (DISAGREEMENT, 'cell',
                                   "the rendered table's text is signed differently from the page"),
    'access_path_disagrees': (DISAGREEMENT, 'cell',
                              "the DataFrame of the Statement by role and of the typed getter's Statement "
                              "show different values for the cell"),
    'surfaces_disagree': (DISAGREEMENT, 'cell',
                          "the DataFrame and the rendered table show different values for the cell"),
    # Presentation differences
    'period_not_in_default_view': (PRESENTATION, 'cell',
                                   "the page's period is not in the surface's default view; it was requested"),
    'unit_column_not_shown': (PRESENTATION, 'cell',
                              "the page shows the cell in another measure (currency or unit) than the library "
                              "row's for that period"),
    'shown_under_fact_period': (PRESENTATION, 'cell',
                                "beside a cell whose column the library does not match: the library shows the "
                                "paired fact's value under the fact's own period, which the page's column is not"),
    'less_precise_duplicate': (PRESENTATION, 'cell',
                               "the page prints a less precise duplicate fact; the library shows another "
                               "fact filed for the same context"),
    'row_out_of_order': (PRESENTATION, 'row', "the library row is not in the page's relative order"),
    'extra_row_in_role': (PRESENTATION, 'row',
                          "a library row the page does not show, in a context the role's presentation includes"),
    'dimension_row_label': (PRESENTATION, 'row',
                            "the library labels a dimension row with its member, the page with the concept"),
    'abstract_row_hidden': (PRESENTATION, 'row',
                            "the page's heading row is hidden by the library's structural-element rule "
                            "(statements.is_xbrl_structural_element)"),
    'coregistrant_parent_row': (PRESENTATION, 'row',
                                "a plain row on a co-registrant's statement page shows the parent's facts; "
                                "the library's statement for the role shows only the co-registrant"),
    # Not comparable
    'page_not_compared': (NOT_COMPARABLE, 'page', "the page is not compared; reason says why"),
    'row_not_comparable': (NOT_COMPARABLE, 'row', "the row cannot be identified; reason says why"),
    'library_row_not_identifiable': (NOT_COMPARABLE, 'row',
                                     "a library row whose dimensions the surface does not name in full"),
    'cell_not_comparable': (NOT_COMPARABLE, 'cell', "the cell does not reach the value comparison; reason says why"),
}

#: Kinds by family.
FAMILIES: Dict[str, Tuple[str, ...]] = {
    family: tuple(kind for kind, (fam, _level, _text) in KINDS.items() if fam == family)
    for family in (MATCHED, DISAGREEMENT, PRESENTATION, NOT_COMPARABLE)
}

# The value outcomes of a cell that reached the value comparison: exactly one per cell and surface.
# The headline's denominator; the two presentation outcomes that also end a cell's comparison
# (unit_column_not_shown, less_precise_duplicate) are not in it.
_VALUE_KINDS = ('cell_matched', 'value_not_shown', 'value_differs', 'sign_differs', 'negative_zero',
                'row_missing_in_period_request', 'library_raised')

# Typed getters, in the order a role is claimed by the first that resolves to it.
_GETTERS = ('balance_sheet', 'income_statement', 'cash_flow_statement', 'statement_of_equity',
            'comprehensive_income')

# DataFrame columns that are not periods (Statement.to_dataframe()).
_DATAFRAME_METADATA = frozenset({
    'concept', 'label', 'standard_concept', 'level', 'abstract', 'dimension', 'is_breakdown',
    'dimension_axis', 'dimension_member', 'dimension_member_label', 'dimension_label', 'balance',
    'weight', 'preferred_sign', 'parent_concept', 'parent_abstract_concept', 'unit', 'point_in_time'})

# "axis QName: member label" items of a DataFrame row's dimension_label.
_AXIS_IN_LABEL = re.compile(r'(?:^|, )[\w.-]+:[\w.-]+: ')

# The facts check's note on a cell matched against a less precise duplicate (``_emit_less_precise_match``).
_LESS_PRECISE_NOTE = 'the page shows a less precise duplicate'

# The renderer joins a row's headings with ' | ' (EdgarRenderer Filing.rowSeparatorStr,
# Report.py ``Label``): the element's label, then the row's unit when the row
# carries one. The label is the first heading.
_ROW_SEPARATOR = ' | '


@dataclass
class StatementFidelityResult:
    """One observation: a page, row or cell outcome on one surface."""
    kind: str
    page: str = ''
    role: str = ''
    #: 'dataframe', 'rendered', or '' for an outcome not tied to one surface.
    surface: str = ''
    concept: str = ''
    #: The row's member context as ``{axis: member}`` QNames.
    dimensions: Optional[Dict[str, str]] = None
    occurrence: Optional[int] = None
    #: The page column (cells).
    column: Optional[str] = None
    period_key: Optional[str] = None
    page_label: Optional[str] = None
    library_label: Optional[str] = None
    page_value: Optional[float] = None
    fact_value: Optional[float] = None
    library_value: Any = None
    library_text: Optional[str] = None
    #: Whether the surface's default view shows the period (cells).
    default_view: Optional[bool] = None
    reason: Optional[str] = None
    #: The facts check's outcome for the cell.
    fact: Optional[vv.ComparisonResult] = field(default=None, repr=False)

    @property
    def family(self) -> str:
        return KINDS[self.kind][0]

    @property
    def level(self) -> str:
        return KINDS[self.kind][1]


@dataclass
class StatementFidelityPage:
    """A statement page and the library statement it was compared with."""
    page: str
    role: str
    #: How the statement was obtained: ``'balance_sheet()'``,
    #: ``'income_statement(parenthetical=True)'``, ``'statements[role]'``,
    #: or None when the library has none.
    access: Optional[str]
    compared: bool
    #: Numeric cells on the page (the facts check's count).
    cells: int
    reason: Optional[str] = None


@dataclass
class StatementFidelityResults:
    """Every outcome of ``compare_statements_to_viewer``, with the facts check it read."""
    facts: vv.ComparisonResults
    pages: List[StatementFidelityPage] = field(default_factory=list)
    results: List[StatementFidelityResult] = field(default_factory=list)

    def of_kind(self, kind: str, surface: Optional[str] = None) -> List[StatementFidelityResult]:
        if kind not in KINDS:
            raise ValidationError(f"unknown kind {kind!r}; kinds are {', '.join(KINDS)}")
        return [r for r in self.results if r.kind == kind and (surface is None or r.surface == surface)]

    def counts(self) -> Dict[Tuple[str, str], int]:
        """Outcomes by (kind, surface)."""
        return dict(Counter((r.kind, r.surface) for r in self.results))

    def family_counts(self, surface: Optional[str] = None) -> Dict[str, int]:
        """Outcomes by family; surface-independent outcomes are counted for every surface."""
        return dict(Counter(r.family for r in self.results
                            if surface is None or r.surface in (surface, '')))

    def compared_cells(self, surface: str) -> int:
        """Cells that reached the value comparison on ``surface``: the headline's denominator."""
        _check_surface(surface)
        return sum(1 for r in self.results if r.surface == surface and r.kind in _VALUE_KINDS)

    def value_rate(self, surface: str) -> float:
        """Share of compared cells the library shows with the paired fact's value and the page's sign."""
        compared = self.compared_cells(surface)
        matched = len(self.of_kind('cell_matched', surface))
        return matched / compared if compared else 0.0

    def coverage(self, surface: str) -> float:
        """Compared cells over every numeric cell of the statement pages."""
        return self.compared_cells(surface) / self.facts.total if self.facts.total else 0.0

    def to_dataframe(self):
        import pandas as pd
        return pd.DataFrame([{
            'kind': r.kind, 'family': r.family, 'level': r.level, 'surface': r.surface, 'page': r.page,
            'role': r.role, 'concept': r.concept, 'dimensions': r.dimensions, 'occurrence': r.occurrence,
            'column': r.column, 'period_key': r.period_key, 'page_label': r.page_label,
            'library_label': r.library_label, 'page_value': r.page_value, 'fact_value': r.fact_value,
            'library_value': r.library_value, 'library_text': r.library_text,
            'default_view': r.default_view, 'reason': r.reason,
        } for r in self.results])

    def __str__(self):
        parts = []
        for surface in SURFACES:
            parts.append(f"{surface}: value_rate={self.value_rate(surface):.1%} "
                         f"coverage={self.coverage(surface):.1%} "
                         f"disagreements={self.family_counts(surface).get(DISAGREEMENT, 0)}")
        return f"StatementFidelityResults({len(self.pages)} pages; " + '; '.join(parts) + ")"

    def __rich__(self):
        from rich.table import Table
        table = Table(title="Statements vs SEC viewer", show_header=True, header_style="dim")
        table.add_column("Kind")
        table.add_column("Family", style="dim")
        for surface in SURFACES:
            table.add_column(surface, justify="right")
        table.add_column("other", justify="right")
        counts = self.counts()
        for kind, (family, _level, _text) in KINDS.items():
            row = [counts.get((kind, s), 0) for s in SURFACES] + [counts.get((kind, ''), 0)]
            if any(row):
                table.add_row(kind, family, *[str(n) for n in row])
        for surface in SURFACES:
            table.caption = (table.caption or '') + (
                f"{surface}: value rate {self.value_rate(surface):.1%}, "
                f"coverage {self.coverage(surface):.1%}  ")
        return table

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


def _check_surface(surface: str) -> None:
    if surface not in SURFACES:
        raise ValidationError(f"unknown surface {surface!r}; surfaces are {', '.join(SURFACES)}")


# ---------------------------------------------------------------------------
# Library side

def _sign(value: float) -> str:
    if value == 0:
        return '-0' if math.copysign(1.0, value) < 0 else '0'
    return '-' if value < 0 else '+'


def _number(value) -> Optional[float]:
    if value is None or isinstance(value, (str, bool)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _text_sign(text: str) -> Optional[str]:
    """The sign a rendered cell's text prints: '-' for parentheses or a minus, '+' otherwise."""
    stripped = text.strip()
    if not stripped:
        return None
    return '-' if '(' in stripped or re.match(r'^\W*-', stripped) else '+'


class _LibraryCallError(Exception):
    """The library call a user makes for a surface raised; carries the exception's type and message."""

    def __init__(self, error: BaseException):
        super().__init__(f"{type(error).__name__}: {error}")
        self.message = f"{type(error).__name__}: {error}"


class _Surface:
    """One library presentation of a statement: rows with identity, values by period key."""

    def __init__(self, kind: str, statement, names: vv._Names, tree_ids: FrozenSet[str],
                 period_filter: Optional[str] = None):
        self.kind = kind
        self.rows: List[dict] = []
        self.keys: List[str] = []       # rendered: the header's period keys
        self.columns: List[str] = []    # dataframe: period columns
        self.period_filter = period_filter
        self.error: Optional[str] = None
        #: Whether ``error`` is the library's: the surface's own call (``to_dataframe()`` or
        #: ``render()``) raised. Otherwise the check could not read what the call returned.
        self.library_raised = False
        try:
            if kind == 'dataframe':
                self._read_dataframe(statement, names, tree_ids, period_filter)
            else:
                self._read_rendered(statement, names, tree_ids, period_filter)
        except _LibraryCallError as e:
            self.error, self.library_raised = e.message, True
        except Exception as e:  # noqa: BLE001 - reported as an outcome, never hidden
            self.error = f"{type(e).__name__}: {e}"
        seen: Counter = Counter()
        for row in self.rows:
            base = ('A' if row['abstract'] else 'D', row['concept'], row['dims'])
            row['key'] = base + (seen[base],)
            seen[base] += 1
        self.by_key = {row['key']: row for row in self.rows}

    def _read_rendered(self, statement, names, tree_ids, period_filter):
        from edgar.xbrl.rendering import _presentation_sign_source, apply_presentation_sign
        library_rows = []
        try:
            # Everything the library computes for a user reading the table: the table, each
            # cell's signed value (as RenderedStatement.to_dataframe() applies the presentation
            # sign, so value and text are one cell's) and its printed text.
            rendered = statement.render(period_filter=period_filter) if period_filter else statement.render()
            keys = list(rendered.header.period_keys)
            for row in rendered.rows:
                values, text = {}, {}
                for i, key in enumerate(keys):
                    if i < len(row.cells):
                        cell = row.cells[i]
                        signs, sign_key = _presentation_sign_source(row, key)
                        values[key] = apply_presentation_sign(cell.value, signs, sign_key)
                        text[key] = cell.get_formatted_value()
                library_rows.append((row, values, text))
        except Exception as e:  # noqa: BLE001 - the library's own calls
            raise _LibraryCallError(e) from e
        self.keys = keys
        for row, values, text in library_rows:
            metadata = row.metadata or {}
            dims, in_role = _library_dims(names, tree_ids, metadata.get('dimension_metadata'))
            self.rows.append(dict(concept=vv._normalize_concept_id(metadata.get('concept') or ''), dims=dims,
                                  in_role=in_role, label=row.label, abstract=bool(row.is_abstract),
                                  dimension=bool(row.is_dimension), values=values, text=text,
                                  units=dict(metadata.get('units') or {})))

    def _read_dataframe(self, statement, names, tree_ids, period_filter):
        try:
            frame = statement.to_dataframe(period_filter=period_filter) if period_filter else statement.to_dataframe()
            columns, records = list(frame.columns), frame.to_dict('records')
        except Exception as e:  # noqa: BLE001 - the library's own calls (a DataFrame a user cannot read raises here)
            raise _LibraryCallError(e) from e
        self.columns = [c for c in columns if c not in _DATAFRAME_METADATA]
        for record in records:
            dims, in_role = frozenset(), True
            if record.get('dimension'):
                axis, member = record.get('dimension_axis'), record.get('dimension_member')
                if axis and len(_AXIS_IN_LABEL.findall(record.get('dimension_label') or '')) <= 1:
                    dims, in_role = _library_dims(names, tree_ids, [{'dimension': axis, 'member': member}])
                else:
                    dims, in_role = None, None
            self.rows.append(dict(concept=vv._normalize_concept_id(record.get('concept') or ''), dims=dims,
                                  in_role=in_role, label=record.get('label'), abstract=bool(record.get('abstract')),
                                  dimension=bool(record.get('dimension')),
                                  values={c: record.get(c) for c in self.columns}, text={}, units={}))


def _library_dims(names: vv._Names, tree_ids: FrozenSet[str], dimension_metadata
                  ) -> Tuple[Optional[FrozenSet], Optional[bool]]:
    """A library row's dimensions as the facts check names them, and whether the role presents them.

    A context is in the role when the role's presentation tree has every
    axis and every explicit member as a node.
    """
    if not dimension_metadata:
        return frozenset(), True
    if isinstance(dimension_metadata, dict):
        dimension_metadata = [dimension_metadata]
    dims, in_role = {}, True
    for item in dimension_metadata:
        axis, member = item.get('dimension'), item.get('member')
        if not axis or member is None:
            return None, None
        axis_id = axis.replace(':', '_', 1)
        typed = axis in names.typed
        member_qname = member if typed or ':' in member else vv._normalize_concept_id(member)
        dims[axis] = member_qname
        member_id = member_qname.replace(':', '_', 1)
        if axis_id not in tree_ids or (not typed and member_id not in tree_ids):
            in_role = False
    return names.context_dims(dims), in_role


def _typed_statements(xbrl) -> Tuple[Dict[str, Tuple[str, Any]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Role -> (getter, Statement) for every typed getter that resolves, (getter, role) for each,
    and (getter, exception) for each getter that raised."""
    by_role: Dict[str, Tuple[str, Any]] = {}
    resolved: List[Tuple[str, str]] = []
    raised: List[Tuple[str, str]] = []
    for name in _GETTERS:
        for parenthetical in (False, True):
            getter = f"{name}(parenthetical={parenthetical})" if parenthetical else f"{name}()"
            try:
                statement = getattr(xbrl.statements, name)(parenthetical=parenthetical)
                role = statement.role_or_type if statement is not None else None
            except Exception as e:  # noqa: BLE001 - reported as getter_raised; the role's statement is used
                raised.append((getter, f"{type(e).__name__}: {e}"))
                continue
            if statement is None:
                continue  # the filing has no such statement
            resolved.append((getter, role))
            by_role.setdefault(role, (getter, statement))
    return by_role, resolved, raised


# ---------------------------------------------------------------------------
# The comparison

def compare_statements_to_viewer(viewer: 'FilingViewer', xbrl: 'XBRL',
                                 tolerance: Optional[float] = None) -> StatementFidelityResults:
    """
    Compare the library's statements with the SEC's statement pages, row by row and cell by cell.

    The facts check (``compare_viewer_to_xbrl``) runs once and is returned as
    ``.facts``; its cell pairings are what this check compares. See the module
    docstring for how pages, rows and cells are aligned, the kinds and their
    families (``KINDS``, ``FAMILIES``) and the headline pair
    (``value_rate`` and ``coverage`` per surface).

    Args:
        viewer: FilingViewer for the filing (``filing.viewer``)
        xbrl: XBRL object from ``filing.xbrl()``
        tolerance: passed to the facts check

    Returns:
        StatementFidelityResults
    """
    check = vv._facts_check(viewer, xbrl, tolerance)
    out = StatementFidelityResults(facts=check.results)
    typed, resolved, raised = _typed_statements(xbrl)
    for getter, error in raised:
        out.results.append(StatementFidelityResult(kind='getter_raised', reason=f"{getter} raised {error}"))
    page_roles = {vr.role for vr, _start, _end in check.pages}
    for getter, role in resolved:
        if role not in page_roles:
            out.results.append(StatementFidelityResult(
                kind='getter_outside_statements', role=role,
                reason=f"{getter} resolves to {role}, which is not in the filing's Statements menu"))

    for vr, start, end in check.pages:
        cells = check.results.results[start:end]
        _compare_page(out, check, xbrl, typed, vr, cells)
    return out


def _compare_page(out: StatementFidelityResults, check: SimpleNamespace, xbrl, typed, vr,
                  cells: List[vv.ComparisonResult]) -> None:
    role = vr.role or ''
    page = vr.short_name
    getter, statement = typed.get(role, (None, None))
    role_statement = xbrl.statements[role] if role else None
    access = getter or ('statements[role]' if role_statement is not None else None)
    statement = statement if statement is not None else role_statement

    def not_compared(reason):
        out.pages.append(StatementFidelityPage(page, role, access, False, len(cells), reason))
        out.results.append(StatementFidelityResult(kind='page_not_compared', page=page, role=role, reason=reason))

    if statement is None:
        out.pages.append(StatementFidelityPage(page, role, None, False, len(cells), 'no library statement'))
        out.results.append(StatementFidelityResult(kind='no_library_statement', page=page, role=role,
                                                   reason=f"no library statement for role {role!r}"))
        return
    cr = vr.concept_report
    if cr is None:
        not_compared("the page could not be read")
        return
    if vv._is_equity_layout(cr) or not all(vv._parse_viewer_period(h) for h in cr.period_headers):
        not_compared("a statement-of-equity layout (member columns, period blocks in rows) is not "
                     "compared yet")
        return
    out.pages.append(StatementFidelityPage(page, role, access, True, len(cells)))
    tree = xbrl.presentation_trees.get(role)
    tree_ids = frozenset(tree.all_nodes) if tree is not None else frozenset()
    ctx = SimpleNamespace(out=out, check=check, xbrl=xbrl, vr=vr, cr=cr, page=page, role=role,
                          statement=statement, tree_ids=tree_ids, names=check.names,
                          coregistrant=xbrl._coregistrant_member(role))
    ctx.unaligned_keys = set()
    page_rows = _page_rows(ctx, cells)
    surfaces = {kind: _Surface(kind, statement, check.names, tree_ids) for kind in SURFACES}
    ctx.default_rendered = surfaces['rendered']
    ctx.requested = {}
    role_frame = (_Surface('dataframe', role_statement, check.names, tree_ids)
                  if getter and role_statement is not None else None)
    if role_frame is not None and role_frame.error:
        # The typed getter's statement is the one compared; the role's own is read only for
        # access_path_disagrees, which cannot be checked on this page.
        if role_frame.library_raised:
            out.results.append(StatementFidelityResult(
                kind='statement_raised', page=page, role=role, surface='dataframe',
                reason=f"statements[role].to_dataframe() raised {role_frame.error}; the page is compared "
                       f"through {getter}, and access_path_disagrees is not checked"))
        else:
            out.results.append(StatementFidelityResult(
                kind='page_not_compared', page=page, role=role, surface='dataframe',
                reason=f"access path statements[role]: the check could not read its DataFrame: "
                       f"{role_frame.error}; access_path_disagrees is not checked"))
    seen_values: Dict[tuple, Dict[str, Any]] = defaultdict(dict)
    for surface_name, surface in surfaces.items():
        if surface.error and surface.library_raised:
            _emit_statement_raised(ctx, surface_name, surface, page_rows, cells)
            continue
        if surface.error:
            out.results.append(StatementFidelityResult(
                kind='page_not_compared', page=page, role=role, surface=surface_name,
                reason=f"the check could not read the library statement: {surface.error}"))
            continue
        aligned = _compare_rows(ctx, surface_name, surface, page_rows)
        _compare_cells(ctx, surface_name, surface, aligned, cells, role_frame, seen_values)
    for values in seen_values.values():
        if len(values) == 2 and _differs(values['dataframe'][0], values['rendered'][0]):
            r = values['dataframe'][1]
            out.results.append(StatementFidelityResult(
                kind='surfaces_disagree', page=page, role=role, concept=r.concept_id,
                dimensions=r.xbrl_dimensions, column=r.period, period_key=r.column_period_key,
                page_value=r.viewer_value, fact_value=r.xbrl_fact_value, fact=r,
                library_value=values['dataframe'][0],
                reason=f"dataframe {values['dataframe'][0]!r}, rendered {values['rendered'][0]!r}"))


def _emit_statement_raised(ctx, surface_name: str, surface: _Surface, page_rows: List[dict],
                           cells: List[vv.ComparisonResult]) -> None:
    """The surface's call raised on the page's statement: one page outcome, and ``library_raised``
    for each cell that would have been looked up.

    Those are the cells the facts check matched, in a row whose context it
    established (a data row of ``page_rows``), under a column whose own period
    is known. No library row can be aligned, so a cell whose row the library
    would have dropped is counted too.
    """
    call = 'to_dataframe()' if surface_name == 'dataframe' else 'render()'
    reason = f"{call} raised {surface.error}"
    ctx.out.results.append(StatementFidelityResult(kind='statement_raised', page=ctx.page, role=ctx.role,
                                                   surface=surface_name, reason=reason))
    rows = {row['i'] for row in page_rows if row['kind'] == 'D'}
    for r in cells:
        if r.status == vv.MATCHED and r.row_index in rows and r.column_period_key is not None:
            ctx.out.results.append(StatementFidelityResult(
                kind='library_raised', page=ctx.page, role=ctx.role, surface=surface_name,
                concept=r.concept_id, dimensions=r.xbrl_dimensions, occurrence=r.row_occurrence,
                column=r.period, period_key=r.column_period_key, page_label=r.label,
                page_value=r.viewer_value, fact_value=r.xbrl_fact_value, fact=r, reason=reason))


def _differs(a, b) -> bool:
    na, nb = _number(a), _number(b)
    if na is None and nb is None:
        return False
    if na is None or nb is None:
        return True
    return na != nb or _sign(na) != _sign(nb)


def _page_rows(ctx, cells: List[vv.ComparisonResult]) -> List[dict]:
    """The page's rows with their identity, or the reason they have none (emitted)."""
    rows = ctx.cr.rows
    contexts = vv._row_contexts(rows, ctx.names, ctx.check.index)
    matched_rows = {r.row_index for r in cells if r.status == vv.MATCHED and r.row_index is not None}
    reasons_by_row: Dict[int, List[str]] = defaultdict(list)
    for r in cells:
        if r.row_index is not None and r.reason:
            reasons_by_row[r.row_index].append(f"{r.status}: {r.reason}")
    occurrence_by_row = {r.row_index: r.row_occurrence for r in cells
                         if r.row_index is not None and r.row_occurrence is not None}
    header_id = None
    seen: Counter = Counter()
    seen_data: Counter = Counter()
    page_rows = []
    for i, crow in enumerate(rows):
        if crow.is_header and crow.is_dimensional:
            header_id = crow.concept_id
        if crow.is_header:
            continue
        dims, reason = contexts[i]
        concept = vv._normalize_concept_id(crow.concept_id)
        base = dict(i=i, concept=concept, label=crow.label)
        if vv._is_data_row(crow):
            if ctx.coregistrant and header_id is None:
                _emit_row(ctx, '', 'coregistrant_parent_row', base, dims, reason=(
                    f"co-registrant role ({ctx.coregistrant}): the page's plain rows show the parent's facts"))
                continue
            # Which row of the concept in this context it is, counted over every data row (the facts
            # check's own count), so a row that is not aligned does not renumber the rows after it.
            occurrence = occurrence_by_row.get(i)
            if occurrence is None:
                occurrence = seen_data[(contexts[i], crow.concept_id)]
            seen_data[(contexts[i], crow.concept_id)] += 1
            if ctx.coregistrant and header_id and header_id.partition('=')[2] == ctx.coregistrant \
                    and dims is not None and len(dims) == 1:
                dims = frozenset()  # the library shows the co-registrant's facts in plain rows
            if dims is None or i not in matched_rows:
                why = reason if dims is None else (
                    "the facts check matched none of the row's cells, so its context is not established"
                    + (f" ({'; '.join(sorted(set(reasons_by_row[i]))[:2])})" if reasons_by_row[i] else ''))
                _emit_row(ctx, '', 'row_not_comparable', base, dims, reason=why, occurrence=occurrence)
                if dims is not None:
                    # The library row it would align with is the page's, not an extra one.
                    ctx.unaligned_keys.add(('D', concept, dims, occurrence))
                continue
            base.update(dims=dims, key=('D', concept, dims, occurrence), kind='D')
            page_rows.append(base)
            continue
        elif crow.is_abstract and not crow.is_dimensional:
            if header_id is not None:
                _emit_row(ctx, '', 'row_not_comparable', base, dims, reason=(
                    "a heading row under a member header: the page repeats headings under every "
                    "header and the library shows each once"))
                continue
            kind, dims = 'A', frozenset()
        else:
            continue
        key = (kind, concept, dims)
        base.update(dims=dims, key=key + (seen[key],), kind=kind)
        seen[key] += 1
        page_rows.append(base)
    return page_rows


def _emit_row(ctx, surface: str, kind: str, row: dict, dims, reason: Optional[str] = None,
              library_label: Optional[str] = None, occurrence: Optional[int] = None) -> None:
    ctx.out.results.append(StatementFidelityResult(
        kind=kind, page=ctx.page, role=ctx.role, surface=surface, concept=row['concept'],
        dimensions=_show_dims(ctx.names, dims), occurrence=occurrence, page_label=row.get('label'),
        library_label=library_label, reason=reason))


def _show_dims(names: vv._Names, dims) -> Optional[Dict[str, str]]:
    if dims is None:
        return None
    return {names.show(axis): names.show(member) for axis, member in sorted(dims)}


def _page_label(label: str) -> str:
    return ' '.join((label or '').split(_ROW_SEPARATOR)[0].split())


def _compare_rows(ctx, surface_name: str, surface: _Surface, page_rows: List[dict]) -> Dict[int, dict]:
    """Align page rows with the surface's rows and emit row outcomes; returns page row index -> library row."""
    aligned: Dict[int, dict] = {}
    matched_library = set()
    hidden = merged = None
    for row in page_rows:
        library_row = surface.by_key.get(row['key'])
        occurrence = row['key'][-1]
        if library_row is None:
            if row['kind'] == 'A':
                if hidden is None:
                    hidden = _hidden_abstracts(ctx.statement)
                hidden_by_rule, line_items = hidden
                if row['concept'] in hidden_by_rule:
                    _emit_row(ctx, surface_name, 'abstract_row_hidden', row, row['dims'], occurrence=occurrence)
                else:
                    _emit_row(ctx, surface_name, 'abstract_row_dropped', row, row['dims'], occurrence=occurrence,
                              reason=("in the statement's line items (get_raw_data), not shown"
                                      if row['concept'] in line_items else
                                      "not in the statement's line items (get_raw_data)"))
            else:
                count = sum(1 for r in surface.rows if r['key'][:3] == row['key'][:3])
                if merged is None:
                    merged = _merged_rows(ctx.statement, surface_name, surface.period_filter)
                into = merged.get(row['concept']) if not row['dims'] else None
                unnamed = row['dims'] and len(row['dims']) > 1 and any(
                    r['dims'] is None and r['concept'] == row['concept'] for r in surface.rows)
                if into:
                    _emit_row(ctx, surface_name, 'row_merged', row, row['dims'], occurrence=occurrence,
                              reason=f"merged into the {into} row")
                elif unnamed:
                    _emit_row(ctx, surface_name, 'library_row_not_identifiable', row, row['dims'],
                              occurrence=occurrence, reason=(
                                  "the page row has several axes; the surface names only the first axis of the "
                                  "library's rows of the concept with several"))
                else:
                    _emit_row(ctx, surface_name, 'row_dropped', row, row['dims'], occurrence=occurrence,
                              reason=f"the page has occurrence {occurrence}; the library has {count} row(s) of "
                                     "the concept in this context")
            continue
        matched_library.add(id(library_row))
        aligned[row['i']] = library_row
        if row['kind'] == 'A':
            _emit_row(ctx, surface_name, 'abstract_row_matched', row, row['dims'], occurrence=occurrence,
                      library_label=library_row['label'])
            continue
        _emit_row(ctx, surface_name, 'row_matched', row, row['dims'], occurrence=occurrence,
                  library_label=library_row['label'])
        page_label = _page_label(row['label'])
        library_label = ' '.join(str(library_row['label'] or '').split())
        if page_label != library_label:
            kind = 'dimension_row_label' if library_row['dimension'] else 'label_differs'
            _emit_row(ctx, surface_name, kind, row, row['dims'], occurrence=occurrence,
                      library_label=library_row['label'])
    _emit_order(ctx, surface_name, surface, page_rows, aligned)
    _emit_extra_rows(ctx, surface_name, surface, matched_library,
                     {(r['concept'], r['dims']) for r in aligned.values() if not r['abstract']})
    return aligned


def _hidden_abstracts(statement) -> Tuple[set, set]:
    """Abstract concepts the library's structural-element rule hides, and every concept of its line items."""
    from edgar.xbrl.statements import is_xbrl_structural_element
    try:
        items = statement.get_raw_data()
    except Exception:  # noqa: BLE001 - then nothing is known to be hidden
        return set(), set()
    return ({vv._normalize_concept_id(item.get('concept') or '') for item in items
             if item.get('is_abstract') and is_xbrl_structural_element(item)},
            {vv._normalize_concept_id(item.get('concept') or '') for item in items})


def _merged_rows(statement, surface_name: str = 'dataframe', period_filter: Optional[str] = None
                 ) -> Dict[str, str]:
    """Concepts whose rows the library merges into a row of another concept: {merged: kept}.

    Replays ``statements._merge_complementary_rows`` on a copy of the
    statement's line items before the merge, read as the surface reads them
    (``Statement.get_raw_data`` for ``to_dataframe()``, ``XBRL.render_statement``
    for ``render()``: the same view and period filter), and names, for each
    non-dimensional row it removes, the nearest kept row with the same label.
    """
    import copy

    from edgar.xbrl.presentation import StatementView
    from edgar.xbrl.statements import _merge_complementary_rows
    try:
        identifier = statement.canonical_type or statement.role_or_type
        if surface_name == 'dataframe':
            view = statement._view or StatementView.DETAILED
            items = statement.xbrl.get_statement(identifier, period_filter=period_filter, view=view) or []
        else:
            view = statement._view or StatementView.STANDARD
            items = statement.xbrl.get_statement(identifier, period_filter, True, view=view) or []
    except Exception:  # noqa: BLE001 - then no merge is known
        return {}
    items = copy.deepcopy(items)
    kept = _merge_complementary_rows(items)
    kept_ids = {id(item) for item in kept}
    merged = {}
    for i, item in enumerate(items):
        if id(item) in kept_ids or item.get('is_dimension') or item.get('is_abstract'):
            continue
        partners = [other for other in items[max(0, i - 2):i] if id(other) in kept_ids
                    and other.get('label') == item.get('label') and other.get('concept') != item.get('concept')]
        if partners:
            merged[vv._normalize_concept_id(item.get('concept') or '')] = vv._normalize_concept_id(
                partners[-1].get('concept') or '')
    return merged


def _emit_order(ctx, surface_name, surface, page_rows, aligned) -> None:
    """Rows outside one longest run in page order, within each member context."""
    position = {id(row): j for j, row in enumerate(surface.rows)}
    groups: Dict[Any, List[Tuple[dict, int]]] = defaultdict(list)
    for row in page_rows:
        if row['kind'] == 'D' and row['i'] in aligned:
            groups[row['dims']].append((row, position[id(aligned[row['i']])]))
    for items in groups.values():
        keep = _longest_increasing([j for _row, j in items])
        for n, (row, _j) in enumerate(items):
            if n not in keep:
                _emit_row(ctx, surface_name, 'row_out_of_order', row, row['dims'], occurrence=row['key'][-1])


def _longest_increasing(sequence: List[int]) -> set:
    tails, tail_index, previous = [], [], [-1] * len(sequence)
    for i, value in enumerate(sequence):
        j = bisect_left(tails, value)
        if j == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[j] = value
            tail_index[j] = i
        previous[i] = tail_index[j - 1] if j else -1
    keep, k = set(), tail_index[-1] if tail_index else -1
    while k != -1:
        keep.add(k)
        k = previous[k]
    return keep


def _emit_extra_rows(ctx, surface_name, surface, matched_library, aligned_contexts) -> None:
    for row in surface.rows:
        if id(row) in matched_library or row['abstract']:
            continue  # library headings are not reported: the page's cannot all be aligned
        if row['key'] in ctx.unaligned_keys:
            continue  # the twin of a page row that is not comparable (reported as such)
        base = dict(concept=row['concept'], label=None)
        has_value = any(_number(v) is not None for v in row['values'].values())
        if row['dims'] is None:
            kind, reason = 'library_row_not_identifiable', (
                "the DataFrame names only the first axis of a row with several")
        elif has_value and (row['concept'], row['dims']) in aligned_contexts:
            kind, reason = 'duplicate_library_row', (
                f"occurrence {row['key'][-1]}; another library row of the concept in this context is aligned")
        elif row['in_role']:
            kind, reason = 'extra_row_in_role', None
        else:
            kind, reason = 'extra_row_outside_role', None
        _emit_row(ctx, surface_name, kind, base, row['dims'], library_label=row['label'],
                  reason=reason if reason else ('has values' if has_value else 'no values'))


def _compare_cells(ctx, surface_name, surface, aligned, cells, role_frame, seen_values) -> None:
    role_by_key = role_frame.by_key if role_frame is not None and not role_frame.error else {}

    def emit(kind, r, period_key=None, **kw):
        ctx.out.results.append(StatementFidelityResult(
            kind=kind, page=ctx.page, role=ctx.role, surface=surface_name, concept=r.concept_id,
            dimensions=r.xbrl_dimensions, occurrence=r.row_occurrence, column=r.period,
            period_key=period_key or r.column_period_key, page_label=r.label, page_value=r.viewer_value,
            fact_value=r.xbrl_fact_value, fact=r, **kw))

    def lookup(key: str):
        """(surface, column, default view, None) for the period as a user gets it, or
        (None, reason, None, raised) with raised True when the library's request raised.

        The default view is read first; the period is requested alone only when
        the default view does not show it.
        """
        if surface_name == 'rendered' and key in surface.keys:
            return surface, key, True, None
        expected = _dataframe_column(ctx.xbrl, key) if surface_name == 'dataframe' else None
        if expected is not None and expected in surface.columns:
            named = _named_alone(ctx, key)
            if named is not None and named != expected:
                return None, (f"to_dataframe(period_filter={key}) names its column {named!r}, not {expected!r} "
                              "as the check expects"), None, False
            return surface, expected, True, None
        call = 'render' if surface_name == 'rendered' else 'to_dataframe'
        single = _requested(ctx, surface_name, key)
        if single.error:
            if single.library_raised:
                return None, f"{call}(period_filter={key}) raised {single.error}", None, True
            return None, f"{call}(period_filter={key}): the check could not read it: {single.error}", None, False
        if surface_name == 'rendered':
            return (single, key, False, None) if key in single.keys else (
                None, f"render(period_filter={key}) shows periods {single.keys}", None, False)
        if len(single.columns) != 1:
            return None, f"to_dataframe(period_filter={key}) gives columns {single.columns}", None, False
        column = single.columns[0]
        if expected is not None and column != expected:
            return None, (f"to_dataframe(period_filter={key}) names its column {column!r}, not {expected!r} "
                          "as the check expects"), None, False
        return (surface, column, True, None) if column in surface.columns else (single, column, False, None)

    for r in cells:
        if r.row_index is None:
            emit('cell_not_comparable', r, reason="the cell is in no row the facts check read")
            continue
        if r.status != vv.MATCHED:
            emit('cell_not_comparable', r, reason=f"facts check: {r.status}" + (f": {r.reason}" if r.reason else ''))
            continue
        library_row = aligned.get(r.row_index)
        if library_row is None:
            emit('cell_not_comparable', r, reason="the cell's row is not aligned")
            continue
        if r.column_period_key is None:
            emit('cell_not_comparable', r, reason="the column's own period is not known: several durations "
                                                  "in the filing render with its heading")
            continue
        # The page column's own period, as a user requesting it sees it.
        period_key = r.column_period_key
        source, column, default, raised = lookup(period_key)
        if source is None:
            emit('library_raised' if raised else 'cell_not_comparable', r, reason=column)
            continue
        if not default:
            emit('period_not_in_default_view', r, default_view=False)
            library_row = source.by_key.get(library_row['key'])
            if library_row is None:
                emit('row_missing_in_period_request', r, default_view=False)
                continue
        kind = _judge(ctx, emit, surface_name, r, library_row, column, default, period_key, role_by_key,
                      seen_values)
        if kind != 'cell_matched' and r.xbrl_period_key and r.xbrl_period_key != period_key:
            _beside_fact_period(emit, lookup, r, library_row['key'])


def _dataframe_column(xbrl, period_key: str) -> Optional[str]:
    """The column ``Statement.to_dataframe()`` names a period with, or None for a key it does not parse.

    Replays the naming in ``Statement._build_dataframe_from_raw_data``: the
    end date, with (Qn), (YTD) or (FY) for a duration of about three, six to
    nine, or twelve months. ``lookup`` checks the replay against the column of
    every period it requests alone, and of every default-view period it reads
    (once per page and period), so a change in the naming is reported as
    ``cell_not_comparable``, not hidden.
    """
    from datetime import datetime

    from edgar.xbrl.parsers.instance import _quarter_for_date
    parts = period_key.split('_')
    if period_key.startswith('instant_') and len(parts) >= 2:
        return parts[1]
    if not (period_key.startswith('duration_') and len(parts) >= 3):
        return None
    start, end = parts[1], parts[2]
    try:
        d0, d1 = datetime.strptime(start, '%Y-%m-%d'), datetime.strptime(end, '%Y-%m-%d')
    except ValueError:
        return end
    days = (d1 - d0).days
    if 80 <= days <= 100:
        entity_info = getattr(xbrl, 'entity_info', None) or {}
        fy_end_month = entity_info.get('fiscal_year_end_month')
        if fy_end_month:
            q = _quarter_for_date(d1, fy_end_month)
        else:
            month = d1.month
            q = "Q1" if month <= 3 or month == 12 else "Q2" if month <= 6 else "Q3" if month <= 9 else "Q4"
        return f"{end} ({q})"
    if 175 <= days <= 285:
        return f"{end} (YTD)"
    if days > 350:
        return f"{end} (FY)"
    return end


def _named_alone(ctx, period_key: str) -> Optional[str]:
    """The column ``to_dataframe(period_filter=period_key)`` names the period with, when it shows that period
    alone; None when the request raises or shows no single column, so the name cannot be verified."""
    single = _requested(ctx, 'dataframe', period_key)
    return single.columns[0] if not single.error and len(single.columns) == 1 else None


def _requested(ctx, surface_name: str, period_key: str) -> _Surface:
    """The surface read with ``period_filter=period_key`` (cached per page)."""
    cache = ctx.requested
    if (surface_name, period_key) not in cache:
        cache[(surface_name, period_key)] = _Surface(surface_name, ctx.statement, ctx.names, ctx.tree_ids,
                                                     period_filter=period_key)
    return cache[(surface_name, period_key)]


def _beside_fact_period(emit, lookup, r: vv.ComparisonResult, row_key) -> None:
    """Report, beside the column's outcome, whether the library shows the fact under its own period."""
    source, column, _default, _raised = lookup(r.xbrl_period_key)
    row = source.by_key.get(row_key) if source is not None else None
    value = _number(row['values'].get(column)) if row is not None else None
    if value is not None and _same_magnitude(value, r.xbrl_fact_value):
        emit('shown_under_fact_period', r, period_key=r.xbrl_period_key, library_value=row['values'].get(column),
             library_label=row['label'], reason=f"the page column's period is {r.column_period_key}")


def _same_magnitude(a: float, b: float) -> bool:
    return abs(abs(a) - abs(b)) <= 1e-9 * max(1.0, abs(b))


def _unit_measure(xbrl, unit_id: Optional[str]):
    """What a unit measures (its measure, or numerator and denominator), or None when unknown."""
    unit = (getattr(xbrl, 'units', None) or {}).get(unit_id) if unit_id else None
    if not unit:
        return None
    if unit.get('type') == 'divide':
        return ('divide', tuple(unit.get('numerator') or ()), tuple(unit.get('denominator') or ()))
    return unit.get('measure')


def _library_unit(ctx, surface_name, library_row, period_key, fact_period_key, default) -> Optional[str]:
    """The library row's unit for the period, from the rendered row (the DataFrame carries no units).

    The DataFrame surface reads the rendered row of the same request: the
    default view's, or ``render(period_filter=period_key)``'s. Units are keyed
    by the period the row's value was taken from: the column's, or the fact's
    own instant for a balance shown under a duration column.
    """
    if surface_name == 'rendered':
        units = library_row['units']
    else:
        rendered = ctx.default_rendered if default else _requested(ctx, 'rendered', period_key)
        twin = rendered.by_key.get(library_row['key']) if not rendered.error else None
        units = twin['units'] if twin is not None else {}
    return units.get(period_key) or (units.get(fact_period_key) if fact_period_key else None)


def _judge(ctx, emit, surface_name, r, library_row, column, default, period_key, role_by_key,
           seen_values) -> str:
    """Emit the value outcome of one compared cell (and the rendered-text outcomes); returns its kind."""
    raw = library_row['values'].get(column)
    value = _number(raw)
    text = library_row['text'].get(column) if surface_name == 'rendered' else None
    seen_values[(r.row_index, r.period)][surface_name] = (raw, r)
    common = dict(default_view=default, library_value=raw, library_label=library_row['label'], library_text=text)
    library_unit = _library_unit(ctx, surface_name, library_row, period_key, r.xbrl_period_key, default)
    page_measure, library_measure = _unit_measure(ctx.xbrl, r.xbrl_unit), _unit_measure(ctx.xbrl, library_unit)
    if page_measure is not None and library_measure is not None and page_measure != library_measure:
        emit('unit_column_not_shown', r, reason=f"page unit {r.xbrl_unit}, library row unit {library_unit}",
             **common)
        return 'unit_column_not_shown'
    if surface_name == 'dataframe' and default and role_by_key:
        # Compared only where the role's DataFrame has the same row and period column.
        role_row = role_by_key.get(library_row['key'])
        if role_row is not None and column in role_row['values'] and _differs(raw, role_row['values'][column]):
            role_value = role_row['values'][column]
            emit('access_path_disagrees', r, reason=f"statements[role] shows {role_value!r}", **common)
    if value is None:
        emit('value_not_shown', r, **common)
        return 'value_not_shown'
    page_sign, library_sign = _sign(r.viewer_value), _sign(value)
    if not _same_magnitude(value, r.xbrl_fact_value):
        if (r.note or '').startswith(_LESS_PRECISE_NOTE) and library_sign == page_sign \
                and _other_duplicate(ctx, r, value):
            kind = 'less_precise_duplicate'
            emit(kind, r, reason=r.note, **common)
        else:
            kind = 'value_differs'
            emit(kind, r, reason=library_unit and library_unit != r.xbrl_unit and
                 f"page unit {r.xbrl_unit}, library row unit {library_unit} (same measure)" or None, **common)
        return kind
    if library_sign == '-0':
        kind = 'negative_zero'
    elif library_sign != page_sign:
        kind = 'sign_differs'
    else:
        kind = 'cell_matched'
    emit(kind, r, reason=f"label role {r.label_role}" if kind == 'sign_differs' else None, **common)
    if surface_name == 'rendered' and text is not None:
        if not text.strip():
            emit('zero_rendered_blank' if r.viewer_value == 0 else 'rendered_text_blank', r, **common)
        elif _text_sign(text) != ('-' if r.viewer_value < 0 else '+'):
            emit('rendered_text_sign_differs', r, **common)
    return kind


def _other_duplicate(ctx, r: vv.ComparisonResult, value: float) -> bool:
    """Whether ``value`` is another fact of the paired fact's unit filed for the cell's concept, period and context."""
    if not r.xbrl_period_key:
        return False
    dims = None
    for row_dims in ctx.check.index.period_contexts.get((r.concept_id, r.xbrl_period_key), ()):
        if _show_dims(ctx.names, row_dims) == (r.xbrl_dimensions or {}):
            dims = row_dims
    if dims is None:
        return False
    return any(f.unit_ref == r.xbrl_unit and f.numeric_value != r.xbrl_fact_value
               and _same_magnitude(value, f.numeric_value)
               for f in ctx.check.index.facts.get((r.concept_id, r.xbrl_period_key, dims), ()))
