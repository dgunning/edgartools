"""Regression: comprehensive income rows with a negated label show the SEC's sign.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1676

The presentation sign (`preferred_sign` from a negated preferredLabel) was applied
only to statements classified IncomeStatement, CashFlowStatement or BalanceSheet,
in both `apply_presentation_sign` (rendering) and `Statement._apply_presentation`
(DataFrame). A comprehensive income statement is classified ComprehensiveIncome,
so its negated rows kept the filed sign and no longer footed to their totals.

American Airlines' FY2025 10-K (0000006201-26-000014) files its pension OCI as
-176, -327 and +312 million and presents the row with a negated label; the SEC
page shows 176 | 327 | (312) beside investments 0 | 2 | 3 and a total of
176 | 329 | (309).
"""

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.rendering import apply_presentation_sign


def test_presentation_sign_applies_to_comprehensive_income():
    signs = {"duration_2025-01-01_2025-12-31": -1}
    assert apply_presentation_sign(-176.0, "ComprehensiveIncome", signs, "duration_2025-01-01_2025-12-31") == 176.0
    # Statements outside the list are still shown as filed.
    assert apply_presentation_sign(-176.0, "StatementOfEquity", signs, "duration_2025-01-01_2025-12-31") == -176.0


AAL_FOLDER = "https://www.sec.gov/Archives/edgar/data/6201/000000620126000014/"
AAL_FILES = ("aal-20251231.xsd", "aal-20251231_htm.xml", "aal-20251231_pre.xml", "aal-20251231_lab.xml")
PENSION = "Pension, retiree medical and other postretirement benefits"
INVESTMENTS = "Investments"
TOTAL_OCI = "Total other comprehensive income (loss), net of tax"
COLUMNS = ["2025-12-31 (FY)", "2024-12-31 (FY)", "2023-12-31 (FY)"]


@pytest.mark.vcr
def test_aal_comprehensive_income_components_foot_to_the_total(tmp_path):
    """Ground truth: American Airlines Group FY2025 10-K, 0000006201-26-000014, R4."""
    for name in AAL_FILES:
        (tmp_path / name).write_text(download_file(AAL_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)
    statement = xbrl.statements.comprehensive_income()

    df = statement.to_dataframe()
    first = df.drop_duplicates("label").set_index("label")
    assert first.loc[PENSION, "preferred_sign"] == -1
    assert list(first.loc[PENSION, COLUMNS]) == [176_000_000, 327_000_000, -312_000_000]
    assert list(first.loc[INVESTMENTS, COLUMNS]) == [0, 2_000_000, 3_000_000]
    assert list(first.loc[TOTAL_OCI, COLUMNS]) == [176_000_000, 329_000_000, -309_000_000]

    # Raw values are still the filed ones.
    raw = statement.to_dataframe(presentation=False).drop_duplicates("label").set_index("label")
    assert list(raw.loc[PENSION, COLUMNS]) == [-176_000_000, -327_000_000, 312_000_000]

    pension_line = next(line for line in str(statement).splitlines() if PENSION in line)
    assert pension_line.split()[-3:] == ["176", "327", "(312)"]


def test_render_and_dataframe_agree_when_comprehensive_income_is_an_equity_role():
    """Fixture: Coca-Cola FY2011 10-K (tests/fixtures/xbrl/ko/10k_2012).

    KO reports comprehensive income inside its shareowners' equity statement, so
    `comprehensive_income()` resolves to an equity role. render() gates the sign
    on the resolved type (StatementOfEquity, still excluded) and the DataFrame
    now does too: both show the filed 38, where the DataFrame alone used to flip
    it to -38.
    """
    from pathlib import Path

    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "ko" / "10k_2012"
    statement = XBRL.from_directory(fixture).statements.comprehensive_income()
    assert statement.role_or_type.endswith("/ConsolidatedStatementsOfShareownersEquity")

    label = "Dividends paid to noncontrolling interests"
    df = statement.to_dataframe()
    row = df[df["label"] == label].iloc[0]
    assert row["preferred_sign"] == -1

    rendered = next(line for line in str(statement).splitlines() if label in line)
    assert rendered.split()[-3:] == ["38", "32", "14"]
    assert [row[c] for c in ("2011-12-31 (FY)", "2010-12-31 (FY)", "2009-12-31 (FY)")] == [
        38_000_000, 32_000_000, 14_000_000]
