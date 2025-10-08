"""
Test backward compatibility for Phase 1 changes to Section class.

This test ensures that adding confidence, detection_method, and validated fields
to the Section dataclass doesn't break existing code.
"""

import pytest
from edgar.documents.document import Section, Document, DocumentMetadata
from edgar.documents.nodes import SectionNode, DocumentNode
from edgar.documents.config import ParserConfig, DetectionThresholds


class TestSectionBackwardCompatibility:
    """Test Section class backward compatibility."""

    def test_section_creation_with_minimal_args(self):
        """Test creating Section with just required arguments."""
        section_node = SectionNode(section_name="test")
        section = Section(
            name="business",
            title="Business Overview",
            node=section_node
        )

        # Should use defaults for new fields
        assert section.confidence == 1.0
        assert section.detection_method == 'unknown'
        assert section.validated is False
        assert section.start_offset == 0
        assert section.end_offset == 0

    def test_section_creation_with_all_old_args(self):
        """Test creating Section with all pre-existing arguments."""
        section_node = SectionNode(section_name="test")
        section = Section(
            name="risk_factors",
            title="Risk Factors",
            node=section_node,
            start_offset=100,
            end_offset=500
        )

        # Should use defaults for new fields
        assert section.confidence == 1.0
        assert section.detection_method == 'unknown'
        assert section.validated is False

    def test_section_creation_with_new_fields(self):
        """Test creating Section with new confidence fields."""
        section_node = SectionNode(section_name="test")
        section = Section(
            name="mda",
            title="MD&A",
            node=section_node,
            start_offset=500,
            end_offset=1000,
            confidence=0.95,
            detection_method='toc',
            validated=True
        )

        assert section.confidence == 0.95
        assert section.detection_method == 'toc'
        assert section.validated is True

    def test_section_text_method_still_works(self):
        """Test that Section.text() method still works."""
        section_node = SectionNode(section_name="test")
        section = Section(
            name="test",
            title="Test Section",
            node=section_node
        )

        # Should not raise an error
        # (will be empty since node has no content, but method should work)
        text = section.text()
        assert isinstance(text, str)

    def test_section_tables_method_still_works(self):
        """Test that Section.tables() method still works."""
        section_node = SectionNode(section_name="test")
        section = Section(
            name="test",
            title="Test Section",
            node=section_node
        )

        # Should return empty list (no tables in node)
        tables = section.tables()
        assert isinstance(tables, list)
        assert len(tables) == 0


class TestDetectionThresholdsConfig:
    """Test DetectionThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = DetectionThresholds()

        assert thresholds.min_confidence == 0.6
        assert thresholds.enable_cross_validation is False
        assert thresholds.cross_validation_boost == 1.15
        assert thresholds.disagreement_penalty == 0.95
        assert thresholds.boundary_overlap_penalty == 0.9

    def test_strict_thresholds(self):
        """Test strict threshold preset."""
        thresholds = DetectionThresholds.strict()

        assert thresholds.min_confidence == 0.75
        assert thresholds.enable_cross_validation is True
        assert thresholds.cross_validation_boost == 1.2

    def test_lenient_thresholds(self):
        """Test lenient threshold preset."""
        thresholds = DetectionThresholds.lenient()

        assert thresholds.min_confidence == 0.50
        assert thresholds.enable_cross_validation is False

    def test_filing_type_specific_thresholds(self):
        """Test filing-type-specific thresholds."""
        thresholds = DetectionThresholds()

        assert '10-K' in thresholds.thresholds_by_filing_type
        assert '10-Q' in thresholds.thresholds_by_filing_type
        assert '8-K' in thresholds.thresholds_by_filing_type

        assert thresholds.thresholds_by_filing_type['10-K']['min_confidence'] == 0.65
        assert thresholds.thresholds_by_filing_type['10-Q']['min_confidence'] == 0.60
        assert thresholds.thresholds_by_filing_type['8-K']['min_confidence'] == 0.55


class TestParserConfigIntegration:
    """Test ParserConfig integration with DetectionThresholds."""

    def test_parser_config_with_default_thresholds(self):
        """Test ParserConfig with default thresholds (None)."""
        config = ParserConfig()

        # Should be None by default (lazy initialization)
        assert config.detection_thresholds is None

    def test_parser_config_with_custom_thresholds(self):
        """Test ParserConfig with custom thresholds."""
        thresholds = DetectionThresholds(min_confidence=0.75)
        config = ParserConfig(detection_thresholds=thresholds)

        assert config.detection_thresholds is not None
        assert config.detection_thresholds.min_confidence == 0.75

    def test_parser_config_backward_compatibility(self):
        """Test that existing ParserConfig usage still works."""
        # Old usage pattern - should not raise
        config = ParserConfig(
            max_document_size=100_000,
            strict_mode=True,
            extract_xbrl=True
        )

        assert config.max_document_size == 100_000
        assert config.strict_mode is True
        assert config.extract_xbrl is True


class TestSectionExtractorCompatibility:
    """Test that SectionExtractor works with new Section fields."""

    def test_section_extractor_creates_sections_with_confidence(self):
        """Test that SectionExtractor creates sections with confidence scores."""
        from edgar.documents.extractors.section_extractor import SectionExtractor

        # Create simple document
        root = DocumentNode()
        metadata = DocumentMetadata(filing_type='10-K')
        doc = Document(root=root, metadata=metadata)

        # Extract sections (will be empty, but should work)
        extractor = SectionExtractor(filing_type='10-K')
        sections = extractor.extract(doc)

        # Should return dict (empty since doc has no content)
        assert isinstance(sections, dict)

        # If any sections were created, they should have confidence
        for section in sections.values():
            assert hasattr(section, 'confidence')
            assert hasattr(section, 'detection_method')
            assert section.detection_method == 'pattern'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
