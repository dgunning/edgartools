"""
Test Phase 2 detection strategies.

Tests for TOCSectionDetector and HeadingSectionDetector.
"""

import pytest
from edgar.documents.document import Document, DocumentMetadata, Section
from edgar.documents.nodes import DocumentNode, HeadingNode, ParagraphNode, TextNode
from edgar.documents.types import HeaderInfo
from edgar.documents.extractors.toc_section_detector import TOCSectionDetector
from edgar.documents.extractors.heading_section_detector import HeadingSectionDetector


class TestTOCSectionDetector:
    """Test TOC-based section detection."""

    def test_detector_creation(self):
        """Test creating TOCSectionDetector."""
        root = DocumentNode()
        metadata = DocumentMetadata()
        doc = Document(root=root, metadata=metadata)

        detector = TOCSectionDetector(doc)
        assert detector.document == doc
        assert detector.toc_analyzer is not None

    def test_detect_without_html(self):
        """Test detection fails gracefully without original_html."""
        root = DocumentNode()
        metadata = DocumentMetadata()
        doc = Document(root=root, metadata=metadata)

        detector = TOCSectionDetector(doc)
        sections = detector.detect()

        # Should return None when HTML not available
        assert sections is None

    def test_detect_with_html_no_toc(self):
        """Test detection with HTML but no TOC structure."""
        root = DocumentNode()
        metadata = DocumentMetadata()

        # Add original_html with no TOC
        metadata.original_html = "<html><body><p>No TOC here</p></body></html>"
        doc = Document(root=root, metadata=metadata)

        detector = TOCSectionDetector(doc)
        sections = detector.detect()

        # Should return None when no TOC found
        assert sections is None


class TestHeadingSectionDetector:
    """Test heading-based section detection."""

    def test_detector_creation(self):
        """Test creating HeadingSectionDetector."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc, filing_type='10-K')
        assert detector.document == doc
        assert detector.filing_type == '10-K'

    def test_detect_without_headings(self):
        """Test detection with no headings."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should return None when no headings
        assert sections is None

    def test_detect_headings_without_header_info(self):
        """Test detection with headings but no HeaderInfo."""
        root = DocumentNode()

        # Add heading without header_info
        heading = HeadingNode(level=1, content="Some Heading")
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should return None when headings lack header_info
        assert sections is None

    def test_detect_headings_low_confidence(self):
        """Test detection filters out low-confidence headings."""
        root = DocumentNode()

        # Add heading with low confidence
        heading = HeadingNode(level=1, content="Item 1 - Business")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.5,  # Below 0.7 threshold
            text="Item 1 - Business",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should return None when all headings below confidence threshold
        assert sections is None

    def test_detect_non_item_headings(self):
        """Test detection ignores non-item headings."""
        root = DocumentNode()

        # Add heading that's not an item
        heading = HeadingNode(level=1, content="General Heading")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.9,
            text="General Heading",
            detection_method='style',
            is_item=False,
            item_number=None
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should return None when no item headings
        assert sections is None

    def test_detect_valid_item_heading(self):
        """Test successful detection of valid item heading."""
        root = DocumentNode()

        # Add valid item heading
        heading = HeadingNode(level=1, content="Item 1 - Business")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.85,
            text="Item 1 - Business",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        # Add some content after heading
        para = ParagraphNode()
        text = TextNode(content="Business description")
        para.add_child(text)
        root.add_child(para)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should find one section
        assert sections is not None
        assert len(sections) == 1
        assert 'item_1' in sections

        section = sections['item_1']
        assert section.title == "Item 1 - Business"
        assert section.confidence == 0.85
        assert section.detection_method == 'heading'

    def test_detect_multiple_item_headings(self):
        """Test detection of multiple item headings."""
        root = DocumentNode()

        # Item 1
        heading1 = HeadingNode(level=1, content="Item 1 - Business")
        heading1.header_info = HeaderInfo(
            level=1,
            confidence=0.9,
            text="Item 1 - Business",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading1)

        para1 = ParagraphNode()
        para1.add_child(TextNode(content="Business content"))
        root.add_child(para1)

        # Item 1A
        heading2 = HeadingNode(level=1, content="Item 1A - Risk Factors")
        heading2.header_info = HeaderInfo(
            level=1,
            confidence=0.95,
            text="Item 1A - Risk Factors",
            detection_method='pattern',
            is_item=True,
            item_number='1A'
        )
        root.add_child(heading2)

        para2 = ParagraphNode()
        para2.add_child(TextNode(content="Risk factors content"))
        root.add_child(para2)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Should find two sections
        assert sections is not None
        assert len(sections) == 2
        assert 'item_1' in sections
        assert 'item_1a' in sections

        assert sections['item_1'].confidence == 0.9
        assert sections['item_1a'].confidence == 0.95

    def test_section_extraction_includes_content(self):
        """Test that section extraction includes content between headings."""
        root = DocumentNode()

        # Item 1
        heading1 = HeadingNode(level=1, content="Item 1")
        heading1.header_info = HeaderInfo(
            level=1,
            confidence=0.9,
            text="Item 1",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading1)

        # Content for Item 1
        para1 = ParagraphNode()
        para1.add_child(TextNode(content="First paragraph"))
        root.add_child(para1)

        para2 = ParagraphNode()
        para2.add_child(TextNode(content="Second paragraph"))
        root.add_child(para2)

        # Item 2 (should stop Item 1 section)
        heading2 = HeadingNode(level=1, content="Item 2")
        heading2.header_info = HeaderInfo(
            level=1,
            confidence=0.9,
            text="Item 2",
            detection_method='style',
            is_item=True,
            item_number='2'
        )
        root.add_child(heading2)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HeadingSectionDetector(doc)
        sections = detector.detect()

        # Item 1 section should include both paragraphs
        assert sections is not None
        item1_section = sections['item_1']

        # Section node should have content
        assert item1_section.node is not None
        assert len(item1_section.node.children) > 0


class TestDetectorIntegration:
    """Test detector integration."""

    def test_both_detectors_can_be_imported(self):
        """Test that both detectors are available."""
        from edgar.documents.extractors import TOCSectionDetector, HeadingSectionDetector

        assert TOCSectionDetector is not None
        assert HeadingSectionDetector is not None

    def test_detectors_return_compatible_sections(self):
        """Test that both detectors return compatible Section objects."""
        root = DocumentNode()

        # Add item heading
        heading = HeadingNode(level=1, content="Item 1")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.9,
            text="Item 1",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        # Heading detector should work
        heading_detector = HeadingSectionDetector(doc)
        heading_sections = heading_detector.detect()

        assert heading_sections is not None
        assert all(isinstance(s, Section) for s in heading_sections.values())
        assert all(hasattr(s, 'confidence') for s in heading_sections.values())
        assert all(hasattr(s, 'detection_method') for s in heading_sections.values())

        # TOC detector should return None (no HTML)
        toc_detector = TOCSectionDetector(doc)
        toc_sections = toc_detector.detect()

        assert toc_sections is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
