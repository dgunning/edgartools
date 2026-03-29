"""
Verification tests for registration fee table extraction from EX-FILING FEES exhibits.

Tests extract_registration_fee_table() against ground-truth values from real S-3 filings,
verified by hand from SEC EDGAR.

See: docs-internal/research/sec-filings/forms/s-3/registration-fee-table-analysis.md
"""
import pytest
from edgar import find
from edgar.offerings._fee_table import (
    extract_registration_fee_table,
    _parse_fee_table_html,
    _join_dollar_cells,
    _parse_dollar_amount,
)
from edgar.offerings.prospectus import RegistrationFeeTable, FeeTableSecurity


# ============================================================
# Unit tests for parsing helpers
# ============================================================

class TestParsingHelpers:

    def test_parse_dollar_amount(self):
        assert _parse_dollar_amount('$12,119.07') == 12119.07
        assert _parse_dollar_amount('300,000,000') == 300000000.0
        assert _parse_dollar_amount('$0.00') == 0.0
        assert _parse_dollar_amount('') is None
        assert _parse_dollar_amount(None) is None

    def test_join_dollar_cells(self):
        assert _join_dollar_cells(['$', '300,000,000']) == ['$300,000,000']
        assert _join_dollar_cells(['$', '12,119.07', '$', '0']) == ['$12,119.07', '$0']
        assert _join_dollar_cells(['hello', '$', '100']) == ['hello', '$100']
        assert _join_dollar_cells(['$300,000']) == ['$300,000']  # already joined
        assert _join_dollar_cells([]) == []


# ============================================================
# Integration tests against real S-3 filings
# ============================================================

class TestFeeTableExtraction:
    """Test fee table extraction against ground-truth values from real filings."""

    @pytest.mark.vcr
    def test_adc_therapeutics_simple_equity(self):
        """ADC Therapeutics S-3 — simple single equity security."""
        filing = find("0000950103-25-008153")
        fee_table = extract_registration_fee_table(filing)

        assert fee_table is not None
        assert isinstance(fee_table, RegistrationFeeTable)
        # Ground truth: Total Offering = $79,157,878.46, Net Fee = $12,119.07
        assert fee_table.total_offering_amount == pytest.approx(79157878.46, rel=0.01)
        assert fee_table.net_fee_due == pytest.approx(12119.07, rel=0.01)
        assert fee_table.fee_deferred is False
        assert fee_table.has_carry_forward is False
        assert len(fee_table.securities) >= 1

    @pytest.mark.vcr
    def test_central_pacific_universal_shelf(self):
        """Central Pacific Financial S-3 — universal shelf with multiple security types."""
        filing = find("0001140361-25-024210")
        fee_table = extract_registration_fee_table(filing)

        assert fee_table is not None
        # Ground truth: Total Offering = $300,000,000
        assert fee_table.total_offering_amount == pytest.approx(300000000.0, rel=0.01)
        assert fee_table.net_fee_due == pytest.approx(45930.0, rel=0.01)
        # Universal shelf has multiple security lines
        assert len(fee_table.securities) >= 1

    @pytest.mark.vcr
    def test_gcm_grosvenor_carry_forward(self):
        """GCM Grosvenor S-3 — carry-forward from prior registration."""
        filing = find("0001213900-25-058997")
        fee_table = extract_registration_fee_table(filing)

        assert fee_table is not None
        # Ground truth: Total Offering = $350,000,000, has carry-forward
        assert fee_table.total_offering_amount == pytest.approx(350000000.0, rel=0.01)
        assert fee_table.net_fee_due == pytest.approx(7655.0, rel=0.01)
        assert fee_table.has_carry_forward is True

    @pytest.mark.vcr
    def test_aerovironment_s3asr_deferred(self):
        """AeroVironment S-3ASR — deferred fee under Rule 457(r)."""
        filing = find("0001104659-25-064107")
        fee_table = extract_registration_fee_table(filing)

        assert fee_table is not None
        # Ground truth: Net Fee = $0 (deferred), fee_deferred = True
        assert fee_table.fee_deferred is True
        assert fee_table.net_fee_due == pytest.approx(0.0, abs=0.01)

    @pytest.mark.vcr
    def test_anterix_2022_pre_xbrl(self):
        """Anterix S-3 (2022) — pre-inline-XBRL, simpler column format."""
        filing = find("0001193125-22-186192")
        fee_table = extract_registration_fee_table(filing)

        assert fee_table is not None
        # Ground truth: Total Offering ≈ $21,730,000
        assert fee_table.total_offering_amount == pytest.approx(21730000.0, rel=0.01)
        assert fee_table.net_fee_due == pytest.approx(2014.37, rel=0.01)

    @pytest.mark.vcr
    def test_filing_without_fee_exhibit(self):
        """A 10-K has no EX-FILING FEES exhibit — returns None."""
        filing = find("0000320193-24-000123")  # Apple 10-K
        fee_table = extract_registration_fee_table(filing)
        assert fee_table is None


class TestRegistrationFeeTableModel:
    """Test the RegistrationFeeTable data model."""

    def test_empty_model(self):
        ft = RegistrationFeeTable()
        assert ft.total_offering_amount is None
        assert ft.net_fee_due is None
        assert ft.securities == []
        assert ft.carry_forwards == []
        assert ft.has_carry_forward is False
        assert ft.fee_deferred is False

    def test_fee_table_security_model(self):
        s = FeeTableSecurity(
            security_type="Equity",
            security_title="Common Stock",
            fee_rule="457(c)",
            max_aggregate_amount=79157878.46,
        )
        assert s.security_type == "Equity"
        assert s.max_aggregate_amount == 79157878.46


# ============================================================
# Prospectus424B.sections integration
# ============================================================

class TestProspectusSections:
    """Test section-level text access on Prospectus424B."""

    @pytest.mark.vcr
    def test_sections_returns_sections_object(self):
        """Verify that prospectus.sections returns a Sections dict."""
        filing = find("0001493152-25-029712")  # A 424B5
        prospectus = filing.obj()
        sections = prospectus.sections
        # Should return a dict-like Sections object (may be empty if no patterns match)
        assert sections is not None
        assert isinstance(sections, dict)

    @pytest.mark.vcr
    def test_section_text_extraction(self):
        """Verify individual sections have extractable text."""
        filing = find("0001493152-25-029712")
        prospectus = filing.obj()
        sections = prospectus.sections
        # If any sections were detected, verify they have text
        for name, section in sections.items():
            text = section.text()
            assert isinstance(text, str)
            assert len(text) > 0, f"Section '{name}' has empty text"
