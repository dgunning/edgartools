"""
Verification tests for RegistrationS1 data object.

Ground truth filings:
  - Solidion Technology (0001213900-26-015175) — IPO
  - BEST SPAC II (0001213900-26-025801) — SPAC
  - Wolfspeed (0001193125-26-098748) — Resale
"""
import pytest
from edgar.offerings.registration_s1 import RegistrationS1, S1OfferingType, S1CoverPage


# ---------------------------------------------------------------------------
# Cover page model tests (no network)
# ---------------------------------------------------------------------------

class TestS1CoverPage:

    def test_default_values(self):
        cp = S1CoverPage(company_name="Test Co")
        assert cp.company_name == "Test Co"
        assert cp.registration_number is None
        assert cp.sic_code is None
        assert cp.is_rule_415 is False
        assert cp.confidence == "low"

    def test_all_fields(self):
        cp = S1CoverPage(
            company_name="Test Co",
            registration_number="333-123456",
            state_of_incorporation="Delaware",
            sic_code="3674",
            ein="12-3456789",
            is_large_accelerated_filer=False,
            is_non_accelerated_filer=True,
            is_smaller_reporting_company=True,
            is_emerging_growth_company=True,
            is_rule_415=False,
            confidence="high",
        )
        assert cp.sic_code == "3674"
        assert cp.is_non_accelerated_filer is True
        assert cp.is_emerging_growth_company is True


class TestS1OfferingType:

    def test_display_names(self):
        assert S1OfferingType.IPO.display_name == "Initial Public Offering"
        assert S1OfferingType.SPAC.display_name == "SPAC IPO"
        assert S1OfferingType.RESALE.display_name == "Resale Registration"
        assert S1OfferingType.DEBT.display_name == "Debt Offering"
        assert S1OfferingType.FOLLOW_ON.display_name == "Follow-On Offering"
        assert S1OfferingType.UNKNOWN.display_name == "Unknown"

    def test_string_values(self):
        assert S1OfferingType.IPO.value == "ipo"
        assert S1OfferingType.SPAC.value == "spac"
        assert S1OfferingType.RESALE.value == "resale"


# ---------------------------------------------------------------------------
# Classifier tests (no network)
# ---------------------------------------------------------------------------

class TestS1Classifier:

    def test_classifier_import(self):
        from edgar.offerings._s1_classifier import classify_s1_offering_type
        assert callable(classify_s1_offering_type)

    def test_classifier_returns_dict_keys(self):
        from edgar.offerings._s1_classifier import classify_s1_offering_type

        class FakeFiling:
            def html(self): return "<html>blank check company trust account</html>"

        result = classify_s1_offering_type(FakeFiling(), html="<html>blank check company trust account</html>")
        assert 'type' in result
        assert 'confidence' in result
        assert 'signals' in result

    def test_spac_signals(self):
        from edgar.offerings._s1_classifier import classify_s1_offering_type
        html = "<html><body>This is a blank check company formed for the purpose of a business combination. Trust account.</body></html>"
        result = classify_s1_offering_type(None, html=html)
        assert result['type'] == 'spac'
        assert result['confidence'] == 'high'

    def test_resale_signals(self):
        from edgar.offerings._s1_classifier import classify_s1_offering_type
        html = "<html><body>resale of shares by selling stockholders. We will not receive any proceeds from the sale. registration rights agreement</body></html>"
        result = classify_s1_offering_type(None, html=html)
        assert result['type'] == 'resale'

    def test_ipo_signals(self):
        from edgar.offerings._s1_classifier import classify_s1_offering_type
        html = "<html><body>initial public offering price. no established trading market for our common stock. we have applied to list our shares on nasdaq.</body></html>"
        result = classify_s1_offering_type(None, html=html)
        assert result['type'] == 'ipo'


# ---------------------------------------------------------------------------
# Cover page extractor tests (no network)
# ---------------------------------------------------------------------------

class TestS1CoverExtractor:

    def test_extract_imports(self):
        from edgar.offerings._s1_cover import extract_s1_cover_page
        assert callable(extract_s1_cover_page)


# ---------------------------------------------------------------------------
# Network tests — ground truth verification
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestRegistrationS1Solidion:
    """Solidion Technology — IPO S-1 with full XBRL financials."""

    @pytest.fixture(scope="class")
    def solidion(self):
        from edgar import find
        f = find("0001213900-26-015175")
        return f.obj()

    def test_returns_registration_s1(self, solidion):
        assert isinstance(solidion, RegistrationS1)

    def test_form_is_s1(self, solidion):
        assert solidion.form == "S-1"

    def test_company_name(self, solidion):
        assert "Solidion" in solidion.company

    def test_offering_type_is_ipo(self, solidion):
        assert solidion.offering_type == S1OfferingType.IPO

    def test_state_of_incorporation(self, solidion):
        assert solidion.cover_page.state_of_incorporation == "Delaware"

    def test_sic_code(self, solidion):
        assert solidion.cover_page.sic_code == "3359"

    def test_ein(self, solidion):
        assert solidion.cover_page.ein == "87-1993879"

    def test_registration_number(self, solidion):
        assert solidion.cover_page.registration_number == "333-293402"

    def test_non_accelerated_filer(self, solidion):
        assert solidion.cover_page.is_non_accelerated_filer is True

    def test_smaller_reporting_company(self, solidion):
        assert solidion.cover_page.is_smaller_reporting_company is True

    def test_emerging_growth_company(self, solidion):
        assert solidion.cover_page.is_emerging_growth_company is True

    def test_large_accelerated_filer_false(self, solidion):
        assert solidion.cover_page.is_large_accelerated_filer is False

    def test_rule_415_false(self, solidion):
        assert solidion.cover_page.is_rule_415 is False

    def test_fee_table_exists(self, solidion):
        assert solidion.fee_table is not None

    def test_total_offering(self, solidion):
        assert solidion.total_offering == 14490000.0

    def test_net_fee(self, solidion):
        assert solidion.net_fee == 2001.07

    def test_securities_count(self, solidion):
        assert len(solidion.securities) == 3

    def test_confidence_high(self, solidion):
        assert solidion.cover_page.confidence == "high"

    def test_is_not_amendment(self, solidion):
        assert solidion.is_amendment is False

    def test_rich_display(self, solidion):
        rich_output = solidion.__rich__()
        assert rich_output is not None

    def test_to_context(self, solidion):
        ctx = solidion.to_context()
        assert "Solidion" in ctx
        assert "IPO" in ctx or "Initial Public Offering" in ctx

    def test_str(self, solidion):
        s = str(solidion)
        assert "RegistrationS1" in s
        assert "ipo" in s


@pytest.mark.network
class TestRegistrationS1BestSpac:
    """BEST SPAC II — SPAC IPO with no operating financials."""

    @pytest.fixture(scope="class")
    def spac(self):
        from edgar import find
        f = find("0001213900-26-025801")
        return f.obj()

    def test_returns_registration_s1(self, spac):
        assert isinstance(spac, RegistrationS1)

    def test_offering_type_is_spac(self, spac):
        assert spac.offering_type == S1OfferingType.SPAC

    def test_state_bvi(self, spac):
        assert "British Virgin Islands" in spac.cover_page.state_of_incorporation

    def test_sic_code(self, spac):
        assert spac.cover_page.sic_code == "6770"

    def test_total_offering(self, spac):
        assert spac.total_offering == 129375000.0


@pytest.mark.network
class TestRegistrationS1Wolfspeed:
    """Wolfspeed — Resale registration, large accelerated filer."""

    @pytest.fixture(scope="class")
    def wolfspeed(self):
        from edgar import find
        f = find("0001193125-26-098748")
        return f.obj()

    def test_returns_registration_s1(self, wolfspeed):
        assert isinstance(wolfspeed, RegistrationS1)

    def test_offering_type_is_resale(self, wolfspeed):
        assert wolfspeed.offering_type == S1OfferingType.RESALE

    def test_state_delaware(self, wolfspeed):
        assert wolfspeed.cover_page.state_of_incorporation == "Delaware"

    def test_sic_code(self, wolfspeed):
        assert wolfspeed.cover_page.sic_code == "3674"

    def test_ein(self, wolfspeed):
        assert wolfspeed.cover_page.ein == "56-1572719"

    def test_large_accelerated_filer(self, wolfspeed):
        assert wolfspeed.cover_page.is_large_accelerated_filer is True

    def test_accelerated_filer_false(self, wolfspeed):
        assert wolfspeed.cover_page.is_accelerated_filer is False

    def test_rule_415_true(self, wolfspeed):
        assert wolfspeed.cover_page.is_rule_415 is True

    def test_total_offering(self, wolfspeed):
        assert wolfspeed.total_offering == pytest.approx(573310592.82, rel=0.01)

    def test_rich_display(self, wolfspeed):
        rich_output = wolfspeed.__rich__()
        assert rich_output is not None

    def test_to_context_full(self, wolfspeed):
        ctx = wolfspeed.to_context(detail='full')
        assert "Resale" in ctx
        assert ".cover_page" in ctx


# ---------------------------------------------------------------------------
# obj() dispatch tests
# ---------------------------------------------------------------------------

class TestObjInfo:

    def test_get_obj_info_s1(self):
        from edgar import get_obj_info
        has_obj, class_name, description = get_obj_info("S-1")
        assert has_obj is True
        assert class_name == "RegistrationS1"

    def test_get_obj_info_s1a(self):
        from edgar import get_obj_info
        has_obj, class_name, description = get_obj_info("S-1/A")
        assert has_obj is True
        assert class_name == "RegistrationS1"

    def test_get_obj_info_f1(self):
        from edgar import get_obj_info
        has_obj, class_name, description = get_obj_info("F-1")
        assert has_obj is True
        assert class_name == "RegistrationS1"

    def test_get_obj_info_f1a(self):
        from edgar import get_obj_info
        has_obj, class_name, description = get_obj_info("F-1/A")
        assert has_obj is True
        assert class_name == "RegistrationS1"


@pytest.mark.network
class TestObjDispatch:

    def test_s1_returns_registration_s1(self):
        from edgar import find
        f = find("0001213900-26-015175")
        obj = f.obj()
        assert isinstance(obj, RegistrationS1)
