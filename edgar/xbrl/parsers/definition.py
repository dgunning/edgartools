"""
Definition parser for XBRL documents.

This module handles parsing of XBRL definition linkbases and building
dimensional structures like tables, axes, and domains.

The dimensional model is ROLE-SCOPED. A concept means different things in
different extended link roles: the same domain can carry a two-way breakdown on
the income statement and a five-way one in a revenue note, and the same axis can
be attached to a different domain in each. Tables were always kept per role;
axes and domains are now kept per role beside them, and `axes` / `domains` are
merged views over that store for callers that predate the distinction.

Relationships are accumulated across every `parse_definition_content` call and
the whole model is rebuilt from the accumulated set each time. That is what
makes `xbrldt:targetRole` resolvable: the target role may be declared in a link,
or a file, that has not been read yet.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from edgar.xbrl.core import STANDARD_LABEL, extract_element_id
from edgar.xbrl.models import Axis, Domain, ElementCatalog, Table, XBRLProcessingError

from .base import BaseParser
from .relationships import arc_candidate, candidate_key, effective_relationships

# XBRL Dimensions arcrole URIs
HYPERCUBE_DIMENSION = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
DIMENSION_DOMAIN = "http://xbrl.org/int/dim/arcrole/dimension-domain"
DIMENSION_DEFAULT = "http://xbrl.org/int/dim/arcrole/dimension-default"
DOMAIN_MEMBER = "http://xbrl.org/int/dim/arcrole/domain-member"
ALL = "http://xbrl.org/int/dim/arcrole/all"

XLINK = "{http://www.w3.org/1999/xlink}"
LINKBASE = "{http://www.xbrl.org/2003/linkbase}"
XBRLDT = "{http://xbrl.org/2005/xbrldt}"


class DefinitionParser(BaseParser):
    """Parser for XBRL definition linkbases."""

    def __init__(self, definition_roles: Dict[str, Dict[str, Any]],
                 tables: Dict[str, List[Table]],
                 axes: Dict[str, Axis],
                 domains: Dict[str, Domain],
                 element_catalog: Dict[str, ElementCatalog],
                 role_types: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize definition parser with data structure references.

        Args:
            definition_roles: Reference to definition roles dictionary
            tables: Reference to tables dictionary
            axes: Reference to the merged axes view (keyed on element ID)
            domains: Reference to the merged domains view (keyed on element ID)
            element_catalog: Reference to element catalog dictionary
            role_types: Shared dict of role type definitions from schema (human-readable definitions)
        """
        super().__init__()

        # Store references to data structures
        self.definition_roles = definition_roles
        self.tables = tables
        self.axes = axes
        self.domains = domains
        self.element_catalog = element_catalog
        self.role_types = role_types if role_types is not None else {}

        # The dimensional model proper: role -> element ID -> axis/domain. Owned
        # here rather than passed in, because `axes` and `domains` above are
        # merged views derived from it.
        self.axes_by_role: Dict[str, Dict[str, Axis]] = {}
        self.domains_by_role: Dict[str, Dict[str, Domain]] = {}

        # Every arc seen so far, prohibiting ones included, grouped by the role
        # that declared it.
        self._candidates_by_role: Dict[str, List[Dict[str, Any]]] = {}
        self._seen_arcs: set = set()

        # The effective relationships among them (XBRL 2.1 section
        # 3.5.3.9.7.5). The dimensional model is rebuilt from this after each
        # parse.
        self._relationships_by_role: Dict[str, List[Dict[str, Any]]] = {}

        # axis -> every default member declared for it in any role. A
        # dimension-default arc is global, not scoped to its extended link.
        self._defaults_by_axis: Dict[str, set] = {}

        # Dimension QNames the instance carries as xbrldi:typedMember. The
        # coordinator replaces this with the instance parser's own set.
        self.observed_typed_dimensions: Set[str] = set()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_definition(self, file_path: Union[str, Path]) -> None:
        """Parse definition linkbase file and build dimensional structures."""
        try:
            content = Path(file_path).read_text()
            self.parse_definition_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing definition file {file_path}: {str(e)}") from e

    def parse_definition_content(self, content: str) -> None:
        """Parse definition linkbase content and build dimensional structures."""
        try:
            root = self._safe_parse_xml(content)

            for link in root.findall(f'.//{LINKBASE}definitionLink'):
                role = link.get(f'{XLINK}role')
                if not role:
                    continue

                self._record_role(role)
                self._collect_relationships(link, role)

            # Rebuild from everything seen so far, not just this file: an arc's
            # xbrldt:targetRole may name a role declared in another link or
            # another file, in either order.
            self._rebuild_dimensional_structures()

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing definition content: {str(e)}") from e

    def _record_role(self, role: str) -> None:
        """Store the human-readable identity of an extended link role."""
        self.definition_roles[role] = self._role_record(role, self.role_types)

    def _collect_relationships(self, link, role: str) -> None:
        """Extract every definition arc in one extended link into the store."""
        candidates = self._candidates_by_role.setdefault(role, [])

        # Resolve every xlink:label once. Searching the link per arc is
        # quadratic, and an extended link can carry hundreds of each.
        labels = {}
        for element in link.iter():
            label = element.get(f'{XLINK}label')
            if label is not None:
                labels.setdefault(label, element)

        for arc in link.findall(f'.//{LINKBASE}definitionArc'):
            from_ref = arc.get(f'{XLINK}from')
            to_ref = arc.get(f'{XLINK}to')
            arcrole = arc.get(f'{XLINK}arcrole')
            if not from_ref or not to_ref or not arcrole:
                continue

            from_loc = labels.get(from_ref)
            to_loc = labels.get(to_ref)
            if from_loc is None or to_loc is None:
                continue

            from_href = from_loc.get(f'{XLINK}href')
            to_href = to_loc.get(f'{XLINK}href')
            if not from_href or not to_href:
                continue

            from_element = extract_element_id(from_href)
            to_element = extract_element_id(to_href)

            candidate = arc_candidate(arc, role, from_element, to_element, {
                'from_element': from_element,
                'to_element': to_element,
                'order': self._parse_order_attribute(arc),
                'arcrole': arcrole,
                'target_role': arc.get(f'{XBRLDT}targetRole'),
                'closed': arc.get(f'{XBRLDT}closed') in ('true', '1'),
                'context_element': arc.get(f'{XBRLDT}contextElement') or 'segment',
            })

            # Re-reading the same linkbase must not duplicate members
            key = candidate_key(candidate)
            if key in self._seen_arcs:
                continue
            self._seen_arcs.add(key)
            candidates.append(candidate)

    def _resolve_relationships(self) -> None:
        """
        Keep each role's effective relationships, one per arcrole and endpoints.

        Prohibition and overriding come first (XBRL 2.1 section 3.5.3.9.7.5).
        Of two effective relationships that still share an arcrole and both
        endpoints, because an attribute such as order differs, the first is
        kept, as before prohibition was honoured.
        """
        self._relationships_by_role.clear()
        for role, candidates in self._candidates_by_role.items():
            seen = set()
            kept = self._relationships_by_role.setdefault(role, [])
            for rel in effective_relationships(candidates):
                edge = (rel['arcrole'], rel['from_element'], rel['to_element'])
                if edge not in seen:
                    seen.add(edge)
                    kept.append(rel)

    # ------------------------------------------------------------------
    # Building the dimensional model
    # ------------------------------------------------------------------

    def _rebuild_dimensional_structures(self) -> None:
        """Rebuild tables, axes and domains from every relationship seen."""
        self.tables.clear()
        self.axes.clear()
        self.domains.clear()
        self.axes_by_role.clear()
        self.domains_by_role.clear()
        self._resolve_relationships()
        self._index_defaults()

        # Three passes over every role, so that resolving a cross-role hop never
        # depends on which extended link happened to be parsed first.
        for role in self._relationships_by_role:
            self._build_domain_hierarchy(role)
        for role in list(self._relationships_by_role):
            self._follow_member_continuations(role)
        for role in self._relationships_by_role:
            self._build_axes(role)
        for role in self._relationships_by_role:
            self._build_tables(role)

        self._rebuild_merged_views()

    def _index_defaults(self) -> None:
        """Every default member declared for each axis, across all roles."""
        self._defaults_by_axis.clear()
        for relationships in self._relationships_by_role.values():
            for rel in relationships:
                if rel['arcrole'] == DIMENSION_DEFAULT:
                    self._defaults_by_axis.setdefault(rel['from_element'], set()).add(rel['to_element'])

    def _arcs(self, role: str, arcrole: str, from_element: Optional[str] = None) -> List[Dict[str, Any]]:
        """Arcs of one arcrole in one role, in filed order."""
        arcs = [rel for rel in self._relationships_by_role.get(role, [])
                if rel['arcrole'] == arcrole
                and (from_element is None or rel['from_element'] == from_element)]
        return sorted(arcs, key=lambda rel: rel['order'])

    def _build_domain_hierarchy(self, role: str) -> None:
        """
        Turn this role's domain-member arcs into domains.

        Every element that parents at least one member becomes a Domain, which
        is what makes a nested member both a member of its parent and a domain
        in its own right — and lets `Domain.parent` be written.
        """
        member_arcs = self._arcs(role, DOMAIN_MEMBER)
        parents = {rel['from_element'] for rel in member_arcs}

        for rel in member_arcs:
            domain = self._domain(role, rel['from_element'])
            if rel['to_element'] not in domain.members:
                domain.members.append(rel['to_element'])

            # A member that is itself a parent records where it hangs from
            if rel['to_element'] in parents:
                self._domain(role, rel['to_element']).parent = rel['from_element']

    def _build_axes(self, role: str) -> None:
        """
        Attach each of this role's axes to its domain and default member.

        The domain may be declared in another extended link, reached through
        the hypercube-dimension arc's `xbrldt:targetRole`. The default may be
        declared in any extended link at all: a dimension-default arc is
        global (see `_global_default`).
        """
        for rel in self._arcs(role, HYPERCUBE_DIMENSION):
            axis_id = rel['to_element']
            axis = self._axis(role, axis_id)
            domain_role = rel['target_role'] or role

            self._resolve_axis_domain(role, domain_role, axis)

    def _resolve_axis_domain(self, role: str, domain_role: str, axis: Axis) -> None:
        """Follow dimension-domain and dimension-default arcs for one axis."""
        # XBRL Dimensions 1.0 s2.5.3 lets one axis carry SEVERAL domain roots, and
        # a root that parents no member of its own is registered nowhere else: the
        # domain-hierarchy pass only creates elements that parent at least one
        # domain-member arc. Stopping at the first arc therefore dropped such a
        # root from domains_for_role() altogether -- Ellington Financial declares
        # efc_DerivativeMaturityPeriodDomain and the childless efc_Year2038Member
        # on one axis, and only the first was ever visible.
        #
        # axis.domain_id is a single field and still names the FIRST root, so no
        # consumer of it sees a different answer.
        for rel in self._arcs(domain_role, DIMENSION_DOMAIN, axis.element_id):
            if axis.domain_id is None:
                axis.domain_id = rel['to_element']
            member_role = rel['target_role'] or domain_role
            self._copy_domain_into_role(role, member_role, rel['to_element'])

        for rel in self._arcs(domain_role, DIMENSION_DEFAULT, axis.element_id):
            axis.default_member_id = rel['to_element']
            break
        else:
            if axis.default_member_id is None:
                axis.default_member_id = self._global_default(role, axis)

    def _global_default(self, role: str, axis: Axis) -> Optional[str]:
        """
        The axis's default declared in any role, if it applies in `role`.

        A dimension-default relationship is global (XBRL Dimensions 1.0
        section 2.7.1): it holds in every extended link that uses the dimension
        and whose domain contains the default, and `xbrldt:targetRole` plays no
        part. Tesla files `srt_RangeAxis -> srt_RangeMember` in one role and
        uses the axis, with that member as its domain, in 26 others (gh #1725).

        Only a default the DTS declares once is taken: two different defaults
        for one dimension is an invalid DTS, and choosing one would be a guess.
        """
        defaults = self._defaults_by_axis.get(axis.element_id)
        if not defaults or len(defaults) != 1 or axis.domain_id is None:
            return None
        default = next(iter(defaults))
        return default if self._domain_contains(role, axis.domain_id, default) else None

    def _domain_contains(self, role: str, root: str, member: str) -> bool:
        """Whether `member` is `root` or sits anywhere beneath it in `role`."""
        domains = self.domains_by_role.get(role, {})
        pending, seen = [root], set()
        while pending:
            element = pending.pop()
            if element == member:
                return True
            if element in seen:
                continue
            seen.add(element)
            domain = domains.get(element)
            if domain is not None:
                pending.extend(domain.members)
        return False

    def _copy_domain_into_role(self, role: str, source_role: str, domain_id: str) -> None:
        """
        Make a domain declared in `source_role` visible from `role`.

        A cross-role hop means the members live under the role that declared
        them; the caller asking about `role` still needs to see them.
        """
        self._domain(role, domain_id)
        self._import_members(role, source_role, domain_id, set())

    def _import_members(self, role: str, source_role: str, element: str, seen: set) -> None:
        """
        Make everything beneath `element` in `source_role` visible from `role`.

        The whole subtree is copied, not one level: a member that is itself a
        domain keeps its own members after the role change (gh #1752). A
        domain-member arc carrying `xbrldt:targetRole` says the member's own
        children are found in that role (XBRL Dimensions 1.0 section 2.4,
        example 7), so the walk continues there. `seen` stops a cycle.
        """
        key = (source_role, element)
        if key in seen:
            return
        seen.add(key)

        source = self.domains_by_role.get(source_role, {}).get(element)
        if source is None:
            return
        if role != source_role:
            target = self._domain(role, element)
            for member in source.members:
                if member not in target.members:
                    target.members.append(member)
            if target.parent is None:
                target.parent = source.parent

        continuations = {rel['to_element']: rel['target_role']
                         for rel in self._arcs(source_role, DOMAIN_MEMBER, element)
                         if rel['target_role']}
        for member in list(source.members):
            member_role = continuations.get(member, source_role)
            self._import_members(role, member_role, member, seen)
            if member_role == role:
                continue  # the role's own hierarchy already says where it hangs
            nested = self.domains_by_role.get(role, {}).get(member)
            if nested is not None and nested.parent is None:
                nested.parent = element

    def _follow_member_continuations(self, role: str) -> None:
        """
        Pull in the children a `targetRole` domain-member arc points at.

        `_build_domain_hierarchy` reads one role's arcs; a member reached
        through `xbrldt:targetRole` has its children declared in another role,
        so they are imported here, once every role's own hierarchy is built.
        """
        for rel in self._arcs(role, DOMAIN_MEMBER):
            if rel['target_role'] and rel['target_role'] != role:
                self._import_members(role, rel['target_role'], rel['to_element'], set())
                nested = self.domains_by_role.get(role, {}).get(rel['to_element'])
                if nested is not None and nested.parent is None:
                    nested.parent = rel['from_element']

    def _build_tables(self, role: str) -> None:
        """
        Build this role's hypercubes from its `all` arcs.

        The dimensions of a hypercube may be declared in another extended link,
        reached through the `all` arc's `xbrldt:targetRole`.
        """
        tables = []

        for rel in self._arcs(role, ALL):
            hypercube_id = rel['to_element']
            axis_role = rel['target_role'] or role
            axis_ids = [arc['to_element']
                        for arc in self._arcs(axis_role, HYPERCUBE_DIMENSION, hypercube_id)]
            if not axis_ids:
                continue

            # An axis reached across a role hop still belongs to this table, so
            # it is registered under the role that uses it, not only the one
            # that declares it.
            if axis_role != role:
                for axis_id in axis_ids:
                    self._resolve_axis_domain(role, axis_role, self._axis(role, axis_id))

            tables.append(Table(
                element_id=hypercube_id,
                label=self._get_element_label(hypercube_id),
                role_uri=role,
                axes=axis_ids,
                line_items=[rel['from_element']],
                closed=rel['closed'],
                context_element=rel['context_element'],
            ))

        if tables:
            self.tables[role] = tables

    # ------------------------------------------------------------------
    # Role-scoped stores and the merged views over them
    # ------------------------------------------------------------------

    def _axis(self, role: str, element_id: str) -> Axis:
        """Get or create the Axis for one element in one role."""
        axes = self.axes_by_role.setdefault(role, {})
        if element_id not in axes:
            is_typed, typed_domain_ref = self._typed_dimension_info(element_id)
            axes[element_id] = Axis(
                element_id=element_id,
                label=self._get_element_label(element_id),
                role_uri=role,
                is_typed_dimension=is_typed,
                typed_domain_ref=typed_domain_ref,
            )
        return axes[element_id]

    def _domain(self, role: str, element_id: str) -> Domain:
        """Get or create the Domain for one element in one role."""
        domains = self.domains_by_role.setdefault(role, {})
        if element_id not in domains:
            domains[element_id] = Domain(
                element_id=element_id,
                label=self._get_element_label(element_id),
                role_uri=role,
            )
        return domains[element_id]

    def axes_for_role(self, role_uri: str) -> Dict[str, Axis]:
        """The axes declared for one extended link role, keyed on element ID."""
        return self.axes_by_role.get(role_uri, {})

    def domains_for_role(self, role_uri: str) -> Dict[str, Domain]:
        """The domains declared for one extended link role, keyed on element ID."""
        return self.domains_by_role.get(role_uri, {})

    def _rebuild_merged_views(self) -> None:
        """
        Rebuild the flat `axes` / `domains` dicts from the role-scoped stores.

        These predate role scoping and callers still read them, so they keep
        their shape. They are a UNION across roles rather than whichever role
        was parsed last: a superset is a fair answer to a question asked without
        a role, a truncation is not. `role_uri` is left empty to mark an entry
        as merged rather than belonging to any one role.
        """
        for role_axes in self.axes_by_role.values():
            for element_id, axis in role_axes.items():
                merged = self.axes.get(element_id)
                if merged is None:
                    self.axes[element_id] = axis.model_copy(update={'role_uri': ''})
                    continue
                merged.domain_id = merged.domain_id or axis.domain_id
                merged.default_member_id = merged.default_member_id or axis.default_member_id
                merged.is_typed_dimension = merged.is_typed_dimension or axis.is_typed_dimension
                merged.typed_domain_ref = merged.typed_domain_ref or axis.typed_domain_ref

        for role_domains in self.domains_by_role.values():
            for element_id, domain in role_domains.items():
                merged = self.domains.get(element_id)
                if merged is None:
                    self.domains[element_id] = domain.model_copy(
                        deep=True, update={'role_uri': ''})
                    continue
                merged.parent = merged.parent or domain.parent
                for member in domain.members:
                    if member not in merged.members:
                        merged.members.append(member)

    def _typed_dimension_info(self, element_id: str) -> tuple:
        """
        Whether an axis is a typed dimension, and the domain it points at.

        A dimension is typed when its element declaration carries
        xbrldt:typedDomainRef. Reading it from the element catalog is what makes
        `is_typed_dimension=False` an answer rather than an untouched default.

        An axis declared only in an imported taxonomy is not in the catalog at
        all — there is no xs:import traversal (edgartools-0c1q.16.1). The
        instance still settles its kind: only a typed dimension may carry an
        xbrldi:typedMember (XBRL Dimensions 1.0 section 3.1.4.4), so an axis
        used that way is typed, with `typed_domain_ref` left empty because the
        declaration that holds it was never read (gh #1234).
        """
        element = self.element_catalog.get(element_id)
        typed_domain_ref = getattr(element, 'typed_domain_ref', None) if element else None
        if typed_domain_ref:
            return True, typed_domain_ref
        return element_id in self._observed_typed_axis_ids(), ""

    def _observed_typed_axis_ids(self) -> Set[str]:
        """The observed typed dimensions as element IDs (`us-gaap_FooAxis`)."""
        return {qname.replace(':', '_', 1) for qname in self.observed_typed_dimensions}

    def mark_observed_typed_dimensions(self) -> None:
        """
        Mark axes the instance used as typed, after an instance is read.

        The dimensional model may already be built when the instance arrives,
        so the axes it holds are updated in place; a later rebuild reads the
        same evidence through `_typed_dimension_info`.
        """
        typed_ids = self._observed_typed_axis_ids()
        if not typed_ids:
            return
        views = [*self.axes_by_role.values(), self.axes]
        for axes in views:
            for element_id in typed_ids & axes.keys():
                axes[element_id].is_typed_dimension = True

    def _get_element_label(self, element_id: str) -> str:
        """Get the label for an element, falling back to the element ID if not found."""
        if element_id in self.element_catalog and self.element_catalog[element_id].labels:
            # Use standard label if available
            standard_label = self.element_catalog[element_id].labels.get(STANDARD_LABEL)
            if standard_label:
                return standard_label
        return element_id  # Fallback to element ID
