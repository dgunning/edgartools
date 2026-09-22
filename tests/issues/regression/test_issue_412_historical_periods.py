"""
Regression test for GitHub Issue #412:
Historical periods in entity statements showed sparse data.

Periods 3rd and 4th should have comprehensive balance sheet data,
not just cash values.

GitHub Issue: https://github.com/dgunning/edgartools/issues/412
"""
import pytest
from edgar import Company


@pytest.mark.network
def test_historical_periods_have_comprehensive_data():
    """Historical periods (3rd, 4th) should have >35% completeness and key balance sheet items."""
    company = Company("TSLA")
    balance_sheet = company.balance_sheet(annual=True, periods=6)
    assert balance_sheet is not None, (
        "TSLA should have an annual balance sheet; None here is the retrieval "
        "path failing, which is the condition this test exists to catch"
    )
    df = balance_sheet.to_dataframe()

    periods = balance_sheet.periods

    # Assert the preconditions instead of testing them. Both of these used to be
    # `if` guards, and issue #412 was sparse historical periods -- so a TSLA
    # balance sheet that stopped returning a 3rd and 4th period, or stopped
    # putting them in the frame, would skip every assertion below and report
    # green. The condition that silences the test is the condition it is for.
    assert len(periods) >= 4, (
        f"TSLA annual balance sheet returned {len(periods)} periods, need 4 to "
        f"check the historical ones: {periods}"
    )

    for period_index in [2, 3]:
        period = periods[period_index]
        assert period in df.columns, (
            f"period {period} (index {period_index}) is in balance_sheet.periods "
            f"but not in the dataframe columns: {list(df.columns)}"
        )

        completeness = df[period].count() / len(df)
        assert completeness > 0.35, (
            f"Historical period {period} (index {period_index}) should have "
            f"comprehensive data. Got {completeness:.1%}, expected >35%"
        )

        non_null_data = df[df[period].notna()]
        key_items_present = 0

        for _, row in non_null_data.iterrows():
            label_lower = row['label'].lower()
            if any(keyword in label_lower for keyword in
                   ['assets', 'liabilities', 'equity', 'stockholders']):
                key_items_present += 1

        assert key_items_present >= 3, (
            f"Historical period {period} should have key balance sheet items, "
            f"not just cash. Found {key_items_present} key items."
        )


# Both tests below were ported here on 2026-08-10 from
# tests/issues/reproductions/entity-facts/test_412_regression.py (bead
# edgartools-07lk.24, Tier 2), which was listed for deletion as a duplicate of
# this file. Its first two tests were duplicates; these two were the only
# coverage of what a user actually sees (the rendered table) and of the fix
# holding for filers other than TSLA.
#
# Both are rewritten rather than copied, because both could pass without
# testing anything. The rich-output test called pytest.skip() on a missing
# balance sheet and wrapped every assertion in `if len(periods) >= 3`; the
# multi-company test did `if balance_sheet is None: continue`, so all three
# companies could drop out and the test still passed.
@pytest.mark.network
def test_rich_output_shows_historical_data():
    """The rendered balance sheet shows populated historical columns.

    This is the user-visible half of issue #412: the data can be present in the
    dataframe and still not reach the table that `print(balance_sheet)` draws.
    """
    import re
    from rich.console import Console

    company = Company("TSLA")
    balance_sheet = company.balance_sheet(annual=True, periods=4)
    assert balance_sheet is not None, (
        "TSLA should have an annual balance sheet; None here is the retrieval "
        "path failing, which is the condition this test exists to catch"
    )

    periods = balance_sheet.periods
    assert len(periods) >= 4, (
        f"TSLA annual balance sheet returned {len(periods)} periods, need 4: {periods}"
    )

    console = Console(file=None, width=120)  # Wide enough to avoid truncation
    with console.capture() as capture:
        console.print(balance_sheet.__rich__())
    output = capture.get()

    # Matches $123,456... or $123,456,789 — a cell with a real value in it.
    value_pattern = r'\$[\d,]+[.,…]'
    lines_with_values = [line for line in output.split('\n')
                         if re.search(value_pattern, line)]
    assert len(lines_with_values) >= 10, (
        f"Expected substantial data in rich output, but only found "
        f"{len(lines_with_values)} lines with values"
    )

    for period_index in (2, 3):
        period = periods[period_index]
        assert period in output, (
            f"Historical period {period} (index {period_index}) is missing from "
            f"the rendered balance sheet"
        )


@pytest.mark.network
def test_multiple_companies_no_regression():
    """The #412 fix holds for filers other than TSLA.

    Failures are collected per company and reported together rather than
    aborting on the first, so one bad filing does not hide the other two.
    """
    tickers = ["AAPL", "MSFT", "GOOGL"]
    failures = []
    exercised = []

    for ticker in tickers:
        try:
            balance_sheet = Company(ticker).balance_sheet(annual=True, periods=4)
            assert balance_sheet is not None, f"{ticker}: no annual balance sheet"

            df = balance_sheet.to_dataframe()
            periods = balance_sheet.periods
            assert len(periods) >= 3, (
                f"{ticker}: expected at least 3 periods, got {len(periods)}"
            )
            assert len(df) > 20, (
                f"{ticker}: expected substantial balance sheet structure, got {len(df)} rows"
            )

            recent_period = periods[0]
            assert recent_period in df.columns, (
                f"{ticker}: most recent period {recent_period} missing from the dataframe"
            )
            completeness = df[recent_period].count() / len(df)
            assert completeness > 0.30, (
                f"{ticker}: recent period should be well-populated. "
                f"Got {completeness:.1%}, expected >30%"
            )
            exercised.append(ticker)
        except AssertionError as e:
            # The messages already name the ticker; don't prefix it twice.
            failures.append(str(e))

    assert not failures, "Issue #412 regression:\n" + "\n".join(failures)
    assert exercised == tickers, (
        f"Expected to exercise {tickers}, actually exercised {exercised}"
    )
