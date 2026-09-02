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
from typing import Any, Dict, List, Optional, Union

from edgar.xbrl.core import STANDARD_LABEL, extract_element_id
from edgar.xbrl.models import Axis, Domain, ElementCatalog, Table, XBRLProcessingError

from .base import BaseParser

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
                 element_catalog: Dict[str, ElementCatalog]):
        """
        Initialize definition parser with data structure references.

        Args:
            definition_roles: Reference to definition roles dictionary
            tables: Reference to tables dictionary
            axes: Reference to the merged axes view (keyed on element ID)
            domains: Reference to the merged domains view (keyed on element ID)
            element_catalog: Reference to element catalog dictionary
        """
        super().__init__()

        # Store references to data structures
        self.definition_roles = definition_roles
        self.tables = tables
        self.axes = axes
        self.domains = domains
        self.element_catalog = element_catalog

        # The dimensional model proper: role -> element ID -> axis/domain. Owned
        # here rather than passed in, because `axes` and `domains` above are
        # merged views derived from it.
        self.axes_by_role: Dict[str, Dict[str, Axis]] = {}
        self.domains_by_role: Dict[str, Dict[str, Domain]] = {}

        # Every relationship seen so far, grouped by the role that declared it.
        # The dimensional model is rebuilt from this after each parse.
        self._relationships_by_role: Dict[str, List[Dict[str, Any]]] = {}
        self._seen_arcs: set = set()

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
        role_id = role.split('/')[-1] if '/' in role else role

        self.definition_roles[role] = {
            'roleUri': role,
            'definition': role_id.replace('_', ' '),
            'roleId': role_id
        }

    def _collect_relationships(self, link, role: str) -> None:
        """Extract every definition arc in one extended link into the store."""
        relationships = self._relationships_by_role.setdefault(role, [])

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

            # Re-reading the same linkbase must not duplicate members
            key = (role, arcrole, from_element, to_element)
            if key in self._seen_arcs:
                continue
            self._seen_arcs.add(key)

            relationships.append({
                'from_element': from_element,
                'to_element': to_element,
                'order': self._parse_order_attribute(arc),
                'arcrole': arcrole,
                'target_role': arc.get(f'{XBRLDT}targetRole'),
                'closed': arc.get(f'{XBRLDT}closed') in ('true', '1'),
                'context_element': arc.get(f'{XBRLDT}contextElement') or 'segment',
            })

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

        # Three passes over every role, so that resolving a cross-role hop never
        # depends on which extended link happened to be parsed first.
        for role in self._relationships_by_role:
            self._build_domain_hierarchy(role)
        for role in self._relationships_by_role:
            self._build_axes(role)
        for role in self._relationships_by_role:
            self._build_tables(role)

        self._rebuild_merged_views()

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

        Both may be declared in another extended link, reached through the
        hypercube-dimension arc's `xbrldt:targetRole`.
        """
        for rel in self._arcs(role, HYPERCUBE_DIMENSION):
            axis_id = rel['to_element']
            axis = self._axis(role, axis_id)
            domain_role = rel['target_role'] or role

            self._resolve_axis_domain(role, domain_role, axis)

    def _resolve_axis_domain(self, role: str, domain_role: str, axis: Axis) -> None:
        """Follow dimension-domain and dimension-default arcs for one axis."""
        for rel in self._arcs(domain_role, DIMENSION_DOMAIN, axis.element_id):
            axis.domain_id = rel['to_element']
            member_role = rel['target_role'] or domain_role
            self._copy_domain_into_role(role, member_role, rel['to_element'])
            break

        for rel in self._arcs(domain_role, DIMENSION_DEFAULT, axis.element_id):
            axis.default_member_id = rel['to_element']
            break

    def _copy_domain_into_role(self, role: str, source_role: str, domain_id: str) -> None:
        """
        Make a domain declared in `source_role` visible from `role`.

        A cross-role hop means the members live under the role that declared
        them; the caller asking about `role` still needs to see them.
        """
        if role == source_role:
            self._domain(role, domain_id)
            return

        source = self.domains_by_role.get(source_role, {}).get(domain_id)
        target = self._domain(role, domain_id)
        if source is None:
            return

        for member in source.members:
            if member not in target.members:
                target.members.append(member)
        if target.parent is None:
            target.parent = source.parent

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
        all — there is no xs:import traversal — so it still reports False. That
        is the remaining half of gh #1234, tracked as edgartools-0c1q.16.1.
        """
        element = self.element_catalog.get(element_id)
        typed_domain_ref = getattr(element, 'typed_domain_ref', None) if element else None

        return bool(typed_domain_ref), typed_domain_ref or ""

    def _get_element_label(self, element_id: str) -> str:
        """Get the label for an element, falling back to the element ID if not found."""
        if element_id in self.element_catalog and self.element_catalog[element_id].labels:
            # Use standard label if available
            standard_label = self.element_catalog[element_id].labels.get(STANDARD_LABEL)
            if standard_label:
                return standard_label
        return element_id  # Fallback to element ID
