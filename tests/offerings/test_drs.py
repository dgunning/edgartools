"""
Verification tests for DraftRegistrationStatement data object.

Ground truth filings:
  - Forgent Power Solutions (0001193125-26-112869) — DRS, S-1 underlying
  - Texxon Holding Ltd (0001213900-26-027227) — DRS, F-1 underlying
  - Arxis, Inc. (0001193125-26-106851) — DRS/A, S-1 underlying
"""
import pytest
from edgar.offerings.drs import DraftRegistrationStatement, _detect_underlying_form


# ---------------------------------------------------------------------------
# Underlying form detection (no network)
# ---------------------------------------------------------------------------

class TestUnderlyingFormDetection:

    def test_detect_s1(self):
        html = "<html><body>FORM S-1 REGISTRATION STATEMENT</body></html>"
        form, amendment = _detect_underlying_form(html)
        assert form == 'S-1'
        assert amendment is None

    def test_detect_f1(self):
        html = "<html><body>FORM F-1 REGISTRATION STATEMENT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'F-1'

    def test_detect_s4(self):
        html = "<html><body>FORM S-4 REGISTRATION STATEMENT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'S-4'

    def test_detect_form_10(self):
        html = "<html><body>GENERAL FORM FOR REGISTRATION OF SECURITIES</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'Form 10'

    def test_detect_20f(self):
        html = "<html><body>FORM 20-F ANNUAL REPORT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == '20-F'

    def test_detect_with_whitespace(self):
        """The HTML line-break problem: FORM and type separated by newline."""
        html = "<html><body><center>FORM\nF-1\nREGISTRATION STATEMENT</center></body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'F-1'

    def test_detect_amendment_number(self):
        html = "<html><body>Amendment No. 3 FORM S-1</body></html>"
        form, amendment = _detect_underlying_form(html)
        assert form == 'S-1'
        assert amendment == 3

    def test_unknown_form(self):
        html = "<html><body>Just some random text</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'Unknown'

    def test_s3_before_s1(self):
        """S-3 should be detected even if S-1 pattern would also match."""
        html = "<html><body>FORM S-3 REGISTRATION STATEMENT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'S-3'

    def test_f3(self):
        html = "<html><body>FORM F-3 REGISTRATION STATEMENT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'F-3'

    def test_f4(self):
        html = "<html><body>FORM F-4 REGISTRATION STATEMENT</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == 'F-4'

    def test_40f(self):
        html = "<html><body>FORM 40-F</body></html>"
        form, _ = _detect_underlying_form(html)
        assert form == '40-F'


# ---------------------------------------------------------------------------
# obj() dispatch (no network)
# ---------------------------------------------------------------------------

class TestObjInfo:

    def test_drs_obj_info(self):
        from edgar import get_obj_info
        has_obj, class_name, desc = get_obj_info("DRS")
        assert has_obj is True
        assert class_name == 'DraftRegistrationStatement'

    def test_drs_a_obj_info(self):
        from edgar import get_obj_info
        has_obj, class_name, desc = get_obj_info("DRS/A")
        assert has_obj is True
        assert class_name == 'DraftRegistrationStatement'


# ---------------------------------------------------------------------------
# Network tests — real DRS filings
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestDraftRegistrationStatement:
    """Test with real DRS filings from EDGAR."""

    def test_s1_drs_forgent(self):
        """Forgent Power Solutions — DRS with S-1 underlying."""
        from edgar import find
        filing = find('0001193125-26-112869')
        drs = filing.obj()

        assert isinstance(drs, DraftRegistrationStatement)
        assert drs.form == 'DRS'
        assert drs.underlying_form == 'S-1'
        assert drs.company == 'Forgent Power Solutions, Inc.'
        assert drs.is_amendment is False
        assert drs.registration_number == '377-09148'

        # Underlying object should be RegistrationS1
        from edgar.offerings.registration_s1 import RegistrationS1
        assert isinstance(drs.underlying_object, RegistrationS1)

    def test_f1_drs_texxon(self):
        """Texxon Holding — DRS with F-1 underlying (foreign issuer)."""
        from edgar import find
        filing = find('0001213900-26-027227')
        drs = filing.obj()

        assert isinstance(drs, DraftRegistrationStatement)
        assert drs.underlying_form == 'F-1'
        assert drs.company == 'Texxon Holding Ltd'
        assert drs.is_amendment is False

        # F-1 also delegates to RegistrationS1
        from edgar.offerings.registration_s1 import RegistrationS1
        assert isinstance(drs.underlying_object, RegistrationS1)

    def test_drs_amendment_arxis(self):
        """Arxis — DRS/A amendment."""
        from edgar import find
        filing = find('0001193125-26-106851')
        drs = filing.obj()

        assert isinstance(drs, DraftRegistrationStatement)
        assert drs.form == 'DRS/A'
        assert drs.is_amendment is True
        assert drs.underlying_form == 'S-1'

    def test_rich_display(self):
        """Rich display should render without error."""
        from edgar import find
        filing = find('0001193125-26-112869')
        drs = filing.obj()

        rich_output = drs.__rich__()
        assert rich_output is not None

    def test_to_context(self):
        """AI context should include underlying form info."""
        from edgar import find
        filing = find('0001193125-26-112869')
        drs = filing.obj()

        ctx = drs.to_context()
        assert 'DRS DRAFT REGISTRATION STATEMENT' in ctx
        assert 'S-1' in ctx
        assert 'Forgent Power Solutions' in ctx

    def test_str(self):
        """String representation should be concise."""
        from edgar import find
        filing = find('0001193125-26-112869')
        drs = filing.obj()

        s = str(drs)
        assert 'DraftRegistrationStatement' in s
        assert 'S-1' in s
