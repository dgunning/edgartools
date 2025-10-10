"""
Hybrid section detection system with multiple fallback strategies.

This module implements a multi-strategy approach to section detection:
1. TOC-based (primary): High confidence, uses Table of Contents structure
2. Heading-based (fallback): Moderate confidence, uses multi-strategy heading detection
3. Pattern-based (last resort): Lower confidence, uses regex pattern matching
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from functools import lru_cache

from edgar.documents.document import Document, Section
from edgar.documents.nodes import SectionNode, HeadingNode
from edgar.documents.extractors.toc_section_detector import TOCSectionDetector
from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
from edgar.documents.config import DetectionThresholds

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

        # Initialize detection strategies
        self.toc_detector = TOCSectionDetector(document)
        self.pattern_extractor = SectionExtractor(form)

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
            return self._validate_pipeline(sections, enable_cross_validation=True)

        # Strategy 2: Heading-based (fallback)
        logger.debug("TOC detection failed, trying heading detection...")
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

    def _try_pattern_detection(self) -> Optional[Dict[str, Section]]:
        """
        Try pattern-based extraction.

        Returns:
            Dictionary of sections if successful, None if failed
        """
        try:
            # Use pattern extractor
            sections = self.pattern_extractor.extract(self.document)

            # Mark with pattern detection confidence
            for section in sections.values():
                section.confidence = 0.6  # Pattern-based = lower confidence
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

            # Create Section object
            section = Section(
                name=section_name,
                title=header_info.text,
                node=section_node,
                start_offset=0,  # Would need actual text position
                end_offset=0,  # Would need actual text position
                confidence=header_info.confidence,
                detection_method='heading'
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
