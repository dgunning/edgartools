"""
Regression tests for edgartools-i24a: get_structured_statement(fiscal_period='FY')
could return the prior-year comparative instant.

Bead: edgartools-i24a
GitHub Discussion: https://github.com/dgunning/edgartools/discussions/946

In SEC companyfacts a 10-K tags fp="FY" and fy=<year> on EVERY instant it
reports, prior-year comparatives included, and every fact in the filing shares
one filing_date. Apple's FY2023 10-K (accession 0000320193-23-000106) therefore
carries two Assets instants both tagged fy=2023 fp=FY:

    end=2022-09-24  352,755,000,000   <- the FY2022 comparative
    end=2023-09-30  352,583,000,000   <- the figure the filing reports

StatementBuilder._create_fact_map deduped on filing_date alone. The dates tie,
so `fact.filing_date > fact_map[concept].filing_date` is False and whichever
fact the list happened to yield first won -- the comparative. _get_period_end
had the same shape, returning the FIRST period_end it saw as the period the
statement claims to cover.

The wrong value is within 0.05% of the right one, which is why no sanity check
anywhere fired on it.
"""

from datetime import date

import pytest

from edgar.entity.enhanced_statement import validate_fiscal_year_period_end
from edgar.entity.models import FinancialFact
from edgar.entity.statement_builder import StatementBuilder

FILED = date(2023, 11, 3)
FY2023_END = date(2023, 9, 30)
FY2022_END = date(2022, 9, 24)

ASSETS_FY2023 = 352_583_000_000.0
ASSETS_FY2022 = 352_755_000_000.0


def _instant(concept: str, value: float, period_end: date,
             filing_date: date = FILED,
             statement_type: str = "BalanceSheet") -> FinancialFact:
    """An instant fact as companyfacts delivers it: fp=FY, fy=2023, on both the
    reported period and the comparative."""
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=value,
        unit="USD",
        period_type="instant",
        period_end=period_end,
        fiscal_year=2023,
        fiscal_period="FY",
        filing_date=filing_date,
        statement_type=statement_type,
    )


@pytest.fixture
def builder():
    return StatementBuilder()


# --- the dedup gap the suite never covered --------------------------------


def test_same_filing_date_different_period_end_keeps_the_reported_period(builder):
    """The existing coverage (test_create_fact_map_keeps_recent_duplicate) only
    varied filing_date. Every fact in one accession shares a filing_date, so
    that case could never expose this."""
    facts = [
        _instant("Assets", ASSETS_FY2022, FY2022_END),  # comparative, listed first
        _instant("Assets", ASSETS_FY2023, FY2023_END),
    ]

    result = builder._create_fact_map(facts)

    assert result["Assets"].numeric_value == ASSETS_FY2023
    assert result["Assets"].period_end == FY2023_END


def test_the_winner_does_not_depend_on_list_order(builder):
    """First-seen-wins is what made this a coin flip."""
    comparative = _instant("Assets", ASSETS_FY2022, FY2022_END)
    reported = _instant("Assets", ASSETS_FY2023, FY2023_END)

    for ordering in ([comparative, reported], [reported, comparative]):
        assert builder._create_fact_map(ordering)["Assets"].numeric_value == ASSETS_FY2023


def test_filing_date_still_outranks_period_end(builder):
    """An amended filing restating an earlier period must still win: filing
    recency is the primary key, period_end only breaks its ties."""
    original = _instant("Assets", ASSETS_FY2023, FY2023_END, filing_date=FILED)
    restated = _instant("Assets", 999.0, FY2022_END, filing_date=date(2024, 2, 1))

    assert builder._create_fact_map([original, restated])["Assets"].numeric_value == 999.0


def test_a_fact_with_no_period_end_does_not_displace_one_that_has_it(builder):
    undated = _instant("Assets", 1.0, None)
    dated = _instant("Assets", ASSETS_FY2023, FY2023_END)

    assert builder._create_fact_map([dated, undated])["Assets"].numeric_value == ASSETS_FY2023
    assert builder._create_fact_map([undated, dated])["Assets"].numeric_value == ASSETS_FY2023


# --- the period the statement claims to cover -----------------------------


def test_period_end_is_the_reported_period_not_the_first_one_seen(builder):
    facts = [
        _instant("Assets", ASSETS_FY2022, FY2022_END),
        _instant("Assets", ASSETS_FY2023, FY2023_END),
    ]

    assert builder._get_period_end(facts) == FY2023_END


def test_period_end_is_none_when_no_fact_carries_one(builder):
    assert builder._get_period_end([_instant("Assets", 1.0, None)]) is None
    assert builder._get_period_end([]) is None


# --- the fiscal-year validator is told the company's FYE ------------------


def test_a_comparative_tagged_with_the_wrong_fiscal_year_is_still_rejected():
    """The fiscal-year validator's own job, unchanged by this fix and asserted
    here because _create_fact_map now leans on period_end the same way."""
    assert validate_fiscal_year_period_end(2023, FY2022_END, 9) is False


def test_the_validator_tolerates_a_52_53_week_year_end_crossing_a_month():
    """Recorded while fixing this bead, and the reason build_multi_period_statement
    is NOT passing its detected fiscal-year-end month to this validator.

    Marvell's fiscal years end 2024-02-03, 2025-02-01 and 2026-01-31 -- a 52/53
    week calendar that straddles the January/February boundary.
    detect_fiscal_year_end() takes the most common month and returns 1, so
    passing it here rejects the two year ends that land in February. The
    validator needs month-boundary tolerance before that argument can be
    supplied; see the bead.
    """
    from edgar.entity.enhanced_statement import detect_fiscal_year_end  # noqa: F401

    # The February year end of a January-FYE filer, which strict month matching
    # rejects and the current default admits.
    assert validate_fiscal_year_period_end(2025, date(2025, 2, 1)) is True
    assert validate_fiscal_year_period_end(2025, date(2025, 2, 1), 1) is False


# --- ground truth from the live filing ------------------------------------


@pytest.mark.network
def test_apple_fy2023_balance_sheet_reports_fy2023():
    """The reported case. Apple's FY2023 balance sheet came back with
    period_end 2022-09-24 and every figure from the comparative column."""
    from edgar import Company

    statement = Company("AAPL").get_structured_statement(
        "BalanceSheet", fiscal_year=2023, fiscal_period="FY"
    )

    assert statement.period_end == FY2023_END

    values = {(item.concept or "").split(":")[-1]: item.value for item in statement.items}

    # Total assets 352,583 less current assets 143,566, both as filed for FY2023.
    # The FY2022 comparative gives 217,350, which is what this returned before.
    assert values["AssetsNoncurrent"] == 209_017_000_000.0
