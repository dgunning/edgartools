"""
Regression tests for edgartools-0q0d (GH #1245): `get_statement()` omitted every
fact beneath the second and later roots of a multi-root presentation role.

Nothing was lost at parse time. `_build_presentation_role` finds all roots and
builds every root's subtree into `all_nodes`, but `PresentationTree` carried a
single `root_element_id` — `root_elements[0]` — and `get_statement()` walked down
from that one root, so the remaining subtrees sat in `all_nodes` structurally
unreachable. Since the root list is sorted for determinism, which subtree
survived was alphabetical, unrelated to the filer's intent.

A role with several roots is ordinary rather than malformed. Measured across the
committed fixture corpus, 9 of 2,052 roles are multi-root, concentrated in two
issuers — and one of the nine is a PRIMARY FACE STATEMENT, Union Pacific's
consolidated statement of comprehensive income, whose net income line was absent
entirely. Recovering the missing roots adds 106 rows across those 9 roles and
changes nothing in the other 2,043.

`PresentationTree` now carries `root_element_ids`; `root_element_id` remains as
the first root for callers that assume one.

Ground truth is Union Pacific's FY2012 10-K. Net income of $3,943M and other
comprehensive income of -$132M sum to the filed comprehensive income of $3,811M,
which is the arithmetic the missing root broke.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

FIXTURE = Path("tests/fixtures/xbrl/unp")

FY2012 = "duration_2012-01-01_2012-12-31"
AT_2012 = "instant_2012-12-31"

# UNP FY2012 10-K, statement of comprehensive income.
NET_INCOME = 3_943_000_000.0
OTHER_COMPREHENSIVE_INCOME = -132_000_000.0
COMPREHENSIVE_INCOME = 3_811_000_000.0

# UNP FY2012 10-K, leases note: the operating-lease schedule, which lives
# entirely under the role's second root and was absent in full.
OPERATING_LEASE_PAYMENTS = {
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueCurrent": 525_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueInTwoYears": 466_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueInThreeYears": 410_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueInFourYears": 375_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueInFiveYears": 339_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDueThereafter": 2_126_000_000.0,
    "us-gaap_OperatingLeasesFutureMinimumPaymentsDue": 4_241_000_000.0,
}


@pytest.fixture(scope="module")
def unp():
    return XBRL.from_directory(FIXTURE)


def _role_ending(xbrl, suffix):
    role = next((r for r in xbrl.presentation_trees if r.endswith(suffix)), None)
    assert role is not None, f"no presentation role ending in {suffix}"
    return role


def test_tree_carries_every_root(unp):
    role = _role_ending(unp, "LeasesDetails")
    tree = unp.presentation_trees[role]

    assert tree.root_element_ids == [
        "us-gaap_CapitalLeasesFutureMinimumPaymentsDueAbstract",
        "us-gaap_OperatingLeasesFutureMinimumPaymentsDueAbstract",
    ]
    # The scalar still answers, as the first of the list.
    assert tree.root_element_id == tree.root_element_ids[0]


def test_no_node_is_unreachable(unp):
    """
    Every node the parser built must be reachable from some root. The role has
    22 nodes and returned 13 rows.
    """
    role = _role_ending(unp, "LeasesDetails")
    tree = unp.presentation_trees[role]

    rows = unp.get_statement(role)
    reached = {row["concept"] for row in rows if not row.get("is_dimension")}

    assert reached == set(tree.all_nodes)
    assert len(rows) == 22


def test_the_second_root_s_schedule_is_present(unp):
    """The operating-lease schedule, absent in full before the fix."""
    rows = unp.get_statement(_role_ending(unp, "LeasesDetails"))
    values = {
        row["concept"]: row["values"].get(AT_2012)
        for row in rows
        if not row.get("is_dimension")
    }

    for concept, filed in OPERATING_LEASE_PAYMENTS.items():
        assert values[concept] == filed, concept

    # The capital-lease schedule under the first root is untouched.
    assert values["us-gaap_CapitalLeasesFutureMinimumPaymentsDueCurrent"] == 282_000_000.0


def test_a_face_statement_was_truncated_too(unp):
    """
    This is why the bug is P1: multi-root is not confined to disclosure details.
    Net income sits under the second root of the consolidated statement of
    comprehensive income and was missing from it.
    """
    role = _role_ending(unp, "ConsolidatedStatementsOfComprehensiveIncome")
    rows = unp.get_statement(role)
    values = {
        row["concept"]: row["values"].get(FY2012)
        for row in rows
        if not row.get("is_dimension")
    }

    assert values["us-gaap_NetIncomeLoss"] == NET_INCOME
    assert values["us-gaap_OtherComprehensiveIncomeLossNetOfTax"] == OTHER_COMPREHENSIVE_INCOME
    comprehensive = values[
        "us-gaap_ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest"
    ]
    assert comprehensive == COMPREHENSIVE_INCOME
    # The statement now reconciles, which it could not while net income was absent.
    assert NET_INCOME + OTHER_COMPREHENSIVE_INCOME == comprehensive


def test_single_root_roles_are_unaffected(unp):
    """
    The overwhelming majority of roles have one root and must be untouched: the
    loop over roots has to be a no-op for them.
    """
    single_root = [
        role
        for role, tree in unp.presentation_trees.items()
        if len(tree.root_element_ids) == 1
    ]
    assert len(single_root) > 50

    for role in single_root:
        tree = unp.presentation_trees[role]
        assert tree.root_element_ids == [tree.root_element_id]
