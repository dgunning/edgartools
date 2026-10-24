"""Regression test for GH #1680: statement rows for us-gaap-supplement concepts were blank.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1680

The FASB supplement schema (2022-2023 taxonomies) gives its elements 'us-gaap_'
fragment IDs, so the presentation linkbase names the row
us-gaap_InvestmentCompanyExpenseAfterReductionOfFeeWaiverAndReimbursement, while
the instance declares the facts under the us-gaap-supplement prefix. The row
looked up facts by the linkbase ID, found none, and stayed blank. A fact key
with the same local name under a prefix that extends the element's prefix is
now used when the linkbase ID has no facts.

Ground truth: Gladstone Investment 10-K for FY ended 2023-03-31
(0001321741-23-000011), Consolidated Statements of Operations, "Total expenses,
net of credits to fees" 44,543 / 57,562 / 38,689 thousand for fiscal 2023 / 2022
/ 2021, filed as us-gaap-supplement:InvestmentCompanyExpenseAfterReductionOf
FeeWaiverAndReimbursement.
"""
import pytest

from edgar import find
from edgar.xbrl import XBRL

LOCAL = "InvestmentCompanyExpenseAfterReductionOfFeeWaiverAndReimbursement"
ROLE = "http://example.com/role/StatementsOfOperations"
GAAP = "https://xbrl.fasb.org/us-gaap/2022/elts/us-gaap-2022.xsd"
SUPP = "https://xbrl.fasb.org/us-gaap/2022/elts/us-gaap-supplement-2022.xsd"
ARC = 'xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/'
LINKBASE = '<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">'


def _write_filing(directory):
    """A one-statement filing shaped like Gladstone's: the linkbase points at the
    supplement schema with a us-gaap_ fragment, the instance uses us-gaap-supplement."""
    concepts = [(GAAP, "us-gaap_IncomeStatementAbstract", "Statements of Operations"),
                (GAAP, "us-gaap_InvestmentIncomeInterest", "Interest income"),
                (SUPP, f"us-gaap_{LOCAL}", "Total expenses, net of credits to fees")]
    locs = "".join(f'<link:loc xlink:type="locator" xlink:href="{schema}#{name}" xlink:label="l{i}"/>'
                   for i, (schema, name, _) in enumerate(concepts))
    labels = "".join(f'<link:label xlink:type="resource" xlink:label="t{i}" xml:lang="en-US" '
                     f'xlink:role="http://www.xbrl.org/2003/role/label">{text}</link:label>'
                     f'<link:labelArc {ARC}concept-label" xlink:from="l{i}" xlink:to="t{i}"/>'
                     for i, (_, _, text) in enumerate(concepts))
    arcs = "".join(f'<link:presentationArc {ARC}parent-child" xlink:from="l0" xlink:to="l{i}" order="{i}"/>'
                   for i in (1, 2))
    (directory / "ex_lab.xml").write_text(
        f'{LINKBASE}<link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">'
        f'{locs}{labels}</link:labelLink></link:linkbase>')
    (directory / "ex_pre.xml").write_text(
        f'{LINKBASE}<link:roleRef roleURI="{ROLE}" xlink:type="simple" xlink:href="ex.xsd#Ops"/>'
        f'<link:presentationLink xlink:type="extended" xlink:role="{ROLE}">{locs}{arcs}'
        f'</link:presentationLink></link:linkbase>')
    period = "<xbrli:startDate>2022-04-01</xbrli:startDate><xbrli:endDate>2023-03-31</xbrli:endDate>"
    (directory / "ex.xml").write_text(
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
        'xmlns:us-gaap="http://fasb.org/us-gaap/2022" xmlns:us-gaap-supplement="http://fasb.org/us-gaap-supplement/2022">'
        '<xbrli:context id="FY2023"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0001321741'
        f'</xbrli:identifier></xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>'
        '<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        '<us-gaap:InvestmentIncomeInterest contextRef="FY2023" unitRef="USD" decimals="-3">100000000'
        '</us-gaap:InvestmentIncomeInterest>'
        f'<us-gaap-supplement:{LOCAL} contextRef="FY2023" unitRef="USD" decimals="-3">44543000'
        f'</us-gaap-supplement:{LOCAL}></xbrli:xbrl>')


def _xbrl_with_index(keys):
    xbrl = XBRL()
    xbrl._element_context_index = {key: ["c1"] for key in keys}
    return xbrl


@pytest.mark.fast
def test_linkbase_id_resolves_to_the_supplement_fact_key():
    xbrl = _xbrl_with_index([f"us-gaap-supplement_{LOCAL}", "us-gaap_Revenues"])
    assert xbrl._fact_element_key(f"us-gaap_{LOCAL}") == f"us-gaap-supplement_{LOCAL}"
    assert xbrl._fact_element_key("us-gaap_Revenues") == "us-gaap_Revenues"


@pytest.mark.fast
def test_no_guess_when_the_match_is_absent_or_ambiguous():
    xbrl = _xbrl_with_index([f"us-gaap-supplement_{LOCAL}", f"us-gaap-other_{LOCAL}", "abc_Revenues"])
    assert xbrl._fact_element_key(f"us-gaap_{LOCAL}") == f"us-gaap_{LOCAL}"
    # A different prefix that merely shares the local name is not a variant.
    assert xbrl._fact_element_key("us-gaap_Revenues") == "us-gaap_Revenues"


@pytest.mark.fast
def test_supplement_row_carries_its_value_end_to_end(tmp_path):
    _write_filing(tmp_path)
    rows = {row["concept"]: row["values"] for row in XBRL.from_directory(tmp_path).get_statement(ROLE)}
    assert rows[f"us-gaap_{LOCAL}"] == {"duration_2022-04-01_2023-03-31": 44_543_000}  # was {}
    assert rows["us-gaap_InvestmentIncomeInterest"] == {"duration_2022-04-01_2023-03-31": 100_000_000}


@pytest.mark.network
def test_gladstone_total_expenses_row_has_its_filed_values():
    xbrl = find("0001321741-23-000011").xbrl()
    df = xbrl.statements.income_statement().to_dataframe(view="summary", standard=False)
    row = df[df["concept"] == f"us-gaap_{LOCAL}"].iloc[0]
    assert row["2023-03-31 (FY)"] == 44_543_000
    assert row["2022-03-31 (FY)"] == 57_562_000
    assert row["2021-03-31 (FY)"] == 38_689_000
