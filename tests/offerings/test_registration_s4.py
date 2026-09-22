"""Verification tests for the RegistrationS4 data object (S-4 / F-4).

Phase 1 parity object — beads edgartools-6yis, GH #876. Covers cover-page
extraction (reusing the S-1 extractor), offering-type classification, the
Exhibit 107 fee table, and form-specific behavior (F-4 foreign flag,
amendments). Ground truth is verified against four real filings in the
``@pytest.mark.network`` classes below.
"""

import pytest

from edgar.offerings.registration_s4 import (
    RegistrationS4, S4OfferingType, S4CoverPage,
    _extract_s4_cover_page, _classify_s4_offering,
)


# ---------------------------------------------------------------------------
# Offering type
# ---------------------------------------------------------------------------

class TestS4OfferingType:

    def test_display_names(self):
        assert S4OfferingType.BUSINESS_COMBINATION.display_name == "Business Combination"
        assert S4OfferingType.EXCHANGE_OFFER.display_name == "Exchange Offer"
        assert S4OfferingType.UNKNOWN.display_name == "Unknown"

    def test_enum_values(self):
        assert S4OfferingType("business_combination") == S4OfferingType.BUSINESS_COMBINATION
        assert S4OfferingType("exchange_offer") == S4OfferingType.EXCHANGE_OFFER


# ---------------------------------------------------------------------------
# Classifier (no network — synthetic cover text)
# ---------------------------------------------------------------------------

class TestS4Classifier:

    def test_business_combination_from_merger_language(self):
        html = "<html><body>This proxy statement/prospectus relates to the Agreement and Plan of Merger.</body></html>"
        assert _classify_s4_offering(None, html=html) == S4OfferingType.BUSINESS_COMBINATION

    def test_exchange_offer_when_no_merger(self):
        html = "<html><body>Offer to Exchange all outstanding 5.0% Senior Notes. Contact the exchange agent.</body></html>"
        assert _classify_s4_offering(None, html=html) == S4OfferingType.EXCHANGE_OFFER

    def test_combination_wins_tie(self):
        # A merger that also references an exchange offer is still, at the
        # registration level, a business combination.
        html = "<html><body>Agreement and Plan of Merger ... a concurrent exchange offer for the notes</body></html>"
        assert _classify_s4_offering(None, html=html) == S4OfferingType.BUSINESS_COMBINATION

    def test_boilerplate_business_combinations_not_misclassified(self):
        # A pure exchange offer that merely mentions "business combinations" in
        # risk-factor boilerplate must NOT be tagged a business combination —
        # only deal-document phrasing counts.
        html = ("<html><body>Offer to Exchange our 5% Senior Notes. Contact the "
                "exchange agent. Risk factors: our ability to consummate "
                "acquisitions or business combinations may be limited.</body></html>")
        assert _classify_s4_offering(None, html=html) == S4OfferingType.EXCHANGE_OFFER

    def test_marker_split_across_tags(self):
        # A deal phrase broken across HTML elements must still match after tags
        # are stripped.
        html = "<html><body>Agreement and Plan of <br/>Merger dated as of ...</body></html>"
        assert _classify_s4_offering(None, html=html) == S4OfferingType.BUSINESS_COMBINATION

    def test_unknown_when_no_markers(self):
        assert _classify_s4_offering(None, html="<html><body>nothing relevant here</body></html>") == S4OfferingType.UNKNOWN

    def test_unknown_when_no_html(self):
        class FakeFiling:
            def html(self): return None
        assert _classify_s4_offering(FakeFiling(), html=None) == S4OfferingType.UNKNOWN


# ---------------------------------------------------------------------------
# Cover page model + extraction (no network)
# ---------------------------------------------------------------------------

class TestS4CoverPage:

    def test_default_values(self):
        cp = S4CoverPage(company_name="Test Corp")
        assert cp.company_name == "Test Corp"
        assert cp.registration_number is None
        assert cp.is_rule_415 is False
        assert cp.confidence == "low"

    def test_all_fields(self):
        cp = S4CoverPage(
            company_name="Acquirer Inc",
            registration_number="333-123456",
            state_of_incorporation="Delaware",
            sic_code="2834",
            ein="12-3456789",
            is_smaller_reporting_company=True,
            confidence="high",
        )
        assert cp.registration_number == "333-123456"
        assert cp.sic_code == "2834"
        assert cp.is_smaller_reporting_company is True


class TestS4CoverExtractor:

    def test_extract_returns_s4_cover_page(self):
        """Reuses the S-1 extractor; falls back to the 333- regex without a header."""
        class FakeFiling:
            company = "Acquirer Inc"
            form = "S-4"

        html = "<html><body>Registration No. 333-123456 ... Agreement and Plan of Merger</body></html>"
        cp = _extract_s4_cover_page(FakeFiling(), html)
        assert isinstance(cp, S4CoverPage)
        assert cp.registration_number == "333-123456"
        assert cp.company_name == "Acquirer Inc"

    def test_company_name_fallback(self):
        class FakeFiling:
            company = "Fallback Corp"
            form = "F-4"

        cp = _extract_s4_cover_page(FakeFiling(), "<html><body>no reg number</body></html>")
        assert cp.company_name == "Fallback Corp"
        assert cp.registration_number is None


# ---------------------------------------------------------------------------
# RegistrationS4 behavior (synthetic — no network)
# ---------------------------------------------------------------------------

def _synthetic_s4(form="S-4", offering_type=S4OfferingType.BUSINESS_COMBINATION,
                  cover=None, fee_table=None):
    s4 = RegistrationS4.__new__(RegistrationS4)
    s4._cover_page = cover or S4CoverPage(company_name="Test Corp")
    s4._offering_type = offering_type
    s4._fee_table = fee_table

    class FakeFiling:
        pass
    ff = FakeFiling()
    ff.form = form
    ff.company = "Test Corp"
    ff.filing_date = "2026-01-15"
    ff.accession_no = "0000000000-00-000000"
    ff.cik = 12345
    s4._filing = ff
    return s4


class TestRegistrationS4Synthetic:

    def test_str_representation(self):
        result = str(_synthetic_s4())
        assert "RegistrationS4" in result
        assert "Test Corp" in result
        assert "business_combination" in result

    def test_is_foreign_true_for_f4(self):
        assert _synthetic_s4(form="F-4").is_foreign is True
        assert _synthetic_s4(form="F-4/A").is_foreign is True

    def test_is_foreign_false_for_s4(self):
        assert _synthetic_s4(form="S-4").is_foreign is False
        assert _synthetic_s4(form="S-4/A").is_foreign is False

    def test_is_amendment(self):
        assert _synthetic_s4(form="S-4/A").is_amendment is True
        assert _synthetic_s4(form="F-4/A").is_amendment is True
        assert _synthetic_s4(form="S-4").is_amendment is False

    def test_total_offering_none_without_fee_table(self):
        s4 = _synthetic_s4(fee_table=None)
        assert s4.total_offering is None
        assert s4.net_fee is None
        assert s4.securities == []

    def test_to_context_minimal(self):
        cover = S4CoverPage(
            company_name="Test Corp",
            registration_number="333-284099",
            state_of_incorporation="Delaware",
            sic_code="2834",
            confidence="high",
        )
        ctx = _synthetic_s4(form="F-4", cover=cover).to_context(detail='minimal')
        assert "Test Corp" in ctx
        assert "333-284099" in ctx
        assert "Delaware" in ctx
        assert "FOREIGN (F-4)" in ctx


# ---------------------------------------------------------------------------
# Network tests — ground truth against real filings
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestRegistrationS4NexPoint:
    """Domestic S-4 — NexPoint Diversified Real Estate Trust reorganization."""

    @pytest.fixture(scope="class")
    def s4(self):
        from edgar import find
        f = find("0001437749-24-038595")
        if f is None:
            pytest.skip("Could not fetch filing from SEC")
        return f.obj()

    def test_returns_registration_s4(self, s4):
        assert isinstance(s4, RegistrationS4)

    def test_form(self, s4):
        assert s4.form == "S-4"

    def test_not_foreign(self, s4):
        assert s4.is_foreign is False

    def test_not_amendment(self, s4):
        assert s4.is_amendment is False

    def test_offering_type(self, s4):
        assert s4.offering_type == S4OfferingType.BUSINESS_COMBINATION

    def test_registration_number(self, s4):
        assert s4.registration_number == "333-284099"

    def test_state(self, s4):
        assert s4.state_of_incorporation == "Delaware"

    def test_ein(self, s4):
        assert s4.ein == "80-0139099"

    def test_fee_table_exists(self, s4):
        assert s4.fee_table is not None

    def test_total_offering(self, s4):
        assert s4.total_offering == 9161137.05

    def test_net_fee(self, s4):
        assert s4.net_fee == 1402.57


@pytest.mark.network
class TestRegistrationS4BroadCapital:
    """S-4/A amendment — Broad Capital Acquisition (SPAC business combination)."""

    @pytest.fixture(scope="class")
    def s4(self):
        from edgar import find
        f = find("0001493152-24-052709")
        if f is None:
            pytest.skip("Could not fetch filing from SEC")
        return f.obj()

    def test_returns_registration_s4(self, s4):
        assert isinstance(s4, RegistrationS4)

    def test_form(self, s4):
        assert s4.form == "S-4/A"

    def test_is_amendment(self, s4):
        assert s4.is_amendment is True

    def test_offering_type(self, s4):
        assert s4.offering_type == S4OfferingType.BUSINESS_COMBINATION

    def test_registration_number(self, s4):
        assert s4.registration_number == "333-273753"

    def test_total_offering(self, s4):
        assert s4.total_offering == 207083299.26

    def test_securities_count(self, s4):
        assert len(s4.securities) == 2


@pytest.mark.network
class TestRegistrationS4NLS:
    """Foreign F-4 — NLS Pharmaceutics (Switzerland) merger."""

    @pytest.fixture(scope="class")
    def f4(self):
        from edgar import find
        f = find("0001213900-24-113211")
        if f is None:
            pytest.skip("Could not fetch filing from SEC")
        return f.obj()

    def test_returns_registration_s4(self, f4):
        assert isinstance(f4, RegistrationS4)

    def test_form(self, f4):
        assert f4.form == "F-4"

    def test_is_foreign(self, f4):
        assert f4.is_foreign is True

    def test_offering_type(self, f4):
        assert f4.offering_type == S4OfferingType.BUSINESS_COMBINATION

    def test_registration_number(self, f4):
        assert f4.registration_number == "333-284075"

    def test_state_switzerland(self, f4):
        assert f4.state_of_incorporation == "Switzerland"

    def test_total_offering(self, f4):
        assert f4.total_offering == 37947879.0

    def test_securities_count(self, f4):
        assert len(f4.securities) == 3


@pytest.mark.network
class TestRegistrationS4SciSparc:
    """Foreign F-4/A amendment — SciSparc (Israel) business combination."""

    @pytest.fixture(scope="class")
    def f4(self):
        from edgar import find
        f = find("0001213900-24-113993")
        if f is None:
            pytest.skip("Could not fetch filing from SEC")
        return f.obj()

    def test_returns_registration_s4(self, f4):
        assert isinstance(f4, RegistrationS4)

    def test_form(self, f4):
        assert f4.form == "F-4/A"

    def test_is_foreign_and_amendment(self, f4):
        assert f4.is_foreign is True
        assert f4.is_amendment is True

    def test_registration_number(self, f4):
        assert f4.registration_number == "333-282351"

    def test_state_israel(self, f4):
        assert f4.state_of_incorporation == "Israel"

    def test_total_offering(self, f4):
        assert f4.total_offering == 6221518.14
