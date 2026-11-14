"""
Regression: a negated label signs the value on every statement, however it is reached.

Bead: edgartools-auvk1.13

The presentation sign (a negated preferredLabel on the arc) was applied only
when the statement's type was IncomeStatement, CashFlowStatement, BalanceSheet
or ComprehensiveIncome. A statement selected by its role URI that the resolver
does not classify is typed None, and a parenthetical is typed
...Parenthetical, so both kept the filed sign while the SEC page negates it.

Ground truth, from the SEC pages (R*.htm) of the filings in the offline
fixtures (tests/fixtures/statement-fidelity):

- DRDGOLD 20-F, 0001562762-22-000397, consolidated statement of profit or loss:
  cost of sales for the year to June 30, 2022 shows (3,742) in millions
  (the fact is 3,741,500,000), through income_statement() and by role.
- Berkshire Hathaway Energy 10-Q, 0001081316-24-000016, comprehensive income
  (parenthetical): the pension and postretirement OCI tax for Q2 2024 shows 1
  (the fact is -1,000,000, on a negatedTerseLabel arc).

Building the DataFrame of the DiamondRock 10-Q (0001298946-24-000052) balance
sheet parenthetical for one instant raised TypeError once the sign applied
there: an object-dtype sign column made an all-NaN object product.
"""
import pytest

from tests.xbrl.statement_fidelity_fixtures import fixture_viewer_and_xbrl

DRDGOLD_ROLE = 'http://www.DRDGold.com/role/CONSOLIDATEDSTATEMENTOFPROFITORLOSSANDOTHERCOMPREHENSIVEINCOME'
COST_OF_SALES = 'ifrs-full_CostOfSales'
PENSION_TAX = 'us-gaap_OtherComprehensiveIncomeLossPensionAndOtherPostretirementBenefitPlansTax'


def _value(frame, concept, column):
    return frame.loc[(frame['concept'] == concept) & ~frame['dimension'], column].tolist()[0]


@pytest.fixture(scope='module')
def drdgold():
    return fixture_viewer_and_xbrl('0001562762-22-000397')[1]


def test_statement_by_role_signs_like_the_typed_getter(drdgold):
    by_getter = drdgold.statements.income_statement()
    by_role = drdgold.statements[DRDGOLD_ROLE]
    assert by_getter.role_or_type == by_role.role_or_type == DRDGOLD_ROLE
    for statement in (by_getter, by_role):
        assert _value(statement.to_dataframe(), COST_OF_SALES, '2022-06-30 (FY)') == -3_741_500_000


def test_statement_by_role_renders_the_negated_sign(drdgold):
    rendered = drdgold.statements[DRDGOLD_ROLE].render()
    row = next(r for r in rendered.rows if r.metadata.get('concept') == COST_OF_SALES and not r.is_dimension)
    assert row.cells[0].value == 3_741_500_000  # the cell keeps the filed value
    assert row.cells[0].get_formatted_value().startswith('(')


def test_parenthetical_negated_label_is_applied():
    _, xbrl = fixture_viewer_and_xbrl('0001081316-24-000016')
    statement = xbrl.statements.comprehensive_income(parenthetical=True)
    frame = statement.to_dataframe()
    q2 = next(c for c in frame.columns if str(c).startswith('2024-06-30') and 'Q2' in str(c))
    assert _value(frame, PENSION_TAX, q2) == 1_000_000
    raw = statement.to_dataframe(presentation=False)
    assert _value(raw, PENSION_TAX, q2) == -1_000_000


def test_single_instant_of_a_parenthetical_balance_sheet_builds():
    viewer, xbrl = fixture_viewer_and_xbrl('0001298946-24-000052')
    role = next(s['role'] for s in xbrl.get_all_statements() if s['type'] == 'BalanceSheetParenthetical')
    frame = xbrl.statements[role].to_dataframe(period_filter='instant_2023-03-31')
    assert '2023-03-31' in frame.columns
