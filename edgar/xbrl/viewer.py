"""
SEC Interactive Data Viewer equivalent for edgartools.

Provides categorized navigation of all reports in a filing, concept-annotated
data from R*.htm files, and a navigable ConceptGraph built from MetaLinks.json.

Access via ``filing.viewer()``:

    viewer = filing.viewer()
    viewer.financial_statements     # Statement reports
    viewer.notes                    # Note reports
    viewer['Revenue']               # Concept lookup
    viewer.search('debt')           # Search all concepts
    viewer.validate()               # Check calculation trees
"""
from collections import Counter
from functools import cached_property
from typing import Dict, List, Optional, TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich
from edgar.sgml.concept_extractor import ConceptReport, extract_concepts_from_report
from edgar.sgml.metalinks import MetaLinks, MetaLinksReport

if TYPE_CHECKING:
    from edgar.sgml.filing_summary import FilingSummary, Report
    from edgar.sgml.sgml_common import FilingSGML
    from edgar.xbrl.concept_graph import Concept, ConceptGraph

__all__ = ['FilingViewer', 'ViewerReport']


# Concepts whose decimals attribute reflects shares / ratios / percentages —
# excluded when inferring the report's currency scaling.
# Keep in sync with edgar.xbrl.core.determine_dominant_scale.
_NON_MONETARY_LABEL_KEYWORDS = (
    'shares', 'share', 'stock', 'eps', 'earnings per share',
    'weighted average', 'number of', 'per common share', 'per share',
    'per basic', 'per diluted', 'outstanding', 'issued',
    'ratio', 'margin', 'percentage', 'rate', 'per cent',
)


def _is_monetary_label(label: str) -> bool:
    if not label:
        return True
    label_lower = label.lower()
    return not any(kw in label_lower for kw in _NON_MONETARY_LABEL_KEYWORDS)


def _multiplier_from_decimals(decimals_values: List[int]) -> int:
    """Convert a sample of XBRL ``decimals`` attribute values into a positive multiplier.

    XBRL convention: ``decimals="-6"`` means rounded to the nearest million,
    so display values are in millions and the raw amount is ``display * 1_000_000``.
    Buckets each input into {-9, -6, -3, 0} and returns the most common scaled
    bucket (preferring scale over units). Returns 1 when the input is empty.
    """
    if not decimals_values:
        return 1
    counts: Counter = Counter()
    for d in decimals_values:
        if d <= -9:
            counts[-9] += 1
        elif d <= -6:
            counts[-6] += 1
        elif d <= -3:
            counts[-3] += 1
        else:
            counts[0] += 1
    scaled = [b for b in counts if b < 0]
    best = max(scaled, key=lambda b: counts[b]) if scaled else 0
    return 10 ** (-best)


class ViewerReport:
    """
    A report in the viewer with concept annotations from R*.htm.

    Wraps an existing FilingSummary Report with concept extraction,
    adding concept_rows and concept-aware to_dataframe().
    """

    def __init__(self,
                 filing_report: 'Report',
                 meta_report: Optional[MetaLinksReport],
                 concept_report: Optional[ConceptReport],
                 viewer: Optional['FilingViewer'] = None):
        self._report = filing_report
        self._meta = meta_report
        self._concept_report = concept_report
        self._viewer = viewer  # back-ref for lazy level enrichment (GH #799)
        self._levels_enriched = False
        self._scaling_resolved = False
        self._scaling: int = 1  # default until first resolution

    @property
    def short_name(self) -> str:
        return self._report.short_name or ''

    @property
    def long_name(self) -> str:
        return self._report.long_name or ''

    @property
    def category(self) -> str:
        return self._report.menu_category or ''

    @property
    def role(self) -> str:
        return self._report.role or ''

    @property
    def html_file_name(self) -> str:
        return self._report.html_file_name or ''

    @property
    def position(self) -> Optional[str]:
        return self._report.position

    @property
    def group_type(self) -> str:
        if self._meta:
            return self._meta.group_type
        return ''

    @property
    def concept_report(self) -> Optional[ConceptReport]:
        return self._concept_report

    @property
    def currency_scaling(self) -> int:
        """Currency-scale multiplier for monetary values in this report.

        ``1`` = units, ``1_000`` = thousands, ``1_000_000`` = millions,
        ``1_000_000_000`` = billions. Multiplying a display value by this
        factor yields the raw amount in dollars (or the reporting currency).

        Derived from the XBRL ``decimals`` attribute on monetary facts mapped
        to this statement's role in the presentation linkbase (GH #807). The
        R*.htm header text-match value on ``concept_report.currency_scaling``
        is used as a fallback when XBRL is unavailable.
        """
        # ConceptReport is falsy when rows is empty (it defines __len__), so we
        # must distinguish "no concept report" from "empty rows" via ``is None``.
        if self._concept_report is None:
            return 1
        if not self._scaling_resolved:
            self._scaling_resolved = True
            if self._viewer is not None:
                self._scaling = self._viewer._resolve_currency_scaling(
                    self._concept_report, self._report.role
                )
            else:
                self._scaling = self._concept_report.currency_scaling
            # Mirror the resolved value back onto ConceptReport so callers
            # accessing it via concept_report.currency_scaling (the path
            # reported in GH #807) also see the corrected value.
            self._concept_report.currency_scaling = self._scaling
        return self._scaling

    @property
    def concept_rows(self) -> list:
        """Concept-annotated rows from R*.htm."""
        if not self._concept_report:
            return []
        # Lazy level enrichment from XBRL presentation linkbase (GH #799).
        # Deferred to first access so that initial viewer construction stays
        # cheap and avoids re-entering FilingSummary iteration during XBRL parse.
        if not self._levels_enriched:
            self._levels_enriched = True
            if self._viewer is not None:
                self._viewer._enrich_levels_from_presentation_tree(
                    self._concept_report, self._report.role
                )
        return self._concept_report.rows

    @property
    def concepts(self) -> List[str]:
        """Unique concept IDs in this report."""
        if self._concept_report:
            return self._concept_report.concepts
        return []

    @property
    def period_headers(self) -> List[str]:
        if self._concept_report:
            return self._concept_report.period_headers
        return []

    def to_dataframe(self):
        """Delegate to the underlying Report's to_dataframe()."""
        return self._report.to_dataframe()

    def view(self):
        """Delegate to the underlying Report's view()."""
        self._report.view()

    def text(self):
        """Delegate to the underlying Report's text()."""
        return self._report.text()

    def __rich__(self):
        title = self.short_name or self.long_name
        category = self.category
        concepts_count = len(self.concepts)
        rows_count = len(self.concept_rows)

        info = Table(show_header=False, box=None, padding=(0, 1))
        info.add_column(width=15)
        info.add_column()
        info.add_row("Category:", category)
        info.add_row("File:", self.html_file_name)
        info.add_row("Concepts:", str(concepts_count))
        info.add_row("Rows:", str(rows_count))
        if self.period_headers:
            info.add_row("Periods:", ', '.join(self.period_headers))

        return Panel(info, title=f"[bold]{title}[/bold]", expand=False, width=80)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"ViewerReport({self.short_name}, category={self.category})"


class FilingViewer:
    """
    SEC Interactive Data Viewer equivalent for edgartools.

    Provides categorized navigation of all reports in a filing,
    concept-annotated data, and a navigable concept graph.
    """

    def __init__(self,
                 sgml: 'FilingSGML',
                 filing_summary: 'FilingSummary',
                 metalinks: MetaLinks,
                 filing=None):
        self._sgml = sgml
        self._filing_summary = filing_summary
        self._metalinks = metalinks
        self._filing = filing  # retained for lazy XBRL parse (level enrichment, GH #799)
        self._viewer_reports_cache: Dict[str, ViewerReport] = {}
        self._concept_reports_cache: Dict[str, ConceptReport] = {}
        # Lazy XBRL — parsed only when concept_rows level enrichment is needed.
        self._xbrl_loaded = False
        self._xbrl = None

    # --- Report access by category (like SEC viewer tabs) ---

    @cached_property
    def financial_statements(self) -> List[ViewerReport]:
        """Reports recognized as financial statements.

        Returns the union of:
          - FilingSummary.xml ``MenuCategory='Statements'``
          - MetaLinks.json ``groupType='statement'``

        The MetaLinks fallback salvages primary statements that filers
        miscategorized in FilingSummary.xml (e.g., AbbVie's 2021 10-K placed
        ``Consolidated Statements of Earnings`` under ``Uncategorized``;
        MetaLinks correctly classifies it as a statement). Reports are
        returned in FilingSummary position order, deduplicated by
        ``html_file_name``.
        """
        return self._get_statement_viewer_reports()

    @cached_property
    def notes(self) -> List[ViewerReport]:
        """Reports in the Notes category."""
        return self._get_viewer_reports_by_category('Notes')

    @cached_property
    def policies(self) -> List[ViewerReport]:
        """Reports in the Policies category."""
        return self._get_viewer_reports_by_category('Policies')

    @cached_property
    def tables(self) -> List[ViewerReport]:
        """Reports in the Tables category."""
        return self._get_viewer_reports_by_category('Tables')

    @cached_property
    def details(self) -> List[ViewerReport]:
        """Reports in the Details category."""
        return self._get_viewer_reports_by_category('Details')

    @cached_property
    def cover(self) -> List[ViewerReport]:
        """Reports in the Cover category."""
        return self._get_viewer_reports_by_category('Cover')

    @cached_property
    def all_reports(self) -> List[ViewerReport]:
        """All reports across all categories."""
        reports = []
        for report in self._filing_summary.reports:
            vr = self._get_or_create_viewer_report(report)
            if vr:
                reports.append(vr)
        return reports

    # --- Concept graph ---

    @cached_property
    def concepts(self) -> 'ConceptGraph':
        """The ConceptGraph for this filing."""
        from edgar.xbrl.concept_graph import ConceptGraph
        # Build concept reports for all R*.htm files
        concept_reports = {}
        for report in self._filing_summary.reports:
            rkey = self._report_key(report)
            if rkey:
                cr = self._get_or_create_concept_report(report)
                if cr:
                    concept_reports[rkey] = cr
        return ConceptGraph.build(self._metalinks, concept_reports)

    def __getitem__(self, key: str):
        """Shortcut for concept lookup: viewer['Revenue']."""
        return self.concepts[key]

    # --- Search ---

    def search(self, query: str, category: Optional[str] = None) -> list:
        """Search across all concepts by label, documentation, or ID."""
        return self.concepts.search(query, category=category)

    # --- Validation ---

    def validate(self, tolerance: float = 0.5) -> list:
        """Validate calculation trees sum correctly."""
        return self.concepts.validate(tolerance=tolerance)

    def compare(self, xbrl, tolerance: float = 1.0):
        """
        Compare viewer values against XBRL parser output.

        The viewer (R*.htm) is treated as ground truth. Each concept+period
        in the viewer's financial statements is matched against the XBRL
        parser's output. Values are compared in display units.

        Args:
            xbrl: XBRL object from filing.xbrl()
            tolerance: Maximum allowed difference in display units
                       (default 1.0 = ±$1M for filings in millions)

        Returns:
            ComparisonResults with match rate, mismatches, and to_dataframe()
        """
        from edgar.xbrl.viewer_validation import compare_viewer_to_xbrl
        return compare_viewer_to_xbrl(self, xbrl, tolerance=tolerance)

    def compare_context(self, xbrl, statement: str = 'balance_sheet') -> str:
        """
        Generate an LLM-ready comparison prompt between viewer and XBRL.

        Outputs both the SEC viewer rendering and the XBRL statement as text,
        side by side, so an LLM can identify discrepancies that numeric
        comparison might miss (labels, ordering, missing items).

        Args:
            xbrl: XBRL object from filing.xbrl()
            statement: Statement method name ('balance_sheet', 'income_statement',
                       'cashflow_statement', 'comprehensive_income')

        Returns:
            Formatted text prompt comparing both renderings
        """
        lines = [
            "Compare the SEC Viewer rendering (ground truth) against the XBRL parser output.",
            "Identify any differences in values, labels, line items, or ordering.",
            "The SEC Viewer is the authoritative source — flag any XBRL discrepancies.",
            "",
        ]

        # Find the matching viewer report
        stmt_keywords = {
            'income_statement': 'OPERATIONS',
            'balance_sheet': 'BALANCE SHEET',
            'cashflow_statement': 'CASH FLOW',
            'comprehensive_income': 'COMPREHENSIVE',
        }
        keyword = stmt_keywords.get(statement, statement.upper())
        viewer_text = None
        for vr in self.financial_statements:
            if keyword in vr.short_name.upper():
                viewer_text = vr.text()
                lines.append(f"--- SEC VIEWER: {vr.short_name} ---")
                break

        if viewer_text:
            lines.append(viewer_text)
        else:
            lines.append(f"(No viewer report found matching '{statement}')")

        lines.append("")

        # Get XBRL statement text
        try:
            stmt_obj = getattr(xbrl.statements, statement)()
            if stmt_obj:
                from edgar.richtools import rich_to_text
                xbrl_text = rich_to_text(stmt_obj.render())
                lines.append(f"--- XBRL PARSER: {statement} ---")
                lines.append(xbrl_text)
            else:
                lines.append(f"(XBRL statement '{statement}' not found)")
        except Exception as e:
            lines.append(f"(Error getting XBRL statement: {e})")

        return '\n'.join(lines)

    # --- Display ---

    def view(self, report_name: Optional[str] = None):
        """
        Show a specific report by name, or print the viewer overview.

        Args:
            report_name: Short name of the report to display (e.g., "Income Statement")
        """
        from edgar.richtools import print_rich
        if report_name:
            for vr in self.all_reports:
                if report_name.lower() in vr.short_name.lower():
                    vr.view()
                    return
        print_rich(self.__rich__())

    def __rich__(self):
        categories = [
            ('FINANCIAL STATEMENTS', self.financial_statements),
            ('NOTES', self.notes),
            ('POLICIES', self.policies),
            ('TABLES', self.tables),
            ('DETAILS', self.details),
        ]

        parts = []
        summary_cats = []

        for cat_name, reports in categories:
            if not reports:
                continue
            if len(reports) <= 8:
                # Show full listing
                cat_table = Table(show_header=False, box=None, padding=(0, 1))
                cat_table.add_column(width=4, justify="right", style="dim")
                cat_table.add_column(width=58)
                cat_table.add_column(width=10, style="dim")
                for vr in reports:
                    cat_table.add_row(
                        str(vr.position) if vr.position else "-",
                        vr.short_name,
                        vr.html_file_name,
                    )
                parts.append(Text(f"\n{cat_name} ({len(reports)})", style="bold"))
                parts.append(cat_table)
            else:
                summary_cats.append(f"{cat_name} ({len(reports)})")

        if summary_cats:
            parts.append(Text(f"\n{' · '.join(summary_cats)}", style="dim"))

        # Stats line
        tag_count = self._metalinks.tag_count
        std_count = self._metalinks.stats.get('key_standard', 0)
        custom_count = self._metalinks.stats.get('key_custom', 0)
        parts.append(Text(f"\nConcepts: {tag_count} tags ({std_count} standard, {custom_count} custom)", style="dim"))

        title = "SEC Viewer"
        return Panel(
            Group(*parts),
            title=f"[bold]{title}[/bold]",
            expand=False,
            width=80,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"FilingViewer(reports={len(self.all_reports)}, tags={self._metalinks.tag_count})"

    # --- AI context ---

    def to_context(self, detail: str = 'standard') -> str:
        """Structured summary for LLM consumption."""
        lines = [
            f"SEC Filing Viewer — {self._metalinks.tag_count} tagged concepts",
            "",
        ]

        categories = [
            ('Financial Statements', self.financial_statements),
            ('Notes', self.notes),
            ('Policies', self.policies),
            ('Tables', self.tables),
            ('Details', self.details),
        ]

        for cat_name, reports in categories:
            if reports:
                lines.append(f"{cat_name} ({len(reports)}):")
                for vr in reports:
                    lines.append(f"  - {vr.short_name}")

        if detail == 'full':
            lines.append("")
            lines.append("Available actions:")
            lines.append("  - viewer['ConceptName'] to look up any tagged concept")
            lines.append("  - viewer.search('query') to search concepts")
            lines.append("  - viewer.validate() to check calculation trees")
            lines.append("  - concept.children to decompose a total")
            lines.append("  - concept.documentation for FASB definition")

        return '\n'.join(lines)

    # --- Internal helpers ---

    def _get_viewer_reports_by_category(self, category: str) -> List[ViewerReport]:
        """Get ViewerReports for a category, ordered by position."""
        fs_reports = self._filing_summary.get_reports_by_category(category)
        result = []
        for report in fs_reports:
            vr = self._get_or_create_viewer_report(report)
            if vr:
                result.append(vr)
        return result

    def _get_statement_viewer_reports(self) -> List[ViewerReport]:
        """Walk all FilingSummary reports, returning those recognized as
        financial statements via either FilingSummary MenuCategory or
        MetaLinks groupType. Preserves filing position order; dedup by
        html_file_name.
        """
        seen: set = set()
        result: List[ViewerReport] = []
        for report in self._filing_summary.reports:
            fname = report.html_file_name
            if not fname or fname in seen:
                continue
            is_stmt = report.menu_category == 'Statements'
            if not is_stmt:
                rkey = self._report_key(report)
                meta = self._metalinks.get_report(rkey) if rkey else None
                if meta and meta.group_type == 'statement':
                    is_stmt = True
            if not is_stmt:
                continue
            vr = self._get_or_create_viewer_report(report)
            if vr:
                seen.add(fname)
                result.append(vr)
        return result

    def _get_or_create_viewer_report(self, report: 'Report') -> Optional[ViewerReport]:
        """Get or create a ViewerReport for a FilingSummary Report."""
        fname = report.html_file_name
        if not fname:
            return None
        if fname in self._viewer_reports_cache:
            return self._viewer_reports_cache[fname]

        rkey = self._report_key(report)
        meta_report = self._metalinks.get_report(rkey) if rkey else None
        concept_report = self._get_or_create_concept_report(report)

        vr = ViewerReport(report, meta_report, concept_report, viewer=self)
        self._viewer_reports_cache[fname] = vr
        return vr

    def _get_or_create_concept_report(self, report: 'Report') -> Optional[ConceptReport]:
        """Lazily parse R*.htm content into a ConceptReport.

        Level enrichment (GH #799) is deferred to first concept_rows access
        on the wrapping ViewerReport — see ViewerReport.concept_rows.
        """
        fname = report.html_file_name
        if not fname:
            return None
        if fname in self._concept_reports_cache:
            return self._concept_reports_cache[fname]
        content = report.content
        if not content:
            return None
        cr = extract_concepts_from_report(content)
        self._concept_reports_cache[fname] = cr
        return cr

    def _get_xbrl(self):
        """Lazy-load the XBRL parser for presentation-tree access (GH #799).

        Returns None if no Filing was supplied (e.g., legacy construction)
        or if XBRL parsing fails. Caches both the success and failure cases
        so we don't retry on every concept_rows access.
        """
        if self._xbrl_loaded:
            return self._xbrl
        self._xbrl_loaded = True
        if self._filing is None:
            return None
        try:
            from edgar.xbrl.xbrl import XBRL
            self._xbrl = XBRL.from_filing(self._filing)
        except Exception:
            self._xbrl = None
        return self._xbrl

    def _resolve_currency_scaling(self, cr: ConceptReport, role: Optional[str]) -> int:
        """Resolve a report's currency-scale multiplier from XBRL decimals (GH #807).

        Mirrors the GH #799 pattern for level enrichment: XBRL is the canonical
        source. The ``decimals`` attribute on each monetary fact is filer-mandated
        and uniform (``-6`` → millions, ``-3`` → thousands, ``0`` → units), unlike
        the R*.htm ``<th class='tl'>`` header which only matches Apple-style
        ``$ in Millions`` formatting and silently misses common variations
        (``In Millions``, ``USD ($) in Millions``, ``(in millions)``, …).

        Falls back to ``cr.currency_scaling`` (the R*.htm header match value)
        when no XBRL is available, when the role is missing from the presentation
        linkbase, or when no monetary facts produce a usable ``decimals`` value.
        """
        if cr is None:
            return 1
        if not cr.rows:
            return cr.currency_scaling
        xbrl = self._get_xbrl()
        if xbrl is None or not role:
            return cr.currency_scaling
        tree = xbrl.presentation_trees.get(role)
        if tree is None or not tree.all_nodes:
            return cr.currency_scaling

        decimals_values: List[int] = []
        seen_concepts = set()
        # Dedup is per-concept (avoid querying the same concept N times when it
        # repeats across dimensional rows). Each query still returns one fact
        # per period context, so a single concept can still contribute multiple
        # decimals samples — that's intentional, the mode absorbs the variance.
        for row in cr.rows:
            if row.is_abstract or row.is_header:
                continue
            if not _is_monetary_label(row.label):
                continue
            if row.concept_id in seen_concepts:
                continue
            seen_concepts.add(row.concept_id)
            try:
                facts = xbrl.facts.query().by_concept(row.concept_id, exact=True).execute()
            except Exception:
                continue
            for fact in facts:
                d = fact.get('decimals') if isinstance(fact, dict) else getattr(fact, 'decimals', None)
                if d is None:
                    continue
                if isinstance(d, str):
                    if d == 'INF':
                        continue
                    try:
                        decimals_values.append(int(d))
                    except ValueError:
                        continue
                elif isinstance(d, int):
                    decimals_values.append(d)

        if not decimals_values:
            return cr.currency_scaling
        return _multiplier_from_decimals(decimals_values)

    def _enrich_levels_from_presentation_tree(self, cr: ConceptReport, role: Optional[str]) -> None:
        """Populate ConceptRow.level from the XBRL presentation linkbase (GH #799).

        SEC R*.htm files no longer encode hierarchy in HTML (no plN classes,
        no padding-left, no row nesting on modern filings). The canonical
        source is the XBRL presentation linkbase, which the parser already
        loads as ``xbrl.presentation_trees[role].all_nodes[concept_id].depth``.

        Levels are normalized so the smallest depth observed in the report
        becomes 0 — e.g., a balance-sheet root abstract at depth 2 maps to
        level 0, its children at depth 3 to level 1, etc.
        """
        if not role or not cr.rows:
            return
        xbrl = self._get_xbrl()
        if xbrl is None:
            return
        tree = xbrl.presentation_trees.get(role)
        if tree is None or not tree.all_nodes:
            return

        # Collect raw depths only for rows whose concept maps into this tree.
        matched = [(row, tree.all_nodes[row.concept_id].depth)
                   for row in cr.rows
                   if row.concept_id in tree.all_nodes]
        if not matched:
            return
        min_depth = min(depth for _, depth in matched)
        for row, depth in matched:
            row.level = depth - min_depth

    def _report_key(self, report: 'Report') -> Optional[str]:
        """Extract report key (e.g., 'R2') from html_file_name (e.g., 'R2.htm')."""
        fname = report.html_file_name
        if fname and fname.endswith('.htm'):
            return fname[:-4]
        return None

    # --- Factory ---

    @classmethod
    def from_filing(cls, filing) -> Optional['FilingViewer']:
        """
        Create a FilingViewer from a Filing object.

        Returns None if the filing doesn't have the required XBRL viewer data.
        Check ``FilingViewer.viewer_support(filing)`` for a diagnostic message.
        """
        sgml = filing.sgml()
        if not sgml:
            return None
        filing_summary = sgml.filing_summary
        if not filing_summary:
            return None
        metalinks_content = sgml.get_content('MetaLinks.json')
        if not metalinks_content:
            return None
        metalinks = MetaLinks.parse(metalinks_content)
        return cls(sgml, filing_summary, metalinks, filing=filing)

    @staticmethod
    def viewer_support(filing) -> str:
        """
        Diagnose why a filing may not support the viewer.

        Returns a human-readable message explaining viewer availability.
        """
        sgml = filing.sgml()
        if not sgml:
            return "No SGML submission bundle available for this filing."
        if not sgml.filing_summary:
            return "No FilingSummary.xml found — this filing has no interactive data."
        if not sgml.get_content('MetaLinks.json'):
            return "No MetaLinks.json found — this filing predates the SEC viewer metadata (pre-2012) or is not XBRL."
        return "Viewer is supported for this filing."
