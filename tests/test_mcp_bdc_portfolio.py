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
from edgar.ai.mcp.tools import continuation, fund
from edgar.ai.mcp.tools.continuation import ResultCache
from edgar.ai.mcp.tools.fund import _BdcLookup, edgar_fund
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
    """Just enough of a BDCEntity for _bdc_portfolio's happy path."""

    def __init__(self, cik=1287750, name="ARES CAPITAL CORP", state="MD", is_active=True):
        self.cik = cik
        self.name = name
        self.state = state
        self.is_active = is_active

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
    """Just enough of a Filing for format_source/paging in _bdc_portfolio.

    ``_load_extraction`` (fund.py) always parses XBRL itself on a cache
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


def _patch_selection(monkeypatch, filing: _FakeFiling, selected_by: str = "latest"):
    monkeypatch.setattr(
        "edgar.ai.mcp.tools.selection.resolve_report_filing",
        lambda **kwargs: FilingSelection(filing=filing, selected_by=selected_by),
    )


def _patch_extraction(monkeypatch, investments: Optional[PortfolioInvestments]):
    monkeypatch.setattr(
        "edgar.bdc.investments.portfolio_investments_from_filing",
        lambda filing, include_untyped=False, xbrl=None: investments,
    )


def _patch_bdc(monkeypatch, bdc: _FakeBDC = None):
    monkeypatch.setattr(
        "edgar.ai.mcp.tools.fund._find_bdc",
        lambda identifier: _BdcLookup(bdc=bdc or _FakeBDC()),
    )


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
        assert result.data["total_investments"] == 0
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
    """`edgar.ai.mcp.tools.fund._find_bdc`: ticker/CIK go through
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

        lookup = fund._find_bdc("845385")

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
        monkeypatch.setattr(fund, "resolve_company", lambda identifier: _FakeCompany(cik=1287750))

        lookup = fund._find_bdc("ARCC")

        assert lookup.bdc is not None
        assert lookup.bdc.cik == 1287750
        assert lookup.ambiguous is None

    def test_ticker_like_identifier_never_reaches_fuzzy_search(self, monkeypatch):
        """A short alphanumeric identifier is a ticker attempt, never a name
        search, even when both `lookup_bdc` and `resolve_company` miss."""

        def _fail_search(*args, **kwargs):
            raise AssertionError("fuzzy search must not run for a ticker-like identifier")

        monkeypatch.setattr("edgar.bdc.reference.lookup_bdc", lambda **kwargs: None)
        monkeypatch.setattr(fund, "resolve_company", lambda identifier: (_ for _ in ()).throw(ValueError("nope")))
        monkeypatch.setattr("edgar.bdc.search.find_bdc", _fail_search)

        lookup = fund._find_bdc("ZZZZZ")

        assert lookup.bdc is None
        assert lookup.ambiguous is None

    def test_ambiguous_name_search_reports_multiple_candidates(self, monkeypatch):
        class _FakeSearchResults:
            empty = False
            results = pd.DataFrame([
                {"cik": 1, "ticker": "AAA", "name": "Alpha BDC", "state": "NY", "is_active": True, "score": 90},
                {"cik": 2, "ticker": None, "name": "Alpha Capital BDC", "state": "CA", "is_active": True, "score": 85},
            ])

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=6: _FakeSearchResults())

        lookup = fund._find_bdc("Alpha Investment Group")

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

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=6: _FakeSearchResults())
        monkeypatch.setattr(
            "edgar.bdc.reference.lookup_bdc",
            lambda cik=None, ticker=None, lookback_years=2: _FakeBDC(cik=cik, name="ARES CAPITAL CORP"),
        )

        lookup = fund._find_bdc("Ares Capital Corporation")

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

        monkeypatch.setattr("edgar.bdc.search.find_bdc", lambda identifier, top_n=6: _FakeSearchResults())

        result = await edgar_fund(action="bdc_portfolio", identifier="Alpha Investment Group")

        assert result.success is False
        assert result.error_code == "AMBIGUOUS_BDC"
        assert len(result.suggestions) == 2
        assert any("Alpha BDC" in s for s in result.suggestions)
        assert any("Alpha Capital BDC" in s for s in result.suggestions)


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
