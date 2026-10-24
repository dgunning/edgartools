"""Regression test for GH #1648: income_statement() picked a co-registrant's statement.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1648

Williams' 10-Q carries face statements for two co-registrants, Transco and
Northwest Pipeline, beside Williams' own. The resolver scores candidate roles by
name, and Williams' "Consolidated Statement of Comprehensive Income" took the
100-point comprehensive-income penalty that Transco's "Statement of Net Income"
did not, so income_statement() returned Transco's role. Since GH #1468 a
co-registrant's role reads that co-registrant's facts, so get_revenue() and
get_net_income() answered with Transco's figures. A co-registrant's own face
statement is now ranked below the parent's.

Ground truth: Williams 10-Q for 2026-06-30 (0000107263-26-000026), R2
(Consolidated Statement of Comprehensive Income - Williams): total revenues
3,053 million, operating income 1,182 million, net income attributable to
Williams 827 million (Q2 2025: 546 million). Transco's role (R9) shows revenues
804 million and net income 367 million.
"""
from pathlib import Path

import pytest

from edgar import find
from edgar.xbrl import XBRL
from edgar.xbrl.statement_resolver import StatementResolver

AAL_10Q = Path("tests/fixtures/xbrl/aal/10q_2026q2")
AAL_GROUP_ROLE = "http://www.aa.com/role/CondensedConsolidatedBalanceSheetsAmericanAirlinesGroupInc"
AAL_SUBSIDIARY_ROLE = "http://www.aa.com/role/CondensedConsolidatedBalanceSheetsAmericanAirlinesInc"


@pytest.mark.fast
def test_coregistrant_role_ranks_below_the_parent_role():
    xbrl = XBRL.from_directory(AAL_10Q)
    assert xbrl._coregistrant_member(AAL_SUBSIDIARY_ROLE) == "aal_AmericanAirlinesIncMember"
    statements = {s["role"]: s for s in xbrl.get_all_statements()}
    resolver = StatementResolver(xbrl)
    group = resolver._score_statement_quality(statements[AAL_GROUP_ROLE], "BalanceSheet")
    subsidiary = resolver._score_statement_quality(statements[AAL_SUBSIDIARY_ROLE], "BalanceSheet")
    assert group - subsidiary >= 200
    assert xbrl.find_statement("BalanceSheet")[1] == AAL_GROUP_ROLE


@pytest.mark.network
def test_williams_income_statement_is_williams():
    financials = find("0000107263-26-000026").obj().financials
    role = financials.income_statement().role_or_type
    assert role == "http://co.williams.com/role/ConsolidatedStatementofComprehensiveIncomeUnauditedWilliams"
    assert financials.get_revenue() == 3_053_000_000           # was Transco's 804,000,000
    assert financials.get_operating_income() == 1_182_000_000  # was 421,000,000
    assert financials.get_net_income() == 827_000_000          # was 367,000,000
    assert financials.get_net_income(1) == 546_000_000
