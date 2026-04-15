"""
Navigable knowledge graph of all tagged XBRL concepts in a filing.

Combines MetaLinks.json tag definitions (credit/debit, calculation trees,
FASB documentation) with R*.htm concept-annotated values to create a
unified, searchable graph where every concept is a navigable node.

Usage:
    from edgar.sgml.metalinks import MetaLinks
    from edgar.sgml.concept_extractor import ConceptReport

    graph = ConceptGraph.build(metalinks, concept_reports, report_map)
    concept = graph['Revenue']
    concept.crdr           # 'credit'
    concept.documentation  # FASB definition
    concept.values         # {'Mar. 29, 2025': '$ 95,359', ...}
    concept.children       # [ProductRevenue, ServiceRevenue]
    concept.statements     # ['Income Statement']
"""
from typing import Dict, List, Optional, TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.sgml.concept_extractor import parse_numeric

if TYPE_CHECKING:
    from edgar.sgml.metalinks import MetaLinks, MetaLinksReport, TagDefinition
    from edgar.sgml.concept_extractor import ConceptReport, ConceptRow

__all__ = ['Concept', 'ConceptGraph']


class Concept:
    """
    A navigable concept node in the filing's knowledge graph.

    Wraps a TagDefinition from MetaLinks with values from R*.htm reports,
    providing navigation to related concepts via calculation relationships.
    """

    def __init__(self,
                 tag: 'TagDefinition',
                 graph: 'ConceptGraph'):
        self._tag = tag
        self._graph = graph

    # --- Identity ---

    @property
    def id(self) -> str:
        return self._tag.tag_id

    @property
    def label(self) -> str:
        return self._tag.terse_label or self._tag.label

    @property
    def full_label(self) -> str:
        return self._tag.label

    @property
    def total_label(self) -> Optional[str]:
        return self._tag.total_label

    @property
    def localname(self) -> str:
        return self._tag.localname

    @property
    def namespace(self) -> str:
        return self._tag.namespace

    # --- XBRL metadata ---

    @property
    def crdr(self) -> Optional[str]:
        """Credit/debit indicator: 'credit', 'debit', or None."""
        return self._tag.crdr

    @property
    def xbrltype(self) -> str:
        return self._tag.xbrltype

    @property
    def documentation(self) -> str:
        """FASB authoritative documentation string."""
        return self._tag.documentation

    @property
    def is_standard(self) -> bool:
        return self._tag.is_standard

    @property
    def is_monetary(self) -> bool:
        return self._tag.is_monetary

    # --- Values from R*.htm ---

    @property
    def value(self) -> Optional[str]:
        """Latest period value from the primary report."""
        rows = self._graph._get_rows_for_concept(self.id)
        if not rows:
            return None
        # Return first non-dimensional value
        for row in rows:
            if not row.is_dimensional and not row.is_abstract and row.values:
                vals = list(row.values.values())
                return vals[0] if vals else None
        return None

    @property
    def values(self) -> Dict[str, str]:
        """All period values from the primary report (first non-dimensional row)."""
        rows = self._graph._get_rows_for_concept(self.id)
        for row in rows:
            if not row.is_dimensional and not row.is_abstract and row.values:
                return dict(row.values)
        return {}

    @property
    def numeric_value(self) -> Optional[float]:
        """Latest period value as a float, or None."""
        v = self.value
        return parse_numeric(v) if v else None

    @property
    def numeric_values(self) -> Dict[str, Optional[float]]:
        """All period values parsed as floats."""
        return {k: parse_numeric(v) for k, v in self.values.items()}

    @property
    def all_values(self) -> List[Dict[str, str]]:
        """All values including dimensional breakdowns."""
        rows = self._graph._get_rows_for_concept(self.id)
        return [dict(row.values) for row in rows if row.values]

    # --- Navigation: where does this concept appear? ---

    @property
    def statements(self) -> List[str]:
        """Report short names where this concept appears (Statements category)."""
        return self._graph._get_report_names_for_concept(self.id, 'Statements')

    @property
    def notes(self) -> List[str]:
        """Report short names where this concept appears (Notes category)."""
        return self._graph._get_report_names_for_concept(self.id, 'Notes')

    @property
    def details(self) -> List[str]:
        """Report short names where this concept appears (Details category)."""
        return self._graph._get_report_names_for_concept(self.id, 'Details')

    @property
    def report_names(self) -> List[str]:
        """All report short names where this concept appears."""
        return self._graph._get_report_names_for_concept(self.id)

    # --- Navigation: calculation tree ---

    @property
    def children(self) -> List['Concept']:
        """Calculation children in the primary role."""
        role = self._primary_calc_role
        if not role:
            return []
        child_tags = self._graph._metalinks.get_calculation_children(self.id, role)
        return [self._graph._get_or_create_concept(t.tag_id) for t in child_tags]

    @property
    def parent(self) -> Optional['Concept']:
        """Calculation parent in the primary role."""
        role = self._primary_calc_role
        if not role:
            return None
        entry = self._tag.calculation_in(role)
        if entry and entry.parent_tag:
            return self._graph._get_or_create_concept(entry.parent_tag)
        return None

    @property
    def weight(self) -> Optional[float]:
        """Calculation weight in the primary role (1.0 or -1.0)."""
        role = self._primary_calc_role
        if not role:
            return None
        entry = self._tag.calculation_in(role)
        return entry.weight if entry else None

    @property
    def is_root(self) -> bool:
        """True if this is a calculation root in its primary role."""
        role = self._primary_calc_role
        if not role:
            return False
        return self._tag.is_root_in(role)

    @property
    def _primary_calc_role(self) -> Optional[str]:
        """The primary calculation role for this concept (first available)."""
        calcs = self._tag.calculations
        if not calcs:
            return None
        # Prefer statement roles over note/detail roles
        metalinks = self._graph._metalinks
        statement_roles = {r.role for r in metalinks.get_reports_by_category('Statements')}
        for role in calcs:
            if role in statement_roles:
                return role
        return next(iter(calcs))

    def calculation_tree(self, max_depth: int = 5) -> dict:
        """Full recursive calculation decomposition."""
        role = self._primary_calc_role
        if not role:
            return {'concept': self, 'children': []}
        return self._graph._build_concept_tree(self.id, role, max_depth)

    # --- Auth refs ---

    @property
    def auth_references(self) -> list:
        """FASB authoritative references for this concept."""
        return self._graph._metalinks.get_auth_refs_for_tag(self._tag)

    # --- Display ---

    def __rich__(self):
        # Header
        balance_str = f"Balance: {self.crdr}" if self.crdr else "Balance: n/a"
        type_str = f"Type: {self.xbrltype}"

        header = Table(show_header=False, box=None, padding=(0, 2))
        header.add_column(width=40)
        header.add_column(width=30)
        header.add_row(f"Label: {self.label}", balance_str)
        header.add_row(f"Full: {self.full_label}", type_str)

        parts = [header]

        # Value
        if self.value:
            parts.append(Text(f"\nValue: {self.value}", style="bold"))

        # Appears in
        report_names = self.report_names
        if report_names:
            appears = Text("\nAppears in:", style="dim")
            for name in report_names[:5]:
                appears.append(f"\n  · {name}")
            if len(report_names) > 5:
                appears.append(f"\n  ... and {len(report_names) - 5} more")
            parts.append(appears)

        # Calculation relationships
        if self.is_root:
            children = self.children
            if children:
                calc_text = Text("\nCalculation root. Children:", style="dim")
                for child in children[:8]:
                    weight_str = f"weight: {child.weight}" if child.weight else ""
                    crdr_str = child.crdr or "n/a"
                    calc_text.append(f"\n  + {child.label} ({crdr_str}, {weight_str})")
                parts.append(calc_text)
        elif self.parent:
            parts.append(Text(f"\nParent: {self.parent.label}", style="dim"))

        # Documentation (truncated)
        if self.documentation:
            doc = self.documentation
            if len(doc) > 200:
                doc = doc[:200] + "..."
            parts.append(Text(f"\n{doc}", style="italic dim"))

        from rich.console import Group
        return Panel(
            Group(*parts),
            title=f"[bold]{self.id}[/bold]",
            expand=False,
            width=80,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"{self.label} ({self.id})"

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized summary of this concept."""
        lines = [
            f"Concept: {self.id}",
            f"Label: {self.label}",
        ]
        if self.crdr:
            lines.append(f"Balance: {self.crdr}")
        if self.value:
            lines.append(f"Value: {self.value}")
        if self.documentation:
            lines.append(f"Definition: {self.documentation}")

        if detail == 'full':
            if self.children:
                lines.append("Components:")
                for child in self.children:
                    val = child.value or ''
                    lines.append(f"  {child.label}: {val}")
            if self.report_names:
                lines.append(f"Appears in: {', '.join(self.report_names[:5])}")
            refs = self.auth_references
            if refs:
                lines.append(f"FASB references: {len(refs)} entries")

        return '\n'.join(lines)


class ConceptGraph:
    """
    Navigable knowledge graph of all tagged concepts in a filing.

    Combines MetaLinks tag definitions with R*.htm concept-annotated values
    to provide unified concept lookup, search, and calculation tree navigation.
    """

    def __init__(self,
                 metalinks: 'MetaLinks',
                 concept_reports: Dict[str, 'ConceptReport'],
                 report_key_to_meta: Dict[str, 'MetaLinksReport']):
        self._metalinks = metalinks
        self._concept_reports = concept_reports  # report_key -> ConceptReport
        self._report_key_to_meta = report_key_to_meta  # report_key -> MetaLinksReport
        self._concepts_cache: Dict[str, Concept] = {}
        # Build reverse indexes
        self._concept_to_report_keys: Dict[str, List[str]] = {}
        self._concept_to_rows: Dict[str, List] = []  # lazy
        self._concept_rows_built = False
        self._build_concept_to_report_index()

    def _build_concept_to_report_index(self):
        """Map concept_id -> list of report_keys where it appears in R*.htm."""
        for rkey, report in self._concept_reports.items():
            for concept_id in report.concepts:
                if concept_id not in self._concept_to_report_keys:
                    self._concept_to_report_keys[concept_id] = []
                self._concept_to_report_keys[concept_id].append(rkey)

    def _ensure_concept_rows_built(self):
        """Lazily build concept_id -> [ConceptRow] reverse index."""
        if self._concept_rows_built:
            return
        self._concept_to_rows = {}
        for report in self._concept_reports.values():
            for row in report.rows:
                if row.concept_id not in self._concept_to_rows:
                    self._concept_to_rows[row.concept_id] = []
                self._concept_to_rows[row.concept_id].append(row)
        self._concept_rows_built = True

    def _get_rows_for_concept(self, concept_id: str) -> list:
        """Get all ConceptRows for a concept across all reports."""
        self._ensure_concept_rows_built()
        return self._concept_to_rows.get(concept_id, [])

    def _get_report_names_for_concept(self, concept_id: str, category: Optional[str] = None) -> List[str]:
        """Get report short names where a concept appears, optionally filtered by category."""
        report_keys = self._concept_to_report_keys.get(concept_id, [])
        names = []
        for rkey in report_keys:
            meta = self._report_key_to_meta.get(rkey)
            if meta:
                if category is None or meta.menu_cat == category:
                    names.append(meta.short_name)
        return names

    def _get_or_create_concept(self, tag_id: str) -> Optional['Concept']:
        """Get cached Concept or create one from MetaLinks tag."""
        if tag_id in self._concepts_cache:
            return self._concepts_cache[tag_id]
        tag = self._metalinks.get_tag(tag_id)
        if not tag:
            return None
        concept = Concept(tag, self)
        self._concepts_cache[tag_id] = concept
        return concept

    def _build_concept_tree(self, tag_id: str, role: str, max_depth: int) -> dict:
        """Recursively build a concept tree with Concept objects."""
        concept = self._get_or_create_concept(tag_id)
        if not concept or max_depth <= 0:
            return {}
        children = self._metalinks.get_calculation_children(tag_id, role)
        return {
            'concept': concept,
            'children': [
                self._build_concept_tree(child.tag_id, role, max_depth - 1)
                for child in children
            ]
        }

    # --- Lookup ---

    def __getitem__(self, key: str) -> Optional[Concept]:
        """
        Look up a concept by label or tag ID.

            graph['Revenue']
            graph['us-gaap_Assets']
        """
        # Try exact tag ID first
        concept = self._get_or_create_concept(key)
        if concept:
            return concept
        # Try label lookup via MetaLinks
        tag = self._metalinks.get_tag_by_label(key)
        if tag:
            return self._get_or_create_concept(tag.tag_id)
        return None

    def concept(self, concept_id: str) -> Optional[Concept]:
        """Look up by exact concept ID."""
        return self._get_or_create_concept(concept_id)

    # --- Search ---

    def search(self, query: str, category: Optional[str] = None) -> List[Concept]:
        """Search concepts by label, documentation, or ID."""
        tags = self._metalinks.search(query, category=category)
        return [self._get_or_create_concept(t.tag_id) for t in tags]

    # --- Validation ---

    def validate(self, tolerance: float = 0.5) -> List[dict]:
        """
        Validate calculation trees by checking if children sum to parent.

        Recursively walks the full calculation tree for every statement role,
        checking every parent-children relationship — not just roots.

        Returns a list of validation results, each with:
            - parent: Concept (the parent being checked)
            - role: str (report short name)
            - expected: float (parent's value)
            - computed: float (weighted sum of children)
            - difference: float (expected - computed)
            - valid: bool (True if within tolerance)
        """
        results = []
        statement_reports = self._metalinks.get_reports_by_category('Statements')
        for meta_report in statement_reports:
            visited = set()
            roots = self._metalinks.get_calculation_roots(meta_report.role)
            for root_tag in roots:
                self._validate_recursive(
                    root_tag.tag_id, meta_report.role, meta_report.short_name,
                    tolerance, results, visited
                )
        return results

    def _validate_recursive(self, tag_id: str, role: str, role_name: str,
                            tolerance: float, results: list, visited: set):
        """Recursively validate a concept and all its calculation descendants."""
        if tag_id in visited:
            return
        visited.add(tag_id)

        children_tags = self._metalinks.get_calculation_children(tag_id, role)
        if not children_tags:
            return  # Leaf — nothing to validate

        parent_concept = self._get_or_create_concept(tag_id)
        if not parent_concept:
            return
        parent_val = parent_concept.numeric_value
        if parent_val is None:
            return

        child_sum = 0.0
        all_parsed = True
        for child_tag in children_tags:
            child_concept = self._get_or_create_concept(child_tag.tag_id)
            if not child_concept:
                all_parsed = False
                break
            child_val = child_concept.numeric_value
            if child_val is None:
                all_parsed = False
                break
            entry = child_tag.calculation_in(role)
            weight = entry.weight if entry else 1.0
            child_sum += child_val * weight

        if all_parsed:
            diff = parent_val - child_sum
            results.append({
                'parent': parent_concept,
                'role': role_name,
                'expected': parent_val,
                'computed': child_sum,
                'difference': diff,
                'valid': abs(diff) <= tolerance,
            })

        # Recurse into children
        for child_tag in children_tags:
            self._validate_recursive(
                child_tag.tag_id, role, role_name, tolerance, results, visited
            )

    # --- Stats ---

    @property
    def tag_count(self) -> int:
        return self._metalinks.tag_count

    @property
    def report_count(self) -> int:
        return len(self._concept_reports)

    @property
    def concept_count_with_values(self) -> int:
        """Number of unique concepts that have at least one value in R*.htm."""
        self._ensure_concept_rows_built()
        return sum(1 for rows in self._concept_to_rows.values()
                   if any(r.values for r in rows))

    def to_dataframe(self, category: Optional[str] = None):
        """
        Export concepts with values as a pandas DataFrame.

        Args:
            category: Optional filter — 'Statements', 'Notes', 'Details', etc.

        Returns:
            DataFrame with columns: concept_id, label, crdr, value, numeric_value, report
        """
        import pandas as pd
        rows = []
        self._ensure_concept_rows_built()

        # Determine which report keys to include
        if category:
            target_keys = {
                rkey for rkey, meta in self._report_key_to_meta.items()
                if meta.menu_cat == category
            }
        else:
            target_keys = set(self._concept_reports.keys())

        seen = set()
        for rkey in target_keys:
            report = self._concept_reports.get(rkey)
            if not report:
                continue
            meta = self._report_key_to_meta.get(rkey)
            report_name = meta.short_name if meta else rkey
            for crow in report.rows:
                if crow.is_abstract or crow.is_dimensional:
                    continue
                row_key = (crow.concept_id, rkey)
                if row_key in seen:
                    continue
                seen.add(row_key)
                tag = self._metalinks.get_tag(crow.concept_id)
                rows.append({
                    'concept_id': crow.concept_id,
                    'label': crow.label,
                    'crdr': tag.crdr if tag else None,
                    'value': crow.numeric_value,
                    'display_value': next(iter(crow.values.values()), None) if crow.values else None,
                    'report': report_name,
                })

        return pd.DataFrame(rows)

    def __len__(self):
        return self.tag_count

    def __repr__(self):
        return f"ConceptGraph(tags={self.tag_count}, reports={self.report_count})"

    # --- Factory ---

    @classmethod
    def build(cls,
              metalinks: 'MetaLinks',
              concept_reports: Dict[str, 'ConceptReport']) -> 'ConceptGraph':
        """
        Build a ConceptGraph from MetaLinks and parsed R*.htm reports.

        Args:
            metalinks: Parsed MetaLinks.json
            concept_reports: Dict of report_key -> ConceptReport (e.g., {'R2': report, 'R4': report})
        """
        report_key_to_meta = {
            rkey: metalinks.get_report(rkey)
            for rkey in concept_reports
            if metalinks.get_report(rkey)
        }
        return cls(metalinks, concept_reports, report_key_to_meta)


