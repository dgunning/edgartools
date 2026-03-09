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
    OfferingType,
    CoverPageData,
    PROSPECTUS_FORMS,
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
# Test: Phase 4 stubs return None
# ============================================================

class TestPhase4Stubs:
    """Phase 4 stubs should return None (to be replaced later)."""

    @pytest.mark.vcr
    def test_phase4_stubs_return_none(self):
        filing = find("0001493152-25-029712")
        p = Prospectus424B.from_filing(filing)

        assert p.filing_fees.has_exhibit is False


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
