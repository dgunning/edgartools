"""
Verification tests for ProxySeason and ProxyContest.

Tests validated against real SEC data from:
- AAPL (clean negative — no contest)
- IMKTA (positive — Summer Road LLC contest 2026)
"""
import pytest

from edgar.proxy.models import (
    ANCHOR_FORMS,
    CONTEST_INDICATOR_FORMS,
    DISSIDENT_ONLY_FORMS,
    SUPPLEMENTAL_FORMS,
    PRELIMINARY_FORMS,
    EXEMPT_SOLICITATION_FORMS,
    classify_proxy_tier,
)


# ── Unit tests (no network) ──────────────────────────────────────────

class TestClassifyProxyTier:
    """Tier classification for proxy form types."""

    def test_full_proxy_forms(self):
        assert classify_proxy_tier('DEF 14A') == 1
        assert classify_proxy_tier('DEFR14A') == 1
        assert classify_proxy_tier('DEFM14A') == 1

    def test_contested_definitive_forms(self):
        assert classify_proxy_tier('DEFC14A') == 2
        assert classify_proxy_tier('DEFN14A') == 2

    def test_preliminary_forms(self):
        assert classify_proxy_tier('PRE 14A') == 3
        assert classify_proxy_tier('PREC14A') == 3
        assert classify_proxy_tier('PREM14A') == 3
        assert classify_proxy_tier('PREN14A') == 3
        assert classify_proxy_tier('PRER14A') == 3
        assert classify_proxy_tier('PRRN14A') == 3

    def test_supplemental_forms(self):
        assert classify_proxy_tier('DEFA14A') == 4
        assert classify_proxy_tier('DFAN14A') == 4
        assert classify_proxy_tier('DFRN14A') == 4

    def test_exempt_solicitation_forms(self):
        assert classify_proxy_tier('PX14A6G') == 5
        assert classify_proxy_tier('PX14A6N') == 5

    def test_amendment_suffix_stripped(self):
        assert classify_proxy_tier('DEF 14A/A') == 1
        assert classify_proxy_tier('DEFC14A/A') == 2
        assert classify_proxy_tier('PREC14A/A') == 3


class TestFormSets:
    """Verify form set definitions are consistent."""

    def test_dissident_only_is_subset_of_contest(self):
        assert DISSIDENT_ONLY_FORMS.issubset(CONTEST_INDICATOR_FORMS)

    def test_anchor_forms(self):
        assert 'DEF 14A' in ANCHOR_FORMS
        assert 'DEFC14A' in ANCHOR_FORMS
        assert len(ANCHOR_FORMS) == 2

    def test_no_overlap_supplemental_and_preliminary(self):
        assert SUPPLEMENTAL_FORMS.isdisjoint(PRELIMINARY_FORMS)

    def test_no_overlap_exempt_and_supplemental(self):
        assert EXEMPT_SOLICITATION_FORMS.isdisjoint(SUPPLEMENTAL_FORMS)


class TestCikNormalization:
    """CIK normalization handles zero-padded strings and ints."""

    def test_normalize_cik(self):
        from edgar.proxy.contest import _normalize_cik
        assert _normalize_cik('0000050493') == 50493
        assert _normalize_cik('50493') == 50493
        assert _normalize_cik(50493) == 50493
        assert _normalize_cik('0000320193') == 320193
        assert _normalize_cik(0) == 0
        assert _normalize_cik('0000000000') == 0


# ── Network tests ────────────────────────────────────────────────────

@pytest.mark.network
class TestAppleProxySeason:
    """AAPL — clean negative control (no contest)."""

    @pytest.fixture(scope='class')
    def season(self):
        from edgar import Company
        return Company('AAPL').proxy_season()

    def test_season_found(self, season):
        assert season is not None

    def test_anchor_is_def14a(self, season):
        assert season.anchor_form == 'DEF 14A'

    def test_not_contested(self, season):
        assert season.is_contested is False

    def test_contest_is_none(self, season):
        assert season.contest is None

    def test_has_filings(self, season):
        assert season.num_filings >= 1

    def test_str_representation(self, season):
        s = str(season)
        assert 'Apple' in s
        assert 'contested' not in s

    def test_to_context(self, season):
        ctx = season.to_context()
        assert 'PROXY SEASON' in ctx
        assert 'Contested: No' in ctx

    def test_proxy_returns_proxy_statement(self, season):
        proxy = season.proxy
        assert proxy is not None
        assert proxy.form == 'DEF 14A'


@pytest.mark.network
class TestImktaProxySeason:
    """IMKTA — positive control (Summer Road LLC contest)."""

    @pytest.fixture(scope='class')
    def season(self):
        from edgar import Company
        return Company('IMKTA').proxy_season()

    def test_season_found(self, season):
        assert season is not None

    def test_is_contested(self, season):
        assert season.is_contested is True

    def test_contest_exists(self, season):
        assert season.contest is not None

    def test_summer_road_is_dissident(self, season):
        assert 'SUMMER ROAD LLC' in season.contest.dissidents

    def test_no_ingles_in_dissidents(self, season):
        """Management should not appear in dissidents list."""
        for name in season.contest.dissidents:
            assert 'INGLES' not in name

    def test_contest_has_filings(self, season):
        assert season.contest.num_filings >= 7

    def test_timeline_has_correct_columns(self, season):
        tl = season.contest.timeline
        assert list(tl.columns) == ['date', 'form', 'party', 'party_type', 'tier', 'accession_no']

    def test_timeline_is_chronological(self, season):
        tl = season.contest.timeline
        dates = tl['date'].tolist()
        assert dates == sorted(dates)

    def test_management_filings_labeled_correctly(self, season):
        for sf in season.contest.management_filings:
            assert sf.party_type == 'management'
            assert 'INGLES' in sf.party_name

    def test_dissident_filings_labeled_correctly(self, season):
        for sf in season.contest.dissident_filings:
            assert sf.party_type == 'dissident'
            assert 'SUMMER ROAD' in sf.party_name

    def test_str_representation(self, season):
        s = str(season)
        assert 'contested' in s.lower()

    def test_contest_str(self, season):
        s = str(season.contest)
        assert 'SUMMER ROAD' in s

    def test_to_context_full(self, season):
        ctx = season.contest.to_context(detail='full')
        assert 'TIMELINE' in ctx
        assert 'SUMMER ROAD' in ctx

    def test_supplemental_filings(self, season):
        """DEFA14A and DFAN14A should be in supplemental."""
        supp = season.supplemental_filings
        forms = {sf.form for sf in supp}
        # Should have at least DEFA14A from management
        assert len(supp) > 0

    def test_rich_rendering_no_error(self, season):
        """Display should not raise."""
        season.__rich__()
        season.contest.__rich__()


@pytest.mark.network
class TestPreviousSeason:
    """Test accessing prior proxy seasons via index."""

    def test_previous_season(self):
        from edgar import Company
        company = Company('AAPL')
        prev = company.proxy_season(index=1)
        assert prev is not None
        # Previous season should have earlier filing date
        latest = company.proxy_season(index=0)
        assert prev.filing_date < latest.filing_date
