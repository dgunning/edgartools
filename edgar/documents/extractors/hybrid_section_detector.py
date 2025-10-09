"""
Hybrid section detection system with multiple fallback strategies.

This module implements a multi-strategy approach to section detection:
1. TOC-based (primary): High confidence (0.95), uses Table of Contents structure
2. Heading-based (fallback): Moderate confidence (0.7-0.9), uses HeaderInfo
3. Pattern-based (last resort): Lower confidence (0.7), uses regex patterns

The hybrid approach achieves higher recall by trying multiple methods,
while maintaining precision through confidence scoring and validation.
"""

import logging
from typing import Dict, List, Optional

from edgar.documents.config import DetectionThresholds
from edgar.documents.document import Document, Section
from edgar.documents.extractors.heading_section_detector import HeadingSectionDetector
from edgar.documents.extractors.section_extractor import SectionExtractor
from edgar.documents.extractors.toc_section_detector import TOCSectionDetector

logger = logging.getLogger(__name__)


class HybridSectionDetector:
    """
    Multi-strategy section detector with fallback.

    Tries strategies in order of reliability:
    1. TOC-based (0.95 confidence) - Most reliable
    2. Heading-based (0.7-0.9 confidence) - Fallback
    3. Pattern matching (0.7 confidence) - Last resort

    Example:
        >>> detector = HybridSectionDetector(document, '10-K')
        >>> sections = detector.detect_sections()
        >>> for name, section in sections.items():
        ...     print(f"{name}: {section.confidence:.2f} ({section.detection_method})")
    """

    def __init__(
        self,
        document: Document,
        filing_type: Optional[str] = None,
        thresholds: Optional[DetectionThresholds] = None
    ):
        """
        Initialize hybrid detector.

        Args:
            document: Document to extract sections from
            filing_type: Filing type ('10-K', '10-Q', '8-K')
            thresholds: Detection thresholds configuration
        """
        self.document = document
        self.filing_type = filing_type
        self.thresholds = thresholds or DetectionThresholds()

        # Initialize strategies
        self.toc_detector = TOCSectionDetector(document)
        self.heading_detector = HeadingSectionDetector(document, filing_type)
        self.pattern_detector = SectionExtractor(filing_type)

    def detect_sections(self) -> Dict[str, Section]:
        """
        Detect sections using hybrid approach with fallback and validation.

        Returns:
            Dictionary mapping section names to Section objects with confidence scores
        """
        sections = {}

        # Strategy 1: TOC-based (most reliable)
        logger.debug("Trying TOC-based detection...")
        toc_sections = self.toc_detector.detect()
        if toc_sections:
            logger.info(f"TOC detection successful: {len(toc_sections)} sections found")
            sections.update(toc_sections)

            # Apply validation pipeline
            sections = self._validate_pipeline(sections, enable_cross_validation=True)
            return sections

        # Strategy 2: Heading-based (fallback)
        logger.debug("TOC detection failed, trying heading detection...")
        heading_sections = self.heading_detector.detect()
        if heading_sections:
            logger.info(f"Heading detection successful: {len(heading_sections)} sections found")
            sections.update(heading_sections)

            # Apply validation pipeline (skip expensive cross-validation)
            sections = self._validate_pipeline(sections, enable_cross_validation=False)
            return sections

        # Strategy 3: Pattern-based (last resort)
        logger.debug("Heading detection failed, trying pattern matching...")
        pattern_sections = self.pattern_detector.extract(self.document)
        if pattern_sections:
            logger.info(f"Pattern detection successful: {len(pattern_sections)} sections found")
            sections.update(pattern_sections)

            # Apply validation pipeline (minimal validation for pattern-based)
            sections = self._validate_pipeline(sections, enable_cross_validation=False)
            return sections

        logger.warning("All detection strategies failed, no sections found")
        return {}

    def _validate_pipeline(
        self,
        sections: Dict[str, Section],
        enable_cross_validation: bool = False
    ) -> Dict[str, Section]:
        """
        Apply validation pipeline to sections.

        Args:
            sections: Sections to validate
            enable_cross_validation: Whether to enable cross-validation

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

        # Get pattern-based sections for comparison
        try:
            pattern_sections = self.pattern_detector.extract(self.document)
        except Exception as e:
            logger.debug(f"Pattern extraction failed for cross-validation: {e}")
            pattern_sections = {}

        for name, section in sections.items():
            # Check if this section is also found by pattern matching
            found_in_patterns = False
            for pattern_name in pattern_sections.keys():
                if self._sections_similar_by_name(name, pattern_name):
                    found_in_patterns = True
                    break

            # Boost confidence if methods agree
            if found_in_patterns:
                section.confidence = min(
                    section.confidence * self.thresholds.cross_validation_boost,
                    1.0
                )
                section.validated = True
                logger.debug(
                    f"Section {name} validated by multiple methods, "
                    f"confidence boosted to {section.confidence:.2f}"
                )
            else:
                # Slight reduction if not validated
                section.confidence *= self.thresholds.disagreement_penalty
                section.validated = False

            validated[name] = section

        return validated

    def _validate_boundaries(self, sections: Dict[str, Section]) -> Dict[str, Section]:
        """
        Validate section boundaries for overlaps and gaps.

        Args:
            sections: Sections to validate

        Returns:
            Sections with validated boundaries
        """
        if not sections or len(sections) <= 1:
            return sections

        # Sort by start offset
        sorted_sections = sorted(
            sections.items(),
            key=lambda x: x[1].start_offset
        )

        validated = {}
        prev_section = None

        for name, section in sorted_sections:
            # Check for overlap with previous section
            if prev_section and section.start_offset > 0:
                prev_name, prev_sec = prev_section

                if section.start_offset < prev_sec.end_offset:
                    # Overlap detected - adjust boundary at midpoint
                    gap_mid = (prev_sec.end_offset + section.start_offset) // 2
                    prev_sec.end_offset = gap_mid
                    section.start_offset = gap_mid

                    # Reduce confidence due to boundary adjustment
                    section.confidence *= self.thresholds.boundary_overlap_penalty
                    prev_sec.confidence *= self.thresholds.boundary_overlap_penalty

                    logger.debug(f"Adjusted boundary between {prev_name} and {name}")

                # Check for large gap (might indicate missing section)
                elif prev_sec.end_offset > 0:
                    gap_size = section.start_offset - prev_sec.end_offset
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
                    logger.debug(
                        f"Merged duplicate sections for {best.name}, "
                        f"methods: {best.detection_method}"
                    )

                deduplicated[best.name] = best

        return deduplicated

    def _group_similar_sections(
        self, sections: Dict[str, Section]
    ) -> List[List[Section]]:
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
        # Check name similarity
        if self._sections_similar_by_name(section1.name, section2.name):
            return True

        # Check title similarity
        title1 = section1.title.lower().strip()
        title2 = section2.title.lower().strip()
        if title1 == title2:
            return True

        # Check for position overlap (if positions are set)
        if section1.start_offset > 0 and section2.start_offset > 0:
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

    def _sections_similar_by_name(self, name1: str, name2: str) -> bool:
        """
        Check if two section names are similar.

        Args:
            name1: First section name
            name2: Second section name

        Returns:
            True if names are similar
        """
        # Normalize names for comparison
        norm1 = name1.lower().replace('_', ' ').replace('-', ' ').strip()
        norm2 = name2.lower().replace('_', ' ').replace('-', ' ').strip()

        return norm1 == norm2

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
        if self.filing_type in self.thresholds.thresholds_by_filing_type:
            filing_thresholds = self.thresholds.thresholds_by_filing_type[self.filing_type]
            min_conf = filing_thresholds.get('min_confidence', min_conf)

        filtered = {}
        for name, section in sections.items():
            if section.confidence >= min_conf:
                filtered[name] = section
            else:
                logger.debug(
                    f"Filtered out section {name} with confidence "
                    f"{section.confidence:.2f} < {min_conf:.2f}"
                )

        return filtered
