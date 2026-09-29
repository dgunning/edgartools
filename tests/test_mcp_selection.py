"""
Tests for the shared filing selection resolver (edgar.ai.mcp.tools.selection)
and the provenance helpers in edgar.ai.mcp.tools.base.

Fast tests use light fake company/filing objects so the selection logic —
precedence, period matching, amendment exclusion, error codes — is verified
without touching the network. Network tests pin the resolver's behaviour
against a real ARCC 10-Q (ground truth from the Phase 1 constraints doc).

Period matching uses ``report_date`` (a plain field already present in the
submissions JSON that ``get_filings()`` loads), never the ``period_of_report``
property, which downloads the entire filing submission just to read one date.
Several tests below use a fake whose ``period_of_report`` raises if it is
ever accessed, to prove that download path is never taken during selection
or listing formatting.
"""

import pytest

from edgar._filings import Filing as _Filing
from edgar.ai.mcp.tools import selection
from edgar.ai.mcp.tools.base import format_filing_summary, format_source
from edgar.ai.mcp.tools.selection import (
    FilingSelectionError,
    resolve_report_filing,
)


# =============================================================================
# Fakes
# =============================================================================


class FakeFiling(_Filing):
    """Just enough of a Filing to exercise selection and provenance.

    ``report_date`` is the field selection actually matches periods against
    (mirrors EntityFiling.report_date, sourced from the submissions JSON).
    ``period_of_report`` is kept as a plain, cheap attribute here only so
    format_source's fallback path (used when report_date is missing) can be
    exercised without a real Filing.

    Subclasses the real ``edgar._filings.Filing`` (Task Q1, P1-M3) purely so
    ``isinstance(filing, edgar._filings.Filing)`` in ``_resolve_by_accession``
    accepts it. ``Filing.__init__`` only assigns plain attributes -- no
    network access -- so calling it here is safe. ``accession_number`` is not
    set directly: it is inherited as a read-only property that reads
    ``accession_no``.
    """

    def __init__(
        self,
        *,
        accession_no="0000000000-26-000001",
        form="10-K",
        cik=1234,
        report_date="",
        period_of_report=None,
        filing_date="2026-01-01",
        company="Test Co",
        homepage_url=None,
    ):
        super().__init__(
            cik=cik, company=company, form=form, filing_date=filing_date, accession_no=accession_no
        )
        self.report_date = report_date
        self._period_of_report = period_of_report
        self._homepage_url = homepage_url or (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no}-index.html"
        )

    @property
    def period_of_report(self):
        return self._period_of_report

    @property
    def homepage_url(self):
        return self._homepage_url


class DownloadTrapFiling(FakeFiling):
    """A FakeFiling whose period_of_report raises if ever accessed.

    On the real ``Filing`` class, ``period_of_report`` is a property that
    calls ``self.sgml()``, downloading the entire filing submission. This
    fake proves a code path never takes that route: any read of
    ``period_of_report`` fails the test instead of silently succeeding.
    """

    @property
    def period_of_report(self):
        raise AssertionError(
            "period_of_report was accessed — on a real Filing this downloads "
            "the entire submission and must never happen here"
        )


class FakeCompany:
    """Just enough of a Company to exercise get_filings(form=, amendments=,
    trigger_full_load=).

    ``filings`` is what's returned regardless of trigger_full_load (stands in
    for the submissions JSON's already-loaded "recent" page). ``extra_filings``
    is only included when trigger_full_load=True (stands in for the additional
    historical pages Entity._load_older_filings() would fetch). ``full_load_calls``
    lets tests assert whether the full-history path was actually taken.
    """

    def __init__(self, cik, filings=None, extra_filings=None):
        self.cik = cik
        self.name = "Test Co"
        self._filings = filings or []
        self._extra_filings = extra_filings or []
        self.full_load_calls = 0
        self.calls = []  # every trigger_full_load value passed, in call order

    def get_filings(self, form=None, amendments=True, trigger_full_load=True):
        self.calls.append(trigger_full_load)
        pool = list(self._filings)
        if trigger_full_load:
            self.full_load_calls += 1
            pool += self._extra_filings

        def base_form_matches(f):
            return form is None or f.form.replace("/A", "") == form

        results = [f for f in pool if base_form_matches(f)]
        if not amendments:
            results = [f for f in results if not f.form.endswith("/A")]
        return results


# =============================================================================
# resolve_report_filing — precedence and selection (fast)
# =============================================================================


@pytest.mark.fast
class TestResolveReportFilingPrecedence:
    def test_accession_precedes_period(self, monkeypatch):
        """A given accession wins even when period would not have matched anything."""
        fake_filing = FakeFiling(accession_no="0000000000-26-000099", form="10-K", cik=1234)
        monkeypatch.setattr("edgar.find", lambda **kwargs: fake_filing)

        company = FakeCompany(cik=1234, filings=[fake_filing])
        result = resolve_report_filing(
            form="10-K",
            accession_number="0000000000-26-000099",
            period="1999-01-01",
            company=company,
        )

        assert result.selected_by == "accession"
        assert result.filing is fake_filing

    def test_no_selector_returns_latest(self):
        older = FakeFiling(accession_no="A1", form="10-K", filing_date="2025-01-01")
        newer = FakeFiling(accession_no="A2", form="10-K", filing_date="2026-01-01")
        company = FakeCompany(cik=1, filings=[older, newer])

        result = resolve_report_filing(form="10-K", company=company)

        assert result.selected_by == "latest"
        assert result.filing is newer


@pytest.mark.fast
class TestResolveReportFilingByPeriod:
    def test_exact_period_match(self):
        filing = FakeFiling(form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        company = FakeCompany(cik=1, filings=[filing])

        result = resolve_report_filing(form="10-Q", period="2026-06-30", company=company)

        assert result.selected_by == "period"
        assert result.filing is filing

    def test_period_not_found_lists_periods_and_does_not_select(self):
        filings = [
            FakeFiling(form="10-Q", report_date="2026-06-30", filing_date="2026-08-01"),
            FakeFiling(form="10-Q", report_date="2026-03-31", filing_date="2026-05-01"),
        ]
        company = FakeCompany(cik=1, filings=filings)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q", period="2026-01-01", company=company)

        err = exc_info.value
        assert err.error_code == "PERIOD_NOT_FOUND"
        assert err.suggestions == ["Available 10-Q periods: 2026-06-30, 2026-03-31"]

    def test_period_not_found_never_picks_nearest(self):
        """A period one day off a real filing must not silently match it."""
        filing = FakeFiling(form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        company = FakeCompany(cik=1, filings=[filing])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q", period="2026-06-29", company=company)

        assert exc_info.value.error_code == "PERIOD_NOT_FOUND"

    def test_duplicate_period_picks_latest_filed(self):
        older = FakeFiling(accession_no="A1", form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        newer = FakeFiling(accession_no="A2", form="10-Q", report_date="2026-06-30", filing_date="2026-08-15")
        company = FakeCompany(cik=1, filings=[older, newer])

        result = resolve_report_filing(form="10-Q", period="2026-06-30", company=company)

        assert result.selected_by == "period"
        assert result.filing is newer

    def test_bad_date_format_is_invalid_arguments(self):
        """Silence check: a malformed period is a useful error, not a None or a guess."""
        company = FakeCompany(cik=1, filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q", period="06-30-2026", company=company)

        assert exc_info.value.error_code == "INVALID_ARGUMENTS"

    def test_bad_calendar_date_is_invalid_arguments(self):
        company = FakeCompany(cik=1, filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q", period="2026-02-30", company=company)

        assert exc_info.value.error_code == "INVALID_ARGUMENTS"

    def test_period_excludes_amendments(self):
        """An amendment covering the same period is not reachable by period."""
        original = FakeFiling(accession_no="A1", form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        amendment = FakeFiling(accession_no="A2", form="10-Q/A", report_date="2026-06-30", filing_date="2026-09-01")
        company = FakeCompany(cik=1, filings=[original, amendment])

        result = resolve_report_filing(form="10-Q", period="2026-06-30", company=company)

        assert result.filing is original

    def test_retries_with_full_load_only_when_recent_page_misses(self):
        """Not found on the recent page triggers exactly one full-history retry,
        and the eventual match/suggestions come from the set that was actually
        searched last."""
        recent = FakeFiling(accession_no="A1", form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        older = FakeFiling(accession_no="A0", form="10-Q", report_date="2025-06-30", filing_date="2025-08-01")
        company = FakeCompany(cik=1, filings=[recent], extra_filings=[older])

        result = resolve_report_filing(form="10-Q", period="2025-06-30", company=company)

        assert result.filing is older
        assert company.full_load_calls == 1

    def test_no_full_load_retry_when_recent_page_already_matches(self):
        """A period found on the recent page never pays for the full-history load."""
        recent = FakeFiling(accession_no="A1", form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        company = FakeCompany(cik=1, filings=[recent])

        result = resolve_report_filing(form="10-Q", period="2026-06-30", company=company)

        assert result.filing is recent
        assert company.full_load_calls == 0


@pytest.mark.fast
class TestResolveReportFilingLatestExcludesAmendments:
    def test_amendment_never_wins_latest_even_when_newer(self):
        original = FakeFiling(accession_no="A1", form="10-K", filing_date="2025-01-01")
        amendment = FakeFiling(accession_no="A2", form="10-K/A", filing_date="2026-01-01")
        company = FakeCompany(cik=1, filings=[original, amendment])

        result = resolve_report_filing(form="10-K", company=company)

        assert result.selected_by == "latest"
        assert result.filing is original

    def test_no_filings_is_filing_not_found(self):
        company = FakeCompany(cik=1, filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-K", company=company)

        assert exc_info.value.error_code == "FILING_NOT_FOUND"

    def test_latest_never_triggers_full_historical_load(self):
        """The latest path never needs more than the already-loaded recent page."""
        filing = FakeFiling(accession_no="A1", form="10-K", filing_date="2026-01-01")
        company = FakeCompany(cik=1, filings=[filing], extra_filings=[FakeFiling(accession_no="A0")])

        resolve_report_filing(form="10-K", company=company)

        assert company.full_load_calls == 0

    def test_empty_recent_page_retries_with_full_load(self):
        """P1-M1: an empty recent page is not the final word -- mirrors
        _resolve_by_period and Entity.latest(). A form like 10-K405 whose only
        filings are old enough to sit outside the recent page must still be
        found via exactly one full-history retry."""
        older = FakeFiling(accession_no="A0", form="10-K405", filing_date="2001-12-21")
        company = FakeCompany(cik=1, filings=[], extra_filings=[older])

        result = resolve_report_filing(form="10-K405", company=company)

        assert result.filing is older
        assert result.selected_by == "latest"
        assert company.calls == [False, True]

    def test_still_not_found_after_full_load_retry(self):
        """A genuinely empty history still raises FILING_NOT_FOUND, after
        exactly one retry -- not an infinite/duplicate retry loop."""
        company = FakeCompany(cik=1, filings=[], extra_filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-K405", company=company)

        assert exc_info.value.error_code == "FILING_NOT_FOUND"
        assert company.calls == [False, True]

    def test_recent_page_hit_never_retries(self):
        """A match on the first page never pays for the full-history load."""
        recent = FakeFiling(accession_no="A1", form="10-K", filing_date="2026-01-01")
        company = FakeCompany(cik=1, filings=[recent])

        result = resolve_report_filing(form="10-K", company=company)

        assert result.filing is recent
        assert company.calls == [False]


@pytest.mark.fast
class TestResolveReportFilingMismatch:
    def test_accession_with_different_cik_is_selection_mismatch(self, monkeypatch):
        fake_filing = FakeFiling(cik=1234, form="10-K")
        monkeypatch.setattr("edgar.find", lambda **kwargs: fake_filing)
        other_company = FakeCompany(cik=9999)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(accession_number="0000000000-26-000099", company=other_company)

        assert exc_info.value.error_code == "SELECTION_MISMATCH"

    def test_accession_with_matching_cik_succeeds(self, monkeypatch):
        fake_filing = FakeFiling(cik=1234, form="10-K/A")
        monkeypatch.setattr("edgar.find", lambda **kwargs: fake_filing)
        same_company = FakeCompany(cik=1234)

        # Amendments are reachable only by accession number, and that path is allowed.
        result = resolve_report_filing(accession_number="0000000000-26-000099", company=same_company)

        assert result.selected_by == "accession"
        assert result.filing is fake_filing

    def test_accession_not_found_is_filing_not_found(self, monkeypatch):
        monkeypatch.setattr("edgar.find", lambda **kwargs: None)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(accession_number="0000000000-26-999999")

        assert exc_info.value.error_code == "FILING_NOT_FOUND"


@pytest.mark.fast
class TestResolveByAccessionShapeValidation:
    """P1-M3: a malformed accession_number must never reach edgar.find() as
    if it might be one -- edgar.find() dispatches on shape and can return a
    Company/Entity or CompanySearchResults for a CIK, name, or oddly-shaped
    string, which downstream code would then use as if it were a filing.
    """

    def test_a_cik_is_invalid_arguments_and_never_calls_find(self, monkeypatch):
        def _unexpected_find(**kwargs):
            raise AssertionError("find() must not be called for a malformed accession")

        monkeypatch.setattr("edgar.find", _unexpected_find)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(accession_number="1287750")

        assert exc_info.value.error_code == "INVALID_ARGUMENTS"

    def test_a_company_name_is_invalid_arguments(self, monkeypatch):
        def _unexpected_find(**kwargs):
            raise AssertionError("find() must not be called for a malformed accession")

        monkeypatch.setattr("edgar.find", _unexpected_find)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(accession_number="Apple Inc")

        assert exc_info.value.error_code == "INVALID_ARGUMENTS"

    def test_leading_and_trailing_space_is_stripped_and_still_resolves(self, monkeypatch):
        fake_filing = FakeFiling(cik=1234, form="10-K", accession_no="0000000000-26-000099")
        seen = {}

        def _find(**kwargs):
            seen.update(kwargs)
            return fake_filing

        monkeypatch.setattr("edgar.find", _find)

        result = resolve_report_filing(accession_number="  0000000000-26-000099 ")

        assert result.filing is fake_filing
        assert seen["search_id"] == "0000000000-26-000099"

    def test_18_digit_form_is_normalized_to_dashed_and_still_resolves(self, monkeypatch):
        fake_filing = FakeFiling(cik=1234, form="10-K", accession_no="0000000000-26-000099")
        seen = {}

        def _find(**kwargs):
            seen.update(kwargs)
            return fake_filing

        monkeypatch.setattr("edgar.find", _find)

        result = resolve_report_filing(accession_number="000000000026000099")

        assert result.filing is fake_filing
        assert seen["search_id"] == "0000000000-26-000099"

    def test_non_filing_result_is_filing_not_found_not_internal_error(self, monkeypatch):
        """A well-formed accession whose find() result isn't a Filing (e.g.
        edgar.find() dispatches to an Entity/CompanySearchResults for some
        other reason) must come back as FILING_NOT_FOUND, not be used as a
        filing and crash downstream with an AttributeError."""
        class _NotAFiling:
            cik = 1287750

        monkeypatch.setattr("edgar.find", lambda **kwargs: _NotAFiling())

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(accession_number="0000000000-26-000099")

        assert exc_info.value.error_code == "FILING_NOT_FOUND"


@pytest.mark.fast
class TestNonAccessionAmendmentFormRejected:
    """P1-L2: an explicit amendment form on the period or latest path used to
    be silently rewritten to the original form (edgar/filtering.py strips
    '/A' when amendments=False). Reject it instead, and point the caller at
    accession_number, where amendments are reachable."""

    def test_period_path_with_amendment_form_is_invalid_arguments(self):
        company = FakeCompany(cik=1, filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q/A", period="2026-06-30", company=company)

        err = exc_info.value
        assert err.error_code == "INVALID_ARGUMENTS"
        assert any("accession_number" in s for s in err.suggestions)

    def test_latest_path_with_amendment_form_is_invalid_arguments(self):
        company = FakeCompany(cik=1, filings=[])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-K/A", company=company)

        err = exc_info.value
        assert err.error_code == "INVALID_ARGUMENTS"
        assert any("accession_number" in s for s in err.suggestions)

    def test_accession_path_with_amendment_form_is_unaffected(self, monkeypatch):
        """The accession path is the one place an amendment form is valid --
        the /A rejection must not reach it."""
        fake_filing = FakeFiling(cik=1234, form="10-K/A")
        monkeypatch.setattr("edgar.find", lambda **kwargs: fake_filing)

        result = resolve_report_filing(
            form="10-K/A", accession_number="0000000000-26-000099", company=FakeCompany(cik=1234)
        )

        assert result.filing is fake_filing


@pytest.mark.fast
class TestResolveReportFilingCompanyResolution:
    def test_no_identifier_no_company_is_company_not_found(self):
        """Silence check: missing company/identifier is a useful error, not None."""
        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-K")

        assert exc_info.value.error_code == "COMPANY_NOT_FOUND"

    def test_unresolvable_identifier_is_company_not_found(self, monkeypatch):
        def _raise(identifier):
            raise ValueError(f"Could not find company: '{identifier}'")

        monkeypatch.setattr(selection, "resolve_company", _raise)

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(identifier="NOSUCHTICKER", form="10-K")

        assert exc_info.value.error_code == "COMPANY_NOT_FOUND"


@pytest.mark.fast
class TestFilingSelectionErrorToResponse:
    def test_to_response_shape(self):
        err = FilingSelectionError("bad period", error_code="PERIOD_NOT_FOUND", suggestions=["try this"])

        resp = err.to_response()

        assert resp.success is False
        assert resp.error == "bad period"
        assert resp.error_code == "PERIOD_NOT_FOUND"
        assert resp.suggestions == ["try this"]


# =============================================================================
# No accidental full-submission downloads (fast) — Finding 1 / Finding 2 guard
# =============================================================================


@pytest.mark.fast
class TestSelectionNeverDownloadsFullSubmissions:
    """period_of_report on a real Filing calls self.sgml(), downloading the
    entire filing submission. Matching a period against a company's whole
    filing history must never do that per filing — it has report_date already.
    DownloadTrapFiling raises if period_of_report is ever read, so any of
    these tests failing with an AssertionError (not the expected outcome)
    means that download path was taken.
    """

    def test_period_match_never_touches_period_of_report(self):
        trap = DownloadTrapFiling(form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        company = FakeCompany(cik=1, filings=[trap])

        result = resolve_report_filing(form="10-Q", period="2026-06-30", company=company)

        assert result.filing is trap

    def test_period_not_found_suggestions_never_touch_period_of_report(self):
        trap = DownloadTrapFiling(form="10-Q", report_date="2026-06-30", filing_date="2026-08-01")
        company = FakeCompany(cik=1, filings=[trap])

        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing(form="10-Q", period="2020-01-01", company=company)

        assert exc_info.value.error_code == "PERIOD_NOT_FOUND"
        assert exc_info.value.suggestions == ["Available 10-Q periods: 2026-06-30"]

    def test_latest_never_touches_period_of_report(self):
        trap = DownloadTrapFiling(form="10-K", filing_date="2026-01-01")
        company = FakeCompany(cik=1, filings=[trap])

        result = resolve_report_filing(form="10-K", company=company)

        assert result.filing is trap

    def test_format_filing_summary_never_touches_period_of_report(self):
        trap = DownloadTrapFiling(report_date="2026-06-30")

        result = format_filing_summary(trap)

        assert result["period_of_report"] == "2026-06-30"

    def test_format_source_prefers_report_date_without_touching_period_of_report(self):
        trap = DownloadTrapFiling(report_date="2026-06-30")

        result = format_source(trap)

        assert result["period_of_report"] == "2026-06-30"


# =============================================================================
# format_source (fast)
# =============================================================================


@pytest.mark.fast
class TestFormatSource:
    def test_fields_and_values(self):
        filing = FakeFiling(
            accession_no="0000000000-26-000042",
            form="10-Q",
            cik=1287750,
            report_date="2026-06-30",
            filing_date="2026-08-01",
            company="Ares Capital Corp",
            homepage_url="https://www.sec.gov/Archives/edgar/data/1287750/index.html",
        )

        result = format_source(filing, selected_by="period")

        assert result == {
            "cik": 1287750,
            "entity": "Ares Capital Corp",
            "form": "10-Q",
            "accession_number": "0000000000-26-000042",
            "period_of_report": "2026-06-30",
            "filed": "2026-08-01",
            "url": "https://www.sec.gov/Archives/edgar/data/1287750/index.html",
            "is_amendment": False,
            "selected_by": "period",
        }

    def test_omits_selected_by_when_none(self):
        filing = FakeFiling()

        result = format_source(filing)

        assert "selected_by" not in result

    def test_amendment_and_missing_period(self):
        filing = FakeFiling(form="10-K/A", report_date="", period_of_report=None)

        result = format_source(filing)

        assert result["is_amendment"] is True
        assert result["period_of_report"] is None

    def test_falls_back_to_period_of_report_when_report_date_missing(self):
        """report_date is preferred, but a filing that never carries it (e.g. a
        bare Filing from edgar.find(), not an EntityFiling) still gets a
        period_of_report in the response — at the cost of one download, on
        one already-chosen filing."""
        filing = FakeFiling(report_date="", period_of_report="2026-06-30")

        result = format_source(filing)

        assert result["period_of_report"] == "2026-06-30"


# =============================================================================
# format_filing_summary (fast) — additive period_of_report field, from
# report_date only
# =============================================================================


@pytest.mark.fast
class TestFormatFilingSummaryPeriodOfReport:
    def test_includes_period_of_report_from_report_date(self):
        filing = FakeFiling(report_date="2026-06-30")

        result = format_filing_summary(filing)

        assert result["period_of_report"] == "2026-06-30"

    def test_period_of_report_none_when_report_date_missing(self):
        filing = FakeFiling(report_date="")

        result = format_filing_summary(filing)

        assert result["period_of_report"] is None

    def test_does_not_fall_back_to_period_of_report_property(self):
        """Even when period_of_report would answer, listings must not use it."""
        filing = FakeFiling(report_date="", period_of_report="2026-06-30")

        result = format_filing_summary(filing)

        assert result["period_of_report"] is None

    def test_existing_fields_unchanged(self):
        """Additive only — the fields the rest of the codebase already relies on."""
        filing = FakeFiling(
            accession_no="0000320193-23-000077",
            form="10-K",
            cik=320193,
            filing_date="2023-11-03",
            company="Apple Inc",
        )

        result = format_filing_summary(filing)

        assert result["accession_number"] == "0000320193-23-000077"
        assert result["form"] == "10-K"
        assert result["filed"] == "2023-11-03"
        assert result["company"] == "Apple Inc"
        assert result["cik"] == "320193"


# =============================================================================
# resolve_report_filing — network + vcr (ARCC ground truth)
# =============================================================================


@pytest.mark.network
class TestResolveReportFilingARCC:
    """Ground truth measured 2026-09-28 (see the Phase 1 constraints doc):
    ARCC (CIK 1287750) 10-Q accession 0001628280-26-050307, period_of_report
    2026-06-30.
    """

    @pytest.mark.vcr
    def test_period_match_selects_ground_truth_accession(self):
        result = resolve_report_filing("ARCC", form="10-Q", period="2026-06-30")

        assert result.selected_by == "period"
        assert result.filing.accession_number == "0001628280-26-050307"

    @pytest.mark.vcr
    def test_period_off_by_one_day_is_not_found_with_correct_suggestion(self):
        with pytest.raises(FilingSelectionError) as exc_info:
            resolve_report_filing("ARCC", form="10-Q", period="2026-06-29")

        err = exc_info.value
        assert err.error_code == "PERIOD_NOT_FOUND"
        assert any("2026-06-30" in s for s in err.suggestions)
