"""
Tests for R*.htm concept extraction.

Uses AAPL 10-Q fixtures at tests/fixtures/attachments/aapl/20250329/R*.htm.
"""
import pytest
from pathlib import Path

from edgar.sgml.concept_extractor import ConceptRow, ConceptReport, extract_concepts_from_report

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "attachments" / "aapl" / "20250329"


@pytest.fixture(scope="module")
def income_statement() -> ConceptReport:
    """R2.htm — Income Statement."""
    return extract_concepts_from_report((FIXTURE_DIR / "R2.htm").read_text())


@pytest.fixture(scope="module")
def balance_sheet() -> ConceptReport:
    """R4.htm — Balance Sheet."""
    return extract_concepts_from_report((FIXTURE_DIR / "R4.htm").read_text())


@pytest.fixture(scope="module")
def cover_page() -> ConceptReport:
    """R1.htm — Cover Page."""
    return extract_concepts_from_report((FIXTURE_DIR / "R1.htm").read_text())


class TestConceptReportParsing:
    """Test basic report parsing from R*.htm files."""

    def test_income_statement_title(self, income_statement):
        assert 'OPERATIONS' in income_statement.title.upper()

    def test_income_statement_has_rows(self, income_statement):
        assert len(income_statement) > 0

    def test_income_statement_row_count(self, income_statement):
        # R2.htm has 24 data rows (grep count confirmed)
        assert len(income_statement) == 24

    def test_balance_sheet_title(self, balance_sheet):
        assert 'BALANCE SHEET' in balance_sheet.title.upper()

    def test_balance_sheet_has_rows(self, balance_sheet):
        assert len(balance_sheet) > 0

    def test_period_headers_income(self, income_statement):
        # 3 Months Ended + 6 Months Ended = 4 periods
        assert len(income_statement.period_headers) == 4
        assert 'Mar. 29, 2025' in income_statement.period_headers
        assert 'Mar. 30, 2024' in income_statement.period_headers

    def test_period_headers_balance_sheet(self, balance_sheet):
        # Balance sheet has 2 instant dates
        assert len(balance_sheet.period_headers) == 2
        assert 'Mar. 29, 2025' in balance_sheet.period_headers
        assert 'Sep. 28, 2024' in balance_sheet.period_headers


class TestConceptRowExtraction:
    """Test individual concept row fields."""

    def test_first_row_is_net_sales(self, income_statement):
        row = income_statement.rows[0]
        assert row.concept_id == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax'
        assert row.label == 'Net sales'

    def test_net_sales_value(self, income_statement):
        row = income_statement.rows[0]
        # First period should be "$ 95,359"
        values = list(row.values.values())
        assert any('95,359' in v for v in values)

    def test_net_income_row(self, income_statement):
        net_income_rows = income_statement.get_by_concept('us-gaap_NetIncomeLoss')
        assert len(net_income_rows) >= 1
        row = net_income_rows[0]
        assert row.label == 'Net income'
        assert row.is_total is True  # rou class
        values = list(row.values.values())
        assert any('24,780' in v for v in values)

    def test_negative_value(self, income_statement):
        """Other income/(expense) has parenthetical negatives."""
        rows = income_statement.get_by_concept('us-gaap_NonoperatingIncomeExpense')
        assert len(rows) >= 1
        values = list(rows[0].values.values())
        assert any('(279)' in v for v in values)

    def test_eps_basic(self, income_statement):
        rows = income_statement.get_by_concept('us-gaap_EarningsPerShareBasic')
        assert len(rows) >= 1
        values = list(rows[0].values.values())
        assert any('1.65' in v for v in values)


class TestRowClassification:
    """Test abstract, total, and header row detection."""

    def test_abstract_row_detection(self, income_statement):
        """Operating expenses abstract should be detected."""
        rows = income_statement.get_by_concept('us-gaap_OperatingExpensesAbstract')
        assert len(rows) == 1
        assert rows[0].is_abstract is True
        assert rows[0].label == 'Operating expenses:'

    def test_total_row_detection(self, income_statement):
        """Gross margin (reu class) should be a total."""
        rows = income_statement.get_by_concept('us-gaap_GrossProfit')
        assert len(rows) >= 1
        assert rows[0].is_total is True

    def test_regular_row_not_total(self, income_statement):
        """Cost of sales (ro class) should not be a total."""
        rows = income_statement.get_by_concept('us-gaap_CostOfGoodsAndServicesSold')
        assert len(rows) >= 1
        assert rows[0].is_total is False
        assert rows[0].is_abstract is False

    def test_dimensional_header(self, income_statement):
        """Products header (rh class with axis=member) should be detected."""
        header_rows = [r for r in income_statement.rows if r.is_header]
        assert len(header_rows) > 0
        # Should have an axis=member pattern
        assert any('=' in r.concept_id for r in header_rows)

    def test_dimensional_header_is_dimensional(self, income_statement):
        header_rows = [r for r in income_statement.rows if r.is_header]
        for row in header_rows:
            assert row.is_dimensional is True


class TestConceptRowProperties:
    """Test ConceptRow property methods."""

    def test_namespace(self, income_statement):
        row = income_statement.rows[0]
        assert row.namespace == 'us-gaap'

    def test_localname(self, income_statement):
        row = income_statement.rows[0]
        assert row.localname == 'RevenueFromContractWithCustomerExcludingAssessedTax'

    def test_custom_namespace(self, cover_page):
        """Cover page may have dei: namespace tags."""
        dei_rows = [r for r in cover_page.rows if r.namespace == 'dei']
        assert len(dei_rows) > 0

    def test_is_dimensional_false_for_regular(self, income_statement):
        row = income_statement.rows[0]
        assert row.is_dimensional is False


class TestConceptReportMethods:

    def test_concepts_unique_ordered(self, income_statement):
        concepts = income_statement.concepts
        # Should be unique
        assert len(concepts) == len(set(concepts))
        # First should be Revenue
        assert concepts[0] == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax'

    def test_data_rows_excludes_abstracts(self, income_statement):
        all_rows = len(income_statement)
        data_rows = len(income_statement.data_rows)
        abstract_count = sum(1 for r in income_statement.rows if r.is_abstract)
        header_count = sum(1 for r in income_statement.rows if r.is_header)
        assert data_rows == all_rows - abstract_count - header_count

    def test_get_by_concept(self, income_statement):
        rows = income_statement.get_by_concept('us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax')
        # Revenue appears in main section + Products + Services dimensional sections
        assert len(rows) >= 1

    def test_get_by_concept_missing(self, income_statement):
        rows = income_statement.get_by_concept('nonexistent_Concept')
        assert rows == []


class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_empty_html(self):
        report = extract_concepts_from_report('')
        assert len(report) == 0
        assert report.title == ''
        assert report.period_headers == []

    def test_html_without_report_table(self):
        report = extract_concepts_from_report('<html><body><p>No table</p></body></html>')
        assert len(report) == 0

    def test_duplicate_period_headers_disambiguated(self, income_statement):
        """When the same date appears for 3-month and 6-month periods, values dict should have all 4 entries."""
        row = income_statement.rows[0]  # Net sales
        # Should have 4 values (2 unique dates x 2 period spans)
        assert len(row.values) == 4

    def test_all_fixture_reports_parse(self):
        """Every R*.htm in the fixture directory should parse without error."""
        htm_files = sorted(FIXTURE_DIR.glob('R*.htm'))
        assert len(htm_files) > 0
        for htm_file in htm_files:
            report = extract_concepts_from_report(htm_file.read_text())
            assert isinstance(report, ConceptReport), f"Failed to parse {htm_file.name}"


class TestRepr:

    def test_concept_row_repr(self, income_statement):
        row = income_statement.rows[0]
        r = repr(row)
        assert 'ConceptRow' in r
        assert 'Net sales' in r

    def test_concept_report_repr(self, income_statement):
        r = repr(income_statement)
        assert 'ConceptReport' in r
        assert 'rows=' in r
