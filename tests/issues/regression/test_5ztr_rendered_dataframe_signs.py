"""
Regression tests for edgartools-5ztr (GH #1248): `Statements.to_dataframe()` and
`Statement.to_dataframe()` returned different signs for the same cash-flow line,
and nothing said which one to believe.

`Statement.to_dataframe()` builds from raw data and applies `_apply_presentation()`,
producing the SEC-displayed sign. The plural accessor instead went through
`statement.render(...).to_dataframe()`, which read `cell.value` — the plain filed
value. The presentation sign lived only inside the cell FORMATTER, which produces
display strings, so it never reached the DataFrame. Apple's FY2023 capex came back
+10,959,000,000 from one accessor and -10,959,000,000 from the other; both calls
succeeded and both look right in isolation.

The sign now lives in one function, `rendering.apply_presentation_sign`, called by
the formatter and by `RenderedStatement.to_dataframe()`. The old raw-value
behaviour is still reachable as `presentation=False`.

Ground truth is Apple's FY2023 10-K cash flow statement (period ending
2023-09-30), which shows capital expenditures as (10,959) and share repurchases
as (77,550).
"""

import re
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

FIXTURE = Path("tests/fixtures/xbrl/aapl/10k_2023")

CAPEX = "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"
BUYBACKS = "us-gaap_PaymentsForRepurchaseOfCommonStock"

# AAPL FY2023 10-K, as filed (positive) and as displayed (parenthesised).
CAPEX_FILED = 10_959_000_000.0
BUYBACKS_FILED = 77_550_000_000.0


@pytest.fixture(scope="module")
def xbrl():
    return XBRL.from_directory(FIXTURE)


def _fy2023_column(df):
    """The first date-stamped column, which is the FY2023 period."""
    dated = [c for c in df.columns if re.match(r"^2023-09-30", str(c))]
    assert dated, f"no FY2023 column in {list(df.columns)}"
    return dated[0]


def _values(df):
    """
    FY2023 value per (concept, label).

    Keyed on the pair, not the concept alone: a concept legitimately appears on
    several rows of one statement (AAPL's balance sheet carries four
    us-gaap:StockholdersEquity rows, the total plus its dimensional breakdown),
    and the two accessors do not select the same set of rows — a difference in
    row selection, unrelated to the sign this file is about.
    """
    column = df[_fy2023_column(df)]
    return {
        (concept, label): value
        for concept, label, value in zip(df["concept"], df["label"], column, strict=True)
    }


def _only(values, concept):
    """The single value for a concept, asserting it has exactly one row."""
    matches = [v for (c, _label), v in values.items() if c == concept]
    assert len(matches) == 1, f"{concept} appears on {len(matches)} rows"
    return matches[0]


def test_singular_and_plural_accessors_agree(xbrl):
    """Every numeric cell must match between the two accessors."""
    singular = _values(xbrl.statements["CashFlowStatement"].to_dataframe())
    plural = _values(xbrl.statements.to_dataframe("CashFlowStatement"))

    disagreements = [
        (concept, singular[concept], plural[concept])
        for concept in singular
        if concept in plural
        and isinstance(singular[concept], (int, float))
        and isinstance(plural[concept], (int, float))
        and singular[concept] == singular[concept]  # not NaN
        and plural[concept] == plural[concept]
        and singular[concept] != plural[concept]
    ]
    assert disagreements == []


def test_plural_accessor_shows_outflows_as_negative(xbrl):
    """
    The specific numbers from the report. Both were positive before the fix,
    where Apple's cash flow statement shows them in parentheses.
    """
    plural = _values(xbrl.statements.to_dataframe("CashFlowStatement"))

    assert _only(plural, CAPEX) == -CAPEX_FILED
    assert _only(plural, BUYBACKS) == -BUYBACKS_FILED


def test_presentation_false_returns_the_filed_values(xbrl):
    """
    The raw values stay reachable, so a consumer that depended on the old
    behaviour has somewhere to go.
    """
    raw = _values(
        xbrl.statements["CashFlowStatement"].render().to_dataframe(presentation=False)
    )

    assert _only(raw, CAPEX) == CAPEX_FILED
    assert _only(raw, BUYBACKS) == BUYBACKS_FILED


def test_presentation_changes_only_negated_rows(xbrl):
    """
    The sign is applied where the presentation linkbase asks for it and nowhere
    else — 13 of this cash flow statement's rows.
    """
    rendered = xbrl.statements["CashFlowStatement"].render()
    presented = _values(rendered.to_dataframe())
    raw = _values(rendered.to_dataframe(presentation=False))

    flipped = [
        concept
        for (concept, label), value in raw.items()
        if isinstance(value, (int, float))
        and isinstance(presented[(concept, label)], (int, float))
        and value != presented[(concept, label)]
    ]
    assert len(flipped) == 13
    assert CAPEX in flipped
    # Net income is filed and displayed positive; it must not move.
    assert "us-gaap_NetIncomeLoss" not in flipped


def test_balance_sheet_and_income_statement_also_agree(xbrl):
    """The disagreement was not specific to the cash flow statement."""
    for statement_type in ("BalanceSheet", "IncomeStatement"):
        singular = _values(xbrl.statements[statement_type].to_dataframe())
        plural = _values(xbrl.statements.to_dataframe(statement_type))
        for key, value in singular.items():
            if key not in plural:
                continue
            other = plural[key]
            if not (isinstance(value, (int, float)) and isinstance(other, (int, float))):
                continue
            if value != value or other != other:  # NaN
                continue
            assert value == other, f"{statement_type}: {key}"
