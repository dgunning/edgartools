"""Regression test: identify_concepts() gave one element two answers, one per separator.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1418

`SynonymGroup._strip_namespace` had a different rule for each separator. A
colon-form tag lost whatever prefix it had; an underscore-form tag lost only a
prefix on a fixed list ('usgaap', 'dei', 'srt' or 'ifrs' once hyphens were
removed). EdgarTools hands callers both spellings of one element: the facts
frame's `concept` column holds the QName (`ifrs-full:CostOfSales`) and a
statement frame's `concept` column holds the element id
(`ifrs-full_CostOfSales`). So `identify_concepts`, `identify_concept` and
`SynonymGroup.contains_tag` answered differently for the same element:

- IFRS. 'ifrs-full' became 'ifrsfull', which was not on the list. On TSMC's
  FY2025 20-F (0001628280-26-025362), all 22 income-statement rows whose
  concept has a builtin synonym (11 concepts, `ifrs-full_CostOfSales` to
  `ifrs-full_DilutedEarningsLossPerShare`) identified as nothing, while the
  same `ifrs-full:` QNames identified correctly.
- Extensions. Any colon prefix was dropped, so a filer's own element matched a
  builtin synonym by its local name. Onto Innovation tags net income with its
  extension `onto:NetIncome` (10-Q for Q1 2024, 0000950170-24-057270:
  46,853,000). The QName identified as `net_income`; the element id
  `onto_NetIncome`, from the income statement frame, as nothing.

Both separators now follow one rule. A standard taxonomy prefix (`us-gaap`,
`ifrs-full`, `dei`, `srt`) is dropped and the local name looked up. Any other
prefix, such as a filer's extension, names a different concept, so the tag
matches no builtin synonym. A bare local name is looked up as before.

The TSMC and Onto tags below are verbatim from those filings; `orcl:Revenues`
is the issue's own example. Offline.
"""

import pytest

from edgar.standardization import SynonymGroups

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def synonyms():
    return SynonymGroups()


def names(synonyms, tag):
    return [info.name for info in synonyms.identify_concepts(tag)]


# TSMC FY2025 20-F income statement: each IFRS concept with a builtin synonym.
TSMC_INCOME_STATEMENT = [
    ("CostOfSales", "cost_of_revenue"),
    ("GrossProfit", "gross_profit"),
    ("ResearchAndDevelopmentExpense", "research_and_development"),
    ("GeneralAndAdministrativeExpense", "sga_expense"),
    ("ProfitLossFromOperatingActivities", "operating_income"),
    ("ProfitLossBeforeTax", "income_before_tax"),
    ("IncomeTaxExpenseContinuingOperations", "income_tax_expense"),
    ("ProfitLoss", "net_income"),
    ("ProfitLossAttributableToOwnersOfParent", "net_income"),
    ("BasicEarningsLossPerShare", "earnings_per_share_basic"),
    ("DilutedEarningsLossPerShare", "earnings_per_share_diluted"),
]


@pytest.mark.parametrize(("local_name", "concept"), TSMC_INCOME_STATEMENT)
def test_an_ifrs_element_id_identifies_like_its_qname(synonyms, local_name, concept):
    element_id, qname = f"ifrs-full_{local_name}", f"ifrs-full:{local_name}"

    assert names(synonyms, element_id) == names(synonyms, qname) == [concept]
    assert synonyms.identify_concept(element_id).name == concept
    assert synonyms.get_group(concept).contains_tag(element_id)


@pytest.mark.parametrize("tag", ["onto:NetIncome", "onto_NetIncome"])
def test_an_extension_element_matches_no_builtin_synonym(synonyms, tag):
    assert names(synonyms, tag) == []
    assert synonyms.identify_concept(tag) is None
    assert not synonyms.get_group("net_income").contains_tag(tag)


@pytest.mark.parametrize(
    ("qname", "expected"),
    [
        ("us-gaap:Revenues", ["revenue"]),
        ("us-gaap:NetIncomeLoss", ["net_income"]),
        ("ifrs-full:Revenue", ["revenue"]),
        ("onto:NetIncome", []),
        ("orcl:Revenues", []),
    ],
)
def test_both_spellings_of_an_element_give_one_answer(synonyms, qname, expected):
    element_id = qname.replace(":", "_", 1)

    assert names(synonyms, qname) == names(synonyms, element_id) == expected


def test_a_bare_local_name_is_still_looked_up(synonyms):
    assert names(synonyms, "NetIncome") == ["net_income"]
    assert names(synonyms, "Revenues") == ["revenue"]
