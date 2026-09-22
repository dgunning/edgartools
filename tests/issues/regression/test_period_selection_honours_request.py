"""
Regression tests for GH #1222, #1246 and #1221 — three places where statement
and period selection accepted what the caller asked for and then quietly
returned something else.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1222
GitHub Issue: https://github.com/dgunning/edgartools/issues/1246
GitHub Issue: https://github.com/dgunning/edgartools/issues/1221
Beads: edgartools-rj4b, edgartools-zt8u, edgartools-z0y2

  GH #1222 (bead edgartools-rj4b)  select_periods(max_periods=N) never re-applied the cap.
        The selectors deliberately over-fetch to N*3 (issue #464) so that
        data-quality filtering has candidates to choose between, but that filter
        only REMOVES periods below the threshold — it never truncates. For a
        healthy filing where every candidate has sufficient data, nothing
        narrowed the over-fetch and up to 3N periods came back. Microsoft's
        FY2024 balance sheet returned 10 periods for max_periods=4.

  GH #1246 (bead edgartools-zt8u)  get_period_views()'s instant branch had no
        fact-sufficiency filter, though the duration branch three lines below
        filters. An incidental instant — a context the filing declares but
        reports no balance-sheet facts against — took a column slot and pushed
        out the populated prior fiscal year. The default (unnamed-view) path
        already filters, which is exactly why the two paths disagreed.

  GH #1221 (bead edgartools-z0y2)  parenthetical=True was silently ignored. The resolver's
        standard-name matcher sits first at 0.95 confidence against a 0.9
        threshold and never inspected the flag, and two later matchers score on
        content and role text alone — they cannot tell a parenthetical role from
        the face statement, yet answered at 0.85 against a 0.6 threshold. The
        caller got a correct-looking statement with no sign the flag was dropped.
"""

from pathlib import Path

import pytest

from edgar.exceptions import StatementNotFoundError
from edgar.xbrl import XBRL
from edgar.xbrl.period_selector import select_periods

AAPL_10K = Path("tests/fixtures/xbrl/aapl/10k_2023")
MSFT_10K = Path("tests/fixtures/xbrl/msft/10k_2024")
KO_10K = Path("tests/fixtures/xbrl/ko/10k_2024")
NFLX_10Q = Path("tests/fixtures/xbrl/nflx/10q_2024")

METADATA_COLUMNS = {
    "concept", "label", "standard_concept", "level", "abstract", "dimension",
    "is_breakdown", "dimension_axis", "dimension_member", "dimension_member_label",
    "dimension_label", "balance", "weight", "preferred_sign", "parent_concept",
    "parent_abstract_concept", "unit", "point_in_time",
}


def _period_columns(df):
    return [c for c in df.columns if c not in METADATA_COLUMNS]


# --- GH #1222: the cap is honoured -----------------------------------------


@pytest.mark.parametrize("fixture", [MSFT_10K, KO_10K, AAPL_10K, NFLX_10Q])
@pytest.mark.parametrize("statement_type", ["BalanceSheet", "IncomeStatement", "CashFlowStatement"])
@pytest.mark.parametrize("max_periods", [1, 2, 3, 4])
def test_select_periods_never_exceeds_max_periods(fixture, statement_type, max_periods):
    periods = select_periods(XBRL.from_directory(fixture), statement_type, max_periods=max_periods)

    assert len(periods) <= max_periods, (
        f"{fixture.parent.name} {statement_type}: asked for at most {max_periods}, "
        f"got {len(periods)} — the N*3 over-fetch was never narrowed back"
    )


def test_the_cap_is_applied_where_filtering_removes_nothing():
    """The guard that matters. A filing where data-quality filtering happens to
    cut the candidates back to N would pass a naive test while the bug is still
    present, so this asserts on a filing that has MORE qualifying instants than
    were asked for: this one returned 10 periods for max_periods=4, 6 for 2 and
    4 for 1."""
    xbrl = XBRL.from_directory(Path("data/xbrl/datafiles/msft"))

    assert len(select_periods(xbrl, "BalanceSheet", max_periods=4)) == 4
    assert len(select_periods(xbrl, "BalanceSheet", max_periods=2)) == 2
    assert len(select_periods(xbrl, "BalanceSheet", max_periods=1)) == 1


def test_capping_keeps_the_most_recent_periods_not_an_arbitrary_slice():
    """Candidates arrive in priority order, so the cap must keep the head."""
    xbrl = XBRL.from_directory(MSFT_10K)

    capped = select_periods(xbrl, "BalanceSheet", max_periods=2)
    uncapped_head = select_periods(xbrl, "BalanceSheet", max_periods=4)[:2]

    assert capped == uncapped_head
    assert capped[0][0] == "instant_2024-06-30"


# --- GH #1246: named views carry real periods ------------------------------


@pytest.mark.parametrize(
    "fixture, expected",
    [
        # (current instant, true prior fiscal-year instant)
        (MSFT_10K, ("instant_2024-06-30", "instant_2023-06-30")),
        (KO_10K, ("instant_2023-12-31", "instant_2022-12-31")),
    ],
)
def test_named_balance_sheet_view_uses_the_prior_fiscal_year_not_an_incidental_instant(fixture, expected):
    xbrl = XBRL.from_directory(fixture)

    view = next(v for v in xbrl.get_period_views("BalanceSheet")
                if v["name"] == "Current vs. Previous Period")

    assert tuple(view["period_keys"]) == expected


@pytest.mark.parametrize("fixture", [MSFT_10K, KO_10K])
def test_every_column_of_a_named_view_carries_facts(fixture):
    """The user-visible symptom: an empty column where the comparative belongs."""
    xbrl = XBRL.from_directory(fixture)
    balance_sheet = xbrl.statements.balance_sheet()

    df = balance_sheet.to_dataframe(period_view="Current vs. Previous Period")

    for column in _period_columns(df):
        assert df[column].notna().sum() > 0, (
            f"column {column!r} is entirely empty — an incidental instant took "
            f"the slot that belongs to the prior fiscal year (GH #1246)"
        )


@pytest.mark.parametrize("fixture", [MSFT_10K, KO_10K])
def test_the_named_view_and_the_default_view_agree(fixture):
    """The two paths disagreeing is the underlying problem: only one of them
    filtered for statement-aware fact sufficiency."""
    xbrl = XBRL.from_directory(fixture)
    balance_sheet = xbrl.statements.balance_sheet()

    named = _period_columns(balance_sheet.to_dataframe(period_view="Current vs. Previous Period"))
    default = _period_columns(balance_sheet.to_dataframe())

    assert named == default


# --- GH #1221: parenthetical=True is honoured or refused -------------------


@pytest.mark.parametrize("fixture", [AAPL_10K, MSFT_10K, KO_10K])
def test_parenthetical_balance_sheet_resolves_to_the_parenthetical_role(fixture):
    xbrl = XBRL.from_directory(fixture)

    main = xbrl.statements.balance_sheet()
    parenthetical = xbrl.statements.balance_sheet(parenthetical=True)

    assert parenthetical is not None
    assert parenthetical.role_or_type != main.role_or_type
    assert "arenthetical" in parenthetical.role_or_type.lower() or \
           "parenthetical" in parenthetical.role_or_type.lower()


def test_the_default_request_still_prefers_the_face_statement():
    """bead edgartools-8ad8: the -80 parenthetical penalty exists on purpose, to
    stop a parenthetical role being chosen as the default. Inverting it for an
    explicit request must not bring that bug back."""
    for fixture in (AAPL_10K, MSFT_10K, KO_10K):
        role = XBRL.from_directory(fixture).statements.balance_sheet().role_or_type
        assert "parenthetical" not in role.lower()


@pytest.mark.parametrize("fixture", [AAPL_10K, MSFT_10K, KO_10K])
def test_an_absent_parenthetical_is_reported_not_substituted(fixture):
    """None of these filings declares a parenthetical income statement. The old
    behaviour returned the ordinary income statement, which is correct-looking
    and not what was asked for."""
    xbrl = XBRL.from_directory(fixture)

    with pytest.raises(StatementNotFoundError):
        xbrl.find_statement("IncomeStatement", is_parenthetical=True)


def test_a_parenthetical_role_identifiable_only_by_name_is_still_found():
    """Union Pacific's FY2012 parenthetical balance sheet has type None and a
    share-count primary concept, so it is identifiable only by its role name —
    which the BalanceSheet role pattern missed because the filing writes the
    plural 'Statements of Financial Position'."""
    xbrl = XBRL.from_directory(Path("data/xbrl/datafiles/unp"))

    _, parenthetical_role, _ = xbrl.find_statement("BalanceSheet", is_parenthetical=True)
    _, main_role, _ = xbrl.find_statement("BalanceSheet")

    assert parenthetical_role != main_role
    assert "Parenthetical" in parenthetical_role
