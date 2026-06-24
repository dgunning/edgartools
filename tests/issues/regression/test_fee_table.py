"""
Verification tests for registration fee table extraction from EX-FILING FEES exhibits.

Tests extract_registration_fee_table() against ground-truth values from real S-3 filings,
verified by hand from SEC EDGAR.

See: docs-internal/research/sec-filings/forms/s-3/registration-fee-table-analysis.md
"""
import pytest
from edgar import find, get_by_accession_number
from edgar.offerings._fee_table import (
    extract_registration_fee_table,
    _parse_fee_table_html,
    _join_dollar_cells,
    _parse_dollar_amount,
    _parse_fee_rate,
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

    def test_parse_dollar_amount_leading_decimal_fee_rate(self):
        """A fee-rate cell with no integer part ('$.0000927') must keep its
        leading decimal. The numeric-token regex used to require a leading digit,
        so the '.' was skipped and '0000927' parsed to 927.0 — making the Tier B
        fee/rate cross-check (Anterix 0001193125-22-186192) flag a correct value
        as inconsistent (implied=2 vs extracted=$21.7M)."""
        assert _parse_dollar_amount('$.0000927') == pytest.approx(0.0000927)
        assert _parse_dollar_amount('.00014760') == pytest.approx(0.00014760)

    def test_parse_fee_rate_per_million_basis(self):
        """The SEC EX-107 template writes the fee rate on a per-$1,000,000 basis
        ('$153.10 per $1,000,000'). _parse_dollar_amount reads only the leading
        token (153.10) and drops the basis, leaving the rate 1,000,000x too large
        — which trips the fee/rate cross-check. _parse_fee_rate normalises both
        the per-million form and the raw per-dollar decimal to a fraction."""
        assert _parse_fee_rate('$153.10 per $1,000,000') == pytest.approx(0.0001531)
        assert _parse_fee_rate('$153.10 per $1,000,000.00') == pytest.approx(0.0001531)
        # Raw per-dollar decimals (with or without a leading integer) pass through.
        assert _parse_fee_rate('0.00015310') == pytest.approx(0.0001531)
        assert _parse_fee_rate('$.0000927') == pytest.approx(0.0000927)
        # Placeholders / empty cells stay None.
        assert _parse_fee_rate('—') is None
        assert _parse_fee_rate('') is None

    def test_join_dollar_cells(self):
        assert _join_dollar_cells(['$', '300,000,000']) == ['$300,000,000']
        assert _join_dollar_cells(['$', '12,119.07', '$', '0']) == ['$12,119.07', '$0']
        assert _join_dollar_cells(['hello', '$', '100']) == ['hello', '$100']
        assert _join_dollar_cells(['$300,000']) == ['$300,000']  # already joined
        assert _join_dollar_cells([]) == []

    def test_find_fee_table_split_tag_header(self):
        """edgartools-zxnj: header words split across inline tags / nbsp must match.

        get_text() with no separator collapses '<font>Security</font>
        <font>Type</font>' to 'SecurityType'; _find_fee_table must use a
        separator and normalize whitespace so the data table is still found.
        """
        import warnings
        from bs4 import BeautifulSoup
        from edgar.offerings._fee_table import _find_fee_table
        html = (
            "<html><body>"
            "<table><tr>"
            "<td><font>Security</font><font>Type</font></td>"
            "<td>Maximum Aggregate Offering Price</td>"
            "</tr>"
            "<tr><td>Equity</td><td>$79,170,150.00</td></tr></table>"
            "</body></html>"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            soup = BeautifulSoup(html, "lxml")
        assert _find_fee_table(soup) is not None


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
        # The fee rate is written '$.0000927' (no integer part); it must parse to
        # 0.0000927, not 927.0, so fee / rate reconciles with the offering amount.
        sec = fee_table.securities[0]
        assert sec.fee_rate == pytest.approx(0.0000927)
        assert sec.fee_amount / sec.fee_rate == pytest.approx(21730000.0, rel=0.01)

    @pytest.mark.network
    def test_per_million_fee_rate_basis(self):
        """S-1 (2025) whose fee-rate cells read '$153.10 per $1,000,000'.

        The headline total_offering_amount was always correct, but the per-
        security fee_rate parsed to 153.1 instead of 0.0001531 (the basis was
        dropped), making fee / rate reconcile to ~190 instead of the $189.75M
        offering amount. Ground truth from the filing's own fee exhibit."""
        ft = extract_registration_fee_table(find("0001213900-25-059789"))
        assert ft is not None
        assert ft.total_offering_amount == pytest.approx(189750000.0, rel=0.01)
        priced = [s for s in ft.securities if s.fee_rate and s.fee_amount]
        assert priced, "expected at least one priced security row"
        for s in priced:
            assert s.fee_rate == pytest.approx(0.0001531)
            # fee / rate must reconcile with the row's aggregate (self-check).
            assert s.fee_amount / s.fee_rate == pytest.approx(s.max_aggregate_amount, rel=0.01)

    @pytest.mark.vcr
    def test_filing_without_fee_exhibit(self):
        """A 10-K has no EX-FILING FEES exhibit — returns None."""
        filing = find("0000320193-24-000123")  # Apple 10-K
        fee_table = extract_registration_fee_table(filing)
        assert fee_table is None

    # --- edgartools-zxnj: capacity missing/garbage for most S-3/F-3 shelves ---

    @pytest.mark.vcr
    def test_zxnj_whitehawk_split_tag_header(self):
        """Whitehawk S-3 — header words split across inline tags.

        'Security Type' rendered as <font>Security</font><font>Type</font>;
        _find_fee_table used get_text() with no separator, collapsing it to
        'securitytype' so the data table was never found (returned None).
        """
        fee_table = extract_registration_fee_table(find("0001193125-25-068942"))
        assert fee_table is not None
        assert fee_table.total_offering_amount == pytest.approx(79170150.0, rel=0.01)

    @pytest.mark.vcr
    def test_zxnj_vigil_avoids_footnote_table(self):
        """Vigil S-3 — must parse the data table, not a footnote table.

        With the split-tag header unmatched, the legacy 'registration fee'
        fallback matched a footnote paragraph table ('...calculating the
        registration fee...'), yielding None. Now the data table is found.
        """
        fee_table = extract_registration_fee_table(find("0001193125-25-067858"))
        assert fee_table is not None
        assert fee_table.total_offering_amount == pytest.approx(9704293.70, rel=0.01)

    @pytest.mark.vcr
    def test_zxnj_welltower_indeterminate_asr_is_none_not_zero(self):
        """Welltower S-3ASR — indeterminate amount, deferred fees.

        Every amount cell is a placeholder under Rule 456(b)/457(r). Capacity is
        genuinely indeterminate, so total_offering_amount must be None (not a
        parsed 0.0) and fee_deferred must be True.
        """
        fee_table = extract_registration_fee_table(find("0001193125-25-066253"))
        assert fee_table is not None
        assert fee_table.total_offering_amount is None
        assert fee_table.fee_deferred is True


class TestAmendmentFeeSourceFallback:
    """Capacity recovery for registration amendments that omit the fee exhibit.

    S-3/A, F-3/A and POS AM amendments routinely drop Exhibit 107 when no further
    fee is due — the fee was paid with the original registration. The registered
    capacity still lives in that original's exhibit, so the extractor walks the
    file-number family to recover it instead of returning None.
    """

    @pytest.mark.vcr
    def test_vincerx_s3a_recovers_from_original(self):
        """Vincerx S-3/A (no fee exhibit) recovers $100M from the original S-3."""
        fee_table = extract_registration_fee_table(find("0001193125-25-068723"))
        assert fee_table is not None
        assert fee_table.total_offering_amount == pytest.approx(100000000.0, rel=0.01)

    @pytest.mark.vcr
    def test_tr_finance_f3a_recovers_from_original(self):
        """TR Finance F-3/A (no fee exhibit) recovers $3B from the original F-3."""
        fee_table = extract_registration_fee_table(find("0001193125-25-068799"))
        assert fee_table is not None
        assert fee_table.total_offering_amount == pytest.approx(3000000000.0, rel=0.01)

    @pytest.mark.vcr
    def test_424b_takedown_stays_none(self):
        """Silence check: a 424B takedown is not a registration form, so the
        family is not walked and the result stays an honest None."""
        # get_by_accession_number (year from the accession) is date-stable; find()
        # walks date-derived quarterly indexes whose cassette drifts over time.
        fee_table = extract_registration_fee_table(get_by_accession_number("0001918704-25-005439"))
        assert fee_table is None


class TestXn7eMisparsedTotalOfferingAmount:
    """edgartools-xn7e: EX-107 parser selected the fee (or a column-misaligned
    value) as total_offering_amount, surfacing genuine shelves as null capacity.

    Three distinct failure modes, one symptom — verified against SEC ground truth
    (live, 2026-06-21):
      1. The "Total Offering Amounts" summary cell is a typo ('$761,12' = the fee
         $761.12 with a comma-decimal -> 76112), while the real $6.9M sits in the
         per-security Maximum Aggregate. The re-derivation guard only fired when
         total == net_fee_due, so it never recovered the aggregate.
      2. A '(3)' footnote on the aggregate column split into two cells, shifting
         columns right: the real $150,000,000 landed in fee_amount and 3.0 in
         max_aggregate.
      3. A carry-forward-only F-3 whose summary cell '$1 (1)(2)(3)(4)' had its
         footnote markers fused into the digits -> 11234.
    """

    def test_parse_dollar_amount_ignores_trailing_footnotes(self):
        """Only the first numeric token is read, so appended footnote markers
        can't be concatenated into the value."""
        assert _parse_dollar_amount('$1 (1)(2)(3)(4)') == 1.0
        assert _parse_dollar_amount('$761.12 (3)') == 761.12
        assert _parse_dollar_amount('$150,000,000 (3)') == 150000000.0
        # Existing behaviour is preserved.
        assert _parse_dollar_amount('$12,119.07') == 12119.07
        assert _parse_dollar_amount('300,000,000') == 300000000.0

    def test_refine_recovers_aggregate_from_shifted_columns(self):
        """fee = aggregate x rate is self-validating, so a column shift that put
        the offering amount in the fee column is corrected (333-275559 shape)."""
        from edgar.offerings._fee_table import _refine_fee_columns
        # ['Unallocated...', '—', '457', '(o)', '—', '(3', ')', '$150,000,000',
        #  '0.00014760', '$22,140.00'] — '(3)' split shifted the columns.
        texts = ['Unallocated (Universal) Shelf (1)', '—', '457', '(o)', '—',
                 '(3', ')', '$150,000,000', '0.00014760', '$22,140.00']
        security = {'max_aggregate_amount': 3.0, 'fee_amount': 150000000.0,
                    'fee_rate': None}
        _refine_fee_columns(security, texts)
        assert security['max_aggregate_amount'] == 150000000.0
        assert security['fee_amount'] == 22140.0
        assert security['fee_rate'] == pytest.approx(0.00014760)

    def test_refine_is_noop_without_fee_rate(self):
        """A deferred / placeholder row with no fee rate is left untouched even
        when a par value in the title falls in the rate band."""
        from edgar.offerings._fee_table import _refine_fee_columns
        texts = ['Equity', 'Common Stock, $0.0001 par value per share',
                 '—', '—', '—', '—', '—', '—']
        security = {'max_aggregate_amount': None, 'fee_amount': None,
                    'fee_rate': None}
        _refine_fee_columns(security, texts)
        assert security['max_aggregate_amount'] is None
        assert security['fee_amount'] is None
        assert security['fee_rate'] is None

    @pytest.mark.vcr
    def test_typo_summary_prefers_per_security_aggregate(self):
        """333-273015 (S-1 @2023-06-29): summary cell '$761,12' is a typo for the
        fee; the registered $6,906,664.94 is recovered from securities[0]."""
        ft = extract_registration_fee_table(find("0001104659-23-076317"))
        assert ft is not None
        assert ft.securities[0].max_aggregate_amount == pytest.approx(6906664.94)
        assert ft.total_offering_amount == pytest.approx(6906664.94, rel=0.01)
        assert ft.net_fee_due == pytest.approx(761.12, rel=0.01)

    @pytest.mark.vcr
    def test_column_misalignment_recovers_offering_amount(self):
        """333-275559 (S-3 @2023-11-15): a split '(3)' footnote shifted $150M into
        the fee column; the fee-rate anchor recovers it."""
        ft = extract_registration_fee_table(find("0001493152-23-041369"))
        assert ft is not None
        assert ft.total_offering_amount == pytest.approx(150000000.0, rel=0.01)
        assert ft.net_fee_due == pytest.approx(22140.0, rel=0.01)

    @pytest.mark.vcr
    def test_carry_forward_only_is_none_not_token(self):
        """333-272539 (F-3 @2023-06-08): a carry-forward-only registration with a
        nominal '$1' summary registers an indeterminate amount -> None, not the
        footnote-fused 11234 the old parser produced."""
        ft = extract_registration_fee_table(find("0001104659-23-069410"))
        assert ft is not None
        assert ft.total_offering_amount is None
        assert ft.has_carry_forward is True


class TestInlineFeeTablePreEX107:
    """edgartools-9q82: pre-2022 inline "Calculation of Registration Fee" tables.

    Before the EX-FILING FEES (Exhibit 107) regime (~2022) the fee table lived
    inline in the S-3/S-1 body, with no exhibit to parse. _extract_inline_fee_table
    reads it from the primary document: the registered capacity is the largest
    clean dollar amount in the table (the fee is that x ~0.0001; the per-unit price
    is smaller; share counts are unpriced), and a table with no dollar amount is an
    indeterminate Rule 457(r) shelf.
    """

    # --- fast unit tests on the pure parser (no network) ---

    def test_multi_row_with_total_picks_aggregate_not_fee(self):
        """Aggregate is the largest $; the smaller fee and an embedded par value
        in a prose cell must both be ignored."""
        from edgar.offerings._fee_table import _parse_inline_fee_table
        html = (
            "<table>"
            "<tr><td>Title of each class of securities to be registered</td>"
            "<td>Amount to be registered</td>"
            "<td>Proposed maximum aggregate offering price</td>"
            "<td>Amount of registration fee</td></tr>"
            "<tr><td>Common stock, par value $0.001 per share</td><td></td><td></td><td></td></tr>"
            "<tr><td>Total</td><td>$</td><td>30,000,000</td><td>$</td><td>3,894</td></tr>"
            "</table>"
        )
        data = _parse_inline_fee_table(html, form="S-3")
        assert data["total_offering_amount"] == 30000000.0
        assert data["fee_deferred"] is False

    def test_single_row_no_total_uses_row_aggregate(self):
        """A single-class resale has no Total row; the aggregate is the row's
        largest $ and the unpriced share count is ignored."""
        from edgar.offerings._fee_table import _parse_inline_fee_table
        html = (
            "<table>"
            "<tr><td>Title of Each Class of Securities To Be Registered</td>"
            "<td>Amount to be Registered</td><td>Proposed Maximum Offering Price Per Share</td>"
            "<td>Proposed Maximum Aggregate Offering Price</td><td>Amount of Registration Fee</td></tr>"
            "<tr><td>Common Stock, $0.01 par value per share</td><td>21,212,123</td>"
            "<td>$1.82</td><td>$38,606,063.86</td><td>$4,679.06</td></tr>"
            "</table>"
        )
        data = _parse_inline_fee_table(html, form="S-3")
        assert data["total_offering_amount"] == 38606063.86

    def test_indeterminate_asr_is_deferred(self):
        """An ASR table with only footnote placeholders (no $) is pay-as-you-go."""
        from edgar.offerings._fee_table import _parse_inline_fee_table
        html = (
            "<table>"
            "<tr><td>Title of each class of securities to be registered</td>"
            "<td>Amount to be registered / aggregate price / fee</td></tr>"
            "<tr><td>Debt Securities</td><td>(1)(2)(3)</td></tr>"
            "<tr><td>Common Stock, par value $0.01 per share</td><td></td></tr>"
            "</table>"
        )
        data = _parse_inline_fee_table(html, form="S-3ASR")
        assert data["total_offering_amount"] is None
        assert data["fee_deferred"] is True

    def test_457r_marker_marks_deferred_even_without_asr_form(self):
        from edgar.offerings._fee_table import _parse_inline_fee_table
        html = (
            "<table>"
            "<tr><td>Title of each class of securities to be registered</td>"
            "<td>Aggregate offering price</td></tr>"
            "<tr><td>Debt Securities</td><td>(1)</td></tr>"
            "</table>"
            "<p>Fees calculated pursuant to Rule 457(r) under the Securities Act.</p>"
        )
        data = _parse_inline_fee_table(html, form="S-3")
        assert data["total_offering_amount"] is None
        assert data["fee_deferred"] is True

    def test_no_fee_table_returns_empty(self):
        from edgar.offerings._fee_table import _parse_inline_fee_table
        data = _parse_inline_fee_table("<html><body><p>No table here.</p></body></html>", form="S-3")
        assert data["total_offering_amount"] is None
        assert data["fee_deferred"] is False

    # --- ground-truth assertions on real filings (network; cassettes too large
    # for these 400KB+ primary docs, so run with the network suite) ---

    @pytest.mark.network
    def test_kingold_multi_row_total(self):
        """Kingold Jewelry S-3 (2020): inline table, $30M shelf, fee $3,894."""
        ft = extract_registration_fee_table(find("0001104659-20-040593"))
        assert ft is not None
        assert ft.total_offering_amount == pytest.approx(30000000.0, rel=0.01)

    @pytest.mark.network
    def test_plug_single_row_resale(self):
        """Plug Power S-3 (2018): single-class resale, $38,606,063.86."""
        ft = extract_registration_fee_table(find("0001047469-18-007293"))
        assert ft is not None
        assert ft.total_offering_amount == pytest.approx(38606063.86, rel=0.01)

    @pytest.mark.network
    def test_dynatronics_amendment_body(self):
        """Dynatronics S-3/A (2021): inline table in the amendment body, $50M."""
        ft = extract_registration_fee_table(find("0001654954-21-007440"))
        assert ft is not None
        assert ft.total_offering_amount == pytest.approx(50000000.0, rel=0.01)

    @pytest.mark.network
    def test_schwab_indeterminate_asr_deferred(self):
        """Charles Schwab S-3ASR (2020): indeterminate 457(r) shelf -> deferred."""
        ft = extract_registration_fee_table(find("0001193125-20-310765"))
        assert ft is not None
        assert ft.total_offering_amount is None
        assert ft.fee_deferred is True


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
        # get_by_accession_number (year from the accession) is date-stable; find()
        # walks date-derived quarterly indexes whose cassette drifts over time.
        filing = get_by_accession_number("0001493152-25-029712")  # A 424B5
        prospectus = filing.obj()
        sections = prospectus.sections
        # Should return a dict-like Sections object (may be empty if no patterns match)
        assert sections is not None
        assert isinstance(sections, dict)

    @pytest.mark.vcr
    def test_section_text_extraction(self):
        """Verify individual sections have extractable text."""
        filing = get_by_accession_number("0001493152-25-029712")
        prospectus = filing.obj()
        sections = prospectus.sections
        # If any sections were detected, verify they have text
        for name, section in sections.items():
            text = section.text()
            assert isinstance(text, str)
            assert len(text) > 0, f"Section '{name}' has empty text"
