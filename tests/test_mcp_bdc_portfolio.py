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

from decimal import Decimal
from typing import Optional

import pytest

from edgar import set_identity
from edgar.ai.mcp.tools import continuation
from edgar.ai.mcp.tools.continuation import ResultCache
from edgar.ai.mcp.tools.fund import edgar_fund
from edgar.ai.mcp.tools.selection import FilingSelection, FilingSelectionError
from edgar.bdc.investments import PortfolioInvestment, PortfolioInvestments


# =============================================================================
# Fakes
# =============================================================================


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

    ``xbrl()`` raises by default — proving the structured-data (happy) path
    never calls it, since portfolio_investments_from_filing is monkeypatched
    directly. Tests that exercise the no-structured-data fallback pass
    ``xbrl_result`` explicitly.
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
        xbrl_result="__raise__",
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
        self._xbrl_result = xbrl_result

    def xbrl(self):
        if self._xbrl_result == "__raise__":
            raise AssertionError(
                "filing.xbrl() was called on the structured-data path — "
                "portfolio_investments_from_filing is monkeypatched and should "
                "make this unnecessary"
            )
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
        lambda filing, include_untyped=False: investments,
    )


def _patch_bdc(monkeypatch, bdc: _FakeBDC = None):
    monkeypatch.setattr(
        "edgar.ai.mcp.tools.fund._find_bdc",
        lambda identifier: bdc or _FakeBDC(),
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
        filing = _FakeFiling(cik=320193, accession_number="0000320193-24-000001")
        _patch_selection(monkeypatch, filing)
        monkeypatch.setattr("edgar.bdc.reference.is_bdc_cik", lambda cik: False)

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
# Network + live (ARCC — no VCR, constraints rule 7a) and VCR (Princeton)
# =============================================================================

ARCC_CIK = 1287750
ARCC_10Q_ACCESSION = "0001628280-26-050307"
ARCC_10Q_HOLDING_COUNT = 1481

PRINCETON_CIK = 845385
PRINCETON_10Q_ACCESSION = "0001213900-26-090000"
PRINCETON_10Q_HOLDING_COUNT = 23


def _patch_find_bdc_for_arcc(monkeypatch):
    """Work around a discovered, pre-existing SEC-dataset gap (see task report):
    the SEC's 2026 BDC Report CSV (the one `get_bdc_list()`/`is_bdc_cik()`
    consult) omits Ares Capital Corp (CIK 1287750) entirely, though it is
    present in the 2024 and 2025 reports. That means `identifier='ARCC'`
    cannot resolve via the unchanged `_find_bdc` lookup chain in the current
    live environment -- not a regression from this task (the lookup chain is
    a straight extraction of the pre-existing logic) and not something this
    task's brief asks it to fix. This patches only BDC-name/ticker
    resolution with the same hand-built BDCEntity Task 3's own tests use for
    ARCC; filing selection, extraction, and paging below all still run live.
    """
    from edgar.bdc.reference import BDCEntity

    arcc = BDCEntity(file_number="814-00663", cik=ARCC_CIK, name="ARES CAPITAL CORP")
    monkeypatch.setattr("edgar.ai.mcp.tools.fund._find_bdc", lambda identifier: arcc)


@pytest.mark.network
@pytest.mark.asyncio
class TestBdcPortfolioARCCLive:
    """Runs live, no VCR cassette (constraints rule 7a): ARCC's 10-Q submission
    is ~88 MB. The in-process results_cache means only the first extraction in
    this class pays the ~11-13s XBRL-parse cost; later tests in the same run
    reuse the cached PortfolioInvestments for this accession.

    `_find_bdc` is patched for ARCC specifically (see `_patch_find_bdc_for_arcc`)
    to work around a discovered SEC-dataset gap unrelated to this task; filing
    selection, extraction, and paging are exercised live and unmocked.
    """

    async def test_period_selects_ground_truth_filing_and_full_count(self, monkeypatch):
        set_identity("Test User test@test.com")
        _patch_find_bdc_for_arcc(monkeypatch)

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-30"
        )

        assert result.success is True
        assert result.data["total_investments"] == ARCC_10Q_HOLDING_COUNT
        assert result.data["source"]["accession_number"] == ARCC_10Q_ACCESSION
        assert result.data["source"]["selected_by"] == "period"

    async def test_borrower_filter_finds_ivy_hill_despite_wrong_company_name(self, monkeypatch):
        set_identity("Test User test@test.com")
        _patch_find_bdc_for_arcc(monkeypatch)

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

    async def test_walking_all_pages_returns_full_count_with_no_duplicates(self, monkeypatch):
        set_identity("Test User test@test.com")
        _patch_find_bdc_for_arcc(monkeypatch)

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

    async def test_period_off_by_one_day_is_period_not_found(self, monkeypatch):
        set_identity("Test User test@test.com")
        _patch_find_bdc_for_arcc(monkeypatch)

        result = await edgar_fund(
            action="bdc_portfolio", identifier="ARCC", form="10-Q", period="2026-06-29"
        )

        assert result.success is False
        assert result.error_code == "PERIOD_NOT_FOUND"


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
