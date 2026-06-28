"""
Section extraction for SEC filings using Table of Contents analysis.

This system uses TOC structure to extract specific sections like "Item 1",
"Item 1A", etc. from SEC filings. This approach works consistently across
all SEC filings regardless of whether they use semantic anchors or generated IDs.
"""
import bisect
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from lxml import etree
from lxml import html as lxml_html

from edgar.documents.document import Document
from edgar.documents.nodes import Node
from edgar.documents.utils.anchor_targets import find_anchor_targets, is_anchor_match
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

logger = logging.getLogger(__name__)

# Canonical title fragment for each 10-K item, used to (a) locate the real
# ITEM header when a TOC anchor lands on a PART header and (b) recognise that a
# short extraction already sits on the correct heading (so a legitimately brief
# item — "incorporated by reference", "Not applicable" — is not over-rescued).
_ITEM_TITLE_PATTERNS = {
    '1': r'BUSINESS',
    '1A': r'RISK\s*FACTORS?',
    '1B': r'UNRESOLVED\s*STAFF\s*COMMENTS?',
    '1C': r'CYBERSECURITY',
    '2': r'PROPERTIES',
    '3': r'LEGAL\s*PROCEEDINGS?',
    '4': r'MINE\s*SAFETY',
    '5': r'MARKET\s*FOR',
    '6': r'(SELECTED|RESERVED)',
    '7': r'MANAGEMENT',
    '7A': r'QUANTITATIVE',
    '8': r'FINANCIAL\s*STATEMENTS?',
    '9': r'CHANGES?\s*IN',
    '9A': r'CONTROLS?',
    '9B': r'OTHER\s*INFORMATION',
    '9C': r'DISCLOSURE',
}


@dataclass
class SectionBoundary:
    """Represents the boundaries of a document section."""
    name: str
    anchor_id: str
    start_element_id: Optional[str] = None
    end_element_id: Optional[str] = None
    start_node: Optional[Node] = None
    end_node: Optional[Node] = None
    text_start: Optional[int] = None  # Character position in full text
    text_end: Optional[int] = None
    confidence: float = 1.0  # Detection confidence (0.0-1.0)
    detection_method: str = 'unknown'  # How section was detected
    # Optional hard end: stop extraction when this exact lxml element is reached,
    # used to bound a section at a block that carries no anchor of its own (the
    # prospectus financial-statements F-pages — gh-878). Takes effect alongside
    # end_element_id; whichever boundary is hit first in document order wins.
    end_element: Optional[object] = None


class SECSectionExtractor:
    """
    Extract specific sections from SEC filings using Table of Contents analysis.

    This uses TOC structure to identify section boundaries and extract content
    between them. Works consistently for all SEC filings.
    """

    def __init__(self, document: Document, agent: Optional[str] = None,
                 form: Optional[str] = None):
        """
        Args:
            document: Document to extract sections from.
            agent: Filing agent name for agent-specific TOC parsing.
            form: SEC form type ('10-K', '10-Q', etc.) used to scope the
                  TOC analyzer's bare-item-number heuristic. Passing this
                  prevents page-number cells from being mis-interpreted
                  as item identifiers on forms with few items.
        """
        self.document = document
        self.agent = agent
        self.form = form
        self.section_map = {}  # Maps section names to canonical names
        self.section_boundaries = {}  # Maps section names to boundaries
        self.toc_analyzer = TOCAnalyzer(form=form)
        self._tree = None  # Cached parsed lxml tree (set by _analyze_sections)
        self._clean_html = None  # HTML with XML declaration stripped
        self._analyze_sections()

    def _parse_html(self, html_content: str):
        """Parse HTML once, stripping XML declaration. Cache the result."""
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
        self._clean_html = html_content
        self._tree = lxml_html.fromstring(html_content)
        return self._tree

    def _analyze_sections(self) -> None:
        """
        Analyze the document using TOC structure to identify section boundaries.

        This creates a map of section names to their anchor positions using
        Table of Contents analysis, which works for all SEC filings.
        """
        # Get the original HTML if available
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            return

        # Parse HTML once and cache the tree for reuse in section extraction
        tree = self._parse_html(html_content)

        # Use TOC analysis to find sections, passing the pre-parsed tree
        # to avoid re-parsing the same HTML inside the analyzer
        toc_mapping = self.toc_analyzer.analyze_toc_structure(
            html_content, agent=self.agent, tree=tree
        )

        if not toc_mapping:
            return  # No sections found

        sec_sections = {}

        for section_name, anchor_id in toc_mapping.items():
            # Verify the anchor target exists (using cached tree)
            target_elements = find_anchor_targets(tree, anchor_id)
            if target_elements:
                element = target_elements[0]

                # Use TOC-based section info
                section_type, order = self.toc_analyzer._get_section_type_and_order(section_name)

                sec_sections[section_name] = {
                    'anchor_id': anchor_id,
                    'element': element,
                    'canonical_name': section_name,
                    'type': section_type,
                    'order': order,
                    'confidence': 0.95,  # TOC-based detection = high confidence
                    'detection_method': 'toc'  # Method: Table of Contents
                }

        if not sec_sections:
            return  # No valid sections found

        # Sort sections by their logical order
        sorted_sections = sorted(sec_sections.items(), key=lambda x: x[1]['order'])

        # Calculate section boundaries
        for i, (section_name, section_data) in enumerate(sorted_sections):
            start_anchor = section_data['anchor_id']

            # End boundary is the start of the next section (if any)
            end_anchor = None
            if i + 1 < len(sorted_sections):
                next_section = sorted_sections[i + 1][1]
                end_anchor = next_section['anchor_id']

            # Title-based forms (424B): tighten the end to the next *TOC entry*
            # (vocabulary or not) so a detected section does not absorb
            # intervening prospectus sections we have no vocabulary for — e.g.
            # "Use of Proceeds" must stop at the next listed section, not run on
            # through Management and the financial statements (edgartools-llmp.3).
            if self.toc_analyzer.schema.title_based:
                tight = self.toc_analyzer.title_section_end(section_name)
                if tight is not None:
                    end_anchor = tight

            self.section_boundaries[section_name] = SectionBoundary(
                name=section_name,
                anchor_id=start_anchor,
                end_element_id=end_anchor,
                confidence=section_data.get('confidence', 0.95),
                detection_method=section_data.get('detection_method', 'toc')
            )

        self.section_map = {name: data['canonical_name'] for name, data in sec_sections.items()}

        # Re-resolve section boundaries whose span is anomalous for their rescue
        # key (edgartools-llmp.1 / D3).
        self._rescue_boundaries()

    # --- Boundary rescue (edgartools-llmp.1 / D3) -------------------------------
    #
    # A "rescue key" is an item that filers commonly defer or merge, so its
    # TOC anchor can land on the wrong place and leave the section's span
    # anomalous. Two anomaly directions are recognised:
    #
    #   * collapsed — the anchor landed on a short incorporation-by-reference
    #     pointer; the real body lives later in an untitled block (the
    #     ExxonMobil / JPMorgan "Financial Section" case, edgartools-rv86 /
    #     GH #873). Handled by _rescue_collapsed_incorporated_financials below.
    #   * oversized — the item swallowed a missing neighbour's content (the
    #     #871 content-bleed class). SEAM ONLY: not yet active here. The bleed
    #     it targets lives on the *pattern* extractor for non-Item forms, which
    #     this TOC engine does not yet serve; the Phase 3 routing flip
    #     (edgartools-llmp.3) is what makes an oversized rescue here meaningful.
    #
    # Phase 1 establishes this structure; the rescue-key set, size bands, and
    # deferred-title vocabulary below move into FormSchema in Phase 2
    # (edgartools-llmp.2), so a new form becomes a schema entry, not new code.

    # Item 7 text that incorporates the MD&A by reference rather than carrying it.
    # The last alternative covers the Chevron-style pointer ("The index to MD&A …
    # is presented in the Financial Table of Contents"), which defers the body to
    # a later 'Financial Section' / 'Financial Table of Contents' supplement
    # rather than to an exhibit — same recovery, different wording (edgartools-gegs).
    _INCORP_RE = re.compile(
        r'reference is made to|incorporated\s+(?:herein\s+)?by\s+reference|appears\s+on\s+pages'
        r'|presented\s+in\s+the\s+financial\s+(?:table\s+of\s+contents|section)',
        re.IGNORECASE,
    )
    # A genuine Item 7 MD&A is many KB; a pointer stub is a sentence or two.
    _STUB_MAX_CHARS = 2000
    # A deferred body anchor must introduce substantially more document (measured
    # in element-index span within the candidate-anchor set) than a pointer stub
    # before it is trusted. Also the cheap pre-gate: an Item 7 that spans at least
    # this many elements to its next anchor is real content, not a pointer.
    _MIN_DEFERRED_SPAN = 1000
    # Deferred (sub-)TOC link text -> canonical item key, for blocks whose link
    # is a section title rather than an "Item N" label.
    _DEFERRED_HEAD_MAP = (
        (re.compile(r"management.{0,3}s\s+discussion\s+and\s+analysis", re.IGNORECASE), 'part_ii_item_7'),
        (re.compile(r"quantitative\s+and\s+qualitative\s+disclosures", re.IGNORECASE), 'part_ii_item_7a'),
        (re.compile(r"^\s*(?:consolidated\s+)?financial\s+statements(?:\s+and\s+supplementary\s+data)?\s*$",
                    re.IGNORECASE), 'part_ii_item_8'),
    )
    _DEFERRABLE_KEYS = ('part_ii_item_7', 'part_ii_item_7a', 'part_ii_item_8')

    def _base_form(self) -> str:
        return (self.form or '').replace('/A', '').strip().upper()

    def _anchor_doc_positions(self):
        """Map id / <a name> -> first document-order index, plus the element total."""
        positions: Dict[str, int] = {}
        total = 0
        if self._tree is None:
            return positions, total
        for idx, el in enumerate(self._tree.iter()):
            total = idx + 1
            eid = el.get('id')
            if eid and eid not in positions:
                positions[eid] = idx
            if el.tag == 'a':
                name = el.get('name')
                if name and name not in positions:
                    positions[name] = idx
        return positions, total

    def _lookup_anchor_indices(self, ids, need_total: bool = False):
        """Document-order index of each requested id / <a name>.

        Resolves only the requested anchors and, unless ``need_total`` is set,
        stops walking as soon as all are found — so the cheap pre-gate does not
        pay a full-document iteration for the overwhelmingly common normal-filer
        case. Returns ``(found, total)``; ``total`` is the full element count when
        the walk ran to completion, else ``None``.
        """
        found: Dict[str, int] = {}
        if self._tree is None:
            return found, None
        targets = {i for i in ids if i}
        idx = -1
        for idx, el in enumerate(self._tree.iter()):
            eid = el.get('id')
            if eid in targets and eid not in found:
                found[eid] = idx
            if el.tag == 'a':
                name = el.get('name')
                if name in targets and name not in found:
                    found[name] = idx
            if not need_total and len(found) == len(targets):
                return found, None
        return found, idx + 1

    def _classify_deferred_link(self, text: str) -> Optional[str]:
        """Classify a (sub-)TOC link's text to a deferrable item key, or None."""
        cleaned = re.sub(r'\s+', ' ', text).strip()
        for rx, key in self._DEFERRED_HEAD_MAP:
            if rx.search(cleaned):
                return key
        norm = self.toc_analyzer._normalize_section_name(cleaned)
        if norm and re.match(r'item', norm, re.IGNORECASE):
            return self.toc_analyzer._make_section_key(norm, None)
        return None

    def _find_supplement_start(self, positions: Dict[str, int], lo: int, hi: int):
        """Find where a deferred financial supplement begins, for MD&A gap-fill.

        The supplement carries its own sub-TOC — a run of forward internal links
        pointing into the region ahead. Its earliest target is the supplement's
        first section, which is where the MD&A starts (and where any exhibit index
        that physically precedes it ends). Returns (target_pos, anchor_id) for the
        earliest such forward link strictly inside ``(lo, hi)``, or (None, None).
        """
        best_pos, best_anchor = None, None
        for idx, el in enumerate(self._tree.iter()):
            if el.tag != 'a':
                continue
            href = el.get('href') or ''
            if not href.startswith('#') or not (lo < idx < hi):
                continue
            target = href[1:]
            tpos = positions.get(target)
            # Forward link whose target is a later section inside the same window.
            if tpos is None or tpos <= idx or not (lo < tpos < hi):
                continue
            if best_pos is None or tpos < best_pos:
                best_pos, best_anchor = tpos, target
        return best_pos, best_anchor

    # Leading navigation breadcrumb that some filers render just before a
    # re-attributed body heading, plus the page number that often trails it.
    _NAV_TEXT_RE = re.compile(r'^(?:table of contents|financial table of contents)$', re.IGNORECASE)
    _NAV_NUM_RE = re.compile(r'^\d{1,4}$')

    def _strip_leading_nav(self, text: Optional[str]) -> Optional[str]:
        """Drop leading blank / navigation-breadcrumb lines from a section's text.

        A re-attributed anchor can land on a page-header breadcrumb ("Table of
        Contents" / "Financial Table of Contents", sometimes followed by the page
        number) that sits immediately before the real heading; strip it so the
        section starts at substantive content. A bare number is only treated as a
        breadcrumb when it follows the textual breadcrumb — a standalone leading
        number with no breadcrumb is kept, since it may be real content (a year,
        a figure) rather than a page number.
        """
        if not text:
            return text
        lines = text.split('\n')
        i = 0
        prev_was_breadcrumb = False
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue  # blank lines don't reset breadcrumb adjacency
            if self._NAV_TEXT_RE.match(stripped):
                prev_was_breadcrumb = True
                i += 1
                continue
            if prev_was_breadcrumb and self._NAV_NUM_RE.match(stripped):
                prev_was_breadcrumb = False
                i += 1
                continue
            break
        return '\n'.join(lines[i:]).lstrip('\n') if i else text

    def _rescue_boundaries(self) -> None:
        """Dispatch the size-band boundary rescues for this document.

        Form-agnostic entry point: each rescue self-gates on the form and
        section shape it applies to, so broadening coverage (Phase 3) is adding
        a call here, not threading new ``if form ==`` branches through callers.
        """
        if self._tree is None:
            return
        self._rescue_collapsed_incorporated_financials()
        self._rescue_trailing_financials()
        # Oversized rescue (#871-bleed class) is a Phase 3 seam — see the module
        # comment above. Intentionally not called: it would be a no-op on the
        # Item/TOC path today and the bleed it targets is on the pattern path.
        # self._rescue_oversized_boundaries()

    def _rescue_collapsed_incorporated_financials(self) -> None:
        if self._base_form() != '10-K' or self._tree is None:
            return
        b7 = self.section_boundaries.get('part_ii_item_7')
        if b7 is None:
            return

        # Cheap pre-gate: a real Item 7 spans most of the body; a pointer stub
        # spans almost nothing before the next item anchor. Resolve only Item 7's
        # own two anchors (stopping the tree walk as soon as both are found) so the
        # overwhelmingly common normal-filer case skips here without paying a full
        # document iteration; the complete position map is built only once both
        # gates pass below.
        need_total = not b7.end_element_id
        gate_pos, walked_total = self._lookup_anchor_indices(
            [b7.anchor_id, b7.end_element_id], need_total=need_total)
        a7 = gate_pos.get(b7.anchor_id)
        if a7 is None:
            return
        end7 = walked_total if need_total else gate_pos.get(b7.end_element_id, walked_total)
        if end7 is None or (end7 - a7) >= self._MIN_DEFERRED_SPAN:
            return

        # Precise gate: confirm the short Item 7 is an incorporation-by-reference
        # pointer (not just a genuinely brief item).
        html = getattr(self.document.metadata, 'original_html', None)
        if not html:
            return
        try:
            item7_text = self._extract_section_content(html, b7, include_subsections=True, clean=True) or ''
        except Exception:
            # The incorporation-by-reference recovery is being aborted; surface it
            # (not debug) so a filer that should have been recovered but failed the
            # stub-extraction gate is diagnosable rather than silently reverting.
            logger.warning("Item 7 pointer gate extraction failed; "
                           "skipping incorporated-financials recovery", exc_info=True)
            return
        if len(item7_text.strip()) > self._STUB_MAX_CHARS or not self._INCORP_RE.search(item7_text):
            return

        # Both gates passed (a genuine incorporation-by-reference filer): now build
        # the full anchor position map for the re-attribution work below.
        positions, total = self._anchor_doc_positions()
        a7 = positions.get(b7.anchor_id, a7)

        # Discover deferred-section anchors document-wide (the real body lives in a
        # block whose own (sub-)TOC links are not in the main item-TOC).
        candidates: Dict[str, List] = {}
        for link in self._tree.xpath('//a[@href]'):
            href = (link.get('href') or '').strip()
            if not href.startswith('#'):
                continue
            text = (link.text_content() or '').strip()
            if not text:
                continue
            key = self._classify_deferred_link(text)
            if key not in self._DEFERRABLE_KEYS:
                continue
            anchor = href[1:]
            pos = positions.get(anchor)
            if pos is not None:
                candidates.setdefault(key, []).append((pos, anchor))
        if not candidates:
            # The stub gates confirmed an incorporation-by-reference Item 7, but no
            # deferred block was recognised — most likely this filer titles its
            # 'Financial Section' sub-TOC with wording _DEFERRED_HEAD_MAP doesn't
            # cover. Surface it so the unenumerated filer is diagnosable instead of
            # silently returning the pointer stub.
            logger.warning("Incorporated-financials recovery: Item 7 is an "
                           "incorporation-by-reference pointer but no deferred "
                           "section was classified (unrecognised sub-TOC wording?)")
            return

        cand_positions = sorted({p for lst in candidates.values() for (p, _) in lst})

        def span(pos: int) -> int:
            j = bisect.bisect_right(cand_positions, pos)
            return (cand_positions[j] - pos) if j < len(cand_positions) else (total - pos)

        # For each deferrable item, the largest-span candidate is the real body;
        # accept it only if it spans meaningfully more than the current (pointer)
        # anchor, so we never replace genuine content.
        deferred: Dict[str, tuple] = {}
        for key, lst in candidates.items():
            current = self.section_boundaries.get(key)
            cur_pos = positions.get(current.anchor_id) if current else None
            cur_span = span(cur_pos) if cur_pos is not None else 0
            best_pos, best_anchor = max(lst, key=lambda c: span(c[0]))
            if (span(best_pos) >= self._MIN_DEFERRED_SPAN
                    and span(best_pos) > cur_span
                    and (current is None or best_anchor != current.anchor_id)):
                deferred[key] = (best_pos, best_anchor)
        if not deferred:
            return

        # Re-point each claimed item at its deferred anchor, ending at the next
        # claimed deferred anchor in document order (last runs to end of document).
        claimed = sorted((pos, key, anchor) for key, (pos, anchor) in deferred.items())
        for i, (pos, key, anchor) in enumerate(claimed):
            end_anchor = claimed[i + 1][2] if i + 1 < len(claimed) else None
            old = self.section_boundaries.get(key)
            self.section_boundaries[key] = SectionBoundary(
                name=key, anchor_id=anchor, end_element_id=end_anchor,
                confidence=min(old.confidence, 0.9) if old else 0.9,
                detection_method='toc-reattributed',
            )

        first_pos, _, first_anchor = claimed[0]
        # The position the absorbing trailing bucket(s) must be clamped to — the
        # start of the deferred block. Defaults to the earliest claimed deferred
        # anchor; gap-fill may push it earlier (to the supplement start).
        clamp_pos, clamp_anchor = first_pos, first_anchor

        # Gap-fill: MD&A (Item 7) often has no deferred title link of its own — the
        # supplement's own sub-TOC lists MD&A *subsections* (Executive Overview,
        # risk-management, ...), not a single "MD&A" entry. If Item 7 was not itself
        # remapped but a later financial block was, give it the region preceding the
        # financial statements, starting at the supplement's first sub-section
        # (which skips any exhibit index physically sitting between the item
        # pointers and the supplement).
        if 'part_ii_item_7' not in deferred:
            sup_pos, sup_anchor = self._find_supplement_start(positions, a7, first_pos)
            if sup_anchor and sup_pos > a7:
                self.section_boundaries['part_ii_item_7'] = SectionBoundary(
                    name='part_ii_item_7', anchor_id=sup_anchor, end_element_id=first_anchor,
                    confidence=min(b7.confidence, 0.9), detection_method='toc-reattributed',
                )
                if a7 < sup_pos < clamp_pos:
                    clamp_pos, clamp_anchor = sup_pos, sup_anchor
            else:
                # No supplement sub-TOC found: we can't locate where MD&A begins, and
                # spanning from the Item 7 pointer to the financial statements would
                # drag in the trailing items and the exhibit index. Leave Item 7 as
                # its original incorporation-by-reference pointer rather than emit
                # contaminated MD&A text.
                logger.warning("Incorporated-financials recovery: financial "
                               "statements re-attributed but the MD&A supplement "
                               "start was not found; Item 7 left as its "
                               "incorporation-by-reference pointer")

        # Clamp the trailing bucket(s) that absorbed the deferred block: any item
        # whose anchor precedes the deferred block but whose span runs into it.
        for key, boundary in list(self.section_boundaries.items()):
            if boundary.detection_method == 'toc-reattributed':
                continue
            a_pos = positions.get(boundary.anchor_id)
            if a_pos is None or a_pos >= clamp_pos:
                continue
            end_pos = positions.get(boundary.end_element_id) if boundary.end_element_id else total
            if end_pos is None or end_pos > clamp_pos:
                self.section_boundaries[key] = SectionBoundary(
                    name=boundary.name, anchor_id=boundary.anchor_id, end_element_id=clamp_anchor,
                    confidence=boundary.confidence, detection_method=boundary.detection_method,
                )

        logger.info("Re-attributed incorporated-by-reference financials: claimed %s",
                    sorted(deferred) + (['part_ii_item_7 (gap-fill)'] if 'part_ii_item_7' not in deferred else []))

    # Heading that opens a prospectus's audited financial-statements block (the
    # F-pages). It follows the last narrative section ("Experts" / "Legal Matters")
    # with no TOC anchor of its own, so the last matched section runs to EOF and
    # swallows it. Filers either index the F-pages ("Index to ... Financial
    # Statements") or, unindexed, lead with the auditor's report (edgartools-ti82 /
    # gh-878).
    _FS_BLOCK_HEADING_RE = re.compile(
        r'^\s*index\s+to\s+(?:the\s+)?(?:unaudited\s+)?(?:condensed\s+)?'
        r'(?:consolidated\s+|combined\s+)?financial\s+statements\s*$'
        r'|^\s*report\s+of\s+independent\s+registered\s+public\s+accounting\s+firm',
        re.IGNORECASE,
    )

    def _rescue_trailing_financials(self) -> None:
        """Bound the last prospectus narrative section at the financial-statements block.

        A prospectus's audited financial statements (F-pages) follow the last
        narrative section with no TOC anchor, so on title-based forms the trailing
        matched section runs to end-of-document and absorbs them — hundreds of KB
        of statements wrongly attributed to "Experts" / "Dilution" (gh-878). Find
        the F-pages heading in the body and clamp whichever section spans it. Item
        forms (title_based False) are unaffected: a 10-K's Item 8 *is* the
        financial statements, so there is nothing to clamp here. Scoped to
        prospectuses (S-1 / 424B): a DEF 14A proxy is title-based too but has no
        F-pages, and could carry an auditor-report reference that must not clamp
        its trailing section.
        """
        if self._tree is None:
            return
        base = self._base_form()
        if not (base.startswith('S-1') or base.startswith('424B')):
            return
        positions, total = self._anchor_doc_positions()
        if not self.section_boundaries:
            return
        # The F-pages sit after every narrative section, so scan only past the last
        # section's anchor — this skips the document-top TOC, where the same heading
        # appears as a link and would otherwise match first.
        last_start = max(
            (positions.get(b.anchor_id, -1) for b in self.section_boundaries.values()),
            default=-1,
        )
        if last_start < 0:
            return
        # The heading may be an element's own text or the tail text following an
        # empty <a name> anchor (a common SEC rendering: <p><a name=..></a>Index to
        # …</p>). Matching both — cheaply, without recursing into text_content —
        # catches either. Stopping extraction at this element excludes its text and
        # its tail (both are emitted on/after this element), so the heading and the
        # F-pages that follow are dropped from the narrative section.
        rx = self._FS_BLOCK_HEADING_RE
        fs_pos, fs_el = None, None
        for idx, el in enumerate(self._tree.iter()):
            if idx <= last_start:
                continue
            own = (el.text or '').strip()
            tail = (el.tail or '').strip()
            if (own and rx.match(own)) or (tail and rx.match(tail)):
                fs_pos, fs_el = idx, el
                break
        if fs_el is None:
            return
        # Clamp every section whose span runs into the F-pages (normally just the
        # trailing one): stop it at the heading element, which carries no anchor.
        for b in self.section_boundaries.values():
            a_pos = positions.get(b.anchor_id)
            if a_pos is None or a_pos >= fs_pos:
                continue
            end_pos = positions.get(b.end_element_id) if b.end_element_id else total
            if end_pos is not None and end_pos <= fs_pos:
                continue
            b.end_element = fs_el
        logger.info("Bounded trailing narrative section(s) at the financial-statements block")

    def get_available_sections(self) -> List[str]:
        """
        Get list of available sections that can be extracted.

        Returns:
            List of section names
        """
        # Sort by the section's logical order (same key the construction path uses
        # at _analyze_sections), not by anchor_id string. Re-attributed boundaries
        # (edgartools-rv86) get fresh anchor_ids that need not string-sort into
        # document order, which would otherwise list e.g. Item 8 before Item 7.
        return sorted(
            self.section_boundaries.keys(),
            key=lambda x: (self.toc_analyzer._get_section_type_and_order(x)[1],
                           self.section_boundaries[x].anchor_id),
        )

    def get_section_text(self, section_name: str,
                        include_subsections: bool = True,
                        clean: bool = True) -> Optional[str]:
        """
        Extract text content for a specific section.

        Args:
            section_name: Name of section (e.g., "Item 1", "Item 1A", "Part I")
            include_subsections: Whether to include subsections
            clean: Whether to apply text cleaning

        Returns:
            Section text content or None if section not found
        """
        # Normalize section name
        normalized_name = self._normalize_section_name(section_name)

        if normalized_name not in self.section_boundaries:
            return None

        boundary = self.section_boundaries[normalized_name]

        # Extract content between boundaries using HTML parsing
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            return None

        try:
            section_text = self._extract_section_content(html_content, boundary, include_subsections, clean)

            # A re-attributed anchor can land on a navigation breadcrumb just before
            # the real heading; strip it so the section starts at real content.
            if boundary.detection_method == 'toc-reattributed':
                section_text = self._strip_leading_nav(section_text)

            # Check if extracted content is suspiciously short for an Item section
            # This can happen when TOC anchors point to "PART I" header instead of actual Item content
            if section_text and len(section_text.strip()) < 200:
                # Check if this is an Item section that should have more content
                item_match = re.match(r'(?:part_[iv]+_)?item[_\s]*(\d+[a-z]?)', normalized_name, re.IGNORECASE)
                if item_match:
                    item_num = item_match.group(1).upper()
                    # Only hunt for "real" content when the short extraction is NOT
                    # already sitting on this item's own heading. An item that is
                    # legitimately brief — Legal Proceedings incorporated by
                    # reference, Mine Safety "Not applicable" — keeps its short,
                    # correctly-bounded text; the HTML-regex rescue (designed for
                    # anchors that land on a PART header) would otherwise run past
                    # the end anchor and swallow following items.
                    if not self._text_on_item_heading(section_text, item_num):
                        # Try to find actual Item content in HTML
                        actual_content = self._find_actual_item_content(html_content, item_num, boundary, clean)
                        if actual_content and len(actual_content) > len(section_text):
                            section_text = actual_content

            # If no direct content but include_subsections=True, aggregate subsection text
            if not section_text and include_subsections:
                subsections = self._get_subsections(normalized_name)
                if subsections:
                    # Recursively get text from all subsections
                    subsection_texts = []
                    for subsection_name in subsections:
                        subsection_text = self.get_section_text(subsection_name, include_subsections=True, clean=clean)
                        if subsection_text:
                            subsection_texts.append(subsection_text)

                    if subsection_texts:
                        section_text = '\n\n'.join(subsection_texts)

            return section_text
        except Exception:
            # Fallback to simple text extraction
            return self._extract_section_fallback(section_name, clean)

    def _normalize_section_name(self, section_name: str) -> str:
        """Normalize section name for lookup."""
        # Handle common variations
        name = section_name.strip()

        # "Item 1" vs "Item 1." vs "Item 1:"
        name = re.sub(r'[.:]$', '', name)

        # Case normalization
        if re.match(r'item\s+\d+', name, re.IGNORECASE):
            match = re.match(r'item\s+(\d+[a-z]?)', name, re.IGNORECASE)
            if match:
                name = f"Item {match.group(1).upper()}"
        elif re.match(r'part\s+[ivx]+', name, re.IGNORECASE):
            match = re.match(r'part\s+([ivx]+)', name, re.IGNORECASE)
            if match:
                name = f"Part {match.group(1).upper()}"

        return name

    def _extract_section_content(self, html_content: str, boundary: SectionBoundary,
                               include_subsections: bool, clean: bool) -> str:
        """
        Extract section content from HTML between anchors using document-order traversal.

        This method traverses the document in reading order (depth-first) from the start
        anchor to the end anchor, correctly handling multi-container sections where content
        spans across different parent elements.

        Args:
            html_content: Full HTML content
            boundary: Section boundary info
            include_subsections: Whether to include subsections
            clean: Whether to clean the text

        Returns:
            Extracted section text
        """
        # Reuse cached tree from _analyze_sections when available
        tree = self._tree
        if tree is None:
            if html_content.startswith('<?xml'):
                html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)
            tree = lxml_html.fromstring(html_content)

        # Verify start anchor exists
        start_elements = find_anchor_targets(tree, boundary.anchor_id)
        if not start_elements:
            return ""

        # Use document-order traversal (iterwalk) to collect all text between anchors
        # This correctly handles multi-container sections where start and end anchors
        # are in different parent containers
        all_text = []
        in_range = False

        # Block-level elements that should have paragraph breaks
        block_elements = {'p', 'div', 'table', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                         'blockquote', 'pre', 'section', 'article', 'header', 'footer'}

        for event, el in etree.iterwalk(tree, events=('start', 'end')):
            # Skip non-element nodes (comments, etc.)
            if not hasattr(el, 'get'):
                continue

            el_id = el.get('id', '')
            tag_name = el.tag.lower() if isinstance(el.tag, str) else ''

            if event == 'start':
                # Check if we've reached the start anchor
                if is_anchor_match(el, boundary.anchor_id):
                    in_range = True
                    continue

                # Check if we've reached the end boundary
                if boundary.end_element_id and is_anchor_match(el, boundary.end_element_id):
                    in_range = False
                    break

                # Check for an anchorless hard end (e.g. the financial-statements
                # block that follows the last narrative prospectus section).
                if in_range and boundary.end_element is not None and el is boundary.end_element:
                    in_range = False
                    break

                # Check for sibling section boundaries (when not including subsections)
                if in_range and not include_subsections and self._is_sibling_section(el_id, boundary.name):
                    in_range = False
                    break

                # Collect text content from element's direct text
                if in_range and el.text:
                    all_text.append(el.text)

            elif event == 'end':
                # Add paragraph break after block-level elements
                if in_range and tag_name in block_elements:
                    all_text.append('\n\n')

                # Collect tail text (text after closing tag)
                if in_range and el.tail:
                    all_text.append(el.tail)

        combined_text = ''.join(all_text)

        # Apply cleaning if requested
        if clean:
            combined_text = self._clean_section_text(combined_text)

        return combined_text

    def _is_sibling_section(self, element_id: str, current_section: str) -> bool:
        """Check if element ID represents a sibling section."""
        if not element_id:
            return False

        # Check if this looks like another item at the same level
        if 'item' in current_section.lower() and 'item' in element_id.lower():
            current_item = re.search(r'item\s*(\d+)', current_section, re.IGNORECASE)
            other_item = re.search(r'item[\s_]*(\d+)', element_id, re.IGNORECASE)

            if current_item and other_item:
                return current_item.group(1) != other_item.group(1)

        return False

    def _extract_element_text(self, element) -> str:
        """Extract clean text from an HTML element."""
        # Skip non-element nodes (comments, processing instructions, etc.)
        try:
            return element.text_content() or ""
        except (ValueError, AttributeError):
            # HtmlComment and other non-element nodes don't have text_content()
            return ""

    def _clean_section_text(self, text: str) -> str:
        """Clean extracted section text."""
        # Apply the same cleaning as the main document
        from edgar.documents.utils.anchor_cache import filter_with_cached_patterns

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        # Filter navigation links
        html_content = getattr(self.document.metadata, 'original_html', None)
        if html_content:
            text = filter_with_cached_patterns(text, html_content)

        return text.strip()

    def _text_on_item_heading(self, section_text: str, item_num: str) -> bool:
        """Return True if ``section_text`` begins on this item's own heading.

        Used to tell a *legitimately short* item (whose anchor is correctly
        placed — e.g. "ITEM 3. LEGAL PROCEEDINGS / incorporated by reference")
        apart from a *mis-anchored* item (whose anchor landed on a PART header,
        so the short text carries no item title). Matches "ITEM <n> <TITLE>"
        within the leading slice, tolerating the non-breaking spaces and
        entity noise that separate the number from the title.
        """
        title_pattern = _ITEM_TITLE_PATTERNS.get(item_num)
        if not title_pattern:
            return False
        head = section_text[:200]
        pattern = rf'ITEM[\s &#;0-9xnbsp]*{re.escape(item_num)}[\s &#;.0-9xnbsp]*{title_pattern}'
        return re.search(pattern, head, re.IGNORECASE) is not None

    def _find_actual_item_content(self, html_content: str, item_num: str,
                                    boundary: SectionBoundary, clean: bool) -> Optional[str]:
        """
        Find actual Item content when TOC anchor points to wrong location.

        Some filings have TOC anchors that point to "PART I" header instead of
        the actual "ITEM 1. BUSINESS" content. This method searches for the
        actual Item header in the HTML and extracts content from there.

        Args:
            html_content: Full HTML content
            item_num: Item number (e.g., "1", "1A", "7")
            boundary: Original section boundary
            clean: Whether to clean the text

        Returns:
            Extracted section text, or None if not found
        """
        from lxml import html as lxml_html

        # Handle XML declaration
        if html_content.startswith('<?xml'):
            html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content, count=1)

        # Build pattern to find actual ITEM header
        # Match "ITEM 1." or "ITEM 1A." with various spacing/entities
        # Examples: "ITEM 1. BUSINESS", "ITEM 1.&#160;&#160;BUSINESS", "ITEM&#160;1. BUSINESS"
        item_pattern = rf'ITEM[\s&#;0-9xnbsp]+{re.escape(item_num)}\.?[\s&#;0-9xnbsp]*'

        title_pattern = _ITEM_TITLE_PATTERNS.get(item_num, r'\w+')
        full_pattern = rf'{item_pattern}{title_pattern}'

        # Search for the pattern in HTML
        match = re.search(full_pattern, html_content, re.IGNORECASE)
        if not match:
            return None

        start_pos = match.start()

        # Find the end of this section (next ITEM header)
        # Start searching after current match
        search_start = start_pos + len(match.group())

        # Find next ITEM or PART header
        next_item_pattern = r'ITEM[\s&#;0-9xnbsp]*\d+[A-Z]?\.?\s*[A-Z]'
        next_match = re.search(next_item_pattern, html_content[search_start:], re.IGNORECASE)

        if next_match:
            end_pos = search_start + next_match.start()
        else:
            # No next item found - use end boundary anchor if available
            if boundary.end_element_id:
                end_anchor_pos = html_content.find(f'id="{boundary.end_element_id}"')
                if end_anchor_pos > start_pos:
                    end_pos = end_anchor_pos
                else:
                    end_pos = len(html_content)
            else:
                end_pos = len(html_content)

        # Extract HTML content
        section_html = html_content[start_pos:end_pos]

        # Parse and extract text
        try:
            wrapped = f'<div>{section_html}</div>'
            tree = lxml_html.fromstring(wrapped)
            text = tree.text_content()

            if clean:
                text = self._clean_section_text(text)

            return text.strip()
        except Exception:
            return None

    def _extract_section_fallback(self, section_name: str, clean: bool) -> Optional[str]:
        """
        Fallback section extraction using document nodes.

        This is used when HTML-based extraction fails.

        NOTE: This method CANNOT access self.document.sections because it's called
        DURING section detection, which would create infinite recursion.
        The circular dependency was: document.sections -> detect_sections() ->
        get_section_text() -> _extract_section_fallback() -> document.sections

        Returns:
            None - fallback disabled to prevent infinite recursion
        """
        # BUGFIX: Removed circular dependency that caused infinite recursion
        # Previously this accessed self.document.sections.items() which created
        # an infinite loop during section detection.
        #
        # If HTML-based extraction fails, we simply return None rather than
        # trying to use sections that haven't been computed yet.
        return None

    def get_section_info(self, section_name: str) -> Optional[Dict]:
        """
        Get detailed information about a section.

        Args:
            section_name: Section name to look up

        Returns:
            Dict with section metadata
        """
        normalized_name = self._normalize_section_name(section_name)

        if normalized_name not in self.section_boundaries:
            return None

        boundary = self.section_boundaries[normalized_name]

        return {
            'name': boundary.name,
            'anchor_id': boundary.anchor_id,
            'available': True,
            'estimated_length': None,  # Could calculate if needed
            'subsections': self._get_subsections(normalized_name)
        }

    def _get_subsections(self, parent_section: str) -> List[str]:
        """
        Get subsections of a parent section.

        For example:
        - "Item 1" has subsections "Item 1A", "Item 1B" (valid)
        - "Item 1" does NOT have subsection "Item 10" (invalid - different item)
        """
        subsections = []

        # Look for sections that start with the parent name
        for section_name in self.section_boundaries:
            if section_name == parent_section:
                continue

            if section_name.startswith(parent_section):
                # Check if this is a true subsection (e.g., Item 1A)
                # vs a different section that happens to start with same prefix (e.g., Item 10)
                remainder = section_name[len(parent_section):]

                # Valid subsection patterns:
                # - "Item 1A" (remainder: "A") - letter suffix
                # - "Item 1 - Business" (remainder: " - Business") - has separator
                # Invalid patterns:
                # - "Item 10" (remainder: "0") - digit continues the number

                if remainder and remainder[0].isalpha():
                    # Letter suffix like "A", "B" - valid subsection
                    subsections.append(section_name)
                elif remainder and remainder[0] in [' ', '-', '.', ':']:
                    # Has separator - could be descriptive title
                    subsections.append(section_name)
                # If remainder starts with digit, it's NOT a subsection (e.g., "Item 10")

        return sorted(subsections)
