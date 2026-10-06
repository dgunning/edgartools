"""
Regression test for GitHub issue #1419: once the industry was set, the industry
overrides in gaap_mappings.json changed standard concepts without carrying any
industry knowledge

GitHub Issue: https://github.com/dgunning/edgartools/issues/1419

Fixing the hook (test_issue_1419_industry_from_header_sic.py) let the Fama-French 48
``industry_overrides`` reach ``ReverseIndex.lookup()`` from ``filing.xbrl()`` for the
first time. None of the 10,073 records on 768 tags, in 48 industries, carried industry
knowledge, yet with an industry set 536 lookups answered differently:

- 9,843 restated their base entry's ``standard_tags``, but every one also set
  ``is_total: false`` on a base entry that says true. Wherever every candidate is a
  "Total ..." concept, the guard in ``lookup()`` that keeps a non-total tag off a total
  then dropped the mapping: 306 lookups on 40 tags gave a concept without an industry
  and none with one. For 37 of those tags the base concept is itself wrong, a line item
  mapped to a grand total: ``CommonStockValue`` (7,620 filers) to "Total Stockholders'
  Equity", ``NoninterestBearingDepositLiabilities`` to "Total Deposits",
  ``UnearnedPremiums`` to "Total Liabilities". That defect is in the base mappings, for
  every industry, and is not this fix's to settle.
- 199 narrowed a multi-candidate entry to its first candidate. 188 of them collapsed a
  current/noncurrent choice to current, among them ``DeferredIncomeTaxLiabilitiesNet``
  (2,494 filers), ``LineOfCredit`` (the taxonomy's "Long-Term Line of Credit") and, for
  banks, ``OperatingLeaseLiability``, although the Regulation S-X balance sheets of banks
  (9-03) and insurers (7-03) have no current/noncurrent split at all.
- 31 swapped one concept for another in the same statement section: ``OtherIncome``
  from Other Income (``OtherIncomeIS``) to the Non-Operating Income (Expense) aggregate
  (``NonoperatingIncomeExpense``) in 17 industries, and
  ``RestrictedCashAndCashEquivalents`` from Other Current Assets to Restricted Cash,
  Current in 14. Neither is industry knowledge; whether an insurer's other revenues
  belong in revenue is a question for the base entry.

All of them were removed, so the base entry answers for every industry. These tests
check that the answer does not depend on the industry, not which answer is right. The
first holds that line for every tag and industry: an override may add to a base
mapping but never lose any of it, and today none changes a lookup at all. A curated
override added later will have to replace the first test's assertions with ones about
its own records. The others pin ten of the lookups, the issue's own example among them,
and two real bank 10-Ks whose statements standardized differently once the industry
was set:

  Auburn National Bancorporation FY2023 10-K (0001193125-24-067944), SIC 6022 -> Banks:
    "Noninterest-bearing deposits" (270,723 thousand) and "Common stock" (39 thousand)
    had a standard concept without the industry and none with it.
  JPMorgan Chase FY2023 10-K (0000019617-24-000225), SIC 6021 -> Banks:
    "Common stock" had a standard concept without the industry and none with it, and
    "Accounts payable and other liabilities" lost its noncurrent candidate and became
    TradePayables.

The amounts were read from the filed 10-K (d731871d10k.htm, balance sheet at
December 31, 2023).
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"
AUBN_10K = FIXTURES / "aubn" / "10k_2023"  # Auburn National Bancorporation, FY2023
JPM_10K = FIXTURES / "jpm" / "10k_2024"  # JPMorgan Chase, FY2023, filed 2024-02-16


def _industries(index):
    """Every industry the hook can set, plus any the mapping data keys an override on."""
    industries = {industry for _, _, industry in _FF48_SIC_RANGES}
    for entry in index._index.values():
        if isinstance(entry, dict):
            industries.update(entry.get("industry_overrides") or {})
    return sorted(industries)


def _compare(base, with_industry):
    """'same', 'added' (keeps every base candidate in order and adds to them) or 'lost'."""
    if with_industry == base:
        return "same"
    if base is None:
        return "added"
    if with_industry is None:
        return "lost"
    kept = with_industry.standard_concepts[: len(base.standard_concepts)] == base.standard_concepts
    return "added" if kept else "lost"


def test_no_industry_loses_a_base_mapping():
    index = get_reverse_index()
    industries = _industries(index)
    lost, added = [], []
    for tag in index._index:
        base = index.lookup(tag)
        for industry in industries:
            with_industry = index.lookup(tag, industry=industry)
            outcome = _compare(base, with_industry)
            if outcome == "same":
                continue
            found = (
                tag,
                industry,
                base.standard_concepts if base else None,
                with_industry.standard_concepts if with_industry else None,
            )
            (lost if outcome == "lost" else added).append(found)

    # A dropped, narrowed or swapped mapping: 536 of them before the fix.
    assert lost == [], f"{len(lost)} lookups lose a base mapping once the industry is set, e.g. {lost[:5]}"
    # Additions would be allowed, but no override ships today: every record the
    # generator wrote restated, narrowed or swapped its base entry. An industry
    # mapping added later should cite the statement format it comes from.
    assert added == []


# (tag, industry, what the lookup answered with the industry set before the fix)
REPORTED = [
    # Dropped: every candidate is a "Total ..." concept, and the record said the tag is not a total.
    ("CommonStockValue", "Util", None),
    ("NoninterestBearingDepositLiabilities", "Banks", None),
    ("UnearnedPremiums", "Insur", None),
    ("OperatingCostsAndExpenses", "Fin", None),
    # Narrowed to the first (current) candidate.
    ("DeferredIncomeTaxLiabilitiesNet", "Banks", ["DeferredTaxCurrentLiabilities"]),
    ("LineOfCredit", "Banks", ["ShortTermDebt"]),
    ("OperatingLeaseLiability", "Banks", ["OperatingLeaseCurrentDebtEquivalent"]),
    ("AccruedIncomeTaxes", "Banks", ["TaxesPayable"]),  # the example in the issue
    # Swapped.
    ("OtherIncome", "Insur", ["NonoperatingIncomeExpense"]),
    ("RestrictedCashAndCashEquivalents", "Banks", ["RestrictedCashCurrent"]),
]


@pytest.mark.parametrize(
    "tag, industry",
    [(tag, industry) for tag, industry, _ in REPORTED],
    ids=[f"{tag}-{industry}" for tag, industry, _ in REPORTED],
)
def test_reported_lookup_answers_as_the_base_entry_does(tag, industry):
    index = get_reverse_index()

    # Whatever the base entry answers, a concept or None, the industry must not change it.
    assert index.lookup(tag, industry=industry) == index.lookup(tag)


def _standard_concept(value):
    """A row's standard_concept, with the NaN of a row that has none read as None."""
    return value if isinstance(value, str) else None


def _standard_concepts(statement):
    df = statement.to_dataframe()
    return [(concept, _standard_concept(standard)) for concept, standard in zip(df["concept"], df["standard_concept"], strict=True)]


@pytest.mark.parametrize("directory, sic", [(AUBN_10K, "6022"), (JPM_10K, "6021")], ids=["AUBN", "JPM"])
def test_bank_10k_standardizes_the_same_with_its_industry_set(directory, sic):
    xbrl = XBRL.from_directory(directory)
    statements = [
        xbrl.statements.balance_sheet(),
        xbrl.statements.income_statement(),
        xbrl.statements.cash_flow_statement(),
    ]
    assert None not in statements
    without_industry = [_standard_concepts(statement) for statement in statements]

    # The call the filing.xbrl() hook makes with the header's SIC.
    assert xbrl.standardization.set_industry_from_sic(sic) == "Banks"
    with_industry = [_standard_concepts(statement) for statement in statements]

    assert with_industry == without_industry


def _row(df, concept):
    rows = df[df["concept"] == concept]
    assert len(rows) == 1, f"{concept}: {len(rows)} rows"
    return rows.iloc[0]


@pytest.mark.parametrize(
    "concept, filed",
    [
        ("us-gaap_NoninterestBearingDepositLiabilities", 270_723_000),  # Noninterest-bearing deposits
        ("us-gaap_CommonStockValue", 39_000),  # Common stock
    ],
    ids=["noninterest-bearing deposits", "common stock"],
)
def test_bank_row_gets_the_same_standard_concept_with_its_industry_set(concept, filed):
    xbrl = XBRL.from_directory(AUBN_10K)
    balance_sheet = xbrl.statements.balance_sheet()
    assert balance_sheet is not None
    without_industry = _row(balance_sheet.to_dataframe(), concept)

    xbrl.standardization.set_industry_from_sic("6022")
    with_industry = _row(balance_sheet.to_dataframe(), concept)

    assert with_industry["2023-12-31"] == filed
    # Before the fix this row had a standard concept without the industry and none with
    # it. Which concept it should have is the base mapping's business, not this fix's;
    # the industry must not change it.
    assert _standard_concept(with_industry["standard_concept"]) == _standard_concept(without_industry["standard_concept"])
