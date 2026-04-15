"""
Fast (no-network) verification for recently added modules:
  - edgar/search/grep.py   (_grep_text, GrepMatch, GrepResult)
  - edgar/search/efts.py   (EFTSResult, EFTSSearch)
  - edgar/proxy/models.py  (classify_proxy_tier, form-set constants)
  - edgar/proxy/season.py  (_base_form)
"""
import pytest

# ---------------------------------------------------------------------------
# _grep_text — pure function, zero I/O
# ---------------------------------------------------------------------------

from edgar.search.grep import GrepMatch, GrepResult, _grep_text


class TestGrepText:
    def test_basic_match_returns_one_result(self):
        matches = _grep_text("The revenue was $100M this quarter.", "revenue", "doc1")
        assert len(matches) == 1
        assert matches[0].location == "doc1"
        assert matches[0].match == "revenue"

    def test_case_insensitive_match(self):
        # Documented behaviour: always case-insensitive
        matches = _grep_text("Revenue grew 12% year-over-year.", "revenue", "doc1")
        assert len(matches) == 1
        assert matches[0].match == "Revenue"

    def test_multiple_matches_in_same_text(self):
        text = "revenue is up; total revenue exceeded expectations; revenue guidance raised"
        matches = _grep_text(text, "revenue", "sec_filing")
        assert len(matches) == 3

    def test_no_match_returns_empty_list(self):
        matches = _grep_text("Cash and equivalents were stable.", "revenue", "doc1")
        assert matches == []

    def test_empty_text_returns_empty_list(self):
        assert _grep_text("", "revenue", "doc1") == []

    def test_empty_pattern_returns_empty_list(self):
        assert _grep_text("Some text here.", "", "doc1") == []

    def test_context_contains_surrounding_text(self):
        text = "We reported strong revenue growth in Q4."
        matches = _grep_text(text, "revenue", "doc1")
        assert "revenue" in matches[0].context.lower()
        # Context should include words before and after the match
        assert "reported" in matches[0].context or "strong" in matches[0].context

    def test_context_prefix_ellipsis_when_truncated(self):
        # Place the match far enough from the start that the context window is cut
        prefix = "A" * 200  # 200 chars before match
        text = prefix + " revenue " + "B" * 200
        matches = _grep_text(text, "revenue", "doc1", context_chars=50)
        assert matches[0].context.startswith("...")

    def test_context_suffix_ellipsis_when_truncated(self):
        suffix = "Z" * 200  # 200 chars after match
        text = "revenue " + suffix
        matches = _grep_text(text, "revenue", "doc1", context_chars=50)
        assert matches[0].context.endswith("...")

    def test_no_ellipsis_when_match_at_start(self):
        text = "revenue is the key metric."
        matches = _grep_text(text, "revenue", "doc1")
        assert not matches[0].context.startswith("...")

    def test_regex_mode_date_pattern(self):
        matches = _grep_text(
            "filed 10-K on 2025-01-15 for period ending 2024-12-31",
            r"\d{4}-\d{2}-\d{2}",
            "doc1",
            regex=True,
        )
        assert len(matches) == 2
        matched_values = {m.match for m in matches}
        assert "2025-01-15" in matched_values
        assert "2024-12-31" in matched_values

    def test_regex_mode_single_match(self):
        matches = _grep_text("Item 1A. Risk Factors", r"Item\s+\d+[A-Z]?\.", "doc1", regex=True)
        assert len(matches) == 1
        assert matches[0].match == "Item 1A."

    def test_invalid_regex_returns_empty_not_crash(self):
        # An invalid regex pattern must not raise — it returns []
        matches = _grep_text("some text", r"[unclosed", "doc1", regex=True)
        assert matches == []

    def test_location_preserved_on_each_match(self):
        matches = _grep_text("risk risk risk", "risk", "EX-21.1")
        assert all(m.location == "EX-21.1" for m in matches)


# ---------------------------------------------------------------------------
# GrepMatch
# ---------------------------------------------------------------------------

class TestGrepMatch:
    def test_repr_truncates_long_context(self):
        long_ctx = "x" * 200
        gm = GrepMatch(location="primary", match="risk", context=long_ctx)
        r = repr(gm)
        # repr context is capped at 80 chars total in context portion → ends with "..."
        assert r.endswith("...")
        assert len(r) < 200

    def test_repr_short_context_no_truncation(self):
        gm = GrepMatch(location="Note 3", match="risk", context="minimal risk context")
        assert "..." not in repr(gm)

    def test_str_uses_full_context(self):
        long_ctx = "y" * 200
        gm = GrepMatch(location="primary", match="risk", context=long_ctx)
        assert long_ctx in str(gm)


# ---------------------------------------------------------------------------
# GrepResult
# ---------------------------------------------------------------------------

class TestGrepResult:
    def _make_result(self, n: int) -> GrepResult:
        matches = [
            GrepMatch(location=f"loc{i}", match="revenue", context=f"context {i}")
            for i in range(n)
        ]
        return GrepResult(pattern="revenue", matches=matches)

    def test_len(self):
        gr = self._make_result(3)
        assert len(gr) == 3

    def test_bool_true_when_has_matches(self):
        assert bool(self._make_result(1)) is True

    def test_bool_false_when_empty(self):
        assert bool(self._make_result(0)) is False

    def test_iter_yields_all_matches(self):
        gr = self._make_result(4)
        items = list(gr)
        assert len(items) == 4
        assert all(isinstance(m, GrepMatch) for m in items)

    def test_getitem(self):
        gr = self._make_result(3)
        assert gr[0].location == "loc0"
        assert gr[2].location == "loc2"

    def test_repr_empty(self):
        gr = self._make_result(0)
        assert repr(gr) == "GrepResult('revenue', 0 matches)"

    def test_repr_with_matches(self):
        gr = self._make_result(5)
        assert repr(gr) == "GrepResult('revenue', 5 matches)"

    def test_to_context_minimal(self):
        gr = self._make_result(2)
        ctx = gr.to_context(detail='minimal')
        assert "2 matches" in ctx
        assert "revenue" in ctx

    def test_to_context_standard(self):
        gr = self._make_result(3)
        ctx = gr.to_context(detail='standard')
        assert "3 matches" in ctx
        # Each match location should appear
        assert "loc0" in ctx

    def test_to_context_full_shows_all(self):
        gr = self._make_result(15)
        ctx = gr.to_context(detail='full')
        # Full detail shows all 15 items (no truncation)
        assert "loc14" in ctx

    def test_to_context_standard_caps_at_ten(self):
        gr = self._make_result(15)
        ctx = gr.to_context(detail='standard')
        # Standard caps display at 10; loc10 and beyond are in the "more" note
        assert "loc9" in ctx
        assert "5 more matches" in ctx

    def test_to_context_empty(self):
        gr = self._make_result(0)
        ctx = gr.to_context()
        assert "0 matches" in ctx

    def test_str_delegates_to_to_context(self):
        gr = self._make_result(2)
        assert str(gr) == gr.to_context()


# ---------------------------------------------------------------------------
# EFTSResult and EFTSSearch
# ---------------------------------------------------------------------------

from edgar.search.efts import EFTSResult, EFTSSearch


def _make_result(**kwargs) -> EFTSResult:
    defaults = dict(
        accession_number="0001234567-25-000001",
        form="10-K",
        filed="2025-01-15",
        company="Apple Inc.",
        cik="320193",
        score=1.5,
    )
    defaults.update(kwargs)
    return EFTSResult(**defaults)


def _make_search(results=None, total=None, query="test") -> EFTSSearch:
    if results is None:
        results = [_make_result()]
    if total is None:
        total = len(results)
    return EFTSSearch(query=query, total=total, results=results)


class TestEFTSResult:
    def test_repr_contains_form_and_company(self):
        r = _make_result()
        text = repr(r)
        assert "10-K" in text
        assert "Apple Inc." in text

    def test_repr_contains_score(self):
        r = _make_result(score=7.3)
        assert "7.3" in repr(r)

    def test_repr_omits_score_when_zero(self):
        r = _make_result(score=0.0)
        # Score 0.0 is falsy — should not appear in repr
        assert "0.0" not in repr(r)

    def test_repr_omits_file_type_when_none(self):
        r = _make_result(file_type=None)
        text = repr(r)
        assert "None" not in text

    def test_repr_includes_file_type_when_set(self):
        r = _make_result(file_type="EX-10.1")
        assert "EX-10.1" in repr(r)

    def test_optional_fields_default_to_none(self):
        r = EFTSResult(accession_number="0001-25-000001", form="8-K", filed="2025-03-01")
        assert r.company is None
        assert r.cik is None
        assert r.period is None
        assert r.score == 0.0

    def test_items_defaults_to_empty_list(self):
        r = EFTSResult(accession_number="0001-25-000001", form="8-K", filed="2025-03-01")
        assert r.items == []


class TestEFTSSearch:
    def test_len(self):
        s = _make_search(results=[_make_result(), _make_result(form="10-Q")])
        assert len(s) == 2

    def test_bool_true_when_results_present(self):
        assert bool(_make_search()) is True

    def test_bool_false_via_empty_property(self):
        s = _make_search(results=[], total=0)
        assert s.empty is True
        # __len__ == 0 → falsy
        assert not s

    def test_iter_yields_efts_results(self):
        s = _make_search(results=[_make_result(), _make_result(form="10-Q")])
        items = list(s)
        assert len(items) == 2
        assert all(isinstance(r, EFTSResult) for r in items)

    def test_getitem_by_index(self):
        r0 = _make_result(form="10-K")
        r1 = _make_result(form="10-Q")
        s = _make_search(results=[r0, r1])
        assert s[0].form == "10-K"
        assert s[1].form == "10-Q"

    def test_getitem_by_slice_returns_efts_search(self):
        results = [_make_result(form=f"10-K") for _ in range(5)]
        s = _make_search(results=results, total=5)
        sliced = s[:3]
        assert isinstance(sliced, EFTSSearch)
        assert len(sliced) == 3

    def test_repr_shows_query_and_totals(self):
        s = _make_search(query="going concern", total=42)
        text = repr(s)
        assert "going concern" in text
        assert "42" in text

    def test_head_returns_first_n(self):
        results = [_make_result(filed=f"2025-0{i+1}-01") for i in range(5)]
        s = _make_search(results=results, total=5)
        top2 = s.head(2)
        assert len(top2) == 2
        assert top2[0].filed == "2025-01-01"

    def test_tail_returns_last_n(self):
        results = [_make_result(filed=f"2025-0{i+1}-01") for i in range(5)]
        s = _make_search(results=results, total=5)
        last2 = s.tail(2)
        assert len(last2) == 2
        assert last2[-1].filed == "2025-05-01"

    def test_filter_by_form(self):
        results = [
            _make_result(form="10-K"),
            _make_result(form="10-Q"),
            _make_result(form="10-K"),
        ]
        s = _make_search(results=results)
        filtered = s.filter(form="10-K")
        assert len(filtered) == 2
        assert all(r.form == "10-K" for r in filtered)

    def test_filter_by_min_score(self):
        results = [
            _make_result(score=1.0),
            _make_result(score=5.0),
            _make_result(score=3.0),
        ]
        s = _make_search(results=results)
        filtered = s.filter(min_score=3.0)
        assert len(filtered) == 2
        assert all(r.score >= 3.0 for r in filtered)

    def test_filter_by_date_range(self):
        results = [
            _make_result(filed="2024-06-01"),
            _make_result(filed="2025-01-15"),
            _make_result(filed="2025-06-30"),
        ]
        s = _make_search(results=results)
        filtered = s.filter(start_date="2025-01-01", end_date="2025-03-31")
        assert len(filtered) == 1
        assert filtered[0].filed == "2025-01-15"

    def test_sort_by_score_descending(self):
        results = [
            _make_result(score=1.0),
            _make_result(score=5.0),
            _make_result(score=3.0),
        ]
        s = _make_search(results=results)
        sorted_s = s.sort_by("score", reverse=True)
        scores = [r.score for r in sorted_s]
        assert scores == [5.0, 3.0, 1.0]

    def test_sort_by_unknown_field_raises(self):
        s = _make_search()
        with pytest.raises(ValueError, match="Unknown sort field"):
            s.sort_by("banana")

    def test_to_context_minimal(self):
        s = _make_search(query="revenue risk", total=100)
        ctx = s.to_context(detail='minimal')
        assert "revenue risk" in ctx
        assert "100" in ctx

    def test_to_context_standard(self):
        s = _make_search(query="revenue risk", total=1)
        ctx = s.to_context(detail='standard')
        assert "revenue risk" in ctx
        assert "Apple Inc." in ctx

    def test_str_delegates_to_to_context(self):
        s = _make_search(query="going concern")
        assert str(s) == s.to_context()

    def test_empty_property_true_when_no_results(self):
        s = EFTSSearch(query="x", total=0, results=[])
        assert s.empty is True

    def test_empty_property_false_when_results_present(self):
        s = _make_search()
        assert s.empty is False


# ---------------------------------------------------------------------------
# classify_proxy_tier — proxy/models.py
# ---------------------------------------------------------------------------

from edgar.proxy.models import (
    ANCHOR_FORMS,
    CONTEST_INDICATOR_FORMS,
    DISSIDENT_ONLY_FORMS,
    EXEMPT_SOLICITATION_FORMS,
    PRELIMINARY_FORMS,
    PROXY_FORMS,
    SUPPLEMENTAL_FORMS,
    classify_proxy_tier,
)


class TestClassifyProxyTier:
    def test_def14a_is_tier_1(self):
        assert classify_proxy_tier("DEF 14A") == 1

    def test_defr14a_is_tier_1(self):
        assert classify_proxy_tier("DEFR14A") == 1

    def test_defm14a_is_tier_1(self):
        assert classify_proxy_tier("DEFM14A") == 1

    def test_defc14a_is_tier_2(self):
        assert classify_proxy_tier("DEFC14A") == 2

    def test_defn14a_is_tier_2(self):
        assert classify_proxy_tier("DEFN14A") == 2

    def test_pre14a_is_tier_3(self):
        assert classify_proxy_tier("PRE 14A") == 3

    def test_prec14a_is_tier_3(self):
        assert classify_proxy_tier("PREC14A") == 3

    def test_defa14a_is_tier_4(self):
        assert classify_proxy_tier("DEFA14A") == 4

    def test_dfan14a_is_tier_4(self):
        assert classify_proxy_tier("DFAN14A") == 4

    def test_px14a6g_is_tier_5(self):
        assert classify_proxy_tier("PX14A6G") == 5

    def test_px14a6n_is_tier_5(self):
        assert classify_proxy_tier("PX14A6N") == 5

    def test_amendment_strips_slash_a_suffix(self):
        # DEF 14A/A should behave the same as DEF 14A
        assert classify_proxy_tier("DEF 14A/A") == 1
        assert classify_proxy_tier("DEFA14A/A") == 4
        assert classify_proxy_tier("PRE 14A/A") == 3


class TestFormSetConstants:
    def test_anchor_forms_contains_def14a(self):
        assert "DEF 14A" in ANCHOR_FORMS

    def test_anchor_forms_contains_defc14a(self):
        assert "DEFC14A" in ANCHOR_FORMS

    def test_anchor_forms_is_set(self):
        assert isinstance(ANCHOR_FORMS, set)

    def test_contest_indicator_forms_contains_dfan14a(self):
        assert "DFAN14A" in CONTEST_INDICATOR_FORMS

    def test_contest_indicator_forms_contains_defc14a(self):
        assert "DEFC14A" in CONTEST_INDICATOR_FORMS

    def test_dissident_only_forms_subset_of_contest_indicators(self):
        # Every dissident-only form must also be a contest indicator
        assert DISSIDENT_ONLY_FORMS.issubset(CONTEST_INDICATOR_FORMS)

    def test_proxy_forms_is_list(self):
        assert isinstance(PROXY_FORMS, list)

    def test_proxy_forms_contains_def14a(self):
        assert "DEF 14A" in PROXY_FORMS

    def test_proxy_forms_contains_dissident_forms(self):
        assert "DFAN14A" in PROXY_FORMS
        assert "DEFN14A" in PROXY_FORMS

    def test_exempt_solicitation_forms(self):
        assert "PX14A6G" in EXEMPT_SOLICITATION_FORMS
        assert "PX14A6N" in EXEMPT_SOLICITATION_FORMS

    def test_preliminary_forms(self):
        assert "PRE 14A" in PRELIMINARY_FORMS
        assert "PREC14A" in PRELIMINARY_FORMS


# ---------------------------------------------------------------------------
# _base_form — proxy/season.py
# ---------------------------------------------------------------------------

from edgar.proxy.season import _base_form


class TestBaseForm:
    def test_def14a_unchanged(self):
        assert _base_form("DEF 14A") == "DEF 14A"

    def test_def14a_amendment_stripped(self):
        assert _base_form("DEF 14A/A") == "DEF 14A"

    def test_defa14a_amendment_stripped(self):
        assert _base_form("DEFA14A/A") == "DEFA14A"

    def test_dfan14a_unchanged(self):
        assert _base_form("DFAN14A") == "DFAN14A"

    def test_prec14a_amendment_stripped(self):
        assert _base_form("PREC14A/A") == "PREC14A"


# ---------------------------------------------------------------------------
# edgar/proxy/contest.py  (_strip_amendment, _normalize_cik, ProxyContest)
# ---------------------------------------------------------------------------

from edgar.proxy.contest import _strip_amendment, _normalize_cik, ProxyContest
from edgar.proxy.models import SeasonFiling


class TestStripAmendment:

    def test_no_amendment(self):
        assert _strip_amendment("DEF 14A") == "DEF 14A"

    def test_strip_slash_a(self):
        assert _strip_amendment("DEF 14A/A") == "DEF 14A"

    def test_strip_concatenated(self):
        assert _strip_amendment("DEFA14A/A") == "DEFA14A"

    def test_strip_defc(self):
        assert _strip_amendment("DEFC14A/A") == "DEFC14A"


class TestNormalizeCik:

    def test_int_passthrough(self):
        assert _normalize_cik(320193) == 320193

    def test_string_int(self):
        assert _normalize_cik("320193") == 320193

    def test_zero_padded_string(self):
        assert _normalize_cik("0000320193") == 320193

    def test_none_returns_none(self):
        assert _normalize_cik(None) is None

    def test_garbage_returns_none(self):
        assert _normalize_cik("not-a-number") is None

    def test_all_zeros(self):
        assert _normalize_cik("0000") == 0

    def test_string_zero(self):
        assert _normalize_cik("0") == 0


class TestProxyContestWithMocks:
    """Test ProxyContest using mock filings to avoid network calls."""

    @staticmethod
    def _make_mock_filing(form, filing_date, accession_no, filer_cik=None, filer_name=None):
        """Create a minimal mock filing for contest tests."""
        class MockCompanyInfo:
            def __init__(self, cik, name):
                self.cik = cik
                self.name = name

        class MockFiler:
            def __init__(self, cik, name):
                self.company_information = MockCompanyInfo(cik, name)

        class MockHeader:
            def __init__(self, filers):
                self.filers = filers
                self.subject_companies = []

        class MockFiling:
            def __init__(self, form_, date_, acc_, header_):
                self.form = form_
                self.filing_date = date_
                self.accession_no = acc_
                self.header = header_
                self.file_number = None

        filers = [MockFiler(filer_cik, filer_name)] if filer_cik else []
        header = MockHeader(filers)
        return MockFiling(form, filing_date, accession_no, header)

    def _make_contest(self, filings):
        return ProxyContest(
            company_name="Test Corp",
            company_cik="100",
            contest_filings=filings,
        )

    def test_is_contested_always_true(self):
        f = self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund")
        contest = self._make_contest([f])
        assert contest.is_contested is True

    def test_company_name(self):
        f = self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund")
        contest = self._make_contest([f])
        assert contest.company_name == "Test Corp"

    def test_num_filings(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        assert contest.num_filings == 2

    def test_dissidents_identified(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        assert "Activist Fund" in contest.dissidents

    def test_management_not_in_dissidents(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        assert "Test Corp" not in contest.dissidents

    def test_parties_dict(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        parties = contest.parties
        assert parties["Activist Fund"] == "dissident"
        assert parties["Test Corp"] == "management"

    def test_is_settled_when_no_defc14a_from_management(self):
        # Only dissident filed DFAN14A; management used standard DEF 14A
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEF 14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        assert contest.is_settled is True

    def test_not_settled_when_management_filed_defc14a(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        assert contest.is_settled is False

    def test_timeline_dataframe(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        df = contest.timeline
        assert len(df) == 2
        assert list(df.columns) == ['date', 'form', 'party', 'party_type', 'tier', 'accession_no']
        # Sorted by date
        assert df.iloc[0]['date'] == '2025-03-01'
        assert df.iloc[1]['date'] == '2025-03-15'

    def test_str_output(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
        ]
        contest = self._make_contest(filings)
        s = str(contest)
        assert "Test Corp" in s
        assert "Activist Fund" in s

    def test_to_context_minimal(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
        ]
        contest = self._make_contest(filings)
        ctx = contest.to_context(detail='minimal')
        assert "PROXY CONTEST" in ctx
        assert "Activist Fund" in ctx

    def test_to_context_full_includes_timeline(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
        ]
        contest = self._make_contest(filings)
        ctx = contest.to_context(detail='full')
        assert "TIMELINE" in ctx
        assert "2025-03-01" in ctx

    def test_management_filings_property(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        mgmt = contest.management_filings
        assert len(mgmt) == 1
        assert mgmt[0].party_name == "Test Corp"

    def test_dissident_filings_property(self):
        filings = [
            self._make_mock_filing("DFAN14A", "2025-03-01", "acc-001", "200", "Activist Fund"),
            self._make_mock_filing("DEFC14A", "2025-03-15", "acc-002", "100", "Test Corp"),
        ]
        contest = self._make_contest(filings)
        diss = contest.dissident_filings
        assert len(diss) == 1
        assert diss[0].party_name == "Activist Fund"
