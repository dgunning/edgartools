"""
Test 10-Q section detection with part-aware naming.

This module tests the hierarchical section detection for 10-Q filings
where Item 1 appears in both Part I and Part II with different content.
"""

import pytest
from pathlib import Path
from edgar.documents import parse_html, ParserConfig


@pytest.fixture
def aapl_10q_doc():
    """Load AAPL 10-Q fixture as parsed document."""
    fixture_path = Path("tests/fixtures/html/aapl/10q/aapl-10-q-2025-08-01.html")
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    html_content = fixture_path.read_text()
    config = ParserConfig(form='10-Q', detect_sections=True)
    return parse_html(html_content, config=config)


class TestTOCAnalyzerPartDetection:
    """Test TOC Analyzer's ability to detect and track part boundaries."""

    def test_part_detection_in_toc(self, aapl_10q_doc):
        """Verify part boundaries are detected in TOC structure."""
        sections = aapl_10q_doc.sections

        # Check we have part-aware section names
        part_i_sections = [name for name in sections.keys() if name.startswith('part_i_')]
        part_ii_sections = [name for name in sections.keys() if name.startswith('part_ii_')]

        assert len(part_i_sections) > 0, "Should detect Part I sections"
        assert len(part_ii_sections) > 0, "Should detect Part II sections"

    def test_correct_10q_structure(self, aapl_10q_doc):
        """Verify 10-Q has correct structure: Part I (4 items) + Part II (7 items)."""
        sections = aapl_10q_doc.sections

        part_i_sections = [name for name in sections.keys() if name.startswith('part_i_')]
        part_ii_sections = [name for name in sections.keys() if name.startswith('part_ii_')]

        assert len(part_i_sections) == 4, f"Part I should have 4 items, got {len(part_i_sections)}"
        assert len(part_ii_sections) == 7, f"Part II should have 7 items, got {len(part_ii_sections)}"

    def test_item_1_in_both_parts(self, aapl_10q_doc):
        """Verify Item 1 appears in both Part I and Part II with distinct names."""
        sections = aapl_10q_doc.sections

        assert 'part_i_item_1' in sections, "Should have Part I Item 1"
        assert 'part_ii_item_1' in sections, "Should have Part II Item 1"

        # Verify they're different sections
        part_i_item_1 = sections['part_i_item_1']
        part_ii_item_1 = sections['part_ii_item_1']

        assert part_i_item_1 != part_ii_item_1, "Part I and Part II Item 1 should be distinct"


class TestSectionDataclass:
    """Test Section dataclass part and item fields."""

    def test_section_has_part_field(self, aapl_10q_doc):
        """Verify Section objects have part field populated."""
        part_i_item_1 = aapl_10q_doc.sections.get('part_i_item_1')
        assert part_i_item_1 is not None
        assert part_i_item_1.part == 'I', f"Part field should be 'I', got {part_i_item_1.part}"

    def test_section_has_item_field(self, aapl_10q_doc):
        """Verify Section objects have item field populated."""
        part_i_item_1 = aapl_10q_doc.sections.get('part_i_item_1')
        assert part_i_item_1 is not None
        assert part_i_item_1.item == '1', f"Item field should be '1', got {part_i_item_1.item}"

    def test_part_and_item_for_multiple_sections(self, aapl_10q_doc):
        """Verify part/item fields are correct across multiple sections."""
        test_cases = [
            ('part_i_item_1', 'I', '1'),
            ('part_i_item_2', 'I', '2'),
            ('part_ii_item_1', 'II', '1'),
            ('part_ii_item_1a', 'II', '1A'),
            ('part_ii_item_2', 'II', '2'),
        ]

        for section_name, expected_part, expected_item in test_cases:
            section = aapl_10q_doc.sections.get(section_name)
            assert section is not None, f"Section {section_name} should exist"
            assert section.part == expected_part, f"{section_name}: part should be {expected_part}, got {section.part}"
            assert section.item == expected_item, f"{section_name}: item should be {expected_item}, got {section.item}"


class TestSectionParsing:
    """Test Section.parse_section_name() static method."""

    def test_parse_10q_section_name(self):
        """Test parsing 10-Q part-aware section names."""
        from edgar.documents.document import Section

        assert Section.parse_section_name('part_i_item_1') == ('I', '1')
        assert Section.parse_section_name('part_ii_item_1') == ('II', '1')
        assert Section.parse_section_name('part_i_item_1a') == ('I', '1A')
        assert Section.parse_section_name('part_ii_item_2') == ('II', '2')

    def test_parse_10k_section_name(self):
        """Test parsing 10-K simple section names."""
        from edgar.documents.document import Section

        assert Section.parse_section_name('item_1') == (None, '1')
        assert Section.parse_section_name('item_1a') == (None, '1A')
        assert Section.parse_section_name('item_7') == (None, '7')

    def test_parse_non_item_section_name(self):
        """Test parsing non-item section names."""
        from edgar.documents.document import Section

        assert Section.parse_section_name('risk_factors') == (None, None)
        assert Section.parse_section_name('md_and_a') == (None, None)


class TestDocumentAPI:
    """Test Document.get_section() API with part parameter."""

    def test_direct_lookup_with_full_name(self, aapl_10q_doc):
        """Test direct lookup using full part-aware name."""
        section = aapl_10q_doc.get_section('part_i_item_1')
        assert section is not None
        assert section.name == 'part_i_item_1'
        assert section.part == 'I'
        assert section.item == '1'

    def test_lookup_with_part_parameter(self, aapl_10q_doc):
        """Test lookup using item name + part parameter."""
        section = aapl_10q_doc.get_section('item_1', part='I')
        assert section is not None
        assert section.name == 'part_i_item_1'
        assert section.part == 'I'
        assert section.item == '1'

    def test_part_parameter_is_case_insensitive(self, aapl_10q_doc):
        """Test part parameter accepts both uppercase and lowercase."""
        section_upper = aapl_10q_doc.get_section('item_1', part='I')
        section_lower = aapl_10q_doc.get_section('item_1', part='i')

        assert section_upper is not None
        assert section_lower is not None
        assert section_upper.name == section_lower.name

    def test_ambiguous_lookup_raises_helpful_error(self, aapl_10q_doc):
        """Test ambiguous item lookup raises clear error message."""
        with pytest.raises(ValueError) as exc_info:
            aapl_10q_doc.get_section('item_1')

        error_msg = str(exc_info.value)
        assert 'Ambiguous' in error_msg
        assert 'part' in error_msg.lower()
        assert 'I' in error_msg or 'II' in error_msg

    def test_part_i_and_part_ii_return_different_sections(self, aapl_10q_doc):
        """Test that Part I and Part II Item 1 return different sections."""
        part_i_item_1 = aapl_10q_doc.get_section('item_1', part='I')
        part_ii_item_1 = aapl_10q_doc.get_section('item_1', part='II')

        assert part_i_item_1 is not None
        assert part_ii_item_1 is not None
        assert part_i_item_1.name != part_ii_item_1.name
        assert part_i_item_1.part != part_ii_item_1.part


class TestSectionTextExtraction:
    """Test text extraction from part-aware sections."""

    def test_extract_text_from_part_i_item_1(self, aapl_10q_doc):
        """Test extracting text from Part I Item 1."""
        section = aapl_10q_doc.get_section('item_1', part='I')
        assert section is not None

        text = section.text()
        assert text is not None
        assert len(text) > 0, "Section should have text content"

    def test_extract_text_from_part_ii_item_1(self, aapl_10q_doc):
        """Test extracting text from Part II Item 1."""
        section = aapl_10q_doc.get_section('item_1', part='II')
        assert section is not None

        text = section.text()
        assert text is not None
        assert len(text) > 0, "Section should have text content"

    def test_part_i_and_part_ii_have_different_content(self, aapl_10q_doc):
        """Verify Part I Item 1 and Part II Item 1 have different content."""
        part_i_text = aapl_10q_doc.get_section('item_1', part='I').text()
        part_ii_text = aapl_10q_doc.get_section('item_1', part='II').text()

        # They should have different content
        assert part_i_text != part_ii_text, "Part I and Part II Item 1 should have different content"


class TestDetectionMetadata:
    """Test detection metadata (confidence, method) for 10-Q sections."""

    def test_toc_based_detection_has_high_confidence(self, aapl_10q_doc):
        """Verify TOC-based sections have high confidence scores."""
        section = aapl_10q_doc.get_section('part_i_item_1')
        assert section is not None
        assert section.detection_method == 'toc'
        assert section.confidence >= 0.9, f"TOC detection should have high confidence, got {section.confidence}"

    def test_all_sections_have_detection_metadata(self, aapl_10q_doc):
        """Verify all sections have proper detection metadata."""
        for section_name, section in aapl_10q_doc.sections.items():
            assert section.detection_method in ['toc', 'heading', 'pattern'], \
                f"Section {section_name} has invalid detection method: {section.detection_method}"
            assert 0.0 <= section.confidence <= 1.0, \
                f"Section {section_name} has invalid confidence: {section.confidence}"


class TestBackwardCompatibility:
    """Test that 10-K section detection still works (backward compatibility)."""

    def test_10k_section_detection_unchanged(self):
        """Verify 10-K filings still use simple item names without parts."""
        # This would need a 10-K fixture
        # For now, just verify the parse_section_name handles 10-K format
        from edgar.documents.document import Section

        # 10-K format: simple item names
        part, item = Section.parse_section_name('item_1')
        assert part is None, "10-K sections should not have part"
        assert item == '1', "10-K sections should have item number"
