"""Form 10-K annual report class."""
import re
import warnings
from functools import cached_property

from rich import box
from rich.console import Group, Text
from rich.padding import Padding
from rich.panel import Panel
from rich.tree import Tree

from edgar.company_reports._base import CompanyReport, report_lookup_miss
from edgar.company_reports._structures import FilingStructure, item_sort_key
from edgar.core import log
from edgar.display.formatting import datefmt
from edgar.documents import HTMLParser, ParserConfig, parse_html
from edgar.exceptions import strict_errors_enabled
from edgar.files.htmltools import ChunkedDocument

__all__ = ['TenK']


# Item number mapping for Cross Reference Index format
_CROSS_REF_ITEM_MAP = {
    'Item 1': '1',
    'Item 1A': '1A',
    'Item 1B': '1B',
    'Item 1C': '1C',
    'Item 2': '2',
    'Item 3': '3',
    'Item 4': '4',
    'Item 5': '5',
    'Item 6': '6',
    'Item 7': '7',
    'Item 7A': '7A',
    'Item 8': '8',
    'Item 9': '9',
    'Item 9A': '9A',
    'Item 9B': '9B',
    'Item 9C': '9C',
    'Item 10': '10',
    'Item 11': '11',
    'Item 12': '12',
    'Item 13': '13',
    'Item 14': '14',
    'Item 15': '15',
    'Item 16': '16',
}


# "Item 7", "ITEM 7", "item 7" are the same lookup. TenQ, TwentyF and
# CurrentReport already treated them so; TenK matched only the "Item " spelling
# and leaned on the legacy parser -- which lowercased -- for the rest. Deleting
# that fallback (edgartools-3dp Group B) made the gap visible as a real miss on
# `tenk['ITEM 7']` and `get_item_with_part('Part II', 'ITEM 7')`, GH #454.
# `\s+` rather than the fixed `normalized[5:]` slice it replaces, so "Item  7"
# works too. The required whitespace is also what keeps "Items 1 and 2" out:
# after the literal "item" comes "s", not a space, so it does not match here and
# is left to the combined-items branch below.
_ITEM_PREFIX = re.compile(r'^item\s+(.+)$', re.IGNORECASE)

# SEC 10-K item-to-part mapping. Each item number has exactly one valid Part
# per SEC rules. Used to constrain section lookups so a missing Part I item
# does not silently fall back to a wrong-Part section produced by a flaky
# section detector. See GH #821 (GS 10-K Item 1 mis-mapped to part_ii_item_1).
_ITEM_TO_PART_10K = {
    '1': 'i', '1a': 'i', '1b': 'i', '1c': 'i', '2': 'i', '3': 'i', '4': 'i',
    '5': 'ii', '6': 'ii', '7': 'ii', '7a': 'ii',
    '8': 'ii', '9': 'ii', '9a': 'ii', '9b': 'ii', '9c': 'ii',
    '10': 'iii', '11': 'iii', '12': 'iii', '13': 'iii', '14': 'iii',
    '15': 'iv', '16': 'iv',
}


# The canonical whole-numbered item order (1, 1A, 1B, 2, ... 16). Shared with
# TwentyF, whose items sort by the same rule; kept bound here because it is
# imported under this name.
_item_sort_key = item_sort_key


class TenK(CompanyReport):
    structure = FilingStructure({
        "PART I": {
            # special case for 10-K
            # Items 1 and 2. Business and Properties
            "ITEM 1": {
                "Title": "Business",
                "Description": "Overview of the company's business operations, products, services, and market environment."
            },
            "ITEM 1A": {
                "Title": "Risk Factors",
                "Description": "Discussion of risks and uncertainties that could materially affect the company's " +
                               "financial condition or results of operations."
            },
            "ITEM 1B": {
                "Title": "Unresolved Staff Comments",
                "Description": "Any comments from the SEC staff on the company's previous filings" +
                               "that remain unresolved."
            },
            "ITEM 1C": {
                "Title": "Cybersecurity",
                "Description": "Cybersecurity risk management, strategy, and governance disclosures."
            },
            "ITEM 2": {
                "Title": "Properties",
                "Description": "Information about the physical properties owned or leased by the company."
            },
            "ITEM 3": {
                "Title": "Legal Proceedings",
                "Description": "Details of significant ongoing legal proceedings."
            },
            "ITEM 4": {
                "Title": "Mine Safety Disclosures",
                "Description": "Relevant for mining companies, disclosures about mine safety and regulatory compliance."
            }
        },
        "PART II": {
            "ITEM 5": {
                "Title": "Market for Registrant's Common Equity",
                "Description": "Information on the company's equity, including stock performance " +
                               "and shareholder matters."
            },
            "ITEM 6": {
                "Title": "Selected Financial Data",
                "Description": "Financial data summary for the last five fiscal years."
            },
            "ITEM 7": {
                "Title": "Management's Discussion and Analysis (MD&A)",
                "Description": "Management's perspective on the financial condition, changes in financial condition, " +
                               "and results of operations."
            },
            "ITEM 7A": {
                "Title": "Quantitative and Qualitative Disclosures About Market Risk",
                "Description": "Information on the company's exposure to market risk, such as interest rate risk, " +
                               "foreign currency exchange risk, commodity price risk, etc."
            },
            "ITEM 8": {
                "Title": "Financial Statements",
                "Description": "Complete audited financial statements, including balance sheet, income statement, " +
                               "cash flow statement, and notes to the financial statements."
            },
            "ITEM 9": {
                "Title": "Controls and Procedures",
                "Description": "Evaluation of the effectiveness of the design and operation of the company's disclosure controls and procedures."
            },
            "ITEM 9A": {
                "Title": "Controls and Procedures",
                "Description": "Evaluation of internal controls over financial reporting."
            },
            "ITEM 9B": {
                "Title": "Other Information",
                "Description": "Any other relevant information not covered in other sections."
            },
            "ITEM 9C": {
                "Title": "Disclosure Regarding Foreign Jurisdictions That Prevent Inspections",
                "Description": "Disclosure Regarding Foreign Jurisdictions That Prevent Inspections."
            }
        },
        "PART III": {
            "ITEM 10": {
                "Title": "Directors, Executive Officers, and Corporate Governance",
                "Description": "Information about the company's directors, executive officers, and governance policies."
            },
            "ITEM 11": {
                "Title": "Executive Compensation",
                "Description": "Details of compensation paid to key executives."
            },
            "ITEM 12": {
                "Title": "Security Ownership of Certain Beneficial Owners and Management",
                "Description": "Information about stock ownership of major shareholders, directors, and management."
            },
            "ITEM 13": {
                "Title": "Certain Relationships and Related Transactions, and Director Independence",
                "Description": "Information on transactions between the company and its directors, officers, " +
                               "and significant shareholders."
            },
            "ITEM 14": {
                "Title": "Principal Accounting Fees and Services",
                "Description": "Fees paid to the principal accountant and services rendered."
            }
        },
        "PART IV": {
            "ITEM 15": {
                "Title": "Exhibits, Financial Statement Schedules",
                "Description": "Legal documents and financial schedules that support the financial statements " +
                               "and disclosures."
            },
            "ITEM 16": {
                "Title": "Form 10-K Summary",
                "Description": "Form 10-K Summary"
            }
        }
    })

    def __init__(self, filing):
        assert filing.form in ['10-K', '10-K/A'], f"This form should be a 10-K but was {filing.form}"
        super().__init__(filing)

    @cached_property
    def document(self):
        """
        Parse 10-K using new HTMLParser with enhanced section detection.

        This uses the pattern-based section extractor that handles:
        - All 10-K item patterns (Items 1, 1A, 1B, 1C, 2, 3, 4 in Part I, etc.)
        - Part boundaries and context
        - Bold paragraph fallback detection
        - Table cell detection
        - Various item number formatting variations

        Returns:
            Document object from edgar.documents module with sections property,
            or None when the filing has no HTML document at all — a real
            condition for older 10-Ks filed as plain text, and the only thing
            None means here from 6.0 onwards.

            Today None also comes back when the parser *failed*, with a
            FutureWarning; in 6.0 that raises instead. Two very different facts
            were arriving as the same value: "this filing has no HTML" and "this
            filing has HTML we could not read". Every sibling report class
            (TenQ, TwentyF, FortyF, CurrentReport) already lets a parse failure
            propagate — this one was the outlier.

            Set EDGARTOOLS_STRICT_ERRORS=1 for the 6.0 behaviour now.
        """
        html = self._filing.html()
        if not html:
            return None
        config = ParserConfig(form='10-K')
        parser = HTMLParser(config)
        try:
            return parser.parse(html)
        except Exception as e:
            # Deliberately not warn_will_raise(): what 6.0 does here is let the
            # parser's own ParsingError through, and a bare `raise` keeps its
            # type, message and traceback. Building a fresh error to raise would
            # replace a specific diagnosis with a generic one.
            if strict_errors_enabled():
                raise
            # Which filing failed, and why, goes to the log: naming it in the
            # warning would put the accession in the text Python dedups on, and
            # a parser regression across a form-year would then warn once per
            # filing. The warning dedups on the failure *mode* instead, which is
            # a bounded set — see warn_will_raise in edgar/exceptions.py.
            log.warning("HTMLParser failed for 10-K filing %s: %s",
                        self._filing.accession_number, e)
            warnings.warn(
                f"HTMLParser raised {type(e).__name__} on a 10-K "
                f"(falling back to ChunkedDocument); the filing and the parser "
                f"message are in the log.\n"
                f"This returns None today and raises in edgartools 6.0. Set "
                f"EDGARTOOLS_STRICT_ERRORS=1 to get the 6.0 behaviour now.",
                FutureWarning,
                stacklevel=2
            )
            return None

    @property
    def sections(self):
        """
        Get detected 10-K sections using new parser.

        Returns a Sections dictionary mapping section names to Section objects.
        Section names use friendly names (e.g., 'business', 'risk_factors', 'mda').

        Example:
            >>> ten_k.sections
            {'business': Section(...), 'risk_factors': Section(...), 'mda': Section(...)}
            >>> ten_k.sections['business'].text()
            'Item 1 - Business...'
            >>> ten_k.sections['mda'].text()
            'Item 7 - Management Discussion and Analysis...'
        """
        if self.document:
            return self.document.sections
        return {}

    @property
    def items(self):
        """
        List of detected item names in standard "Item X" format.

        Uses new parser's section detection for improved accuracy.
        Falls back to old chunked_document if new parser returns no sections.

        Returns:
            List of unique item titles in canonical SEC order
            (e.g., ['Item 1', 'Item 1A', 'Item 1B', 'Item 2', ...]).
        """
        # Mapping from friendly section names to Item numbers
        section_to_item = {
            'business': 'Item 1',
            'risk_factors': 'Item 1A',
            'unresolved_staff_comments': 'Item 1B',
            'cybersecurity': 'Item 1C',
            'properties': 'Item 2',
            'legal_proceedings': 'Item 3',
            'mine_safety': 'Item 4',
            'market_equity': 'Item 5',
            'selected_financial_data': 'Item 6',
            'mda': 'Item 7',
            'market_risk': 'Item 7A',
            'financial_statements': 'Item 8',
            'controls_procedures': 'Item 9',
            'controls_procedures_9a': 'Item 9A',
            'other_information': 'Item 9B',
            'foreign_jurisdictions': 'Item 9C',
            'directors_officers': 'Item 10',
            'executive_compensation': 'Item 11',
            'security_ownership': 'Item 12',
            'relationships_transactions': 'Item 13',
            'accounting_fees': 'Item 14',
            'exhibits': 'Item 15',
            'summary': 'Item 16'
        }

        def _canonical(raw_items):
            """Deduplicate and sort into canonical SEC 10-K item order."""
            return sorted(dict.fromkeys(raw_items), key=_item_sort_key)

        # Try new parser first
        if self.sections:
            items = []
            for key, section in self.sections.items():
                # Check if section has an item attribute
                if hasattr(section, 'item') and section.item:
                    items.append(f"Item {section.item}")
                # Map friendly names to Item numbers
                elif key in section_to_item:
                    items.append(section_to_item[key])
                # Handle keys that are already in "Item X" format
                elif key.startswith('Item '):
                    items.append(key)
            if items:
                return _canonical(items)

        # No legacy fallback here any more (edgartools-07lk.23). Measured across
        # the 115-fixture era-stratified corpus: removing it changes `.items` on
        # ZERO filings, for every one of 10-K, 10-Q, 20-F and 8-K. Strategy 5c in
        # the pattern extractor closed the last case that needed it — a 2001 10-K
        # losing Item 7 (edgartools-3dp).
        #
        # This says nothing about `__getitem__` below, which still falls back and
        # still has to: `.items` consulted legacy only when the new parser found
        # NOTHING, while `__getitem__` consults it whenever THIS item is missing,
        # so a partial detection miss reaches the second and never the first. That
        # is not hypothetical — on the same corpus, 15 item lookups return real
        # text only because of the fallback (e.g. 0000950153-99-001234 Item 14,
        # 19KB). Deleting that one is a separate, unfinished piece of work.
        return []

    # These four go through .get() rather than self[...] on purpose, and keep
    # returning None when the section is absent — in 6.0 too.
    #
    # `report[item]` raises in 6.0 because the caller named a specific thing and
    # `.get()` is there for the callers who would rather have None. A property
    # has no `.get(default)` form, so flipping these would delete the `if
    # tenk.risk_factors:` idiom with nowhere to move it to. They read as probes
    # — "does this filing have an MD&A?" — and a probe answering None is the
    # documented behaviour, not a silent failure.
    @property
    def business(self):
        """Item 1, or None if this filing has no Part I Item 1."""
        return self.get('Item 1')

    @property
    def risk_factors(self):
        """Item 1A, or None if this filing has no risk factors section."""
        return self.get('Item 1A')

    @property
    def management_discussion(self):
        """Item 7 (MD&A), or None if this filing has no Part II Item 7."""
        return self.get('Item 7')

    @property
    def directors_officers_and_governance(self):
        """Item 10, or None if this filing has no Part III Item 10."""
        return self.get('Item 10')

    @cached_property
    def subsidiaries(self):
        """Subsidiaries from Exhibit 21, if present.

        Returns SubsidiaryList if an EX-21 attachment exists (may be empty),
        or None if the filing has no EX-21 exhibit.
        """
        from edgar.company_reports.subsidiaries import SubsidiaryList, parse_subsidiaries

        for att in self._filing.attachments:
            doc_type = att.document_type or ''
            if doc_type.startswith('EX-21'):
                content = att.content
                if not content:
                    continue
                subs = parse_subsidiaries(content)
                return SubsidiaryList(subs)
        return None

    @cached_property
    def _chunked_document(self):
        # Construction only — the deprecation lives on the public
        # `chunked_document` in CompanyReport. Overriding that one here is what
        # previously cost TenK users their warning entirely.
        return ChunkedDocument(self._filing.html(), prefix_src=self._filing.base_dir)

    @cached_property
    def _cross_reference_index(self):
        """
        Lazy-load Cross Reference Index parser.

        Some companies (e.g., GE) use a "Form 10-K Cross Reference Index" table
        instead of standard Item headings. This parser detects and extracts
        Item-to-page mappings when present.

        Returns None if filing uses standard format.
        """
        from edgar.documents import CrossReferenceIndex

        html = self._filing.html()
        index = CrossReferenceIndex(html)

        # Only create parser if Cross Reference Index format is detected
        if index.has_index():
            return index
        return None

    def __str__(self):
        return f"""TenK('{self.company}')"""

    def to_context(self, detail: str = 'standard', focus: 'str | list[str] | None' = None) -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
            focus: Optional topic or list of topics for cross-cutting context.
                   When set, returns statement lines + note + policy for that topic.
                   Example: focus='debt' or focus=['debt', 'revenue']
        """
        # Handle focus mode — cross-cutting topic context
        if focus:
            return self._focused_context(focus, detail)

        from edgar.display.formatting import format_currency_short

        lines = []

        # === IDENTITY ===
        lines.append(f"TENK: {self.company} Annual Report")
        lines.append("")

        # === CORE METADATA ===
        try:
            period = self.period_of_report
            if period:
                lines.append(f"Period: {period}")
        except Exception:
            pass
        lines.append(f"Filed: {self.filing_date}")

        if detail == 'minimal':
            # Headline financials for minimal only
            try:
                fin = self.financials
                if fin:
                    cs = fin.get_currency_symbol()
                    revenue = fin.get_revenue()
                    net_income = fin.get_net_income()
                    if revenue:
                        lines.append(f"Revenue: {format_currency_short(revenue, cs)}")
                    if net_income:
                        lines.append(f"Net Income: {format_currency_short(net_income, cs)}")
            except Exception:
                pass
            return "\n".join(lines)

        # === STANDARD ===
        lines.append(f"Form: {self.form}")
        lines.append(f"CIK: {str(self._filing.cik).zfill(10)}")

        # Financials section
        try:
            fin = self.financials
            if fin:
                cs = fin.get_currency_symbol()
                fin_lines = []
                for label, getter in [
                    ("Revenue", "get_revenue"),
                    ("Net Income", "get_net_income"),
                    ("Total Assets", "get_total_assets"),
                    ("Operating Income", "get_operating_income"),
                    ("Stockholders Equity", "get_stockholders_equity"),
                ]:
                    try:
                        val = getattr(fin, getter)()
                        if val is not None:
                            fin_lines.append(f"  {label}: {format_currency_short(val, cs)}")
                    except Exception:
                        pass
                if fin_lines:
                    lines.append("")
                    lines.append("FINANCIALS:")
                    lines.extend(fin_lines)
        except Exception:
            pass

        # Sections (items property is already deduplicated and canonically sorted)
        try:
            items = self.items
            if items:
                lines.append("")
                lines.append("SECTIONS:")
                lines.append(f"  {', '.join(items)}")
        except Exception:
            pass

        # Available actions
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .financials              XBRL financial statements")
        lines.append("  .income_statement        Income statement")
        lines.append("  .balance_sheet           Balance sheet")
        lines.append("  .cash_flow_statement     Cash flow statement")
        lines.append("  .notes                   Notes to financial statements")
        lines.append("  .business                Item 1 business description")
        lines.append("  .risk_factors            Item 1A risk factors")
        lines.append("  .management_discussion   Item 7 MD&A")
        lines.append("  .items                   All available section items")
        lines.append("  .subsidiaries            Exhibit 21 subsidiary list")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL ===
        try:
            auditor = self.auditor
            if auditor:
                lines.append("")
                lines.append("AUDITOR:")
                aud_line = f"  {auditor.name}"
                if auditor.location:
                    aud_line += f", {auditor.location}"
                if auditor.firm_id:
                    aud_line += f" (PCAOB #{auditor.firm_id})"
                lines.append(aud_line)
        except Exception:
            pass

        try:
            subs = self.subsidiaries
            if subs and len(subs) > 0:
                lines.append("")
                lines.append(f"SUBSIDIARIES: {len(subs)} entities")
        except Exception:
            pass

        return "\n".join(lines)

    def __getitem__(self, item_or_part: str):
        """
        Get section/item text by name or number.

        Supports multiple lookup formats:
        - Standard format: 'Item 1', 'Item 1A', 'Item 7'
        - Short format: '1', '1A', '7', '7A'
        - Friendly names: 'business', 'risk_factors', 'mda'

        Falls back to old chunked_document and Cross Reference Index for backward compatibility.

        Args:
            item_or_part: Section identifier in various formats

        Returns:
            Section text content as string, or None if not found
        """
        # Mapping from Item numbers to friendly section names
        item_to_section = {
            'Item 1': 'business',
            'Item 1A': 'risk_factors',
            'Item 1B': 'unresolved_staff_comments',
            'Item 1C': 'cybersecurity',
            'Item 2': 'properties',
            'Item 3': 'legal_proceedings',
            'Item 4': 'mine_safety',
            'Item 5': 'market_equity',
            'Item 6': 'selected_financial_data',
            'Item 7': 'mda',
            'Item 7A': 'market_risk',
            'Item 8': 'financial_statements',
            'Item 9': 'controls_procedures',
            'Item 9A': 'controls_procedures_9a',
            'Item 9B': 'other_information',
            'Item 9C': 'foreign_jurisdictions',
            'Item 10': 'directors_officers',
            'Item 11': 'executive_compensation',
            'Item 12': 'security_ownership',
            'Item 13': 'relationships_transactions',
            'Item 14': 'accounting_fees',
            'Item 15': 'exhibits',
            'Item 16': 'summary'
        }

        # Reverse mapping: friendly names to Item numbers
        # (TOC-based detection uses "Item X" keys, so we need to map friendly names back)
        section_to_item = {v: k for k, v in item_to_section.items()}

        # Try new parser sections first
        if self.sections:
            # Normalize input
            normalized = item_or_part.strip()

            # PRIORITY 1: Try part-based naming convention first (most reliable)
            # These have proper part context (e.g., "part_i_item_1", "part_ii_item_5")
            item_num = None
            item_prefix = _ITEM_PREFIX.match(normalized)
            if item_prefix:
                # Extract item number: "Item 1" -> "1", "ITEM 1A" -> "1a"
                item_num = item_prefix.group(1).strip().lower()
            elif re.match(r'^\d+[A-Z]?$', normalized, re.IGNORECASE):
                # Short format: "1", "1A" -> "1", "1a"
                item_num = normalized.lower()
            elif normalized in section_to_item:
                # Friendly name: "business" -> "Item 1" -> "1"
                item_key = section_to_item[normalized]
                item_num = item_key[5:].strip().lower()

            # The spelling the two lookup maps are keyed by. They are written
            # title-case ('Item 1', 'Item 1A'), so matching them against the
            # caller's raw string only works when the caller happened to type it
            # that way -- which is the other half of GH #454.
            canonical_item = f'Item {item_num.upper()}' if item_num else None

            if item_num:
                # Only check the SEC-canonical Part for this item — prevents
                # silent fallback to wrong-Part content when the section
                # detector mis-labels a section (GH #821).
                canonical_part = _ITEM_TO_PART_10K.get(item_num)
                if canonical_part:
                    part_key = f'part_{canonical_part}_item_{item_num}'
                    if part_key in self.sections:
                        text = self.sections[part_key].text()
                        if text and text.strip():
                            return text

                # PRIORITY 1.5: Try combined-items keys (e.g., "Items 1 and 2. Business and Properties")
                # Some filings (energy, MLP, REIT) combine items under a single heading.
                # Match whether the item is the first or second number: items_1_and_2 or items_2_and_3
                inum = re.escape(item_num)
                combined_pattern = re.compile(rf'part_[iv]+_items_(?:{inum}_and_\d+|\d+_and_{inum})')
                for key in self.sections:
                    if combined_pattern.match(key):
                        text = self.sections[key].text()
                        if text and text.strip():
                            return text

            # PRIORITY 2: Direct key lookup (e.g., 'Item 1', 'business' if pattern-based)
            if item_or_part in self.sections:
                return self.sections[item_or_part].text()

            # PRIORITY 3: Try friendly name -> Item mapping
            if item_or_part in section_to_item:
                item_key = section_to_item[item_or_part]
                if item_key in self.sections:
                    return self.sections[item_key].text()

            # PRIORITY 4: Handle 'Item X' format -> try friendly name.
            # Canonical spelling first so 'ITEM 1' and 'item 1' reach the same
            # entry as 'Item 1'; the raw string stays as a second attempt so no
            # spelling that resolved before stops resolving.
            for candidate in (canonical_item, normalized):
                if candidate and candidate in item_to_section:
                    friendly_name = item_to_section[candidate]
                    if friendly_name in self.sections:
                        return self.sections[friendly_name].text()

            # PRIORITY 5: Handle short format '1', '1A', etc. -> convert to 'Item X'
            if re.match(r'^\d+[A-Z]?$', normalized, re.IGNORECASE):
                item_key = f'Item {normalized.upper()}'
                # Try direct lookup
                if item_key in self.sections:
                    return self.sections[item_key].text()
                # Try friendly name
                if item_key in item_to_section:
                    friendly_name = item_to_section[item_key]
                    if friendly_name in self.sections:
                        return self.sections[friendly_name].text()

            # Legacy fallback: SEC-canonical Part lookup only.
            # Items have exactly one valid Part per SEC rules — see GH #821.
            legacy_item_num = None
            legacy_prefix = _ITEM_PREFIX.match(normalized)
            if legacy_prefix:
                legacy_item_num = legacy_prefix.group(1).strip().lower()
            elif re.match(r'^\d+[a-z]?$', normalized, re.IGNORECASE):
                legacy_item_num = normalized.lower()

            if legacy_item_num:
                canonical_part = _ITEM_TO_PART_10K.get(legacy_item_num)
                if canonical_part:
                    part_key = f'part_{canonical_part}_item_{legacy_item_num}'
                    if part_key in self.sections:
                        text = self.sections[part_key].text()
                        if text and text.strip():
                            return text

        # If Cross Reference Index format is detected, prefer it over chunked_document
        # (Some filings like GE, Henry Schein use Cross Reference Index - issue #107)
        if self._cross_reference_index is not None:
            item_id = _CROSS_REF_ITEM_MAP.get(item_or_part)
            if item_id:
                # Extract content using Cross Reference Index parser.
                # extract_item_content() returns HTML by contract (it slices the
                # source document by page range), while every other branch of
                # this method returns text. Returning it unconverted handed
                # callers raw markup — 1.7MB of <div>/<span> for Citigroup's
                # Item 1, the "HTML leakage" half of GH #821. Convert before the
                # PART-stripping below, which is written for text and silently
                # did nothing on markup.
                item_html = self._cross_reference_index.extract_item_content(item_id)
                if item_html:
                    item_text = parse_html(item_html).text()
                    # An empty conversion falls through to the legacy fallback
                    # rather than returning the markup — a caller that asked for
                    # text is better served by the next strategy than by HTML.
                    if item_text and item_text.strip():
                        item_text = item_text.rstrip()
                        last_line = item_text.split("\n")[-1]
                        if re.match(r'^\b(PART\s+[IVXLC]+)\b', last_line):
                            item_text = item_text.rstrip(last_line)
                        return item_text

        report_lookup_miss(self, item_or_part)
        return None

    def get_item_with_part(self, part: str, item: str, markdown:bool=True):
        """
        Get item text with explicit part specification.

        Note: For 10-K filings, items are unique across parts, so the part parameter
        is less critical than for 10-Q. This method delegates to __getitem__ for new parser
        support while maintaining backward compatibility.

        Args:
            part: Part identifier (e.g., 'Part I', 'Part II') - largely ignored for 10-K
            item: Item identifier (e.g., 'Item 1', '1', 'business')
            markdown: If True, return markdown formatted text (default True)

        Returns:
            Item text content, or None if not found
        """
        # .get() rather than self[item] because a miss must return None, not
        # raise. It used to be a probe ahead of two edgar.files fallbacks; those
        # are gone (edgartools-3dp Group B) and the modern parser now answers
        # alone, but the non-raising contract is what callers were given.
        if self.sections:
            # Since 10-K items are unique, just use the item lookup
            result = self.get(item)
            if result:
                return result

        return None

    def get_structure(self):
        # Create the main tree
        tree = Tree("📄 ")

        # Get the actual items from the filing
        actual_items = self.items

        # Create a mapping of uppercase to actual case items
        case_mapping = {item.upper(): item for item in actual_items}

        # Process each part in the structure
        for part, items in self.structure.structure.items():
            # Create a branch for each part
            part_tree = tree.add(f"[bold blue]{part}[/]")

            # Add items under each part
            for item_key, item_data in items.items():
                # Check if this item exists in the actual filing
                if item_key in case_mapping:
                    # Use the actual case from the filing
                    actual_item = case_mapping[item_key]
                    item_text = Text.assemble(
                        (f"{actual_item:<7} ", "bold green"),
                        (f"{item_data['Title']}", "bold"),
                    )
                else:
                    # Item doesn't exist - show in grey with original structure case
                    item_text = Text.assemble(
                        (f"{item_key}: ", "dim"),
                        (f"{item_data['Title']}", "dim"),
                    )

                part_tree.add(item_text)

        return tree

    def __rich__(self):
        title = Text.assemble(
            (f"{self.company}", "bold deep_sky_blue1"),
            (" ", ""),
            (f"{self.form}", "bold"),
        )
        periods = Text.assemble(
            ("Period ending ", "grey70"),
            (f"{datefmt(self.period_of_report, '%B %d, %Y')}", "bold"),
            (" filed on ", "grey70"),
            (f"{datefmt(self.filing_date, '%B %d, %Y')}", "bold"),

        )
        panel = Panel(
            Group(
                periods,
                Padding(" ", (1, 0, 0, 0)),
                self.get_structure(),
                Padding(" ", (1, 0, 0, 0)),
                self.financials or Text("No financial data available", style="italic")
            ),
            title=title,
            box=box.ROUNDED,
        )
        return panel
