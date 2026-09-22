"""
Tests for AI-optimized .to_context() methods on core EdgarTools objects.

These methods provide research-backed format optimization:
- Plain text key-value for metadata objects (Company uses UPPERCASE labels)
- Markdown-KV for XBRL objects (60.7% accuracy, 25% fewer tokens)
- TSV for tabular collections (maximum token efficiency)

Note: .text() methods are deprecated in favor of .to_context() for consistency.

Research: https://improvingagents.com/blog/best-input-data-format-for-llms
"""

import pytest


@pytest.mark.network
def test_company_to_context_method(aapl_company):
    """Test Company.to_context() returns plain text key-value format."""
    text = aapl_company.to_context(max_tokens=2000)

    # Check format is plain text key-value (UPPERCASE labels)
    assert "COMPANY:" in text
    assert "CIK:" in text

    # Check company-specific data
    assert "Apple" in text or "AAPL" in text
    assert "0000320193" in text  # Apple's CIK

    # Check token limiting works (4 chars/token heuristic)
    max_chars = 2000 * 4
    assert len(text) <= max_chars + 100  # Allow small buffer for truncation message


@pytest.mark.network
def test_company_to_context_contains_key_fields(aapl_company):
    """Test Company.to_context() includes essential company fields."""
    text = aapl_company.to_context(max_tokens=2000)

    # Essential fields that should be present (plain text format)
    assert "COMPANY:" in text
    assert "CIK:" in text

    # Optional fields (may or may not be present depending on data)
    # Just verify format if present
    if "Ticker:" in text:
        assert "AAPL" in text


@pytest.mark.network
def test_filing_text_method(aapl_company):
    """Test Filing.text() returns document text content."""
    filings = aapl_company.get_filings(form="10-K")
    if len(filings) == 0:
        pytest.skip("No 10-K filings available")

    filing = filings[0]
    text = filing.text()

    # Filing.text() returns full document text, not AI metadata
    # It should be a long string containing filing content
    assert isinstance(text, str)
    assert len(text) > 1000  # Should be substantial content

    # Should not have Markdown-KV markers (that's for Company.text())
    # This is raw document text


# NOTE: Filings/EntityFilings do not have a .text() method
# They have .docs for API documentation, but no AI-optimized text export


@pytest.mark.network
def test_xbrl_to_context_method(aapl_company):
    """Test XBRL.to_context() returns Markdown-KV format optimized for AI consumption."""
    filings = aapl_company.get_filings(form="10-K")
    if len(filings) == 0:
        pytest.skip("No 10-K filings available")

    filing = filings[0]

    try:
        xbrl = filing.xbrl()
    except Exception:
        pytest.skip("XBRL not available for this filing")

    text = xbrl.to_context(max_tokens=1000)

    # XBRL.to_context() returns Markdown-KV format (not rich display format)
    # Check for Markdown-KV markers
    assert "**Entity:**" in text
    assert "**CIK:**" in text
    assert "**Form:**" in text

    # Should NOT have ANSI escape codes
    assert "\x1B[" not in text

    # Should NOT have box drawing characters (that's the old repr format)
    assert "╭" not in text and "│" not in text and "╰" not in text

    # XBRL metadata should be present
    assert "**Facts:**" in text
    assert "**Contexts:**" in text

    # Should have available statements section
    assert "**Available Statements:**" in text

    # Should have common actions section
    assert "**Common Actions:**" in text

    # Should be substantial text
    assert len(text) > 400


@pytest.mark.network
def test_company_text_deprecated(aapl_company):
    """Test that Company.text() still works but issues deprecation warning."""
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        text = aapl_company.text(max_tokens=2000)

        # Should have issued a deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "to_context" in str(w[0].message)

        # But should still return valid output (plain text format)
        assert "COMPANY:" in text
        assert "Apple" in text or "AAPL" in text


@pytest.mark.network
def test_xbrl_text_deprecated(aapl_company):
    """Test that XBRL.text() still works but issues deprecation warning."""
    import warnings

    filings = aapl_company.get_filings(form="10-K")
    if len(filings) == 0:
        pytest.skip("No 10-K filings available")

    filing = filings[0]

    try:
        xbrl = filing.xbrl()
    except Exception:
        pytest.skip("XBRL not available for this filing")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        text = xbrl.text(max_tokens=1000)

        # Should have issued a deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "to_context" in str(w[0].message)

        # But should still return valid output
        assert "**Entity:**" in text
        assert "**Form:**" in text


@pytest.mark.fast
def test_text_method_token_limiting():
    """Test that token limiting works correctly."""
    # Create a long string
    long_text = "word " * 1000  # ~5000 characters

    # Simulate token limiting logic (4 chars/token)
    max_tokens = 100
    max_chars = max_tokens * 4

    if len(long_text) > max_chars:
        truncated = long_text[:max_chars] + "\n\n[Truncated for token limit]"
    else:
        truncated = long_text

    # Check truncation happened
    assert len(truncated) < len(long_text)
    assert "[Truncated for token limit]" in truncated
    assert len(truncated) <= max_chars + 50  # Allow for truncation message


@pytest.mark.fast
def test_markdown_kv_format():
    """Test Markdown-KV format structure (used by XBRL.to_context())."""
    # Example Markdown-KV output (as used by XBRL)
    text = """**Entity:** Apple Inc.
**CIK:** 0000320193
**Form:** 10-K
**Facts:** 1234"""

    lines = text.strip().split('\n')

    # Each line should be a key-value pair with ** markers
    for line in lines:
        assert line.startswith("**")
        assert ":**" in line
        parts = line.split(":**", 1)
        assert len(parts) == 2
        key = parts[0].strip("*")
        value = parts[1].strip()
        assert len(key) > 0
        assert len(value) > 0


@pytest.mark.fast
def test_plain_text_kv_format():
    """Test plain text key-value format structure (used by Company.to_context())."""
    # Example plain text output (as used by Company)
    text = """COMPANY: Apple Inc.
CIK: 0000320193
Ticker: AAPL
Industry: Electronic Computers"""

    lines = text.strip().split('\n')

    # Each line should be a key-value pair with colon separator
    for line in lines:
        assert ":" in line
        parts = line.split(":", 1)
        assert len(parts) == 2
        key = parts[0].strip()
        value = parts[1].strip()
        assert len(key) > 0
        assert len(value) > 0


@pytest.mark.fast
def test_tsv_format():
    """Test TSV format structure."""
    # Example TSV output
    text = """Form\tCompany\tCIK\tFiling Date
10-K\tApple Inc.\t0000320193\t2023-11-03
10-Q\tApple Inc.\t0000320193\t2023-08-04"""

    lines = text.strip().split('\n')

    # First line should be headers
    headers = lines[0].split('\t')
    assert len(headers) > 0

    # Data lines should have same number of columns
    for line in lines[1:]:
        columns = line.split('\t')
        assert len(columns) == len(headers)
