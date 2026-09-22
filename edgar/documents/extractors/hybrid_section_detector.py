"""
Hybrid section detection system with multiple fallback strategies.

This module implements a multi-strategy approach to section detection:
1. TOC-based (primary): High confidence, uses Table of Contents structure
2. Heading-based (fallback): Moderate confidence, uses multi-strategy heading detection
3. Pattern-based (last resort): Lower confidence, uses regex pattern matching
"""

import logging
import re
from typing import Dict, List, Optional

from edgar.documents.config import DetectionThresholds
from edgar.documents.document import Document, Section
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.extractors.toc_section_detector import TOCSectionDetector
from edgar.documents.nodes import HeadingNode, SectionNode

logger = logging.getLogger(__name__)


class HybridSectionDetector:
    """
    Multi-strategy section detector with fallback.

    Tries strategies in order of reliability:
    1. TOC-based (0.95 confidence) - Most reliable
    2. Multi-strategy heading detection (0.7-0.9 confidence) - Fallback
    3. Pattern matching (0.6 confidence) - Last resort

    Example:
        >>> detector = HybridSectionDetector(document, '10-K')
        >>> sections = detector.detect_sections()
        >>> for name, section in sections.items():
        ...     print(f"{name}: {section.confidence:.2f} ({section.detection_method})")
    """

    def __init__(self, document: Document, form: str, thresholds: Optional[DetectionThresholds] = None):
        """
        Initialize hybrid detector.

        Args:
            document: Document to extract sections from
            form: Filing type ('10-K', '10-Q', '8-K')
            thresholds: Detection thresholds configuration
        """
        self.document = document
        self.form = form
        self.thresholds = thresholds or DetectionThresholds()

        # Detect filing agent from the original HTML for agent-aware TOC parsing
        agent = self._detect_agent()

        # Initialize detection strategies. `form` flows through to the
        # TOC analyzer so its bare-item-number heuristic can apply
        # form-aware bounds (prevents page-number cells from being
        # mis-interpreted as item identifiers on forms with few items
        # like 10-Q).
        self.toc_detector = TOCSectionDetector(document, agent=agent, form=form)
        self.pattern_extractor = SectionExtractor(form)

    def _detect_agent(self) -> Optional[str]:
        """Detect filing agent from the document's original HTML."""
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            return None
        try:
            from edgar.documents.agents import detect_filing_agent
            return detect_filing_agent(html_content)
        except Exception:
            return None

    def detect_sections(self) -> Dict[str, Section]:
        """
        Detect sections using hybrid approach with fallback and validation.

        Returns:
            Dictionary mapping section names to Section objects with confidence scores
        """
        # Strategy 1: TOC-based (most reliable)
        logger.debug("Trying TOC-based detection...")
        sections = self.toc_detector.detect()
        if sections:
            logger.info(f"TOC detection successful: {len(sections)} sections found")
            validated = self._validate_pipeline(sections, enable_cross_validation=True)
            # Augment TOC result with pattern-detected sections for items not in the
            # TOC (most commonly Part III "incorporated by reference" stubs — Items
            # 10-14 appear only as sparse paragraphs, not as TOC entries).
            # GH #880 / edgartools-01x4.
            augmented = self._augment_with_pattern_sections(validated)
            if augmented is not validated:
                logger.info(
                    f"Augmented TOC sections with {len(augmented) - len(validated)} "
                    f"pattern-detected item(s)"
                )
            return augmented

        # Strategy 1.5: Cross-reference index.
        #
        # Ranked directly below the TOC because it is the same kind of evidence:
        # the filer stating where each item is, rather than us inferring it. It
        # only ever fires on filings that publish a "Form 10-K Cross-Reference
        # Index" and have no navigable TOC — Citigroup, whose 16.7MB 10-K used to
        # fall all the way through to keyword matching and surface four
        # non-canonical keys (`mda`, `risk_factors`, ...) while a caller asking
        # for part_ii_item_7 got nothing (edgartools-4agg).
        logger.debug("TOC detection failed, trying cross-reference index detection...")
        sections = self._try_index_detection()
        if sections:
            logger.info(f"Cross-reference index detection successful: {len(sections)} sections found")
            return self._validate_pipeline(sections, enable_cross_validation=False)

        # Strategy 2: Heading-based (fallback)
        logger.debug("Index detection failed, trying heading detection...")
        sections = self._try_heading_detection()
        if sections:
            logger.info(f"Heading detection successful: {len(sections)} sections found")
            return self._validate_pipeline(sections, enable_cross_validation=False)

        # Strategy 3: Pattern-based (last resort)
        logger.debug("Heading detection failed, trying pattern matching...")
        sections = self._try_pattern_detection()
        if sections:
            logger.info(f"Pattern detection successful: {len(sections)} sections found")
            return self._validate_pipeline(sections, enable_cross_validation=False)

        logger.warning("All detection strategies failed, no sections found")
        return {}

    def _augment_with_pattern_sections(
        self, toc_sections: Dict[str, Section]
    ) -> Dict[str, Section]:
        """Augment TOC-detected sections with pattern-detected items not in the TOC.

        A table of contents is a thing the filer wrote, not a manifest, and items
        go missing from it routinely: Part III (Items 10-14) when they are
        incorporated by reference from the proxy, Item 16 (Form 10-K Summary)
        because it is optional and usually empty, Item 1C (Cybersecurity) because
        it was new in 2023 and templates lagged. The items are still in the body
        as sparse bold paragraphs. This method runs the pattern extractor and
        merges in the ones the TOC did not name. It never replaces or overrides a
        TOC section: those carry higher confidence and real extracted text.

        WHAT IS MISSING IS THE GATE'S QUESTION, NOT WHICH PART IT IS IN. This
        used to skip the pattern pass whenever the five Part III keys were
        present, on the reasoning that Part III is what TOCs omit. That was true
        of the filings it was written against and false in general — and because
        Part III is complete on most filings, the skip fired almost always. Six
        tracked filings lost an item to it: Item 16 on axp, cvx and jnj, and
        Item 1C on bac, jpm and tsla, each already found by the pattern extractor
        and thrown away before it ran. Item 1C has been mandatory since December
        2023, so the population affected is most modern 10-Ks, not an edge case.
        The gate now asks whether the TOC result is missing any item the form
        defines, which is the condition the augmentation exists for.

        The pattern pass itself costs 30-260ms on a 2.6-12.9MB 10-K, 3-13% of
        that filing's parse, and runs only on filings actually missing an item.
        Total parse time over the 85-filing 10-K/10-Q corpus is unchanged within
        run-to-run variance (61-62s either way, two runs each): the pass now runs
        on more filings, and the item-keyed merge below hands far fewer sections
        to ``_validate_pipeline`` on the filings where it already ran.

        Args:
            toc_sections: Validated sections from TOC detection.

        Returns:
            A new dict that includes all toc_sections plus any pattern-only additions,
            or the original dict unchanged if nothing was added.
        """
        from edgar.documents.form_schema import get_form_schema

        # Only augment for Item-based forms; skip title-based (DEF 14A, 424B, S-1).
        schema = get_form_schema(self.form)
        if schema.title_based:
            return toc_sections

        # 8-K reports only the items that happened to occur, so "missing" has no
        # meaning there — every 8-K is missing almost all of them — and the gate
        # below would degenerate into "always run".
        if not self.form or self.form.startswith('8-K'):
            return toc_sections

        # What the form defines, and what the TOC named, BOTH AS (part, item)
        # pairs. On a 10-Q an item number is only unique within its part — Item 1
        # is Financial Statements in Part I and Legal Proceedings in Part II — so
        # comparing bare numbers reports a TOC that named one of them as having
        # named both. That is not a near-miss: on pg/10q the two sets came out
        # exactly equal, this returned "the TOC named everything", and the
        # augmentation that would have supplied the missing part_ii_item_1 never
        # ran at all (edgartools-yrrh).
        #
        # `resolve_section_key` is what makes the comparison possible on the
        # schema side: it recovers ('II', '7') for a semantic key like `mda`,
        # whose key string carries neither part nor item.
        canonical = {schema.resolve_section_key(key) for key in schema.section_patterns}
        canonical = {(part, item) for part, item in canonical if item}
        found_items = {sec.item for sec in toc_sections.values() if sec.item}
        found_part_items = {
            (sec.part, sec.item) for sec in toc_sections.values() if sec.item
        }
        if not canonical or canonical <= found_part_items:
            return toc_sections  # The TOC named everything the form defines.

        # Run pattern extractor against the same document.
        pattern_sections = self._try_pattern_detection()
        if not pattern_sections:
            return toc_sections

        # Merge in the pattern sections that add an item the TOC did not have.
        #
        # KEYED ON THE ITEM, NOT THE KEY, because the two detectors name the same
        # section differently: the TOC path emits `part_ii_item_7` and the pattern
        # path emits `mda`, and `Section.item` is '7' for both. Merging on the key
        # alone would have added 9-11 duplicate sections per filing here — a
        # second span of the same item under its other spelling — which is the
        # same two-vocabulary trap that cost `wfc/10k` a week in BASELINE_GAPS.
        # It did not bite before only because the Part III gate kept this code
        # from running on the filings where the TOC succeeds.
        #
        # AND ON THE PART AS WELL AS THE ITEM, because an item number is only
        # unique within its part. A 10-Q has TWO Item 1s — Financial Statements
        # in Part I, Legal Proceedings in Part II — so an item-only comparison
        # reads the second as a duplicate of the first and drops it. On pg/10q
        # the pattern extractor found part_ii_item_1 and this filter discarded
        # it, because the TOC had already contributed part_i_item_1 and both
        # answer '1'; `get_item_with_part('Part II', 'Item 1')` then fell through
        # to id_parse_document, which returned 222,536 characters for a section
        # of 1,018 (edgartools-yrrh).
        #
        # The 10-K dedup above is unaffected: its pattern sections carry a part
        # too — `mda` is part 'II', item '7', the same pair as `part_ii_item_7` —
        # so they still collide. Only a section with no part at all falls back to
        # comparing the bare item, which is what 20-F and the part-less keys need.
        def _toc_already_has(sec) -> bool:
            if not sec.item:
                return False
            if sec.part:
                return (sec.part, sec.item) in found_part_items
            return sec.item in found_items

        extras = {
            key: sec
            for key, sec in pattern_sections.items()
            if key not in toc_sections and not _toc_already_has(sec)
        }
        if not extras:
            return toc_sections

        # Validate extras through the same pipeline (boundary checks, dedup,
        # confidence filter, size guardrail) before merging.  Pass
        # enable_cross_validation=False — the pattern extractor has already
        # made its best effort and we don't want a second expensive pass.
        extras = self._validate_pipeline(extras, enable_cross_validation=False)
        if not extras:
            return toc_sections

        merged = dict(toc_sections)
        merged.update(extras)
        return merged

    def _validate_pipeline(
        self,
        sections: Dict[str, Section],
        enable_cross_validation: bool = False
    ) -> Dict[str, Section]:
        """
        Apply validation pipeline to sections.

        Centralizes validation logic to eliminate duplication.

        Args:
            sections: Sections to validate
            enable_cross_validation: Whether to enable cross-validation (expensive)

        Returns:
            Validated sections
        """
        if not sections:
            return sections

        # Cross-validate (optional, expensive)
        if enable_cross_validation and self.thresholds.enable_cross_validation:
            sections = self._cross_validate(sections)

        # Validate boundaries
        sections = self._validate_boundaries(sections)

        # Deduplicate
        sections = self._deduplicate(sections)

        # Filter by confidence
        sections = self._filter_by_confidence(sections)

        # Header-only artifact drop (title-based forms only) — a proxy/424B/S-1
        # TOC entry whose section collapses to just its own heading phrase (the
        # body absorbed by an adjacent section) is a mislabeled sliver, not
        # content. Drop it before the size guardrail so it is never emitted as a
        # labeled section (edgartools-x341). Runs before the guardrail so the
        # bands evaluate only surviving sections.
        sections = self._drop_header_only_sections(sections)

        # Size guardrail — runs LAST so a confidence reduction here cannot cause
        # the confidence filter to silently drop a flagged section. Flags
        # anomalously-sized sections (wrong-content failures) rather than
        # returning them at full confidence (edgartools-9hwf).
        sections = self._apply_size_guardrail(sections)

        # Schema-validity and successor-header guardrails — same flag-and-return
        # placement as the size guardrail (after the confidence filter, so a
        # reduction here cannot silently drop the flagged section).
        sections = self._apply_part_validity(sections)
        sections = self._apply_successor_guardrail(sections)

        return sections

    # Length below which a TOC section is a candidate header-only artifact. The
    # largest empty-header sliver observed across a 32-filer proxy corpus is 48
    # chars ('Table of Contents     Executive Compensation'); the shortest *real*
    # short section is 120 ('Item 1: Election of Directors. The Board ...
    # recommends FOR ...'). 64 sits safely between them.
    _HEADER_ONLY_MAX_LEN = 64

    def _drop_header_only_sections(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """Drop title-based TOC sections that collapsed to a bare heading.

        On hierarchical / divider proxy TOCs a vocabulary term sometimes matches
        a divider tab or summary cross-reference whose section boundary lands at
        the very next entry, so the section's entire body is just its heading
        phrase ('Executive Compensation', 'BOARD OF DIRECTORS') — the real
        content lives in an adjacent absorbing section. Such a sliver is a
        mislabeled artifact; the labeled-or-full contract says never emit it.

        Scoped to title-based forms (DEF 14A / PRE 14A / 424B / S-1): the
        Item-based forms (10-K/10-Q/8-K) keep their existing output untouched.
        A section is header-only when its extracted text is short
        (< ``_HEADER_ONLY_MAX_LEN``) AND carries no sentence punctuation — a
        real short section (a proposal recommendation, a one-line disclosure)
        has a sentence; a heading-table section is long. Only ``toc`` sections
        are considered (heading/pattern sections measure length differently).
        """
        from edgar.documents.form_schema import get_form_schema

        if not get_form_schema(self.form).title_based:
            return sections

        survivors: Dict[str, Section] = {}
        for name, section in sections.items():
            if section.detection_method == 'toc':
                # Cheap length proxy first (TOC sections store text length in
                # end_offset); only materialize text() for plausible slivers.
                proxy = section.end_offset - section.start_offset
                if 0 < proxy < 2 * self._HEADER_ONLY_MAX_LEN:
                    body = (section.text() or "").strip()
                    if len(body) < self._HEADER_ONLY_MAX_LEN and not re.search(r'[.!?]', body):
                        logger.info(
                            f"Dropping header-only section '{name}' "
                            f"(body={body!r}) — content absorbed by a sibling"
                        )
                        continue
            survivors[name] = section
        return survivors

    def _apply_size_guardrail(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """Flag sections whose extracted content size is anomalous for their item.

        Uses the per-(form, part, item) bands in ``section_size_bands``. The
        Part is part of the key because a 10-Q's item numbers repeat: judging
        Part II's Legal Proceedings against Part I's Financial Statements band
        flagged a correctly-extracted section on most of the corpus
        (edgartools-xhmd). For
        TOC-detected sections the content length is already known (stored in
        ``end_offset`` by the detector), so this adds no extraction cost. A
        section outside its band gets a human-readable ``warning`` and its
        confidence reduced to ``ANOMALOUS_CONFIDENCE`` — the section is still
        returned (callers can introspect ``.warnings``), it is just no longer
        presented as high-confidence wrong content.

        Undersize sections are then split by cause (GH #927): a filer that
        incorporates the item by reference is short *and correctly extracted*,
        so it gets the cross-reference warning rather than the truncation one.
        Only sections the bands already flagged pay for the text extraction that
        test needs — a healthy filing does no extra work.
        """
        from edgar.documents.section_size_bands import (
            ANOMALOUS_CONFIDENCE,
            cross_reference_warning,
            evaluate_size,
            is_cross_reference,
            is_undersize,
        )

        for section in sections.values():
            # Only TOC sections set end_offset to the extracted *text length*
            # (start_offset == 0), which is what the bands are calibrated on.
            # Pattern sections set end_offset to a *document character position*
            # (a different, markup-inclusive yardstick) and heading sections set
            # 0; applying text-length bands to either would mis-flag. The
            # documented failures (GS/Citi-class) are all on the TOC path.
            if section.detection_method != 'toc':
                continue
            # Length proxy: TOC sections set end_offset to the extracted text
            # length (start_offset == 0). Skip when length is unknown (0).
            length = section.end_offset - section.start_offset
            if length <= 0:
                continue
            item_key = section.item
            part = section.part
            if evaluate_size(self.form, item_key, length, part=part) is None:
                continue
            # The proxy said anomalous; decide on the length the caller will
            # actually see. end_offset and .text() disagree by a few characters
            # (nflx 10-Q: 227 vs 223), and a warning that quotes a number the
            # caller cannot reproduce is not diagnosable (edgartools-xhmd). Only
            # sections the proxy already flagged pay for this.
            try:
                text = section.text()
            except Exception:  # noqa: BLE001
                text = None
                logger.debug("Section %s: text extraction failed; sizing on the "
                             "offset proxy", section.name, exc_info=True)
            # An empty render says nothing about size — the proxy stands.
            if text:
                length = len(text)
            warning = evaluate_size(self.form, item_key, length, part=part)
            if warning:
                if text and is_undersize(self.form, item_key, length, part=part):
                    try:
                        if is_cross_reference(text):
                            warning = cross_reference_warning(self.form, item_key, length,
                                                              part=part)
                    except Exception:
                        # Keep the size warning: the section is still anomalous,
                        # we just could not tell which cause it is.
                        logger.debug("Section %s: cross-reference test failed; "
                                     "keeping the size warning", section.name, exc_info=True)
                section.warnings.append(warning)
                section.confidence = min(section.confidence, ANOMALOUS_CONFIDENCE)
                logger.info(f"Section {section.name}: {warning}")

        return sections

    def _apply_part_validity(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """Flag sections whose (part, item) cannot exist on this form (GH #905).

        A 10-Q Part I has Items 1-4 only, yet running-header mis-anchoring can
        scatter content into phantom keys like ``part_i_item_6`` (Freddie Mac
        Q1 2026 10-Q put the entire MD&A there, while the real Part I items
        returned scraps). Length heuristics can't catch this — the phantoms
        look like valid short-or-long items — but the form schema knows the key
        is impossible. Flag-and-return: the section keeps its content so
        nothing is silently lost, with a warning and reduced confidence so
        callers can tell the whole Part's boundaries are suspect. Only forms
        with curated per-part ranges (10-Q) are checked.
        """
        from edgar.documents.form_schema import get_form_schema
        from edgar.documents.section_size_bands import ANOMALOUS_CONFIDENCE

        schema = get_form_schema(self.form)
        if not schema.part_item_ranges:
            return sections

        for section in sections.values():
            if schema.item_valid_in_part(section.part, section.item) is False:
                warning = (
                    f"Part {section.part} of a {self.form} has no Item {section.item} — "
                    f"the item boundaries were mis-anchored and this content likely "
                    f"belongs to another section."
                )
                section.warnings.append(warning)
                section.confidence = min(section.confidence, ANOMALOUS_CONFIDENCE)
                logger.info(f"Section {section.name}: {warning}")

        return sections

    # Only TOC item sections at least this long are scanned for embedded
    # successor headers: re-extracting text has a real cost, and a shorter
    # over-capture (two adjacent stubs) is low-impact. An absorbed item's
    # header deep inside a large section is exactly the failure worth paying
    # one extra extraction to catch.
    _SUCCESSOR_SCAN_MIN_CHARS = 15_000

    # Line-anchored item header: start of line, optional (nbsp) indent, then
    # "Item N." / "ITEM 7A:" with mandatory punctuation so mid-sentence
    # references ("see Item 7A below") and prose starting with "Item 7A is…"
    # don't match.
    _SUCCESSOR_HEADER_RE = re.compile(
        r'^[ \t\xa0]*Item\s+(\d{1,2})([A-D]?)\s*[.:]', re.IGNORECASE | re.MULTILINE
    )

    def _apply_successor_guardrail(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """Flag item sections whose text embeds the header of a LATER item that
        detection missed (GH #904).

        Size bands can't see every overshoot: Coeur Mining's overflowed Item 7
        (257K chars) sat inside Item 7's generous band, and Item 1B (317K chars
        of everything through Part IV) has no band at all. But both contained
        line-anchored headers of items absent from the section map — the
        smoking gun for an end boundary that ran past them. Flag-and-return,
        like the size guardrail.

        Scoped to forms with unique items across parts (10-K: schema has
        ``item_part_ranges``) — on repeating-item forms the bare header number
        can't be ordered against the section without knowing its Part. Only
        TOC-detected sections are scanned (same calibration argument as the
        size guardrail), and only when the map is actually missing a later item
        number, so fully-anchored filings (AAPL) pay no extraction cost.
        """
        from edgar.documents.form_schema import get_form_schema
        from edgar.documents.section_size_bands import ANOMALOUS_CONFIDENCE

        schema = get_form_schema(self.form)
        if not schema.item_part_ranges:
            return sections

        def order(num: int, letter: str) -> int:
            return num * 1000 + (ord(letter.upper()) - ord('A') + 1 if letter else 0)

        item_re = re.compile(r'^(\d{1,2})([A-D]?)$', re.IGNORECASE)
        present: set = set()
        present_numbers: set = set()
        for section in sections.values():
            m = item_re.match(section.item or '')
            if m:
                present.add(section.item.upper())
                present_numbers.add(int(m.group(1)))

        max_item_number = max((hi for _lo, hi, _roman in schema.item_part_ranges), default=16)
        optional_numbers = set(schema.optional_item_numbers)

        for section in sections.values():
            if section.detection_method != 'toc':
                continue
            length = section.end_offset - section.start_offset
            if length < self._SUCCESSOR_SCAN_MIN_CHARS:
                continue
            m = item_re.match(section.item or '')
            if not m:
                continue
            own_num, own_letter = int(m.group(1)), m.group(2)
            # Cheap pre-gate: scan only when a later item *number* is actually
            # missing from the map — a complete ladder has nowhere to overflow.
            # Optional items (10-K Item 16) don't count as gaps: a filing that
            # legitimately omits one would otherwise force a text extraction on
            # every large section (JPM, items 1-15: +16% section-detection time).
            if all(n in present_numbers or n in optional_numbers
                   for n in range(own_num + 1, max_item_number + 1)):
                continue

            text = section.text() or ""
            matches = list(self._SUCCESSOR_HEADER_RE.finditer(text))
            for hit in matches:
                token = f"{int(hit.group(1))}{hit.group(2).upper()}"
                if token in present:
                    continue
                if order(int(hit.group(1)), hit.group(2)) <= order(own_num, own_letter):
                    continue
                if int(hit.group(1)) > max_item_number:
                    continue
                # An embedded TOC/index block lists many item headers in a tight
                # run; a genuinely absorbed item's header is surrounded by body
                # text. Skip hits with 2+ other headers within 300 chars.
                neighbors = sum(1 for other in matches
                                if other is not hit and abs(other.start() - hit.start()) <= 300)
                if neighbors >= 2:
                    continue
                warning = (
                    f"Item {section.item} content contains the header of Item {token}, "
                    f"which was not detected as its own section — the end boundary "
                    f"likely overshoots into later items (extraction over-captured)."
                )
                section.warnings.append(warning)
                section.confidence = min(section.confidence, ANOMALOUS_CONFIDENCE)
                logger.info(f"Section {section.name}: {warning}")
                break

        return sections

    def _try_heading_detection(self) -> Optional[Dict[str, Section]]:
        """
        Try multi-strategy heading detection.

        Returns:
            Dictionary of sections if successful, None if failed
        """
        try:
            # Get heading nodes from document
            headings = self.document.headings
            if not headings:
                return None

            sections = {}

            for heading in headings:
                # Check if heading has header info
                if not hasattr(heading, 'header_info') or not heading.header_info:
                    continue

                header_info = heading.header_info

                # Only use headings with sufficient confidence
                if header_info.confidence < 0.7:
                    continue

                # Check if it's an item header
                if not header_info.is_item:
                    continue

                # Extract section from this heading to next
                section = self._extract_section_from_heading(heading, header_info)
                if section:
                    section.confidence = header_info.confidence
                    section.detection_method = 'heading'
                    sections[section.name] = section

            return sections if sections else None

        except Exception as e:
            logger.warning(f"Heading detection failed: {e}")
            return None

    def _try_index_detection(self) -> Optional[Dict[str, Section]]:
        """Try Cross Reference Index detection.

        Returns:
            Dictionary of sections if the filing publishes a usable index,
            None otherwise.
        """
        try:
            from edgar.documents.extractors.index_section_detector import IndexSectionDetector

            return IndexSectionDetector(self.document, self.form).detect()
        except Exception as e:
            logger.warning(f"Index detection failed: {e}")
            return None

    def _try_pattern_detection(self) -> Optional[Dict[str, Section]]:
        """
        Try pattern-based extraction.

        Returns:
            Dictionary of sections if successful, None if failed
        """
        try:
            # Use pattern extractor
            sections = self.pattern_extractor.extract(self.document)

            # Mark detection method (but preserve confidence from pattern extractor)
            for section in sections.values():
                # Keep the pattern extractor's confidence (typically 0.70)
                # instead of overwriting with hardcoded 0.6
                section.detection_method = 'pattern'

            return sections if sections else None

        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")
            return None

    def _extract_section_from_heading(self, heading: HeadingNode, header_info) -> Optional[Section]:
        """
        Extract section content from heading node to next heading.

        Args:
            heading: HeadingNode representing section start
            header_info: HeaderInfo with section metadata

        Returns:
            Section object if successful, None otherwise
        """
        try:
            # Create section name from item number
            section_name = f"item_{header_info.item_number.replace('.', '_')}" if header_info.item_number else "unknown"

            # Create section node
            section_node = SectionNode(section_name=section_name)

            # Find next heading at same or higher level to determine section end
            current_level = header_info.level
            parent = heading.parent
            if not parent:
                return None

            # Find heading position in parent's children
            try:
                heading_index = parent.children.index(heading)
            except ValueError:
                return None

            # Collect nodes until next section heading
            for i in range(heading_index + 1, len(parent.children)):
                child = parent.children[i]

                # Stop at next heading of same or higher level
                if isinstance(child, HeadingNode):
                    if hasattr(child, 'header_info') and child.header_info:
                        if child.header_info.level <= current_level:
                            break

                # Add child to section
                section_node.add_child(child)

            # Resolve part/item so heading-detected sections carry the same
            # metadata as pattern/TOC ones — a consumer keying on section.item
            # or section.part would otherwise silently drop these (GH #891).
            # Heading section names are item-only ('item_7'), so
            # parse_section_name resolves the item but leaves part=None; fill the
            # part from the form's item->part ranges, mirroring _create_sections.
            part, item = Section.parse_section_name(section_name)
            if item is not None and part is None:
                from edgar.documents.form_schema import get_form_schema
                part_label = get_form_schema(self.form).part_for_item(f"Item {item}")
                if part_label:
                    part = part_label.replace('Part ', '')

            # Create Section object
            section = Section(
                name=section_name,
                title=header_info.text,
                node=section_node,
                start_offset=0,  # Would need actual text position
                end_offset=0,  # Would need actual text position
                confidence=header_info.confidence,
                detection_method='heading',
                part=part,
                item=item
            )

            return section

        except Exception as e:
            logger.warning(f"Failed to extract section from heading: {e}")
            return None

    def _cross_validate(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """
        Cross-validate sections using multiple detection methods.

        Boosts confidence if multiple methods detect the same section.
        Reduces confidence if methods disagree.

        Args:
            sections: Sections detected by primary method

        Returns:
            Validated sections with adjusted confidence scores
        """
        validated = {}

        # Get pattern-based sections once for comparison (not per section)
        try:
            pattern_sections = self.pattern_extractor.extract(self.document)
        except Exception as e:
            logger.debug(f"Pattern extraction failed for cross-validation: {e}")
            pattern_sections = {}

        for name, section in sections.items():
            # Try alternative detection (pattern matching for validation)
            try:
                # Check if this section is also found by pattern matching
                found_in_patterns = False
                for pattern_name, pattern_section in pattern_sections.items():
                    # Check for name similarity or overlap
                    if self._sections_similar(section, pattern_section):
                        found_in_patterns = True
                        break

                # Boost confidence if methods agree
                if found_in_patterns:
                    section.confidence = min(section.confidence * self.thresholds.cross_validation_boost, 1.0)
                    section.validated = True
                    logger.debug(f"Section {name} validated by multiple methods, confidence boosted to {section.confidence:.2f}")
                else:
                    # Slight reduction if not validated
                    section.confidence *= self.thresholds.disagreement_penalty
                    section.validated = False

            except Exception as e:
                logger.debug(f"Cross-validation failed for {name}: {e}")
                # Keep original confidence if validation fails
                pass

            validated[name] = section

        return validated

    def _validate_boundaries(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """
        Validate section boundaries for overlaps, gaps, and ordering.

        Args:
            sections: Sections to validate

        Returns:
            Sections with validated boundaries
        """
        if not sections:
            return sections

        # Sort by start offset
        sorted_sections = sorted(sections.items(), key=lambda x: x[1].start_offset)

        validated = {}
        prev_section = None

        for name, section in sorted_sections:
            # Check for overlap with previous section
            if prev_section and section.start_offset > 0:
                if section.start_offset < prev_section[1].end_offset:
                    # Overlap detected - adjust boundary at midpoint
                    gap_mid = (prev_section[1].end_offset + section.start_offset) // 2
                    prev_section[1].end_offset = gap_mid
                    section.start_offset = gap_mid

                    # Reduce confidence due to boundary adjustment
                    section.confidence *= self.thresholds.boundary_overlap_penalty
                    prev_section[1].confidence *= self.thresholds.boundary_overlap_penalty

                    logger.debug(f"Adjusted boundary between {prev_section[0]} and {name}")

                # Check for large gap (>10% of document size)
                elif prev_section[1].end_offset > 0:
                    gap_size = section.start_offset - prev_section[1].end_offset
                    if gap_size > 100000:  # Arbitrary large gap threshold
                        # Large gap - might indicate missing section
                        section.confidence *= 0.9
                        logger.debug(f"Large gap detected before {name}")

            validated[name] = section
            prev_section = (name, section)

        return validated

    def _deduplicate(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """
        Remove duplicate sections detected by multiple methods.

        Keeps the detection with highest confidence.

        Args:
            sections: Sections possibly containing duplicates

        Returns:
            Deduplicated sections
        """
        if len(sections) <= 1:
            return sections

        # Group similar sections
        groups = self._group_similar_sections(sections)

        deduplicated = {}
        for group in groups:
            if len(group) == 1:
                # No duplicates
                deduplicated[group[0].name] = group[0]
            else:
                # Keep section with highest confidence
                best = max(group, key=lambda s: s.confidence)

                # Merge detection methods
                methods = set(s.detection_method for s in group)
                if len(methods) > 1:
                    best.detection_method = ','.join(sorted(methods))
                    # Boost confidence for multi-method detection
                    best.confidence = min(best.confidence * 1.15, 1.0)
                    best.validated = True
                    logger.debug(f"Merged duplicate sections for {best.name}, methods: {best.detection_method}")

                deduplicated[best.name] = best

        return deduplicated

    def _group_similar_sections(self, sections: Dict[str, Section]) -> List[List[Section]]:
        """
        Group sections that appear to be duplicates.

        Args:
            sections: Sections to group

        Returns:
            List of section groups
        """
        groups = []
        used = set()

        for name1, section1 in sections.items():
            if name1 in used:
                continue

            group = [section1]
            used.add(name1)

            for name2, section2 in sections.items():
                if name2 in used:
                    continue

                # Check if sections are similar
                if self._sections_similar(section1, section2):
                    group.append(section2)
                    used.add(name2)

            groups.append(group)

        return groups

    def _sections_similar(self, section1: Section, section2: Section) -> bool:
        """
        Check if two sections are similar (likely duplicates).

        Args:
            section1: First section
            section2: Second section

        Returns:
            True if sections are similar
        """
        # Normalize names for comparison
        name1 = section1.name.lower().replace('_', ' ').strip()
        name2 = section2.name.lower().replace('_', ' ').strip()

        # Check exact match after normalization
        if name1 == name2:
            return True

        # Check title similarity (exact match)
        title1 = section1.title.lower().strip()
        title2 = section2.title.lower().strip()

        if title1 == title2:
            return True

        # Check for position overlap (if positions are set)
        if section1.start_offset > 0 and section2.start_offset > 0:
            # Calculate overlap
            overlap_start = max(section1.start_offset, section2.start_offset)
            overlap_end = min(section1.end_offset, section2.end_offset)

            if overlap_end > overlap_start:
                # There is overlap
                overlap_size = overlap_end - overlap_start
                min_size = min(
                    section1.end_offset - section1.start_offset,
                    section2.end_offset - section2.start_offset
                )

                # If overlap is >50% of smaller section, consider similar
                if min_size > 0 and overlap_size / min_size > 0.5:
                    return True

        return False

    def _filter_by_confidence(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """
        Filter sections by minimum confidence threshold.

        Args:
            sections: Sections to filter

        Returns:
            Filtered sections meeting minimum confidence
        """
        # Check for filing-specific thresholds
        min_conf = self.thresholds.min_confidence
        if self.form in self.thresholds.thresholds_by_form:
            filing_thresholds = self.thresholds.thresholds_by_form[self.form]
            min_conf = filing_thresholds.get('min_confidence', min_conf)

        filtered = {}
        for name, section in sections.items():
            if section.confidence >= min_conf:
                filtered[name] = section
            else:
                logger.debug(f"Filtered out section {name} with confidence {section.confidence:.2f} < {min_conf:.2f}")

        return filtered
