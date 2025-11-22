"""
Regression test for edgartools-2bb: TextExtractor introduces extra spaces in item numbers

Issue: TextExtractor was adding extra spaces in multi-part item numbers like "Item 2.02"
becoming "Item 2. 02" due to overly aggressive punctuation normalization.

Root cause: The _normalize_punctuation() method was adding space after ANY period,
including those in item numbers and decimals.

Fix: Changed regex to only add space after punctuation when followed by a letter,
preserving decimals and multi-part item numbers.
"""

import pytest
from edgar import Filing
from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.text_extractor import TextExtractor


@pytest.mark.network
def test_text_extractor_preserves_item_numbers():
    """TextExtractor should preserve multi-part item numbers without adding extra spaces."""
    filing = Filing(
        form='8-K',
        filing_date='2023-03-15',
        company='ADOBE INC.',
        cik=796343,
        accession_no='0000796343-23-000044'
    )
    html = filing.html()

    config = ParserConfig(form='8-K')
    parser = HTMLParser(config)
    doc = parser.parse(html)

    section = doc.sections['item_202']
    extractor = TextExtractor()

    # Get text from both methods
    node_text = section.node.text()
    extracted_text = extractor.extract_from_node(section.node)

    # Both should have "Item 2.02." not "Item 2. 02."
    assert 'Item 2.02.' in node_text, "node.text() should have 'Item 2.02.'"
    assert 'Item 2.02.' in extracted_text, "TextExtractor should preserve 'Item 2.02.'"
    assert 'Item 2. 02.' not in extracted_text, "Should not have extra space: 'Item 2. 02.'"


def test_normalize_punctuation_preserves_decimals():
    """The _normalize_punctuation method should preserve decimals and item numbers."""
    extractor = TextExtractor()

    test_cases = [
        # (input, expected_output, description)
        ('Item 2.02. Results', 'Item 2.02. Results', 'Multi-part item number'),
        ('Item 1.01.Entry', 'Item 1.01. Entry', 'Item number before word'),
        ('Revenue was $100.5 million.Great!', 'Revenue was $100.5 million. Great!', 'Decimal in currency'),
        ('The rate is 3.14%.Perfect', 'The rate is 3.14%. Perfect', 'Decimal in percentage'),
        ('Item 7.Management Discussion', 'Item 7. Management Discussion', 'Single-digit item'),
        ('Q1 results.Q2 results.Q3 results.', 'Q1 results. Q2 results. Q3 results.', 'Sentence separation'),
    ]

    for input_text, expected, description in test_cases:
        result = extractor._normalize_punctuation(input_text)
        assert result == expected, f"{description}: expected {expected!r}, got {result!r}"


def test_normalize_punctuation_adds_sentence_spacing():
    """Should add space after punctuation when starting a new sentence."""
    extractor = TextExtractor()

    # Should add space between sentences
    assert extractor._normalize_punctuation('First sentence.Second sentence.') == 'First sentence. Second sentence.'
    assert extractor._normalize_punctuation('Question?Answer here.') == 'Question? Answer here.'
    assert extractor._normalize_punctuation('Exclamation!Next one.') == 'Exclamation! Next one.'

    # Should NOT add space when punctuation is followed by digit or end of string
    assert extractor._normalize_punctuation('Item 1.23.') == 'Item 1.23.'
    assert extractor._normalize_punctuation('Value is 99.9') == 'Value is 99.9'


@pytest.mark.network
def test_text_extractor_consistency_across_forms():
    """TextExtractor should handle item numbers consistently across different forms."""
    test_cases = [
        ('8-K', '2023-03-15', 'ADOBE INC.', 796343, '0000796343-23-000044', 'Item 2.02.'),
        ('10-K', '2023-03-24', 'APPLE INC', 320193, '0000320193-23-000077', 'Item 1.'),
    ]

    for form, date, company, cik, accession, expected_item in test_cases:
        filing = Filing(form=form, filing_date=date, company=company,
                       cik=cik, accession_no=accession)
        html = filing.html()

        config = ParserConfig(form=form)
        parser = HTMLParser(config)
        doc = parser.parse(html)

        extractor = TextExtractor()
        extracted = extractor.extract(doc)

        # Should find the expected item number without extra spaces
        assert expected_item in extracted[:5000], \
            f"{form} should contain properly formatted '{expected_item}'"

        # Should not have spacing issues like "Item 1. 01."
        import re
        bad_pattern = re.search(r'Item\s+\d+\.\s+\d+\.', extracted[:5000])
        assert bad_pattern is None, \
            f"{form} should not have bad spacing in item numbers: {bad_pattern.group(0) if bad_pattern else 'N/A'}"
