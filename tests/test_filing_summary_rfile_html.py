"""Characterization coverage for FilingSummary R-file HTML traversal."""

from types import SimpleNamespace

from edgar.sgml.filing_summary import Report


R_FILE_HTML = """<?xml version="1.0" encoding="UTF-8"?>
<html><body>
<table class="report">
  <tr>
    <td class="pl">Revenue <span>details</span></td>
    <td class="text">
      Intro <span>three</span> reportable
      <table><tr><td>Product</td><td>42</td></tr></table>
      after table
    </td>
  </tr>
</table>
</body></html>"""


def _report(content: str) -> Report:
    filing_sgml = SimpleNamespace(get_content=lambda _: content)
    filing_summary = SimpleNamespace(_filing_sgml=filing_sgml)
    reports = SimpleNamespace(_filing_summary=filing_summary)
    return Report(
        instance=None,
        is_default=False,
        has_embedded_reports=True,
        long_name="Revenue details",
        short_name="Revenue (Tables)",
        menu_category="Tables",
        position=1,
        html_file_name="R1.htm",
        report_type="Details",
        role=None,
        reports=reports,
    )


def test_rfile_narrative_preserves_boundaries_and_excludes_table_text():
    tree = Report._parse_report_html(R_FILE_HTML)
    report_table = Report._first_with_class(tree, 'table', 'report')
    text_cell = Report._first_with_class(report_table, 'td', 'text')

    assert Report._has_embedded_tables(report_table)
    assert Report._narrative_text(text_cell) == "Intro three reportable after table"


def test_rfile_rendering_keeps_label_narrative_and_embedded_values():
    text = _report(R_FILE_HTML).text()

    assert "Revenue details" in text
    assert "Intro three reportable after table" in text
    assert "Product" in text
    assert "42" in text


def test_rfile_parser_recovers_after_unclosed_comment():
    tree = Report._parse_report_html("<!-- malformed\n" + R_FILE_HTML)

    assert Report._first_with_class(tree, 'table', 'report') is not None
