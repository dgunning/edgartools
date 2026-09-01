"""
FactsView convenience methods silently degraded what the query selected
(bead edgartools-r013).

Four independent root causes, one failure shape: selection succeeds, then the
projection or aggregation built on top of it loses fidelity, and nothing
surfaces the loss. Every one of these calls returned something plausible and
warned about nothing.

Covers gh #1242, #1243, #1223 and #1220.

Runs offline against the committed Tesla fixture; the ground-truth case uses a
hand-checked real filing.
"""

from pathlib import Path

import pandas as pd
import pytest

from edgar.exceptions import ValidationError
from edgar.xbrl import XBRL

# Anchored on __file__, not the working directory: a path resolved against cwd
# only works under a repo-root invocation and fails obscurely anywhere else.
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "tsla"


@pytest.fixture(scope='module')
def xbrl():
    assert FIXTURE.is_dir(), (
        f"committed fixture missing: {FIXTURE}. Its absence means a broken "
        f"checkout, which belongs in the failure report rather than in a skip."
    )
    return XBRL.from_directory(str(FIXTURE))


# ---------------------------------------------------------------------------
# gh #1242 - statement membership is a set, and was stored as a scalar
# ---------------------------------------------------------------------------

def test_statement_membership_records_every_role(xbrl):
    """
    The enrichment loop took the FIRST presentation role it happened to reach
    and wrote it as a single scalar, so a concept presented in several
    statements was tagged with only one of them.
    """
    facts = xbrl.facts.get_facts()

    multi = [f for f in facts if len(f.get('statement_types', [])) > 1]
    assert multi, "precondition: some concept is presented in more than one statement"

    # The scalar is still the primary statement, and is always the first of the
    # recorded memberships - consumers reading it keep their answer.
    for fact in facts:
        memberships = fact.get('statement_types')
        if memberships:
            assert fact['statement_type'] == memberships[0]
            assert len(memberships) == len(set(memberships)), "statement types are distinct"
            roles = fact.get('statement_roles', [])
            assert len(roles) == len(set(roles)), "statement roles are distinct"
            assert len(roles) >= len(memberships), \
                "one statement type can be presented through several roles"


def test_by_statement_type_finds_secondary_role_facts(xbrl):
    """
    gh #1242: get_statement_facts() returned zero rows for a concept that
    by_concept() retrieves without trouble, because the concept's membership in
    the requested statement was not the one that happened to be recorded.
    """
    facts = xbrl.facts.get_facts()

    # Find a concept whose membership in some statement is NOT its primary one.
    secondary = None
    for fact in facts:
        memberships = fact.get('statement_types', [])
        for statement_type in memberships[1:]:
            secondary = (fact['concept'], statement_type)
            break
        if secondary:
            break
    assert secondary, "precondition: some fact belongs to a non-primary statement"

    concept, statement_type = secondary
    rows = xbrl.facts.get_statement_facts(statement_type)
    assert not rows.empty
    assert (rows['concept'] == concept).any(), (
        f"{concept} is presented in {statement_type} but the statement query missed it"
    )


def test_by_statement_type_still_matches_the_primary_statement(xbrl):
    """Widening to membership must not lose what equality already matched."""
    for statement_type in ('IncomeStatement', 'BalanceSheet'):
        rows = xbrl.facts.get_statement_facts(statement_type)
        if rows.empty:
            continue
        for concept in rows['concept'].unique()[:20]:
            fact = next(f for f in xbrl.facts.get_facts() if f['concept'] == concept)
            assert statement_type in fact.get('statement_types', [fact.get('statement_type')])


def test_membership_stays_off_the_declared_frame_schema(xbrl):
    """
    The frame's column set is declared by the query's configuration, not by the
    rows (edgartools-rsyt). The membership lists are list-valued and exist for
    filtering, so they must not widen that contract.
    """
    df = xbrl.facts.query().to_dataframe()
    assert 'statement_types' not in df.columns
    assert 'statement_roles' not in df.columns
    assert 'statement_type' in df.columns


# ---------------------------------------------------------------------------
# gh #1243 - the projection discarded the columns the predicate selected on
# ---------------------------------------------------------------------------

def test_get_facts_with_dimensions_keeps_the_dimension_columns(xbrl):
    """
    gh #1243: the predicate matches rows BECAUSE they have dim_* keys, and then
    to_dataframe()'s projection dropped every dim_* column because
    include_dimensions was falsy. The caller got the right rows with the
    information that made them the right rows removed.
    """
    df = xbrl.facts.get_facts_with_dimensions()
    assert not df.empty, "precondition: the fixture has dimensionally-qualified facts"

    dim_cols = [c for c in df.columns if c.startswith('dim_')]
    assert dim_cols, "rows were selected for having dimensions, then had them stripped"

    # Every returned row actually carries a value in at least one dim_ column.
    assert df[dim_cols].notna().any(axis=1).all()


# ---------------------------------------------------------------------------
# gh #1223 - pivot_by_dimension fell through to the unpivoted frame
# ---------------------------------------------------------------------------

def _an_axis(xbrl) -> str:
    """
    An axis present in the fixture.

    Asserted rather than skipped: the fixture is committed and demonstrably
    dimensional, so "no axes" would mean the dimension columns stopped being
    projected - which is the #1243 defect itself. Skipping on it would retire
    the tests below exactly when they start mattering.
    """
    df = xbrl.facts.query().with_dimensions().to_dataframe()
    axes = sorted(c[4:] for c in df.columns if c.startswith('dim_'))
    assert axes, "the fixture projected no dim_ columns at all"
    return axes[0]


def test_pivot_by_dimension_accepts_every_axis_spelling(xbrl):
    """
    gh #1223: the lookup column was built with an f-string off the caller's raw
    spelling, but the projected column is always normalised. Passing the natural
    QName missed, and the method returned the plain unpivoted frame - of
    plausible shape, and not a pivot, with no warning.
    """
    underscore = _an_axis(xbrl)                        # dei_LegalEntityAxis
    qname = underscore.replace('_', ':', 1)            # dei:LegalEntityAxis
    local = underscore.split('_', 1)[-1]               # LegalEntityAxis

    pivots = [xbrl.facts.pivot_by_dimension(s) for s in (underscore, qname, local)]

    shapes = {p.shape for p in pivots}
    assert len(shapes) == 1, f"the same axis pivoted differently per spelling: {shapes}"

    # And the result is actually a pivot, not the passed-through frame. The
    # unpivoted frame is the full fact schema, which is far wider and carries
    # columns a pivot never has.
    for pivot in pivots:
        assert 'value' not in pivot.columns
        assert 'period_key' not in pivot.columns
        assert 'concept' in pivot.columns


def test_pivot_by_unknown_dimension_raises_instead_of_returning_a_frame(xbrl):
    """
    An axis nobody filed and an axis the caller misspelled both select zero
    rows; returning an empty frame for the second reads as "no data" rather
    than "no such axis".
    """
    with pytest.raises(ValidationError) as excinfo:
        xbrl.facts.pivot_by_dimension('us-gaap:NoSuchAxisExists')
    assert 'NoSuchAxisExists' in str(excinfo.value)
    # ValidationError IS-A ValueError, so an existing `except ValueError` still catches it.
    assert isinstance(excinfo.value, ValueError)


def test_pivot_keeps_colliding_rows_distinguishable(caplog):
    """
    pivot_table(aggfunc='first') resolves two facts landing in the same cell by
    keeping one and discarding the other. When they differ only by a column
    that is not in the index, the survivor also loses the field that identified
    it and reads as an unqualified number.
    """
    from edgar.xbrl.facts import FactsView

    # Two facts, same concept and label and period, different units - the shape
    # that collides. Driven through the helper directly so the case is exact.
    df = pd.DataFrame([
        {'concept': 'ifrs-full:AverageForeignExchangeRate', 'label': 'FX rate',
         'period_key': 'FY2024', 'unit_ref': 'COP', 'numeric_value': 4071.0},
        {'concept': 'ifrs-full:AverageForeignExchangeRate', 'label': 'FX rate',
         'period_key': 'FY2024', 'unit_ref': 'CRC', 'numeric_value': 518.0},
        {'concept': 'ifrs-full:AverageForeignExchangeRate', 'label': 'FX rate',
         'period_key': 'FY2024', 'unit_ref': 'PEN', 'numeric_value': 3.756},
    ])

    pivot = FactsView._pivot_without_losing_collisions(
        FactsView.__new__(FactsView), df, columns='period_key', what='period'
    )

    # All three survive, and each still says which currency it is.
    assert len(pivot) == 3
    assert 'unit_ref' in pivot.columns
    assert set(pivot['unit_ref']) == {'COP', 'CRC', 'PEN'}
    assert sorted(pivot['FY2024']) == [3.756, 518.0, 4071.0]


def test_an_unresolvable_collision_is_reported(caplog):
    """When the unit does not separate them either, say so rather than drop one."""
    from edgar.xbrl.facts import FactsView

    df = pd.DataFrame([
        {'concept': 'us-gaap:Assets', 'label': 'Assets', 'period_key': 'FY2024',
         'unit_ref': 'usd', 'numeric_value': 1.0},
        {'concept': 'us-gaap:Assets', 'label': 'Assets', 'period_key': 'FY2024',
         'unit_ref': 'usd', 'numeric_value': 2.0},
    ])

    with caplog.at_level('WARNING'):
        pivot = FactsView._pivot_without_losing_collisions(
            FactsView.__new__(FactsView), df, columns='period_key', what='period'
        )

    assert len(pivot) == 1, "genuinely indistinguishable rows still collapse"
    assert any('share a cell' in r.getMessage() for r in caplog.records), \
        "the collision was not reported"


# ---------------------------------------------------------------------------
# gh #1220 - unitless facts carried a numeric_value
# ---------------------------------------------------------------------------

def test_unitless_facts_have_no_numeric_value(xbrl):
    """
    gh #1220: float(value) ran on every fact unconditionally, so a unitless
    metadata item got a numeric_value. XBRL requires a unitRef on numeric items
    and forbids one on non-numeric items, which makes the unit the test.
    """
    facts = xbrl.facts.get_facts()

    unitless_with_number = [
        f for f in facts
        if not f.get('unit_ref') and f.get('numeric_value') is not None
        and not pd.isna(f.get('numeric_value'))
    ]
    assert unitless_with_number == [], (
        f"unitless facts still classified as numeric: "
        f"{[f['concept'] for f in unitless_with_number][:5]}"
    )

    # And the real numeric facts are untouched.
    numeric = [f for f in facts if f.get('unit_ref') and f.get('numeric_value') is not None]
    assert len(numeric) > 100, "precondition: the fixture has many genuine numeric facts"


def test_by_value_does_not_match_document_metadata(xbrl):
    """
    A numeric predicate returned document metadata as a match: querying for
    facts valued near 2023 returned the fiscal-year focus alongside real
    monetary facts. numeric_value is what consumers read as "this is a numeric
    fact", so every one of them inherited the misclassification.
    """
    hits = xbrl.facts.query().by_value(lambda v: 1990 <= v <= 2050).to_dataframe()

    if not hits.empty:
        offenders = [c for c in hits['concept'] if c.startswith('dei:')]
        assert offenders == [], f"by_value matched document metadata: {offenders}"

    # The specific reported fact: a gYear, unitless, must not be numeric.
    focus = xbrl.facts.query().by_concept('dei:DocumentFiscalYearFocus').to_dataframe()
    if not focus.empty:
        assert focus['numeric_value'].isna().all()
        assert focus['value'].notna().all(), "the filed value is still there"
