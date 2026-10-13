"""
A ...CurrentAndNoncurrent element can sit in either section of a classified
balance sheet. ``ReverseIndex._disambiguate_by_context`` read the tag name
before the section, and treated "nonoperating" as "noncurrent", so both
sections resolved to one side.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1434

For mappings with current and noncurrent candidates, a matching statement
section takes precedence over the tag-name hint. Role URIs and blank statement
types use the untyped section lookup; "Non-Current" is not read as "current"
just because it contains the word.
The default ``EquitySecuritiesFvNiCurrentAndNoncurrent`` pair now contains
short-term and long-term investment concepts. Its existing Banks and Insur
overrides still select CashAndMarketableSecurities until #1432 removes them.

Ground truth: JPMorgan Chase's FY2023 10-K (0000019617-24-000225) reports
"Accounts payable and other liabilities" of $290,307 million on an unclassified
balance sheet, tagged AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent.
With no current/noncurrent section this mapping resolves to its first concept,
TradePayables. The tag name used to make it
OtherOperatingNonCurrentLiabilities.
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization.reverse_index import ReverseIndex, get_reverse_index

ROLE_URI = "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS"
JPM_FY2023 = Path("tests/fixtures/xbrl/jpm/10k_2024")


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def resolve(index, tag, section, statement_type="BalanceSheet"):
    return index.get_standard_concept(tag, context={"section": section, "statement_type": statement_type})


@pytest.mark.parametrize("statement_type", ["BalanceSheet", ROLE_URI, ""], ids=["typed", "role-uri", "untyped"])
@pytest.mark.parametrize(
    "tag, section, expected",
    [
        # Name hint used to return the noncurrent candidate in both sections.
        ("AccountsPayableCurrentAndNoncurrent", "Current Liabilities", "TradePayables"),
        ("AccountsPayableCurrentAndNoncurrent", "Non-Current Liabilities", "OtherOperatingNonCurrentLiabilities"),
        ("AccruedBonusesCurrentAndNoncurrent", "Current Liabilities", "OtherOperatingCurrentLiabilities"),
        ("AccruedBonusesCurrentAndNoncurrent", "Non-Current Liabilities", "OtherOperatingNonCurrentLiabilities"),
        # "nonoperating" used to count as "noncurrent", so the current candidate won both sections.
        ("AccountsPayableOtherCurrentAndNoncurrent", "Current Liabilities", "OtherNonOperatingCurrentLiabilities"),
        ("AccountsPayableOtherCurrentAndNoncurrent", "Non-Current Liabilities", "OtherNonOperatingNonCurrentLiabilities"),
        ("AccountsPayableOtherCurrentAndNoncurrent", "Noncurrent Liabilities", "OtherNonOperatingNonCurrentLiabilities"),
        # The default equity-securities pair follows the current or noncurrent asset section.
        ("EquitySecuritiesFvNiCurrentAndNoncurrent", "Current Assets", "ShortTermInvestments"),
        ("EquitySecuritiesFvNiCurrentAndNoncurrent", "Non-Current Assets", "LongtermInvestments"),
    ],
)
def test_the_section_decides_between_current_and_noncurrent(index, tag, section, expected, statement_type):
    assert resolve(index, tag, section, statement_type) == expected


def test_no_section_keeps_the_first_candidate(index):
    """With no section, the pair's first concept is the answer."""
    assert (
        index.get_standard_concept(
            "AccountsPayableCurrentAndNoncurrent",
            context={"statement_type": "BalanceSheet"},
        )
        == "TradePayables"
    )


def test_an_unclassified_section_keeps_the_first_candidate(index):
    """'Liabilities' names neither side, so the name hint must not pick one."""
    assert resolve(index, "AccountsPayableCurrentAndNoncurrent", "Liabilities") == "TradePayables"


@pytest.mark.parametrize(
    "tag, section, expected",
    [
        ("AccountsPayableCurrentAndNoncurrent", "Long-Term Liabilities", "OtherOperatingNonCurrentLiabilities"),
        ("AccountsPayableCurrentAndNoncurrent", "Longterm Liabilities", "OtherOperatingNonCurrentLiabilities"),
        # Neither candidate's name says which side it is on, so only the
        # section match can tell that 'Long-Term Liabilities' is noncurrent.
        (
            "AccruedCappingClosurePostClosureAndEnvironmentalCosts",
            "Long-Term Liabilities",
            "DefiniteLivedOperatingProvisions(DecommissioningEtc)",
        ),
        # A section that names no asset or liability side is settled by its words.
        ("CapitalLeaseObligations", "Long-Term Debt", "LongTermDebt"),
    ],
)
def test_long_term_section_is_noncurrent(index, tag, section, expected):
    """'Long-term' is the noncurrent side, including the hyphenated spelling."""
    assert resolve(index, tag, section) == expected


def test_a_misplaced_line_still_follows_the_noncurrent_side(index):
    """
    A receivable that lands in a 'Non-Current Liabilities' block matches neither
    candidate's section, so the words decide. 'Non-Current' is not 'current',
    and 'NonOperating' is not 'NonCurrent'.
    """
    assert resolve(index, "AccountsReceivableRelatedParties", "Non-Current Liabilities") == "OtherNonOperatingNonCurrentAssets"


def test_nonoperating_in_a_candidate_is_not_a_noncurrent_hint(tmp_path):
    """
    A tag named for the noncurrent side picks the noncurrent candidate, not the
    first candidate that merely says 'NonOperating'. No shipped mapping lists a
    current 'NonOperating' concept ahead of the noncurrent one for such a tag,
    so the rule is pinned with a one-entry mapping file.
    """
    mappings = tmp_path / "gaap_mappings.json"
    mappings.write_text(
        json.dumps(
            {
                "OtherAssetsNoncurrentExample": {
                    "standard_tags": ["OtherNonOperatingCurrentAssets", "OtherNonOperatingNonCurrentAssets"],
                    "ambiguous": True,
                }
            }
        ),
        encoding="utf-8",
    )
    index = ReverseIndex(gaap_mappings_path=str(mappings))
    assert (
        index.get_standard_concept("OtherAssetsNoncurrentExample", context={"statement_type": "BalanceSheet"}) == "OtherNonOperatingNonCurrentAssets"
    )


def test_default_equity_securities_pair_uses_investments(index):
    """Without an industry override, the pair contains short-term and long-term investments."""
    tag = "EquitySecuritiesFvNiCurrentAndNoncurrent"
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == ["ShortTermInvestments", "LongtermInvestments"]
    assert result.display_names == ["Short-Term Investments", "Long-Term Investments"]
    assert result.is_ambiguous is True
    assert "CashAndMarketableSecurities" not in result.standard_concepts
    entry = index._gaap_mappings[tag]
    assert entry["display_name"] == "Short-Term Investments"
    assert entry["statement"] == "BalanceSheet"
    assert entry["section"] == "Current Assets"
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert entry["ambiguous"] is True


def test_jpmorgan_accounts_payable_is_accounts_payable():
    """JPMorgan Chase FY2023 10-K, accession 0000019617-24-000225."""
    balance_sheet = XBRL.from_directory(JPM_FY2023).statements.balance_sheet()
    assert balance_sheet is not None
    df = balance_sheet.to_dataframe(standard=True)
    row = df[df["concept"] == "us-gaap_AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent"]
    assert len(row) == 1
    assert row["2023-12-31"].iloc[0] == 290_307_000_000
    assert row["standard_concept"].iloc[0] == "TradePayables"


@pytest.mark.parametrize("statement_type", ["BalanceSheet", ROLE_URI, ""], ids=["typed", "role-uri", "untyped"])
@pytest.mark.parametrize(
    "section, expected",
    [("Current Liabilities", "ShortTermDebt"), ("Non-Current Liabilities", "LongTermDebt")],
)
def test_section_overrides_a_contradicting_long_term_name(tmp_path, statement_type, section, expected):
    """Pin the rule independently of which debt-disclosure mappings are shipped."""
    mappings = tmp_path / "gaap_mappings.json"
    tag = "DebtLongtermAndShorttermExample"
    mappings.write_text(
        json.dumps({tag: {"standard_tags": ["LongTermDebt", "ShortTermDebt"], "ambiguous": True}}),
        encoding="utf-8",
    )
    index = ReverseIndex(gaap_mappings_path=str(mappings))
    assert resolve(index, tag, section, statement_type) == expected


@pytest.mark.parametrize("statement_type", ["BalanceSheet", ROLE_URI, ""], ids=["typed", "role-uri", "untyped"])
@pytest.mark.parametrize("concept_section", ["Long-Term Liabilities", "Longterm Liabilities"])
def test_long_term_concept_section_matches_noncurrent_context(tmp_path, monkeypatch, statement_type, concept_section):
    """Recognize the section alias without candidate-name fallbacks deciding it."""
    from edgar.xbrl.standardization import sections

    mappings = tmp_path / "gaap_mappings.json"
    tag = "SectionAliasExample"
    mappings.write_text(
        json.dumps({tag: {"standard_tags": ["CandidateOne", "CandidateTwo"], "ambiguous": True}}),
        encoding="utf-8",
    )
    candidate_sections = {"CandidateOne": "Current Liabilities", "CandidateTwo": concept_section}
    monkeypatch.setattr(sections, "get_section_for_concept", lambda concept, statement_type=None: candidate_sections.get(concept))
    index = ReverseIndex(gaap_mappings_path=str(mappings))
    assert resolve(index, tag, "Non-Current Liabilities", statement_type) == "CandidateTwo"
