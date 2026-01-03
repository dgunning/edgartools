"""
Regression test for Issue #03zg: Hide XBRL structural elements from to_dataframe() output.

XBRL filings contain structural elements like:
- [Axis] - Dimensional axes
- [Domain] - Domain members
- [Table] - Hypercube tables
- [Line Items] - Container elements
- [Abstract] - Abstract containers

These are XBRL metadata, not financial data. Users should see clean financial
statements without these internal constructs cluttering the output.
"""

import pytest

from edgar.xbrl.statements import (
    is_xbrl_structural_element,
    STRUCTURAL_LABEL_PATTERNS,
    STRUCTURAL_CONCEPT_SUFFIXES,
)


class TestStructuralElementDetection:
    """Test the is_xbrl_structural_element helper function."""

    def test_axis_in_label_detected(self):
        """Items with [Axis] in label should be detected as structural."""
        item = {'label': 'Product and Service [Axis]', 'concept': 'srt_ProductOrServiceAxis'}
        assert is_xbrl_structural_element(item) is True

    def test_domain_in_label_detected(self):
        """Items with [Domain] in label should be detected as structural."""
        item = {'label': 'Product and Service [Domain]', 'concept': 'srt_ProductsAndServicesDomain'}
        assert is_xbrl_structural_element(item) is True

    def test_table_in_label_detected(self):
        """Items with [Table] in label should be detected as structural."""
        item = {'label': 'Statement [Table]', 'concept': 'us-gaap_StatementTable'}
        assert is_xbrl_structural_element(item) is True

    def test_line_items_in_label_detected(self):
        """Items with [Line Items] in label should be detected as structural."""
        item = {'label': 'Statement [Line Items]', 'concept': 'us-gaap_StatementLineItems'}
        assert is_xbrl_structural_element(item) is True

    def test_abstract_in_label_detected(self):
        """Items with [Abstract] in label should be detected as structural."""
        item = {'label': 'Income Statement [Abstract]', 'concept': 'us-gaap_IncomeStatementAbstract'}
        assert is_xbrl_structural_element(item) is True

    def test_concept_suffix_axis_detected(self):
        """Concepts ending with 'Axis' should be detected as structural."""
        item = {'label': 'Product or Service', 'concept': 'srt_ProductOrServiceAxis'}
        assert is_xbrl_structural_element(item) is True

    def test_concept_suffix_domain_detected(self):
        """Concepts ending with 'Domain' should be detected as structural."""
        item = {'label': 'Products and Services', 'concept': 'srt_ProductsAndServicesDomain'}
        assert is_xbrl_structural_element(item) is True

    def test_concept_suffix_table_detected(self):
        """Concepts ending with 'Table' should be detected as structural."""
        item = {'label': 'Statement', 'concept': 'us-gaap_StatementTable'}
        assert is_xbrl_structural_element(item) is True

    def test_regular_items_not_detected(self):
        """Regular financial items should NOT be detected as structural."""
        # Revenue item
        item = {'label': 'Total revenues', 'concept': 'us-gaap_Revenues'}
        assert is_xbrl_structural_element(item) is False

        # Section header (abstract but not structural)
        item = {'label': 'Revenues:', 'concept': 'us-gaap_RevenuesAbstract'}
        assert is_xbrl_structural_element(item) is False

        # Balance sheet item
        item = {'label': 'Cash and cash equivalents', 'concept': 'us-gaap_CashAndCashEquivalentsAtCarryingValue'}
        assert is_xbrl_structural_element(item) is False

    def test_empty_item_not_detected(self):
        """Empty items should NOT be detected as structural."""
        item = {}
        assert is_xbrl_structural_element(item) is False

        item = {'label': '', 'concept': ''}
        assert is_xbrl_structural_element(item) is False


class TestPatternLists:
    """Test that pattern lists contain expected values."""

    def test_label_patterns_complete(self):
        """Label patterns should include all XBRL structural brackets."""
        assert '[Axis]' in STRUCTURAL_LABEL_PATTERNS
        assert '[Domain]' in STRUCTURAL_LABEL_PATTERNS
        assert '[Table]' in STRUCTURAL_LABEL_PATTERNS
        assert '[Line Items]' in STRUCTURAL_LABEL_PATTERNS
        assert '[Member]' in STRUCTURAL_LABEL_PATTERNS
        assert '[Abstract]' in STRUCTURAL_LABEL_PATTERNS

    def test_concept_suffixes_complete(self):
        """Concept suffixes should include all XBRL structural endings."""
        assert 'Axis' in STRUCTURAL_CONCEPT_SUFFIXES
        assert 'Domain' in STRUCTURAL_CONCEPT_SUFFIXES
        assert 'Table' in STRUCTURAL_CONCEPT_SUFFIXES
        assert 'LineItems' in STRUCTURAL_CONCEPT_SUFFIXES
        assert 'Member' in STRUCTURAL_CONCEPT_SUFFIXES


@pytest.mark.network
class TestStructuralFilteringWithRealData:
    """Test structural filtering with real SEC filings."""

    def test_wday_income_statement_no_structural_elements(self):
        """WDAY income statement should not contain structural elements."""
        from edgar import Company

        company = Company("WDAY")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=False)

        # Check that no structural patterns appear in labels
        for pattern in ['[Axis]', '[Domain]', '[Table]', '[Line Items]']:
            matching = df[df['label'].str.contains(pattern, regex=False, na=False)]
            assert len(matching) == 0, f"Found structural element with {pattern}: {matching['label'].tolist()}"

        # Check that we still have meaningful data
        assert len(df) > 10, "Should have meaningful financial data rows"
        assert 'Revenues:' in df['label'].values or any('Revenue' in str(l) for l in df['label'].values), \
            "Should contain revenue data"

    def test_visa_balance_sheet_no_structural_elements(self):
        """Visa balance sheet should not contain structural elements."""
        from edgar import Company

        company = Company("V")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        bs = xbrl.statements.balance_sheet()
        df = bs.to_dataframe(include_dimensions=False)

        # Check that no structural patterns appear in labels
        for pattern in ['[Axis]', '[Domain]', '[Table]', '[Line Items]', '[Abstract]']:
            matching = df[df['label'].str.contains(pattern, regex=False, na=False)]
            assert len(matching) == 0, f"Found structural element with {pattern}: {matching['label'].tolist()}"

        # Check that we still have meaningful section headers
        assert 'Assets' in df['label'].values, "Should contain Assets section"
        assert 'Liabilities' in df['label'].values, "Should contain Liabilities section"

    def test_structural_filtering_preserves_section_headers(self):
        """Filtering should preserve legitimate section headers like 'Revenues:'."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=False)

        # Should still have abstract rows for section headers
        abstract_rows = df[df['abstract'] == True]
        assert len(abstract_rows) > 0, "Should preserve section header abstract rows"

        # But should not have XBRL structural elements
        for pattern in ['[Table]', '[Axis]', '[Domain]', '[Line Items]']:
            assert not any(pattern in str(label) for label in df['label'].values), \
                f"Should not contain {pattern} structural elements"

    def test_dataframe_row_count_reduced(self):
        """Filtering should reduce row count compared to raw data."""
        from edgar import Company

        company = Company("WDAY")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        income = xbrl.statements.income_statement()

        # Get dataframe (with filtering)
        df = income.to_dataframe(include_dimensions=False)

        # Get raw data (without filtering)
        raw_data = income.get_raw_data()

        # Count structural elements in raw data
        structural_count = sum(
            1 for item in raw_data
            if is_xbrl_structural_element(item)
        )

        # Dataframe should have fewer rows due to filtering
        assert structural_count > 0, "Raw data should contain structural elements"
        assert len(df) < len(raw_data), "Filtered dataframe should have fewer rows than raw data"
