"""
Regression test for Issue #755: Wrong text formatting for a statement in Jupyter

GitHub Issue: https://github.com/dgunning/edgartools/issues/755
Reporter: BaraVaq

Bug (FIXED): Rendering a "(Tables)" R-file report (e.g. "Revenue (Tables)") via
``Report.view()`` / ``Report.text()`` produced a mangled layout. These R-files
wrap a complete HTML table inside a TextBlock (``<td class="text">``) cell.
``view()`` rendered the outer wrapper table, which flattened the nested table
into a single narrow column, scrambling the financial data.

Fix: ``Report._build_renderable()`` detects reports whose TextBlock cells embed
full tables and renders each embedded table on its own (prefixed by its element
label and narrative lead-in text) instead of the flattened wrapper.

Ground truth (AAPL 10-Q, accession 0000320193-24-000081, Q3 FY2024):
    Net sales disaggregated by significant products and services
    - iPhone (three months ended Jun 29, 2024):  $39,296
    - iPhone (nine months ended Jun 29, 2024):  $154,961
    - Total net sales (three months ended Jun 29, 2024):  $85,777
"""

import pytest

from edgar import find

# A fixed AAPL 10-Q so the ground-truth values are deterministic.
ACCESSION = "0000320193-24-000081"
REVENUE_TABLES_SHORT_NAME = "Revenue (Tables)"


def _revenue_tables_report():
    filing = find(ACCESSION)
    report = filing.reports.get_by_short_name(REVENUE_TABLES_SHORT_NAME)
    assert report is not None, "Should find the 'Revenue (Tables)' report"
    return report


@pytest.mark.network
@pytest.mark.regression
def test_issue_755_embedded_table_values_present():
    """The embedded disaggregated-net-sales table renders with all its values."""
    report = _revenue_tables_report()
    text = report.text()
    assert text is not None and text.strip(), "Report text should not be empty"

    # Ground-truth values from the embedded table must all be present.
    for value in ("39,296", "39,669", "154,961", "85,777", "296,105"):
        assert value in text, f"Expected disaggregated revenue value {value!r} in output"

    # Product/category labels and narrative lead-in must survive.
    for label in ("iPhone", "Mac", "iPad", "Services", "Total net sales"):
        assert label in text, f"Expected line item {label!r} in output"
    assert "disaggregated" in text.lower()


@pytest.mark.network
@pytest.mark.regression
def test_issue_755_table_not_flattened_to_narrow_column():
    """
    Regression guard for the mangled layout: a line item and its value must
    appear together on the same rendered line, not split across a squeezed
    single column.
    """
    report = _revenue_tables_report()
    text = report.text()

    # In the broken rendering the label and value were forced onto separate
    # lines in a narrow column. After the fix, the iPhone row carries its value.
    iphone_lines = [ln for ln in text.splitlines() if "iPhone" in ln]
    assert iphone_lines, "Expected an 'iPhone' row in the rendered table"
    assert any("39,296" in ln for ln in iphone_lines), (
        "iPhone label and its value (39,296) should render on the same line, "
        "not be split into a narrow flattened column"
    )

    total_lines = [ln for ln in text.splitlines() if "Total net sales" in ln]
    assert total_lines, "Expected a 'Total net sales' row in the rendered table"
    assert any("85,777" in ln for ln in total_lines), (
        "Total net sales label and value (85,777) should render on the same line"
    )


@pytest.mark.network
@pytest.mark.regression
def test_issue_755_regular_statement_still_renders():
    """A normal statement R-file (no embedded tables) renders unchanged."""
    filing = find(ACCESSION)
    income = filing.reports.get_by_short_name(
        "CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS (Unaudited)"
    )
    assert income is not None
    text = income.text()
    assert "Net sales" in text
    assert "85,777" in text  # Q3 total net sales appears on the income statement too
