"""
Regression tests for edgartools-vaau.3: `Statements.__getitem__` typed a role by
looking for a canonical statement name INSIDE the role's spelling.

Found while fixing vaau.1/.2 (PR #1300); not caused by them.

For any string that was not a known statement type, `__getitem__` walked
`statement_to_concepts` and took the first canonical type whose name occurred as a
substring of the input. A role called
`.../CONSOLIDATEDBALANCESHEETSParenthetical` therefore came back typed
`BalanceSheet`, as did 71 disclosure roles with names like
`...ReflectedInTheConsolidatedBalanceSheets`. Measured over tests/fixtures/xbrl:
the sniff disagreed with the resolver's own classification on 165 of 2,658 roles.

TWO CONSEQUENCES, and the second is the serious one:

1. `canonical_type` is what the presentation-sign gate keys on, and `BalanceSheet`
   is in `PRESENTATION_SIGN_STATEMENTS` -- so a note table could have its rows
   sign-flipped purely because its role name mentions a statement.

2. `canonical_type` ALSO decides which role `render()` renders
   (`rendering_type = self.canonical_type if self.canonical_type else
   self.role_or_type`). Typing a role from its own name therefore turned
   "render this role" into "render the canonical statement of this kind":
   asking for Apple's `...CONSOLIDATEDBALANCESHEETSParenthetical` by its exact
   role URI returned the primary balance sheet -- 38 rows of assets and
   liabilities -- and the parenthetical's own share counts and par values were
   unreachable.

THE FIX: a known role is never sniffed. The resolver has already classified every
role, and `Statement.classified_type` (added by #1300) reads that classification
back without selecting a role. The substring test survives only for a bare
statement name that is not a role, where the name is all there is to go on.

MEASURED over the fixture corpus, 2,658 roles: 2,492 render identically and 166
change. 94 roles stop being sign-gated -- 72 the resolver calls `Disclosures`, 18
`BalanceSheetParenthetical`, 4 unclassified -- and NOT ONE of them is a primary
statement. One role starts being sign-gated: an income statement the sniff had
mistyped `ComprehensiveIncome` from its own name. No primary statement loses its
signs, so the 1,060 rows corrected by #1300 stay corrected.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

FIXTURE = Path('tests/fixtures/xbrl/aapl/10k_2023')

PRIMARY_ROLE = 'http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS'
PARENTHETICAL_ROLE = 'http://www.apple.com/role/CONSOLIDATEDBALANCESHEETSParenthetical'

# From rendering.py; a statement typed as one of these has the presentation sign
# applied to its values.
SIGN_GATED = ('IncomeStatement', 'CashFlowStatement', 'BalanceSheet')


@pytest.fixture(scope='module')
def xbrl():
    return XBRL.from_directory(FIXTURE)


def test_a_parenthetical_role_renders_its_own_content(xbrl):
    """The heart of it: selecting a role by its URI must return THAT role.

    This used to return the primary balance sheet, whose rows are assets and
    liabilities, so the parenthetical's share counts had no accessor at all.
    """
    statement = xbrl.statements[PARENTHETICAL_ROLE]
    labels = [row.label for row in statement.render().rows]

    assert any('par value' in label.lower() for label in labels), \
        f"parenthetical returned another statement's rows: {labels[:4]}"
    assert any('shares authorized' in label.lower() for label in labels)
    assert not any(label.lower().startswith('cash and cash equivalents')
                   for label in labels), "this is the primary balance sheet's content"


def test_a_parenthetical_is_not_typed_as_the_statement_it_annotates(xbrl):
    statement = xbrl.statements[PARENTHETICAL_ROLE]
    assert statement.canonical_type is None
    assert statement.classified_type not in SIGN_GATED, \
        "a parenthetical must not pass the presentation-sign gate"


def test_the_primary_statement_is_unaffected(xbrl):
    """The role the parenthetical annotates keeps its content and its signs."""
    statement = xbrl.statements[PRIMARY_ROLE]
    labels = [row.label for row in statement.render().rows]

    assert any(label.lower().startswith('cash and cash equivalents') for label in labels)
    assert statement.classified_type == 'BalanceSheet', \
        "the primary balance sheet must still be sign-gated (#1300's rows stay corrected)"


def test_the_two_roles_no_longer_render_the_same_table(xbrl):
    primary = [row.label for row in xbrl.statements[PRIMARY_ROLE].render().rows]
    parenthetical = [row.label for row in xbrl.statements[PARENTHETICAL_ROLE].render().rows]
    assert primary != parenthetical


def test_a_bare_statement_name_still_resolves_by_name(xbrl):
    """The substring path is kept for a genuine statement name, which is the only
    thing it was ever meant to serve."""
    statement = xbrl.statements['BalanceSheet']
    assert statement.canonical_type == 'BalanceSheet'
    labels = [row.label for row in statement.render().rows]
    assert any(label.lower().startswith('cash and cash equivalents') for label in labels)


def test_no_role_is_typed_as_a_statement_the_resolver_disagrees_with(xbrl):
    """The general invariant, over every role in this filing.

    A role may legitimately resolve to no canonical type; what it may not do is
    claim a canonical type that contradicts the resolver.
    """
    mismatches = []
    for entry in xbrl.statements.statements:
        role = entry['role']
        classified = xbrl.statements[role].classified_type
        if classified is not None and classified != entry.get('type'):
            mismatches.append((role, entry.get('type'), classified))
    assert mismatches == []


def test_only_resolver_classified_statements_are_sign_gated(xbrl):
    """Nothing the resolver calls a disclosure or a parenthetical may reach the
    presentation-sign gate."""
    offenders = [
        (entry['role'], entry.get('type'))
        for entry in xbrl.statements.statements
        if xbrl.statements[entry['role']].classified_type in SIGN_GATED
        and entry.get('type') not in SIGN_GATED
    ]
    assert offenders == []
