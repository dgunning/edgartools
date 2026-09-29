"""
Tests for edgar_fund's ``bdc_nonaccrual`` action.

Fast tests monkeypatch filing selection (``resolve_report_filing``) and
extraction (``extract_nonaccrual``) with a hand-built ``NonAccrualResult`` so
the evidence_level mapping, aggregate-case shape, warnings pass-through,
honest-null serialization, and paging/cursor handling are verified without
touching the network. Selection reuses the same ``_resolve_bdc_and_filing``
helper (and fakes) as ``bdc_portfolio`` -- see tests/test_mcp_bdc_portfolio.py.

Network tests pin behaviour against real filings (constraints rule 7a):
- ARCC's 10-Q (CIK 1287750, accession 0001628280-26-050307) runs LIVE, no VCR
  cassette -- its full submission is ~88 MB, an oversized commit.
- Princeton Capital Corp's 10-Q (CIK 845385, accession 0001213900-26-090000)
  is the small-BDC deterministic VCR fixture from Task 3. Its non-accrual
  extraction genuinely returns zero non-accruals (measured 2026-09-28,
  method 'none', 2 warnings) -- the fixture rule says to assert what the
  extraction really returns, not to force a non-empty case onto it.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Optional

import pytest

from edgar import set_identity
from edgar.ai.mcp.tools import continuation
from edgar.ai.mcp.tools.bdc.identity import BdcLookup
from edgar.ai.mcp.tools.continuation import ResultCache
from edgar.ai.mcp.tools.fund import edgar_fund
from edgar.ai.mcp.tools.selection import FilingSelection
from edgar.bdc.nonaccrual import NonAccrualInvestment, NonAccrualResult

from tests.test_mcp_bdc_portfolio import _FakeBDC, _FakeFiling, _patch_bdc, _patch_selection


# =============================================================================
# Fakes / builders
# =============================================================================


def _make_nonaccrual_investment(
    identifier: str,
    company_name: str,
    investment_type: str = "First lien senior secured loan",
    fair_value: Optional[Decimal] = Decimal("1000000"),
    cost: Optional[Decimal] = Decimal("1200000"),
    footnote_text: str = "Loan was on non-accrual status as of June 30, 2026.",
) -> NonAccrualInvestment:
    return NonAccrualInvestment(
        identifier=identifier,
        company_name=company_name,
        investment_type=investment_type,
        fair_value=fair_value,
        cost=cost,
        footnote_text=footnote_text,
    )


def _make_result(
    investments: Optional[list] = None,
    extraction_method: str = "footnote",
    nonaccrual_fair_value: Optional[Decimal] = None,
    total_portfolio_fair_value: Optional[Decimal] = Decimal("1000000000"),
    custom_concept_rate: Optional[float] = None,
    aggregate_concept_value: Optional[Decimal] = None,
    warnings: Optional[list] = None,
    period: str = "2026-06-30",
    cik: int = 1287750,
    entity_name: str = "ARES CAPITAL CORP",
    source_filing: str = "0001628280-26-050307",
) -> NonAccrualResult:
    investments = investments or []
    return NonAccrualResult(
        cik=cik,
        entity_name=entity_name,
        period=period,
        source_filing=source_filing,
        investments=investments,
        nonaccrual_fair_value=nonaccrual_fair_value,
        total_portfolio_fair_value=total_portfolio_fair_value,
        extraction_method=extraction_method,
        custom_concept_rate=custom_concept_rate,
        aggregate_concept_value=aggregate_concept_value,
        warnings=warnings or [],
    )


def _patch_extraction(monkeypatch, result: Optional[NonAccrualResult]) -> list:
    """Patch non-accrual extraction; returns the list of filings it was called with."""
    calls = []

    def _extract(filing):
        calls.append(filing)
        return result

    monkeypatch.setattr("edgar.bdc.nonaccrual.extract_nonaccrual", _extract)
    return calls


@pytest.fixture(autouse=True)
def _isolated_caches(monkeypatch):
    """Fresh result cache per test so extraction-swap tests are deterministic."""
    monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
    monkeypatch.setattr(continuation, "text_cache", ResultCache(max_entries=8, max_bytes=1024 * 1024))


# =============================================================================
# Fast: evidence_level mapping
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestEvidenceLevelMapping:
    async def test_footnote_method_maps_to_investment_evidence_level(self, monkeypatch):
        inv = _make_nonaccrual_investment("Acme Corp - Term Loan", "Acme Corp")
        result = _make_result(
            investments=[inv],
            extraction_method="footnote",
            nonaccrual_fair_value=Decimal("1000000"),
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert response.data["evidence_level"] == "investment"
        assert response.data["extraction_method"] == "footnote"
        assert len(response.data["investments"]) == 1

    async def test_custom_concept_method_maps_to_aggregate_evidence_level(self, monkeypatch):
        result = _make_result(
            investments=[],
            extraction_method="custom_concept",
            custom_concept_rate=0.0173,
            nonaccrual_fair_value=Decimal("17300000"),
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert response.data["evidence_level"] == "aggregate"
        assert response.data["investments"] == []
        assert "portfolio-level" in response.data["note"]

    async def test_aggregate_concept_method_maps_to_aggregate_evidence_level(self, monkeypatch):
        result = _make_result(
            investments=[],
            extraction_method="aggregate_concept",
            aggregate_concept_value=Decimal("5000000"),
            nonaccrual_fair_value=Decimal("5000000"),
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert response.data["evidence_level"] == "aggregate"
        assert response.data["investments"] == []
        assert response.data["aggregate_concept_value"] == 5000000.0

    async def test_none_method_maps_to_none_evidence_level(self, monkeypatch):
        result = _make_result(
            investments=[],
            extraction_method="none",
            nonaccrual_fair_value=None,
            warnings=["No non-accrual data extracted despite a portfolio of $1,000,000,000."],
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert response.data["evidence_level"] == "none"
        assert response.data["investments"] == []
        assert response.data["warnings"] == [
            "No non-accrual data extracted despite a portfolio of $1,000,000,000."
        ]


# =============================================================================
# Fast: honest gaps, verbatim warnings, fixed interpretation_limits
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestHonestGapsAndFixedFields:
    async def test_missing_numeric_fields_serialize_as_null_not_zero(self, monkeypatch):
        inv = _make_nonaccrual_investment(
            "Bare Co - Term Loan", "Bare Co", fair_value=None, cost=None
        )
        result = _make_result(investments=[inv], extraction_method="footnote")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        record = response.data["investments"][0]
        assert record["fair_value"] is None
        assert record["cost"] is None

    async def test_total_portfolio_fair_value_null_when_extraction_has_none(self, monkeypatch):
        result = _make_result(
            investments=[],
            extraction_method="none",
            total_portfolio_fair_value=None,
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["total_portfolio_fair_value"] is None
        assert response.data["nonaccrual_rate"] is None

    async def test_warnings_surfaced_verbatim(self, monkeypatch):
        warnings = ["First warning message.", "Second warning message."]
        result = _make_result(investments=[], extraction_method="none", warnings=warnings)
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["warnings"] == warnings

    async def test_interpretation_limits_is_the_fixed_string(self, monkeypatch):
        result = _make_result(investments=[], extraction_method="none")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["interpretation_limits"] == (
            "Non-accrual is an accounting status (interest income no longer recognized), "
            "not a legal default determination. Absence from this list does not establish "
            "that a loan is performing. Aggregate evidence is not attributed to individual "
            "borrowers."
        )
        assert response.data["rate_convention"] == "decimal_fraction"

    async def test_unique_footnote_texts_deduplicated(self, monkeypatch):
        inv1 = _make_nonaccrual_investment(
            "Co A - Loan", "Co A", footnote_text="Loan was on non-accrual status."
        )
        inv2 = _make_nonaccrual_investment(
            "Co B - Loan", "Co B", footnote_text="Loan was on non-accrual status."
        )
        result = NonAccrualResult(
            cik=1287750,
            entity_name="ARES CAPITAL CORP",
            period="2026-06-30",
            source_filing="0001628280-26-050307",
            investments=[inv1, inv2],
            nonaccrual_fair_value=Decimal("2000000"),
            total_portfolio_fair_value=Decimal("1000000000"),
            extraction_method="footnote",
            warnings=[],
        )
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["unique_footnote_texts"] == ["Loan was on non-accrual status."]


# =============================================================================
# Fast: NO_XBRL silence check
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestNoXbrl:
    async def test_extract_nonaccrual_none_returns_no_xbrl_error(self, monkeypatch):
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, None)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is False
        assert response.error_code == "NO_XBRL"

    async def test_missing_identifier_and_accession_is_invalid_arguments(self):
        response = await edgar_fund(action="bdc_nonaccrual")

        assert response.success is False
        assert response.error_code == "INVALID_ARGUMENTS"


# =============================================================================
# Fast: paging + cursor errors
# =============================================================================


def _make_investment_batch(n: int) -> list:
    return [
        _make_nonaccrual_investment(f"Company {i} - Term Loan", f"Company {i}")
        for i in range(n)
    ]


@pytest.mark.fast
@pytest.mark.asyncio
class TestPaging:
    async def test_walks_all_records_exactly_once_and_ends_with_null_cursor(self, monkeypatch):
        investments = _make_investment_batch(7)
        result = _make_result(investments=investments, extraction_method="footnote")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        seen_identifiers = []
        cursor = None
        pages = 0
        while True:
            response = await edgar_fund(
                action="bdc_nonaccrual", identifier="ARCC", limit=3, cursor=cursor
            )
            assert response.success is True
            pages += 1
            seen_identifiers.extend(rec["identifier"] for rec in response.data["investments"])
            cursor = response.data["page"]["next_cursor"]
            if cursor is None:
                break
            assert pages < 10  # guard against an infinite loop bug

        assert pages == 3  # 3 + 3 + 1
        assert len(seen_identifiers) == 7
        assert len(set(seen_identifiers)) == 7

    async def test_next_cursor_null_when_everything_fits_on_one_page(self, monkeypatch):
        investments = _make_investment_batch(3)
        result = _make_result(investments=investments, extraction_method="footnote")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=20)

        assert response.data["page"]["next_cursor"] is None
        assert response.data["page"]["remaining"] == 0
        assert "note" not in response.data


@pytest.mark.fast
@pytest.mark.asyncio
class TestCursorErrors:
    async def test_cursor_mismatch_on_different_accession(self, monkeypatch):
        investments = _make_investment_batch(5)
        result = _make_result(investments=investments, extraction_method="footnote")
        filing = _FakeFiling(accession_number="0001628280-26-050307")
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=2)
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        other_filing = _FakeFiling(accession_number="0000000000-00-000000")
        _patch_selection(monkeypatch, other_filing)

        second = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=2, cursor=cursor)

        assert second.success is False
        assert second.error_code == "CURSOR_MISMATCH"

    async def test_cursor_stale_when_underlying_extraction_changes(self, monkeypatch):
        investments_v1 = _make_investment_batch(5)
        result_v1 = _make_result(investments=investments_v1, extraction_method="footnote")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result_v1)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=2)
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        # Simulate a process restart / cache eviction with a changed extraction.
        monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
        investments_v2 = [_make_nonaccrual_investment("Totally Different Co - Loan", "Different")]
        result_v2 = _make_result(investments=investments_v2, extraction_method="footnote")
        _patch_extraction(monkeypatch, result_v2)

        second = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=2, cursor=cursor)

        assert second.success is False
        assert second.error_code == "CURSOR_STALE"

    @pytest.mark.parametrize("field,value", [
        ("fair_value", Decimal("1234567")),
        ("fair_value", None),
        ("cost", Decimal("7654321")),
        ("investment_type", "Preferred equity"),
        ("footnote_text", "Interest payments were suspended."),
    ])
    async def test_cursor_stale_when_evidence_changes_with_stable_identifiers(self, monkeypatch, field, value):
        investments = _make_investment_batch(2)
        result = _make_result(investments=investments, extraction_method="footnote")
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        first = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=1)
        assert first.data["investments"][0]["fair_value"] == 1000000
        cursor = first.data["page"]["next_cursor"]
        assert cursor is not None

        identifiers = [inv.identifier for inv in investments]
        changed = [replace(investments[0], **{field: value}), investments[1]]
        assert [inv.identifier for inv in changed] == identifiers
        monkeypatch.setattr(continuation, "results_cache", ResultCache(max_entries=8))
        _patch_extraction(monkeypatch, _make_result(investments=changed, extraction_method="footnote"))

        second = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=1, cursor=cursor)
        assert second.success is False
        assert second.error_code == "CURSOR_STALE"

    async def test_invalid_cursor_on_garbage_input(self, monkeypatch):
        investments = _make_investment_batch(2)
        result = _make_result(investments=investments, extraction_method="footnote")
        filing = _FakeFiling()
        _patch_selection(monkeypatch, filing)
        _patch_extraction(monkeypatch, result)
        _patch_bdc(monkeypatch)

        response = await edgar_fund(
            action="bdc_nonaccrual", identifier="ARCC", cursor="!!!not-a-real-cursor!!!"
        )

        assert response.success is False
        assert response.error_code == "INVALID_CURSOR"


# =============================================================================
# Fast: QA fix wave Q2 -- unknown-is-null (P1-M4) and cursor-only
# continuation (P1-H2 / rule 7b)
# =============================================================================


@pytest.mark.fast
@pytest.mark.asyncio
class TestPatchSeamsAreLive:
    """Q2 fix round 1: the non-accrual code moved into
    edgar/ai/mcp/tools/bdc/nonaccrual.py. Prove the patched resolution,
    selection and extraction seams are the ones actually called."""

    async def test_nonaccrual_uses_patched_resolution_selection_and_extraction(self, monkeypatch):
        bdc_calls = _patch_bdc(monkeypatch)
        selection_calls = _patch_selection(monkeypatch, _FakeFiling())
        extraction_calls = _patch_extraction(monkeypatch, _make_result(investments=_make_investment_batch(2)))

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert bdc_calls == ["ARCC"]
        assert len(selection_calls) == 1
        assert len(extraction_calls) == 1
        assert response.data["num_nonaccrual"] == 2


@pytest.mark.fast
@pytest.mark.asyncio
class TestUnknownCountIsNull:
    @pytest.mark.parametrize("method,kwargs", [
        ("aggregate_concept", {"aggregate_concept_value": Decimal("250000000"),
                               "nonaccrual_fair_value": Decimal("250000000")}),
        ("custom_concept", {"custom_concept_rate": 0.0173, "nonaccrual_fair_value": Decimal("17300000")}),
        ("none", {}),
    ])
    async def test_count_and_page_totals_null_without_investment_evidence(self, monkeypatch, method, kwargs):
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_result(investments=[], extraction_method=method, **kwargs))
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.success is True
        assert response.data["evidence_level"] in ("aggregate", "none")
        assert response.data["num_nonaccrual"] is None
        assert response.data["page"]["total_matching"] is None
        assert response.data["page"]["total_extracted"] is None
        assert response.data["page"]["returned"] == 0
        assert response.data["investments"] == []

    async def test_aggregate_value_is_kept_alongside_the_null_count(self, monkeypatch):
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_result(
            investments=[], extraction_method="aggregate_concept",
            aggregate_concept_value=Decimal("250000000"), nonaccrual_fair_value=Decimal("250000000"),
        ))
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["num_nonaccrual"] is None
        assert response.data["nonaccrual_fair_value"] == 250000000.0

    async def test_investment_evidence_keeps_the_count(self, monkeypatch):
        investments = _make_investment_batch(3)
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_result(investments=investments, extraction_method="footnote"))
        _patch_bdc(monkeypatch)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["num_nonaccrual"] == 3
        assert response.data["page"]["total_matching"] == 3
        assert response.data["page"]["total_extracted"] == 3


@pytest.mark.fast
@pytest.mark.asyncio
class TestCursorOnlyContinuation:
    @staticmethod
    def _setup(monkeypatch, n=7):
        from tests.test_mcp_bdc_portfolio import _patch_lookup_bdc_by_cik, _patch_selection_by_accession

        calls = _patch_selection_by_accession(monkeypatch, [_FakeFiling()])
        _patch_extraction(monkeypatch, _make_result(investments=_make_investment_batch(n), extraction_method="footnote"))
        _patch_bdc(monkeypatch)
        _patch_lookup_bdc_by_cik(monkeypatch)
        return calls

    async def test_cursor_alone_walks_all_records(self, monkeypatch):
        calls = self._setup(monkeypatch, n=45)

        first = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", form="10-Q", period="2026-06-30", limit=5)
        seen = [rec["identifier"] for rec in first.data["investments"]]
        cursor = first.data["page"]["next_cursor"]
        pages = 1
        while cursor is not None:
            nxt = await edgar_fund(action="bdc_nonaccrual", cursor=cursor)
            assert nxt.success is True, (nxt.error_code, nxt.error)
            seen.extend(rec["identifier"] for rec in nxt.data["investments"])
            cursor = nxt.data["page"]["next_cursor"]
            pages += 1
            assert pages < 10

        assert pages == 3  # 5 + 20 + 20
        assert seen == [f"Company {i} - Term Loan" for i in range(45)]
        assert all(c["accession_number"] == "0001628280-26-050307" for c in calls[1:])

    async def test_identifier_for_a_different_bdc_is_selection_mismatch(self, monkeypatch):
        self._setup(monkeypatch)
        first = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC", limit=2)
        monkeypatch.setattr(
            "edgar.ai.mcp.tools.bdc.identity.resolve_bdc",
            lambda identifier: BdcLookup(bdc=_FakeBDC(cik=1396440, name="MAIN STREET CAPITAL CORP")),
        )

        nxt = await edgar_fund(action="bdc_nonaccrual", identifier="MAIN", cursor=first.data["page"]["next_cursor"])

        assert nxt.success is False
        assert nxt.error_code == "SELECTION_MISMATCH"

    async def test_a_portfolio_cursor_is_rejected_before_any_selection(self, monkeypatch):
        calls = self._setup(monkeypatch)
        portfolio_cursor = continuation.encode_cursor(
            tool="edgar_fund:bdc_portfolio", accession="0001628280-26-050307", offset=20, fp="abc",
            query={"borrower": None, "include_untyped": False},
        )

        response = await edgar_fund(action="bdc_nonaccrual", cursor=portfolio_cursor)

        assert response.success is False
        assert response.error_code == "CURSOR_MISMATCH"
        assert calls == []

    async def test_identity_block_carries_bdc_report_year(self, monkeypatch):
        _patch_selection(monkeypatch, _FakeFiling())
        _patch_extraction(monkeypatch, _make_result(investments=_make_investment_batch(1)))
        _patch_bdc(monkeypatch, _FakeBDC(report_year=2026))
        monkeypatch.setattr("edgar.bdc.reference.get_latest_bdc_report_year", lambda: 2026)

        response = await edgar_fund(action="bdc_nonaccrual", identifier="ARCC")

        assert response.data["bdc_report_year"] == 2026
        assert response.data["is_active"] is True


# =============================================================================
# Network: ARCC (live, no VCR -- constraints rule 7a)
# =============================================================================

ARCC_CIK = 1287750
ARCC_10Q_ACCESSION = "0001628280-26-050307"

PRINCETON_CIK = 845385
PRINCETON_10Q_ACCESSION = "0001213900-26-090000"


@pytest.mark.network
@pytest.mark.asyncio
class TestBdcNonaccrualARCCLive:
    """Runs live, no VCR cassette (constraints rule 7a): ARCC's 10-Q submission
    is ~88 MB. Ground truth (measured 2026-09-28, constraints doc): method
    'footnote', 32 investments, 0 warnings.
    """

    async def test_period_selects_ground_truth_filing_and_footnote_evidence(self):
        set_identity("Test User test@test.com")

        response = await edgar_fund(
            action="bdc_nonaccrual", identifier="ARCC", form="10-Q", period="2026-06-30"
        )

        assert response.success is True
        assert response.data["extraction_method"] == "footnote"
        assert response.data["evidence_level"] == "investment"
        assert response.data["num_nonaccrual"] == 32
        assert response.data["warnings"] == []
        assert response.data["source"]["accession_number"] == ARCC_10Q_ACCESSION
        assert response.data["cik"] == ARCC_CIK
        # P1-M5: ARCC is only in the 2025 BDC Report (measured 2026-09-29);
        # is_active comes from its own latest filing, not that stale row.
        assert response.data["bdc_report_year"] == 2025
        assert response.data["is_active"] is True

    async def test_hand_verified_investment_identifier_and_footnote(self):
        set_identity("Test User test@test.com")

        response = await edgar_fund(
            action="bdc_nonaccrual", identifier="ARCC", form="10-Q", period="2026-06-30", limit=50
        )

        assert response.success is True
        matches = [
            rec for rec in response.data["investments"]
            if rec["identifier"] == "KBHS Acquisition, LLC (d/b/a Alita Care, LLC) | First lien senior secured revolving loan"
        ]
        assert len(matches) == 1
        assert matches[0]["footnote_text"] == "Loan was on non-accrual status as of June 30, 2026."
        assert matches[0]["fair_value"] == 2500000.0
        assert matches[0]["cost"] == 4100000.0

    async def test_walking_all_pages_returns_full_count_with_no_duplicates(self):
        set_identity("Test User test@test.com")

        seen = set()
        cursor = None
        total_returned = 0
        while True:
            response = await edgar_fund(
                action="bdc_nonaccrual",
                identifier="ARCC",
                form="10-Q",
                period="2026-06-30",
                limit=10,
                cursor=cursor,
            )
            assert response.success is True
            for rec in response.data["investments"]:
                key = rec["identifier"]
                assert key not in seen, f"duplicate record across pages: {key}"
                seen.add(key)
            total_returned += response.data["page"]["returned"]
            cursor = response.data["page"]["next_cursor"]
            if cursor is None:
                break

        assert total_returned == 32
        assert len(seen) == 32


# =============================================================================
# Network: Princeton (VCR fixture -- constraints rule 7a / Task 3)
# =============================================================================


@pytest.mark.network
@pytest.mark.vcr
@pytest.mark.asyncio
class TestBdcNonaccrualPrincetonVCR:
    """Deterministic small-BDC VCR fixture (constraints rule 7a / Task 3).

    Princeton Capital Corp's 10-Q genuinely has no extractable non-accrual
    signal (measured 2026-09-28): extraction_method 'none', 0 investments,
    and two data-quality warnings (a recognized non-accrual footnote whose
    linkage did not resolve any investment for this period, plus the
    "portfolio exists but nothing extracted" check). The fixture rule says to
    assert what the extraction really returns, not to force a non-empty case.

    Uses `accession_number=` (not identifier + period): the ticker-based
    resolution path pulls SEC's company_tickers.json (~2 MB) on a cold cache,
    which pushed an earlier bdc_portfolio cassette over the 10 MB cap (see
    tests/test_mcp_bdc_portfolio.py's TestBdcPortfolioPrincetonVCR docstring).
    """

    async def test_accession_selects_princeton_filing_with_no_extractable_signal(self):
        set_identity("Test User test@test.com")

        response = await edgar_fund(
            action="bdc_nonaccrual", accession_number=PRINCETON_10Q_ACCESSION
        )

        assert response.success is True
        assert response.data["cik"] == PRINCETON_CIK
        assert response.data["source"]["accession_number"] == PRINCETON_10Q_ACCESSION
        assert response.data["source"]["selected_by"] == "accession"
        assert response.data["period"] == "2026-06-30"
        assert response.data["extraction_method"] == "none"
        assert response.data["evidence_level"] == "none"
        # P1-M4: no investment-level evidence means the count is unknown
        # (null), not "zero loans on non-accrual".
        assert response.data["num_nonaccrual"] is None
        assert response.data["page"]["total_matching"] is None
        assert response.data["bdc_report_year"] == 2026
        assert response.data["investments"] == []
        assert response.data["nonaccrual_fair_value"] is None
        assert response.data["total_portfolio_fair_value"] == 24679396.0
        assert response.data["nonaccrual_rate"] is None
        assert response.data["warnings"] == [
            "Recognized 1 non-accrual footnote(s) but resolved no investments for "
            "period 2026-06-30; investment-level detail may be incomplete (possible "
            "period or linkage mismatch).",
            "No non-accrual data extracted despite a portfolio of $24,679,396; "
            "verify manually — this may indicate a parsing gap rather than "
            "genuinely zero non-accruals.",
        ]
