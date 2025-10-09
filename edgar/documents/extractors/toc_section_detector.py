"""
TOC-based section detection strategy.

Detects sections using Table of Contents structure. Provides highest
confidence (0.95) and includes full text extraction capabilities.

This detector wraps SECSectionExtractor which has proven implementations of:
- Multi-column TOC support (checks all preceding table cells)
- Nested anchor handling (traverses up to find content container)
- Full section text extraction
"""

import logging
from typing import Dict, Optional

from edgar.documents.document import Document, Section
from edgar.documents.nodes import SectionNode
from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor

logger = logging.getLogger(__name__)


class TOCSectionDetector:
    """
    TOC-based section detection strategy.

    Uses Table of Contents structure to identify section boundaries and
    extract full section content. Provides high confidence (0.95) detection.

    This implementation wraps the proven SECSectionExtractor which includes:
    - Multi-column TOC support for edge cases like Morgan Stanley
    - Nested anchor handling for sections with no sibling content
    - Complete text extraction with proper boundary detection
    """

    def __init__(self, document: Document):
        """
        Initialize TOC-based detector.

        Args:
            document: Document to analyze (must have metadata.original_html)
        """
        self.document = document
        self.extractor = SECSectionExtractor(document)

    def detect(self) -> Optional[Dict[str, Section]]:
        """
        Detect sections using TOC structure.

        Returns:
            Dictionary mapping section names to Section objects, or None if unavailable

        Note:
            Requires document.metadata.original_html to be available.
            Returns None if HTML is not available or no sections found.
        """
        # Check if original HTML is available
        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            logger.debug("TOC detection unavailable: original_html not in document metadata")
            return None

        try:
            # Get available sections from TOC
            available = self.extractor.get_available_sections()
            if not available:
                logger.debug("No sections found in TOC")
                return None

            sections = {}

            # Extract each section
            for section_name in available:
                # Get section text
                section_text = self.extractor.get_section_text(section_name)
                if not section_text:
                    # Skip sections that can't be extracted
                    logger.debug(f"Skipping {section_name}: no text extracted")
                    continue

                # Get section metadata
                section_info = self.extractor.get_section_info(section_name)
                if not section_info:
                    logger.debug(f"Skipping {section_name}: no section info")
                    continue

                # Create section node (placeholder - actual content extracted lazily)
                section_node = SectionNode(section_name=section_name)

                # Create Section with TOC confidence
                section = Section(
                    name=section_name,
                    title=section_info.get('canonical_name', section_name),
                    node=section_node,
                    start_offset=0,  # Would need actual offsets from parsing
                    end_offset=len(section_text),
                    confidence=0.95,  # TOC-based = high confidence
                    detection_method='toc'
                )

                sections[section_name] = section

            if sections:
                logger.info(f"TOC detection found {len(sections)} sections")
                return sections

            return None

        except Exception as e:
            logger.warning(f"TOC detection failed: {e}", exc_info=True)
            return None


def get_section_text(document: Document, section_name: str) -> Optional[str]:
    """
    Get section text using TOC-based extraction.

    Args:
        document: Document to extract from
        section_name: Section name (e.g., 'Item 1', 'Item 1A')

    Returns:
        Section text if available, None otherwise
    """
    html_content = getattr(document.metadata, 'original_html', None)
    if not html_content:
        return None

    try:
        extractor = SECSectionExtractor(document)
        return extractor.get_section_text(section_name)
    except Exception as e:
        logger.warning(f"Failed to get section text for {section_name}: {e}")
        return None


def get_available_sections(document: Document) -> list[str]:
    """
    Get list of available sections from TOC.

    Args:
        document: Document to analyze

    Returns:
        List of section names found in TOC
    """
    html_content = getattr(document.metadata, 'original_html', None)
    if not html_content:
        return []

    try:
        extractor = SECSectionExtractor(document)
        return extractor.get_available_sections()
    except Exception as e:
        logger.warning(f"Failed to get available sections: {e}")
        return []
