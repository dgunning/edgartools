"""
Cross-validation between the SEC Viewer (R*.htm) and XBRL parser output.

Compares values from the SEC's pre-rendered viewer reports against the
edgartools XBRL parser to detect discrepancies. The viewer is treated as
ground truth since it reflects the SEC's authoritative rendering.

Usage:
    from edgar.xbrl.viewer_validation import compare_viewer_to_xbrl

    viewer = filing.viewer
    xbrl = filing.xbrl()
    results = compare_viewer_to_xbrl(viewer, xbrl)
    results.match_rate          # 0.97
    results.mismatches          # [ComparisonResult(...), ...]
    results.to_dataframe()      # Full results as DataFrame
"""
import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from types import SimpleNamespace
from typing import TYPE_CHECKING, Dict, FrozenSet, List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from edgar.sgml.concept_extractor import declared_currency_scales, is_currency_unit, parse_numeric, unit_code, unit_symbol
from edgar.xbrl.core import is_period_end_label_role, is_period_start_label_role
from edgar.xbrl.models import is_negated_label_role

if TYPE_CHECKING:
    from edgar.xbrl.viewer import FilingViewer
    from edgar.xbrl.xbrl import XBRL

__all__ = ['compare_viewer_to_xbrl', 'ComparisonResult', 'ComparisonResults',
           'MATCHED', 'MISMATCHED', 'MISSING', 'NOT_COMPARABLE']

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

_DATE_RE = re.compile(
    r'(?:(\d+)\s+(?:Months?|Years?)\s+Ended\s+)?'
    r'([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})'
)


def _parse_viewer_period(header: str) -> Optional[dict]:
    """
    Parse a structured period header into components.

    Examples:
        "Mar. 29, 2025"                 -> {end: '2025-03-29', duration_hint: None, months: None}
        "3 Months Ended Mar. 29, 2025"  -> {end: '2025-03-29', duration_hint: 90, months: 3}
        "6 Months Ended Mar. 29, 2025"  -> {end: '2025-03-29', duration_hint: 180, months: 6}

    ``duration_hint`` is a rough day count (30 per month); ``months`` is the
    exact month count the header states, for calendar arithmetic.
    """
    match = _DATE_RE.match(header)
    if not match:
        return None
    duration_num, month_str, day_str, year_str = match.groups()
    month_key = month_str[:3].lower()
    month = _MONTH_MAP.get(month_key)
    if not month:
        return None
    try:
        end_date = datetime(int(year_str), month, int(day_str)).strftime('%Y-%m-%d')
    except ValueError:
        return None

    duration_hint = None
    months = None
    if duration_num:
        n = int(duration_num)
        if 'year' in header.lower():
            duration_hint = n * 365
            months = n * 12
        else:
            duration_hint = n * 30  # approximate
            months = n

    return {'end': end_date, 'duration_hint': duration_hint, 'months': months}


def _normalize_concept_id(viewer_id: str) -> str:
    """
    Normalize viewer concept ID for XBRL fact lookup.

    Viewer uses underscore: us-gaap_Assets
    XBRL facts use colon:   us-gaap:Assets
    """
    parts = viewer_id.split('_', 1)
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}"
    return viewer_id


def _match_xbrl_period(end_date: str, duration_hint: Optional[int],
                       xbrl_columns: List[str]) -> Optional[str]:
    """
    Find the XBRL DataFrame column matching a viewer period.

    XBRL DataFrame columns may be:
        - Just end dates: "2025-12-27" (most common — used for both instant and duration)
        - Full duration keys: "2024-09-28_2025-12-27" (less common)

    Since the XBRL parser typically uses just end dates as column names,
    we first try a direct end-date match, then fall back to duration keys.
    """
    # Direct end-date match (most common case)
    if end_date in xbrl_columns:
        return end_date

    # Try full duration columns (start_end format)
    candidates = []
    for col in xbrl_columns:
        if '_' in col and col.count('-') >= 4:
            parts = col.split('_')
            if len(parts) == 2:
                col_start, col_end = parts
                if col_end == end_date:
                    try:
                        start_dt = datetime.strptime(col_start, '%Y-%m-%d')
                        end_dt = datetime.strptime(col_end, '%Y-%m-%d')
                        days = (end_dt - start_dt).days
                        candidates.append((col, days))
                    except ValueError:
                        continue

    if candidates and duration_hint is not None:
        candidates.sort(key=lambda x: abs(x[1] - duration_hint))
        return candidates[0][0]
    elif candidates:
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    return None


#: Outcomes a viewer cell can have. ``not_comparable`` means the harness
#: cannot tell which XBRL fact the cell shows; it is never counted as a match.
MATCHED = 'matched'
MISMATCHED = 'mismatched'
MISSING = 'missing'
NOT_COMPARABLE = 'not_comparable'

# The "(N)" suffix concept_extractor adds to a values key when two columns
# share a header label.
_DUPLICATE_KEY_SUFFIX_RE = re.compile(r'\s\(\d+\)$')

Dims = FrozenSet[Tuple[str, str]]


def _qname(viewer_id: str) -> str:
    """``us-gaap_CommonClassAMember`` -> ``us-gaap:CommonClassAMember``."""
    return _normalize_concept_id(viewer_id)


def _typed_value(value) -> str:
    """A typed dimension's value with leading and trailing whitespace removed.

    The library stores a typed member's simple content stripped
    (``_typed_member_value``, parsers/instance.py), so a page header
    "Delayed Draw Term Loans And Revolvers " (Blackstone Private Credit
    Fund, 0001803498-26-000014, a trailing space) names the fact value
    "Delayed Draw Term Loans And Revolvers". Inner whitespace is kept: the
    same filing has distinct contexts "Investment Three  Verdelite JV LP"
    and "Investment Three Verdelite JV LP" (ten such pairs), which the page
    heads separately, so collapsing inner runs would merge two contexts.
    """
    return str(value).strip()


class _Names:
    """Axis and member names compared by namespace and local name.

    A QName's prefix is a display choice: a filer may bind the ``srt``
    namespace to ``pf0``, and the viewer's ``srt_ProductOrServiceAxis`` then
    names the instance's ``pf0:ProductOrServiceAxis``. Like the library's own
    parsers, which key concepts by expanded name (``InstanceParser._resolve_prefix``)
    and resolve QName values through the filing's declarations
    (``XBRL.parser.namespace_prefixes``, GH #1255), both sides are resolved
    to ``{namespace}local``: a context's dimension QNames through the
    filing's prefix declarations, a member header's ids through the
    namespace MetaLinks records for that element (``nsuri``). The local
    name alone never matches: one local name in two namespaces gives two
    names. A typed dimension's value is content, not a QName, and is kept.

    Without the filing's declarations (an XBRL object that does not carry
    them), names are compared as prefixed QNames, as written. So are names
    whose prefix cannot be resolved: ``namespace_prefixes`` merges the
    bindings of the instance and the filer's schema
    (``BaseParser._record_namespace_bindings``), and when they bind one
    prefix to two namespaces (a schema binding ``us-gaap`` to
    ``srt-sup``) the instance's own binding cannot be told. A context QName
    under such a prefix stays as written, and a viewer id whose namespace
    the filing binds to that prefix (or not at all) is compared as the
    viewer's own prefixed QName, which is how both sides compared before
    namespaces were resolved.
    """

    def __init__(self, xbrl, metalinks=None):
        parser = getattr(xbrl, 'parser', None)
        uri_prefixes = getattr(parser, 'namespace_prefixes', None)
        self.uri_prefixes: Dict[str, str] = dict(uri_prefixes) if isinstance(uri_prefixes, dict) else {}
        typed = getattr(parser, 'typed_dimensions', None)
        self.typed = set(typed) if isinstance(typed, (set, frozenset, list, tuple)) else set()
        # prefix -> namespace; a prefix the filing binds to two namespaces resolves to neither
        self.namespaces: Dict[str, Optional[str]] = {}
        for uri, prefix in self.uri_prefixes.items():
            self.namespaces[prefix] = uri if self.namespaces.get(prefix, uri) == uri else None
        self.metalinks = metalinks

    @property
    def resolving(self) -> bool:
        return bool(self.uri_prefixes)

    def _expand(self, qname: str) -> str:
        prefix, sep, local = qname.partition(':')
        uri = self.namespaces.get(prefix) if sep else None
        return f'{{{uri}}}{local}' if uri else qname

    def axis_name(self, axis: str) -> str:
        """A context's axis QName as ``context_dims`` names it."""
        return self._expand(axis) if self.resolving else axis

    def context_dims(self, dimensions) -> Dims:
        """A context's dimensions, as names that compare by namespace.

        A typed dimension's value is kept as content, with its edge
        whitespace stripped (``_typed_value``).
        """
        if not self.resolving:
            return frozenset((axis, _typed_value(member) if axis in self.typed else member)
                             for axis, member in (dimensions or {}).items())
        return frozenset((self._expand(axis), _typed_value(member) if axis in self.typed else self._expand(member))
                         for axis, member in (dimensions or {}).items())

    def viewer_name(self, viewer_id: str) -> str:
        """A viewer element id (``srt_ProductOrServiceAxis``), as a name that compares by namespace."""
        if not self.resolving:
            return _qname(viewer_id)
        tag = self.metalinks.get_tag(viewer_id) if self.metalinks is not None else None
        uri = getattr(tag, 'nsuri', None) if tag is not None else None
        local = getattr(tag, 'localname', None) if tag is not None else None
        if uri and local:
            prefix = self.uri_prefixes.get(uri)
            if prefix is None or self.namespaces.get(prefix) != uri:
                # The filing does not bind this namespace to one prefix of
                # its own: the instance side cannot resolve it either.
                return _qname(viewer_id)
            return f'{{{uri}}}{local}'
        # Not in MetaLinks: read the id's prefix as the filing declares it.
        return self._expand(_qname(viewer_id))

    def show(self, name: str) -> str:
        """A name for a message: ``prefix:local`` as the filing binds the namespace."""
        if name.startswith('{'):
            uri, _, local = name[1:].partition('}')
            prefix = self.uri_prefixes.get(uri)
            return f'{prefix}:{local}' if prefix else name
        return name

    def show_dims(self, dims: Dims) -> str:
        return str({self.show(axis): self.show(member) for axis, member in sorted(dims)})


def _member_header_dims(crow, names: Optional[_Names] = None,
                        typed_values: Optional[Dict[str, set]] = None) -> Tuple[Optional[Dims], Optional[str]]:
    """The dimensions a member-header row (``rh``) puts the rows below it in.

    The row's concept id names one ``Axis=Member`` pair. When the label shows
    more than one member (``'VIEs | Nonrecourse'``) the page names only the
    first by QName and the rest by label, so the context cannot be told and
    a reason is returned instead. A typed axis's value is read with
    ``_typed_header_value`` against ``typed_values`` (axis -> the filing's
    values on it).
    """
    names = names or _Names(None)
    axis_id, _, member_id = crow.concept_id.partition('=')
    if not axis_id or not member_id:
        return None, f"member header {crow.concept_id!r} does not name an axis and member"
    if ' | ' in (crow.label or ''):
        return None, (f"member header {crow.label!r} spans several members; the page names "
                      f"only {axis_id}={member_id} by QName")
    if _qname(axis_id) in names.typed:
        axis = names.viewer_name(axis_id)
        value, reason = _typed_header_value(member_id, crow.label or '', (typed_values or {}).get(axis, ()))
        if reason is not None:
            return None, reason
        return frozenset({(axis, value)}), None
    return frozenset({(names.viewer_name(axis_id), names.viewer_name(member_id))}), None


def _renderer_typed_id(value: str) -> str:
    """The form of a typed value in the renderer's header id: every ':' written as '_'.

    The header link is ``defref_{translate(concat(dim, '=', mem), ':', '_')}``
    (EdgarRenderer Common.xslt, the segment-title row), with ``mem`` the
    typed value as Arelle reads it; XPath ``translate`` replaces every
    colon. The id keeps the value's whitespace.
    """
    return value.replace(':', '_')


def _renderer_typed_label(value: str) -> str:
    """The form of a typed value in the header's label: XPath ``normalize-space``.

    The label is ``"{axis label}: {typed value}"`` (Embedding.py), printed
    with ``normalize-space(Label)`` (Common.xslt): edge whitespace removed,
    inner runs collapsed to one space. Colons are kept.
    """
    return ' '.join(value.split())


def _typed_header_value(member_id: str, label: str, values) -> Tuple[Optional[str], Optional[str]]:
    """The filing's typed value a member header names, or a reason.

    The id tells the value with every ':' written as '_', and the label
    tells it with whitespace normalized; neither alone is the value. A fact
    value is the header's when both of the renderer's forms of it agree with
    the page: its id form equals the header id's value (the library stores
    the value stripped, so the id's edge whitespace is not compared) and
    the label ends with ``': '`` plus its label form. Exactly one value must
    fit. A value whose id form fits while the label shows something else
    is not taken: the cell is not comparable. With no value fitting either
    form, the id's value (stripped) is used, which names no fact, so the
    rows are reported missing.
    """
    wanted = member_id.strip()
    by_id = [v for v in values if _renderer_typed_id(v) == wanted]
    fitting = [v for v in by_id
               if label == _renderer_typed_label(v) or label.endswith(': ' + _renderer_typed_label(v))]
    if len(fitting) == 1:
        return fitting[0], None
    if len(fitting) > 1:
        return None, (f"member header {label!r} fits several typed values of the axis "
                      f"({', '.join(repr(v) for v in sorted(fitting))}): the page writes ':' as '_' in the "
                      "id and normalizes whitespace in the label, so it does not tell them apart")
    if by_id:
        return None, (f"member header {label!r} names typed value {wanted!r} in its id, and the filing's "
                      f"value of that id form ({', '.join(repr(v) for v in sorted(by_id))}) is not what its "
                      "label shows")
    return _typed_value(member_id), None


def _float_or_none(value) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _text_or_none(value) -> Optional[str]:
    if value is None or (isinstance(value, float) and value != value):
        return None
    text = str(value)
    return text or None


def _rendered_months(start_date: str, end_date: str) -> Optional[int]:
    """The N the SEC renderer prints as "N Months Ended" for a duration.

    The renderer (Arelle EdgarRenderer, ``Filing.StartEndContext.startEndContextInMonths``)
    takes the context's end datetime -- the day after the XBRL ``endDate``,
    since a date-only end means the end of that day -- adds 15 days
    ("because it rounds down") and counts whole months from the start with
    ``relativedelta``: ``years * 12 + months``. So 2021-01-13 to 2021-12-31
    renders as 12 months, 2019-12-01 to 2020-08-31 as 9.
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return None
    delta = relativedelta(end + timedelta(days=1 + 15), start)
    return delta.years * 12 + delta.months


class _FactIndex:
    """XBRL facts keyed exactly by (concept, period key, dimensions).

    Every candidate is kept, so the unit and the duplicate rules can be
    applied per viewer cell instead of letting the last fact read win.
    """

    def __init__(self, xbrl: 'XBRL', names: Optional[_Names] = None):
        self.names = names or _Names(xbrl)
        self.facts: Dict[Tuple[str, str, Dims], List[SimpleNamespace]] = defaultdict(list)
        # (concept, period key) -> every context (dims) a fact for it is in
        self.period_contexts: Dict[Tuple[str, str], set] = defaultdict(set)
        self.period_types: Dict[str, str] = {}
        # end date -> {duration period key: start date}, every duration in the filing
        self.durations_by_end: Dict[str, Dict[str, str]] = defaultdict(dict)
        # (concept, dims, end date) -> {duration period key: start date}
        self.concept_durations: Dict[Tuple[str, Dims, str], Dict[str, str]] = defaultdict(dict)
        # (concept, period key) of every fact, nil and non-numeric ones too:
        # the renderer finds a statement's periods from all its facts
        self.fact_periods: set = set()
        # typed axis -> every value the filing's contexts give it
        self.typed_values: Dict[str, set] = defaultdict(set)

        self._contexts = getattr(xbrl, 'contexts', None) or {}
        self._typed_axes = {self.names.axis_name(axis) for axis in self.names.typed}
        facts_df = xbrl.facts.to_dataframe()
        if facts_df is None or facts_df.empty:
            return
        for row in facts_df.to_dict('records'):
            self._add_row(row)

    def _row_dims(self, row: dict) -> Optional[Dims]:
        """The row's context dimensions, or None when it is dimensioned but its members cannot be read."""
        context = self._contexts.get(row.get('context_ref'))
        if context is not None:
            return self.names.context_dims(context.dimensions)
        if row.get('is_dimensioned', False):
            return None
        return frozenset()

    def _record_duration(self, concept: str, period_key: str, dims: Dims) -> None:
        if not period_key.startswith('duration_'):
            return
        parts = period_key[len('duration_'):].split('_')
        if len(parts) == 2:
            self.durations_by_end[parts[1]][period_key] = parts[0]
            self.concept_durations[(concept, dims, parts[1])][period_key] = parts[0]

    def _add_row(self, row: dict) -> None:
        """Index one row of the facts DataFrame."""
        concept = row.get('concept')
        period_key = row.get('period_key')
        if not concept or not isinstance(period_key, str) or not period_key:
            return
        self.fact_periods.add((concept, period_key))
        value = _float_or_none(row.get('numeric_value'))
        if value is None:
            value = _float_or_none(row.get('value'))
        if value is None:
            return
        dims = self._row_dims(row)
        if dims is None:
            return
        self._record_duration(concept, period_key, dims)
        period_type = row.get('period_type')
        if isinstance(period_type, str) and period_type:
            self.period_types.setdefault(concept, period_type)
        self.period_contexts[(concept, period_key)].add(dims)
        for axis, member in dims:
            if axis in self._typed_axes:
                self.typed_values[axis].add(member)
        self.facts[(concept, period_key, dims)].append(SimpleNamespace(
            numeric_value=value,
            value=row.get('value'),
            decimals=row.get('decimals'),
            unit_ref=_text_or_none(row.get('unit_ref')),
            currency=_text_or_none(row.get('currency')),
        ))

    def wider_context_reason(self, concept: str, dims: Dims, period_keys: List[str]) -> Optional[str]:
        """Why the page does not identify the context, when facts carry more dimensions than the row.

        When no fact has exactly the row's dimensions but facts for the
        concept and one of ``period_keys`` have those dimensions plus
        others, the page has not said which of those contexts it shows (a
        statement for one legal entity whose member headers name only a
        partner type, say). Such a fact is never taken as the cell. None
        when there is no such fact, so the cell is missing.

        Only a row under a member header (``dims`` not empty) can be
        unidentified this way. A plain row claims the undimensioned fact,
        and an undimensioned total usually has dimensioned siblings, so a
        plain row with only dimensioned facts stays missing.
        """
        if not dims:
            return None
        extra = sorted({self.names.show(axis)
                        for key in period_keys
                        for other in self.period_contexts.get((concept, key), ())
                        if other > dims
                        for axis, _member in other - dims})
        if not extra:
            return None
        return (f"no fact for {period_keys[0]} has exactly the row's context; the page names only "
                f"{self.names.show_dims(dims)}, "
                f"while the facts for this period also carry {', '.join(extra)}, so the page does "
                "not say which context it shows")

    def rendered_period_keys(self, end_date: str, months: int) -> List[str]:
        """Duration period keys in the filing that render as "``months`` Months Ended ``end_date``"."""
        return sorted(key for key, start in self.durations_by_end.get(end_date, {}).items()
                      if _rendered_months(start, end_date) == months)

    def column_starts(self, end_date: str, months: int) -> List[str]:
        """Start dates of every duration in the filing that would render as "``months`` Months Ended ``end_date``"."""
        return sorted({start for start in self.durations_by_end.get(end_date, {}).values()
                       if _rendered_months(start, end_date) == months})

    def concept_period(self, concept: str, dims: Dims, end_date: str,
                       months: int) -> Tuple[Optional[str], Optional[str]]:
        """The duration period key of this concept's fact for an "N Months Ended" column.

        Decided per concept and context, so one stray fact cannot decide for
        the whole column. A period qualifies exactly when the renderer would
        head it "``months`` Months Ended ``end_date``" (``_rendered_months``);
        a period that renders with another month count never does. When
        several of the concept's periods qualify and their facts agree, any
        of them is the cell; when they disagree, the page cannot say which
        one it shows.

        Returns ``(period key, None)`` or ``(None, reason)``; a reason that
        starts with "no " means there is no such fact.
        """
        options = sorted(period_key for period_key, start
                         in self.concept_durations.get((concept, dims, end_date), {}).items()
                         if _rendered_months(start, end_date) == months)
        if not options:
            return None, (f"no fact for a period that renders as {months} months ending {end_date}"
                          + (f" with {self.names.show_dims(dims)}" if dims else " without dimensions"))
        if len(options) > 1 and len({self.value_signature(concept, key, dims) for key in options}) > 1:
            return None, (f"facts for several periods that render as {months} months ending "
                          f"{end_date} disagree: " + ", ".join(options))
        return options[0], None

    def value_signature(self, concept: str, period_key: str, dims: Dims) -> FrozenSet:
        """``{(unit, value)}`` of a concept's facts for one period and context, for comparing periods."""
        return frozenset((f.currency or f.unit_ref, f.numeric_value)
                         for f in self.facts.get((concept, period_key, dims), []))


def _opening_instant_keys(start_date: str) -> List[str]:
    """Instant period keys an opening balance for a duration starting ``start_date`` may use.

    XBRL dates a duration's start at the beginning of its first day and an
    instant at the end of its day, so the opening balance is the instant on
    the day before ``startDate``. Some filers date it on ``startDate``
    itself; that key is tried only when the first has no fact.
    """
    try:
        day_before = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError:
        return [f'instant_{start_date}']
    return [f'instant_{day_before}', f'instant_{start_date}']


def _tree_children(tree) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    """``{parent: [(child, preferred label role)]}`` of a presentation tree, in arc order.

    Read from the role's network as filed (``PresentationTree.relationships``)
    when the tree carries it: the renderer walks every arc, and the
    library's tree nodes list a child once per parent unless the arc is a
    roll-forward one (presentation.py ``_build_presentation_subtree``), so a
    concept presented twice under one parent with different label roles
    would otherwise show one arc. Falls back to the nodes' children.
    """
    relationships = list(getattr(tree, 'relationships', None) or [])
    out: Dict[str, List[Tuple[str, Optional[str]]]] = defaultdict(list)
    if relationships:
        ordered = sorted(enumerate(relationships), key=lambda item: (item[1].order, item[0]))
        for _index, rel in ordered:
            out[rel.parent_id].append((rel.child_id, rel.preferred_label))
        return out
    for element_id, node in (getattr(tree, 'all_nodes', None) or {}).items():
        children = list(getattr(node, 'children', None) or [])
        labels = list(getattr(node, 'child_preferred_labels', None) or [])
        labels += [None] * (len(children) - len(labels))
        if children:
            out[element_id] = list(zip(children, labels, strict=True))
    return out


def _presentation_references(xbrl: 'XBRL', role: str) -> Dict[str, List[str]]:
    """``{concept id: [preferred label role of each reference]}`` in presentation order.

    Read from the role's presentation tree, walked depth first from its
    roots, which is the order the renderer lays the rows out in. The role
    is the arc's full preferred-label role URI, or ``''`` when the arc has
    none. Every arc counts, a second arc to a concept under the same parent
    included (``_tree_children``). Empty when the tree is unavailable.
    """
    trees = getattr(xbrl, 'presentation_trees', None) or {}
    tree = trees.get(role) if role else None
    nodes = getattr(tree, 'all_nodes', None) if tree is not None else None
    if not nodes:
        return {}
    roots = list(getattr(tree, 'root_element_ids', None) or [])
    if not roots and getattr(tree, 'root_element_id', None):
        roots = [tree.root_element_id]
    children_of = _tree_children(tree)
    refs: Dict[str, List[str]] = defaultdict(list)
    # Pre-order: a reference is recorded when it is reached, before its own
    # children, as the renderer lists a parent row before the rows under it.
    stack = [(root, (), None) for root in reversed(roots)]
    while stack:
        element_id, path, preferred = stack.pop()
        if path:
            refs[element_id].append(preferred or '')
        path = path + (element_id,)
        stack.extend((child, path, label)
                     for child, label in reversed(children_of.get(element_id, []))
                     if child not in path)
    return refs


def _normalize_label(text: str) -> str:
    """A row label or label text, entities decoded, whitespace collapsed, case folded."""
    return ' '.join(html.unescape(text).split()).casefold()


def _renderer_negates(role: Optional[str]) -> bool:
    """EdgarRenderer's own test: ``'negated' in preferredLabel`` (Utils.strFactValue), case-sensitive, anywhere."""
    return bool(role) and 'negated' in role


def _role_name(role: Optional[str]) -> str:
    return role.rsplit('/', 1)[-1] if role else 'label (no preferred label)'


def _roles_sign(roles: List[Optional[str]]) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Whether the renderer negates a row that may be any of ``roles``' arcs.

    Returns ``(negated, role, None)`` when every possible arc gives the same
    answer (``role`` is the arc when only one is possible), else
    ``(None, None, reason)``. Negation is the library's rule
    (``is_negated_label_role``). Where the renderer's own test
    (``_renderer_negates``) gives another answer for a role, the sign is
    not verified.
    """
    if not roles:
        return None, None, "the row's presentation arc is not known, so its label role (and sign) is not"
    for role in roles:
        if is_negated_label_role(role) != _renderer_negates(role):
            return None, None, (f"label role {role!r}: the library's negated-role rule and the renderer's "
                                "disagree on it")
    signs = {is_negated_label_role(role) for role in roles}
    if len(signs) > 1:
        listed = ', '.join(sorted({_role_name(r) for r in roles}))
        return None, None, (f"the row may be any of the concept's arcs ({listed}); some negate and some do "
                            "not, and the page does not tell which this row is")
    distinct = set(roles)
    return signs.pop(), (roles[0] or '') if len(distinct) == 1 else None, None


def _role_text(xbrl, tag, element_id: str, role: Optional[str]) -> str:
    """The label text the renderer prints for an arc's role (standard label when the role has none)."""
    catalog = getattr(xbrl, 'element_catalog', None) or {}
    entry = catalog.get(element_id)
    labels = dict(getattr(entry, 'labels', None) or {}) if entry is not None else {}
    if role and labels.get(role):
        return labels[role]
    role_labels = tag.role_labels if tag is not None else {}
    if role and role_labels.get(_role_name(role)):
        return role_labels[_role_name(role)]
    return labels.get(_STANDARD_LABEL_ROLE) or role_labels.get('label') or ''


_UNIT_SUFFIX_RE = re.compile(r'\s*\((?:in|per) [^()]*\)\s*$', re.IGNORECASE)


def _row_sign(xbrl, tag, crow, references: Dict[str, List[str]], occurrence: int,
              occurrences: int) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Whether the renderer printed this row's facts negated: ``(negated, role, reason)``.

    EdgarRenderer negates a numeric fact's value when the row's preferred
    label role is a negated one (Utils.strFactValue: nil prints blank, zero
    is never negated) and prints a negative in parentheses (Common.xslt
    ``numFilters``). The row's arc is identified as for balances: when all
    the concept's arcs on the statement agree, any of them; else the arcs
    whose label text is the row's label; else, when the arcs line up one to
    one with the concept's rows in this member context, the row's own
    arc. When the page shows more rows of the concept than it has arcs, or
    no rule identifies the arc, the sign is not verified (``negated`` None).
    """
    if not references:
        return None, None, "the statement's presentation tree is not available, so the row's label role is not known"
    refs = references.get(crow.concept_id)
    if not refs:
        return None, None, "the concept has no arc in the statement's presentation tree"
    if occurrences > len(refs):
        return None, None, (f"the page shows {occurrences} rows of the concept here and the presentation has "
                            f"{len(refs)} arc(s) for it, so which arc each row is cannot be told")
    if len({is_negated_label_role(r) for r in refs}) == 1:
        negated, _role, reason = _roles_sign(refs)
        if reason is None:
            role = refs[occurrence] if len(refs) == occurrences and occurrence < len(refs) else _role
            return negated, role, None
        return negated, _role, reason
    label = _normalize_label(_UNIT_SUFFIX_RE.sub('', crow.label or ''))
    texts = {r: _normalize_label(_role_text(xbrl, tag, crow.concept_id, r)) for r in set(refs)}
    by_label = [r for r in refs if texts[r] == label] or [
        r for r in refs if texts[r] == _normalize_label(crow.label or '')]
    if by_label and len({is_negated_label_role(r) for r in by_label}) == 1:
        return _roles_sign(by_label)
    if len(refs) == occurrences and occurrence < len(refs):
        positional = refs[occurrence]
        if by_label and positional not in by_label:
            return None, None, ("the presentation arcs do not line up with the page's rows: the row's label "
                                f"is not the label of its arc in presentation order ({_role_name(positional)})")
        return _roles_sign([positional])
    return _roles_sign(by_label or refs)


def _balance_role(crow, tag, occurrence: int, occurrences: int,
                  references: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """Whether an instant concept in a duration column is the opening or closing balance.

    Returns ``('opening' | 'closing', None)`` or ``(None, reason)``.

    The renderer shows an instant at the start of a duration column only
    when the presentation arc uses the period-start label, and at the end
    otherwise. "Period-start label" means any role the library treats as
    one (``is_period_start_label_role``: ``periodStartLabel`` and its
    negated forms, GH #1700), and likewise for period-end. So, in order:

    1. When the presentation references of the concept line up one-to-one
       with its rows in this member context, each row's own arc decides:
       period-start label is the opening balance, anything else the closing
       one. If the row's label contradicts its arc (the arcs are in another
       order than the rows), the cell is undecidable. A concept shown more
       than twice is the exception: for a
       reference that is neither the period-start nor the period-end label
       (a "total" row in a reconciliation) the renderer was seen to show
       the opening balance in some columns and the closing in others
       (Brixmor 0001581068-21-000012 R8, Zscaler 0001713683-20-000163 R8),
       so it is undecidable.
    2. Otherwise the row label stands in for the arc: a concept whose
       period-start label has text of its own is opening for that text and
       closing for any other; the period-end label's text is closing. A
       concept shown once with no period-start label at all can only be the
       closing balance.
    3. A concept shown exactly twice is then the opening/closing pair in
       that order. Anything else is undecidable.
    """
    label, start_labels, end_labels, label_says = _balance_row_label(crow, tag)
    if references and len(references) == occurrences:
        return _balance_from_arc(references[occurrence], occurrences, label_says)
    return _balance_from_label(tag, label, start_labels, end_labels, label_says, occurrence, occurrences)


def _balance_row_label(crow, tag) -> Tuple[str, set, set, Optional[str]]:
    """The row's label, the concept's period-start and period-end label texts, and what the label says.

    What the label says (``'opening'`` or ``'closing'``, else None) is known
    only when the concept's period-start text is its own (no other role
    uses it). Part of ``_balance_role``.
    """
    labels = tag.role_labels if tag is not None else {}
    label = (crow.label or '').strip()
    start_labels, end_labels, other_labels = _period_label_texts(labels)
    # What the row's own label says, when its period-start text is unique.
    label_says = None
    if label and start_labels and start_labels.isdisjoint(other_labels):
        label_says = 'opening' if label in start_labels else 'closing'
    return label, start_labels, end_labels, label_says


def _period_label_texts(labels: Dict[str, str]) -> Tuple[set, set, set]:
    """A concept's label texts by role: period-start, period-end (both without blanks), and every other."""
    start_labels = {(t or '').strip() for r, t in labels.items() if is_period_start_label_role(r)} - {''}
    end_labels = {(t or '').strip() for r, t in labels.items() if is_period_end_label_role(r)} - {''}
    other_labels = {(t or '').strip() for r, t in labels.items() if not is_period_start_label_role(r)}
    return start_labels, end_labels, other_labels


def _balance_from_arc(preferred: Optional[str], occurrences: int,
                      label_says: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Step 1 of ``_balance_role``: the row's own arc decides, unless the label contradicts it."""
    is_start = is_period_start_label_role(preferred)
    if occurrences > 2 and not (is_start or is_period_end_label_role(preferred)):
        short = preferred.rsplit('/', 1)[-1] if preferred else 'unlabelled'
        return None, (f"instant concept shown {occurrences} times; for its "
                      f"{short} reference the renderer's choice of "
                      "opening or closing balance is not determinable")
    arc_says = 'opening' if is_start else 'closing'
    if label_says is not None and label_says != arc_says:
        return None, ("the presentation arcs do not line up with the page's rows: the row label "
                      f"says {label_says}, its arc in presentation order says {arc_says}")
    return arc_says, None


def _balance_from_label(tag, label: str, start_labels: set, end_labels: set, label_says: Optional[str],
                        occurrence: int, occurrences: int) -> Tuple[Optional[str], Optional[str]]:
    """Steps 2 and 3 of ``_balance_role``: the row label stands in for the arc, then row order."""
    if occurrences > 2 and label not in start_labels | end_labels:
        return None, (f"instant concept shown {occurrences} times; a row with neither its "
                      "period-start nor its period-end label is undecidable")
    if tag is not None and not start_labels and occurrences == 1:
        return 'closing', None
    if label_says is not None:
        return label_says, None
    return _balance_from_end_label_or_order(label, start_labels, end_labels, occurrence, occurrences)


def _balance_from_end_label_or_order(label: str, start_labels: set, end_labels: set, occurrence: int,
                                     occurrences: int) -> Tuple[Optional[str], Optional[str]]:
    """The end of ``_balance_role``: the period-end label's text is closing; else a pair is opening then closing."""
    if label and label in end_labels and label not in start_labels:
        return 'closing', None
    if occurrences == 2:
        return ('opening' if occurrence == 0 else 'closing'), None
    return None, ("instant concept in a duration column; the page does not say "
                  "whether it is the opening or the closing balance")


def _is_rounding_of(other, precise) -> bool:
    """Whether ``other`` is ``precise`` rounded to ``other``'s own decimals.

    ``other`` must be a whole number of its last stated unit (``10**-decimals``)
    and within half of that unit of ``precise``; a tie may round either way.
    INF or unreadable decimals must agree exactly.
    """
    value, target = other.numeric_value, precise.numeric_value
    if value == target:
        return True  # an identical copy agrees whatever decimals it states
    try:
        decimals = int(other.decimals)
    except (TypeError, ValueError):
        return value == target
    unit = 10.0 ** -decimals
    noise = 8 * math.ulp(max(abs(value), abs(target), 1.0))
    steps = value / unit
    if abs(steps - round(steps)) * unit > noise:
        return False  # not a value stated to that many decimals
    return abs(value - target) <= 0.5 * unit + noise


def _inconsistency(chosen, candidates) -> Optional[str]:
    """A note when a duplicate is not the chosen (most precise) fact rounded to its own decimals."""
    for other in candidates:
        if other is chosen:
            continue
        if not _is_rounding_of(other, chosen):
            return ("duplicate facts disagree beyond their stated precision: "
                    + ", ".join(f"{c.numeric_value:.15g} (decimals={c.decimals})" for c in candidates)
                    + f"; compared with {chosen.numeric_value:.15g}, the one statements use")
    return None


def _displayed_decimals(display: str) -> int:
    """Digits after the decimal point in a displayed value (``'$ (1,959.30)'`` -> 2)."""
    digits = re.search(r'\d[\d,]*(?:\.(\d+))?', display or '')
    return len(digits.group(1)) if digits and digits.group(1) else 0


def _display_tolerance(display: str, viewer_num: float, xbrl_display: float = 0.0) -> float:
    """Half a unit in the last digit the page displays, plus float rounding noise.

    The noise term is a few units in the last place of the larger value
    (about 2e-4 at 1.2e12), not a relative allowance.
    """
    noise = 8 * math.ulp(max(abs(viewer_num), abs(xbrl_display), 1.0))
    return 0.5 * 10 ** -_displayed_decimals(display) + noise


# Item types whose values are not numbers (the cell cannot be compared numerically).
# Non-numeric item types by local name: XBRL 2.1's non-numeric items, the
# nonnum and dtr-types non-numeric types, and dei's token-derived types.
_NON_NUMERIC_ITEM_TYPES = frozenset(t.casefold() for t in (
    'stringItemType', 'normalizedStringItemType', 'tokenItemType', 'languageItemType', 'NameItemType',
    'NCNameItemType', 'QNameItemType', 'anyURIItemType', 'booleanItemType', 'base64BinaryItemType',
    'hexBinaryItemType', 'dateTimeItemType', 'dateItemType', 'timeItemType', 'durationItemType',
    'gYearItemType', 'gYearMonthItemType', 'gMonthDayItemType', 'gDayItemType', 'gMonthItemType',
    'IDItemType', 'IDREFItemType', 'IDREFSItemType', 'ENTITYItemType', 'ENTITIESItemType', 'NMTOKENItemType',
    'NMTOKENSItemType', 'NOTATIONItemType',
    'textBlockItemType', 'escapedItemType', 'xmlNodesItemType', 'xmlItemType', 'simpleItemType',
    'domainItemType', 'enumerationItemType', 'enumerationSetItemType', 'extensibleEnumerationItemType',
    'extensibleEnumerationSetItemType', 'extensibleListItemType', 'internationalNameItemType',
    'yesNoItemType', 'fiscalPeriodItemType', 'submissionTypeItemType', 'edgarStateCountryItemType',
    'edgarStateProvinceItemType', 'edgarExchangeCodeItemType', 'entityFilerCategoryItemType',
    'filerCategoryItemType', 'fileNumberItemType', 'centralIndexKeyItemType', 'gMonthDayItemType',
    'sicNumberItemType', 'tradingSymbolItemType', 'securityTitleItemType', 'employerIdItemType',
    'countryCodeItemType', 'currencyItemType', 'nineDigitItemType', 'fiveDigitItemType',
    'threeDigitItemType', 'stateOrProvinceItemType', 'invCompanyTypeItemType',
))


def _is_numeric_type(xbrltype: str) -> bool:
    """Whether an item type is numeric, by its local name (``nonnum:textBlockItemType`` -> no).

    The local name is matched whole: ``candidateCountItemType`` and
    ``tokenAmountItemType`` are a filer's numeric types, not dates or tokens.
    """
    local = (xbrltype or '').strip().rsplit(':', 1)[-1]
    return bool(local) and local.casefold() not in _NON_NUMERIC_ITEM_TYPES


@dataclass
class ComparisonResult:
    """Result of comparing one concept+period between viewer and XBRL."""
    concept_id: str
    label: str
    period: str
    #: The cell's value as displayed; None when it cannot be read as a number.
    viewer_value: Optional[float]
    xbrl_value: Optional[float]
    difference: Optional[float]
    match: bool
    report: str
    #: 'matched', 'mismatched', 'missing' or 'not_comparable'. Derived from
    #: ``match`` and ``xbrl_value`` when not given.
    status: str = ''
    #: Why a cell is missing or not comparable, when the harness knows.
    reason: Optional[str] = None
    #: Something the reader should know about a compared cell, such as
    #: duplicate facts that disagree beyond their stated precision.
    note: Optional[str] = None
    #: A match whose sign is not verified: the magnitude agrees, but the
    #: row's presentation arc, and so whether the renderer negated the
    #: value, cannot be identified (``reason`` says why). A cell whose
    #: label role is known must agree in sign as well, or it is mismatched.
    sign_only: bool = False
    #: The fact the cell was compared with (matched or mismatched cells):
    #: its period key (``instant_2024-12-31``, ``duration_2024-01-01_2024-12-31``),
    #: its dimensions as ``{axis: member}`` QNames, and its unit id.
    xbrl_period_key: Optional[str] = None
    xbrl_dimensions: Optional[Dict[str, str]] = None
    xbrl_unit: Optional[str] = None
    #: The row's preferred label role, when its arc is identified (``''``
    #: for an arc without one), and whether the renderer negates it (None
    #: when not known).
    label_role: Optional[str] = None
    negated: Optional[bool] = None

    def __post_init__(self):
        if not self.status:
            if self.match:
                self.status = MATCHED
            elif self.xbrl_value is None:
                self.status = MISSING
            else:
                self.status = MISMATCHED


@dataclass
class ComparisonResults:
    """Aggregate comparison results between viewer and XBRL."""
    results: List[ComparisonResult] = field(default_factory=list)
    #: The currency scale every compared statement declares (1 when there
    #: were none), or None when statements differ; see ``scaling_factors``.
    scaling_factor: Optional[int] = 1
    #: Currency scale per statement (``ViewerReport.short_name``).
    scaling_factors: Dict[str, int] = field(default_factory=dict)
    #: Statements whose page could not be read, so none of their cells are
    #: counted (``ViewerReport.short_name``).
    unread_statements: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def matched(self) -> int:
        return sum(1 for r in self.results if r.status == MATCHED)

    @property
    def mismatched(self) -> int:
        return sum(1 for r in self.results if r.status == MISMATCHED)

    @property
    def missing(self) -> int:
        """Viewer cells with no XBRL fact for their concept, period, context and unit."""
        return sum(1 for r in self.results if r.status == MISSING)

    @property
    def not_comparable(self) -> int:
        """Viewer cells whose XBRL fact the harness cannot identify (see ``reason``)."""
        return sum(1 for r in self.results if r.status == NOT_COMPARABLE)

    @property
    def exact_matches(self) -> int:
        """Matched cells whose value agrees including the sign the row's label role gives it."""
        return sum(1 for r in self.results if r.status == MATCHED and not r.sign_only)

    @property
    def sign_only_matches(self) -> int:
        """Matched cells whose sign is not verified (see ``ComparisonResult.sign_only``)."""
        return sum(1 for r in self.results if r.status == MATCHED and r.sign_only)

    @property
    def sign_unverified(self) -> List[ComparisonResult]:
        """Matched cells whose magnitude agrees and whose sign could not be verified."""
        return [r for r in self.results if r.status == MATCHED and r.sign_only]

    @property
    def noted(self) -> int:
        """Compared cells that carry a ``note``, such as duplicate facts that disagree."""
        return sum(1 for r in self.results if r.note)

    @property
    def match_rate(self) -> float:
        """Matched cells over the cells compared (matched + mismatched)."""
        compared = self.matched + self.mismatched
        if compared == 0:
            return 0.0
        return self.matched / compared

    @property
    def coverage(self) -> float:
        """Compared cells (matched + mismatched) over every numeric cell of the statement pages.

        Pages that could not be read are listed in ``unread_statements``
        and are not in the denominator.
        """
        if not self.results:
            return 0.0
        return (self.matched + self.mismatched) / self.total

    @property
    def mismatches(self) -> List[ComparisonResult]:
        return [r for r in self.results if r.status == MISMATCHED]

    @property
    def not_comparables(self) -> List[ComparisonResult]:
        return [r for r in self.results if r.status == NOT_COMPARABLE]

    def to_dataframe(self):
        """Export results as a pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame([
            {
                'concept_id': r.concept_id,
                'label': r.label,
                'period': r.period,
                'viewer_value': r.viewer_value,
                'xbrl_value': r.xbrl_value,
                'difference': r.difference,
                'match': r.match,
                'report': r.report,
                'status': r.status,
                'reason': r.reason,
                'note': r.note,
                'sign_only': r.sign_only,
                'xbrl_period_key': r.xbrl_period_key,
                'xbrl_dimensions': r.xbrl_dimensions,
                'xbrl_unit': r.xbrl_unit,
                'label_role': r.label_role,
                'negated': r.negated,
            }
            for r in self.results
        ])

    def __rich__(self):
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        summary = Text()
        summary.append(f"Compared: {self.total}  ", style="dim")
        summary.append(f"Matched: {self.matched}  ", style="green")
        if self.sign_only_matches:
            summary.append(f"(exact {self.exact_matches}, sign unverified {self.sign_only_matches})  ",
                           style="yellow")
        if self.mismatched:
            summary.append(f"Mismatched: {self.mismatched}  ", style="red")
        if self.missing:
            summary.append(f"Missing: {self.missing}  ", style="yellow")
        if self.not_comparable:
            summary.append(f"Not comparable: {self.not_comparable}  ", style="dim")
        summary.append(f"Match rate: {self.match_rate:.1%}  ", style="bold")
        summary.append(f"Coverage: {self.coverage:.1%}", style="dim")
        if self.noted:
            summary.append(f"  Noted: {self.noted} (duplicate facts disagree)", style="yellow")
        if self.unread_statements:
            summary.append(f"  Unread statements: {len(self.unread_statements)}", style="red")

        parts = [summary]

        if self.mismatches:
            table = Table(show_header=True, header_style="dim", padding=(0, 1))
            table.add_column("Concept", width=35)
            table.add_column("Period", width=28)
            table.add_column("Viewer", justify="right", width=12)
            table.add_column("XBRL", justify="right", width=12)
            table.add_column("Diff", justify="right", width=10)
            for r in self.mismatches[:15]:
                table.add_row(
                    r.label[:35],
                    r.period[:28],
                    f"{r.viewer_value:,.0f}",
                    f"{r.xbrl_value:,.0f}" if r.xbrl_value is not None else "—",
                    f"{r.difference:,.0f}" if r.difference is not None else "—",
                )
            parts.append(table)

        return Panel(Group(*parts), title="[bold]Viewer vs XBRL[/bold]", expand=False, width=105)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __str__(self):
        return (f"ComparisonResults(total={self.total}, matched={self.matched} "
                f"(exact={self.exact_matches}, sign_unverified={self.sign_only_matches}), "
                f"mismatched={self.mismatched}, missing={self.missing}, not_comparable={self.not_comparable}, "
                f"noted={self.noted}, rate={self.match_rate:.1%}, coverage={self.coverage:.1%}"
                + (f", unread_statements={len(self.unread_statements)}" if self.unread_statements else "")
                + ")")


def _emit(results: ComparisonResults, cell: dict, status: str, xbrl_display: Optional[float] = None,
          diff: Optional[float] = None, reason: Optional[str] = None, note: Optional[str] = None,
          sign_only: bool = False, paired: Optional[dict] = None) -> None:
    results.results.append(ComparisonResult(
        xbrl_value=xbrl_display, difference=diff, match=status == MATCHED,
        status=status, reason=reason, note=note, sign_only=sign_only, **cell, **(paired or {})))


# ISO 4217 symbols from the XBRL Units Type Registry (https://www.xbrl.org/utr/utr.xml,
# status REC), the symbol the renderer prints for a currency unit (Arelle
# ``ModelFact.unitSymbol``; EdgarRenderer ``Utils.getSymbolStr`` falls back to
# the unit's id when the registry has none).
_UTR_CURRENCY_SYMBOLS = {
    'AED': 'د.إ', 'AFN': '؋', 'ALL': 'L', 'AMD': '֏', 'ANG': 'NAƒ', 'AOA': 'Kz', 'ARS': '$', 'AUD': '$',
    'AWG': 'ƒ', 'AZN': '₼', 'BAM': 'KM', 'BBD': '$', 'BDT': '৳', 'BGN': 'лв', 'BHD': '.د.ب', 'BIF': 'FBu',
    'BMD': '$', 'BND': '$', 'BOB': 'Bs.', 'BRL': 'R$', 'BSD': '$', 'BTN': 'Ch.', 'BWP': 'P', 'BYN': 'Br',
    'BYR': 'Br', 'BZD': '$', 'CAD': '$', 'CDF': 'CF', 'CHF': 'SFr', 'CLP': '$', 'CNY': '¥', 'COP': '$',
    'CRC': '₡', 'CUC': 'CUC$', 'CUP': '$MN', 'CVE': 'Esc', 'CZK': 'Kč', 'DJF': 'Fdj', 'DKK': 'kr', 'DOP': '$',
    'DZD': 'دج', 'EGP': 'ج.م.', 'ERN': 'Nfk', 'ETB': 'Br', 'EUR': '€', 'FJD': '$', 'FKP': '£', 'GBP': '£',
    'GEL': 'ლ', 'GHS': 'GH₵', 'GIP': '£', 'GMD': 'D', 'GNF': 'FG', 'GTQ': 'Q', 'GYD': '$', 'HKD': '$',
    'HNL': 'L', 'HRK': 'kn', 'HTG': 'G', 'HUF': 'Ft', 'IDR': 'Rp', 'ILS': '₪', 'INR': '₨', 'IQD': 'د.ع',
    'IRR': '﷼', 'ISK': 'kr', 'JMD': '$', 'JOD': 'JD', 'JPY': '¥', 'KES': 'Ksh', 'KGS': 'сом', 'KHR': '៛',
    'KMF': '₣', 'KPW': '₩', 'KRW': '₩', 'KWD': 'د.ك', 'KYD': '$', 'KZT': '₸', 'LAK': '₭', 'LBP': 'LL',
    'LKR': 'රු', 'LRD': '$', 'LSL': 'M', 'LTL': 'Lt', 'LVL': 'Ls', 'LYD': 'ل.د', 'MAD': 'د.م.', 'MGA': 'Ar',
    'MKD': 'ден', 'MMK': 'K', 'MNT': '₮', 'MOP': 'MOP$', 'MRO': 'UM', 'MUR': '₨', 'MVR': 'Rf.', 'MWK': 'MK',
    'MXN': '$', 'MYR': 'RM', 'MZN': 'MT', 'NAD': '$', 'NGN': '₦', 'NIO': 'C$', 'NOK': 'kr', 'NPR': '₨',
    'NZD': '$', 'OMR': 'ر.ع.', 'PAB': 'B/.', 'PEN': 'S/', 'PGK': 'K', 'PHP': '₱', 'PKR': '₨', 'PLN': 'zł',
    'PYG': '₲', 'QAR': 'ر.ق', 'RSD': 'дин', 'RUB': '₽', 'RWF': 'FRw', 'SAR': 'ر.س', 'SBD': '$', 'SCR': 'SRe',
    'SEK': 'kr', 'SGD': '$', 'SHP': '£', 'SLL': 'Le', 'SOS': 'Sh.So', 'SRD': '$', 'STD': 'Db', 'SVC': '₡',
    'SYP': 'LS', 'SZL': 'E', 'THB': '฿', 'TND': 'د.ت', 'TOP': 'T$', 'TRY': '₺', 'TTD': '$', 'TWD': '$',
    'TZS': 'Tsh', 'UAH': '₴', 'UGX': 'USh', 'USD': '$', 'USN': '$', 'USS': '$', 'UYU': '$', 'VEB': 'Bs.',
    'VEF': 'Bs.F', 'VND': '₫', 'VUV': 'VT', 'WST': 'WS$', 'XCD': '$', 'XSU': 'Sucre', 'ZAR': 'R', 'ZMK': 'ZK',
    'ZMW': 'ZK', 'ZWG': 'ZiG', 'ZWL': '$',
}


def _renderer_unit_exponent(facts) -> int:
    """EdgarRenderer's scale for one unit's facts on a report (Report.py ``scaleUnitGlobally``).

    A unit is scaled only when every one of its facts with a ``decimals``
    is at -3 or below; ``INF`` inhibits scaling. The renderer tests
    ``maxSoFar > -3`` before taking the maximum, so the fact that breaks
    the rule may be the last one read, but the result is the same: the
    largest ``decimals`` decides. The exponent is that maximum rounded to
    a multiple of 3 (0 means not scaled).
    """
    max_so_far = None
    for fact in facts:
        decimals = str(fact.decimals).strip() if fact.decimals is not None else ''
        if not decimals or decimals.lower() == 'nan':
            continue
        if decimals.casefold() == 'inf' or (max_so_far is not None and max_so_far > -3):
            return 0
        try:
            value = int(decimals)
        except ValueError:
            return 0
        max_so_far = value if max_so_far is None else max(max_so_far, value)
    if max_so_far is None or max_so_far > -3:
        return 0
    return round(max_so_far / 3) * 3


def _shared_symbol_scales(cr, index: '_FactIndex', metalinks, xbrl, role: str
                          ) -> Optional[Dict[str, Tuple[Optional[int], Optional[str]]]]:
    """Per-unit scales when a declared scale's symbol is shared by several currencies.

    The renderer writes one ``{symbol} in {scale}`` per scaled unit, so
    ``$ in Thousands`` on a page that holds both CAD and USD facts (both
    ``$`` in the registry) does not say which of them is in thousands.
    Several unit ids of one currency do not make a symbol shared.
    Only then is the renderer's own rule (``_renderer_unit_exponent``)
    applied, per unit, to the statement's facts: those of its presented
    concepts in contexts on its own axes. Returns ``{unit id: (scale, None)}``
    or ``{unit id: (None, reason)}`` when the rule cannot settle it, or None
    when no declared symbol is shared (the declaration is read as before).
    """
    declared = {symbol: scale for symbol, scale in (cr.unit_scales or {}).items() if is_currency_unit(symbol)}
    if not declared:
        return None
    references = _presentation_references(xbrl, role)
    if not references:
        return None
    concepts = {_normalize_concept_id(c) for c in references}
    axes = {c for c in concepts if c.endswith('Axis')}
    page_symbols = _page_unit_symbols(cr)
    plain, fitting, codes = _statement_unit_facts(index, metalinks, concepts, axes)
    shared = _symbols_shared_by_currencies(declared, codes, page_symbols)
    if not shared:
        return None
    out: Dict[str, Tuple[Optional[int], Optional[str]]] = {}
    for symbol, units in shared.items():
        out.update(_shared_symbol_unit_scales(symbol, units, declared, codes, plain, fitting))
    return out


def _page_unit_symbols(cr) -> Dict[str, str]:
    """``{ISO code: symbol}`` for every unit label the page prints (column units and the title's unit)."""
    page_symbols = {}
    for label in list(getattr(cr, 'column_units', None) or []) + [cr.header_unit]:
        if unit_code(label) and unit_symbol(label):
            page_symbols[unit_code(label)] = unit_symbol(label)
    return page_symbols


def _statement_unit_facts(index: '_FactIndex', metalinks, concepts: set, axes: set
                          ) -> Tuple[Dict[str, list], Dict[str, list], Dict[str, str]]:
    """The statement's facts by unit id: ``(undimensioned, all, {unit id: currency code})``.

    A statement's facts are those of its presented concepts in contexts on
    its own axes; a unit's currency code is taken from its monetary facts.
    Part of ``_shared_symbol_scales``.
    """
    # unit id -> facts: the statement's undimensioned facts, and all its facts
    plain: Dict[str, list] = defaultdict(list)
    fitting: Dict[str, list] = defaultdict(list)
    codes: Dict[str, str] = {}
    for (concept, _period, dims), facts in index.facts.items():
        if concept not in concepts or not all(axis in axes for axis, _member in dims):
            continue
        tag = metalinks.get_tag(concept.replace(':', '_')) if metalinks is not None else None
        monetary = 'monetaryItemType' in ((tag.xbrltype if tag else '') or '')
        _add_unit_facts(facts, dims, monetary, plain, fitting, codes)
    return plain, fitting, codes


def _add_unit_facts(facts, dims, monetary: bool, plain: Dict[str, list], fitting: Dict[str, list],
                    codes: Dict[str, str]) -> None:
    """File one context's facts under their unit ids (see ``_statement_unit_facts``)."""
    for fact in facts:
        unit = (fact.unit_ref or '').strip()
        if not unit:
            continue
        if monetary and fact.currency:
            codes.setdefault(unit, fact.currency)
        fitting[unit].append(fact)
        if not dims:
            plain[unit].append(fact)


def _symbols_shared_by_currencies(declared: Dict[str, int], codes: Dict[str, str],
                                  page_symbols: Dict[str, str]) -> Dict[str, list]:
    """``{symbol: [unit id, ...]}`` for each declared symbol that units of different currencies print as.

    A unit prints as the page's symbol for its currency, else the
    registry's, else its own id. Part of ``_shared_symbol_scales``.
    """
    def symbol_of(unit: str) -> str:
        code = codes[unit]
        return page_symbols.get(code) or _UTR_CURRENCY_SYMBOLS.get(code) or unit

    sharing: Dict[str, list] = defaultdict(list)
    for unit in codes:
        sharing[symbol_of(unit)].append(unit)
    # Shared only by different currencies: one currency filed under two unit
    # ids (``usd`` and ``U_USD``) is one currency, and the page's declaration
    # is read for it as for any single-currency page.
    shared = {symbol: units for symbol, units in sharing.items()
              if symbol in declared and len({codes[u] for u in units}) > 1}
    return shared


def _settled_unit_exponents(units: list, plain: Dict[str, list], fitting: Dict[str, list]
                            ) -> Dict[str, Optional[int]]:
    """Each unit's renderer exponent, or None where its undimensioned facts and all its facts disagree."""
    exponents = {}
    for unit in units:
        undimensioned, every = _renderer_unit_exponent(plain[unit]), _renderer_unit_exponent(fitting[unit])
        exponents[unit] = undimensioned if undimensioned == every else None
    return exponents


def _scales_give_declaration(scales: Dict[str, int], declared_scale: int) -> bool:
    """Whether per-unit scales produce the page's declaration: each 1 or the declared scale, one the declared."""
    return not (any(scale not in (1, declared_scale) for scale in scales.values())
                or declared_scale not in scales.values())


def _shared_symbol_unit_scales(symbol: str, units: list, declared: Dict[str, int], codes: Dict[str, str],
                               plain: Dict[str, list], fitting: Dict[str, list]
                               ) -> Dict[str, Tuple[Optional[int], Optional[str]]]:
    """Each unit's scale under one shared symbol by the renderer's rule, or a reason for all of them.

    The rule must give the same answer on the statement's undimensioned
    facts as on all its facts, and must reproduce the page's declaration
    (every unit at 1 or the declared scale, at least one at the declared
    scale). Part of ``_shared_symbol_scales``.
    """
    out: Dict[str, Tuple[Optional[int], Optional[str]]] = {}
    named = ', '.join(sorted(codes[u] for u in units))
    exponents = _settled_unit_exponents(units, plain, fitting)
    if any(e is None for e in exponents.values()):
        reason = (f"page declares '{symbol} in ...' and {named} all print as '{symbol}'; the renderer's rule "
                  "(scale a unit only when all its facts on the report are at decimals -3 or below) gives "
                  "different answers for the statement's undimensioned facts and for all its facts, so "
                  "which unit is scaled is not settled")
        out.update({u: (None, reason) for u in units})
        return out
    scales = {unit: 10 ** -e for unit, e in exponents.items()}
    if not _scales_give_declaration(scales, declared[symbol]):
        given = dict(sorted((codes[u], scale) for u, scale in scales.items()))
        reason = (f"page declares '{symbol} in ...' ({declared[symbol]}) and {named} all print as "
                  f"'{symbol}'; the renderer's rule gives {given}, which does not produce the page's "
                  "declaration, so which unit is scaled is not settled")
        out.update({u: (None, reason) for u in units})
        return out
    out.update({unit: (scale, None) for unit, scale in scales.items()})
    return out


def _cell_scale(chosen, xbrltype: str, cr, column_unit: Optional[str],
                currency_scaling: int,
                unit_scales: Optional[Dict[str, Tuple[Optional[int], Optional[str]]]] = None
                ) -> Tuple[Optional[int], Optional[str]]:
    """The factor the page divides this fact by, from the fact's own unit.

    Returns ``(scale, None)`` or ``(None, reason)``. Per-share, pure and
    percent values are never scaled. Share counts use the page's shares
    statement. Only a currency amount uses a currency scale: the column's
    own currency when the page declares currencies at different scales,
    else the report's (``ViewerReport.currency_scaling``). When a declared
    symbol is shared by several currencies on the page, ``unit_scales``
    (``_shared_symbol_scales``) gives each unit's scale. Any other unit
    (ounces, tokens) is shown in whole units unless the page declares a
    scale for it.
    """
    if any(t in xbrltype for t in ('perShareItemType', 'pureItemType', 'percentItemType')):
        return 1, None
    unit_ref = (chosen.unit_ref or '').strip()
    if 'sharesItemType' in xbrltype or unit_ref.lower() == 'shares':
        return cr.shares_scaling, None
    if chosen.currency or 'monetaryItemType' in xbrltype:
        if unit_scales and unit_ref in unit_scales:
            return unit_scales[unit_ref]
        if len(declared_currency_scales(cr.unit_scales)) <= 1:
            return currency_scaling, None
        symbol = unit_symbol(column_unit or cr.header_unit)
        if symbol in cr.unit_scales:
            return cr.unit_scales[symbol], None
        return None, (f"page declares different scales per currency {cr.unit_scales} "
                      "and names no unit for this column")
    for unit, scale in cr.unit_scales.items():
        if unit.lower() == unit_ref.lower():
            return scale, None
    others = {u: s for u, s in cr.unit_scales.items()
              if u != 'shares' and '/' not in u and not is_currency_unit(u)}
    if others:
        return None, (f"page declares scales for {others}, which cannot be tied to unit {unit_ref!r}")
    return 1, None


# ---------------------------------------------------------------------------
# Statements of changes in equity
#
# The SEC renderer (Arelle EdgarRenderer) lays a statement of equity out
# differently from every other statement (``Cube.isStatementOfEquity``,
# EdgarRenderer Cube.py, decided from the statement's name):
#
# - Rows: the period is the outermost row command, then the concept in
#   presentation order, then any axis the renderer moves to rows
#   (Embedding.py, ``commandTextListOfLists`` for an equity cube;
#   ``Filing.builtinEquityRowAxes``), whose members the row's heading names
#   in parentheses. Only complete *movements* survive (Cube.py
#   ``SurvivorsOfMovementAnalysis``): a duration with an instant on the day
#   before it starts and one on its end date. The period members are those
#   durations and instants, sorted by start and then month count
#   (``populatePeriodPseudoaxis``). A row whose arc has a period-start or
#   period-end label is a balance row (class ``rc``, ``IsCalendarTitle`` in
#   InstanceReport_Common.xslt) dated with its instant ("... at Dec. 31,
#   2021"); every other row shows the facts of its block's period and no
#   date. A start row that repeats the end row of the previous movement is
#   hidden (Report.py ``HideAdjacentInstantRows``), and rows of a movement
#   can follow its closing rows when the presentation puts them later. So
#   a row's period is read from where it can sit among the blocks
#   (``_place_rows``), never from the nearest balance row.
# - Columns: every other axis in the statement's presentation group, except
#   the axes the renderer moves to rows (``Filing.builtinEquityRowAxes``).
#   A column's heading lists, one line per axis, the label of each member
#   that is not the axis default (Report.py ``generateRowOrColHeading``);
#   the label is the member's label under the preferred label role of its
#   presentation arc (PresentationGroup.py ``buildLabel``). A column on every
#   axis default has no line and is headed "Total" (Embedding.py
#   ``getEmptyHeading``).
# ---------------------------------------------------------------------------

_BALANCE_DATE_RE = re.compile(r'\sat\s+([A-Z][a-z]{2}\.?\s+\d{1,2},\s+\d{4})\s*$')
_EQUITY_ROW_AXES = frozenset({
    'CreationDateAxis', 'StatementScenarioAxis', 'AdjustmentsForNewAccountingPronouncementsAxis',
    'AdjustmentsForChangeInAccountingPrincipleAxis',
    'ErrorCorrectionsAndPriorPeriodAdjustmentsRestatementByRestatementPeriodAndAmountAxis',
    'RetrospectiveApplicationAndRetrospectiveRestatementAxis'})
# The renderer's pattern for the us-gaap and ifrs-full namespaces (Filing.py
# ``nspattern``): either URI scheme, since IFRS moved to https in 2022.
_EQUITY_ROW_AXIS_NAMESPACES = re.compile(r'(fasb\.org/us-gaap/20|ifrs\.org/taxonomy/20[^/]*/ifrs)')
_STANDARD_LABEL_ROLE = 'http://www.xbrl.org/2003/role/label'
_TOTAL_HEADING = 'Total'


def _heading_text(text: str) -> str:
    """A heading or label as compared: no-break spaces as spaces, runs of space collapsed."""
    return ' '.join((text or '').replace('\xa0', ' ').split())


def _element_labels(xbrl, element_id: str) -> Dict[str, str]:
    catalog = getattr(xbrl, 'element_catalog', None) or {}
    element = catalog.get(element_id) if hasattr(catalog, 'get') else None
    labels = getattr(element, 'labels', None)
    return dict(labels) if isinstance(labels, dict) else {}


def _rendered_label(xbrl, element_id: str, preferred_role: Optional[str]) -> str:
    """The label the renderer prints for an element under a preferred label role.

    The preferred role's label, else the standard label, else the local name
    split at its capitals (EdgarRenderer ``Utils.prettyPrintQname``).
    """
    labels = _element_labels(xbrl, element_id)
    text = labels.get(preferred_role) if preferred_role else None
    text = text or labels.get(_STANDARD_LABEL_ROLE)
    if not text:
        local = element_id.split('_', 1)[-1]
        text = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', local)
    return _heading_text(text)


def _local_name(element_id: str) -> str:
    return element_id.split('_', 1)[-1] if '_' in element_id else element_id.split(':')[-1]


class _EquityColumns:
    """Resolves an equity statement's column headings to the members they name.

    Built from the statement's presentation tree, the member labels under
    their arcs' preferred label roles, and each axis default from the
    definition linkbase. A heading resolves only when exactly one
    combination of members on distinct column axes prints it.
    """

    def __init__(self, xbrl, role: str, names: _Names, metalinks):
        self.reason: Optional[str] = None
        self.names = names
        tree = (getattr(xbrl, 'presentation_trees', None) or {}).get(role)
        if tree is None:
            self.reason = "the statement's presentation tree is not available to resolve its member columns"
            return
        role_axes = {}
        axes_for_role = getattr(xbrl, 'axes_for_role', None)
        if callable(axes_for_role):
            role_axes = axes_for_role(role) or {}
        merged_axes = getattr(xbrl, 'axes', None) or {}

        def is_axis(element_id: str) -> bool:
            tag = metalinks.get_tag(element_id) if metalinks is not None else None
            if tag is not None and getattr(tag, 'is_axis', None) is not None:
                return bool(tag.is_axis)
            return element_id in role_axes or element_id.endswith('Axis')

        # Pre-order walk; a later visit of an element relabels it, as the
        # renderer's labelDict does.
        labels: Dict[str, str] = {}
        axis_members: Dict[str, List[str]] = {}
        order: List[str] = []
        # primary items in presentation order: (position, element id, preferred label role, label)
        self.primary: List[Tuple[int, str, Optional[str], str]] = []
        # pre-order position of each axis, and of each member on its axis (the
        # last visit under that axis), as the renderer orders columns
        # (PresentationGroup.doPreorderTraversal: ``len(visited)``)
        self.axis_position: Dict[str, int] = {}
        self.member_position: Dict[str, Dict[str, int]] = defaultdict(dict)
        visits = [0]
        children_of = _tree_children(tree)

        def walk(element_id: str, preferred: Optional[str], axis: Optional[str], seen: set):
            if element_id in seen:
                return
            seen = seen | {element_id}
            visits[0] += 1
            labels[element_id] = _rendered_label(xbrl, element_id, preferred)
            node = tree.all_nodes.get(element_id)
            here_axis = axis
            if axis is None and not is_axis(element_id):
                self.primary.append((len(self.primary), element_id, preferred, labels[element_id]))
            if is_axis(element_id):
                here_axis = element_id
                if element_id not in axis_members:
                    axis_members[element_id] = []
                    order.append(element_id)
                    self.axis_position[element_id] = visits[0]
            elif axis is not None:
                self.member_position[axis][element_id] = visits[0]
                if element_id not in axis_members[axis]:
                    axis_members[axis].append(element_id)
            if node is None and element_id not in children_of:
                return
            for child, child_preferred in children_of.get(element_id, []):
                walk(child, child_preferred, here_axis, seen)

        roots = list(getattr(tree, 'root_element_ids', None) or [])
        if not roots and getattr(tree, 'root_element_id', None):
            roots = [tree.root_element_id]
        for root in roots:
            walk(root, None, None, set())

        def is_row_axis(element_id: str) -> bool:
            # The renderer's list names us-gaap and ifrs-full axes; a filer's
            # own axis with the same local name stays a column axis.
            if _local_name(element_id) not in _EQUITY_ROW_AXES:
                return False
            tag = metalinks.get_tag(element_id) if metalinks is not None else None
            uri = getattr(tag, 'nsuri', None) if tag is not None else None
            if uri:
                return bool(_EQUITY_ROW_AXIS_NAMESPACES.search(uri))
            return element_id.split('_', 1)[0] in ('us-gaap', 'ifrs-full')

        self.axes: List[str] = [a for a in order if not is_row_axis(a)]
        self.row_axes: List[str] = [a for a in order if is_row_axis(a)]
        self.defaults: Dict[str, Optional[str]] = {}
        self.typed: set = set()
        for axis in self.axes:
            declared = role_axes.get(axis) or merged_axes.get(axis)
            self.defaults[axis] = getattr(declared, 'default_member_id', None) if declared is not None else None
            if declared is not None and getattr(declared, 'is_typed_dimension', False):
                self.typed.add(axis)
        # heading line -> [(axis, member)] of the non-default members it can name
        self.by_label: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for axis in self.axes:
            for member in axis_members.get(axis, []):
                if member != self.defaults.get(axis):
                    self.by_label[labels[member]].append((axis, member))
        # the same for the axes the renderer moves to rows, whose members a
        # row's heading names in parentheses after the concept's label
        self.by_row_label: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for axis in self.row_axes:
            declared = role_axes.get(axis) or merged_axes.get(axis)
            default = getattr(declared, 'default_member_id', None) if declared is not None else None
            for member in axis_members.get(axis, []):
                if member != default:
                    self.by_row_label[labels[member]].append((axis, member))

    def row_options(self, concept_id: str, label: str, kinds: Tuple[str, ...], roles: Optional[list] = None):
        """Where a row of ``concept_id`` headed ``label`` can sit: ``[(position, kind, row dims)]``.

        ``kinds`` are the label kinds the row may have ('start', 'end' for a
        balance row; 'plain' for any other). A node whose label the row
        shows exactly is a row on every row-axis default; the label followed
        by ``(member, ...)`` names members of row axes. When no node's label
        fits and the statement has no row axes, every node of the kind is
        possible (the row names no member); with row axes, none is.

        ``roles``, when given, receives the preferred label role of each
        returned option's arc, in the same order.
        """
        nodes = []
        for position, element_id, preferred, node_label in self.primary:
            if element_id != concept_id:
                continue
            kind = ('start' if is_period_start_label_role(preferred) else
                    'end' if is_period_end_label_role(preferred) else 'plain')
            if kind in kinds:
                nodes.append((position, kind, node_label, preferred))
        text = _heading_text(label)
        out = []
        found_roles = []
        for position, kind, node_label, preferred in nodes:
            if text == node_label:
                out.append((position, kind, frozenset()))
                found_roles.append(preferred)
            elif self.by_row_label and text.startswith(node_label + ' (') and text.endswith(')'):
                parts = text[len(node_label) + 2:-1].split(', ')
                picks = [self.by_row_label.get(part, []) for part in parts]
                if all(len(p) == 1 for p in picks) and len({p[0][0] for p in picks}) == len(picks):
                    out.append((position, kind, frozenset((self.names.viewer_name(a), self.names.viewer_name(m))
                                                          for p in picks for a, m in p)))
                    found_roles.append(preferred)
        if not out and not self.by_row_label:
            out = [(position, kind, frozenset()) for position, kind, _label, _preferred in nodes]
            found_roles = [preferred for _position, _kind, _label, preferred in nodes]
        if roles is not None:
            roles.extend(found_roles)
        return out

    def heading_combos(self, parts: List[str], unit: Optional[str]) -> Tuple[List[frozenset], str, Optional[str]]:
        """Every combination of column-axis members whose column the renderer heads with ``parts``.

        Returns ``(combos, shown, reason)``; each combo is a frozenset of
        ``(axis id, member id)`` for the non-default members it names. A
        column on every default is headed "Total" (``Embedding.getEmptyHeading``),
        so "Total" is also that combination, even when a member's label is
        "Total" too. A heading with no line at all is not a heading the
        renderer prints; it is never read as the all-defaults column.
        """
        if self.reason:
            return [], '', self.reason
        lines = [_heading_text(p) for p in parts if _heading_text(p)]
        unit_text = _heading_text(unit) if unit else None
        kept = [line for line in lines if not (line == unit_text and line not in self.by_label)]
        shown = ' / '.join(kept) or '(empty)'
        if not lines:
            return [], shown, "column heading is blank: it names no member and is not the renderer's 'Total'"
        lines = kept
        combos: List[frozenset] = []
        if lines == [_TOTAL_HEADING]:
            combos.append(frozenset())
        options = [self.by_label.get(line, []) for line in lines]
        unknown = [line for line, opts in zip(lines, options, strict=True) if not opts]
        if unknown and not combos:
            return [], shown, (f"column heading {shown!r}: {unknown[0]!r} is not the label of any member "
                               "on the statement's column axes")
        if not unknown:
            found: List[frozenset] = []

            def assign(k: int, used: set, picked: List[Tuple[str, str]]):
                if k == len(options):
                    found.append(frozenset(picked))
                    return
                for axis, member in options[k]:
                    if axis not in used:
                        assign(k + 1, used | {axis}, picked + [(axis, member)])

            assign(0, set(), [])
            if not found and not combos:
                return [], shown, f"column heading {shown!r} names two members of one axis"
            combos.extend(found)
        combos = list(dict.fromkeys(combos))
        printable = []
        for combo in combos:
            named = {axis for axis, _member in combo}
            if not [axis for axis in self.axes if axis not in named and not self.defaults.get(axis)]:
                printable.append(combo)
        if not printable:
            named = {axis for axis, _member in combos[0]}
            no_default = [axis for axis in self.axes if axis not in named and not self.defaults.get(axis)]
            return [], shown, (f"column heading {shown!r} does not name a member of {no_default[0]}, "
                               "which has no default member")
        return printable, shown, None

    def dims_of(self, combo: frozenset) -> Dims:
        return frozenset((self.names.viewer_name(axis), self.names.viewer_name(member)) for axis, member in combo)

    def column_order(self, combo: frozenset) -> Optional[tuple]:
        """Where the renderer puts this combination's column, or None when it prints none.

        Columns sort by each column axis in presentation order, then by the
        member's presentation position on that axis; a defaulted axis sorts
        at its default member's position, and a fact defaulted on an axis
        whose default is not presented is filtered (Embedding.py,
        ``generateFactAxisMemberForNonPrimary``). A typed axis has no such
        order here.
        """
        chosen = dict(combo)
        key = []
        for axis in sorted(self.axes, key=lambda a: self.axis_position.get(a, 0)):
            if axis in self.typed:
                return None
            member = chosen.get(axis, self.defaults.get(axis))
            position = self.member_position.get(axis, {}).get(member)
            if position is None:
                return None
            key.append(position)
        return tuple(key)

    def resolve_page(self, headings: List[Tuple[List[str], Optional[str]]], statement_dims: set
                     ) -> List[Tuple[Optional[Dims], Optional[str]]]:
        """The dimensions of every column of the page, or the reason a column cannot be told.

        A heading that only one combination prints is that combination.
        Columns whose headings two combinations could print (identical
        headings, or "Total" for the all-defaults column and a member
        labelled "Total") are told apart by the renderer's column order: the
        renderer prints a column for each combination that has facts on the
        statement, in ``column_order``. When as many such combinations as
        columns with that heading exist, the k-th column is the k-th
        combination; otherwise the columns are not comparable.
        """
        out: List[Tuple[Optional[Dims], Optional[str]]] = [(None, None)] * len(headings)
        groups: Dict[tuple, List[int]] = defaultdict(list)
        info = []
        for c, (parts, unit) in enumerate(headings):
            combos, shown, reason = self.heading_combos(parts, unit)
            info.append((combos, shown, reason))
            unit_text = _heading_text(unit) if unit else None
            groups[(shown, unit_text, reason)].append(c)
        row_axis_names = {self.names.viewer_name(a) for a in self.row_axes}
        for (_shown, _unit, reason), cols in groups.items():
            combos, shown, _reason = info[cols[0]]
            if reason:
                for c in cols:
                    out[c] = (None, reason)
                continue
            if len(combos) == 1 and len(cols) == 1:
                out[cols[0]] = (self.dims_of(combos[0]), None)
                continue
            filed = []
            for combo in combos:
                order = self.column_order(combo)
                dims = self.dims_of(combo)
                if order is not None and any(
                        frozenset(d for d in seen if d[0] not in row_axis_names) == dims for seen in statement_dims):
                    filed.append((order, combo))
            filed.sort(key=lambda item: item[0])
            if len(filed) == len(cols):
                for c, (_order, combo) in zip(cols, filed, strict=True):
                    out[c] = (self.dims_of(combo), None)
                continue
            listed = '; '.join(', '.join(sorted(f'{a}={m}' for a, m in combo)) or 'every default'
                               for combo in combos)
            told = (f"{len(cols)} column(s) carry the heading and {len(filed)} of the combinations that print "
                    "it have facts on the statement, so the renderer's column order does not tell which "
                    "column is which")
            reason = (f"column heading {shown!r} matches the labels of several members: {listed}; {told}"
                      if len(combos) > 1 else f"column heading {shown!r} names {listed}; {told}")
            for c in cols:
                out[c] = (None, reason)
        return out


def _day_before(date: str) -> str:
    return (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')


def _statement_periods(index: '_FactIndex', concepts: set, page_movements=()) -> List[dict]:
    """The period blocks the renderer prints for a statement of equity, in page order.

    As EdgarRenderer's ``SurvivorsOfMovementAnalysis``: every duration among
    the statement's facts with an instant on the day before it starts and one
    on its end date is a movement; those durations and instants are the
    period row members, sorted by start (an instant sorts at the start of
    the next day) and then by month count. Facts of every presented concept
    in any context count, nil facts included (the renderer prints a nil
    fact's cell blank, and its period still makes a block), so a period the
    renderer printed is never missing from the list (an extra one can only
    make a row's period ambiguous).

    ``page_movements`` are ``(start, end)`` durations the page's own dated
    balance rows delimit (``_page_movements``). They are added as movements
    even when the facts do not give them, so a block whose facts are gone
    or misdated is still a block: its rows are then placed in it and
    found missing, instead of having nowhere to go.
    """
    durations, instants = set(), set()
    for concept, period_key in getattr(index, 'fact_periods', None) or index.period_contexts:
        if concept not in concepts:
            continue
        if period_key.startswith('instant_'):
            instants.add(period_key[len('instant_'):])
        elif period_key.startswith('duration_'):
            parts = period_key[len('duration_'):].split('_')
            if len(parts) == 2:
                durations.add((parts[0], parts[1]))
    periods = []
    used_instants = set()
    movements = set()
    for start, end in durations:
        opening = _day_before(start)
        if opening in instants and end in instants:
            months = _rendered_months(start, end)
            periods.append(dict(kind='duration', key=f'duration_{start}_{end}', opening=opening, closing=end,
                                sort=(start, months if months is not None else 0)))
            used_instants.update({opening, end})
            movements.add((start, end))
    for start, end in set(page_movements) - movements:
        months = _rendered_months(start, end)
        periods.append(dict(kind='duration', key=f'duration_{start}_{end}', opening=_day_before(start),
                            closing=end, sort=(start, months if months is not None else 0)))
        used_instants.update({_day_before(start), end})
    for date in used_instants:
        next_day = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        periods.append(dict(kind='instant', key=f'instant_{date}', date=date, sort=(next_day, 0)))
    periods.sort(key=lambda p: p['sort'])
    return periods


def _page_movements(entries: List[dict]) -> set:
    """The durations the page's dated balance rows delimit: ``{(start, end)}``.

    A block prints its opening balances (dated the day before it starts)
    and its closing balances (dated its end); the renderer hides an opening
    row that repeats the closing row just above it (``HideAdjacentInstantRows``).
    So two balance rows of one concept that follow each other on the page,
    the second dated later and presented as a closing row (an end label),
    bound a block running from the day after the first date to the second.
    A pair that bounds no real block only adds a reading, which can make a
    row's period ambiguous.
    """
    out = set()
    last: Dict[str, str] = {}
    for entry in entries:
        if entry['kind'] != 'balance' or not entry.get('date'):
            continue
        previous = last.get(entry['concept_id'])
        closing = any(option[1] == 'end' for option in entry['options'])
        if previous and previous < entry['date'] and closing:
            start = (datetime.strptime(previous, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            out.add((start, entry['date']))
        last[entry['concept_id']] = entry['date']
    return out


def _place_rows(entries: List[dict], periods: List[dict],
                options_out: Optional[List[set]] = None) -> List[Optional[set]]:
    """Every period block each page row can belong to, over all readings of the page.

    A reading splits the page's rows, in order, into consecutive blocks, one
    per period in the renderer's order (``_statement_periods``; a period may
    print no rows). Within a block the rows follow the presentation order
    (a row on a row-axis member follows the row on the default at the same
    position). A balance row sits only in a movement whose opening (start
    label) or closing (end label) is the row's date; another row of a
    duration concept only in a movement; of an instant concept in an
    instant block, or in a movement, where it shows the instant at the
    movement's opening or closing date (``_block_period_keys``). A row's period is known
    when every reading gives it the same period; forward and backward
    reachability give exactly that.

    A row that fits no block is left out of the readings (its entry is an
    empty set), so it does not take every other row's placement with it;
    leaving a row out only adds readings. When no reading of the remaining
    rows exists at all, every placement is None.

    ``options_out``, when given, receives for each entry the indexes into its
    ``options`` that some reading uses: a concept with two arcs under one
    parent (EPAM's tax-withholding row, negated in the first, plain in the
    second) is read at one arc per row when the block order allows only one.
    """
    n, m = len(entries), len(periods)

    def fits(entry, option, g):
        period = periods[g]
        kind = option[1]
        if entry['kind'] == 'balance':
            if period['kind'] != 'duration':
                return False
            return entry['date'] == (period['opening'] if kind == 'start' else period['closing'])
        return period['kind'] == entry['period_type'] or (
            entry['period_type'] == 'instant' and period['kind'] == 'duration')

    def follows(prev, prev_g, cur, cur_g):
        if prev_g == cur_g:
            return prev[0] < cur[0] or (prev[0] == cur[0] and prev[2] != cur[2])
        return periods[prev_g]['sort'] < periods[cur_g]['sort'] or (
            periods[prev_g]['sort'] == periods[cur_g]['sort'])  # order of tied periods is not fixed

    states = [[(g, o) for g in range(m) for o in entry['options'] if fits(entry, o, g)] for entry in entries]
    chain = [i for i in range(n) if states[i]]
    forward: Dict[int, set] = {}
    previous = None
    for i in chain:
        forward[i] = {(g, o) for g, o in states[i]
                      if previous is None or any(follows(po, pg, o, g) for pg, po in forward[previous])}
        previous = i
    backward: Dict[int, set] = {}
    following = None
    for i in reversed(chain):
        backward[i] = {(g, o) for g, o in states[i]
                       if following is None or any(follows(o, g, no, ng) for ng, no in backward[following])}
        following = i
    if chain and not forward[chain[-1]]:
        if options_out is not None:
            options_out.extend(set() for _ in range(n))
        return [None] * n
    if options_out is not None:
        for i in range(n):
            used = {o for _g, o in forward[i] & backward[i]} if states[i] else set()
            options_out.append({k for k, o in enumerate(entries[i]['options']) if o in used})
    return [{g for g, o in forward[i] & backward[i]} if states[i] else set() for i in range(n)]


def _block_period_keys(entry: dict, period: dict) -> Tuple[str, ...]:
    """The periods a non-balance row can show in a block.

    A row of an instant concept inside a movement shows an instant at the
    movement's opening or its closing date, and the page does not say
    which: Digi International's 10-K (0000854775-20-000032, R7) prints the
    "Cumulative-effect adjustment" row in the fiscal 2018 movement with
    total equity at Sep. 30, 2018 (330,493) beside the adoption adjustment
    at Sep. 30, 2017 (19), and in fiscal 2020 with total equity at the
    opening (348,978) although the closing (371,500) is filed. Such a cell
    is compared only when exactly one of the two has a fact in its context.
    """
    if entry.get('period_type') == 'instant' and period['kind'] == 'duration':
        return (f"instant_{period['opening']}", f"instant_{period['closing']}")
    return (period['key'],)


def _is_equity_layout(cr) -> bool:
    """The page is laid out as a statement of equity: member columns and dated balance rows.

    ``rc`` rows exist only on a statement the renderer treats as one of
    changes in equity (Report.py: ``IsCalendarTitle`` needs
    ``isStatementOfEquity``), and its columns carry no period.
    """
    headers = cr.period_headers or []
    if not headers or any(_DATE_RE.search(h) for h in headers):
        return False
    return any(c.row_class == 'rc' for c in (getattr(cr, 'unextracted_cells', None) or []))


def _compare_equity_statement(results: ComparisonResults, vr, cr, xbrl, index: '_FactIndex',
                              names: _Names, metalinks, tolerance: Optional[float],
                              currency_scaling: int,
                              unit_scales: Optional[Dict[str, Tuple[Optional[int], Optional[str]]]] = None) -> None:
    """Compare every numeric cell of a statement of changes in equity.

    A cell's member comes from its column heading (``_EquityColumns``) and
    any row-axis member its row's label names; its period from where its
    row sits among the statement's period blocks (``_place_rows``).
    """
    rows = cr.rows
    columns = _EquityColumns(xbrl, getattr(vr, 'role', ''), names, metalinks)
    headings = _equity_headings(cr)
    cell_columns = cr.row_cell_columns if len(cr.row_cell_columns) == len(rows) else None
    entries, other_cells = _equity_entries(cr, rows, columns, index)
    column_dims, periods = _place_equity_entries(entries, columns, index, headings)
    member_header_rows = any(crow.is_header and crow.is_dimensional for crow in rows)
    page = SimpleNamespace(results=results, vr=vr, cr=cr, metalinks=metalinks, index=index, names=names,
                           columns=columns, column_dims=column_dims, periods=periods,
                           member_header_rows=member_header_rows, currency_scaling=currency_scaling,
                           tolerance=tolerance, unit_scales=unit_scales)
    judge = partial(_judge_equity_cell, page)

    for entry in entries:
        if entry['kind'] == 'balance':
            for cell in entry['cells']:
                judge(entry, cell.column, cell.value)
        else:
            crow = rows[entry['row']]
            for value_key, display_val in crow.values.items():  # noqa: PD011 (dict)
                column = cell_columns[entry['row']].get(value_key) if cell_columns is not None else None
                judge(entry, column, display_val)

    _emit_unextracted_cells(results, vr, cr, other_cells)


def _equity_headings(cr) -> List[Tuple[List[str], Optional[str]]]:
    """Each column's heading lines and unit, as ``_EquityColumns.resolve_page`` reads them."""
    heading_parts = getattr(cr, 'column_heading_parts', None) or []
    headings: List[Tuple[List[str], Optional[str]]] = []
    for c, header in enumerate(cr.period_headers):
        parts = heading_parts[c] if c < len(heading_parts) else [header]
        unit = cr.column_units[c] if c < len(cr.column_units) else None
        headings.append((parts, unit))
    return headings


def _equity_entries(cr, rows, columns: '_EquityColumns', index: '_FactIndex') -> Tuple[List[dict], list]:
    """The page's rows in order as entries, and the unextracted cells that are not balance rows.

    Balance rows (``rc``, carried as unextracted cells) come before the
    ConceptRow they precede; each entry carries the presentation options
    its label fits and their arcs' roles. Part of ``_compare_equity_statement``.
    """
    # The page's rows in order: balance rows (rc, carried as unextracted
    # cells) before the ConceptRow they precede, and every other data row.
    entries: List[dict] = []
    other_cells = []
    balance_at: Dict[int, List[dict]] = defaultdict(list)
    for cell in cr.unextracted_cells:
        if cell.row_class != 'rc' or cell.row_index is None or not cell.concept_id:
            other_cells.append(cell)
            continue
        _add_balance_cell(balance_at[cell.row_index], cell, columns)
    for i, crow in enumerate(rows):
        entries.extend(balance_at.pop(i, []))
        if crow.is_abstract or crow.is_dimensional or crow.is_header or not crow.values:  # noqa: PD011 (dict)
            continue
        concept = _normalize_concept_id(crow.concept_id)
        roles = []
        entries.append(dict(kind='row', concept_id=crow.concept_id, label=crow.label, row=i,
                            period_type=index.period_types.get(concept),
                            options=columns.row_options(crow.concept_id, crow.label, ('plain',), roles),
                            roles=roles))
    for leftover in balance_at.values():
        entries.extend(leftover)
    return entries, other_cells


def _add_balance_cell(group: List[dict], cell, columns: '_EquityColumns') -> None:
    """Add a balance-row cell to the balance entries before one ConceptRow.

    A cell of the same concept and label in a column the last entry does
    not have yet joins that entry; otherwise it starts a new balance entry,
    dated by its label. Part of ``_equity_entries``.
    """
    last = group[-1] if group else None
    if (last is not None and last['concept_id'] == cell.concept_id and last['label'] == cell.label
            and cell.column not in {c.column for c in last['cells']}):
        last['cells'].append(cell)
        return
    match = _BALANCE_DATE_RE.search(cell.label)
    info = _parse_viewer_period(match.group(1)) if match else None
    base = _BALANCE_DATE_RE.sub('', cell.label) if match else cell.label
    roles: List[Optional[str]] = []
    group.append(dict(kind='balance', concept_id=cell.concept_id, label=cell.label,
                      date=info['end'] if info else None, cells=[cell],
                      options=columns.row_options(cell.concept_id, base, ('start', 'end'), roles),
                      roles=roles))


def _place_equity_entries(entries: List[dict], columns: '_EquityColumns', index: '_FactIndex',
                          headings) -> Tuple[list, List[dict]]:
    """Resolve the columns' members and place each row in a period block.

    Returns ``(column dims, periods)``; each placeable entry gains
    ``groups`` (its possible period blocks) and has its ``roles`` narrowed
    to the arcs some reading places it at. Part of ``_compare_equity_statement``.
    """
    presented = {_normalize_concept_id(element_id) for _p, element_id, _r, _l in columns.primary}
    statement_dims = {dims for (concept, _key), contexts in index.period_contexts.items() if concept in presented
                      for dims in contexts}
    column_dims = columns.resolve_page(headings, statement_dims)
    periods = _statement_periods(index, presented, _page_movements(entries))
    placeable = _placeable_entries(entries)
    used_options: List[set] = []
    placements = _place_rows(placeable, periods, used_options) if columns.reason is None else []
    _record_placements(placeable, placements, used_options)
    return column_dims, periods


def _placeable_entries(entries: List[dict]) -> List[dict]:
    """The entries ``_place_rows`` places: dated balance rows, and rows of instant or duration concepts."""
    return [e for e in entries if e['options'] and e['kind'] == 'balance' and e['date']
            or e['options'] and e['kind'] == 'row' and e['period_type'] in ('instant', 'duration')]


def _record_placements(placeable: List[dict], placements: list, used_options: List[set]) -> None:
    """Store each entry's possible period blocks, and narrow its roles to the arcs some reading uses."""
    for entry, groups, used in zip(placeable, placements, used_options, strict=False):
        entry['groups'] = groups
        # The row's sign is read from the arcs some reading places it at.
        if used and len(entry['roles']) == len(entry['options']):
            entry['roles'] = [entry['roles'][k] for k in sorted(used)]


def _equity_period_of(entry: dict, columns: '_EquityColumns', periods: List[dict]
                      ) -> Tuple[Optional[List[str]], Optional[str], frozenset]:
    """The period keys an equity row's cells show, or a reason; and its row-axis dims.

    A balance row is its own date's instant; any other row's period is
    its period block's (``_equity_block_period``). Part of
    ``_compare_equity_statement``.
    """
    if columns.reason:
        return None, columns.reason, frozenset()
    if entry['kind'] == 'balance' and not entry['date']:
        return None, f"balance row {entry['label']!r} states no date", frozenset()
    if not entry['options']:
        return None, (f"row {entry['label']!r} is not a presented row of its concept, or names a "
                      "row-axis member the statement does not present"), frozenset()
    row_dims = {o[2] for o in entry['options']}
    if len(row_dims) > 1:
        return None, "the row's label fits more than one row-axis member", frozenset()
    # A balance row is dated: its instant is its own date, wherever it
    # sits and whatever facts exist. Any other row's period is its block's.
    if entry['kind'] == 'balance':
        return [f"instant_{entry['date']}"], None, next(iter(row_dims))
    return _equity_block_period(entry, periods, row_dims)


def _equity_block_period(entry: dict, periods: List[dict], row_dims: set
                         ) -> Tuple[Optional[List[str]], Optional[str], frozenset]:
    """A non-balance equity row's period: its one possible period block's (see ``_place_rows``)."""
    if 'groups' not in entry:
        return None, "the row's concept has no facts to place it in a period", frozenset()
    groups = entry['groups']
    if groups is None:
        return None, ("no reading of the page's row order fits the period blocks of the statement's "
                      "facts and balance rows"), frozenset()
    if not groups:
        return None, ("the row does not fit any period block the statement's facts and balance rows "
                      "give, in the renderer's order"), frozenset()
    keys = sorted({_block_period_keys(entry, periods[g]) for g in groups})
    if len(keys) > 1:
        listed = ', '.join(' or '.join(k) for k in keys)
        return None, f"the page's row order fits more than one period for this row: {listed}", frozenset()
    return list(keys[0]), None, next(iter(row_dims))


def _judge_equity_cell(page: SimpleNamespace, entry: dict, column: Optional[int], display_val: str):
    """Compare one cell of a statement of equity and emit its outcome (part of ``_compare_equity_statement``).

    ``page`` holds the statement's comparison state: results, report,
    resolved column dims, periods and the scale and tolerance settings.
    """
    results, vr, cr, metalinks, index, names = (page.results, page.vr, page.cr, page.metalinks,
                                                page.index, page.names)
    currency_scaling, tolerance, unit_scales = page.currency_scaling, page.tolerance, page.unit_scales
    label = entry['label']
    reading = _equity_cell_reading(cr, metalinks, entry, column, display_val)
    if reading is None:
        return
    xbrl_concept, xbrltype, unit, viewer_num, header = reading
    emit = partial(_emit, results, dict(concept_id=xbrl_concept, label=label, period=header,
                                        viewer_value=viewer_num, report=vr.short_name))
    if _equity_cell_settled(emit, page, column, display_val, viewer_num, xbrl_concept):
        return
    context = _equity_cell_context(emit, page, entry, column, xbrl_concept)
    if context is None:
        return
    period_keys, dims, row_dims = context
    negated, sign_role, sign_reason = _roles_sign(entry.get('roles') or [])
    _judge_cell(emit, index, names, xbrl_concept, period_keys, dims | row_dims, xbrltype, display_val,
                viewer_num, cr, unit, currency_scaling, tolerance,
                sign=(negated, sign_role, sign_reason), unit_scales=unit_scales)


def _equity_cell_reading(cr, metalinks, entry: dict, column: Optional[int], display_val: str):
    """``(concept, item type, column unit, number shown, column header)`` for an equity cell.

    None when the cell is not a numeric cell of the statement: a footnote
    marker, or an unreadable value of a concept whose type is not numeric
    (or a blank). Part of ``_judge_equity_cell``.
    """
    concept_id = entry['concept_id']
    xbrl_concept = _normalize_concept_id(concept_id)
    tag = metalinks.get_tag(concept_id)
    xbrltype = (tag.xbrltype if tag else '') or ''
    unit = cr.column_units[column] if column is not None and column < len(cr.column_units) else None
    viewer_num = _read_number(display_val, unit or cr.header_unit)
    if viewer_num is None and _not_a_numeric_cell(display_val, xbrltype):
        return None
    header = cr.period_headers[column] if column is not None and column < len(cr.period_headers) else ''
    return xbrl_concept, xbrltype, unit, viewer_num, header


def _not_a_numeric_cell(display_val: str, xbrltype: str):
    """An unread cell that is no number of the statement: a footnote marker, or a non-numeric type or blank."""
    return (_is_footnote_marker(display_val)
            or not (_is_numeric_type(xbrltype) and (display_val or '').strip()))


def _equity_cell_settled(emit, page: SimpleNamespace, column: Optional[int], display_val: str,
                         viewer_num: Optional[float], xbrl_concept: str) -> bool:
    """Emit the outcome of an equity cell that cannot be compared at all; True when emitted.

    An unreadable value, a cell under no column, a statement with member
    header rows (not comparable), or a concept with no facts (missing).
    Part of ``_judge_equity_cell``.
    """
    if viewer_num is None:
        emit(NOT_COMPARABLE, reason=f"value {display_val!r} cannot be read as a number")
        return True
    if column is None or column >= len(page.column_dims):
        emit(NOT_COMPARABLE, reason="cell is under no column")
        return True
    if page.member_header_rows:
        emit(NOT_COMPARABLE, reason="member header rows on a statement of equity are not read")
        return True
    if page.index.period_types.get(xbrl_concept) is None:
        emit(MISSING, reason="no XBRL fact for this concept")
        return True
    return False


def _equity_cell_context(emit, page: SimpleNamespace, entry: dict, column: int, xbrl_concept: str):
    """An equity cell's ``(period keys, column dims, row dims)``, or None after emitting why it has none.

    The row's period (``_equity_period_of``) and the column's members must
    both be known. An instant row inside a movement may show its opening or
    its closing instant: it keeps only the filed one, and is not comparable
    when both are filed. Part of ``_judge_equity_cell``.
    """
    index = page.index
    period_keys, period_reason, row_dims = _equity_period_of(entry, page.columns, page.periods)
    if period_keys is None:
        emit(NOT_COMPARABLE, reason=period_reason)
        return None
    dims, dims_reason = page.column_dims[column]
    if dims is None:
        emit(NOT_COMPARABLE, reason=dims_reason)
        return None
    if len(period_keys) > 1:
        filed = [k for k in period_keys if index.facts.get((xbrl_concept, k, dims | row_dims))]
        if len(filed) > 1:
            emit(NOT_COMPARABLE, reason=(
                f"an instant row inside a movement shows its opening or its closing balance and facts "
                f"exist for both ({', '.join(filed)}); the page does not say which"))
            return None
        period_keys = filed or period_keys
    return period_keys, dims, row_dims


def _emit_unextracted_cells(results: ComparisonResults, vr, cr, other_cells) -> None:
    """Emit each numeric cell the extractor put in no row as not comparable, saying why."""
    for cell in other_cells:
        header = (cr.period_headers[cell.column]
                  if cell.column is not None and cell.column < len(cr.period_headers) else '')
        what = (f"cell is not extracted (row class {cell.row_class!r}"
                + (", no concept link" if not cell.concept_id else "")
                + (", under no column" if cell.column is None else "") + ")")
        _emit(results, dict(concept_id=_normalize_concept_id(cell.concept_id) if cell.concept_id else '',
                            label=cell.label, period=header, viewer_value=parse_numeric(cell.value),
                            report=vr.short_name),
              NOT_COMPARABLE, reason=what)


_FOOTNOTE_MARKER_RE = re.compile(r'^\s*\[\d+\](?:\s*,?\s*\[\d+\])*\s*$')


def _is_footnote_marker(display: Optional[str]) -> bool:
    """The text is only footnote references (``[1]``, ``[1],[2]``): the renderer's footnote cell.

    EdgarRenderer prints a fact's footnote references in a cell of their own
    (class ``fn`` beside the value, or ``th`` for a row-level footnote), and
    the extractor maps that cell to the value's column. It holds no value,
    so it is not a cell of the statement. In 6 fresh-sample filings every
    one of 1,709 such cells was an ``fn`` or ``th`` cell, none a value cell.
    """
    return bool(display) and bool(_FOOTNOTE_MARKER_RE.match(display))


def _read_number(display: str, unit_label: Optional[str]) -> Optional[float]:
    """A cell's number; also reads one prefixed with the symbol its page declares for the unit.

    ``parse_numeric`` strips only ISO codes and currency-sign symbols. A page
    whose unit is ``ZAR (R)`` prints ``R 2,688.6``; the declared symbol, and
    only it, followed by a space, is stripped here.
    """
    number = parse_numeric(display)
    if number is not None or not display:
        return number
    symbol = unit_symbol(unit_label)
    if not symbol:
        return None
    match = re.match(r'^(\(?)\s*' + re.escape(symbol) + r'\s+(?=[\d(.-])', display.strip())
    if not match:
        return None
    return parse_numeric(match.group(1) + display.strip()[match.end():])


def _judge_cell(emit, index: '_FactIndex', names: _Names, xbrl_concept: str, period_keys: List[str],
                dims: Dims, xbrltype: str, display_val: str, viewer_num: float, cr,
                column_unit: Optional[str], currency_scaling: int, tolerance: Optional[float],
                sign: Tuple[Optional[bool], Optional[str], Optional[str]] = (None, None, None),
                unit_scales: Optional[Dict[str, Tuple[Optional[int], Optional[str]]]] = None) -> None:
    """Compare one cell with the fact for its concept, period keys and dimensions, and emit the outcome.

    ``sign`` is ``(negated, role, reason)`` from ``_row_sign``: the page
    must show the fact negated when its row's label role negates and as
    filed otherwise. When the role is not known (``negated`` None), a cell
    that agrees in magnitude is a match flagged ``sign_only`` (its sign is
    not verified) with ``reason``.

    ``period_keys`` are tried in order; the first with facts in ``dims`` is
    the cell's. The unit, duplicate, scale and tolerance rules then decide
    between matched and mismatched.
    """
    from edgar.xbrl.xbrl import XBRL

    candidates, used_key = _cell_candidates(index, xbrl_concept, period_keys, dims)
    if not candidates:
        _emit_no_fact(emit, index, names, xbrl_concept, period_keys, dims)
        return
    candidates = _candidates_in_cell_unit(emit, candidates, column_unit, cr)
    if candidates is None:
        return

    chosen = XBRL._select_most_precise_fact(candidates)
    note = _inconsistency(chosen, candidates)

    compare = partial(_compare_cell_to_fact, xbrltype=xbrltype, cr=cr, column_unit=column_unit,
                      currency_scaling=currency_scaling, unit_scales=unit_scales, display_val=display_val,
                      viewer_num=viewer_num, negated=sign[0], tolerance=tolerance)

    def paired(fact) -> dict:
        return dict(xbrl_period_key=used_key,
                    xbrl_dimensions={names.show(axis): names.show(member) for axis, member in sorted(dims)},
                    xbrl_unit=fact.unit_ref, label_role=sign[1], negated=sign[0])

    def sign_reason(unverified: bool) -> Optional[str]:
        return f"sign not verified: {sign[2]}" if unverified else None

    outcome, xbrl_display, diff, sign_only = compare(chosen)
    if outcome is None:
        emit(NOT_COMPARABLE, reason=xbrl_display, note=note)
        return
    if outcome == MISMATCHED and note is None and len(candidates) > 1:
        # Duplicates where each less precise copy is the most precise value
        # rounded to that copy's own decimals (``_is_rounding_of``): the page may
        # print a less precise copy (Bilibili's 10-K, 0001193125-25-061847,
        # prints (27,661,500) for RetainedEarningsUnappropriated, filed at
        # decimals -3 as -27,661,459,000 and at -5 as -27,661,500,000; which
        # copy the renderer prints could not be established from its source).
        # A disagreeing duplicate never gets here: ``note`` is set.
        if _emit_less_precise_match(emit, candidates, chosen, compare, paired, sign_reason):
            return
    emit(outcome, xbrl_display, diff, note=note, sign_only=sign_only, paired=paired(chosen),
         reason=sign_reason(sign_only))


def _compare_cell_to_fact(fact, xbrltype: str, cr, column_unit: Optional[str], currency_scaling: int,
                          unit_scales, display_val: str, viewer_num: float, negated: Optional[bool],
                          tolerance: Optional[float]):
    """``(outcome, xbrl display, difference, sign only)`` for the cell against ``fact`` (part of ``_judge_cell``).

    The outcome is None, with the scale's reason in place of the display,
    when the fact's scale on the page cannot be told.
    """
    scaling, scale_reason = _cell_scale(fact, xbrltype, cr, column_unit, currency_scaling, unit_scales)
    if scaling is None:
        return None, scale_reason, None, False
    xbrl_display = fact.numeric_value / scaling if scaling else fact.numeric_value
    if 'percentItemType' in xbrltype and '%' in display_val:
        xbrl_display *= 100  # the page shows the percent-type value as a percentage
    expected = -xbrl_display if negated else xbrl_display  # the renderer never negates zero
    diff = viewer_num - expected
    cell_tolerance = (_display_tolerance(display_val, viewer_num, xbrl_display)
                      if tolerance is None else tolerance)
    if negated is not None:
        # The row's label role is known: the page must agree in sign too.
        return (MATCHED if abs(diff) <= cell_tolerance else MISMATCHED), xbrl_display, diff, False
    # Role unknown: the magnitude is checked, the sign is not verified.
    magnitude = abs(abs(viewer_num) - abs(xbrl_display)) <= cell_tolerance
    zero = magnitude and abs(xbrl_display) <= cell_tolerance
    return (MATCHED if magnitude else MISMATCHED), xbrl_display, diff, magnitude and not zero


def _cell_candidates(index: '_FactIndex', xbrl_concept: str, period_keys: List[str],
                     dims: Dims) -> Tuple[List[SimpleNamespace], Optional[str]]:
    """The facts for the first of ``period_keys`` that has any in ``dims``, and that key (part of ``_judge_cell``)."""
    candidates: List[SimpleNamespace] = []
    used_key = None
    for period_key in period_keys:
        candidates = index.facts.get((xbrl_concept, period_key, dims), [])
        if candidates:
            used_key = period_key
            break
    return candidates, used_key


def _emit_no_fact(emit, index: '_FactIndex', names: _Names, xbrl_concept: str, period_keys: List[str],
                  dims: Dims) -> None:
    """Emit a cell with no fact in its context: not comparable when wider contexts have one, else missing."""
    wider = index.wider_context_reason(xbrl_concept, dims, period_keys)
    if wider:
        emit(NOT_COMPARABLE, reason=wider)
    else:
        emit(MISSING, reason=(
            f"no fact for {' or '.join(period_keys)}"
            + (f" with {names.show_dims(dims)}" if dims else " without dimensions")))


def _candidates_in_cell_unit(emit, candidates: List[SimpleNamespace], column_unit: Optional[str],
                             cr) -> Optional[List[SimpleNamespace]]:
    """The candidates in the currency the column (or the report) names.

    Returns None after emitting the outcome when the unit rules settle the
    cell: no fact in the named currency (missing), several currencies and
    none named, or several units with no currency to choose (not
    comparable). Part of ``_judge_cell``.
    """
    candidates = _candidates_in_named_currency(emit, candidates, column_unit, cr)
    if candidates is None:
        return None
    units = {c.unit_ref for c in candidates}
    if len(units) > 1 and any(not c.currency for c in candidates):
        emit(NOT_COMPARABLE, reason=(
            f"facts in units {sorted(u or '?' for u in units)} and no currency to tell "
            "which unit this cell shows"))
        return None
    return candidates


def _candidates_in_named_currency(emit, candidates: List[SimpleNamespace], column_unit: Optional[str],
                                  cr) -> Optional[List[SimpleNamespace]]:
    """The candidates in the currency the column (or the report) names, or None after emitting why not."""
    # Unit: the currency the column (or the report) names.
    code = unit_code(column_unit or cr.header_unit)
    currencies = {c.currency for c in candidates if c.currency}
    if currencies:
        if code:
            candidates = [c for c in candidates if c.currency == code]
            if not candidates:
                emit(MISSING, reason=f"no fact in {code} (facts in {sorted(currencies)})")
                return None
        elif len(currencies) > 1:
            emit(NOT_COMPARABLE, reason=(
                f"facts in {sorted(currencies)} and the page names no unit for this column"))
            return None
    return candidates


def _emit_less_precise_match(emit, candidates, chosen, compare, paired, sign_reason) -> bool:
    """Emit a match against a less precise duplicate the page shows, if one matches; True when emitted.

    Part of ``_judge_cell``; ``compare``, ``paired`` and ``sign_reason`` are its helpers.
    """
    for other in candidates:
        if other is chosen or other.numeric_value == chosen.numeric_value:
            continue
        other_outcome, other_display, other_diff, other_sign = compare(other)
        if other_outcome == MATCHED:
            emit(MATCHED, other_display, other_diff, sign_only=other_sign, paired=paired(other),
                 reason=sign_reason(other_sign), note=(
                f"the page shows a less precise duplicate: {other.numeric_value:.15g} "
                f"(decimals={other.decimals}); the most precise is {chosen.numeric_value:.15g} "
                f"(decimals={chosen.decimals}), and the less precise one is it rounded to its decimals"))
            return True
    return False


def compare_viewer_to_xbrl(viewer: 'FilingViewer', xbrl: 'XBRL',
                           tolerance: Optional[float] = None) -> ComparisonResults:
    """
    Compare viewer (R*.htm) values against XBRL facts.

    Every numeric cell of the viewer's financial statements ends in exactly
    one outcome. Each is matched to the one XBRL fact it shows:

    - **Period** is the column's: the instant for a date column; for an
      "N Months Ended" column, the concept's own duration that ends on the
      date and that the SEC renderer would head with that month count
      (``_rendered_months``); a period that renders with another count never
      pairs, and two qualifying periods whose facts disagree are not
      comparable. An instant
      concept in a duration column (cash at beginning / end of period) is
      the opening balance (instant before the period starts) or the closing
      balance (instant at its end), decided as the renderer does by the
      presentation arc's period-start label (see ``_balance_role``).
    - **Dimensions** are exactly the member context the page states: none for
      rows above any member header, the header's ``Axis=Member`` for rows
      below it. Axes and members compare by namespace and local name (the
      filer's prefix for a namespace does not matter; one local name in two
      namespaces never matches; a prefix the filing binds to two namespaces
      is compared as written, on both sides). When a row under a member header has no
      fact with exactly those dimensions but facts for the concept and
      period carry them plus other dimensions, the page has not identified
      the context: the cell is not comparable, and such a fact is never
      taken as the cell. A plain row claims the undimensioned fact; with
      only dimensioned facts it is missing.
    - **Unit** is the column's currency when the page names one. Facts in
      several units with no currency to tell them apart are not comparable.
    - **Duplicates** in that unit are resolved with the rule statements use
      (``XBRL._select_most_precise_fact``). A less precise duplicate agrees
      only when it is the most precise value rounded to its own decimals
      (``_is_rounding_of``); otherwise the duplicates disagree, the chosen
      fact is still compared and ``note`` records the disagreement. When
      they agree and the page prints a less precise copy, the cell matches
      that copy and ``note`` says so.
    - **Scale** follows the fact's unit: a currency amount is divided by
      ``ViewerReport.currency_scaling`` (the scale the page declares; per
      column when the page declares currencies at different scales), share
      counts by the page's shares statement; per-share, pure, percent and
      other units are not scaled. When a declared symbol is shared by more
      than one currency on the statement (``$`` for CAD and USD), each
      unit's scale is the renderer's own rule (``_shared_symbol_scales``),
      and a cell is ``not_comparable`` when that rule cannot settle it. A
      percent-type fact is compared x100 when the cell shows it as a
      percentage (``8.25%``).
    - **Typed dimensions** compare by value with leading and trailing
      whitespace removed (the library stores the instance's value
      stripped); inner whitespace is part of the value.
    - **Sign** is the renderer's: a row whose presentation arc has a
      negated label role shows the fact negated (zero and nil are never
      negated), every other row shows it as filed, and the page must agree
      in sign as well as magnitude. Arcs are read from the role's network as
      filed (``PresentationTree.relationships``), which keeps a second arc
      to a concept under the same parent. When the row's arc cannot be
      identified, or the page shows more rows of a concept than the arcs
      visible for it
      (the concept is presented on arcs that differ in negation and neither
      the label text nor the row order tells which this row is), or the
      library's and the renderer's negated-role tests disagree on the role,
      a cell that agrees in magnitude is ``matched`` with ``sign_only``
      (sign unverified) and ``reason`` says why.
    - **Tolerance** is half a unit in the last digit the cell displays
      (``164,993`` -> 0.5; ``-0.42`` -> 0.005), unless ``tolerance`` is given.

    A statement of changes in equity (member columns, dated balance rows)
    is read as the renderer lays it out (see the notes above
    ``_EquityColumns``): a column's member is the one whose label, under
    its presentation arc's preferred label, the heading prints ("Total" is
    every axis default); columns that several combinations could print are
    told apart by the renderer's column order when exactly as many of
    them have facts, and a blank heading names nothing. A balance row is
    the instant it is dated with, whatever facts exist; any other row is
    the period block the page's row order puts it in (blocks come from
    the facts, nil ones included, and from the page's own balance rows),
    and must be the only possible one (``_place_rows``); an instant row
    inside a movement shows its opening or closing instant and is compared
    only when one of the two is filed. Otherwise the cell is not
    comparable, with a reason. Unit, duplicate, scale and tolerance rules
    are those above.

    Footnote cells (``[1]`` beside a value) and extensible-list cells are
    not numeric cells. A compared cell also reports the fact it was paired
    with: ``xbrl_period_key``, ``xbrl_dimensions`` and ``xbrl_unit``.

    A cell lands in one of four outcomes (``ComparisonResult.status``):
    ``matched`` and ``mismatched`` when a fact was identified, ``missing``
    when there is no fact for the cell's concept and period under its
    dimensions (or, below a member header, any extension of them), and
    ``not_comparable`` when the
    harness cannot tell which fact the cell shows (a member column whose
    period the page does not give, an unreadable value, an undecidable
    balance); ``reason`` says why.
    ``match_rate`` counts only matched and mismatched cells; ``coverage``
    is their share of all numeric cells, including cells the extractor does
    not put in a row. A match up to sign only is marked ``sign_only``
    (counted by ``sign_only_matches``); a compared cell whose duplicate
    facts disagree carries a ``note`` (counted by ``noted``). Statement
    pages that could not be read are listed in ``unread_statements``.

    Args:
        viewer: FilingViewer with parsed R*.htm data
        xbrl: XBRL object from filing.xbrl()
        tolerance: Maximum allowed difference in display units. None (the
            default) uses half a unit in each cell's last displayed digit.

    Returns:
        ComparisonResults with per-cell outcomes
    """
    results = ComparisonResults()
    metalinks = viewer._metalinks
    names = _Names(xbrl, metalinks)
    index = _FactIndex(xbrl, names)

    for vr in viewer.financial_statements:
        _compare_statement(results, vr, xbrl, index, names, metalinks, tolerance)

    scales = set(results.scaling_factors.values())
    results.scaling_factor = scales.pop() if len(scales) == 1 else (None if scales else 1)
    return results


def _compare_statement(results: ComparisonResults, vr, xbrl, index: '_FactIndex', names: _Names,
                       metalinks, tolerance: Optional[float]) -> None:
    """Compare every numeric cell of one statement page (part of ``compare_viewer_to_xbrl``).

    A page with no concept report is listed as unread; a statement of
    equity goes to ``_compare_equity_statement``; any other page is read
    row by row, each row in the member context its member header gives.
    """
    cr = vr.concept_report
    if cr is None:
        results.unread_statements.append(vr.short_name)
        return

    currency_scaling = vr.currency_scaling
    results.scaling_factors[vr.short_name] = currency_scaling
    rows = cr.rows
    cell_columns = cr.row_cell_columns if len(cr.row_cell_columns) == len(rows) else None
    unit_scales = _shared_symbol_scales(cr, index, metalinks, xbrl, getattr(vr, 'role', ''))
    if _is_equity_layout(cr):
        _compare_equity_statement(results, vr, cr, xbrl, index, names, metalinks, tolerance,
                                  currency_scaling, unit_scales)
        return
    references = _presentation_references(xbrl, getattr(vr, 'role', ''))
    row_contexts = _row_contexts(rows, names, index)
    occurrences = _row_occurrences(rows, row_contexts)
    page = SimpleNamespace(results=results, vr=vr, cr=cr, xbrl=xbrl, index=index, names=names,
                           metalinks=metalinks, tolerance=tolerance, currency_scaling=currency_scaling,
                           unit_scales=unit_scales, references=references, cell_columns=cell_columns)
    seen: Counter = Counter()

    for i, crow in enumerate(rows):
        if not _is_data_row(crow):
            continue
        occurrence_key = (row_contexts[i], crow.concept_id)
        occurrence = seen[occurrence_key]
        seen[occurrence_key] += 1
        _compare_row(page, i, crow, row_contexts[i], occurrence, occurrences[occurrence_key])

    _emit_page_unextracted_cells(results, vr, cr)


def _row_contexts(rows, names: _Names, index: '_FactIndex') -> List[Tuple[Optional[Dims], Optional[str]]]:
    """Member context of every row: a member header (rh row) puts the rows below it in that member."""
    # Member context of every row: a member header (rh row) puts the rows
    # below it in that member, up to the next member header.
    row_contexts: List[Tuple[Optional[Dims], Optional[str]]] = []
    current: Tuple[Optional[Dims], Optional[str]] = (frozenset(), None)
    for crow in rows:
        if crow.is_header and crow.is_dimensional:
            current = _member_header_dims(crow, names, index.typed_values)
        row_contexts.append(current)
    return row_contexts


def _is_data_row(crow) -> bool:
    """A row that carries values: not abstract, not a member header, not dimensional."""
    return not (crow.is_abstract or crow.is_dimensional or crow.is_header) and bool(crow.values)


def _row_occurrences(rows, row_contexts) -> Counter:
    """How many data rows each (member context, concept) has on the page."""
    occurrences: Counter = Counter()
    for crow, context in zip(rows, row_contexts, strict=True):
        if _is_data_row(crow):
            occurrences[(context, crow.concept_id)] += 1
    return occurrences


def _compare_row(page: SimpleNamespace, i: int, crow, row_context, occurrence: int, occurrence_count: int) -> None:
    """Compare each cell of one data row (part of ``_compare_statement``).

    ``occurrence`` is which of the ``occurrence_count`` rows of the concept
    in this member context the row is.
    """
    dims, context_reason = row_context
    xbrl_concept = _normalize_concept_id(crow.concept_id)
    tag = page.metalinks.get_tag(crow.concept_id)
    xbrltype = (tag.xbrltype if tag else '') or ''
    row = SimpleNamespace(i=i, crow=crow, dims=dims, context_reason=context_reason, xbrl_concept=xbrl_concept,
                          tag=tag, xbrltype=xbrltype, occurrence=occurrence, occurrence_count=occurrence_count)
    for value_key, display_val in crow.values.items():
        _compare_row_cell(page, row, value_key, display_val)


def _cell_column(cr, cell_columns, i: int, value_key: str) -> Tuple[str, Optional[str]]:
    """A cell's column header and the unit its column names (part of ``_compare_row_cell``)."""
    column_unit = None
    if cell_columns is not None and value_key in cell_columns[i]:
        column = cell_columns[i][value_key]
        period_header = cr.period_headers[column]
        if column < len(cr.column_units):
            column_unit = cr.column_units[column]
    else:
        period_header = _DUPLICATE_KEY_SUFFIX_RE.sub('', value_key)
    return period_header, column_unit


def _compare_row_cell(page: SimpleNamespace, row: SimpleNamespace, value_key: str, display_val: str) -> None:
    """Compare one cell of a data row and emit its outcome (part of ``_compare_row``)."""
    cr, crow, xbrl_concept, xbrltype = page.cr, row.crow, row.xbrl_concept, row.xbrltype
    period_header, column_unit = _cell_column(cr, page.cell_columns, row.i, value_key)

    viewer_num = _read_number(display_val, column_unit or cr.header_unit)
    if viewer_num is None and (_is_footnote_marker(display_val)
                               or not (_is_numeric_type(xbrltype) and (display_val or '').strip())):
        return  # not a numeric cell
    emit = partial(_emit, page.results, dict(
        concept_id=xbrl_concept, label=crow.label, period=value_key,
        viewer_value=viewer_num, report=page.vr.short_name))
    if viewer_num is None:
        emit(NOT_COMPARABLE, reason=f"value {display_val!r} cannot be read as a number")
        return

    period_info = _column_period(emit, period_header)
    if period_info is None:
        return
    period_keys = _cell_period_keys(emit, page, row, period_info)
    if period_keys is None:
        return

    _judge_cell(emit, page.index, page.names, xbrl_concept, period_keys, row.dims, xbrltype,
                display_val, viewer_num, cr, column_unit, page.currency_scaling, page.tolerance,
                sign=_row_sign(page.xbrl, row.tag, crow, page.references, row.occurrence,
                               row.occurrence_count),
                unit_scales=page.unit_scales)


def _column_period(emit, period_header: str) -> Optional[dict]:
    """The period a column header states, or None after emitting why the header gives none.

    A header with no period, or one that names a member or unit by label
    as well as its period, is not comparable. Part of ``_compare_row_cell``.
    """
    period_info = _parse_viewer_period(period_header)
    if not period_info:
        if _DATE_RE.search(period_header):
            emit(NOT_COMPARABLE, reason=(
                f"column header {period_header!r} names a member or unit by label "
                "before its period"))
        else:
            emit(NOT_COMPARABLE, reason=(
                f"column {period_header!r} states no period (a member column, as in "
                "an equity statement); the page does not give each row's period"))
        return None

    header_match = _DATE_RE.match(period_header)
    if header_match.end() < len(period_header.rstrip()):
        emit(NOT_COMPARABLE, reason=(
            f"column header {period_header!r} carries more than a period "
            "(a member or unit named only by label)"))
        return None
    return period_info


def _cell_period_keys(emit, page: SimpleNamespace, row: SimpleNamespace, period_info: dict
                      ) -> Optional[List[str]]:
    """The period keys a cell may show, or None after emitting why it has none.

    An instant column shows an instant concept at its date; a duration
    column shows a duration concept's own period (``_FactIndex.concept_period``)
    or an instant concept's opening or closing balance (``_balance_role``).
    Part of ``_compare_row_cell``.
    """
    index, xbrl_concept, dims = page.index, row.xbrl_concept, row.dims
    # Period keys the cell may show.
    period_type = index.period_types.get(xbrl_concept)
    if period_type is None:
        emit(MISSING, reason="no XBRL fact for this concept")
        return None
    if dims is None:
        emit(NOT_COMPARABLE, reason=row.context_reason)
        return None
    end_date = period_info['end']
    months = period_info['months']
    if months is None:
        if period_type != 'instant':
            emit(NOT_COMPARABLE, reason="duration concept under an instant column header")
            return None
        return [f'instant_{end_date}']
    if period_type == 'instant':
        return _balance_period_keys(emit, page, row, end_date, months)
    return _duration_period_keys(emit, index, xbrl_concept, dims, end_date, months)


def _balance_period_keys(emit, page: SimpleNamespace, row: SimpleNamespace, end_date: str,
                         months: int) -> Optional[List[str]]:
    """An instant concept in a duration column: its opening or closing balance's keys, or None after emitting."""
    index, xbrl_concept, dims = page.index, row.xbrl_concept, row.dims
    role, role_reason = _balance_role(row.crow, row.tag, row.occurrence, row.occurrence_count,
                                      page.references.get(row.crow.concept_id))
    if role is None:
        emit(NOT_COMPARABLE, reason=role_reason)
        return None
    if role == 'opening':
        starts = index.column_starts(end_date, months)
        if not starts:
            emit(MISSING, reason=(f"no period in the filing renders as {months} months "
                                  f"ending {end_date}"))
            return None
        # The opening balance of each period that renders with
        # this heading; they must agree, or the page cannot say
        # which one it shows.
        openings = {}
        for start in starts:
            for key in _opening_instant_keys(start):
                if index.facts.get((xbrl_concept, key, dims)):
                    openings[key] = index.value_signature(xbrl_concept, key, dims)
                    break
        if len(set(openings.values())) > 1:
            emit(NOT_COMPARABLE, reason=(
                f"periods that render as {months} months ending {end_date} start on "
                f"different dates whose opening balances disagree: {', '.join(sorted(openings))}"))
            return None
        return (sorted(openings)[:1]
                or [key for start in starts for key in _opening_instant_keys(start)])
    return [f'instant_{end_date}']


def _duration_period_keys(emit, index: '_FactIndex', xbrl_concept: str, dims: Dims, end_date: str,
                          months: int) -> Optional[List[str]]:
    """A duration concept's own period for the column, or None after emitting why there is none."""
    duration_key, duration_reason = index.concept_period(xbrl_concept, dims, end_date, months)
    if duration_key is None:
        if duration_reason.startswith('no '):
            wider = index.wider_context_reason(
                xbrl_concept, dims, index.rendered_period_keys(end_date, months))
            if wider:
                emit(NOT_COMPARABLE, reason=wider)
            else:
                emit(MISSING, reason=duration_reason)
        else:
            emit(NOT_COMPARABLE, reason=duration_reason)
        return None
    return [duration_key]


def _emit_page_unextracted_cells(results: ComparisonResults, vr, cr) -> None:
    """Emit each numeric cell the extractor put in no row as not comparable, saying why.

    Equity-statement "Balance ... at <date>" rows of class rc, rows with no
    concept link, cells under no column: counted, never compared.
    """
    # Numeric cells the extractor did not put in any row (equity-statement
    # "Balance ... at <date>" rows of class rc, rows with no concept link,
    # cells under no column): counted, never compared.
    for cell in getattr(cr, 'unextracted_cells', None) or []:
        header = (cr.period_headers[cell.column]
                  if cell.column is not None and cell.column < len(cr.period_headers) else '')
        what = (f"row class {cell.row_class!r} is not extracted (an equity-statement balance row)"
                if cell.row_class == 'rc' else
                f"cell is not extracted (row class {cell.row_class!r}"
                + (", no concept link" if not cell.concept_id else "")
                + (", under no column" if cell.column is None else "") + ")")
        _emit(results, dict(concept_id=_normalize_concept_id(cell.concept_id) if cell.concept_id else '',
                            label=cell.label, period=header, viewer_value=parse_numeric(cell.value),
                            report=vr.short_name),
              NOT_COMPARABLE, reason=what)
