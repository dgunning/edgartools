"""
Regression tests for edgartools-hxnw (GH #1249): negated preferred labels that
rendered with the filed positive sign — a wrong number in a financial statement.

Two independent matchers decided whether a preferredLabel role meant "negate for
display", and both were wrong in different ways.

  edgar/xbrl/xbrl.py     A substring test requiring the role to either start with
                         'negated' or contain '/role/negated'. The legacy xbrl.us
                         role is 'http://xbrl.us/us-gaap/role/label/negated' —
                         its path segment is '/role/label/negated', so neither
                         disjunct held and every negated line in a 2009-2011
                         filing kept the filed positive sign.

  edgar/xbrl/facts.py    An exact-match whitelist of eight strings covering only
                         the 2003 namespace and bare label names. Filings use the
                         2009 namespace, so this matched NOTHING: measured across
                         the committed fixtures, `preferred_sign == -1` appeared
                         on zero of 1,075 AAPL FY2023 facts, zero of 1,059 TSLA
                         and zero of 1,526 UNP facts. Negation on the Facts API
                         was not incomplete, it was entirely dead.

Both now read `is_negated_label_role`, so the two surfaces cannot disagree about
the sign of the same fact.

Ground truth is Apple's FY2010 10-K cash flow statement (fiscal year ended
2010-09-25), whose investing section the SEC-filed document shows in parentheses.
That filing uses the legacy xbrl.us role, which is what makes it the repro.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.models import is_negated_label_role

AAPL_2010 = Path("tests/fixtures/xbrl/aapl/10k_2010")
AAPL_2023 = Path("tests/fixtures/xbrl/aapl/10k_2023")

LEGACY_XBRL_US_ROLE = "http://xbrl.us/us-gaap/role/label/negated"
FY2010 = "duration_2009-09-27_2010-09-25"

# AAPL FY2010 10-K, cash flow statement. Values as FILED (positive); the document
# displays each in parentheses, so the presentation sign must be -1.
FY2010_NEGATED_FILED_VALUES = {
    "us-gaap_PaymentsToAcquireAvailableForSaleSecuritiesDebt": 57_793_000_000.0,
    "us-gaap_IncreaseDecreaseInAccountsReceivable": 2_142_000_000.0,
    "us-gaap_IncreaseDecreaseInOtherReceivables": 2_718_000_000.0,
}
# PaymentsToAcquireProductiveAssets is also negated here and would be a third
# case, but it appears twice in this role (once for retail), so a concept-keyed
# lookup cannot address one occurrence — see edgartools-f07v.



@pytest.mark.parametrize(
    "role, expected",
    [
        # The legacy xbrl.us LRR role that GH #1249 is about — the extra
        # '/label' segment is what defeated the old substring test.
        (LEGACY_XBRL_US_ROLE, True),
        ("http://xbrl.us/us-gaap/role/label/negatedLabel", True),
        # The modern namespace, including the roles the facts whitelist omitted.
        ("http://www.xbrl.org/2009/role/negatedLabel", True),
        ("http://www.xbrl.org/2009/role/negatedTotalLabel", True),
        ("http://www.xbrl.org/2009/role/negatedNetLabel", True),
        ("http://www.xbrl.org/2009/role/negatedPeriodStartLabel", True),
        ("http://www.xbrl.org/2003/role/negatedLabel", True),
        ("http://www.xbrl.org/lrr/role/negated", True),
        # The bare forms a linkbase may carry.
        ("negatedLabel", True),
        ("negatedTerseLabel", True),
        # Non-negated roles, and the case that a plain substring search would
        # get wrong: 'negated' appears in the URI but not as the local name.
        ("http://www.xbrl.org/2003/role/label", False),
        ("http://www.xbrl.org/2003/role/totalLabel", False),
        ("http://www.xbrl.org/2003/role/periodStartLabel", False),
        ("http://example.com/negated/role/label", False),
        ("", False),
        (None, False),
    ],
)
def test_negated_role_matcher(role, expected):
    assert is_negated_label_role(role) is expected


@pytest.fixture(scope="module")
def aapl_2010():
    return XBRL.from_directory(AAPL_2010)


@pytest.fixture(scope="module")
def aapl_2023():
    return XBRL.from_directory(AAPL_2023)


def test_legacy_role_negates_on_the_statement_path(aapl_2010):
    """The statement path assigns preferred_sign == -1 to the legacy role."""
    by_concept = {
        item["concept"]: item
        for item in aapl_2010.get_statement("CashFlowStatement")
    }

    for concept, filed_value in FY2010_NEGATED_FILED_VALUES.items():
        item = by_concept[concept]
        assert item["preferred_label"] == LEGACY_XBRL_US_ROLE, concept
        assert item["values"][FY2010] == filed_value, concept
        # This was +1 before the fix, so the displayed figure carried the filed
        # positive sign where Apple's 10-K shows it in parentheses.
        assert item["preferred_signs"][FY2010] == -1, concept


def test_legacy_role_negates_on_the_facts_path(aapl_2010):
    """The Facts API agrees with the statement path about the same facts."""
    df = aapl_2010.facts.query().to_dataframe()

    negated = df[df["preferred_sign"] == -1]
    # The whitelist matched none of these, on any filing.
    assert len(negated) > 0

    for concept in FY2010_NEGATED_FILED_VALUES:
        element_id = concept.replace("_", ":", 1)
        rows = df[(df["concept"] == element_id) & (df["preferred_sign"] == -1)]
        assert len(rows) > 0, f"{element_id} carries no negated fact"


def test_modern_namespace_negates_on_the_facts_path(aapl_2023):
    """
    The dead whitelist was not a legacy-only problem: it covered the 2003
    namespace while filings use 2009, so a modern filing got no negation either.
    """
    df = aapl_2023.facts.query().to_dataframe()
    assert (df["preferred_sign"] == -1).sum() > 0


def test_statement_path_unchanged_on_a_modern_filing(aapl_2023):
    """
    The modern roles already matched xbrl.py's substring test, so widening the
    matcher must not change which rows a current filing negates.
    """
    negated = [
        item["concept"]
        for item in aapl_2023.get_statement("CashFlowStatement")
        if any(sign == -1 for sign in (item.get("preferred_signs") or {}).values())
    ]
    # Measured on the fixture before and after the fix: 13 rows, unchanged.
    assert len(negated) == 13
    assert "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment" in negated
