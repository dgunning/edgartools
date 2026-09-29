"""
Tests for edgar_fund's ``bdc_portfolio`` action.

Fast tests monkeypatch filing selection (``resolve_report_filing``) and
extraction (``portfolio_investments_from_filing``) so paging, the borrower
filter, and cursor error handling are verified without touching the network.
They use the real ``PortfolioInvestment``/``PortfolioInvestments`` classes so
``data_quality``/coverage math is exercised, not re-implemented in a fake.

Network tests pin behaviour against real filings (constraints rule 7a):
- ARCC's 10-Q (CIK 1287750, accession 0001628280-26-050307) runs LIVE, no VCR
  cassette — its full submission is ~88 MB, an oversized commit.
- Princeton Capital Corp's 10-Q (CIK 845385, accession 0001213900-26-090000,
  23 holdings) is the small-BDC deterministic VCR fixture from Task 3
  (see tests/test_bdc_filing_scoped.py for how it was chosen).
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Optional

import pandas as pd
import pytest

from edgar import set_identity
from edgar.ai.mcp.tools import continuation
from edgar.ai.mcp.tools.bdc import identity as bdc_identity
from edgar.ai.mcp.tools.bdc import portfolio as bdc_portfolio_mod
from edgar.ai.mcp.tools.continuation import ResultCache
from edgar.ai.mcp.tools.bdc.identity import BdcLookup
from edgar.ai.mcp.tools.fund import edgar_fund
from edgar.ai.mcp.tools.selection import FilingSelection, FilingSelectionError
from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments


# =============================================================================
# Fakes
# =============================================================================

_UNSET = object()  # sentinel: "use the default", distinct from an explicit None


class _FakeCompany:
    def __init__(self, cik):
        self.cik = cik


class _FakeBDC:
    """Just enough of a BDCEntity for bdc_portfolio's happy path."""

    def __init__(self, cik=1287750, name="ARES CAPITAL CORP", state="MD", is_active=True, report_year=None):
        self.cik = cik
        self.name = name
        self.state = state
        self.is_active = is_active
        # None = "unknown report year" (e.g. a fake that predates P1-M5):
        # identity fields then trust `is_active` as given and never probe SEC
        # for the latest report year.
        self.report_year = report_year

    def get_company(self):
        return _FakeCompany(self.cik)


class _FakeXBRLNoSOI:
    class _Statements:
        def schedule_of_investments(self):
            return None

    statements = _Statements()


class _FakeXBRLWithSOI:
    def __init__(self, text):
        self._text = text

    class _Statements:
        def __init__(self, text):
            self._text = text

        def schedule_of_investments(self):
            return self._text  # str(text) below is identity for a plain string

    @property
    def statements(self):
        return self._Statements(self._text)


class _FakeFiling:
    """Just enough of a Filing for format_source/paging in bdc_portfolio.

    ``_load_extraction`` (edgar/ai/mcp/tools/bdc/portfolio.py) always parses XBRL itself on a cache
    miss -- threading it into ``portfolio_investments_from_filing`` and,
    if needed, the no-structured-data fallback -- so ``xbrl()`` is called
    on essentially every test here, not just the no-structured-data ones.
    It defaults to a benign ``_FakeXBRLNoSOI()`` (harmless when extraction
    itself is monkeypatched to ignore its ``xbrl`` argument) and counts
    calls via ``xbrl_call_count``, which the no-double-parse regression
    test asserts is exactly 1.
    """

    def __init__(
        self,
        *,
        accession_number="0001628280-26-050307",
        cik=1287750,
        form="10-Q",
        report_date="2026-06-30",
        filing_date="2026-08-01",
        company="ARES CAPITAL CORP",
        xbrl_result=_UNSET,
    ):
        self.accession_number = accession_number
        self.cik = cik
        self.form = form
        self.report_date = report_date
        self.filing_date = filing_date
        self.company = company
        self.homepage_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}-index.html"
        )
        self._xbrl_result = _FakeXBRLNoSOI() if xbrl_result is _UNSET else xbrl_result
        self.xbrl_call_count = 0

    def xbrl(self):
        self.xbrl_call_count += 1
        return self._xbrl_result


def _make_investment(
    identifier: str,
    company_name: str,
    investment_type: str = "First lien senior secured loan",
    **kwargs,
) -> PortfolioInvestment:
    return PortfolioInvestment(
        identifier=identifier,
        company_name=company_name,
        investment_type=investment_type,
        **kwargs,
    )


def _patch_selection(monkeypatch, filing: _FakeFiling, selected_by: str = "latest") -> list:
    """Patch filing selection; returns the list of recorded call kwargs."""
    calls = []

    def _resolve(**kwargs):
        calls.append(kwargs)
        return FilingSelection(filing=filing, selected_by=selected_by)

    monkeypatch.setattr("edgar.ai.mcp.tools.selection.resolve_report_filing", _resolve)
    return calls


def _patch_extraction(monkeypatch, investments: Optional[PortfolioInvestments]) -> list:
    """Patch holdings extraction; returns the list of filings it was called with."""
    calls = []

    def _extract(filing, include_untyped=False, xbrl=None):
        calls.append(filing)
        return investments

    monkeypatch.setattr("edgar.bdc.investments.portfolio_investments_from_filing", _extract)
    return calls


def _patch_bdc(monkeypatch, bdc: _FakeBDC = None) -> list:
    """Patch BDC identifier resolution where it is looked up
    (`edgar.ai.mcp.tools.bdc.identity.resolve_bdc`); returns the identifiers
    it was called with, so a test can prove the patch took effect."""
    calls = []

    def _resolve_bdc(identifier):
        calls.append(identifier)
        return BdcLookup(bdc=bdc or _FakeBDC())

    monkeypatch.setattr("edgar.ai.mcp.tools.bdc.identity.resolve_bdc", _resolve_bdc)
    return calls


@pytest.fixture(autouse=True)
def _isolated_caches(monkeypatch):
    """Fresh result/text caches per test so extraction-swap tests are deterministic."""
    monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
    monkeypatch.setattr(continuation, "text_cache", ResultCache(max_entries=8, max_bytes=1024 * 1024))


# =============================================================================
# Fast: borrower filter
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestBorrowerFilter:
    async def test_matches_on_identifier_when_company_name_is_wrong(self, monkeypatch):
        """A borrower filter must check `identifier` too, not just company_name.

        Regression for the bug this task fixes: an ARCC record has
        company_name='Subordinated' while identifier contains the real
        borrower name ('Ivy Hill Asset Management, L.P. | ...').
        """
        ivy_hill = _make_investment(
            identifier="Ivy Hill Asset Management, L.P. | Subordinated revolving loan",
            company_name="Subordinated",
            fair_value=Decimal("946000000"),
            cost=Decimal("946000000"),
        )
        other = _make_investment(
            identifier="Other Co - Term Loan",
            company_name="Other Co",
            fair_value=Decimal("1000"),
            cost=Decimal("1000"),
        )
        investments = PortfolioInvestments([ivy_hill, other], period="2026-06-30", extraction_method="xbrl_facts")

        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="ivy hill")

        assert result.success is True
        assert result.data["total_investments"] == 2  # full extraction, unfiltered
        assert len(result.data["investments"]) == 1
        assert result.data["investments"][0]["company_name"] == "Subordinated"
        assert result.data["investments"][0]["identifier"].startswith("Ivy Hill")
        assert result.data["filtered_totals"] == {
            "count": 1,
            "fair_value": 946000000.0,
            "cost": 946000000.0,
        }

    async def test_borrower_matching_is_case_insensitive_substring(self, monkeypatch):
        inv = _make_investment(identifier="Acme Corp - Term Loan B", company_name="Acme Corp")
        investments = PortfolioInvestments([inv], period="2026-06-30", extraction_method="xbrl_facts")

        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="ACME")

        assert result.success is True
        assert result.data["filtered_totals"]["count"] == 1


# =============================================================================
# Fast: paging
# =============================================================================


def _make_investment_batch(n: int) -> PortfolioInvestments:
    invs = [
        _make_investment(identifier=f"Company {i} - Term Loan", company_name=f"Company {i}")
        for i in range(n)
    ]
    return PortfolioInvestments(invs, period="2026-06-30", extraction_method="xbrl_facts")


@pytest.mark.fast
@pytest.mark.asyncio
class TestPaging:
    async def test_walks_all_records_exactly_once_and_ends_with_null_cursor(self, monkeypatch):
        investments = _make_investment_batch(7)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        seen_identifiers = []
        cursor = None
        pages = 0
        while True:
            result = await edgar_fund(
                action="bdc_portfolio", identifier="ARCC", limit=3, cursor=cursor
            )
            assert result.success is True
            pages += 1
            seen_identifiers.extend(rec["identifier"] for rec in result.data["investments"])
            cursor = result.data["page"]["next_cursor"]
            if cursor is None:
                break
            assert pages < 10  # guard against an infinite loop bug

        assert pages == 3  # 3 + 3 + 1
        assert len(seen_identifiers) == 7
        assert len(set(seen_identifiers)) == 7  # no duplicates
        assert set(seen_identifiers) == {f"Company {i} - Term Loan" for i in range(7)}

    async def test_next_cursor_null_when_everything_fits_on_one_page(self, monkeypatch):
        investments = _make_investment_batch(3)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=20)

        assert result.data["page"]["next_cursor"] is None
        assert result.data["page"]["remaining"] == 0
        assert "note" not in result.data


# =============================================================================
# Fast: cursor errors
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestCursorErrors:
    async def test_cursor_mismatch_when_borrower_changes_between_pages(self, monkeypatch):
        investments = _make_investment_batch(5)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        second = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", limit=2, cursor=cursor, borrower="company 1"
        )

        assert second.success is False
        assert second.error_code == "CURSOR_MISMATCH"

    async def test_cursor_stale_when_underlying_extraction_changes(self, monkeypatch):
        investments_v1 = _make_investment_batch(5)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments_v1)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        # Simulate a process restart / cache eviction: fresh cache, and the
        # extraction now returns different identifiers than it did when the
        # cursor was issued.
        monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
        investments_v2 = PortfolioInvestments(
            [_make_investment(identifier="Totally Different Co - Loan", company_name="Different")],
            period="2026-06-30",
            extraction_method="xbrl_facts",
        )
        _patch_extraction(monkeypatch, investments_v2)

        second = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2, cursor=cursor)

        assert second.success is False
        assert second.error_code == "CURSOR_STALE"

    @pytest.mark.parametrize("field,value", [
        ("fair_value", Decimal("1234567")),
        ("fair_value", None),
        ("cost", Decimal("7654321")),
        ("investment_type", "Preferred equity"),
    ])
    async def test_cursor_stale_when_evidence_changes_with_stable_identifiers(self, monkeypatch, field, value):
        holdings = list(_make_investment_batch(2))
        holdings[0] = replace(holdings[0], fair_value=Decimal("1000000"))
        investments = PortfolioInvestments(holdings, period="2026-06-30", extraction_method="xbrl_facts")
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=1)
        assert first.data["investments"][0]["fair_value"] == 1000000
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        identifiers = [inv.identifier for inv in holdings]
        holdings[0] = replace(holdings[0], **{field: value})
        assert [inv.identifier for inv in holdings] == identifiers
        monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
        _patch_extraction(monkeypatch, PortfolioInvestments(
            holdings, period="2026-06-30", extraction_method="xbrl_facts"
        ))

        second = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=1, cursor=cursor)
        assert second.success is False
        assert second.error_code == "CURSOR_STALE"

    async def test_invalid_cursor_on_garbage_input(self, monkeypatch):
        investments = _make_investment_batch(2)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", cursor="!!!not-a-real-cursor!!!"
        )

        assert result.success is False
        assert result.error_code == "INVALID_CURSOR"


# =============================================================================
# Fast: honest gaps (null vs 0) and totals
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestHonestGapsAndTotals:
    async def test_missing_numeric_fields_serialize_as_null_not_zero(self, monkeypatch):
        inv = _make_investment(
            identifier="Bare Co - Common Equity",
            company_name="Bare Co",
            investment_type="Common equity",
            fair_value=None,
            cost=None,
            principal_amount=None,
            shares=None,
            interest_rate=None,
            pik_rate=None,
            spread=None,
            percent_of_net_assets=None,
        )
        investments = PortfolioInvestments([inv], period="2026-06-30", extraction_method="xbrl_facts")

        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        record = result.data["investments"][0]
        for key in (
            "fair_value", "cost", "principal_amount", "shares",
            "interest_rate", "pik_rate", "spread", "percent_of_net_assets",
        ):
            assert record[key] is None, f"{key} should be None, got {record[key]!r}"

    async def test_filtered_totals_separate_from_full_totals(self, monkeypatch):
        matched = _make_investment(
            identifier="Match Co - Loan", company_name="Match Co", fair_value=Decimal("100"), cost=Decimal("90")
        )
        unmatched = _make_investment(
            identifier="Skip Co - Loan", company_name="Skip Co", fair_value=Decimal("500"), cost=Decimal("400")
        )
        investments = PortfolioInvestments([matched, unmatched], period="2026-06-30", extraction_method="xbrl_facts")

        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="match")

        assert result.data["total_investments"] == 2
        assert result.data["total_fair_value"] == 600.0
        assert result.data["total_cost"] == 490.0
        assert result.data["filtered_totals"] == {"count": 1, "fair_value": 100.0, "cost": 90.0}

    async def test_legacy_type_key_kept_alongside_investment_type(self, monkeypatch):
        inv = _make_investment(identifier="X - Loan", company_name="X", investment_type="First lien")
        investments = PortfolioInvestments([inv], period="2026-06-30", extraction_method="xbrl_facts")

        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        record = result.data["investments"][0]
        assert record["type"] == "First lien"
        assert record["investment_type"] == "First lien"


# =============================================================================
# Fast: silence checks / argument and selection errors
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestArgumentAndSelectionErrors:
    async def test_missing_identifier_and_accession_is_invalid_arguments(self):
        """Silence check: no identifier and no accession_number is a useful error."""
        result = await edgar_fund(action="bdc_portfolio")

        assert result.success is False
        assert result.error_code == "INVALID_ARGUMENTS"

    async def test_selection_error_is_passed_through_as_response(self, monkeypatch):
        def _raise(**kwargs):
            raise FilingSelectionError(
                "period not found", error_code="PERIOD_NOT_FOUND", suggestions=["try another period"]
            )

        monkeypatch.setattr("edgar.ai.mcp.tools.selection.resolve_report_filing", _raise)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", period="1999-01-01"
        )

        assert result.success is False
        assert result.error_code == "PERIOD_NOT_FOUND"
        assert result.suggestions == ["try another period"]

    async def test_accession_only_non_bdc_cik_is_not_a_bdc(self, monkeypatch):
        """The accession-only path now checks `lookup_bdc` (which itself
        checks multiple report years), not the old latest-report-only
        `is_bdc_cik`; a CIK absent from every checked year is still
        NOT_A_BDC."""
        filing = _FakeFiling(cik=320193, accession_number="0000320193-24-000001")
        _patch_selection(monkeypatch, filing)
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)

        result = await edgar_fund(action="bdc_portfolio", accession_number="0000320193-24-000001")

        assert result.success is False
        assert result.error_code == "NOT_A_BDC"


# =============================================================================
# Fast: no structured data fallback
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestNoStructuredData:
    async def test_no_xbrl_at_all_is_no_xbrl_error(self, monkeypatch):
        filing = _FakeFiling(accession_number="0000000000-26-000001", xbrl_result=None)
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.success is False
        assert result.error_code == "NO_XBRL"
        assert "0000000000-26-000001" in result.error

    async def test_xbrl_without_structured_holdings_falls_back_to_text(self, monkeypatch):
        soi_text = "Schedule of Investments\n" + ("Holding line.\n" * 10)
        fake_xbrl = _FakeXBRLWithSOI(soi_text)
        filing = _FakeFiling(xbrl_result=fake_xbrl)
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.success is True
        # P1-M4: the holdings exist in the text, they just weren't extracted --
        # the count is unknown (null), not zero.
        assert result.data["total_investments"] is None
        assert result.data["total_fair_value"] is None
        assert result.data["investments"] == []
        assert soi_text.strip() in result.data["schedule_of_investments"] or (
            result.data["schedule_of_investments"] in soi_text
        )
        assert "reason" in result.data["structured_data_unavailable"]
        assert any("edgar_notes" in step for step in result.next_steps)


# =============================================================================
# Fast: no double-parse on the no-structured-data fallback (fix round 1,
# finding 1)
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestNoDoubleParseOnFallback:
    async def test_fallback_path_calls_filing_xbrl_exactly_once(self, monkeypatch):
        """Regression: `_bdc_portfolio_no_structured_data` used to call
        `filing.xbrl()` itself even though `portfolio_investments_from_filing`
        (called just before it) had already parsed the same filing's XBRL --
        a second parse of the filing's full submission. `_load_extraction`
        now parses once and threads the result through both places.
        """
        fake_xbrl = _FakeXBRLNoSOI()
        filing = _FakeFiling(xbrl_result=fake_xbrl)
        _patch_selection(monkeypatch, filing)
        _patch_bdc(monkeypatch)

        def _extraction_uses_given_xbrl(filing_arg, include_untyped=False, xbrl=None):
            assert xbrl is fake_xbrl, "extraction must receive the already-parsed xbrl, not re-parse it"
            return None  # no structured holdings -> triggers the fallback

        monkeypatch.setattr(
            "edgar.bdc.investments.portfolio_investments_from_filing",
            _extraction_uses_given_xbrl,
        )

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.success is True  # falls back to the (empty) SOI text, not an error
        assert filing.xbrl_call_count == 1


# =============================================================================
# Fast: BDC resolution (fix round 1, finding 3) -- lookback across report
# years, ticker->CIK fallback, and ambiguous fuzzy-search results
# =============================================================================


@pytest.mark.fast
class TestLookupBdcLookback:
    """`edgar.bdc.reference.lookup_bdc`: checks the latest SEC BDC Report
    first, then falls back to prior years -- the real-world motivation is
    that the 2026 report is missing Ares Capital Corp, present in 2024 and
    2025 (see the fix-round-1 report)."""

    class _FakeBdcEntities:
        def __init__(self, ciks=(), tickers=None):
            self._ciks = set(ciks)
            self._tickers = tickers or {}

        def get_by_cik(self, cik):
            return _FakeBDC(cik=cik, name="Some BDC") if cik in self._ciks else None

        def get_by_ticker(self, ticker):
            cik = self._tickers.get(ticker)
            return _FakeBDC(cik=cik, name="Some BDC") if cik is not None else None

    def test_latest_report_miss_falls_back_to_prior_year(self, monkeypatch):
        from edgar.bdc import reference

        def _fake_get_bdc_list(year=None):
            if year == 2026:
                return self._FakeBdcEntities(ciks=())
            if year == 2025:
                return self._FakeBdcEntities(ciks={1287750})
            return self._FakeBdcEntities(ciks=())

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", _fake_get_bdc_list)

        result = reference.lookup_bdc(cik=1287750, lookback_years=2)

        assert result is not None
        assert result.cik == 1287750

    def test_latest_report_hit_never_checks_prior_years(self, monkeypatch):
        """The latest-year iteration calls get_bdc_list(None) -- the same
        call a bare get_bdc_list() makes -- so it shares fetch_bdc_report's
        cache entry instead of fetching the identical CSV again under an
        explicit-year key (QA fix wave, P1-L1)."""
        from edgar.bdc import reference

        years_checked = []

        def _fake_get_bdc_list(year=None):
            years_checked.append(year)
            return self._FakeBdcEntities(ciks={1287750})

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", _fake_get_bdc_list)

        result = reference.lookup_bdc(cik=1287750, lookback_years=2)

        assert result is not None
        assert years_checked == [None]

    def test_latest_match_carries_the_matched_report_year(self, monkeypatch):
        """P1-M5 (library part): the match exposes which report year it came
        from via an additive `report_year` attribute, even though the call
        into get_bdc_list() for that year used None."""
        from edgar.bdc import reference

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(
            reference, "get_bdc_list",
            lambda year=None: self._FakeBdcEntities(ciks={1287750}),
        )

        result = reference.lookup_bdc(cik=1287750, lookback_years=2)

        assert result.report_year == 2026

    def test_lookback_match_carries_the_matched_report_year(self, monkeypatch):
        from edgar.bdc import reference

        def _fake_get_bdc_list(year=None):
            if year == 2025:
                return self._FakeBdcEntities(ciks={1287750})
            return self._FakeBdcEntities(ciks=())

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", _fake_get_bdc_list)

        result = reference.lookup_bdc(cik=1287750, lookback_years=2)

        assert result.report_year == 2025

    def test_ticker_lookback_hit(self, monkeypatch):
        from edgar.bdc import reference

        def _fake_get_bdc_list(year=None):
            if year == 2025:
                return self._FakeBdcEntities(tickers={"ARCC": 1287750})
            return self._FakeBdcEntities()

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", _fake_get_bdc_list)

        result = reference.lookup_bdc(ticker="ARCC", lookback_years=2)

        assert result is not None
        assert result.cik == 1287750

    def test_no_match_in_any_lookback_year_returns_none(self, monkeypatch):
        from edgar.bdc import reference

        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", lambda year=None: self._FakeBdcEntities())

        assert reference.lookup_bdc(cik=999999, lookback_years=2) is None

    def test_requires_cik_or_ticker(self):
        from edgar.bdc.reference import lookup_bdc

        # Still a ValueError (ValidationError IS-A ValueError) -- ratchet fix,
        # QA fix wave item 1 -- so existing `except ValueError:` callers are
        # unaffected.
        with pytest.raises(ValueError):
            lookup_bdc()

    def test_requires_cik_or_ticker_is_a_validation_error(self):
        from edgar.bdc.reference import lookup_bdc
        from edgar.exceptions import ValidationError

        with pytest.raises(ValidationError):
            lookup_bdc()


@pytest.mark.fast
class TestGetLatestBdcReportYearCaching:
    """P1-L1: get_latest_bdc_report_year() is lru_cached, so a second call in
    the same process does not re-probe SEC."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from edgar.bdc.reference import get_latest_bdc_report_year
        get_latest_bdc_report_year.cache_clear()
        yield
        get_latest_bdc_report_year.cache_clear()

    def test_second_call_makes_no_further_requests(self, monkeypatch):
        from edgar.bdc import reference

        calls = []

        class _Response:
            status_code = 200

        def _spy(url, timeout=5):
            calls.append(url)
            return _Response()

        monkeypatch.setattr(reference, "get_with_retry", _spy)

        first = reference.get_latest_bdc_report_year()
        second = reference.get_latest_bdc_report_year()

        assert first == second
        assert len(calls) == 1


@pytest.mark.fast
class TestFindBdcResolution:
    """`edgar.ai.mcp.tools.bdc.identity.resolve_bdc`: ticker/CIK go through
    `lookup_bdc`; a ticker absent from every report falls back to
    `resolve_company`; a name goes through fuzzy search, which must be
    unambiguous."""

    def test_numeric_identifier_resolves_as_cik(self, monkeypatch):
        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: (
                _FakeBDC(cik=cik) if cik == 845385 else None
            ),
        )

        lookup = bdc_identity.resolve_bdc("845385")

        assert lookup.bdc is not None
        assert lookup.bdc.cik == 845385
        assert lookup.ambiguous is None

    def test_ticker_not_in_any_report_falls_back_to_resolve_company(self, monkeypatch):
        """A ticker absent from every checked report year's ticker column
        (the real-world ARCC gap) still resolves, via resolve_company()'s
        CIK -- proving `_find_bdc` doesn't stop at "not a known ticker"."""

        def _fake_lookup_bdc(cik=None, ticker=None, lookback_years=2):
            if ticker is not None:
                return None  # not in any report's ticker column
            assert cik == 1287750
            return _FakeBDC(cik=1287750, name="ARES CAPITAL CORP")

        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", _fake_lookup_bdc)
        monkeypatch.setattr(bdc_identity, "resolve_company", lambda identifier: _FakeCompany(cik=1287750))

        lookup = bdc_identity.resolve_bdc("ARCC")

        assert lookup.bdc is not None
        assert lookup.bdc.cik == 1287750
        assert lookup.ambiguous is None

    def test_ticker_like_identifier_falls_back_to_name_search_on_a_miss(self, monkeypatch):
        """P1-M2(a) (replaces the old "never reaches fuzzy search" test,
        which asserted the regression): a short alphanumeric identifier is
        tried as a ticker first, but when both `lookup_bdc(ticker)` and
        `resolve_company` miss it falls through to the name search, so a
        short name like "Golub" still resolves."""
        searched = []

        class _FakeSearchResults:
            empty = False
            results = pd.DataFrame([
                {"cik": 1476765, "ticker": "GBDC", "name": "GOLUB CAPITAL BDC, Inc.",
                 "state": "NY", "is_active": True, "score": 100},
            ])

        def _fake_search(identifier, top_n=10, **kwargs):
            searched.append(identifier)
            return _FakeSearchResults()

        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: (
                _FakeBDC(cik=cik, name="GOLUB CAPITAL BDC, Inc.") if cik == 1476765 else None
            ),
        )
        monkeypatch.setattr(bdc_identity, "resolve_company", lambda identifier: (_ for _ in ()).throw(ValueError("nope")))
        monkeypatch.setattr("edgar.bdc.search.find_bdc", _fake_search)

        lookup = bdc_identity.resolve_bdc("Golub")

        assert searched == ["Golub"]
        assert lookup.bdc is not None
        assert lookup.bdc.cik == 1476765
        assert lookup.resolved_by == "search"

    def test_ticker_like_identifier_with_no_search_hit_is_not_found(self, monkeypatch):
        """Silence check: ticker miss, company miss and no search hit is a
        plain not-found (both fields None), not a guess."""
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        monkeypatch.setattr(bdc_identity, "resolve_company", lambda identifier: (_ for _ in ()).throw(ValueError("nope")))

        class _Empty:
            empty = True
            results = pd.DataFrame(columns=["cik", "ticker", "name", "state", "is_active", "score"])

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=10, **kwargs: _Empty())

        lookup = bdc_identity.resolve_bdc("ZZZZZ")

        assert lookup.bdc is None
        assert lookup.ambiguous is None

    def test_ambiguous_name_search_reports_multiple_candidates(self, monkeypatch):
        class _FakeSearchResults:
            empty = False
            results = pd.DataFrame([
                {"cik": 1, "ticker": "AAA", "name": "Alpha BDC", "state": "NY", "is_active": True, "score": 90},
                {"cik": 2, "ticker": None, "name": "Alpha Capital BDC", "state": "CA", "is_active": True, "score": 85},
            ])

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=10, **kwargs: _FakeSearchResults())

        lookup = bdc_identity.resolve_bdc("Alpha Investment Group")

        assert lookup.bdc is None
        assert lookup.ambiguous is not None
        assert len(lookup.ambiguous) == 2
        assert {c["cik"] for c in lookup.ambiguous} == {1, 2}

    def test_unambiguous_name_search_resolves_by_cik(self, monkeypatch):
        class _FakeSearchResults:
            empty = False
            results = pd.DataFrame([
                {"cik": 1287750, "ticker": "ARCC", "name": "ARES CAPITAL CORP", "state": "MD", "is_active": True, "score": 95},
            ])

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=10, **kwargs: _FakeSearchResults())
        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: _FakeBDC(cik=cik, name="ARES CAPITAL CORP"),
        )

        lookup = bdc_identity.resolve_bdc("Ares Capital Corporation")

        assert lookup.bdc is not None
        assert lookup.bdc.cik == 1287750
        assert lookup.resolved_by == "search"


@pytest.mark.fast
@pytest.mark.asyncio
class TestAmbiguousBdcEndToEnd:
    async def test_edgar_fund_returns_ambiguous_bdc_with_candidate_suggestions(self, monkeypatch):
        class _FakeSearchResults:
            empty = False
            results = pd.DataFrame([
                {"cik": 1, "ticker": "AAA", "name": "Alpha BDC", "state": "NY", "is_active": True, "score": 90},
                {"cik": 2, "ticker": None, "name": "Alpha Capital BDC", "state": "CA", "is_active": True, "score": 85},
            ])

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=10, **kwargs: _FakeSearchResults())

        result = await edgar_fund(action="bdc_portfolio", identifier="Alpha Investment Group")

        assert result.success is False
        assert result.error_code == "AMBIGUOUS_BDC"
        assert len(result.suggestions) == 2
        assert any("Alpha BDC" in s for s in result.suggestions)
        assert any("Alpha Capital BDC" in s for s in result.suggestions)


# =============================================================================
# Fast: patch seams are live (Q2 fix round 1). The BDC code moved from fund.py
# into edgar/ai/mcp/tools/bdc/; these tests patch names where they are looked
# up now. A stale patch target would make the tests above run against real
# code and pass vacuously, so each key seam is asserted to be called.
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestPatchSeamsAreLive:
    async def test_portfolio_uses_patched_resolution_selection_and_extraction(self, monkeypatch):
        bdc_calls = _patch_bdc(monkeypatch)
        selection_calls = _patch_selection(monkeypatch, _FakeFiling())
        extraction_calls = _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.success is True
        assert bdc_calls == ["ARCC"]
        assert len(selection_calls) == 1
        assert selection_calls[0]["company"].cik == 1287750
        assert len(extraction_calls) == 1

    async def test_resolve_company_patch_is_live(self, monkeypatch):
        calls = []

        def _resolve(identifier):
            calls.append(identifier)
            return _FakeCompany(cik=320193)

        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        monkeypatch.setattr(bdc_identity, "resolve_company", _resolve)

        result = await edgar_fund(action="bdc_portfolio", identifier="320193")

        assert result.error_code == "NOT_A_BDC"
        assert calls == ["320193"]

    async def test_lookup_bdc_patch_is_live_on_the_accession_path(self, monkeypatch):
        calls = []

        def _lookup(cik=None, ticker=None, lookback_years=2):
            calls.append(cik)
            return _FakeBDC(cik=cik)

        _patch_selection(monkeypatch, _FakeFiling(), selected_by="accession")
        _patch_extraction(monkeypatch, _make_investment_batch(1))
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", _lookup)

        result = await edgar_fund(action="bdc_portfolio", accession_number="0001628280-26-050307")

        assert result.success is True
        assert calls == [1287750]


# =============================================================================
# Fast: QA fix wave Q2 -- SOI cursor routing (P1-H1), cursor-only
# continuation (P1-H2 / rule 7b), unknown-is-null (P1-M4), BDC name
# resolution (P1-M2), stale report year (P1-M5), strict include_untyped and
# NOT_A_BDC for a numeric identifier (P1-L10)
# =============================================================================

MAIN_CIK = 1396440


def _patch_selection_by_accession(monkeypatch, filings, latest=None):
    """A resolver fake that honours the accession path the way the real one
    does: selects by `accession_number` when given (SELECTION_MISMATCH when a
    pre-resolved `company` has a different CIK), by exact `period` when
    given, else returns `latest`. Records every call's kwargs."""
    by_acc = {f.accession_number: f for f in filings}
    calls = []

    def _resolve(**kwargs):
        calls.append(kwargs)
        acc = kwargs.get("accession_number")
        if acc:
            filing = by_acc.get(acc)
            if filing is None:
                raise FilingSelectionError("not found", error_code="FILING_NOT_FOUND")
            company = kwargs.get("company")
            if company is not None and int(company.cik) != int(filing.cik):
                raise FilingSelectionError("mismatch", error_code="SELECTION_MISMATCH")
            return FilingSelection(filing=filing, selected_by="accession")
        if kwargs.get("period"):
            match = next(f for f in filings if f.report_date == kwargs["period"])
            return FilingSelection(filing=match, selected_by="period")
        return FilingSelection(filing=latest or filings[0], selected_by="latest")

    monkeypatch.setattr("edgar.ai.mcp.tools.selection.resolve_report_filing", _resolve)
    return calls


def _patch_lookup_bdc_by_cik(monkeypatch, bdc_factory=None):
    """`lookup_bdc(cik=...)` for the accession/cursor path: echoes the CIK back."""
    factory = bdc_factory or (lambda cik: _FakeBDC(cik=cik))
    monkeypatch.setattr(
        "edgar.bdc.reference.lookup_bdc",
        lambda cik=None, ticker=None, lookback_years=2: factory(cik) if cik is not None else None,
    )


def _long_soi_text(lines: int = 700) -> str:
    return "Schedule of Investments\n\n" + "".join(
        f"Holding {i:04d}: first lien term loan, some words.\n" for i in range(lines)
    )


@pytest.mark.fast
@pytest.mark.asyncio
class TestSoiTextContinuation:
    """P1-H1: the SOI text fallback's own cursors must continue."""

    async def test_cursor_alone_walks_every_soi_page(self, monkeypatch):
        soi_text = _long_soi_text()
        assert len(soi_text) == 33625
        filing = _FakeFiling(xbrl_result=_FakeXBRLWithSOI(soi_text))
        calls = _patch_selection_by_accession(monkeypatch, [filing])
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)
        _patch_lookup_bdc_by_cik(monkeypatch)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC")
        assert first.success is True
        pages = [first.data["schedule_of_investments"]]
        cursor = first.data["text_page"]["next_cursor"]
        while cursor is not None:
            nxt = await edgar_fund(action="bdc_portfolio", cursor=cursor)
            assert nxt.success is True, (nxt.error_code, nxt.error)
            assert nxt.data["source"]["accession_number"] == filing.accession_number
            pages.append(nxt.data["schedule_of_investments"])
            cursor = nxt.data["text_page"]["next_cursor"]
            assert len(pages) < 20  # guard against an infinite loop bug

        assert "".join(pages) == soi_text
        assert len(pages) == 6
        # Every continuation selected the cursor's own filing by accession.
        assert [c.get("accession_number") for c in calls[1:]] == [filing.accession_number] * 5
        # Parsed once, on page 1; later pages read text_cache before xbrl().
        assert filing.xbrl_call_count == 1

    async def test_text_page_has_only_documented_keys(self, monkeypatch):
        """P1-L6: the internal `next_offset` is not part of the response."""
        filing = _FakeFiling(xbrl_result=_FakeXBRLWithSOI(_long_soi_text()))
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert set(result.data["text_page"]) == {
            "offset", "returned_chars", "total_chars", "remaining_chars", "next_cursor",
        }
        assert result.data["text_page"]["offset"] == 0
        assert result.data["text_page"]["total_chars"] == 33625

    async def test_soi_cursor_after_cache_loss_reparses_once_and_continues(self, monkeypatch):
        """A fresh process (empty caches) re-extracts the text once, checks
        the fingerprint, and continues -- no CURSOR_MISMATCH."""
        soi_text = _long_soi_text()
        filing = _FakeFiling(xbrl_result=_FakeXBRLWithSOI(soi_text))
        _patch_selection_by_accession(monkeypatch, [filing])
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)
        _patch_lookup_bdc_by_cik(monkeypatch)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC")
        monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
        monkeypatch.setattr(continuation, "text_cache", ResultCache(max_entries=8, max_bytes=1024 * 1024))

        second = await edgar_fund(action="bdc_portfolio", cursor=first.data["text_page"]["next_cursor"])

        assert second.success is True
        assert second.data["text_page"]["offset"] == len(first.data["schedule_of_investments"])
        assert filing.xbrl_call_count == 2

    @pytest.mark.parametrize("xbrl_factory,reason", [
        (lambda: _FakeXBRLNoSOI(), bdc_portfolio_mod.NO_SOI_STATEMENT_REASON),
        (lambda: _FakeXBRLWithSOI("Schedule of Investments\nShort.\n"), bdc_portfolio_mod.NO_STRUCTURED_FIELDS_REASON),
    ])
    async def test_no_structured_holdings_outcome_is_cached(self, monkeypatch, xbrl_factory, reason):
        """P1-H1 secondary: a `None` extraction (no structured holdings) is
        cached, so repeat first-page calls do not re-parse the XBRL."""
        filing = _FakeFiling(xbrl_result=xbrl_factory())
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)

        for _ in range(3):
            result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")
            assert result.success is True
            assert result.data["structured_data_unavailable"]["reason"] == reason

        assert filing.xbrl_call_count == 1


@pytest.mark.fast
@pytest.mark.asyncio
class TestCursorOnlyContinuation:
    """P1-H2 / rule 7b: a cursor alone is enough; repeated arguments must agree."""

    @staticmethod
    def _setup(monkeypatch, investments=None, filings=None, latest=None):
        filings = filings or [_FakeFiling()]
        calls = _patch_selection_by_accession(monkeypatch, filings, latest=latest)
        _patch_extraction(monkeypatch, investments or _make_investment_batch(25))
        _patch_bdc(monkeypatch)
        _patch_lookup_bdc_by_cik(monkeypatch)
        return calls

    async def test_cursor_alone_walks_all_filtered_holdings(self, monkeypatch):
        holdings = list(_make_investment_batch(60)) + [
            _make_investment(identifier=f"Other Co {i} - Loan", company_name=f"Other Co {i}") for i in range(5)
        ]
        investments = PortfolioInvestments(holdings, period="2026-06-30", extraction_method="xbrl_facts")
        calls = self._setup(monkeypatch, investments)

        first = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30",
            borrower="company", limit=5,
        )
        seen = [rec["identifier"] for rec in first.data["investments"]]
        cursor = first.data["page"]["next_cursor"]
        pages = 1
        while cursor is not None:
            nxt = await edgar_fund(action="bdc_portfolio", cursor=cursor)
            assert nxt.success is True, (nxt.error_code, nxt.error)
            assert nxt.data["page"]["total_matching"] == 60  # borrower filter came from the cursor
            assert nxt.data["page"]["total_extracted"] == 65
            seen.extend(rec["identifier"] for rec in nxt.data["investments"])
            cursor = nxt.data["page"]["next_cursor"]
            pages += 1
            assert pages < 10

        assert pages == 4  # 5 + 20 + 20 + 15 (default limit on cursor-only calls)
        assert seen == [f"Company {i} - Term Loan" for i in range(60)]
        assert all(c["accession_number"] == "0001628280-26-050307" for c in calls[1:])
        assert all(c.get("period") is None for c in calls[1:])

    async def test_documented_next_page_example_continues_the_chosen_filing(self, monkeypatch):
        """The exact QA scenario: page 1 by period (a 10-Q), page 2 per the
        documented example with only identifier + cursor. The second call
        used to default to the latest 10-K and fail CURSOR_MISMATCH."""
        q2 = _FakeFiling(accession_number="0001628280-26-050307", form="10-Q")
        tenk = _FakeFiling(accession_number="0001287750-26-000010", form="10-K", report_date="2025-12-31")
        self._setup(monkeypatch, filings=[q2, tenk], latest=tenk)

        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30")
        assert first.data["source"]["accession_number"] == q2.accession_number

        nxt = await edgar_fund(action="bdc_portfolio", identifier="ARCC", cursor=first.data["page"]["next_cursor"])

        assert nxt.success is True, (nxt.error_code, nxt.error)
        assert nxt.data["source"]["accession_number"] == q2.accession_number
        assert nxt.data["page"]["offset"] == 20
        assert nxt.data["page"]["returned"] == 5

    async def test_repeating_the_same_borrower_and_selectors_is_accepted(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="Company 1", limit=2)

        nxt = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", borrower="  COMPANY 1 ", include_untyped=False,
            form="10-K", period="1999-12-31", cursor=first.data["page"]["next_cursor"],
        )

        assert nxt.success is True, (nxt.error_code, nxt.error)
        assert nxt.data["page"]["offset"] == 2
        assert nxt.data["page"]["total_matching"] == 11  # Company 1, 10..19

    async def test_a_different_borrower_with_the_cursor_is_cursor_mismatch(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="company 1", limit=2)

        nxt = await edgar_fund(action="bdc_portfolio", borrower="company 2", cursor=first.data["page"]["next_cursor"])

        assert nxt.success is False
        assert nxt.error_code == "CURSOR_MISMATCH"

    async def test_a_different_include_untyped_with_the_cursor_is_cursor_mismatch(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)

        nxt = await edgar_fund(action="bdc_portfolio", include_untyped=True, cursor=first.data["page"]["next_cursor"])

        assert nxt.success is False
        assert nxt.error_code == "CURSOR_MISMATCH"

    async def test_identifier_for_a_different_bdc_is_selection_mismatch(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)
        monkeypatch.setattr(
            "edgar.ai.mcp.tools.bdc.identity.resolve_bdc",
            lambda identifier: BdcLookup(bdc=_FakeBDC(cik=MAIN_CIK, name="MAIN STREET CAPITAL CORP")),
        )

        nxt = await edgar_fund(action="bdc_portfolio", identifier="MAIN", cursor=first.data["page"]["next_cursor"])

        assert nxt.success is False
        assert nxt.error_code == "SELECTION_MISMATCH"

    async def test_an_accession_number_differing_from_the_cursor_is_cursor_mismatch(self, monkeypatch):
        calls = self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)
        calls.clear()

        nxt = await edgar_fund(
            action="bdc_portfolio", accession_number="0000000000-26-000001",
            cursor=first.data["page"]["next_cursor"],
        )

        assert nxt.success is False
        assert nxt.error_code == "CURSOR_MISMATCH"
        assert calls == []  # rejected before any filing selection

    async def test_the_cursor_accession_repeated_without_dashes_is_accepted(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_portfolio", identifier="ARCC", limit=2)

        nxt = await edgar_fund(
            action="bdc_portfolio", accession_number="000162828026050307",
            cursor=first.data["page"]["next_cursor"],
        )

        assert nxt.success is True, (nxt.error_code, nxt.error)

    async def test_another_tools_cursor_is_rejected_before_any_selection(self, monkeypatch):
        calls = self._setup(monkeypatch)
        nonaccrual_cursor = continuation.encode_cursor(
            tool="edgar_fund:bdc_nonaccrual", accession="0001628280-26-050307", offset=20, fp="abc", query=None,
        )

        result = await edgar_fund(action="bdc_portfolio", cursor=nonaccrual_cursor)

        assert result.success is False
        assert result.error_code == "CURSOR_MISMATCH"
        assert calls == []

    async def test_garbage_cursor_alone_is_invalid_cursor(self, monkeypatch):
        """Silence check: a cursor-only call with a garbage cursor names the
        cursor as the problem, not a missing identifier."""
        calls = self._setup(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", cursor="!!!not-a-real-cursor!!!")

        assert result.success is False
        assert result.error_code == "INVALID_CURSOR"
        assert calls == []


@pytest.mark.fast
@pytest.mark.asyncio
class TestUnknownIsNull:
    """P1-M4 / rule 7b: sums over values that are all null are null, never 0."""

    async def test_filtered_totals_null_when_matching_values_all_missing(self, monkeypatch):
        investments = PortfolioInvestments(
            [
                _make_investment("Acme Holdings - Common Stock", "Acme Holdings", "Common equity"),
                _make_investment("Other - Loan", "Other", fair_value=Decimal("5"), cost=Decimal("5")),
            ],
            period="2026-06-30", extraction_method="xbrl_facts",
        )
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="acme")

        assert result.data["filtered_totals"] == {"count": 1, "fair_value": None, "cost": None}
        assert result.data["investments"][0]["fair_value"] is None
        assert result.data["total_fair_value"] == 5.0

    async def test_filtered_totals_sum_only_known_values(self, monkeypatch):
        investments = PortfolioInvestments(
            [
                _make_investment("Acme A - Loan", "Acme A", fair_value=Decimal("100")),
                _make_investment("Acme B - Loan", "Acme B", cost=Decimal("40")),
            ],
            period="2026-06-30", extraction_method="xbrl_facts",
        )
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", borrower="acme")

        assert result.data["filtered_totals"] == {"count": 2, "fair_value": 100.0, "cost": 40.0}

    async def test_total_fair_value_and_cost_null_when_no_holding_has_them(self, monkeypatch):
        investments = PortfolioInvestments(
            [_make_investment("Bare - Equity", "Bare", "Common equity")],
            period="2026-06-30", extraction_method="xbrl_facts",
        )
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, investments)
        _patch_bdc(monkeypatch)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.data["total_investments"] == 1
        assert result.data["total_fair_value"] is None
        assert result.data["total_cost"] is None


class _FakeFilingsPage:
    def __init__(self, latest_filed):
        self._latest_filed = latest_filed

    def __len__(self):
        return 0 if self._latest_filed is None else 1

    def latest(self, n=1):
        return None if self._latest_filed is None else type("F", (), {"filing_date": self._latest_filed})()


class _CompanyWithFilings:
    def __init__(self, cik, latest_filed=None, fail=False):
        self.cik = cik
        self._latest_filed = latest_filed
        self._fail = fail
        self.get_filings_calls = 0

    def get_filings(self, **kwargs):
        self.get_filings_calls += 1
        if self._fail:
            raise RuntimeError("submissions unavailable")
        return _FakeFilingsPage(self._latest_filed)


@pytest.mark.fast
@pytest.mark.asyncio
class TestStaleReportYear:
    """P1-M5: a lookback-year match takes `is_active` from the company's own
    latest filing (18-month rule), not from the stale report row."""

    @staticmethod
    def _stale_bdc(monkeypatch, company, report_year=2025, is_active=False):
        bdc = _FakeBDC(is_active=is_active, report_year=report_year)
        bdc.get_company = lambda: company
        monkeypatch.setattr("edgar.bdc.reference.get_latest_bdc_report_year", lambda: 2026)
        return bdc

    async def test_lookback_match_derives_is_active_from_latest_filing(self, monkeypatch):
        from datetime import date, timedelta

        company = _CompanyWithFilings(1287750, latest_filed=date.today() - timedelta(days=30))
        _patch_bdc(monkeypatch, self._stale_bdc(monkeypatch, company))
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.data["is_active"] is True  # the stale 2025 row said False
        assert result.data["bdc_report_year"] == 2025

    async def test_lookback_match_with_an_old_latest_filing_is_inactive(self, monkeypatch):
        from datetime import date

        company = _CompanyWithFilings(1287750, latest_filed=date(2020, 1, 15))
        _patch_bdc(monkeypatch, self._stale_bdc(monkeypatch, company, is_active=True))
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.data["is_active"] is False

    async def test_lookback_match_without_filing_data_is_null(self, monkeypatch):
        company = _CompanyWithFilings(1287750, fail=True)
        _patch_bdc(monkeypatch, self._stale_bdc(monkeypatch, company, is_active=True))
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.success is True
        assert result.data["is_active"] is None
        assert result.data["bdc_report_year"] == 2025

    async def test_latest_year_match_trusts_the_report_row(self, monkeypatch):
        company = _CompanyWithFilings(1287750, fail=True)
        _patch_bdc(monkeypatch, self._stale_bdc(monkeypatch, company, report_year=2026, is_active=True))
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC")

        assert result.data["is_active"] is True
        assert result.data["bdc_report_year"] == 2026
        assert company.get_filings_calls == 0

    async def test_accession_only_path_loads_the_company_for_a_lookback_match(self, monkeypatch):
        from datetime import date, timedelta

        company = _CompanyWithFilings(1287750, latest_filed=date.today() - timedelta(days=10))
        bdc = self._stale_bdc(monkeypatch, company)
        _patch_selection(monkeypatch, _FakeFiling(), selected_by="accession")
        _patch_lookup_bdc_by_cik(monkeypatch, lambda cik: bdc)
        _patch_extraction(monkeypatch, _make_investment_batch(2))

        result = await edgar_fund(action="bdc_portfolio", accession_number="0001628280-26-050307")

        assert result.data["is_active"] is True
        assert result.data["bdc_report_year"] == 2025
        assert company.get_filings_calls == 1


def _fake_search_results(rows: list[dict]):
    frame = pd.DataFrame(rows, columns=["cik", "ticker", "name", "state", "is_active", "score"])
    return type("_R", (), {"empty": frame.empty, "results": frame})()


def _hit(cik, name, score, ticker=None):
    return {"cik": cik, "ticker": ticker, "name": name, "state": "NY", "is_active": True, "score": score}


@pytest.mark.fast
class TestNameSearchResolutionRules:
    """P1-M2(b): auto-select only an exact name match or a clear, high-scoring
    winner; everything else is AMBIGUOUS_BDC with up to 5 candidates."""

    @staticmethod
    def _search(monkeypatch, rows, captured=None):
        def _fake(identifier, top_n=10, **kwargs):
            if captured is not None:
                captured.append({"identifier": identifier, "top_n": top_n, **kwargs})
            return _fake_search_results(rows)

        monkeypatch.setattr("edgar.bdc.search.find_bdc", _fake)
        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: _FakeBDC(cik=cik) if cik else None,
        )

    def test_exact_name_match_resolves_despite_other_high_hits(self, monkeypatch):
        self._search(monkeypatch, [
            _hit(1287750, "ARES CAPITAL CORP", 100, "ARCC"),
            _hit(1000001, "ARES STRATEGIC INCOME FUND", 99.4),
            _hit(1000002, "Ares Core Infrastructure Fund", 99.2),
        ])

        lookup = bdc_identity.resolve_bdc_by_search("ares  capital CORP")

        assert lookup.bdc.cik == 1287750
        assert lookup.resolved_by == "search"

    def test_clear_high_scoring_winner_resolves(self, monkeypatch):
        self._search(monkeypatch, [_hit(1396440, "MAIN STREET CAPITAL CORP", 97), _hit(2, "Other", 70.6)])

        assert bdc_identity.resolve_bdc_by_search("Main Street Capital").bdc.cik == 1396440

    @pytest.mark.parametrize("rows", [
        [_hit(1, "Alpha One Fund", 99), _hit(2, "Alpha Two Fund", 98)],   # two >= 95
        [_hit(1, "Alpha One Fund", 97), _hit(2, "Alpha Two Fund", 91)],   # runner-up >= 90
        [_hit(1, "Alpha One Fund", 80)],                                  # single hit below 95
    ])
    def test_unclear_results_are_ambiguous(self, monkeypatch, rows):
        self._search(monkeypatch, rows)

        lookup = bdc_identity.resolve_bdc_by_search("Alpha")

        assert lookup.bdc is None
        assert [c["cik"] for c in lookup.ambiguous] == [r["cik"] for r in rows]

    def test_ambiguous_lists_at_most_five_candidates(self, monkeypatch):
        self._search(monkeypatch, [_hit(i, f"Ares Fund {i}", 99 - i / 10) for i in range(1, 9)])

        lookup = bdc_identity.resolve_bdc_by_search("Ares")

        assert [c["cik"] for c in lookup.ambiguous] == [1, 2, 3, 4, 5]

    def test_search_covers_the_lookup_bdc_lookback_years(self, monkeypatch):
        captured = []
        self._search(monkeypatch, [_hit(1287750, "ARES CAPITAL CORP", 100)], captured)

        bdc_identity.resolve_bdc_by_search("Ares Capital Corp")

        assert captured == [{"identifier": "Ares Capital Corp", "top_n": 10, "lookback_years": 2}]

    def test_short_name_resolving_to_a_non_bdc_company_reaches_search(self, monkeypatch):
        """"Ares" resolves to Ares Management (not a BDC); that is not the end."""
        self._search(monkeypatch, [
            _hit(1287750, "ARES CAPITAL CORP", 100, "ARCC"),
            _hit(1000001, "ARES STRATEGIC INCOME FUND", 99.4),
        ])
        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: None,
        )
        resolved = []
        monkeypatch.setattr(
            bdc_identity, "resolve_company", lambda identifier: resolved.append(identifier) or _FakeCompany(cik=1176948)
        )

        lookup = bdc_identity.resolve_bdc("Ares")

        assert resolved == ["Ares"]  # the patch is live: Ares Management was resolved, then searched
        assert lookup.bdc is None
        assert [c["cik"] for c in lookup.ambiguous] == [1287750, 1000001]


@pytest.mark.fast
@pytest.mark.asyncio
class TestNumericIdentifierNotABdc:
    """P1-L10: a numeric identifier that is a real company but not a BDC is
    NOT_A_BDC (as on the accession path), not COMPANY_NOT_FOUND."""

    async def test_real_non_bdc_cik_is_not_a_bdc(self, monkeypatch):
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        resolved = []
        monkeypatch.setattr(
            bdc_identity, "resolve_company", lambda identifier: resolved.append(identifier) or _FakeCompany(cik=320193)
        )

        result = await edgar_fund(action="bdc_portfolio", identifier="320193")

        assert resolved == ["320193"]
        assert result.success is False
        assert result.error_code == "NOT_A_BDC"
        assert "320193" in result.error

    async def test_unknown_cik_is_company_not_found(self, monkeypatch):
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        monkeypatch.setattr(bdc_identity, "resolve_company", lambda identifier: (_ for _ in ()).throw(ValueError("nope")))

        result = await edgar_fund(action="bdc_portfolio", identifier="99999999")

        assert result.success is False
        assert result.error_code == "COMPANY_NOT_FOUND"

    async def test_placeholder_entity_for_an_unknown_cik_is_company_not_found(self, monkeypatch):
        """`Company(99999999)` does not raise; it returns a placeholder whose
        `not_found` is True (measured live 2026-09-29). That is not a real
        company, so it must not read as NOT_A_BDC."""
        placeholder = _FakeCompany(cik=99999999)
        placeholder.not_found = True
        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        monkeypatch.setattr(bdc_identity, "resolve_company", lambda identifier: placeholder)

        result = await edgar_fund(action="bdc_portfolio", identifier="99999999")

        assert result.success is False
        assert result.error_code == "COMPANY_NOT_FOUND"


@pytest.mark.fast
@pytest.mark.asyncio
class TestIncludeUntypedParsing:
    """P1-L10: `include_untyped` is parsed strictly, never with bool()."""

    @pytest.mark.parametrize("value,expected", [
        ("false", False), ("FALSE", False), ("True", True), (True, True), (False, False),
    ])
    async def test_bools_and_true_false_strings_parse(self, monkeypatch, value, expected):
        seen = []
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_bdc(monkeypatch)

        def _extract(filing, include_untyped=False, xbrl=None):
            seen.append(include_untyped)
            return _make_investment_batch(1)

        monkeypatch.setattr("edgar.bdc.investments.portfolio_investments_from_filing", _extract)

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", include_untyped=value)

        assert result.success is True
        assert seen == [expected]
        assert result.data["extraction"]["include_untyped"] is expected

    @pytest.mark.parametrize("value", ["yes", "0", "", "flase", 1])
    async def test_anything_else_is_invalid_arguments(self, monkeypatch, value):
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_bdc(monkeypatch)
        _patch_extraction(monkeypatch, _make_investment_batch(1))

        result = await edgar_fund(action="bdc_portfolio", identifier="ARCC", include_untyped=value)

        assert result.success is False
        assert result.error_code == "INVALID_ARGUMENTS"
        assert "include_untyped" in result.error


@pytest.mark.fast
class TestBdcSearchIndexAcrossYears:
    """P1-M2(c): `find_bdc(..., lookback_years=N)` indexes the same report
    years `lookup_bdc` checks, one row per CIK (latest year's row wins)."""

    @pytest.fixture(autouse=True)
    def _reports(self, monkeypatch):
        from datetime import date

        from edgar.bdc import reference, search
        from edgar.bdc.reference import BDCEntities, BDCEntity

        def _bdc(cik, name, filed):
            return BDCEntity(file_number="814-0", cik=cik, name=name, last_filing_date=filed)

        reports = {
            None: [  # 2026, the latest: ARCC missing, as measured live
                _bdc(1000001, "ARES STRATEGIC INCOME FUND", date(2026, 5, 1)),
                _bdc(1000002, "Ares Core Infrastructure Fund", date(2026, 5, 2)),
            ],
            2025: [
                _bdc(1287750, "ARES CAPITAL CORP", date(2025, 5, 29)),
                _bdc(1000001, "ARES STRATEGIC INCOME FUND (OLD NAME)", date(2025, 5, 1)),
            ],
            2024: [_bdc(1287750, "ARES CAPITAL CORP", date(2024, 5, 30))],
        }
        monkeypatch.setattr(reference, "get_latest_bdc_report_year", lambda: 2026)
        monkeypatch.setattr(reference, "get_bdc_list", lambda year=None: BDCEntities(list(reports.get(year, []))))
        monkeypatch.setattr(search.BDCSearchIndex, "_get_ticker_map", staticmethod(lambda: {1287750: "ARCC"}))
        search._get_bdc_search_index.cache_clear()
        search.find_bdc.cache_clear()
        yield
        search._get_bdc_search_index.cache_clear()
        search.find_bdc.cache_clear()

    def test_lookback_index_has_one_row_per_cik_from_the_latest_year(self):
        from edgar.bdc.search import BDCSearchIndex

        index = BDCSearchIndex(lookback_years=2)
        rows = dict(zip(index.data["cik"].to_pylist(), index.data["name"].to_pylist(), strict=True))

        assert rows == {
            1000001: "ARES STRATEGIC INCOME FUND",
            1000002: "Ares Core Infrastructure Fund",
            1287750: "ARES CAPITAL CORP",
        }

    def test_default_index_is_still_the_latest_year_only(self):
        from edgar.bdc.search import BDCSearchIndex

        assert sorted(BDCSearchIndex().data["cik"].to_pylist()) == [1000001, 1000002]

    def test_find_bdc_with_lookback_finds_arcc_from_a_prior_year_row(self):
        from edgar.bdc.search import find_bdc

        results = find_bdc("Ares Capital Corp", top_n=10, lookback_years=2)

        assert int(results.results.iloc[0]["cik"]) == 1287750
        assert results.results.iloc[0]["ticker"] == "ARCC"
        assert int(find_bdc("Ares Capital Corp", top_n=10).results.iloc[0]["cik"]) != 1287750

    def test_search_results_item_resolves_a_prior_year_row(self):
        from edgar.bdc.search import find_bdc

        entity = find_bdc("Ares Capital Corp", top_n=10, lookback_years=2)[0]

        assert entity.cik == 1287750
        assert entity.report_year == 2025

    def test_fund_resolves_the_registrant_name_to_arcc(self):
        lookup = bdc_identity.resolve_bdc("Ares Capital Corp")

        assert lookup.ambiguous is None
        assert lookup.bdc.cik == 1287750
        assert lookup.bdc.report_year == 2025
        assert lookup.resolved_by == "search"


# =============================================================================
# Network + live (ARCC — no VCR, constraints rule 7a) and VCR (Princeton)
# =============================================================================

ARCC_CIK = 1287750
ARCC_10Q_ACCESSION = "0001628280-26-050307"
ARCC_10Q_HOLDING_COUNT = 1481

PRINCETON_CIK = 845385
PRINCETON_10Q_ACCESSION = "0001213900-26-090000"
PRINCETON_10Q_HOLDING_COUNT = 23


@pytest.mark.network
@pytest.mark.asyncio
class TestBdcPortfolioARCCLive:
    """Runs live, no VCR cassette (constraints rule 7a): ARCC's 10-Q submission
    is ~88 MB. The in-process results_cache means only the first extraction in
    this class pays the ~11-13s XBRL-parse cost; later tests in the same run
    reuse the cached PortfolioInvestments for this accession.

    `identifier="ARCC"` resolves for real here (no `_find_bdc` patch): fix
    round 1 added `lookup_bdc`'s report-year lookback specifically so this
    works despite the SEC's 2026 BDC Report omitting Ares Capital Corp
    (present in 2024 and 2025) -- see the fix-round-1 report.
    """

    async def test_period_selects_ground_truth_filing_and_full_count(self):
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30"
        )

        assert result.success is True
        assert result.data["total_investments"] == ARCC_10Q_HOLDING_COUNT
        assert result.data["source"]["accession_number"] == ARCC_10Q_ACCESSION
        assert result.data["source"]["selected_by"] == "period"

    async def test_borrower_filter_finds_ivy_hill_despite_wrong_company_name(self):
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio",
            identifier="ARCC",
            form="10-Q",
            period="2026-06-30",
            borrower="ivy hill",
        )

        assert result.success is True
        matches = [
            rec for rec in result.data["investments"]
            if rec["company_name"] == "Subordinated" and "Ivy Hill" in (rec["identifier"] or "")
        ]
        assert len(matches) >= 1

    async def test_walking_all_pages_returns_full_count_with_no_duplicates(self):
        set_identity("Test User test@test.com")

        seen = set()
        cursor = None
        total_returned = 0
        while True:
            result = await edgar_fund(
                action="bdc_portfolio",
                identifier="ARCC",
                form="10-Q",
                period="2026-06-30",
                limit=50,
                cursor=cursor,
            )
            assert result.success is True
            for rec in result.data["investments"]:
                key = (rec["identifier"], rec["fair_value"], rec["cost"])
                assert key not in seen, f"duplicate record across pages: {key}"
                seen.add(key)
            total_returned += result.data["page"]["returned"]
            cursor = result.data["page"]["next_cursor"]
            if cursor is None:
                break

        assert total_returned == ARCC_10Q_HOLDING_COUNT
        assert len(seen) == ARCC_10Q_HOLDING_COUNT

    async def test_walking_all_pages_with_the_cursor_alone(self):
        """P1-H2 / rule 7b: after page 1, only `cursor` is sent."""
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30", limit=50
        )
        total_returned = result.data["page"]["returned"]
        cursor = result.data["page"]["next_cursor"]
        while cursor is not None:
            result = await edgar_fund(action="bdc_portfolio", cursor=cursor)
            assert result.success is True, (result.error_code, result.error)
            assert result.data["source"]["accession_number"] == ARCC_10Q_ACCESSION
            total_returned += result.data["page"]["returned"]
            cursor = result.data["page"]["next_cursor"]

        assert total_returned == ARCC_10Q_HOLDING_COUNT

    async def test_period_off_by_one_day_is_period_not_found(self):
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-29"
        )

        assert result.success is False
        assert result.error_code == "PERIOD_NOT_FOUND"

    async def test_accession_only_path_resolves_arcc_as_a_bdc(self):
        """Fix round 1, finding 3c: the accession-only path now checks
        `lookup_bdc` (with lookback), not the latest-report-only
        `is_bdc_cik`. ARCC's own 10-Q accession, given with no identifier,
        must not come back NOT_A_BDC."""
        set_identity("Test User test@test.com")

        result = await edgar_fund(action="bdc_portfolio", accession_number=ARCC_10Q_ACCESSION)

        assert result.success is True
        assert result.data["cik"] == ARCC_CIK
        assert result.data["source"]["selected_by"] == "accession"
        assert result.data["total_investments"] == ARCC_10Q_HOLDING_COUNT
        # P1-M5: accession-only path, lookback-year (2025) match.
        assert result.data["bdc_report_year"] == 2025
        assert result.data["is_active"] is True


@pytest.mark.network
@pytest.mark.vcr
@pytest.mark.asyncio
class TestBdcPortfolioPrincetonVCR:
    """Deterministic small-BDC VCR fixture (constraints rule 7a / Task 3).

    Uses `accession_number=` rather than `identifier=` + `period=`: an
    identifier-based lookup goes through `_find_bdc`'s ticker-first
    resolution, which pulls SEC's company_tickers.json + company_tickers_mf.json
    (~2 MB combined) on a cold cache. Recorded once that way, this class's
    "period selection" cassette measured 11.9 MB -- over the 10 MB cap.
    The accession-only path (still exercising extraction, paging, and the
    borrower filter live against a real filing) skips that ticker lookup
    entirely and keeps the cassette under 10 MB. Period-based selection
    itself is already covered live against ARCC above and extensively by
    the fast, mocked resolver tests in tests/test_mcp_selection.py.
    """

    async def test_accession_selects_princeton_filing_and_full_count(self):
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio", accession_number=PRINCETON_10Q_ACCESSION
        )

        assert result.success is True
        assert result.data["total_investments"] == PRINCETON_10Q_HOLDING_COUNT
        assert result.data["source"]["accession_number"] == PRINCETON_10Q_ACCESSION
        assert result.data["source"]["selected_by"] == "accession"
        assert result.data["cik"] == PRINCETON_CIK

    async def test_borrower_filter_finds_rockfish_holding(self):
        set_identity("Test User test@test.com")

        result = await edgar_fund(
            action="bdc_portfolio",
            accession_number=PRINCETON_10Q_ACCESSION,
            borrower="rockfish",
        )

        assert result.success is True
        # "rockfish" matches several related-party holdings (the borrower is
        # a group of Rockfish entities); pin down the specific hand-verified
        # one from tests/test_bdc_filing_scoped.py's ground truth.
        matches = [
            rec for rec in result.data["investments"]
            if rec["identifier"] == "Control Investments - Rockfish Seafood Grill, Inc. - Revolving Loan"
        ]
        assert len(matches) == 1
        assert matches[0]["fair_value"] == 2433581.0
        assert matches[0]["principal_amount"] == 2251000.0
        assert matches[0]["interest_rate"] == 0.08


@pytest.mark.network
class TestBdcNameSearchLive:
    """P1-M2(c), live (BDC report CSVs + SEC ticker map only; no XBRL). ARCC
    is absent from the 2026 BDC Report (measured 2026-09-28/29), so its
    registrant name only resolves when the name-search index covers the
    `lookup_bdc` lookback years."""

    def test_arcc_registrant_name_resolves_to_cik_1287750(self):
        set_identity("Test User test@test.com")

        lookup = bdc_identity.resolve_bdc("Ares Capital Corp")

        assert lookup.ambiguous is None
        assert lookup.bdc is not None
        assert lookup.bdc.cik == ARCC_CIK
        assert lookup.bdc.name == "ARES CAPITAL CORP"
        assert lookup.bdc.report_year == 2025
        assert lookup.resolved_by == "search"
