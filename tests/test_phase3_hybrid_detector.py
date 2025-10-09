"""
Test Phase 3 hybrid section detector.

Tests for HybridSectionDetector orchestration and validation pipeline.
"""

import pytest
from edgar.documents.document import Document, DocumentMetadata, Section
from edgar.documents.nodes import DocumentNode, HeadingNode, ParagraphNode, TextNode, SectionNode
from edgar.documents.types import HeaderInfo
from edgar.documents.config import DetectionThresholds
from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector


class TestHybridDetectorCreation:
    """Test hybrid detector initialization."""

    def test_detector_creation_minimal(self):
        """Test creating detector with minimal arguments."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc)
        assert detector.document == doc
        assert detector.filing_type is None
        assert detector.thresholds is not None  # Uses default

    def test_detector_creation_with_filing_type(self):
        """Test creating detector with filing type."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc, filing_type='10-K')
        assert detector.filing_type == '10-K'

    def test_detector_creation_with_thresholds(self):
        """Test creating detector with custom thresholds."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        thresholds = DetectionThresholds(min_confidence=0.75)
        detector = HybridSectionDetector(doc, thresholds=thresholds)
        assert detector.thresholds.min_confidence == 0.75

    def test_detector_has_all_strategies(self):
        """Test that detector initializes all strategies."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc, '10-K')
        assert detector.toc_detector is not None
        assert detector.heading_detector is not None
        assert detector.pattern_detector is not None


class TestStrategyFallback:
    """Test strategy fallback chain."""

    def test_no_detection_returns_empty(self):
        """Test that no sections returns empty dict."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc)
        sections = detector.detect_sections()

        assert sections == {}

    def test_heading_strategy_used_when_available(self):
        """Test that heading strategy is used when headings available."""
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

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc)
        sections = detector.detect_sections()

        # Should find section via heading detection
        assert len(sections) > 0
        assert 'item_1' in sections
        assert sections['item_1'].detection_method == 'heading'

    def test_toc_strategy_not_available_without_html(self):
        """Test that TOC strategy gracefully fails without HTML."""
        root = DocumentNode()
        metadata = DocumentMetadata()
        # No original_html set
        doc = Document(root=root, metadata=metadata)

        detector = HybridSectionDetector(doc)

        # TOC should fail, should fallback to other strategies
        # Since we have no headings either, should return empty
        sections = detector.detect_sections()
        assert sections == {}


class TestValidationPipeline:
    """Test validation pipeline functionality."""

    def test_confidence_filtering(self):
        """Test that low-confidence sections are filtered out."""
        root = DocumentNode()

        # Add heading with low confidence
        heading = HeadingNode(level=1, content="Item 1")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.5,  # Below default 0.6 threshold
            text="Item 1",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        detector = HybridSectionDetector(doc)
        sections = detector.detect_sections()

        # Should be filtered out
        assert len(sections) == 0

    def test_confidence_filtering_with_custom_threshold(self):
        """Test confidence filtering with custom threshold."""
        root = DocumentNode()

        heading = HeadingNode(level=1, content="Item 1")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.65,
            text="Item 1",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        # With default threshold (0.6), should pass
        detector1 = HybridSectionDetector(doc)
        sections1 = detector1.detect_sections()
        assert len(sections1) == 1

        # With strict threshold (0.75), should fail
        strict_thresholds = DetectionThresholds.strict()
        detector2 = HybridSectionDetector(doc, thresholds=strict_thresholds)
        sections2 = detector2.detect_sections()
        assert len(sections2) == 0

    def test_filing_type_specific_thresholds(self):
        """Test filing-type-specific confidence thresholds."""
        root = DocumentNode()

        heading = HeadingNode(level=1, content="Item 1")
        heading.header_info = HeaderInfo(
            level=1,
            confidence=0.63,  # Between 10-Q (0.6) and 10-K (0.65) thresholds
            text="Item 1",
            detection_method='style',
            is_item=True,
            item_number='1'
        )
        root.add_child(heading)

        doc = Document(root=root, metadata=DocumentMetadata())

        # 10-Q threshold is 0.60, should pass
        detector_10q = HybridSectionDetector(doc, filing_type='10-Q')
        sections_10q = detector_10q.detect_sections()
        assert len(sections_10q) == 1

        # 10-K threshold is 0.65, should fail
        detector_10k = HybridSectionDetector(doc, filing_type='10-K')
        sections_10k = detector_10k.detect_sections()
        assert len(sections_10k) == 0


class TestDeduplication:
    """Test section deduplication."""

    def test_sections_similar_by_name(self):
        """Test that similar section names are detected."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())
        detector = HybridSectionDetector(doc)

        # Test name similarity
        assert detector._sections_similar_by_name('business', 'business')
        assert detector._sections_similar_by_name('risk_factors', 'risk-factors')
        assert detector._sections_similar_by_name('item_1', 'item 1')
        assert not detector._sections_similar_by_name('business', 'risk_factors')

    def test_sections_similar_by_title(self):
        """Test that sections with same title are similar."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())
        detector = HybridSectionDetector(doc)

        node1 = SectionNode(section_name='sec1')
        node2 = SectionNode(section_name='sec2')

        section1 = Section(
            name='business',
            title='Business Overview',
            node=node1,
            confidence=0.8,
            detection_method='heading'
        )

        section2 = Section(
            name='item_1',
            title='Business Overview',
            node=node2,
            confidence=0.9,
            detection_method='pattern'
        )

        assert detector._sections_similar(section1, section2)

    def test_deduplication_keeps_highest_confidence(self):
        """Test that deduplication keeps section with highest confidence."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())
        detector = HybridSectionDetector(doc)

        node1 = SectionNode(section_name='sec1')
        node2 = SectionNode(section_name='sec2')

        # Two sections with same name but different confidence
        sections = {
            'business_low': Section(
                name='business',
                title='Business',
                node=node1,
                confidence=0.7,
                detection_method='pattern'
            ),
            'business_high': Section(
                name='business',
                title='Business',
                node=node2,
                confidence=0.9,
                detection_method='heading'
            )
        }

        deduplicated = detector._deduplicate(sections)

        # Should keep only one
        assert len(deduplicated) == 1

        # Should be the one with higher confidence
        section = list(deduplicated.values())[0]
        assert section.confidence >= 0.9  # May be boosted for multi-method


class TestBoundaryValidation:
    """Test boundary validation."""

    def test_boundary_validation_with_valid_sections(self):
        """Test boundary validation with non-overlapping sections."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())
        detector = HybridSectionDetector(doc)

        node1 = SectionNode(section_name='sec1')
        node2 = SectionNode(section_name='sec2')

        sections = {
            'section1': Section(
                name='section1',
                title='Section 1',
                node=node1,
                start_offset=0,
                end_offset=100,
                confidence=0.9,
                detection_method='heading'
            ),
            'section2': Section(
                name='section2',
                title='Section 2',
                node=node2,
                start_offset=100,
                end_offset=200,
                confidence=0.9,
                detection_method='heading'
            )
        }

        validated = detector._validate_boundaries(sections)

        # Should maintain confidence (no overlap)
        assert validated['section1'].confidence == 0.9
        assert validated['section2'].confidence == 0.9

    def test_boundary_validation_with_overlap(self):
        """Test boundary validation adjusts overlapping sections."""
        root = DocumentNode()
        doc = Document(root=root, metadata=DocumentMetadata())
        detector = HybridSectionDetector(doc)

        node1 = SectionNode(section_name='sec1')
        node2 = SectionNode(section_name='sec2')

        sections = {
            'section1': Section(
                name='section1',
                title='Section 1',
                node=node1,
                start_offset=0,
                end_offset=150,  # Overlaps with section2
                confidence=0.9,
                detection_method='heading'
            ),
            'section2': Section(
                name='section2',
                title='Section 2',
                node=node2,
                start_offset=100,
                end_offset=200,
                confidence=0.9,
                detection_method='heading'
            )
        }

        validated = detector._validate_boundaries(sections)

        # Confidence should be reduced due to overlap
        assert validated['section1'].confidence < 0.9
        assert validated['section2'].confidence < 0.9

        # Boundaries should be adjusted
        assert validated['section1'].end_offset == validated['section2'].start_offset


class TestIntegration:
    """Test integration scenarios."""

    def test_hybrid_detector_can_be_imported(self):
        """Test that hybrid detector is available."""
        from edgar.documents.extractors import HybridSectionDetector
        assert HybridSectionDetector is not None

    def test_end_to_end_with_headings(self):
        """Test end-to-end detection with heading-based strategy."""
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
        para2.add_child(TextNode(content="Risk content"))
        root.add_child(para2)

        doc = Document(root=root, metadata=DocumentMetadata())

        # Detect with hybrid detector
        detector = HybridSectionDetector(doc, filing_type='10-K')
        sections = detector.detect_sections()

        # Should find both sections
        assert len(sections) == 2
        assert 'item_1' in sections
        assert 'item_1a' in sections

        # All sections should have confidence and method
        for section in sections.values():
            assert section.confidence > 0.0
            assert section.detection_method in ['heading', 'pattern', 'toc', 'heading,pattern']
            assert hasattr(section, 'validated')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
