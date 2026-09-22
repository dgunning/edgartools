"""
Tests for 8-K improvements (edgartools-79gv).

Verifies: content_type, is_amendment, get_exhibit, get_exhibits,
has_press_release behavioral change, missing structure items,
and to_context improvements.
"""
import pytest
from edgar import Filing
from edgar.company_reports import EightK
from edgar.company_reports.current_report import CurrentReport


# ---------------------------------------------------------------------------
# Fixtures — representative filings from the 8-K research
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adobe_earnings():
    """Adobe 8-K with Item 2.02 earnings release."""
    f = Filing(form='8-K', filing_date='2023-03-15', company='ADOBE INC.',
               cik=796343, accession_no='0000796343-23-000044')
    return f.obj()


@pytest.fixture(scope="module")
def acelrx_director_vote():
    """AcelRx 8-K with Items 5.02 + 5.07 (director change + vote)."""
    f = Filing(form='8-K', filing_date='2023-10-10',
               company='ACELRX PHARMACEUTICALS INC', cik=1427925,
               accession_no='0001437749-23-027971')
    return f.obj()


@pytest.fixture(scope="module")
def aar_item801():
    """AAR Corp 8-K with Items 7.01, 8.01, 9.01."""
    f = Filing(form='8-K', filing_date='2023-03-20', company='AAR CORP',
               cik=1750, accession_no='0001104659-23-034265')
    return f.obj()


@pytest.fixture(scope="module")
def fourfront_director():
    """4Front Ventures 8-K with only Item 5.02."""
    f = Filing(form='8-K', filing_date='2023-03-20',
               company='4Front Ventures Corp.', cik=1783875,
               accession_no='0001279569-23-000330')
    return f.obj()


@pytest.fixture(scope="module")
def afc_gamma_regfd():
    """AFC Gamma 8-K with Items 5.02, 7.01, 9.01 (Reg FD press release)."""
    f = Filing(form='8-K', filing_date='2023-03-20',
               company='AFC Gamma, Inc.', cik=1822523,
               accession_no='0001829126-23-002149')
    return f.obj()


# ---------------------------------------------------------------------------
# Structure dict completeness
# ---------------------------------------------------------------------------

class TestStructureDict:

    def test_item_801_in_structure(self):
        """Item 8.01 (Other Events) must be in structure dict."""
        item = CurrentReport.structure.get_item("ITEM 8.01")
        assert item is not None
        assert item["Title"] == "Other Events"

    def test_item_105_in_structure(self):
        """Item 1.05 (Cybersecurity) must be in structure dict."""
        item = CurrentReport.structure.get_item("ITEM 1.05")
        assert item is not None
        assert item["Title"] == "Material Cybersecurity Incidents"

    def test_item_104_in_structure(self):
        """Item 1.04 (Mine Safety) must be in structure dict."""
        item = CurrentReport.structure.get_item("ITEM 1.04")
        assert item is not None
        assert item["Title"] == "Mine Safety Disclosures"

    def test_item_701_in_structure(self):
        """Item 7.01 (Regulation FD) must be in structure dict."""
        item = CurrentReport.structure.get_item("ITEM 7.01")
        assert item is not None
        assert item["Title"] == "Regulation FD Disclosure"

    def test_all_sections_1_through_9_have_at_least_one_item(self):
        """Every section number 1-9 should have at least one item."""
        structure = CurrentReport.structure.structure
        sections_found = set()
        for key in structure:
            # "ITEM 2.02" → "2"
            section = key.replace("ITEM ", "").split(".")[0]
            sections_found.add(section)
        for s in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            assert s in sections_found, f"Section {s} has no items in structure dict"


# ---------------------------------------------------------------------------
# content_type
# ---------------------------------------------------------------------------

class TestContentType:

    def test_earnings(self, adobe_earnings):
        assert adobe_earnings.content_type == 'earnings'

    def test_shareholder_vote(self, acelrx_director_vote):
        """5.02 + 5.07 → shareholder_vote wins (higher priority)."""
        assert acelrx_director_vote.content_type == 'shareholder_vote'

    def test_director_change(self, fourfront_director):
        assert fourfront_director.content_type == 'director_change'

    def test_regulation_fd(self, afc_gamma_regfd):
        """5.02 + 7.01 + 9.01 → director_change wins over regulation_fd."""
        # 5.02 is checked before 7.01 in priority order
        assert afc_gamma_regfd.content_type == 'director_change'

    def test_other_for_item_801(self, aar_item801):
        """7.01 + 8.01 + 9.01 → regulation_fd (7.01 takes precedence)."""
        assert aar_item801.content_type == 'regulation_fd'



# ---------------------------------------------------------------------------
# is_amendment
# ---------------------------------------------------------------------------

class TestIsAmendment:

    def test_regular_8k_is_not_amendment(self, adobe_earnings):
        assert adobe_earnings.is_amendment is False

    def test_8ka_is_amendment(self):
        """An 8-K/A filing should return is_amendment=True."""
        f = Filing(form='8-K/A', filing_date='2013-01-04',
                   company='Cactus Ventures, Inc.', cik=1388320,
                   accession_no='0001213900-13-000029')
        eightk = f.obj()
        assert eightk.is_amendment is True


# ---------------------------------------------------------------------------
# get_exhibit / get_exhibits
# ---------------------------------------------------------------------------

class TestExhibitAccess:

    def test_get_exhibit_returns_attachment(self, adobe_earnings):
        """Adobe earnings has EX-99.1."""
        exhibit = adobe_earnings.get_exhibit('EX-99.1')
        assert exhibit is not None
        assert exhibit.document_type == 'EX-99.1'

    def test_get_exhibit_returns_none_for_missing(self, adobe_earnings):
        assert adobe_earnings.get_exhibit('EX-16.1') is None

    def test_get_exhibits_returns_list(self, adobe_earnings):
        exhibits = adobe_earnings.get_exhibits()
        assert isinstance(exhibits, list)
        assert len(exhibits) > 0

    def test_get_exhibits_with_prefix_filter(self, adobe_earnings):
        ex99 = adobe_earnings.get_exhibits(prefix='EX-99')
        assert all(att.document_type.startswith('EX-99') for att in ex99)

    def test_get_exhibits_excludes_xbrl_infrastructure(self, adobe_earnings):
        """XBRL infrastructure files (EX-101.*) should be excluded."""
        exhibits = adobe_earnings.get_exhibits()
        for att in exhibits:
            assert not att.document_type.startswith('EX-101'), \
                f"XBRL file {att.document_type} should be excluded"

    def test_get_exhibits_excludes_primary_8k(self, adobe_earnings):
        """The primary 8-K document itself should be excluded."""
        exhibits = adobe_earnings.get_exhibits()
        for att in exhibits:
            assert att.document_type not in ('8-K', '8-K/A'), \
                f"Primary doc type {att.document_type} should be excluded"


# ---------------------------------------------------------------------------
# has_press_release behavioral change
# ---------------------------------------------------------------------------

class TestHasPressRelease:

    def test_true_for_earnings_with_ex99(self, adobe_earnings):
        """Item 2.02 + EX-99.1 → has_press_release=True."""
        assert '2.02' in str(adobe_earnings.items)
        assert adobe_earnings.has_press_release is True

    def test_false_for_regfd_with_ex99(self, afc_gamma_regfd):
        """Item 7.01 with EX-99 but no Item 2.02 → has_press_release=False."""
        items_str = str(afc_gamma_regfd.items)
        assert '7.01' in items_str
        assert '2.02' not in items_str
        assert afc_gamma_regfd.has_press_release is False

    def test_false_for_director_change_no_ex99(self, fourfront_director):
        """Item 5.02 only, no EX-99 → has_press_release=False."""
        assert fourfront_director.has_press_release is False

    def test_press_releases_still_returns_attachments_for_regfd(self, afc_gamma_regfd):
        """The press_releases property itself still returns EX-99 attachments
        regardless of item type — only the boolean flag changed."""
        # press_releases returns attachments matching EX-99 types
        pr = afc_gamma_regfd.press_releases
        # This filing has EX-99.1 as a press release attachment
        if pr is not None:
            assert len(pr) > 0


# ---------------------------------------------------------------------------
# to_context improvements
# ---------------------------------------------------------------------------

class TestToContext:

    def test_minimal_includes_content_type(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='minimal')
        assert 'Content Type: earnings' in ctx

    def test_minimal_includes_item_titles(self, aar_item801):
        """Item 8.01 should show 'Other Events' title, not blank."""
        ctx = aar_item801.to_context(detail='minimal')
        assert 'Other Events' in ctx

    def test_standard_shows_earnings_actions_for_earnings(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='standard')
        assert '.earnings' in ctx
        assert '.income_statement' in ctx
        assert '.press_releases' in ctx

    def test_standard_hides_earnings_actions_for_non_earnings(self, fourfront_director):
        ctx = fourfront_director.to_context(detail='standard')
        assert '.earnings' not in ctx
        assert '.income_statement' not in ctx
        assert '.press_releases' not in ctx

    def test_standard_shows_get_exhibit(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='standard')
        assert '.get_exhibit' in ctx

    def test_standard_shows_content_type_action(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='standard')
        assert '.content_type' in ctx

    def test_amendment_shown_for_8ka(self):
        f = Filing(form='8-K/A', filing_date='2013-01-04',
                   company='Cactus Ventures, Inc.', cik=1388320,
                   accession_no='0001213900-13-000029')
        eightk = f.obj()
        ctx = eightk.to_context(detail='minimal')
        assert 'Amendment: Yes (8-K/A)' in ctx

    def test_amendment_not_shown_for_regular_8k(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='minimal')
        assert 'Amendment' not in ctx

    def test_full_includes_exhibits(self, adobe_earnings):
        ctx = adobe_earnings.to_context(detail='full')
        assert 'EXHIBITS:' in ctx
