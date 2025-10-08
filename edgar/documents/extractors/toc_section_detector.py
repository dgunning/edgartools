"""
TOC-based section detection strategy.

Detects sections using Table of Contents structure. Provides highest
confidence (0.95) but requires access to original HTML content.

NOTE: This implementation is currently limited because the Document class
on main does not store original_html. This detector will return None until
the Document class is enhanced to preserve HTML content, or until we integrate
with the existing edgar.htmltools module that has access to HTML.
"""

import logging
from typing import Dict, Optional

from edgar.documents.document import Document, Section
from edgar.documents.nodes import SectionNode
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

logger = logging.getLogger(__name__)


class TOCSectionDetector:
    """
    TOC-based section detection strategy.

    Uses Table of Contents structure to identify section boundaries.
    Provides high confidence (0.95) detection when HTML is available.

    Current Limitation:
        The Document class does not currently store original_html, so this
        detector will return None. This is a known limitation that will be
        addressed in future integration work.
    """

    def __init__(self, document: Document):
        """
        Initialize TOC-based detector.

        Args:
            document: Document to analyze
        """
        self.document = document
        self.toc_analyzer = TOCAnalyzer()

    def detect(self) -> Optional[Dict[str, Section]]:
        """
        Detect sections using TOC structure.

        Returns:
            Dictionary of sections if successful, None if HTML not available

        Note:
            Currently returns None because Document.metadata.original_html
            is not available on main branch. This will be implemented once
            HTML preservation is added to the Document class.
        """
        # Check if original HTML is available
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            logger.debug("TOC detection unavailable: original_html not in document metadata")
            return None

        try:
            # Analyze TOC structure
            toc_mapping = self.toc_analyzer.analyze_toc_structure(html_content)

            if not toc_mapping:
                logger.debug("No TOC structure found in HTML")
                return None

            sections = {}

            # For each section found in TOC
            for section_name, anchor_id in toc_mapping.items():
                # Create a section node
                # Note: Without access to the HTML tree, we can't extract the actual content
                # This would require coordination with the parser to preserve element IDs
                section_node = SectionNode(section_name=section_name)

                # Create Section with high TOC confidence
                section = Section(
                    name=section_name,
                    title=section_name,  # Would need better title extraction
                    node=section_node,
                    start_offset=0,  # Would need position tracking
                    end_offset=0,  # Would need position tracking
                    confidence=0.95,  # TOC-based = high confidence
                    detection_method='toc'
                )

                sections[section_name] = section

            if sections:
                logger.info(f"TOC detection found {len(sections)} sections")
                return sections

            return None

        except Exception as e:
            logger.warning(f"TOC detection failed: {e}")
            return None


def get_section_text(document: Document, section_name: str) -> Optional[str]:
    """
    Get section text using TOC-based extraction.

    This is a placeholder for future integration with edgar.htmltools
    or enhanced Document class that preserves HTML structure.

    Args:
        document: Document to extract from
        section_name: Section name (e.g., 'item_1', 'item_1a')

    Returns:
        Section text if available, None otherwise

    Note:
        Not currently implemented. Will require either:
        1. Document class enhancement to store HTML with element IDs
        2. Integration with edgar.htmltools for HTML-based extraction
        3. Parser enhancement to track element positions during parsing
    """
    logger.debug(f"get_section_text not implemented: {section_name}")
    return None


def get_available_sections(document: Document) -> list[str]:
    """
    Get list of available sections from TOC.

    Args:
        document: Document to analyze

    Returns:
        List of section names found in TOC

    Note:
        Not currently implemented due to original_html limitation.
    """
    html_content = getattr(document.metadata, 'original_html', None)
    if not html_content:
        return []

    try:
        analyzer = TOCAnalyzer()
        toc_mapping = analyzer.analyze_toc_structure(html_content)
        return list(toc_mapping.keys())
    except Exception as e:
        logger.warning(f"Failed to get available sections: {e}")
        return []
