"""
Regression tests for edgartools-ysr8 (GH #1240, #1241, #1244): three public
`Statement` helpers that had never returned a correct result for any filing.

Each was a small, independent mistake, and the suite never caught any of them
because no test asserted a real result — `analyze_trends`, `_pivot_to_matrix`
and `matrix=True` had zero references in tests/, and the four `calculate_ratios`
hits either mocked the return value or called it without asserting anything.
That appearance of coverage is why these shipped.

  GH #1240  analyze_trends() read period_views[0]['periods']; the producer
            (edgar/xbrl/periods.py generate_period_view) only ever emits
            'period_keys'. Dead lookup -> empty list -> `{}` for every filing.

  GH #1241  The balance-sheet ratios looked up 'us-gaap_CurrentAssets',
            'us-gaap_CurrentLiabilities' and 'us-gaap_Inventory'. The words are
            reversed and none of those is a us-gaap concept, so current_ratio
            and quick_ratio were never computed — indistinguishable from
            "this filing lacks the data".

  GH #1244  _pivot_to_matrix()'s metadata_cols omitted 'standard_concept', which
            the DataFrame builder emits right after 'label'. It therefore became
            period_cols[0], every cell was read from a metadata column, and the
            equity matrix came back all null.

Ground truth is Apple's FY2023 10-K (period ending 2023-09-30), read off the
filed balance sheet, income statement and statement of equity.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

FIXTURE = Path("tests/fixtures/xbrl/aapl/10k_2023")

# Filed values, AAPL FY2023 10-K.
CURRENT_ASSETS = 143_566_000_000.0
CURRENT_LIABILITIES = 145_308_000_000.0
INVENTORIES = 6_331_000_000.0
REVENUE_FY2023 = 383_285_000_000.0
REVENUE_FY2022 = 394_328_000_000.0
GROSS_PROFIT_FY2023 = 169_148_000_000.0
TOTAL_ASSETS_FY2023 = 352_583_000_000.0
TOTAL_ASSETS_FY2022 = 352_755_000_000.0
NET_INCOME_FY2023 = 96_995_000_000.0

# Statement of equity, beginning balances for FY2023 (= FY2022 ending balances).
APIC_BEGINNING = 64_849_000_000.0
RETAINED_EARNINGS_BEGINNING = -3_068_000_000.0
AOCI_BEGINNING = -11_109_000_000.0


@pytest.fixture(scope="module")
def xbrl():
    return XBRL.from_directory(FIXTURE)


# --- GH #1241: calculate_ratios ------------------------------------------


def test_balance_sheet_ratios_are_computed_from_the_real_concepts(xbrl):
    ratios = xbrl.statements.balance_sheet().calculate_ratios()

    assert ratios["current_ratio"] == pytest.approx(
        CURRENT_ASSETS / CURRENT_LIABILITIES
    )
    assert ratios["quick_ratio"] == pytest.approx(
        (CURRENT_ASSETS - INVENTORIES) / CURRENT_LIABILITIES
    )


def test_income_statement_ratios_survive_the_revenue_concept_a_filer_chose(xbrl):
    """Apple tags revenue as RevenueFromContractWithCustomerExcludingAssessedTax,
    not us-gaap:Revenues, so a single hardcoded revenue name answers for only a
    fraction of filings."""
    ratios = xbrl.statements.income_statement().calculate_ratios()

    assert ratios["gross_margin"] == pytest.approx(
        GROSS_PROFIT_FY2023 / REVENUE_FY2023
    )
    assert ratios["net_margin"] == pytest.approx(NET_INCOME_FY2023 / REVENUE_FY2023)


# --- GH #1240: analyze_trends --------------------------------------------


def test_analyze_trends_returns_the_filed_series_not_an_empty_dict(xbrl):
    trends = xbrl.statements.balance_sheet().analyze_trends()

    assert trends, "analyze_trends() returned {} — the period-key lookup is dead again"
    assert trends["total_assets"][:2] == [TOTAL_ASSETS_FY2023, TOTAL_ASSETS_FY2022]
    assert set(trends) >= {"total_assets", "total_liabilities", "equity"}


def test_analyze_trends_reads_a_distinct_value_per_period(xbrl):
    """The failure mode after a naive fix is one value repeated, because the
    per-period filter is not applied."""
    trends = xbrl.statements.income_statement().analyze_trends()

    assert trends["revenue"][:2] == [REVENUE_FY2023, REVENUE_FY2022]
    assert len(set(trends["revenue"])) == len(trends["revenue"])


# --- GH #1244: to_dataframe(matrix=True) ---------------------------------


def test_equity_matrix_is_populated_and_carries_no_metadata_column(xbrl):
    df = xbrl.statements.statement_of_equity().to_dataframe(matrix=True)

    assert not df.empty
    assert "standard_concept" not in df.columns, (
        "standard_concept leaked into the matrix columns; it is metadata, and "
        "as period_cols[0] it made every cell null"
    )

    component_cols = [c for c in df.columns
                      if c not in ("concept", "label", "level", "abstract")]
    assert component_cols, "no equity component columns produced"

    values = df[component_cols]
    assert values.notna().to_numpy().any(), "every matrix cell is null (GH #1244)"

    beginning = df[df["label"] == "Beginning balances"].iloc[0]
    assert beginning["Common stock and additional paid-in capital"] == pytest.approx(
        APIC_BEGINNING
    )
    assert beginning["Retained earnings/(Accumulated deficit)"] == pytest.approx(
        RETAINED_EARNINGS_BEGINNING
    )
    assert beginning["Accumulated other comprehensive income/(loss)"] == pytest.approx(
        AOCI_BEGINNING
    )


# --- Breadth and silence checks ------------------------------------------


@pytest.mark.parametrize(
    "fixture, gross_margin, current_ratio",
    [
        # Filed figures. Apple and Microsoft tag revenue as
        # RevenueFromContractWithCustomerExcludingAssessedTax; Coca-Cola and IBM
        # file a us-gaap:Revenues total.
        ("tests/fixtures/xbrl/msft/10k_2024", 0.6976, 1.2750),
        ("tests/fixtures/xbrl/ko/10k_2024", 0.5952, 1.1341),
        ("tests/fixtures/xbrl/ibm/10k_2024", 0.5665, 1.0404),
        ("tests/fixtures/xbrl/aapl/10k_2010", 0.3520, 2.0113),
    ],
)
def test_ratios_across_filers_and_taxonomy_vintages(fixture, gross_margin, current_ratio):
    x = XBRL.from_directory(Path(fixture))

    assert x.statements.income_statement().calculate_ratios()["gross_margin"] == pytest.approx(
        gross_margin, abs=1e-4
    )
    assert x.statements.balance_sheet().calculate_ratios()["current_ratio"] == pytest.approx(
        current_ratio, abs=1e-4
    )


def test_an_unclassified_balance_sheet_yields_no_ratio_rather_than_a_wrong_one():
    """JPMorgan files an unclassified balance sheet: there is no AssetsCurrent
    and no LiabilitiesCurrent, so there is no current ratio to report. The
    helper must return nothing rather than compute one from whatever it finds."""
    x = XBRL.from_directory(Path("tests/fixtures/xbrl/jpm/10k_2024"))

    ratios = x.statements.balance_sheet().calculate_ratios()

    assert "current_ratio" not in ratios
    assert "quick_ratio" not in ratios
