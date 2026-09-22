"""Verification tests for FortyF (40-F Canadian MJDS annual report).

Ground-truth assertions use Shopify Inc.'s 2024 40-F filing (FY2023).
"""
import pytest
from edgar import Filing
from edgar.company_reports import FortyF


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shop_40f_filing():
    """Shopify Inc. 2024 40-F filing (fiscal year ending Dec 31, 2023)."""
    return Filing(
        company='SHOPIFY INC.', cik=1594805, form='40-F',
        filing_date='2024-02-13', accession_no='0001594805-24-000007',
    )


@pytest.fixture(scope="module")
def shop_forty_f(shop_40f_filing):
    """FortyF object for Shopify — cached for the module."""
    return shop_40f_filing.obj()


# ---------------------------------------------------------------------------
# Construction and basic properties
# ---------------------------------------------------------------------------

class TestFortyFConstruction:

    @pytest.mark.network
    def test_filing_obj_returns_forty_f(self, shop_40f_filing):
        obj = shop_40f_filing.obj()
        assert isinstance(obj, FortyF)

    @pytest.mark.network
    def test_basic_properties(self, shop_forty_f):
        assert shop_forty_f.company == 'SHOPIFY INC.'
        assert shop_forty_f.form == '40-F'
        assert str(shop_forty_f.filing_date) == '2024-02-13'
        assert str(shop_forty_f.period_of_report) == '2023-12-31'

    def test_wrong_form_raises(self):
        """Constructing FortyF from a non-40-F filing raises AssertionError."""
        f = Filing(company='Apple Inc.', cik=320193, form='10-K',
                   filing_date='2024-11-01', accession_no='0000320193-24-000123')
        with pytest.raises(AssertionError, match="Expected 40-F"):
            FortyF(f)


# ---------------------------------------------------------------------------
# AIF discovery
# ---------------------------------------------------------------------------

class TestAIFDiscovery:

    @pytest.mark.network
    def test_aif_attachment_found(self, shop_forty_f):
        """SHOP uses EX-1 (standard MJDS) for its AIF."""
        assert shop_forty_f.aif_attachment is not None
        assert 'EX-1' in shop_forty_f._aif_result[1]

    @pytest.mark.network
    def test_aif_html_is_large(self, shop_forty_f):
        """The AIF HTML should be substantial (600K+ chars for SHOP)."""
        html = shop_forty_f.aif_html
        assert html is not None
        assert len(html) > 500_000

    @pytest.mark.network
    def test_aif_text_is_large(self, shop_forty_f):
        """The AIF plain text should be substantial (300K+ chars for SHOP)."""
        text = shop_forty_f.aif_text
        assert text is not None
        assert len(text) > 200_000


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

class TestSectionDetection:

    @pytest.mark.network
    def test_items_detects_multiple_sections(self, shop_forty_f):
        items = shop_forty_f.items
        assert len(items) >= 7

    @pytest.mark.network
    def test_items_contains_key_ni_51_102_sections(self, shop_forty_f):
        """SHOP's AIF should contain the core NI 51-102 sections."""
        items_lower = [i.lower() for i in shop_forty_f.items]
        assert 'corporate structure' in items_lower
        assert 'risk factors' in items_lower
        assert 'directors and officers' in items_lower
        assert 'legal proceedings' in items_lower


# ---------------------------------------------------------------------------
# Named section properties — ground-truth assertions
# ---------------------------------------------------------------------------

class TestNamedProperties:

    @pytest.mark.network
    def test_business_contains_shopify_description(self, shop_forty_f):
        biz = shop_forty_f.business
        assert biz is not None
        assert 'Shopify' in biz
        assert 'commerce' in biz.lower()

    @pytest.mark.network
    def test_risk_factors_not_empty(self, shop_forty_f):
        rf = shop_forty_f.risk_factors
        assert rf is not None
        assert len(rf) > 5000  # Risk factors are always lengthy

    @pytest.mark.network
    def test_corporate_structure_mentions_incorporation(self, shop_forty_f):
        cs = shop_forty_f.corporate_structure
        assert cs is not None
        assert 'Canada Business Corporations Act' in cs

    @pytest.mark.network
    def test_dividends_section(self, shop_forty_f):
        """SHOP hasn't declared dividends — the section should say so."""
        div = shop_forty_f.dividends
        assert div is not None
        assert 'not declared' in div.lower() or 'no dividend' in div.lower() or 'not currently' in div.lower()

    @pytest.mark.network
    def test_directors_and_officers_mentions_ceo(self, shop_forty_f):
        dao = shop_forty_f.directors_and_officers
        assert dao is not None
        # Tobi Lütke is Shopify's founder/CEO
        assert 'Lütke' in dao or 'Lutke' in dao or 'L\u00fctke' in dao

    @pytest.mark.network
    def test_legal_proceedings_present(self, shop_forty_f):
        lp = shop_forty_f.legal_proceedings
        assert lp is not None
        assert len(lp) > 100

    @pytest.mark.network
    def test_capital_structure_none_when_absent(self, shop_forty_f):
        """SHOP's AIF doesn't have a 'Description Of Capital Structure' heading."""
        assert shop_forty_f.capital_structure is None


# ---------------------------------------------------------------------------
# __getitem__ — exact, fuzzy, and edge cases
# ---------------------------------------------------------------------------

class TestGetItem:

    @pytest.mark.network
    def test_exact_case_insensitive_match(self, shop_forty_f):
        assert shop_forty_f['risk factors'] is not None
        assert shop_forty_f['RISK FACTORS'] is not None

    @pytest.mark.network
    def test_fuzzy_keyword_match(self, shop_forty_f):
        """'business' should match 'Description Of The Business'."""
        result = shop_forty_f['business']
        assert result is not None
        assert 'Shopify' in result

    @pytest.mark.network
    def test_missing_section_returns_none(self, shop_forty_f):
        assert shop_forty_f['Nonexistent Section XYZ'] is None

    @pytest.mark.network
    def test_empty_key_returns_none(self, shop_forty_f):
        assert shop_forty_f[''] is None
        assert shop_forty_f['   '] is None

    def test_non_string_key_raises_type_error(self, shop_forty_f):
        with pytest.raises(TypeError, match="must be a string"):
            shop_forty_f[42]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class TestDisplay:

    @pytest.mark.network
    def test_repr_contains_company_and_sections(self, shop_forty_f):
        r = repr(shop_forty_f)
        assert 'SHOPIFY' in r
        assert '40-F' in r
        # The tree should show section names
        assert 'Risk Factors' in r

    @pytest.mark.network
    def test_get_structure_returns_tree(self, shop_forty_f):
        from rich.tree import Tree
        tree = shop_forty_f.get_structure()
        assert isinstance(tree, Tree)


# ---------------------------------------------------------------------------
# LLM context
# ---------------------------------------------------------------------------

class TestToContext:

    @pytest.mark.network
    def test_to_context_minimal(self, shop_forty_f):
        ctx = shop_forty_f.to_context('minimal')
        assert 'SHOPIFY' in ctx
        assert '40-F' in ctx
        assert 'AIF: found' in ctx

    @pytest.mark.network
    def test_to_context_standard_lists_properties(self, shop_forty_f):
        ctx = shop_forty_f.to_context()
        assert '.risk_factors' in ctx
        assert '.aif_text' in ctx
        assert 'Detected Sections' in ctx

    @pytest.mark.network
    def test_to_context_full_has_previews(self, shop_forty_f):
        ctx = shop_forty_f.to_context('full')
        assert 'SECTION PREVIEWS' in ctx
        assert 'Corporate Structure' in ctx


# ---------------------------------------------------------------------------
# Financials (from base class)
# ---------------------------------------------------------------------------

class TestFinancials:

    @pytest.mark.network
    def test_financials_available(self, shop_forty_f):
        """40-F filings contain XBRL financial data."""
        assert shop_forty_f.financials is not None

    @pytest.mark.network
    def test_income_statement(self, shop_forty_f):
        stmt = shop_forty_f.income_statement
        assert stmt is not None

    @pytest.mark.network
    def test_balance_sheet(self, shop_forty_f):
        stmt = shop_forty_f.balance_sheet
        assert stmt is not None


# ---------------------------------------------------------------------------
# MD&A discovery — filer with separate MD&A exhibit (Manulife Financial)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mfc_40f_filing():
    """Manulife Financial Corp. 40-F filing (fiscal year ending Dec 31, 2024)."""
    return Filing(
        company='MANULIFE FINANCIAL CORP', cik=1086888, form='40-F',
        filing_date='2025-02-19', accession_no='0001086888-25-000054',
    )


@pytest.fixture(scope="module")
def mfc_forty_f(mfc_40f_filing):
    """FortyF object for Manulife — cached for the module."""
    return mfc_40f_filing.obj()


class TestMDADiscovery:

    @pytest.mark.network
    def test_mda_attachment_found(self, mfc_forty_f):
        """MFC includes a separate MD&A as an EX-99.x exhibit."""
        assert mfc_forty_f.mda_attachment is not None

    @pytest.mark.network
    def test_mda_different_from_aif(self, mfc_forty_f):
        """The MD&A exhibit must be a different attachment from the AIF."""
        aif = mfc_forty_f.aif_attachment
        mda = mfc_forty_f.mda_attachment
        assert aif is not None
        assert mda is not None
        assert str(aif.url) != str(mda.url)

    @pytest.mark.network
    def test_mda_html_not_empty(self, mfc_forty_f):
        """The MD&A HTML should be a substantial document."""
        html = mfc_forty_f.mda_html
        assert html is not None
        assert len(html) > 10_000

    @pytest.mark.network
    def test_mda_text_contains_mda_headings(self, mfc_forty_f):
        """The MD&A text should contain characteristic MD&A headings."""
        text = mfc_forty_f.mda_text
        assert text is not None
        upper = text.upper()
        assert 'MANAGEMENT' in upper
        assert 'DISCUSSION' in upper or 'ANALYSIS' in upper

    @pytest.mark.network
    def test_shop_has_no_separate_mda(self, shop_forty_f):
        """SHOP does not file a separate MD&A — returns None gracefully."""
        assert shop_forty_f.mda_attachment is None
        assert shop_forty_f.mda_html is None
        assert shop_forty_f.mda_text is None


class TestMDADisplay:

    @pytest.mark.network
    def test_repr_contains_mda_line(self, mfc_forty_f):
        r = repr(mfc_forty_f)
        assert 'MD&A' in r

    @pytest.mark.network
    def test_to_context_shows_mda_status(self, mfc_forty_f):
        ctx = mfc_forty_f.to_context('minimal')
        assert 'MD&A: found' in ctx

    @pytest.mark.network
    def test_to_context_shows_mda_not_found(self, shop_forty_f):
        ctx = shop_forty_f.to_context('minimal')
        assert 'MD&A: not found' in ctx

    @pytest.mark.network
    def test_to_context_lists_mda_properties(self, mfc_forty_f):
        ctx = mfc_forty_f.to_context()
        assert '.mda_text' in ctx
        assert '.mda_html' in ctx
