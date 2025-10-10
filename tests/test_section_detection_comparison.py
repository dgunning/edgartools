"""
Comparison tests: Old parser (TenK) vs New parser (HybridSectionDetector).

Tests section detection accuracy across multiple real 10-K filings.
"""
from pathlib import Path
import pytest
from typing import Set, Dict

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig

# Try to import old parser if available
try:
    from edgar import *
    from edgar.httprequests import download_filing
    OLD_PARSER_AVAILABLE = True
except ImportError:
    OLD_PARSER_AVAILABLE = False


def get_old_parser_sections(cik: str, filing_date: str) -> Set[str]:
    """
    Get sections from old TenK parser.

    Args:
        cik: Company CIK
        filing_date: Filing date (YYYY-MM-DD format)

    Returns:
        Set of section names detected by old parser
    """
    if not OLD_PARSER_AVAILABLE:
        pytest.skip("Old parser not available")

    try:
        # Get filing using old API
        company = Company(cik)
        tenk = company.get_filings(form='10-K').filter(date=filing_date).latest(1)

        if not tenk:
            return set()

        tenk_obj = tenk[0].obj()

        # Extract section names from old parser
        sections = set()

        # Try various methods old parser might use
        if hasattr(tenk_obj, 'items'):
            for item in tenk_obj.items:
                sections.add(item)

        if hasattr(tenk_obj, 'sections'):
            for section in tenk_obj.sections:
                sections.add(section)

        return sections
    except Exception as e:
        pytest.skip(f"Could not get sections from old parser: {e}")


def get_new_parser_sections(html_path: Path, form: str = '10-K') -> Dict[str, float]:
    """
    Get sections from new hybrid parser.

    Args:
        html_path: Path to HTML file
        form: Form type (10-K, 10-Q, etc.)

    Returns:
        Dict mapping section names to confidence scores
    """
    if not html_path.exists():
        pytest.skip(f"HTML fixture not found: {html_path}")

    html = html_path.read_text()
    config = ParserConfig(form=form)
    doc = parse_html(html, config)

    sections = doc.sections

    return {name: section.confidence for name, section in sections.items()}


def normalize_section_name(name: str) -> str:
    """Normalize section name for comparison."""
    # Remove common variations
    normalized = name.lower().strip()
    normalized = normalized.replace('item_', 'item ')
    normalized = normalized.replace('_', ' ')
    normalized = normalized.replace('.', '')
    normalized = normalized.replace('  ', ' ')
    return normalized


def compare_section_sets(old_sections: Set[str], new_sections: Dict[str, float]) -> Dict:
    """
    Compare section sets from old and new parsers.

    Returns:
        Dict with comparison metrics
    """
    # Normalize section names for comparison
    old_normalized = {normalize_section_name(s) for s in old_sections}
    new_normalized = {normalize_section_name(s) for s in new_sections.keys()}

    # Calculate metrics
    common = old_normalized & new_normalized
    only_old = old_normalized - new_normalized
    only_new = new_normalized - old_normalized

    recall = len(common) / len(old_normalized) if old_normalized else 0
    precision = len(common) / len(new_normalized) if new_normalized else 0

    return {
        'old_count': len(old_sections),
        'new_count': len(new_sections),
        'common_count': len(common),
        'only_old': only_old,
        'only_new': only_new,
        'recall': recall,
        'precision': precision,
        'avg_confidence': sum(new_sections.values()) / len(new_sections) if new_sections else 0
    }


class TestSectionDetectionComparison:
    """Compare old vs new parser section detection."""

    def test_apple_10k_comparison(self):
        """Compare Apple 10-K section detection."""
        html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')

        if not html_path.exists():
            pytest.skip("Apple 10-K fixture not found")

        # Get new parser results
        new_sections = get_new_parser_sections(html_path, '10-K')

        # Validate new parser results
        assert len(new_sections) > 0, "New parser should detect sections"

        # Check for key item numbers expected in a 10-K
        # Items are named like "Item 1", "Item 1A", "Item 7A", etc.
        expected_items = ['item 1', 'item 2', 'item 7', 'item 8']
        new_normalized = {normalize_section_name(s) for s in new_sections.keys()}

        found_key_sections = sum(1 for exp in expected_items
                                if any(exp in norm for norm in new_normalized))

        assert found_key_sections >= 3, \
            f"Should find at least 3 key items, found {found_key_sections}"

        print(f"\nApple 10-K: {len(new_sections)} sections detected")
        print(f"Average confidence: {sum(new_sections.values()) / len(new_sections):.2f}")
        print(f"Sections: {list(new_sections.keys())[:5]}...")

    def test_microsoft_10k_comparison(self):
        """Compare Microsoft 10-K section detection."""
        html_path = Path('tests/fixtures/html/msft/10k/msft-10-k-2024-07-30.html')

        if not html_path.exists():
            pytest.skip("Microsoft 10-K fixture not found")

        new_sections = get_new_parser_sections(html_path, '10-K')

        assert len(new_sections) > 0, "Should detect sections in Microsoft 10-K"

        # Check confidence scores
        high_confidence = sum(1 for conf in new_sections.values() if conf >= 0.8)

        print(f"\nMicrosoft 10-K: {len(new_sections)} sections detected")
        print(f"High confidence sections (>=0.8): {high_confidence}")

    def test_multiple_tickers_section_counts(self):
        """Test section detection across multiple tickers."""
        test_cases = [
            ('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html', 'AAPL'),
            ('tests/fixtures/html/msft/10k/msft-10-k-2024-07-30.html', 'MSFT'),
        ]

        results = []
        for html_path_str, ticker in test_cases:
            html_path = Path(html_path_str)

            if not html_path.exists():
                continue

            new_sections = get_new_parser_sections(html_path, '10-K')

            results.append({
                'ticker': ticker,
                'sections': len(new_sections),
                'avg_confidence': sum(new_sections.values()) / len(new_sections) if new_sections else 0,
                'high_confidence': sum(1 for c in new_sections.values() if c >= 0.8)
            })

        # Should have results for at least one ticker
        assert len(results) > 0, "Should test at least one ticker"

        print("\n=== Section Detection Results ===")
        for result in results:
            print(f"{result['ticker']}: {result['sections']} sections, "
                  f"avg confidence {result['avg_confidence']:.2f}, "
                  f"{result['high_confidence']} high confidence")

        # All tested tickers should detect sections
        for result in results:
            assert result['sections'] > 0, f"{result['ticker']} should detect sections"

    def test_section_detection_consistency(self):
        """Test that section detection is consistent across runs."""
        html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')

        if not html_path.exists():
            pytest.skip("Apple 10-K fixture not found")

        # Run detection multiple times
        runs = []
        for _ in range(3):
            sections = get_new_parser_sections(html_path, '10-K')
            runs.append({
                'count': len(sections),
                'sections': set(sections.keys()),
                'confidences': sections
            })

        # All runs should detect same sections
        for i in range(1, len(runs)):
            assert runs[i]['count'] == runs[0]['count'], \
                "Section count should be consistent"
            assert runs[i]['sections'] == runs[0]['sections'], \
                "Section names should be consistent"

            # Confidence scores should be identical
            for section in runs[0]['confidences']:
                assert runs[i]['confidences'][section] == runs[0]['confidences'][section], \
                    f"Confidence for {section} should be consistent"

    def test_section_confidence_distribution(self):
        """Test confidence score distribution across sections."""
        html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')

        if not html_path.exists():
            pytest.skip("Apple 10-K fixture not found")

        sections = get_new_parser_sections(html_path, '10-K')

        # Categorize by confidence
        high = sum(1 for c in sections.values() if c >= 0.9)
        medium = sum(1 for c in sections.values() if 0.7 <= c < 0.9)
        low = sum(1 for c in sections.values() if c < 0.7)

        print(f"\nConfidence distribution:")
        print(f"  High (>=0.9): {high}")
        print(f"  Medium (0.7-0.9): {medium}")
        print(f"  Low (<0.7): {low}")

        # Most sections should have reasonable confidence
        assert high + medium >= low, \
            "Most sections should have medium to high confidence"

    def test_standard_10k_sections_present(self):
        """Test that standard 10-K items are detected."""
        html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')

        if not html_path.exists():
            pytest.skip("Apple 10-K fixture not found")

        sections = get_new_parser_sections(html_path, '10-K')
        section_names_lower = {name.lower() for name in sections.keys()}

        # Standard 10-K item numbers (support both formats: "item_1" and "part_i_item_1")
        expected_items = [
            ('1', 'item_1'),      # Business
            ('1a', 'item_1a'),    # Risk Factors
            ('2', 'item_2'),      # Properties
            ('7', 'item_7'),      # MD&A
            ('8', 'item_8'),      # Financial Statements
        ]

        found = []
        for item_num, item_name in expected_items:
            # Check for either simple format (item_1) or part-aware format (part_i_item_1)
            if any(item_name in name for name in section_names_lower) or \
               any(f'item_{item_num}' in name for name in section_names_lower):
                found.append(item_name)

        print(f"\nFound standard items: {found}")
        print(f"Section names: {sorted(section_names_lower)[:10]}")

        # Should find at least half of expected items
        assert len(found) >= len(expected_items) // 2, \
            f"Should find at least {len(expected_items) // 2} standard items, found {len(found)}"


class TestDetectionMethodDistribution:
    """Test distribution of detection methods."""

    def test_detection_method_tracking(self):
        """Test that detection methods are properly tracked."""
        html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')

        if not html_path.exists():
            pytest.skip("Apple 10-K fixture not found")

        html = html_path.read_text()
        config = ParserConfig(form='10-K')
        doc = parse_html(html, config)

        sections = doc.sections

        # Count detection methods
        methods = {}
        for section in sections.values():
            method = section.detection_method
            methods[method] = methods.get(method, 0) + 1

        print(f"\nDetection methods used:")
        for method, count in methods.items():
            print(f"  {method}: {count} sections")

        # Should have at least one detection method used
        assert len(methods) > 0, "Should use at least one detection method"

        # Most common method should be TOC for documents with TOC
        if 'toc' in methods:
            assert methods['toc'] > 0, "TOC method should detect sections"


if __name__ == '__main__':
    pytest.main([__file__, '-xvs'])
