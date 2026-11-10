"""EarningsRelease must preserve reported EPS and non-USD table units.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1824

Ground truth: TSM 6-K 0001046179-26-000726, exhibit
a3q26e_withguidancexfinal.htm (2026-10-15). Original SEC bytes downloaded
2026-11-01 before implementation: TWD 763,064 million net income and NT$29.43
EPS with a trailing letter footnote. Fixture provenance is in its README.

Review regression: Cardlytics 8-K 0001666071-25-000124, EX-99.1 (2025-08-06),
downloaded unchanged on 2026-11-04 before this revision. Q2 revenue is USD
63,249 thousand, net loss USD 9,283 thousand, diluted loss per share USD 0.18.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.documents import parse_html
from edgar.earnings import EarningsRelease, RowType, Scale, _classify_row_type, _parse_numeric, _table_context

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html" / "issue1824"


@pytest.fixture
def income():
    attachment = SimpleNamespace(content=(FIXTURES / "a3q26e_withguidancexfinal.htm").read_text(), document="a3q26e_withguidancexfinal.htm")
    return EarningsRelease(attachment).income_statement


def test_real_tsm_units_and_eps_are_correct_without_financials_adapter(income):
    assert income.currency == "TWD"
    assert income.scaled_dataframe.loc["Net income"].iloc[0] == 763_064_000_000
    assert income.scaled_dataframe.loc["EPS (NT$)"].iloc[0] == 29.43
    assert income.get_row_type("EPS (NT$)", 5) is RowType.PER_SHARE
    assert "actual TWD" in income.to_context()
    assert "actual USD" not in income.to_context()
    assert json.loads(income.to_json())["metadata"]["currency"] == "TWD"
    facts = income.to_facts_dataframe()
    amounts = facts.loc[facts["label"] == "Net income"]
    eps = facts.loc[facts["label"] == "EPS (NT$)"]
    assert set(amounts["unit"]) == {"TWD"}
    assert amounts["numeric_value"].iloc[0] == 763_064_000_000
    assert set(eps["unit"]) == {"TWD/shares"}
    assert eps["numeric_value"].iloc[0] == 29.43


def test_real_tsm_percent_change_columns_are_not_scaled(income):
    # Filed row: "Net income 763,064 | 452,302 | 68.7 | 706,562 | 8.0" under
    # "(Unit: NT$ million)", with "YoY Inc. (Dec.) %" and "QoQ Inc. (Dec.) %" columns.
    scaled = income.scaled_dataframe
    yoy, qoq = [c for c in scaled.columns if "%" in str(c)]
    assert scaled.loc["Net income"].iloc[0] == 763_064_000_000
    assert scaled.loc["Net income", yoy] == 68.7
    assert scaled.loc["Net income", qoq] == 8.0
    assert scaled.loc["Net sales", yoy] == 50.9


def test_cleaned_tables_keep_currency_and_row_types(income):
    renamed = income.with_standardized_labels({"EPS (NT$)": "Reported EPS"})
    cleaned = income.with_clean_columns()
    assert renamed.currency == cleaned.currency == "TWD"
    assert renamed.scaled_dataframe.loc["Reported EPS"].iloc[0] == 29.43
    assert cleaned.scaled_dataframe.loc["EPS (NT$)"].iloc[0] == 29.43


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("29.43b", "29.43b"),
        ("(29.43)b", "(29.43)b"),
        ("-29.43b", "-29.43b"),
        ("1,234a", "1,234a"),
        ("0.00b", "0.00b"),
        ("1.2B", "1.2B"),
        ("1.2b", "1.2b"),
        ("1.2m", "1.2m"),
        ("500k", "500k"),
        ("$1.2m", "$1.2m"),
        ("(500k)", "(500k)"),
        ("1.2M", "1.2M"),
        ("500K", "500K"),
        ("(-0.18)", -0.18),
        ("29.43 basis points", "29.43 basis points"),
        ("1e3", 1000.0),
    ],
)
def test_unmarked_suffixes_are_ambiguous_and_must_not_be_stripped(cell, expected):
    assert _parse_numeric(cell) == expected


@pytest.mark.parametrize(
    "label, expected",
    [
        ("Weighted average shares used in EPS", RowType.SHARES),
        ("EPS growth rate", RowType.PERCENTAGE),
    ],
)
def test_eps_reference_does_not_override_share_counts_or_percentages(label, expected):
    assert _classify_row_type(label) is expected


def test_context_without_node_in_parent_does_not_raise():
    parent = SimpleNamespace(children=[SimpleNamespace(content="unrelated")], parent=None)
    node = SimpleNamespace(parent=parent)
    assert _table_context(node, "Income") == (["Income"], [])


def test_context_reads_non_string_dom_content_safely():
    before = SimpleNamespace(content=["not text"], text=lambda: "(Unit: TWD million)")
    after = SimpleNamespace(content=5, text=lambda: "Reported footnote")
    parent = SimpleNamespace(children=[], parent=None)
    node = SimpleNamespace(parent=parent)
    parent.children = [before, node, after]
    assert _table_context(node, "Income") == (["Income", "(Unit: TWD million)"], ["Reported footnote"])


def release_from_html(html):
    return EarningsRelease(SimpleNamespace(content=html, document="synthetic.htm"))


def financial_html(note="", revenue="12", caption="", header="Q1 2025", eps="0.18"):
    return f"""<html><body><p>{note}</p><div><table>
    <caption>{caption}</caption>
    <tr><th>Item</th><th>{header}</th></tr>
    <tr><td>Revenue</td><td>{revenue}</td></tr>
    <tr><td>Net income</td><td>2</td></tr>
    <tr><td>EPS</td><td>{eps}</td></tr>
    </table></div></body></html>"""


def test_real_cardlytics_keeps_usd_with_unqualified_amounts_in_thousands():
    path = FIXTURES / "cdlx_form8-kx2025q2xex991.htm"
    release = release_from_html(path.read_text())
    income = release.income_statement
    assert income.currency == "USD"
    assert income.scale is Scale.THOUSANDS
    assert income.scaled_dataframe.loc["Revenue"].iloc[0] == 63_249_000
    assert income.scaled_dataframe.loc["Net Loss"].iloc[0] == -9_283_000
    assert income.scaled_dataframe.loc["Net Loss per share, basic and diluted"].iloc[0] == -0.18
    assert "actual USD" in income.to_context()
    facts = income.to_facts_dataframe()
    assert set(facts.loc[facts["label"] == "Revenue", "unit"]) == {"USD"}
    assert set(facts.loc[facts["label"].str.startswith("Net Loss per share"), "unit"]) == {"USD/shares"}


@pytest.mark.parametrize(
    "note",
    [
        "(Amounts in thousands, except per share amounts)",
        "(in thousands)",
        "(Dollars in thousands)",
    ],
)
def test_scale_only_declarations_keep_legacy_usd_and_unscaled_eps(note):
    income = release_from_html(financial_html(note)).income_statement
    assert income.currency == "USD"
    assert income.scale is Scale.THOUSANDS
    assert income.scaled_dataframe.loc["Revenue"].iloc[0] == 12_000
    assert income.scaled_dataframe.loc["EPS"].iloc[0] == 0.18


@pytest.mark.parametrize(
    "table_units",
    [
        {"caption": "(in millions)"},
        {"header": "Q1 2025 (in millions)"},
    ],
)
@pytest.mark.parametrize(
    "note",
    [
        "(in constant currency)",
        "(Unit: TWD)",
        "(Unit: TWD thousands)",
    ],
)
def test_caption_and_header_scale_take_precedence_over_nearby_notes(table_units, note):
    income = release_from_html(financial_html(note, **table_units)).income_statement
    assert income.scale is Scale.MILLIONS
    assert income.scaled_dataframe.loc["Revenue"].iloc[0] == 12_000_000


def test_constant_currency_note_does_not_replace_document_scale_or_usd():
    html = financial_html("(in constant currency)")
    html = html.replace("<body>", "<body><p>(in millions)</p><p>Unaudited</p><p>Results</p><p>Quarter</p>")
    income = release_from_html(html).income_statement
    assert income.scale is Scale.MILLIONS
    assert income.currency == "USD"


@pytest.mark.parametrize(
    "note, currency",
    [
        ("(Unit: TWD million, except for EPS)", "TWD"),
        ("(Unit: USD and TWD million)", None),
    ],
)
def test_explicit_currency_is_preserved_and_mixed_currency_stays_unknown(note, currency):
    income = release_from_html(financial_html(note)).income_statement
    assert income.currency == currency
    assert income.scale is Scale.MILLIONS


def test_unsupported_explicit_currency_is_not_silently_changed_to_usd():
    income = release_from_html(financial_html("(Unit: GBP)", caption="(in millions)")).income_statement
    assert income.currency is None
    assert income.scale is Scale.MILLIONS


@pytest.mark.parametrize(
    "note, currency",
    [
        ("(in millions of yen)", "JPY"),
        ("(Yen in millions)", "JPY"),
        ("(¥ in millions)", "JPY"),
        ("(€ in millions)", "EUR"),
        ("(RMB in thousands)", "CNY"),
        # A named currency the table does not map is unknown, never the USD default.
        ("(in millions of Canadian dollars)", None),
        ("(in thousands of pounds sterling)", None),
        ("(£ in millions)", None),
        # Only a scale is named: the legacy USD default stands.
        ("(in thousands)", "USD"),
        ("(in millions, except per share data)", "USD"),
        ("(in millions of dollars)", "USD"),
        ("(Shares in thousands)", "USD"),
        # Metric acronyms in a US note are not currency codes.
        ("(in thousands, except per share and DAU data)", "USD"),
        ("(in millions, except per share, ARR and FTE data)", "USD"),
        ("(in thousands of GBP)", None),
    ],
)
def test_declared_currency_is_named_currency_or_unknown_never_wrong_usd(note, currency):
    income = release_from_html(financial_html(note)).income_statement
    assert income.currency == currency


# Toyota 6-K 0001193125-26-448368, EX-99.2 d87505dex992.htm (filed 2026-11-05):
# the semi-annual statement of income puts its unit in a header row, "Yen in
# millions", above "For the first half ended September 30, 2025 / 2026".
# Sales of products: 22,324,109 and 24,231,768 million yen. Markup trimmed of styles.
TOYOTA_INCOME_HEADER = """<html><body><p>Unaudited Condensed Semi-Annual Consolidated Statement of Income</p>
<table>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>&nbsp;</td><td>&nbsp;&nbsp;</td><td colspan="6"><b>Yen in millions</b></td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;&nbsp;</td>
<td colspan="2" nowrap><b>For&nbsp;the&nbsp;first&nbsp;half&nbsp;ended</b><br><b>September&nbsp;30, 2025</b></td>
<td>&nbsp;</td><td>&nbsp;</td>
<td colspan="2" nowrap><b>For&nbsp;the&nbsp;first&nbsp;half&nbsp;ended</b><br><b>September&nbsp;30, 2026</b></td>
<td>&nbsp;</td></tr>
<tr><td> Sales of products</td><td>&nbsp;&nbsp;</td><td>&nbsp;</td><td>22,324,109</td><td>&nbsp;</td>
<td>&nbsp;</td><td>&nbsp;</td><td>24,231,768</td><td>&nbsp;</td></tr>
<tr><td> Net income</td><td>&nbsp;&nbsp;</td><td>&nbsp;</td><td>1,000</td><td>&nbsp;</td>
<td>&nbsp;</td><td>&nbsp;</td><td>2,000</td><td>&nbsp;</td></tr>
</table></body></html>"""


def test_percent_column_unscaled_but_amount_column_under_a_percent_banner_scaled():
    # Toyota's summary table nests "Million yen" amount columns under a
    # "(% of change from previous first half)" banner; Deere/Delta use "% Change".
    html = """<html><body><p>(in millions)</p><div><table>
    <tr><th>Item</th><th>(% of change) Sales revenues Million yen</th><th>Q1 2025 % Change</th></tr>
    <tr><td>Revenue</td><td>12</td><td>9.5</td></tr>
    <tr><td>Net income</td><td>2</td><td>-7.4</td></tr>
    </table></div></body></html>"""
    scaled = release_from_html(html).financial_tables[0].scaled_dataframe
    assert scaled.loc["Revenue"].iloc[0] == 12_000_000
    assert scaled.loc["Revenue"].iloc[1] == 9.5
    assert scaled.loc["Net income"].iloc[1] == -7.4


def test_toyota_unit_header_row_reports_jpy():
    tables = release_from_html(TOYOTA_INCOME_HEADER).financial_tables
    assert tables, "Toyota income statement snippet produced no financial table"
    table = tables[0]
    assert table.currency == "JPY"
    assert table.scale is Scale.MILLIONS
    assert table.scaled_dataframe.loc["Sales of products"].iloc[-1] == 24_231_768_000_000
    facts = table.to_facts_dataframe()
    assert set(facts.loc[facts["label"] == "Sales of products", "unit"]) == {"JPY"}


def test_each_table_keeps_its_own_currency_and_scale():
    twd = financial_html("(Unit: TWD million)")
    usd = financial_html("(Amounts in thousands, except EPS)")
    html = twd.replace("</body>", usd.split("<body>")[1].split("</body>")[0] + "</body>")
    tables = release_from_html(html).financial_tables
    assert [(t.currency, t.scale) for t in tables] == [("TWD", Scale.MILLIONS), ("USD", Scale.THOUSANDS)]


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("29.43<sup>b</sup>", 29.43),
        ("(29.43)<sup>b</sup>", -29.43),
        ("(29.43<sup>b</sup>)", -29.43),
        ('-29.43<span style="vertical-align: super">b</span>', -29.43),
        ('29.43<font style="position:relative;top:-3.5pt;vertical-align:baseline">b</font>', 29.43),
        ("29.43b", "29.43b"),
        ("1.2m", "1.2m"),
        ("500k", "500k"),
    ],
)
def test_only_html_identified_letter_footnotes_are_removed(cell, expected):
    income = release_from_html(financial_html(revenue=cell)).income_statement
    assert income.dataframe.loc["Revenue"].iloc[0] == expected


def test_footnote_handling_is_scoped_and_keeps_source_and_prose():
    html = financial_html(revenue="29.43<sup>b</sup>")
    html = html.replace("Net income</td>", "Net income<sup>a</sup></td>")
    release = release_from_html(html)
    assert release.income_statement.dataframe.loc["Revenue"].iloc[0] == 29.43
    assert "Net incomea" in release.income_statement.dataframe.index
    assert release.document.metadata.original_html == html
    assert release.attachment.content == html
    # Other consumers of the canonical parser still get the original cell text.
    document = parse_html(html)
    assert any(cell.content == "29.43b" for row in document.tables[0].rows for cell in row.cells)
