"""
Heading-based section detection strategy.

Detects sections by analyzing heading nodes with HeaderInfo metadata.
This strategy provides moderate confidence (0.7-0.9) and serves as a
fallback when TOC-based detection is not available.
"""

import logging
from typing import Dict, Optional

from edgar.documents.document import Document, Section
from edgar.documents.nodes import HeadingNode, SectionNode
from edgar.documents.types import HeaderInfo

logger = logging.getLogger(__name__)


class HeadingSectionDetector:
    """
    Heading-based section detection using HeaderInfo.

    Analyzes heading nodes that have been annotated with HeaderInfo
    during parsing. Detects sections based on:
    - Item numbers (Item 1, Item 1A, etc.)
    - Heading confidence scores
    - Heading hierarchy

    Provides moderate confidence (0.7-0.9) detection.
    """

    def __init__(
        self,
        document: Document,
        form: Optional[str] = None,
        min_confidence: float = 0.5  # Lower threshold, let hybrid detector filter
    ):
        """
        Initialize heading-based detector.

        Args:
            document: Document to analyze
            form: Optional filing type for context ('10-K', '10-Q', '8-K')
            min_confidence: Minimum confidence for headings (default 0.5)
        """
        self.document = document
        self.form = form
        self.min_confidence = min_confidence

    def detect(self) -> Optional[Dict[str, Section]]:
        """
        Detect sections from heading nodes with HeaderInfo.

        Returns:
            Dictionary of sections if successful, None if no sections found
        """
        try:
            # Get heading nodes from document
            headings = self.document.headings
            if not headings:
                logger.debug("No headings found in document")
                return None

            sections = {}

            for heading in headings:
                # Check if heading has header info
                if not hasattr(heading, 'header_info') or not heading.header_info:
                    continue

                header_info = heading.header_info

                # Only use headings with sufficient confidence
                if header_info.confidence < self.min_confidence:
                    continue

                # Check if it's an item header
                if not header_info.is_item:
                    continue

                # Extract section from this heading
                section = self._extract_section_from_heading(heading, header_info)
                if section:
                    section.confidence = header_info.confidence
                    section.detection_method = 'heading'
                    sections[section.name] = section

            if not sections:
                logger.debug("No item headers found with sufficient confidence")
                return None

            logger.info(f"Heading detection found {len(sections)} sections")
            return sections

        except Exception as e:
            logger.warning(f"Heading detection failed: {e}")
            return None

    def _extract_section_from_heading(
        self, heading: HeadingNode, header_info: HeaderInfo
    ) -> Optional[Section]:
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
            if header_info.item_number:
                # Normalize: "1A" -> "item_1a", "7" -> "item_7"
                section_name = f"item_{header_info.item_number.replace('.', '_').lower()}"
            else:
                section_name = "unknown"

            # Create section node
            section_node = SectionNode(section_name=section_name)

            # Find next heading at same or higher level to determine section end
            current_level = header_info.level
            parent = heading.parent
            if not parent:
                logger.debug(f"Heading {header_info.text} has no parent")
                return None

            # Find heading position in parent's children
            try:
                heading_index = parent.children.index(heading)
            except ValueError:
                logger.debug(f"Could not find heading in parent's children")
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

            # Parse section name to extract part and item identifiers
            part, item = Section.parse_section_name(section_name)

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
