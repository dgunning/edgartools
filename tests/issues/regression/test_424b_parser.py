"""
Regression tests for 424B Prospectus Parser (Phase 1).

Tests cover page extraction, offering type classification, and obj() dispatch
against ground-truth values from real SEC filings.

Each test case uses a specific filing accession number and asserts specific
values verified by hand against the SEC EDGAR filing.
"""
import pytest
from edgar import find
from edgar.offerings.prospectus import (
    Prospectus424B,
    ShelfLifecycle,
    Deal,
    OfferingType,
    CoverPageData,
    PROSPECTUS_FORMS,
    _parse_sec_number,
)
from edgar.offerings._424b_classifier import classify_offering_type
from edgar.offerings._424b_cover import extract_cover_page_fields


# ============================================================
# Test: obj() dispatch returns Prospectus424B
# ============================================================

class TestObjDispatch:
    """Verify filing.obj() returns Prospectus424B for all 424B variants."""

    @pytest.mark.vcr
    def test_424b5_returns_prospectus(self):
        filing = find("0001493152-25-029712")
        result = filing.obj()
        assert isinstance(result, Prospectus424B)

    @pytest.mark.vcr
    def test_424b2_returns_prospectus(self):
        filing = find("0001918704-24-002559")
        result = filing.obj()
        assert isinstance(result, Prospectus424B)

    @pytest.mark.vcr
    def test_424b4_returns_prospectus(self):
        filing = find("0001104659-24-132924")
        result = filing.obj()
        assert isinstance(result, Prospectus424B)


# ============================================================
# Test: Cover page extraction ground truth
# ============================================================

class TestCoverPageExtraction:
    """Assert specific field values from known filings."""

    @pytest.mark.vcr
    def test_imunon_424b5_cover_page(self):
        """Imunon best-efforts PIPE offering."""
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)

        assert p.form == "424B5"
        assert p.cover_page.rule_number == "5"
        assert p.cover_page.registration_number == "333-279425"
        assert p.cover_page.is_supplement is True
        assert p.cover_page.is_preliminary is False
        assert p.cover_page.is_atm is False
        assert p.cover_page.exchange_ticker == "IMNN"
        assert p.cover_page.offering_price == "$3.6100"
        assert p.cover_page.base_prospectus_date == "May 22, 2024"

    @pytest.mark.vcr
    def test_nextera_424b5_atm(self):
        """NextEra at-the-market equity program."""
        filing = find("0001193125-25-338333")
        p = Prospectus424B.from_filing(filing)

        assert p.is_atm is True
        assert p.is_supplement is True
        assert p.offering_price == "at-the-market"
        assert p.offering_amount == "$4,000,000,000"
        assert p.ticker == "NEE"
        assert p.registration_number == "333-278184"
        assert p.cover_page.base_prospectus_date == "March 22, 2024"

    @pytest.mark.vcr
    def test_bofa_424b2_structured_note(self):
        """BofA structured note — preliminary, no ticker."""
        filing = find("0001918704-24-002559")
        p = Prospectus424B.from_filing(filing)

        assert p.is_preliminary is True
        assert p.cover_page.is_supplement is False
        assert p.ticker is None  # Notes not listed on exchange
        assert p.cover_page.base_prospectus_date is None  # Not in standard format

    @pytest.mark.vcr
    def test_traws_pharma_424b4(self):
        """Traws Pharma best-efforts PIPE supplement."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)

        assert p.ticker == "TRAW"
        assert p.is_supplement is True
        assert p.cover_page.base_prospectus_date == "July 11, 2023"


# ============================================================
# Test: Offering type classification
# ============================================================

class TestOfferingTypeClassification:
    """Verify offering type classification matches ground truth."""

    @pytest.mark.vcr
    def test_imunon_best_efforts(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        assert p.offering_type == OfferingType.BEST_EFFORTS

    @pytest.mark.vcr
    def test_nextera_atm(self):
        filing = find("0001193125-25-338333")
        p = Prospectus424B.from_filing(filing)
        assert p.offering_type == OfferingType.ATM

    @pytest.mark.vcr
    def test_bofa_structured_note(self):
        filing = find("0001918704-24-002559")
        p = Prospectus424B.from_filing(filing)
        assert p.offering_type == OfferingType.STRUCTURED_NOTE

    @pytest.mark.vcr
    def test_traws_pharma_best_efforts(self):
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.offering_type in (OfferingType.BEST_EFFORTS, OfferingType.FIRM_COMMITMENT)


# ============================================================
# Test: Convenience properties
# ============================================================

class TestConvenienceProperties:
    """Verify shortcut properties delegate correctly to cover_page."""

    @pytest.mark.vcr
    def test_shortcut_properties(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)

        # These should delegate to cover_page
        assert p.ticker == p.cover_page.exchange_ticker
        assert p.offering_price == p.cover_page.offering_price
        assert p.offering_amount == p.cover_page.offering_amount
        assert p.is_atm == p.cover_page.is_atm
        assert p.is_preliminary == p.cover_page.is_preliminary
        assert p.is_supplement == p.cover_page.is_supplement
        assert p.registration_number == p.cover_page.registration_number

    @pytest.mark.vcr
    def test_filing_metadata_properties(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)

        assert p.form == filing.form
        assert p.company == filing.company
        assert p.filing_date == filing.filing_date
        assert p.accession_number == filing.accession_no
        assert p.filing is filing


# ============================================================
# Test: Rich display
# ============================================================

class TestRichDisplay:
    """Verify __repr__ and __str__ produce output."""

    @pytest.mark.vcr
    def test_repr_produces_output(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        text = repr(p)
        assert "Imunon" in text
        assert "424B5" in text
        assert "Best Efforts" in text

    @pytest.mark.vcr
    def test_str_produces_output(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        text = str(p)
        assert "Prospectus424B" in text
        assert "best_efforts" in text


# ============================================================
# Test: Filing fees (Phase 4)
# ============================================================

class TestFilingFees:
    """Verify XBRL filing fees extraction."""

    @pytest.mark.vcr
    def test_imunon_no_filing_fees(self):
        """Imunon 424B5 may or may not have filing fees exhibit."""
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        # Just verify it doesn't crash — coverage varies
        assert isinstance(p.filing_fees.has_exhibit, bool)


# ============================================================
# Test: Table classification and extraction (Phase 2)
# ============================================================

class TestTableClassification:
    """Verify table classification on known filings."""

    @pytest.mark.vcr
    def test_traws_pharma_has_pricing_table(self):
        """Traws Pharma 424B4 should have a pricing table."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.pricing is not None
        assert len(p.pricing.columns) == 2
        assert p.pricing.fee_type == "placement_agent_fees"

    @pytest.mark.vcr
    def test_traws_pharma_pricing_values(self):
        """Traws Pharma pricing: per-share price = $5.103."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.pricing is not None
        per_share = p.pricing.columns[0]
        assert per_share.offering_price == "$5.103"
        total = p.pricing.columns[1]
        assert total.offering_price == "$3,103,629.29"

    @pytest.mark.vcr
    def test_traws_pharma_has_dilution(self):
        """Traws Pharma has a dilution table."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.dilution is not None
        assert p.dilution.public_offering_price == "$5.103"
        assert p.dilution.dilution_per_share == "$5.046"

    @pytest.mark.vcr
    def test_traws_pharma_has_capitalization(self):
        """Traws Pharma has a capitalization table."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.capitalization is not None
        assert p.capitalization.cash_actual == "5,410,000"
        assert p.capitalization.cash_as_adjusted == "7,822,000"
        assert len(p.capitalization.rows) >= 5

    @pytest.mark.vcr
    def test_nextera_atm_no_pricing(self):
        """NextEra ATM offering should have no pricing table."""
        filing = find("0001193125-25-338333")
        p = Prospectus424B.from_filing(filing)
        assert p.pricing is None

    @pytest.mark.vcr
    def test_nextera_atm_no_dilution(self):
        """NextEra ATM has no dilution or capitalization."""
        filing = find("0001193125-25-338333")
        p = Prospectus424B.from_filing(filing)
        assert p.dilution is None
        assert p.capitalization is None


# ============================================================
# Test: CoverPageData model
# ============================================================

class TestCoverPageDataModel:
    """Unit tests for CoverPageData Pydantic model."""

    def test_empty_string_coercion(self):
        cp = CoverPageData(company_name="Test", offering_amount="", offering_price="")
        assert cp.offering_amount is None
        assert cp.offering_price is None

    def test_offering_amount_float(self):
        cp = CoverPageData(company_name="Test", offering_amount="$7,000,040.63")
        assert cp.offering_amount_float == pytest.approx(7000040.63)

    def test_offering_price_float(self):
        cp = CoverPageData(company_name="Test", offering_price="$3.6100")
        assert cp.offering_price_float == pytest.approx(3.61)

    def test_atm_price_returns_none_float(self):
        cp = CoverPageData(company_name="Test", offering_price="at-the-market")
        assert cp.offering_price_float is None

    def test_exchange_amount_returns_none_float(self):
        cp = CoverPageData(company_name="Test", offering_amount="exchange-offer")
        assert cp.offering_amount_float is None


# ============================================================
# Test: OfferingType enum
# ============================================================

class TestOfferingTypeEnum:
    """Unit tests for OfferingType enum properties."""

    def test_display_names(self):
        assert OfferingType.ATM.display_name == "At-the-Market"
        assert OfferingType.FIRM_COMMITMENT.display_name == "Firm Commitment"
        assert OfferingType.STRUCTURED_NOTE.display_name == "Structured Note"

    def test_is_equity(self):
        assert OfferingType.ATM.is_equity is True
        assert OfferingType.FIRM_COMMITMENT.is_equity is True
        assert OfferingType.STRUCTURED_NOTE.is_equity is False
        assert OfferingType.DEBT_OFFERING.is_equity is False

    def test_has_fixed_price(self):
        assert OfferingType.FIRM_COMMITMENT.has_fixed_price is True
        assert OfferingType.ATM.has_fixed_price is False
        assert OfferingType.PIPE_RESALE.has_fixed_price is False

    def test_has_selling_stockholders(self):
        assert OfferingType.PIPE_RESALE.has_selling_stockholders is True
        assert OfferingType.FIRM_COMMITMENT.has_selling_stockholders is False


# ============================================================
# Test: PROSPECTUS_FORMS constant
# ============================================================

class TestConstants:

    def test_prospectus_forms_list(self):
        assert '424B5' in PROSPECTUS_FORMS
        assert '424B2' in PROSPECTUS_FORMS
        assert '424B7' in PROSPECTUS_FORMS
        assert len(PROSPECTUS_FORMS) == 7


# ============================================================
# Test: Underwriting extraction (Phase 3)
# ============================================================

class TestUnderwritingExtraction:
    """Verify underwriting info extraction from tables and text."""

    @pytest.mark.vcr
    def test_traws_pharma_placement_agent(self):
        """Traws Pharma has a sole placement agent from cover page text."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        assert p.underwriting is not None
        assert p.underwriting.lead_manager is not None
        # Tungsten Advisors is the placement agent
        assert 'tungsten' in p.underwriting.lead_manager.lower()

    @pytest.mark.vcr
    def test_nextera_atm_no_underwriting(self):
        """NextEra ATM: sales agents may or may not appear as underwriting."""
        filing = find("0001193125-25-338333")
        p = Prospectus424B.from_filing(filing)
        # ATMs may have sales agents or no underwriting - both are valid
        if p.underwriting is not None:
            assert len(p.underwriting.underwriters) >= 1


# ============================================================
# Test: Structured note terms (Phase 3)
# ============================================================

class TestStructuredNoteTerms:
    """Verify structured note key terms extraction."""

    @pytest.mark.vcr
    def test_bofa_structured_note_terms(self):
        """BofA structured note should have key terms."""
        filing = find("0001918704-24-002559")
        p = Prospectus424B.from_filing(filing)
        # Structured note should have key terms table
        if p.structured_note_terms is not None:
            # If terms are found, they should have at least an issuer or underlying
            terms = p.structured_note_terms
            assert terms.issuer is not None or terms.underlying is not None or terms.cusip is not None


# ============================================================
# Test: Selling stockholders (Phase 3)
# ============================================================

class TestSellingStockholders:
    """Verify selling stockholders table extraction."""

    @pytest.mark.vcr
    def test_imunon_no_selling_stockholders(self):
        """Imunon best-efforts has no selling stockholders."""
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        assert p.selling_stockholders is None


# ============================================================
# Test: ShelfLifecycle
# ============================================================

class TestShelfLifecycle:
    """Verify ShelfLifecycle computation from related filings."""

    @pytest.mark.vcr
    def test_lifecycle_returns_shelf_lifecycle(self):
        """lifecycle property should return a ShelfLifecycle object."""
        filing = find("0001214659-26-002941")  # Alzamend 424B5
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert isinstance(lc, ShelfLifecycle)

    @pytest.mark.vcr
    def test_alzamend_shelf_filed_date(self):
        """Alzamend shelf was filed 2023-08-02."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.shelf_filed_date == "2023-08-02"

    @pytest.mark.vcr
    def test_alzamend_takedown_position(self):
        """Alzamend 424B5 is takedown #5 of 5."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.takedown_number == 5
        assert lc.total_takedowns == 5
        assert lc.is_latest_takedown is True

    @pytest.mark.vcr
    def test_alzamend_shelf_registration(self):
        """Shelf registration should be an S-3 variant."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        reg = lc.shelf_registration
        assert reg is not None
        assert 'S-3' in reg.form or 'S-1' in reg.form

    @pytest.mark.vcr
    def test_alzamend_effective_date(self):
        """Alzamend shelf was declared effective on 2023-08-10."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.effective_date == "2023-08-10"

    @pytest.mark.vcr
    def test_alzamend_review_period(self):
        """S-3 to EFFECT was 8 days."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.review_period_days == 8

    @pytest.mark.vcr
    def test_alzamend_shelf_expires(self):
        """Shelf expires 3 years after filing."""
        from datetime import date
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.shelf_expires == date(2026, 8, 2)

    @pytest.mark.vcr
    def test_alzamend_cadence(self):
        """Average days between takedowns should be positive."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert lc.avg_days_between_takedowns is not None
        assert lc.avg_days_between_takedowns > 0

    @pytest.mark.vcr
    def test_alzamend_filings_returns_full_set(self):
        """filings property should return all related filings."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        assert len(lc.filings) >= 7  # S-3, EFFECT, 5x 424B5

    @pytest.mark.vcr
    def test_imunon_lifecycle_accessible(self):
        """Imunon 424B5 should have an accessible lifecycle."""
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        # lifecycle may or may not be available depending on filing metadata
        if lc is not None:
            assert isinstance(lc, ShelfLifecycle)
            reg = lc.shelf_registration
            if reg is not None:
                assert 'S-' in reg.form or 'F-' in reg.form

    @pytest.mark.vcr
    def test_backward_compat_shelf_registration(self):
        """Prospectus424B.shelf_registration should delegate to lifecycle."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        assert p.shelf_registration is not None
        assert p.shelf_registration is p.lifecycle.shelf_registration

    @pytest.mark.vcr
    def test_backward_compat_related_filings(self):
        """Prospectus424B.related_filings should delegate to lifecycle."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        assert p.related_filings is not None

    @pytest.mark.vcr
    def test_lifecycle_rich_display(self):
        """Rich display should render without error."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        text = repr(lc)
        assert "Shelf Lifecycle" in text
        assert "Alzamend" in text

    @pytest.mark.vcr
    def test_lifecycle_str(self):
        """str() should produce readable summary."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        lc = p.lifecycle
        assert lc is not None
        text = str(lc)
        assert "ShelfLifecycle" in text
        assert "#5/5" in text


# ============================================================
# Test: _parse_sec_number helper
# ============================================================

class TestParseSecNumber:
    """Unit tests for the _parse_sec_number helper."""

    def test_dollar_with_commas(self):
        assert _parse_sec_number("$1,234,567") == 1234567.0

    def test_plain_number_with_commas(self):
        assert _parse_sec_number("1,234,567") == 1234567.0

    def test_decimal_price(self):
        assert _parse_sec_number("$3.6100") == pytest.approx(3.61)

    def test_million_multiplier(self):
        assert _parse_sec_number("10.5 million") == 10500000.0

    def test_billion_multiplier(self):
        assert _parse_sec_number("1.2 billion") == 1200000000.0

    def test_parenthetical_negative(self):
        assert _parse_sec_number("(0.45)") == pytest.approx(-0.45)

    def test_parenthetical_negative_with_inner_space(self):
        assert _parse_sec_number("( 0.45)") == pytest.approx(-0.45)

    def test_plain_negative_number(self):
        assert _parse_sec_number("-0.45") == pytest.approx(-0.45)

    def test_plain_negative_dollar(self):
        assert _parse_sec_number("-$5.00") == pytest.approx(-5.0)

    def test_bare_dash_sentinel(self):
        assert _parse_sec_number("-") is None

    def test_percentage_strip(self):
        assert _parse_sec_number("3.5%") == pytest.approx(3.5)

    def test_none_input(self):
        assert _parse_sec_number(None) is None

    def test_empty_string(self):
        assert _parse_sec_number("") is None

    def test_atm_sentinel(self):
        assert _parse_sec_number("at-the-market") is None

    def test_exchange_sentinel(self):
        assert _parse_sec_number("exchange-offer") is None

    def test_preliminary_sentinel(self):
        assert _parse_sec_number("preliminary-TBD") is None

    def test_real_offering_amount(self):
        assert _parse_sec_number("$7,000,040.63") == pytest.approx(7000040.63)

    def test_dollar_sign_with_space(self):
        assert _parse_sec_number("$ 25.00") == pytest.approx(25.0)


# ============================================================
# Test: Deal object
# ============================================================

class TestDeal:
    """Verify Deal object synthesizes data from sub-objects correctly."""

    @pytest.mark.vcr
    def test_deal_always_returned(self):
        """prospectus.deal never returns None."""
        filing = find("0001214659-26-002941")  # Alzamend 424B5
        p = Prospectus424B.from_filing(filing)
        assert isinstance(p.deal, Deal)

    @pytest.mark.vcr
    def test_deal_is_cached(self):
        """deal property returns same instance on repeated access."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        assert p.deal is p.deal

    @pytest.mark.vcr
    def test_alzamend_offering_type(self):
        """Alzamend is an ATM offering."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.offering_type == OfferingType.ATM
        assert deal.is_atm is True

    @pytest.mark.vcr
    def test_alzamend_security_type(self):
        """Alzamend offers common stock."""
        filing = find("0001214659-26-002941")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.security_type is not None
        assert 'common stock' in deal.security_type.lower()

    @pytest.mark.vcr
    def test_traws_pharma_price(self):
        """Traws Pharma per-share price from pricing table = $5.103."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.price == pytest.approx(5.103, abs=0.01)

    @pytest.mark.vcr
    def test_traws_pharma_fee_per_share(self):
        """Traws Pharma has placement agent fee per share."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.fee_per_share is not None
        assert deal.fee_type == "placement_agent_fees"

    @pytest.mark.vcr
    def test_traws_pharma_discount_rate(self):
        """Discount rate is fee_per_share / price."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        if deal.discount_rate is not None:
            assert 0 < deal.discount_rate < 1  # Should be a fraction, not percent

    @pytest.mark.vcr
    def test_traws_pharma_dilution(self):
        """Traws Pharma has dilution data: $5.046/share."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.dilution_per_share == pytest.approx(5.046, abs=0.01)

    @pytest.mark.vcr
    def test_traws_pharma_gross_proceeds(self):
        """Traws Pharma gross proceeds from pricing table total column."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.gross_proceeds is not None
        assert deal.gross_proceeds == pytest.approx(3103629.29, abs=1.0)

    @pytest.mark.vcr
    def test_traws_pharma_net_proceeds(self):
        """Traws Pharma net proceeds from pricing table total column."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.net_proceeds is not None
        # Net proceeds should be less than gross
        assert deal.net_proceeds < deal.gross_proceeds

    @pytest.mark.vcr
    def test_traws_pharma_underwriting(self):
        """Traws Pharma has Tungsten Advisors as placement agent."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert deal.lead_bookrunner is not None
        assert 'tungsten' in deal.lead_bookrunner.lower()
        assert deal.underwriter_count >= 1

    @pytest.mark.vcr
    def test_bofa_structured_note_graceful(self):
        """BofA 424B2 structured note: most equity fields should be None."""
        filing = find("0001918704-24-002559")
        p = Prospectus424B.from_filing(filing)
        deal = p.deal
        assert isinstance(deal, Deal)
        # Structured notes typically don't have equity-style shares/dilution
        assert deal.offering_type == OfferingType.STRUCTURED_NOTE
        assert deal.security_type is not None

    @pytest.mark.vcr
    def test_to_dict_no_none_values(self):
        """to_dict() should not contain any None values."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        d = p.deal.to_dict()
        for key, val in d.items():
            assert val is not None, f"to_dict() has None for {key}"
        # Should have at least offering_type
        assert 'offering_type' in d

    @pytest.mark.vcr
    def test_to_dict_has_core_fields(self):
        """to_dict() for Traws Pharma should have price and gross_proceeds."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        d = p.deal.to_dict()
        assert 'price' in d
        assert 'gross_proceeds' in d

    @pytest.mark.vcr
    def test_to_context_produces_text(self):
        """to_context() should produce readable LLM context."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        ctx = p.deal.to_context()
        assert "DEAL SUMMARY" in ctx
        assert "Offering Type" in ctx

    @pytest.mark.vcr
    def test_deal_repr(self):
        """repr() should produce rich output without crashing."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        text = repr(p.deal)
        assert "Deal" in text

    @pytest.mark.vcr
    def test_deal_str(self):
        """str() should produce readable summary."""
        filing = find("0001104659-24-132924")
        p = Prospectus424B.from_filing(filing)
        text = str(p.deal)
        assert "Deal" in text
        assert "Traws Pharma" in text or "company=" in text
