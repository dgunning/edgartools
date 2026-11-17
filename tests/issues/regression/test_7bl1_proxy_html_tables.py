"""
Proxy statement HTML tables: the SCT, beneficial ownership, director
compensation and audit fee extractors read the table the filing shows.

Bead: edgartools-7bl1

On 19 large-cap DEF 14As the four ProxyStatement table accessors came back
empty on about half (SCT 9 of 19, ownership 10, director comp 11, audit fees
11), and many that did return rows had columns misread. The causes, each
covered below with a small table of the shape that broke and then with
ground truth from AMZN, KO and SHAK:

1. The table grid ignored ``rowspan``, so an executive's later rows shifted
   left (AMZN's SCT names span three rows), and a value counted only if it
   sat in the label's first column or the next, though a label like "Salary"
   spans several columns with the value after a "$" cell.
2. Only the first heading that named the section was tried, and it was often
   a table-of-contents row, a sentence that mentions the section, or a title
   row inside the table itself.
3. The table scorer read only the first three rows.
4. Stacked headers ("Shares of Class A Common Stock" over "Number" and
   "Percentage") were read one row at a time.

Fixtures are verbatim SEC primary documents; see
tests/fixtures/html/proxy_7bl1/README.md.
"""
from pathlib import Path

import lxml.html
import pytest

from edgar.proxy import ProxyStatement
from edgar.proxy.html_extractor import (
    extract_audit_fees,
    extract_beneficial_ownership,
    extract_director_compensation,
    extract_summary_compensation,
)

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).parents[2] / "fixtures" / "html" / "proxy_7bl1"


class _Filing:
    """The two attributes ProxyStatement reads for its HTML accessors."""
    form = "DEF 14A"

    def __init__(self, path: Path):
        self._path = path
        self.accession_no = path.stem

    def html(self) -> str:
        return self._path.read_bytes().decode("utf-8")


def _proxy(name: str) -> ProxyStatement:
    return ProxyStatement(_Filing(FIXTURES / name))


@pytest.fixture(scope="module")
def amzn():
    return _proxy("amzn_tm261382-1_def14a.htm")


@pytest.fixture(scope="module")
def ko():
    return _proxy("ko_ko-20260429xdef14a.htm")


@pytest.fixture(scope="module")
def shak():
    return _proxy("shak_tm261375-1_def14a.htm")


def _tree(body: str):
    return lxml.html.fromstring(f"<html><body>{body}</body></html>")


def _row(r, **values):
    return {k: getattr(r, k) for k in values} == values


# ── Mechanisms, on tables of the shape that broke ─────────────────────

SCT_ROWSPAN = """
<p>Summary Compensation Table</p>
<table>
<tr><td>Name and Principal Position</td><td></td><td colspan="2">Year</td>
    <td colspan="3">Salary</td><td colspan="3">Stock Awards</td><td colspan="3">Total</td></tr>
<tr><td rowspan="2">Pat Doe<br/>Chief Executive Officer</td><td></td><td></td><td>2025</td>
    <td>$</td><td>900,000</td><td></td><td>$</td><td>4,000,000</td><td></td><td>$</td><td>4,900,000</td><td></td></tr>
<tr><td></td><td>2024</td><td></td>
    <td></td><td>850,000</td><td></td><td></td><td>3,500,000</td><td></td><td></td><td>4,350,000</td><td></td></tr>
</table>
"""


def test_rowspan_keeps_an_executives_later_years_in_their_columns():
    rows = extract_summary_compensation(_tree(SCT_ROWSPAN))
    assert [(r.name, r.year, r.salary, r.stock_awards, r.total) for r in rows] == [
        ("Pat Doe", 2025, 900_000, 4_000_000, 4_900_000),
        ("Pat Doe", 2024, 850_000, 3_500_000, 4_350_000),
    ]


def test_a_title_on_the_next_row_is_not_a_new_executive():
    html = """
    <p>Summary Compensation Table</p>
    <table>
    <tr><td>Name and Principal Position</td><td>Year</td><td>Salary</td><td>Bonus</td><td>Total</td></tr>
    <tr><td>Winnie Park</td><td>2025</td><td>1,100,000</td><td>0</td><td>1,100,000</td></tr>
    <tr><td>Chief Executive Officer and</td><td>2024</td><td>126,923</td><td>0</td><td>126,923</td></tr>
    </table>"""
    rows = extract_summary_compensation(_tree(html))
    assert [r.name for r in rows] == ["Winnie Park", "Winnie Park"]


def test_a_heading_in_the_tables_own_title_row_finds_that_table():
    html = """
    <table>
    <tr><td colspan="4"><p>SUMMARY COMPENSATION TABLE</p></td></tr>
    <tr><td>Name</td><td>Year</td><td>Salary</td><td>Total</td></tr>
    <tr><td>Pat Doe</td><td>2025</td><td>500,000</td><td>800,000</td></tr>
    </table>"""
    rows = extract_summary_compensation(_tree(html))
    assert [(r.name, r.salary, r.total) for r in rows] == [("Pat Doe", 500_000, 800_000)]


def test_a_stacked_dual_class_header_reads_the_first_class():
    html = """
    <p>Security Ownership of Certain Beneficial Owners and Management</p>
    <table>
    <tr><td></td><td colspan="2">Shares of Class A Common Stock</td><td colspan="2">Shares of Class B Common Stock</td></tr>
    <tr><td></td><td>Number</td><td>Percentage</td><td>Number</td><td>Percentage</td></tr>
    <tr><td>Named Executive Officers</td><td></td><td></td><td></td><td></td></tr>
    <tr><td>Daniel Meyer</td><td>1,625,520</td><td>4.0%</td><td>1,861,057</td><td>76.6%</td></tr>
    <tr><td>Robert Lynch</td><td>23,969</td><td>2.5%</td><td>—</td><td>—</td></tr>
    </table>"""
    owners = extract_beneficial_ownership(_tree(html))
    assert [(o.name, o.shares, o.percent_of_class) for o in owners] == [
        ("Daniel Meyer", 1_625_520, 4.0),
        ("Robert Lynch", 23_969, 2.5),
    ]


def test_a_footnote_superscript_is_not_a_percent():
    html = """
    <p>Security Ownership of Certain Beneficial Owners and Management</p>
    <table>
    <tr><td>Name</td><td>Total Shares Beneficially Owned</td><td>Percent of Class</td></tr>
    <tr><td>Jennifer Davis</td><td>250,680</td><td><sup>6</sup></td></tr>
    <tr><td>Vanguard Group</td><td>9,000,000</td><td>9.6</td></tr>
    </table>"""
    owners = {o.name: o for o in extract_beneficial_ownership(_tree(html))}
    assert owners["Jennifer Davis"].shares == 250_680
    assert owners["Jennifer Davis"].percent_of_class is None
    assert owners["Vanguard Group"].percent_of_class == 9.6


def test_an_empty_cell_does_not_borrow_the_next_columns_value():
    html = """
    <p>Director Compensation</p>
    <table>
    <tr><td>Name</td><td>Fees Earned or Paid in Cash ($)</td><td>Stock Awards ($)</td><td>Option Awards ($)</td><td>Total ($)</td></tr>
    <tr><td>Marissa Mayer</td><td></td><td></td><td></td><td>$220,784</td></tr>
    <tr><td>Ritch Allison</td><td>—</td><td>$329,921</td><td>—</td><td>$329,921</td></tr>
    </table>"""
    rows = {r.name: r for r in extract_director_compensation(_tree(html))}
    assert _row(rows["Marissa Mayer"], fees_earned=None, stock_awards=None, option_awards=None, total=220_784)
    assert _row(rows["Ritch Allison"], stock_awards=329_921, total=329_921)


def test_fees_skip_subtotals_and_apply_a_stated_unit_before_rounding():
    html = """
    <p>Audit Fees</p>
    <table>
    <tr><td></td><td>2025</td><td>2024</td></tr>
    <tr><td colspan="3">(millions of dollars)</td></tr>
    <tr><td>Audit Fees</td><td>32.0</td><td>34.8</td></tr>
    <tr><td>Audit-Related Fees</td><td>5.2</td><td>4.6</td></tr>
    <tr><td>Subtotal</td><td>37.2</td><td>39.4</td></tr>
    <tr><td>Tax Fees</td><td>0.4</td><td>0.3</td></tr>
    <tr><td>Total</td><td>37.6</td><td>39.7</td></tr>
    </table>"""
    fees = extract_audit_fees(_tree(html))
    assert (fees.audit_fees_current, fees.audit_related_current, fees.tax_fees_current, fees.total_current) == (
        32_000_000, 5_200_000, 400_000, 37_600_000)
    assert fees.total_prior == 39_700_000


def test_a_years_only_table_is_not_an_audit_fee_disclosure():
    html = """
    <p>Audit Fees</p>
    <table>
    <tr><td></td><td>2025</td><td>2024</td></tr>
    <tr><td>Audit Fees</td><td>See below</td><td>See below</td></tr>
    <tr><td>Total Fees</td><td></td><td></td></tr>
    </table>"""
    assert extract_audit_fees(_tree(html)) is None


def test_a_document_without_the_section_yields_nothing():
    tree = _tree("<p>Proposal 1: Election of Directors</p><table><tr><td>a</td></tr></table>")
    assert extract_summary_compensation(tree) is None
    assert extract_beneficial_ownership(tree) is None
    assert extract_director_compensation(tree) is None
    assert extract_audit_fees(tree) is None


# ── Ground truth: Amazon.com DEF 14A, 0001104659-26-041026 ────────────

def test_amzn_summary_compensation(amzn):
    sct = amzn.summary_compensation_table
    jassy = sct[(sct["name"] == "Andrew R. Jassy") & (sct["year"] == 2025)].iloc[0]
    assert (jassy["salary"], jassy["other_compensation"], jassy["total"]) == (365_000, 1_704_861, 2_069_861)
    # The title follows a line break, so the name stops there.
    assert jassy["title"] == "President and Chief Executive Officer"
    # Every executive keeps all three years; the rowspan shift kept only the first.
    assert sorted(sct.loc[sct["name"] == "Andrew R. Jassy", "year"]) == [2023, 2024, 2025]


def test_amzn_beneficial_ownership(amzn):
    own = amzn.beneficial_ownership
    bezos = own[own["holder_name"].str.startswith("Jeffrey P. Bezos")].iloc[0]
    assert (bezos["shares"], bezos["percent_of_class"]) == (950_434_581, 8.8)


def test_amzn_director_compensation_paid_only_in_stock(amzn):
    dcomp = amzn.director_compensation_table
    row = dcomp[dcomp["name"].str.startswith("Daniel P. Huttenlocher")].iloc[0]
    assert row["stock_awards"] == 1_095_757


# ── Ground truth: Coca-Cola DEF 14A, 0001104659-26-028215 ─────────────

def test_ko_summary_compensation(ko):
    sct = ko.summary_compensation_table
    q = sct[(sct["name"] == "James Quincey") & (sct["year"] == 2025)].iloc[0]
    assert (q["salary"], q["stock_awards"], q["option_awards"], q["non_equity_incentive"],
            q["pension_change"], q["other_compensation"], q["total"]) == (
        1_675_000, 12_516_109, 10_352_255, 5_025_000, 1_108_486, 531_315, 31_208_165)


def test_ko_director_compensation_with_labels_stacked_over_six_rows(ko):
    dcomp = ko.director_compensation_table
    allen = dcomp[dcomp["name"] == "Herb Allen"].iloc[0]
    assert (allen["fees_earned"], allen["stock_awards"], allen["other_compensation"], allen["total"]) == (
        110_000, 200_000, 1_229, 311_229)


def test_ko_principal_shareowners(ko):
    own = ko.beneficial_ownership
    berkshire = own[own["holder_name"].str.startswith("Berkshire Hathaway")].iloc[0]
    assert (berkshire["shares"], berkshire["percent_of_class"]) == (400_000_000, 9.29)


def test_ko_audit_fees_in_thousands(ko):
    fees = ko.audit_fees
    assert (fees.audit_fees_current, fees.audit_fees_prior) == (30_587_000, 32_104_000)


# ── Ground truth: Shake Shack DEF 14A, 0001104659-26-051572 ───────────

def test_shak_summary_compensation_under_a_summary_compensation_heading(shak):
    sct = shak.summary_compensation_table
    lynch = sct[(sct["name"] == "Robert Lynch") & (sct["year"] == 2025)].iloc[0]
    assert (lynch["salary"], lynch["stock_awards"], lynch["non_equity_incentive"],
            lynch["other_compensation"], lynch["total"]) == (1_000_000, 5_000_161, 1_011_750, 198_907, 7_210_818)


def test_shak_dual_class_ownership_reads_class_a(shak):
    own = shak.beneficial_ownership
    meyer = own[own["holder_name"] == "Daniel Meyer"].iloc[0]
    assert (meyer["shares"], meyer["percent_of_class"]) == (1_625_520, 4.0)


def test_shak_director_compensation(shak):
    dcomp = shak.director_compensation_table
    balbale = dcomp[dcomp["name"] == "Sumaiya Balbale"].iloc[0]
    assert (balbale["fees_earned"], balbale["stock_awards"], balbale["total"]) == (17_500, 200_073, 217_573)


def test_shak_audit_fees(shak):
    fees = shak.audit_fees
    assert (fees.audit_fees_current, fees.audit_fees_prior, fees.total_current) == (1_705_682, 1_622_068, 1_725_182)
