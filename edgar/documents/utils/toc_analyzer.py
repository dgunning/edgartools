"""
Table of Contents analyzer for SEC filings.

This module analyzes the TOC structure to map section names to anchor IDs,
enabling section extraction for API filings with generated anchor IDs.
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lxml import html as lxml_html

from edgar.documents.form_schema import get_form_schema
from edgar.documents.utils.anchor_targets import find_anchor_targets

logger = logging.getLogger(__name__)


@dataclass
class TOCSection:
    """Represents a section found in the Table of Contents."""
    name: str
    anchor_id: str
    normalized_name: str
    section_type: str  # 'item', 'part', 'other'
    order: int
    part: Optional[str] = None  # NEW: "Part I", "Part II", or None for 10-K


class TOCAnalyzer:
    """
    Analyzes Table of Contents structure to map section names to anchor IDs.

    This enables section extraction for filings where anchor IDs are generated
    rather than semantic (like API filings vs local HTML files).
    """

    def __init__(self, form: Optional[str] = None):
        """
        Args:
            form: SEC form type ('10-K', '10-Q', '20-F', etc.). Used to
                  bound the bare-item-number TOC heuristic; without it
                  the analyzer falls back to a conservative default
                  that may treat small page numbers as item identifiers
                  on forms with few items (e.g., 10-Q has only Items 1-6).
        """
        self.form = form
        # Per-form schema: bare-item cap, text-keyword item rules, and the
        # unmatched-text policy. Replaces the scattered `if self.form in (...)`
        # branches that baked 10-K shape into form-agnostic code (edgartools-fhno).
        self.schema = get_form_schema(form)
        # Document-order rank of each title-based section key, populated by
        # _analyze_title_toc and consulted by _get_section_type_and_order so a
        # prospectus's sections are bounded in physical order (not declaration
        # order) — empty for Item forms (edgartools-llmp.3).
        self._title_section_order: Dict[str, int] = {}
        # End anchor for each title-based section key: the next TOC entry (any,
        # not just vocabulary matches) so detected sections don't absorb the
        # gap to the next *recognised* section. None = run to document end.
        self._title_next_anchor: Dict[str, Optional[str]] = {}
        # SEC section patterns for normalization
        self.section_patterns = [
            (r'(?:item|part)\s+\d+[a-z]?', 'item'),
            (r'business', 'item'),
            (r'risk\s+factors?', 'item'),
            (r'properties', 'item'),
            (r'legal\s+proceedings', 'item'),
            (r'management.*discussion', 'item'),
            (r'md&a', 'item'),
            (r'financial\s+statements?', 'item'),
            (r'exhibits?', 'item'),
            (r'signatures?', 'item'),
            (r'part\s+[ivx]+', 'part'),
        ]

    def analyze_toc_structure(self, html_content: str, agent: Optional[str] = None,
                              tree=None) -> Dict[str, str]:
        """
        Analyze HTML content to extract section mappings from TOC.

        When a filing agent is known, dispatches to an agent-specific parser
        that understands the agent's particular TOC HTML structure. Falls back
        to generic parsing for unknown agents.

        Args:
            html_content: Raw HTML content
            agent: Filing agent name (e.g., 'Workiva', 'Donnelley') or None
            tree: Pre-parsed lxml tree to avoid redundant parsing (optional)

        Returns:
            Dict mapping normalized section names to anchor IDs
        """
        result: Dict[str, str] = {}

        # Title-based forms (424B prospectuses) key their TOC by section title, not
        # "Item N" labels. A dedicated parser handles them; the entire Item-based
        # flow below is never entered for these forms, so 10-K/10-Q/8-K/20-F stay
        # byte-identical (edgartools-llmp.3).
        if self.schema.title_based:
            return self._analyze_title_toc(html_content, tree=tree)

        if agent == 'Workiva':
            result = self._analyze_workiva_toc(html_content, tree=tree)
        elif agent == 'Donnelley':
            result = self._analyze_dfin_toc(html_content, tree=tree)
        elif agent == 'Novaworks':
            result = self._analyze_novaworks_toc(html_content, tree=tree)
        elif agent == 'Toppan Merrill':
            result = self._analyze_toppan_toc(html_content, tree=tree)

        # Generic fallback for unknown agents or when agent-specific parser returns empty
        if not result:
            if agent:
                # The agent parser was tried and found nothing — make the
                # degradation to the generic scan observable (edgartools-hk9w).
                logger.debug("Agent parser %r returned no sections; "
                             "falling back to generic TOC scan", agent)
            result = self._analyze_generic_toc(html_content, tree=tree)

        # Body-header fallback: some filers (Goldman Sachs, Citi — large bank
        # 10-Ks) carry the SEC item structure only in a *link-less* TOC (page
        # numbers, no anchors), so every link-based parser above finds few or no
        # real items. But the document body marks each item with a bold
        # "Item N. Title" heading preceded by an anchor. When the linked-TOC
        # result is below the floor of items a healthy 10-K must have, scan the
        # body headers and prefer them if they recover more canonical items.
        if self._canonical_item_count(result) < self._expected_item_floor():
            body = self._analyze_body_item_headers(html_content, tree=tree)
            if self._canonical_item_count(body) > self._canonical_item_count(result):
                return body
        return result

    @staticmethod
    def _canonical_item_count(mapping: Optional[Dict[str, str]]) -> int:
        """Count keys that name a canonical SEC item (optionally part-prefixed)."""
        # A single letter suffix covers standard items (1A, 1B, 1C, 7A, 9A–9C) and
        # legitimate company-specific ones (e.g. Caterpillar's Item 1D, Executive
        # Officers) — not just a–c.
        pat = re.compile(r'^(part_[ivxlcdm]+_)?item_\d+[a-z]?$', re.IGNORECASE)
        return sum(1 for k in (mapping or {}) if pat.match(k))

    def _expected_item_floor(self) -> int:
        """Minimum canonical item count below which a 10-K TOC parse is suspect.

        A real 10-K always carries well over a dozen items (1, 1A, 2, 3, 5, 7,
        7A, 8, 9A, 10–15 …); a parse yielding only a handful means the linked
        TOC was missed. Only 10-K is gated — the body-header signature
        ("Item N. Title") is 10-K-shaped and the fallback is validated there.
        Other forms return 0 (fallback never triggers).
        """
        return 8 if (self.form or '10-K').replace('/A', '') == '10-K' else 0

    def _analyze_generic_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Generic TOC analysis — the original strategy that scans all anchor links.

        Works across all filing agents but may miss sections or pick up
        non-TOC links for agents with unusual TOC structures.

        Args:
            html_content: Raw HTML content
            tree: Pre-parsed lxml tree (optional, avoids re-parsing)

        Returns:
            Dict mapping normalized section names to anchor IDs
        """
        section_mapping = {}

        try:
            if tree is None:
                # Handle XML declaration issues
                if html_content.startswith('<?xml'):
                    html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
                tree = lxml_html.fromstring(html_content)

            # Find all anchor links that could be TOC links
            anchor_links = tree.xpath('//a[@href]')

            toc_sections = []
            current_part = self.schema.seed_part  # Track part context; seeds Part I for 10-Q

            for link in anchor_links:
                href = link.get('href', '').strip()
                text = (link.text_content() or '').strip()

                # Only internal anchors can define TOC section boundaries.
                if not href.startswith('#'):
                    continue

                if not text:
                    continue

                # Check if this link or its row represents a part header
                # Part headers in 10-Q TOCs typically appear as separate rows: "Part I", "Part II"
                explicit_part = self._extract_part_context(text)
                if explicit_part and not re.search(r'item\s+\d+[a-z]?', text, re.IGNORECASE):
                    # Update current part context
                    current_part = explicit_part
                    # Don't create a section for the part header itself
                    continue

                anchor_id = href[1:]  # Remove #

                # Try to find item number in preceding context (for table-based TOCs)
                preceding_item = self._extract_preceding_item_label(link)

                # Infer current part from surrounding TOC row context when part headers
                # are standalone rows without links (common in some 10-K filings).
                inferred_part = self._infer_part_from_row_context(link)
                if inferred_part:
                    current_part = inferred_part

                # Check if this looks like a section reference (check text, anchor ID, and context)
                if self._is_section_link(text, anchor_id, preceding_item):
                    # Verify target exists
                    target_elements = find_anchor_targets(tree, anchor_id)
                    if target_elements:
                        # Try to extract item number from: anchor ID > preceding context > text
                        normalized_name = self._normalize_section_name(text, anchor_id, preceding_item)
                        section_type, order = self._get_section_type_and_order(normalized_name)

                        toc_section = TOCSection(
                            name=text,
                            anchor_id=anchor_id,
                            normalized_name=normalized_name,
                            section_type=section_type,
                            order=order,
                            part=current_part  # Assign current part context
                        )
                        toc_sections.append(toc_section)

            # Build mapping prioritizing the most standard section names
            section_mapping = self._build_section_mapping(toc_sections, tree=tree)

        except Exception:
            # Degrade to other strategies, but record why the generic scan failed
            # so the silent-fallback path stays diagnosable (edgartools-hk9w).
            logger.debug("Generic TOC parser failed", exc_info=True)

        return section_mapping

    # Trailing page-number / dot-leader run on a TOC link's text ("Use of
    # Proceeds .... 12"), stripped before matching the schema title vocabulary
    # (whose regexes are heading-anchored with \s*$).
    _TOC_PAGE_TAIL = re.compile(r'[\s.…]*\d{0,4}\s*$')

    # A TOC entry whose visible text is only a page number ("8", "12") is a
    # dot-leader artifact, not a section title. It shares its sibling title's
    # target so it still marks a boundary position, but it must not define that
    # boundary's indentation depth (edgartools-gb99).
    _TOC_PAGE_NUMBER = re.compile(r'^\d{1,4}$')

    # Indents are compared with this tolerance (pt/px) so render noise never
    # fabricates a depth level; entries within tolerance are siblings.
    _TOC_INDENT_TOL = 1.5
    # A CSS length value ("7.2pt", "-7.2pt", "12px"); only the numeric part is
    # kept (units are assumed consistent within one TOC).
    _CSS_LEN = re.compile(r'^-?\d+(?:\.\d+)?')
    # Inline-style declarations, split on ';'.
    _CSS_DECL = re.compile(r'([a-z-]+)\s*:\s*([^;]+)')

    @classmethod
    def _css_len(cls, value: str) -> float:
        m = cls._CSS_LEN.match(value.strip())
        return float(m.group(0)) if m else 0.0

    @classmethod
    def _shorthand_left(cls, value: str) -> float:
        """Left component of a ``margin``/``padding`` shorthand (top right bottom
        left). 1 value → all sides; 2 → left is the 2nd; 3 → 2nd; 4 → 4th."""
        parts = value.split()
        if not parts:
            return 0.0
        if len(parts) == 1:
            return cls._css_len(parts[0])
        if len(parts) >= 4:
            return cls._css_len(parts[3])
        return cls._css_len(parts[1])  # 2 or 3 values: left == right == parts[1]

    @classmethod
    def _element_left(cls, style: str) -> float:
        """Left offset an element's inline style contributes: explicit
        ``margin-left``/``padding-left`` (falling back to the box shorthand) plus
        ``text-indent``. A hanging indent (``padding-left:7.2pt;text-indent:-7.2pt``)
        nets to zero, exactly as it renders."""
        decls = {k: v.strip() for k, v in cls._CSS_DECL.findall(style.lower())}
        left = 0.0
        for box in ('margin', 'padding'):
            if f'{box}-left' in decls:
                left += cls._css_len(decls[f'{box}-left'])
            elif box in decls:
                left += cls._shorthand_left(decls[box])
        if 'padding-left' not in decls and 'padding-inline-start' in decls:
            left += cls._css_len(decls['padding-inline-start'])
        if 'text-indent' in decls:
            left += cls._css_len(decls['text-indent'])
        return left

    @classmethod
    def _toc_indent(cls, el) -> float:
        """Cumulative left indentation (pt/px) of a TOC entry, summed over up to
        eight ancestors.

        A nested sub-entry sits deeper than its parent section, so bounding a
        section at the next *shallower-or-equal* entry skips its own children
        (edgartools-gb99). A flat single-level TOC (prospectus / S-1 / 424B)
        yields one uniform value, so the sibling rule collapses to "bound at the
        next entry" — the prior behaviour, unchanged.
        """
        total = 0.0
        cur = el
        for _ in range(8):
            if cur is None:
                break
            style = cur.get('style')
            if style:
                total += cls._element_left(style)
            cur = cur.getparent()
        return total

    _TOC_FONT_WEIGHT = re.compile(r'font-weight\s*:\s*(bold|bolder|\d{3})')
    _TOC_BACKGROUND = re.compile(r'background(?:-color)?\s*:\s*([^;]+)')

    @classmethod
    def _is_divider(cls, el) -> bool:
        """Whether a TOC entry is rendered as a section-divider *tab* — bold text
        on a filled background.

        Such an entry heads the proxy outline regardless of indentation:
        JPMorgan's otherwise-flat TOC marks its parts ("Corporate governance",
        "Executive compensation", "Audit matters") this way while nested
        subsections stay weight-400 with no fill, the only depth signal it carries
        (edgartools-zas6). Both bold AND a non-white background are required so
        striped rows and page chrome don't qualify (verified zero false positives
        on KO/AAPL/WMT)."""
        bold = bg = False
        cur = el
        for _ in range(5):
            if cur is None:
                break
            style = (cur.get('style') or '').lower()
            if style:
                if not bold:
                    m = cls._TOC_FONT_WEIGHT.search(style)
                    if m and (m.group(1) in ('bold', 'bolder') or
                              (m.group(1).isdigit() and int(m.group(1)) >= 700)):
                        bold = True
                if not bg:
                    b = cls._TOC_BACKGROUND.search(style)
                    if b:
                        val = b.group(1).strip()
                        if (val not in ('transparent', 'none', 'white')
                                and not val.startswith('#fff')):
                            bg = True
            cur = cur.getparent()
        return bold and bg

    # A divider tab outranks any indentation, so its depth is pushed below every
    # normal entry's; only another divider (or the document end) can bound it.
    _DIVIDER_BONUS = 1000.0

    @classmethod
    def _toc_depth(cls, el) -> float:
        """A TOC entry's outline depth: its indentation, lifted above all normal
        entries when it is a section-divider tab (lower number = higher in the
        outline). A section is bounded at the next entry of equal-or-lower depth,
        so a divider bounds only at the next divider and its nested subsections
        are absorbed (edgartools-gb99 + zas6)."""
        return cls._toc_indent(el) - (cls._DIVIDER_BONUS if cls._is_divider(el) else 0.0)

    def _analyze_title_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """TOC parser for title-based forms (424B prospectuses, llmp.3).

        Keys sections by matching each internal TOC link's text against the
        schema's title vocabulary (``section_patterns``) rather than parsing an
        "Item N" number. Returns ``{section_key: anchor_id}`` — the same contract
        the Item-based parsers return — so the boundary/slicing pipeline in
        ``SECSectionExtractor`` works unchanged. First occurrence of a key wins
        (the TOC lists each section once, in document order).

        Only reached when ``self.schema.title_based`` — never for Item forms.
        """
        mapping: Dict[str, str] = {}
        self._title_section_order = {}
        self._title_next_anchor = {}
        try:
            tree = self._ensure_tree(html_content, tree)
        except Exception:
            logger.debug("Title TOC parser: tree parse failed", exc_info=True)
            return mapping

        try:
            # Document-order index of every id / <a name>, so sections can be
            # ordered (and therefore bounded) by where their bodies physically
            # sit — a prospectus's TOC declaration order is not always its body
            # order, and ordering by anything else over-captures (a section runs
            # to a later-declared but earlier-positioned anchor).
            # Single document-order pass: record each id / <a name> target
            # position, and collect every internal anchor link with its own
            # source position (the index of the <a> element) so the authoritative
            # TOC can be located by where the links physically sit.
            positions: Dict[str, int] = {}
            # Raw internal anchor links in document order, before fragment
            # coalescing: (src_idx, anchor_id, element, title_text, is_page_number).
            raw_links: List[Tuple[int, str, object, str, bool]] = []
            for idx, el in enumerate(tree.iter()):
                eid = el.get('id')
                if eid and eid not in positions:
                    positions[eid] = idx
                if el.tag == 'a':
                    nm = el.get('name')
                    if nm and nm not in positions:
                        positions[nm] = idx
                    href = (el.get('href') or '').strip()
                    if href.startswith('#'):
                        raw = (el.text_content() or '').strip()
                        # Keep the raw text; page-number handling happens after
                        # coalescing so a proposal number ("PROPOSAL NO. 1") isn't
                        # mistaken for a trailing page reference per-fragment.
                        is_pg = (not raw) or bool(self._TOC_PAGE_NUMBER.match(raw))
                        raw_links.append((idx, href[1:], el, raw, is_pg))

            # Coalesce fragmented entries: a single logical TOC entry is often
            # split across several <a> elements that all target the same anchor —
            # JPMorgan renders "PROPOSAL 1:" / "Election of directors" / the page
            # number as three separate links and even splits a word ("E" +
            # "ngagement"). Group consecutive links sharing an anchor id, join
            # their title fragments, and match the vocabulary once on the whole
            # title, so a fragment never keys a section on its own and the entry
            # carries one position and one depth (edgartools-zas6).
            # entry = (first_src, anchor_id, key, depth, is_page_only)
            entries: List[Tuple[int, str, Optional[str], float, bool]] = []
            i, n = 0, len(raw_links)
            while i < n:
                j = i
                anchor_id = raw_links[i][1]
                while j < n and raw_links[j][1] == anchor_id:
                    j += 1
                group = raw_links[i:j]
                i = j
                # Drop page-number / empty fragments at the LEADING and TRAILING
                # edges of the entry (running-header digits like JPMorgan's
                # "202"/"6" and the dot-leader page reference), then join the core
                # fragments. A numeric fragment that survives in the MIDDLE is a
                # proposal number ("PROPOSAL NO." "1" "Election of directors"), not
                # a page reference, and must stay or the "Proposal N" vocabulary no
                # longer matches (the WMT voting_proposals failure, edgartools-zas6).
                texts = [t for _s, _a, _e, t, _pg in group]
                pgs = [pg for _s, _a, _e, _t, pg in group]
                lo_k, hi_k = 0, len(texts)
                while lo_k < hi_k and pgs[lo_k]:
                    lo_k += 1
                while hi_k > lo_k and pgs[hi_k - 1]:
                    hi_k -= 1
                title = ' '.join(t for t in texts[lo_k:hi_k] if t).strip()
                # A single-fragment entry can still carry an inline trailing page
                # number ("Use of Proceeds 12"); strip it for matching.
                title = self._TOC_PAGE_TAIL.sub('', title).strip() or title
                key = self.schema.match_section_pattern(title) if title else None
                # Depth from the non-page fragments only: a page-number link is
                # rendered flush (indent 0) and would otherwise drag every entry's
                # depth to zero, erasing the indentation hierarchy.
                title_els = [e for _s, _a, e, _t, pg in group if not pg] \
                    or [e for _s, _a, e, _t, _pg in group]
                depth = min(self._toc_depth(e) for e in title_els)
                is_pg_only = all(pg for _s, _a, _e, _t, pg in group)
                entries.append((group[0][0], anchor_id, key, depth, is_pg_only))

            # Locate the authoritative TOC: the body cross-references / back-links
            # a section emits ("return to contents") also match the title
            # vocabulary and point *adjacent* to a section start, so including them
            # as boundaries cuts every section to a sliver (the Apple/JPM proxy
            # failure: two TOC-like link sets whose targets differ by one node).
            # The real TOC is the densest contiguous run of vocabulary-matching
            # entries; scattered body back-links form sparse runs with few distinct
            # keys. Pick the richest run and restrict BOTH key matching and
            # boundary collection to its source-position span — a single-TOC
            # filing (prospectus/S-1) has one run, so its behaviour is unchanged.
            matched_src = [(src, anc, key) for src, anc, key, _d, _pg in entries if key]
            toc_lo, toc_hi = self._authoritative_toc_span(matched_src)
            if toc_lo is None:
                return mapping

            # Anchor selection: a key can appear several times in one proxy TOC —
            # a shallow top-level entry plus deeper sub-entry / summary mentions
            # (Apple lists "Executive Compensation" inside the Proxy Summary
            # before the real section). Prefer the SHALLOWEST-depth match so a
            # section keys to its real body, not a summary cross-reference; ties
            # keep document order (first wins). On a flat TOC every match shares
            # one depth, so this is exactly first-occurrence-wins (edgartools-gb99).
            matched: Dict[str, str] = {}          # key -> chosen anchor_id
            matched_depth: Dict[str, float] = {}  # key -> that anchor's outline depth
            matched_src: Dict[str, int] = {}      # key -> that entry's TOC source index
            for src, anchor_id, key, depth, _pg in entries:
                if key is None or not (toc_lo <= src <= toc_hi):
                    continue
                if anchor_id not in positions or not find_anchor_targets(tree, anchor_id):
                    continue
                if key not in matched or depth < matched_depth[key] - self._TOC_INDENT_TOL:
                    matched[key] = anchor_id
                    matched_depth[key] = depth
                    matched_src[key] = src

            if not matched:
                return mapping

            # Boundary depths: every TOC entry's body position is a potential
            # section end, tagged with its outline depth. Coalescing has already
            # folded each entry's page number into its title, so a page-only entry
            # (rare) only fills a position no titled entry claimed. Restricted to
            # entries inside the TOC span, which excludes the body back-links that
            # previously sliced sections to nothing.
            boundary_depth: Dict[int, float] = {}
            boundary_pg: Dict[int, bool] = {}
            boundary_src: Dict[int, int] = {}  # body pos -> owning entry's TOC source index
            pos_to_anchor: Dict[int, str] = {}
            for src, anchor_id, _key, depth, is_pg_only in entries:
                if not (toc_lo <= src <= toc_hi):
                    continue
                pos = positions.get(anchor_id)
                if pos is None:
                    continue
                pos_to_anchor.setdefault(pos, anchor_id)
                if pos in boundary_depth and (not boundary_pg[pos] or is_pg_only):
                    continue
                boundary_depth[pos] = depth
                boundary_pg[pos] = is_pg_only
                boundary_src[pos] = src
            sorted_boundaries = sorted(boundary_depth)

            # Order detected sections by body position; bound each at the next TOC
            # entry that is NOT one of its own descendants — the next entry at the
            # same-or-lower outline depth (a sibling-or-shallower). Deeper entries
            # in between are children and are absorbed, so a section is no longer
            # sliced to a sliver by its own audit/compensation sub-headings (the KO
            # audit_matters=13-char failure, gb99) nor cut by a nested proposal
            # under a divider tab (the JPM corporate_governance=39-char failure,
            # zas6). On a flat single-level TOC every entry is a sibling, so this
            # stays "bound at the next entry" — prospectus/S-1 behaviour unchanged.
            ordered = sorted(matched.items(), key=lambda kv: positions[kv[1]])
            for rank, (key, anchor_id) in enumerate(ordered):
                mapping[key] = anchor_id
                self._title_section_order[key] = rank
                start = positions[anchor_id]
                depth = matched_depth[key]
                sect_src = matched_src[key]
                # The end boundary must be a TOC entry positioned after this section
                # AND declared at-or-after it in the TOC. The declaration-order guard
                # rejects an out-of-order anchor: a TOC entry listed *before* this
                # section whose body anchor nonetheless sits *inside* it — e.g. a
                # "Glossary of Terms" sub-block opening Airbnb's MD&A, declared above
                # MD&A in the TOC but anchored a few nodes into its body. On a flat
                # TOC its depth equals MD&A's, so the depth guard alone lets it
                # truncate MD&A to a sliver; requiring boundary_src > sect_src drops
                # it (edgartools-ti82 / gh-878). Normal sections, whose body order
                # matches TOC order, satisfy this for free.
                nxt = next(
                    (p for p in sorted_boundaries
                     if p > start and boundary_depth[p] <= depth + self._TOC_INDENT_TOL
                     and boundary_src.get(p, sect_src + 1) > sect_src),
                    None,
                )
                # Resolve the boundary position back to the entry anchor sitting
                # there, else find the id occupying that position.
                self._title_next_anchor[key] = (
                    pos_to_anchor.get(nxt) or self._id_at_position(positions, nxt)
                    if nxt is not None else None
                )
        except Exception:
            logger.debug("Title TOC parser failed", exc_info=True)

        return mapping

    @staticmethod
    def _id_at_position(positions: Dict[str, int], pos: Optional[int]) -> Optional[str]:
        """The id/name whose first document index is ``pos`` (inverse of positions)."""
        if pos is None:
            return None
        for anchor, p in positions.items():
            if p == pos:
                return anchor
        return None

    # A gap (in document-order element indices) between consecutive internal
    # anchor links larger than this ends the current run. A real TOC is a dense
    # block of links; body back-references are separated by paragraphs of content,
    # so this cleanly splits the authoritative TOC from scattered body links.
    _TOC_RUN_GAP = 120

    @classmethod
    def _authoritative_toc_span(
        cls, internal_links: List[Tuple[int, str, Optional[str]]]
    ) -> Tuple[Optional[int], Optional[int]]:
        """Source-index span ``(lo, hi)`` of the authoritative TOC, or ``(None, None)``.

        ``internal_links`` is every internal anchor link in document order as
        ``(src_idx, anchor_id, matched_key_or_None)``. The links are clustered
        into contiguous runs (a gap over :attr:`_TOC_RUN_GAP` starts a new run);
        the run carrying the most distinct vocabulary keys (ties broken by link
        count) is the real TOC. Body back-references — which also match the
        vocabulary but point adjacent to a section start — fall into sparse,
        key-poor runs and are excluded, so they no longer pollute the boundary
        set. A single-TOC filing yields one run, leaving its behaviour unchanged.
        """
        if not any(key for _src, _anc, key in internal_links):
            return (None, None)

        runs: List[List[Tuple[int, str, Optional[str]]]] = []
        current: List[Tuple[int, str, Optional[str]]] = []
        for entry in internal_links:
            if current and entry[0] - current[-1][0] > cls._TOC_RUN_GAP:
                runs.append(current)
                current = []
            current.append(entry)
        if current:
            runs.append(current)

        def score(run: List[Tuple[int, str, Optional[str]]]) -> Tuple[int, int]:
            return (len({key for _s, _a, key in run if key}), len(run))

        best = max(runs, key=score)
        return (best[0][0], best[-1][0])

    def title_section_end(self, key: str) -> Optional[str]:
        """End anchor for a title-based section key (next TOC entry), or None.

        None means the section runs to the end of the document (it is the last
        TOC entry). Populated by :meth:`_analyze_title_toc`.
        """
        return self._title_next_anchor.get(key)

    # Matches a body section heading: "Item 1A. Risk Factors", "Item 8. Financial
    # Statements …". The required title after the number (``\S``) is what separates
    # a real heading from a bare "Item 1A" TOC cell and from inline prose
    # cross-references like "… in Part II, Item 7 of this Form 10-K …" (which start
    # with "Part", not "Item N.").
    _BODY_ITEM_HEADER = re.compile(r'^Item\s+(\d+)([A-Z]?)\.?\s+\S', re.IGNORECASE)
    _BODY_PART_DIVIDER = re.compile(r'^Part\s+([IVX]+)\b', re.IGNORECASE)

    def _analyze_body_item_headers(self, html_content: str, tree=None) -> Dict[str, str]:
        """Map items from bold body headings instead of TOC links.

        Some filers (notably Goldman Sachs and Citigroup — large bank 10-Ks)
        carry the SEC item structure only in a *link-less* TOC (item labels and
        page numbers, no anchors), so every anchor/link-based TOC parser finds
        nothing usable. But the document body marks each item with a bold
        heading like "Item 1A. Risk Factors", each immediately preceded by an
        empty anchor ``<div id="…">``. This scans those headers in document
        order, tracks Part context from sibling "PART II" dividers, and resolves
        each item to its nearest preceding anchor id — returning the same
        ``{section_key: anchor_id}`` contract as the link-based parsers, so the
        standard boundary/slicing pipeline works unchanged (edgartools-sldz).
        """
        try:
            tree = self._ensure_tree(html_content, tree)
        except Exception:
            logger.debug("Body-header scan: tree parse failed", exc_info=True)
            return {}

        mapping: Dict[str, str] = {}
        current_part: Optional[str] = None
        last_anchor_id: Optional[str] = None

        for el in tree.iter():
            tag = el.tag
            if not isinstance(tag, str):
                continue
            # Track the most recent element carrying an id; for a body heading
            # this is the empty anchor div placed immediately before it.
            eid = el.get('id')
            if eid:
                last_anchor_id = eid

            text = (el.text_content() or '').strip()
            # A heading is short; an over-long text means we're looking at an
            # ancestor container that wraps the heading plus its body — skip it
            # and let the inner heading element match.
            if not text or len(text) > 200:
                continue
            if not self._is_bold_header(el, tag):
                continue

            part_m = self._BODY_PART_DIVIDER.match(text)
            if part_m and not re.search(r'item\s+\d', text, re.IGNORECASE):
                current_part = f"Part {part_m.group(1).upper()}"
                continue

            item_m = self._BODY_ITEM_HEADER.match(text)
            if not item_m:
                continue
            if not last_anchor_id:
                continue
            item_name = f"Item {item_m.group(1)}{item_m.group(2).upper()}"
            key = self._make_section_key(item_name, current_part)
            # First occurrence in document order wins (the body heading; a
            # link-less TOC has no competing "Item N. Title" span).
            if key:
                mapping.setdefault(key, last_anchor_id)

        return mapping

    @staticmethod
    def _is_bold_header(el, tag: str) -> bool:
        """Heuristic: is this element styled as a heading?

        True for semantic heading tags and for elements whose own inline style
        is bold (``font-weight:700`` / ``bold``). Body prose is not bold, so this
        plus the strict heading-text patterns keeps inline references out.
        """
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return True
        style = (el.get('style') or '').lower()
        m = re.search(r'font-weight:\s*(bold|\d+)', style)
        if not m:
            return False
        val = m.group(1)
        return val == 'bold' or (val.isdigit() and int(val) >= 600)

    # ---- Agent-specific TOC parsers ----

    def _find_toc_table(self, tree, headings: List[str] = None) -> Optional[object]:
        """
        Locate the TOC <table> element by searching for a known heading.

        Args:
            tree: Parsed lxml HTML tree
            headings: List of heading texts to search for (case-insensitive).
                      Defaults to ["TABLE OF CONTENTS", "INDEX"].

        Returns:
            The first <table> element following the heading, or None.
        """
        if headings is None:
            headings = ['TABLE OF CONTENTS', 'INDEX']

        headings_upper = [h.upper() for h in headings]

        def _find_table_in_siblings(element):
            """Search following siblings (and their descendants) for a <table>."""
            for following in element.itersiblings():
                if not isinstance(following.tag, str):
                    continue
                if following.tag == 'table':
                    return following
                tables = following.xpath('.//table')
                if tables:
                    return tables[0]
            return None

        # Search block-level and inline-heading elements likely to contain a TOC heading.
        # Restricting to these tags avoids calling text_content() on every node in a
        # large document (which recursively traverses subtrees).
        _heading_tags = ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                         'b', 'strong', 'span', 'td', 'th', 'center')
        for el in tree.iter(*_heading_tags):
            try:
                text = (el.text_content() or '').strip().upper()
            except (ValueError, AttributeError):
                continue
            if not text:
                continue
            # Check for exact or near-exact match
            for heading in headings_upper:
                if text == heading or text == heading + '.':
                    # Walk up to 3 levels looking for a sibling table
                    current = el
                    for _ in range(3):
                        table = _find_table_in_siblings(current)
                        if table is not None:
                            return table
                        parent = current.getparent()
                        if parent is None:
                            break
                        current = parent

        return None

    def _parse_item_from_text(self, text: str) -> Optional[str]:
        """
        Extract a normalized item/part name from TOC entry text.

        Handles formats like:
        - "Item 1." / "ITEM 1A." / "Item 1A. Risk Factors"
        - "Part I" / "PART II."

        Returns:
            Normalized name like "Item 1A" or "Part II", or None.
        """
        text = text.strip()
        # Strip zero-width spaces
        text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

        item_match = re.match(r'(?:item|ITEM)\s+(\d+[A-Za-z]?)', text, re.IGNORECASE)
        if item_match:
            return f"Item {item_match.group(1).upper()}"

        part_match = re.match(r'(?:part|PART)\s+([IVXivx]+)', text, re.IGNORECASE)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        # Keyword fallback (Business → Item 1, Risk Factors → Item 1A, …). Agent
        # TOCs sometimes split the "Item N" label and its title into separate
        # cells with different hrefs, so a row grouped by shared href carries only
        # the title ("Business"). The generic parser resolves these via the
        # per-form keyword vocabulary; without this the agent parsers silently
        # drop the row, losing Item 1 on Workiva 10-Ks (GH #837). Explicit Item/
        # Part matches above keep priority, so "Item 1A. Risk Factors" still
        # resolves to Item 1A, not Item 1A-via-keyword.
        matched = self.schema.match_text(text.lower(), use_exclusions=True)
        if matched:
            return matched

        # Allowlisted named sections (Signatures) carry no Item/Part number but
        # are real, retrievable sections that the generic parser recognizes via
        # _is_known_named_section. Without this the agent parsers silently drop
        # them, so the agent path loses part_iv_signatures the generic path finds
        # (edgartools-rbsx). Normalize to the lowercase allowlist token so
        # _make_section_key yields the same key as the generic parser.
        if self._is_known_named_section(text):
            return text.strip().lower()

        return None

    def _item_from_anchor(self, anchor_id: str) -> Optional[str]:
        """
        Extract a normalized item/part name from an anchor ID.

        Handles patterns like:
        - "item_1_business", "item_1a_risk_factors" (DFIN)
        - "ITEM1BUSINESS_392371", "ITEM1ARISKFACTORS_986989" (Toppan Merrill)
        - "item1a", "Item1C" (Novaworks)

        Returns:
            Normalized name like "Item 1A" or None.
        """
        anchor_lower = anchor_id.lower()

        # Match item number + optional single letter suffix.
        # The letter must NOT be followed by another letter (to avoid matching
        # "item1business" as "Item 1B" — the "b" is part of "business", not a suffix).
        item_match = re.search(r'item[_\s]*(\d+)([a-z]?)(?![a-z])', anchor_lower)
        if item_match:
            num = item_match.group(1)
            letter = item_match.group(2).upper()
            return f"Item {num}{letter}"

        # Require a left delimiter (start, separator, '#', or '-') so the 'part'
        # token is a real word boundary — otherwise 'counterparties' matches as
        # 'Part I' and pollutes the part context of every item parsed afterward.
        part_match = re.search(r'(?:^|[_\s#-])part[_\s]*([ivx]+)', anchor_lower)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        return None

    @staticmethod
    def _count_item_links(table) -> int:
        """Count how many internal links in a table look like item references."""
        count = 0
        for link in table.xpath('.//a[@href]'):
            href = (link.get('href', '') or '').strip()
            if not href.startswith('#'):
                continue
            text = (link.text_content() or '').strip()
            if re.search(r'item\s+\d', text, re.IGNORECASE):
                count += 1
            elif re.search(r'item[_]?\d', href, re.IGNORECASE):
                count += 1
        return count

    def _find_toc_table_by_links(self, tree) -> Optional[object]:
        """
        Fallback: locate the TOC table by finding the table with the most item links.

        Used when _find_toc_table fails because there's no explicit heading
        (some Toppan and Novaworks filings omit the heading).

        Returns:
            The table element with >= 5 item links, or None.
        """
        best_table = None
        best_count = 0

        for table in tree.xpath('//table'):
            count = self._count_item_links(table)
            if count > best_count:
                best_count = count
                best_table = table

        # Require at least 5 item links to qualify as a TOC
        return best_table if best_count >= 5 else None

    def _find_best_toc_table(self, tree, headings: List[str]) -> Optional[object]:
        """
        Find the best TOC table using heading-based search with link-based fallback.

        First tries heading-based search. If the found table has fewer than 5
        item links, falls back to the link-based search which finds the table
        with the highest concentration of item links.

        Args:
            tree: Parsed HTML tree
            headings: Heading text patterns to search for

        Returns:
            Table element, or None.
        """
        toc_table = self._find_toc_table(tree, headings)
        if toc_table is not None and self._count_item_links(toc_table) >= 5:
            return toc_table
        # Heading table was absent or too small — try link-based detection
        return self._find_toc_table_by_links(tree)

    @staticmethod
    def _part_rank(label: Optional[str]) -> Optional[int]:
        """Document-order rank of a Part label from its roman numeral.

        "Part I" -> 1, "Part II" -> 2, "Part IV" -> 4. Tolerates formatting
        differences ("IV", "part iv"). Returns None when no roman numeral is
        present.
        """
        m = re.search(r'[ivxlcdm]+', label or '', re.IGNORECASE)
        if not m:
            return None
        values = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}
        total = prev = 0
        for ch in reversed(m.group().lower()):
            v = values[ch]
            total += -v if v < prev else v
            prev = max(prev, v)
        return total

    def _make_section_key(self, item_name: str, current_part: Optional[str]) -> Optional[str]:
        """
        Build a section mapping key, adding part context when available.

        When no part context was detected, infer the canonical part from the item
        number for forms whose items are unique across parts (10-K: Items 1–4 are
        Part I, 5–9 Part II, 10–14 Part III, 15–16 Part IV). This yields a
        consistent ``part_ii_item_7`` key instead of a bare ``Item 7`` on filings
        where the TOC lacked explicit Part headers (edgartools-3usf). 10-Q items
        repeat across parts, so its schema supplies no ranges and the bare key is
        kept — a 10-Q part must be detected, never inferred.

        Rejects a spurious *back-reference* by returning ``None``: on a unique-item
        form an item has exactly one valid Part, so when the detected
        ``current_part`` comes *after* the item's canonical Part the anchor was
        matched on a cross-reference, not the real heading — typically the Item 15
        exhibit index in Part IV that cites "Item 1A …". Emitting a
        ``part_iv_item_1`` key there would shadow the real Part I section in the
        unconstrained ``sections.get_item("1")`` accessor and silently return Risk
        Factors instead of Business (GH #836). Retrieval of a dropped section
        falls through to the canonical-Part key or the legacy parser (same path as
        GH #821, whose GS mislabel — Item 1 under Part II — is also a back-ref).

        A detected part *before* the canonical Part is left untouched: that is a
        coarse TOC with a single Part header preceding later-Part items (Item 7
        listed under the lone "Part I" header), where the detected key is the
        established behavior and dropping it would lose a real section.

        Args:
            item_name: Normalized item name like "Item 1A"
            current_part: Current part context like "Part I", or None

        Returns:
            Key like "part_i_item_1a", a bare "Item 1A" when no part is known, or
            ``None`` when the detected part is later than the item's only valid
            part (a back-reference).
        """
        canonical_part = self.schema.part_for_item(item_name)
        if current_part:
            if canonical_part:
                cur_rank = self._part_rank(current_part)
                can_rank = self._part_rank(canonical_part)
                if cur_rank is not None and can_rank is not None and cur_rank > can_rank:
                    return None
            effective_part = current_part
        else:
            effective_part = canonical_part
        if effective_part:
            part_key = effective_part.lower().replace(' ', '_')
            item_key = item_name.lower().replace(' ', '_')
            return f"{part_key}_{item_key}"
        return item_name

    @staticmethod
    def _ensure_tree(html_content: str, tree=None):
        """Return the pre-parsed tree or parse from html_content."""
        if tree is not None:
            return tree
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
        return lxml_html.fromstring(html_content)

    def _analyze_workiva_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Workiva-specific TOC parser.

        Workiva TOCs use a 3-column table with split <a> tags sharing the same
        UUID href: [Item label] [Title] [Page number]. Anchors are UUID-style
        (e.g., #i719388195b384d85a4e238ad88eba90a_13).

        Strategy:
        1. Find TOC table after "TABLE OF CONTENTS" heading
        2. Process each <tr> — group <a> tags by shared href
        3. Combine text from grouped links to reassemble item + title
        4. Extract item number from combined text (anchor IDs are opaque UUIDs)
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['TABLE OF CONTENTS'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = self.schema.seed_part
            rows = toc_table.xpath('.//tr')

            for row in rows:
                row_text = (row.text_content() or '').strip()
                links = row.xpath('.//a[@href]')
                if not links:
                    # A text-only row may be a bare "PART IV" header carrying no
                    # link. Track it so a numberless named section that follows
                    # (Signatures) inherits the right Part context (edgartools-rbsx);
                    # numbered 10-K items infer their Part from the item number, so
                    # this only changes sections that have no number to infer from.
                    part = self._parse_item_from_text(row_text)
                    if part and part.startswith('Part'):
                        current_part = part
                    continue

                # Group links by href
                href_groups: Dict[str, List[str]] = {}
                href_order = []
                for link in links:
                    href = link.get('href', '').strip()
                    if not href.startswith('#'):
                        continue
                    text = (link.text_content() or '').strip()
                    if not text:
                        continue
                    if href not in href_groups:
                        href_groups[href] = []
                        href_order.append(href)
                    href_groups[href].append(text)

                for href in href_order:
                    texts = href_groups[href]
                    anchor_id = href[1:]

                    # Skip page-number-only entries (single short numeric text)
                    if len(texts) == 1 and re.match(r'^\d{1,3}$', texts[0]):
                        continue

                    # Filter out page numbers from multi-text groups
                    non_page_texts = [t for t in texts if not re.match(r'^\d{1,3}$', t)]
                    combined = ' '.join(non_page_texts)

                    # Try to parse an item/part name from the combined text
                    parsed = self._parse_item_from_text(combined)

                    # Workiva sometimes renders the "Item N." label as plain
                    # (non-link) cell text while only the title and page number
                    # are links, so the href-grouped text carries the title alone
                    # ("Disclosure Regarding Foreign Jurisdictions …") with no
                    # item marker. When the row holds a single anchor, recover the
                    # number from the full row text, which still reads "Item 9C.
                    # <title>" (edgartools-rbsx). Guarded to single-anchor rows so
                    # a multi-item row can't mis-attribute one row's number.
                    if not parsed and len(href_order) == 1:
                        parsed = self._parse_item_from_text(row_text)

                    if not parsed:
                        continue

                    # Track part context
                    if parsed.startswith('Part'):
                        current_part = parsed
                        continue

                    # Verify target exists
                    if find_anchor_targets(tree, anchor_id):
                        key = self._make_section_key(parsed, current_part)
                        if key and key not in mapping:
                            mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Workiva TOC parser failed", exc_info=True)
            return {}

    def _analyze_dfin_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Donnelley/DFIN-specific TOC parser.

        DFIN TOCs use semantic anchor IDs (e.g., #item_1_business) and may use
        "INDEX" as the heading instead of "TABLE OF CONTENTS". Links are typically
        one per cell with the title text (not split like Workiva/Toppan).

        Strategy:
        1. Find TOC region (try "INDEX" first, then "TABLE OF CONTENTS")
        2. Extract all internal <a> links from the TOC table
        3. Derive item number from the semantic anchor ID (most reliable for DFIN)
        4. Fall back to text-based extraction when anchor doesn't contain item pattern
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            # DFIN typically uses "INDEX" but some use "TABLE OF CONTENTS"
            toc_table = self._find_toc_table(tree, ['INDEX', 'TABLE OF CONTENTS'])
            if toc_table is None:
                # DFIN may also have links without a formal TOC table — fall back
                # to scanning all links but preferring semantic anchors
                return self._analyze_dfin_links(tree)

            mapping = {}
            current_part = self.schema.seed_part
            rows = toc_table.xpath('.//tr')

            # Walk rows in order so text-only "PART I"/"PART II" rows update
            # part context for the item links that follow.
            for row in rows:
                row_text = (row.text_content() or '').strip()
                links = row.xpath('.//a[@href]')

                if not links:
                    # Text-only row — may be a part header like "PART I"
                    if row_text:
                        part_from_text = self._parse_item_from_text(row_text)
                        if part_from_text and part_from_text.startswith('Part'):
                            current_part = part_from_text
                    continue

                for link in links:
                    href = link.get('href', '').strip()
                    if not href.startswith('#'):
                        continue
                    text = (link.text_content() or '').strip()
                    if not text:
                        continue

                    anchor_id = href[1:]

                    # Skip page numbers
                    if re.match(r'^\d{1,3}$', text):
                        continue

                    # DFIN anchors are semantic — extract item from anchor ID
                    parsed = self._item_from_anchor(anchor_id)

                    # Fall back to text if anchor doesn't have item pattern
                    if not parsed:
                        parsed = self._parse_item_from_text(text)

                    if not parsed:
                        continue

                    # Track part context
                    if parsed.startswith('Part'):
                        current_part = parsed
                        continue

                    if find_anchor_targets(tree, anchor_id):
                        key = self._make_section_key(parsed, current_part)
                        if key and key not in mapping:
                            mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("DFIN TOC parser failed", exc_info=True)
            return {}

    def _analyze_dfin_links(self, tree) -> Dict[str, str]:
        """
        Fallback for DFIN filings without a formal TOC table.

        Scans all internal links for semantic anchor IDs like #item_1_business.
        DFIN anchors are distinctive (underscore-separated, descriptive) so we can
        identify TOC-like links by their anchor pattern alone.
        """
        mapping = {}
        current_part = self.schema.seed_part

        for link in tree.xpath('//a[@href]'):
            href = link.get('href', '').strip()
            if not href.startswith('#'):
                continue
            anchor_id = href[1:]

            # Only accept semantic DFIN-style anchors (contain item_ or part_)
            parsed = self._item_from_anchor(anchor_id)
            if not parsed:
                continue

            if parsed.startswith('Part'):
                current_part = parsed
                continue

            if find_anchor_targets(tree, anchor_id):
                key = self._make_section_key(parsed, current_part)
                if key and key not in mapping:
                    mapping[key] = anchor_id

        return mapping

    def _analyze_novaworks_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Novaworks-specific TOC parser.

        Novaworks TOCs use combined text in single <a> tags (e.g.,
        "ITEM 1A. Risk Factors") with short anchors (#item1a, #Item1C).
        Known quirks:
        - Item 1 often shares anchor with Part I (#part1)
        - Anchor casing is inconsistent (#item1a vs #Item1C)
        - Page numbers are separate <a> tags with class="tocPGNUM"

        Strategy:
        1. Find TOC table after heading
        2. Parse combined "ITEM X. Title" text from each <a>
        3. Handle shared Part/Item anchors by accepting #partN for Item 1
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['INDEX', 'TABLE OF CONTENTS'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = self.schema.seed_part
            links = toc_table.xpath('.//a[@href]')

            for link in links:
                href = link.get('href', '').strip()
                if not href.startswith('#'):
                    continue
                text = (link.text_content() or '').strip()
                if not text:
                    continue

                anchor_id = href[1:]

                # Skip page number links
                if re.match(r'^\d{1,3}$', text):
                    continue

                # Parse item from the combined text (e.g., "ITEM 1A. Risk Factors")
                parsed = self._parse_item_from_text(text)
                if not parsed:
                    continue

                # Track part context
                if parsed.startswith('Part'):
                    current_part = parsed
                    continue

                # Verify target exists
                if find_anchor_targets(tree, anchor_id):
                    key = self._make_section_key(parsed, current_part)
                    if key and key not in mapping:
                        mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Novaworks TOC parser failed", exc_info=True)
            return {}

    def _analyze_toppan_toc(self, html_content: str, tree=None) -> Dict[str, str]:
        """
        Toppan Merrill-specific TOC parser.

        Toppan TOCs split links across cells like Workiva: "ITEM 1." in one <td>,
        "BUSINESS" in the next, both sharing the same href. Anchors are descriptive
        with numeric suffixes (e.g., #ITEM1BUSINESS_392371). Text may contain
        zero-width spaces (&#8203; / U+200B).

        Strategy:
        1. Find TOC table (may use "INDEX" or "TABLE OF CONTENTS" heading)
        2. Group <a> tags per row by shared href
        3. Strip zero-width spaces from text
        4. Combine texts and extract item number
        """
        try:
            tree = self._ensure_tree(html_content, tree)

            toc_table = self._find_best_toc_table(tree, ['TABLE OF CONTENTS', 'INDEX'])
            if toc_table is None:
                return {}

            mapping = {}
            current_part = self.schema.seed_part
            rows = toc_table.xpath('.//tr')

            for row in rows:
                links = row.xpath('.//a[@href]')
                if not links:
                    continue

                # Group links by href
                href_groups: Dict[str, List[str]] = {}
                href_order = []
                for link in links:
                    href = link.get('href', '').strip()
                    if not href.startswith('#'):
                        continue
                    text = (link.text_content() or '').strip()
                    # Strip zero-width spaces
                    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
                    text = text.replace('\xa0', ' ')  # non-breaking space
                    text = text.strip()
                    if not text:
                        continue
                    if href not in href_groups:
                        href_groups[href] = []
                        href_order.append(href)
                    href_groups[href].append(text)

                for href in href_order:
                    texts = href_groups[href]
                    anchor_id = href[1:]

                    # Filter out page numbers
                    non_page_texts = [t for t in texts if not re.match(r'^\d{1,3}$', t)]
                    if not non_page_texts:
                        continue

                    combined = ' '.join(non_page_texts)

                    # Try text first (e.g., "ITEM 1. BUSINESS")
                    parsed = self._parse_item_from_text(combined)

                    # Fall back to anchor ID (e.g., ITEM1BUSINESS_392371)
                    if not parsed:
                        parsed = self._item_from_anchor(anchor_id)

                    if not parsed:
                        continue

                    # Track part context
                    if parsed.startswith('Part'):
                        current_part = parsed
                        continue

                    if find_anchor_targets(tree, anchor_id):
                        key = self._make_section_key(parsed, current_part)
                        if key and key not in mapping:
                            mapping[key] = anchor_id

            return mapping

        except Exception:
            logger.debug("Toppan Merrill TOC parser failed", exc_info=True)
            return {}

    def _extract_preceding_item_label(self, link_element) -> str:
        """
        Extract item/part label from preceding context.

        Handles table-based TOCs where item number is in a separate cell:
        <td>Item 1.</td><td><a href="...">Business</a></td>

        Also handles nested structures like:
        <td>Item 1.</td><td><div><span><a href="...">Business</a></span></div></td>

        Args:
            link_element: The <a> element

        Returns:
            Item label like "Item 1", "Item 1A", "Part I" or empty string
        """
        try:
            # Traverse up to find the containing <td> or <th> (up to 5 levels)
            current = link_element
            td_element = None

            for _ in range(5):
                parent = current.getparent()
                if parent is None:
                    break

                if parent.tag in ['td', 'th']:
                    td_element = parent
                    break

                current = parent

            # If we found a <td>, check ALL preceding siblings in the row
            # This handles TOCs where item number is not in the immediately adjacent cell
            # Example: ['Business', 'I', '1', '5'] where '1' is the item number
            if td_element is not None:
                # Check all preceding siblings (rightmost to leftmost)
                prev_sibling = td_element.getprevious()
                while prev_sibling is not None:
                    if prev_sibling.tag in ['td', 'th']:
                        prev_text = (prev_sibling.text_content() or '').strip()

                        # Look for "Item X" or just "X" (bare number) pattern
                        # Match full format: "Item 1A"
                        item_match = re.match(r'(Item\s+\d+[A-Z]?)\.?\s*$', prev_text, re.IGNORECASE)
                        if item_match:
                            return item_match.group(1)

                        # Match bare item number: "1A" or "1". Page numbers
                        # (50, 108, etc.) are filtered by capping the
                        # accepted range to the form's known maximum.
                        # Without `form` we fall back to 15 (legacy behaviour).
                        # PPG 10-Q `0000079879-26-000170` triggered the bug
                        # this guard fixes: a page-number `<td>8</td>` was
                        # interpreted as "Item 8", producing a phantom
                        # `part_i_item_8` on a form that has no Item 8.
                        # Leading digit must be 1-9 (no zero-padded
                        # forms like `08` or `01` — those are page
                        # numbers, not item identifiers). Matches the
                        # tight `[1-9]` prefix of the original regex
                        # rather than allowing any `\d`.
                        max_item_num = self.schema.max_bare_item
                        bare_item_match = re.match(r'^([1-9]\d?)([A-Za-z]?)\.?\s*$', prev_text, re.IGNORECASE)
                        if bare_item_match and 1 <= int(bare_item_match.group(1)) <= max_item_num:
                            item_num = bare_item_match.group(1)
                            item_letter = bare_item_match.group(2).upper()
                            return f"Item {item_num}{item_letter}"

                        # Match part: "Part I" or just "I"
                        part_match = re.match(r'(Part\s+[IVX]+)\.?\s*$', prev_text, re.IGNORECASE)
                        if part_match:
                            return part_match.group(1)

                        # Match bare part: "I", "II", etc.
                        bare_part_match = re.match(r'^([IVX]+)\.?\s*$', prev_text)
                        if bare_part_match:
                            return f"Part {bare_part_match.group(1)}"

                    prev_sibling = prev_sibling.getprevious()

            # Also check immediate parent's text for inline patterns (div/span structures)
            parent = link_element.getparent()
            if parent is not None and parent.tag in ['div', 'span', 'p']:
                if parent.text:
                    text_before = parent.text.strip()
                    item_match = re.search(r'(Item\s+\d+[A-Z]?)\.?\s*$', text_before, re.IGNORECASE)
                    if item_match:
                        return item_match.group(1)

                    part_match = re.search(r'(Part\s+[IVX]+)\.?\s*$', text_before, re.IGNORECASE)
                    if part_match:
                        return part_match.group(1)

        except Exception:
            logger.debug("Preceding-item-label extraction failed", exc_info=True)

        return ''

    def _extract_part_context(self, text: str) -> Optional[str]:
        """Extract normalized part label from text, e.g., "Part II"."""
        part_match = re.match(r'^\s*part\s+([ivx]+)\b', text, re.IGNORECASE)
        if not part_match:
            return None

        return f"Part {part_match.group(1).upper()}"

    def _infer_part_from_row_context(self, link_element) -> Optional[str]:
        """
        Infer part context from nearby table rows.

        Many TOCs place part headers ("PART I", "PART II", ...) in standalone
        rows that do not contain links. This method finds the nearest preceding
        sibling row with a part marker and returns it as context for the current
        linked item row.
        """
        max_rows_to_scan = 200

        try:
            # Find containing row for this link.
            current = link_element
            row = None
            for _ in range(10):
                parent = current.getparent()
                if parent is None:
                    break
                if parent.tag == 'tr':
                    row = parent
                    break
                current = parent

            if row is None:
                return None

            # Search backwards through previous rows for a standalone part header.
            prev = row.getprevious()
            rows_scanned = 0
            while prev is not None and rows_scanned < max_rows_to_scan:
                rows_scanned += 1

                if prev.tag == 'tr':
                    # Check each cell separately to avoid row text concatenation
                    # artifacts like "PART I3" when a page number is in another cell.
                    cells = prev.xpath('./td|./th')
                    if cells:
                        for cell in cells:
                            cell_text = (cell.text_content() or '').strip()
                            part = self._extract_part_context(cell_text)
                            if part:
                                return part
                    else:
                        prev_text = (prev.text_content() or '').strip()
                        part = self._extract_part_context(prev_text)
                        if part:
                            return part

                prev = prev.getprevious()

        except Exception:
            logger.debug("Part inference from row context failed", exc_info=True)
            return None

        return None

    def _is_section_link(self, text: str, anchor_id: str = '', preceding_item: str = '') -> bool:
        """
        Check if link represents a section reference.

        Checks link text, anchor ID, and preceding context to handle cases where:
        - Text is descriptive (e.g., "Executive Compensation")
        - Anchor ID contains item number (e.g., "item_11_executive_compensation")
        - Item number is in preceding table cell (e.g., <td>Item 1.</td><td><a>Business</a></td>)

        Args:
            text: Link text
            anchor_id: Anchor ID from href (without #)
            preceding_item: Item/part label from preceding context (e.g., "Item 1A")

        Returns:
            True if this appears to be a section link
        """
        if not text:
            return False

        # First check if there's a preceding item label (table-based TOC)
        if preceding_item:
            return True

        # Then check anchor ID for item/part patterns (most reliable)
        if anchor_id:
            anchor_lower = anchor_id.lower()
            # Match patterns like: item_1, item_1a, item1, item1a, part_i, part_ii, etc.
            if re.search(r'item_?\d+[a-z]?', anchor_lower):
                return True
            if re.search(r'part_?[ivx]+', anchor_lower):
                return True

        # Then check text (with relaxed length limit for descriptive section names)
        if len(text) > 150:  # Increased from 100 to accommodate longer section titles
            return False

        # Check against known patterns
        for pattern, _ in self.section_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # Also consider links with section keywords
        if len(text) < 100 and any(keyword in text.lower() for keyword in
                                   ['item', 'part', 'business', 'risk', 'properties', 'legal',
                                    'compensation', 'ownership', 'governance', 'directors']):
            return True

        return False

    def _normalize_section_name(self, text: str, anchor_id: str = '', preceding_item: str = '') -> str:
        """
        Normalize section name for consistent lookup.

        Prioritizes:
        1. Preceding item label (table-based TOC)
        2. Anchor ID pattern
        3. Text-based normalization

        Args:
            text: Link text
            anchor_id: Anchor ID from href (without #)
            preceding_item: Item/part label from preceding context

        Returns:
            Normalized section name (e.g., "Item 1A", "Part II")
        """
        text = text.strip()

        # HIGHEST PRIORITY: Use preceding item label if available (table-based TOC)
        if preceding_item:
            # Clean up and normalize the preceding item
            item_match = re.match(r'item\s+(\d+[a-z]?)', preceding_item, re.IGNORECASE)
            if item_match:
                return f"Item {item_match.group(1).upper()}"

            part_match = re.match(r'part\s+([ivx]+)', preceding_item, re.IGNORECASE)
            if part_match:
                return f"Part {part_match.group(1).upper()}"

        # SECOND PRIORITY: Try to extract from anchor ID
        if anchor_id:
            anchor_lower = anchor_id.lower()

            # Match item patterns: item_1a, item1a, item_1_business, etc.
            item_match = re.search(r'item_?(\d+[a-z]?)', anchor_lower)
            if item_match:
                item_num = item_match.group(1).upper()
                return f"Item {item_num}"

            # Match part patterns: part_i, part_ii, parti, partii, etc.
            part_match = re.search(r'part_?([ivx]+)', anchor_lower)
            if part_match:
                part_num = part_match.group(1).upper()
                return f"Part {part_num}"

        # THIRD PRIORITY: Text-based normalization
        # Handle common Item patterns in text
        item_match = re.match(r'item\s+(\d+[a-z]?)', text, re.IGNORECASE)
        if item_match:
            return f"Item {item_match.group(1).upper()}"

        # Handle Part patterns
        part_match = re.match(r'part\s+([ivx]+)', text, re.IGNORECASE)
        if part_match:
            return f"Part {part_match.group(1).upper()}"

        # Text-keyword fallback, driven by the per-form schema. The keyword→item
        # vocabulary (Business→Item 1, Financial Statements→Item 8, ...) is
        # 10-K-shaped, so the schema scopes it per form: 10-K applies the full
        # table; 10-Q keeps only the safe Risk-Factors→Item 1A overlap and skips
        # everything else (returning "" so `_build_section_mapping` doesn't emit
        # bogus `part_i_<text>` keys); other forms (20-F, ...) have no rules and
        # return the raw text. This replaces the old `if self.form in (...)`
        # branches with declarative data (edgartools-fhno).
        text_lower = text.lower()
        matched = self.schema.match_text(text_lower, use_exclusions=True)
        if matched:
            return matched
        if self.schema.skip_unmatched_text:
            return ""
        return text  # Return as-is if no normalization applies

    def _get_section_type_and_order(self, text: str) -> Tuple[str, int]:
        """Get section type and order for sorting."""
        # Title-based forms (424B): the section name is a vocabulary key
        # ('use_of_proceeds', ...), ordered by the body position recorded during
        # _analyze_title_toc so boundaries follow physical document order. Falls
        # back to the schema's canonical declaration order if a key wasn't ranked
        # (e.g. ordering by a direct caller rather than the TOC parser). Gated on
        # title_based so Item forms reach the item-number logic below unchanged.
        if self.schema.title_based:
            rank = self._title_section_order.get(text)
            if rank is None:
                return 'section', self.schema.section_order(text)
            return 'section', rank

        text_lower = text.lower()

        # Part-aware section names (e.g., part_i_item_1, part_ii_item_1a)
        # These names are generated for 10-Q filings to distinguish Part I and Part II items
        part_aware_match = re.search(r'part_([ivx]+)_item[_\s]*(\d+)([a-z]?)', text_lower)
        if part_aware_match:
            part_roman = part_aware_match.group(1)
            item_num = int(part_aware_match.group(2))
            item_letter = part_aware_match.group(3) or ''
            part_num = self._roman_to_int(part_roman)
            # Order: Part I Item 1=100_1000, Part II Item 1=200_1000
            # Part multiplier ensures Part I items come before Part II items
            item_order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
            order = part_num * 100000 + item_order
            return 'item', order

        # Standard Items (Item 1, Item 1A, etc.)
        item_match = re.search(r'item[\s_]*(\d+)([a-z]?)', text_lower)
        if item_match:
            item_num = int(item_match.group(1))
            item_letter = item_match.group(2) or ''
            # Order: Item 1=1000, Item 1A=1001, Item 2=2000, etc.
            order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
            return 'item', order

        # Allowlisted named sections (Signatures) carry no item number and sit at
        # the very end of the filing, after every item. Order them after the last
        # item — within their Part for a part-prefixed key ("part_iv_signatures"),
        # or globally last for a bare key — so the trailing "part_iv_" doesn't fall
        # through to the Part rule below and sort them as a bare "Part IV" header
        # (order 400). That misorder placed Signatures first and handed it the next
        # section's anchor as its end boundary — a backward end-anchor that emptied
        # its text and dropped it from document.sections (edgartools-nqzc).
        named_match = re.match(r'(?:part_([ivx]+)_)?([a-z_]+)$', text_lower)
        if named_match and self._is_known_named_section(named_match.group(2)):
            part_roman = named_match.group(1)
            if part_roman:
                return 'section', self._roman_to_int(part_roman) * 100000 + 99000
            return 'section', 9_900_000

        # Parts (Part I, Part II, etc.)
        part_match = re.search(r'part[\s_]*([ivx]+)', text_lower)
        if part_match:
            part_roman = part_match.group(1)
            part_num = self._roman_to_int(part_roman)
            return 'part', part_num * 100  # Part I=100, Part II=200, etc.

        # Known sections without explicit item numbers, via the per-form schema
        # keyword rules. The order is derived from the matched item name using
        # the same formula as the explicit-item path above (Business→Item 1→1000,
        # Risk Factors→Item 1A→1001, Financial Statements→Item 8→8000, ...), so
        # the keyword table no longer needs its own hand-maintained order
        # constants. Form scoping lives in the schema: 10-Q matches only Risk
        # Factors, other forms match nothing → ('other', 99999) (edgartools-fhno).
        #
        # Exclusions are intentionally NOT applied here, mirroring the historical
        # behaviour where the sort-order lookup (unlike name normalization)
        # ignored the "…and 'item' absent" guard. See form_schema.py.
        matched = self.schema.match_text(text_lower, use_exclusions=False)
        if matched:
            m = re.match(r'item\s+(\d+)([a-z]?)', matched, re.IGNORECASE)
            if m:
                item_num = int(m.group(1))
                item_letter = m.group(2) or ''
                order = item_num * 1000 + (ord(item_letter.upper()) - ord('A') + 1 if item_letter else 0)
                return 'item', order

        return 'other', 99999

    def _roman_to_int(self, roman: str) -> int:
        """Convert roman numerals to integers."""
        roman_map = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}
        roman = roman.lower()
        result = 0
        prev = 0

        for char in reversed(roman):
            value = roman_map.get(char, 0)
            if value < prev:
                result -= value
            else:
                result += value
            prev = value

        return result

    # Named sections that legitimately carry no item number but should still be
    # exposed. Everything else without an item number is descriptive free-text noise.
    _KNOWN_NAMED_SECTIONS = frozenset({'signatures'})
    # A canonical section key: item, optionally part-prefixed (part_ii_item_7).
    # The single-letter suffix admits standard items (1A, 7A, 9A–9C) and
    # legitimate company-specific ones (Caterpillar's Item 1D), not just a–c.
    _CANONICAL_ITEM_KEY = re.compile(r'^(part_[ivxlcdm]+_)?item_\d+[a-z]?$', re.IGNORECASE)
    # A still-unprefixed bare item key ("Item 7") — valid content, wrong shape;
    # the missing-part-prefix normalization is tracked separately (edgartools-3usf).
    _BARE_ITEM_KEY = re.compile(r'^Item\s+\d+[A-Z]?$', re.IGNORECASE)

    @classmethod
    def _is_known_named_section(cls, name: str) -> bool:
        return (name or '').strip().lower() in cls._KNOWN_NAMED_SECTIONS

    def _is_valid_section_key(self, section_name: str, normalized_name: str) -> bool:
        """A section key is valid only if it names a canonical item (optionally
        part-prefixed), a bare ``Item N`` (missing-prefix), or an allowlisted
        named section. Everything else is descriptive free-text noise from the
        raw-text fallback (edgartools-3au1)."""
        if self._CANONICAL_ITEM_KEY.match(section_name):
            return True
        if self._BARE_ITEM_KEY.match(section_name):
            return True
        return self._is_known_named_section(normalized_name)

    def _build_section_mapping(self, toc_sections: List[TOCSection],
                               tree=None) -> Dict[str, str]:
        """Build final section mapping, handling duplicates intelligently.

        For 10-Q filings with part context, generates part-aware section names
        like "part_i_item_1" and "part_ii_item_1" to distinguish sections
        with the same item number across different parts.

        When duplicate entries exist for the same section (e.g., "Item 1." and
        "Business" both normalizing to "Item 1"), validates anchors by checking
        if the target content matches the expected item heading.
        """
        # Sort sections by order
        toc_sections.sort(key=lambda x: x.order)

        mapping = {}
        seen_names = set()

        for section in toc_sections:
            # Skip rows whose text didn't normalise to anything (the
            # 10-Q text fallback returns "" for unrecognised section
            # names — see `_normalize_section_name`). Without this
            # guard, downstream would emit empty-tail keys like
            # `part_i_` and a `SECSectionExtractor` Part-header
            # mis-classification.
            if not section.normalized_name:
                continue
            # A Part label is navigation context, never a content section. Some
            # TOCs (and the Item 15 exhibit index, which cross-references "Part I,
            # Item 1A …") feed bare "Part X" link text through normalization,
            # which would otherwise emit malformed keys like `part_i_part_ii`,
            # `part_iv_part_i`, or a bare `Part I`. Part context is already tracked
            # via `current_part`, so dropping these loses no boundary (edgartools-sldz).
            if re.match(r'^Part\s+[IVXLCDM]+$', section.normalized_name, re.IGNORECASE):
                continue
            # Build the key with part context — detected (section.part) or, when
            # absent, inferred from the item number for 10-K (edgartools-3usf).
            section_name = self._make_section_key(section.normalized_name, section.part)

            # Emit only well-formed keys. The 10-K raw-text fallback in
            # _normalize_section_name returns link text verbatim when no
            # Item/Part/keyword rule matches, leaking two kinds of noise as
            # top-level sections: pure descriptive titles (part_ii_risk_management,
            # "19. Deferred Compensation …") and Item-15 exhibit-index prose that
            # merely *contains* an item number (part_iv_,_item_1a,
            # "in Part II, Item 5 of this report …"). A canonical key is an item
            # (optionally part-prefixed), a still-unprefixed bare "Item N" (the
            # missing-part-prefix case, edgartools-3usf), or an allowlisted named
            # section like Signatures (edgartools-3au1).
            if section_name is None or not self._is_valid_section_key(section_name, section.normalized_name):
                continue

            if section_name in seen_names:
                # Duplicate: validate which anchor is better.
                # Some TOCs have split links: "Item 1." → wrong anchor,
                # "Business" → correct anchor. Check if the new anchor's
                # target content matches the expected section heading.
                if tree is not None and section_name in mapping:
                    existing_anchor = mapping[section_name]
                    new_anchor = section.anchor_id
                    if existing_anchor != new_anchor:
                        if self._anchor_matches_heading(tree, new_anchor, section.normalized_name):
                            if not self._anchor_matches_heading(tree, existing_anchor, section.normalized_name):
                                # New anchor is better — replace
                                mapping[section_name] = new_anchor
                continue

            mapping[section_name] = section.anchor_id
            seen_names.add(section_name)

        return mapping

    def _anchor_matches_heading(self, tree, anchor_id: str, expected_name: str) -> bool:
        """Check if the content near an anchor target matches the expected section heading."""
        targets = find_anchor_targets(tree, anchor_id)
        if not targets:
            return False

        target = targets[0]
        # Look at the next few elements for a heading that matches
        try:
            following = target.xpath('following::*[string-length(normalize-space(text())) > 3][position() <= 3]')
            for el in following:
                el_text = (el.text_content() or '').strip().upper()[:80]
                # Extract item pattern from expected name (e.g., "Item 1" → "ITEM 1")
                item_match = re.search(r'item\s+(\d+[a-z]?)', expected_name, re.IGNORECASE)
                if item_match:
                    item_pattern = f'ITEM {item_match.group(1).upper()}'
                    if item_pattern in el_text:
                        return True
        except Exception:
            logger.debug("Anchor/heading match check failed", exc_info=True)

        return False

    def get_section_suggestions(self, html_content: str) -> List[str]:
        """Get list of available sections that can be extracted."""
        mapping = self.analyze_toc_structure(html_content)
        return sorted(mapping.keys(), key=lambda x: self._get_section_type_and_order(x)[1])


def analyze_toc_for_sections(html_content: str, agent: Optional[str] = None,
                             tree=None, form: Optional[str] = None) -> Dict[str, str]:
    """
    Convenience function to analyze TOC and return section mapping.

    Args:
        html_content: Raw HTML content
        agent: Filing agent name or None
        tree: Pre-parsed lxml tree (optional)
        form: SEC form type ('10-K', '10-Q', '20-F', ...) used to bound
              TOC heuristics. Without it, the analyzer falls back to
              a conservative default that may mis-interpret page-number
              cells as item identifiers on forms with few items.

    Returns:
        Dict mapping section names to anchor IDs
    """
    analyzer = TOCAnalyzer(form=form)
    return analyzer.analyze_toc_structure(html_content, agent=agent, tree=tree)


def find_toc_boundaries(html_content: str) -> Tuple[int, int]:
    """
    Find the start and end positions of the Table of Contents region in HTML.

    This is used by pattern-based section extraction to skip TOC entries
    and only match actual section headers in the document body.

    The function uses two strategies:
    1. Look for explicit "TABLE OF CONTENTS" heading
    2. Fallback: Find tables with Item + page number pattern

    Args:
        html_content: Raw HTML content

    Returns:
        Tuple of (start_position, end_position) for TOC region.
        Returns (0, 0) if no TOC is found.

    Example:
        >>> start, end = find_toc_boundaries(html)
        >>> if start < match_position < end:
        ...     # Skip this match - it's inside the TOC
        ...     continue
    """
    if not html_content:
        return (0, 0)

    # Handle XML declaration
    if html_content.startswith('<?xml'):
        html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

    # Strategy 1: Look for explicit "TABLE OF CONTENTS" heading
    toc_start = html_content.find('TABLE OF CONTENTS')
    if toc_start == -1:
        # Try case-insensitive
        toc_start_lower = html_content.lower().find('table of contents')
        if toc_start_lower > 0:
            toc_start = toc_start_lower

    # Strategy 2: If no heading found, look for table with TOC-like structure
    if toc_start == -1:
        toc_start = _find_toc_table_start(html_content)

    if toc_start == -1:
        return (0, 0)  # No TOC found

    # Find TOC end by locating "SIGNATURES" (last item in most TOCs)
    # then finding the closing </table> tag
    signatures_pos = html_content.find('SIGNATURES', toc_start)
    if signatures_pos == -1:
        # Fallback: look for case-insensitive
        signatures_lower = html_content.lower().find('signatures', toc_start)
        if signatures_lower > 0:
            signatures_pos = signatures_lower

    if signatures_pos > 0:
        # Find the closing </table> after SIGNATURES
        toc_end = html_content.find('</table>', signatures_pos)
        if toc_end > 0:
            # Add length of </table> tag to include it
            toc_end += len('</table>')
            return (toc_start, toc_end)

    # Fallback: estimate TOC end as ~50KB after start (typical TOC size)
    # This is a safety fallback if SIGNATURES isn't found
    return (toc_start, min(toc_start + 50000, len(html_content)))


def _find_toc_table_start(html_content: str) -> int:
    """
    Find the start position of a TOC table by detecting Item + page number pattern.

    This handles filings that don't have an explicit "TABLE OF CONTENTS" heading
    but do have a structured TOC table.

    Args:
        html_content: Raw HTML content

    Returns:
        Start position of TOC table, or -1 if not found
    """
    try:
        tree = lxml_html.fromstring(html_content)
        tables = tree.xpath('//table')

        for table in tables:
            rows = table.xpath('.//tr')
            if len(rows) < 3:
                continue

            # Count rows with TOC-like pattern: "Item X" + page number at end
            toc_like_rows = 0
            for row in rows[:20]:  # Check first 20 rows
                row_text = row.text_content().strip()
                # Pattern: "Item X" followed by page number (1-3 digits) at end
                has_item = re.search(r'Item\s+\d', row_text, re.IGNORECASE)
                has_page_num = re.search(r'\d{1,3}\s*$', row_text)
                if has_item and has_page_num:
                    toc_like_rows += 1

            # If 3+ rows match the pattern, this is likely a TOC table
            if toc_like_rows >= 3:
                # Find the table's position by searching for its first row content
                first_row_text = rows[0].text_content().strip()
                if first_row_text:
                    # Use first 30 chars to find position
                    search_text = first_row_text[:30]
                    pos = html_content.find(search_text)
                    if pos > 0:
                        return pos

    except Exception:
        logger.debug("TOC table-start scan failed", exc_info=True)

    return -1
