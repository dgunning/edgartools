"""
Regression tests for edgartools-vaau: the presentation-sign gate keys on a
statement's type, and two callers fed it a type it could not recognise, so a
correctly hydrated `preferred_sign` of -1 was silently skipped.

`apply_presentation_sign()` is already a single function (edgartools-5ztr) and
already correct. Both defects are about what reaches its `statement_type`
argument:

GH #1285 -- selecting a statement by its ROLE URI. `Statements.__getitem__`
infers `canonical_type` by testing whether a canonical type's literal spelling
appears inside the string, which is not a property of a role URI: no issuer
writes "CashFlowStatement" into
`http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFCASHFLOWS`. So the statement
came back with `canonical_type=None`, `_apply_presentation` compared the full
URI against the three gate types, and the SAME statement exported opposite
signs depending on which accessor produced it.

GH #1289 -- `render(standard=False)`. `statement_type` was stamped onto the row
dicts only on the standardization path, so the cell formatter received rows
with no type and passed None into the gate. The `RenderedStatement`'s own
`statement_type` was correct throughout, which is why its `to_dataframe()` was
right while its formatted cells were wrong.

WHY `classified_type` IS A SEPARATE FIELD, and not just a better
`canonical_type`. The first attempt resolved the role's real type and assigned
it to `canonical_type`. That is wrong, and the corpus caught it:
`Statement.render()` uses `canonical_type or role_or_type` to decide WHICH ROLE
to render, so populating it turns "render this role" into "render the canonical
statement of this kind" -- a different role. On Boeing that silently dropped a
filed FY2020 asset impairment charge of $24,000,000 from the cash flow
statement. Classification ("what kind of statement is this") and selection
("which statement did you ask for") are different questions, so they get
different fields.

MEASURED over the fixture corpus: 1,060 rows across 35 statements change sign,
confined to the three types the gate covers (CashFlowStatement 952/23,
IncomeStatement 102/9, BalanceSheet 6/3). Zero rows change magnitude, and no
row or column appears or disappears -- except that 1,032 previously
empty-string cells in 11 statements become NaN, because the gate also converts
its columns to numeric, which is what the by-name accessor already did.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

AAPL = Path("tests/fixtures/xbrl/aapl/10k_2023")
CAPEX = "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"
OPERATING = "us-gaap_NetCashProvidedByUsedInOperatingActivities"
FILED_CAPEX = [10959000000.0, 10708000000.0, 11085000000.0]
OPTS = dict(standard=False, view="detailed")


@pytest.fixture(scope="module")
def xbrl():
    return XBRL.from_directory(AAPL)


@pytest.fixture(scope="module")
def accessors(xbrl):
    """The same cash flow statement, reached two ways."""
    by_name = xbrl.statements["CashFlowStatement"]
    by_role = xbrl.statements[by_name.role_or_type]
    assert by_name.role_or_type == by_role.role_or_type
    return by_name, by_role


def period_columns(frame):
    return [c for c in frame.columns if str(c)[:4].isdigit()]


def row(frame, concept):
    columns = period_columns(frame)
    return frame.loc[frame["concept"] == concept, columns].values.tolist()[0]


# --------------------------------------------------------------------------
# GH #1285 -- the role-URI accessor
# --------------------------------------------------------------------------

def test_both_accessors_select_the_same_statement(accessors):
    """Precondition: this is one statement, not two similar ones."""
    by_name, by_role = accessors
    assert by_name.to_dataframe(presentation=False, **OPTS).equals(
        by_role.to_dataframe(presentation=False, **OPTS))
    assert row(by_name.to_dataframe(presentation=False, **OPTS), CAPEX) == FILED_CAPEX


def test_role_uri_accessor_applies_the_presentation_sign(accessors):
    by_name, by_role = accessors
    presented = by_role.to_dataframe(presentation=True, **OPTS)
    assert row(presented, CAPEX) == [-v for v in FILED_CAPEX]
    # And it is no longer indistinguishable from the raw frame.
    assert not by_role.to_dataframe(presentation=False, **OPTS).equals(presented)


def test_the_two_accessors_agree(accessors):
    """The defect was that the answer depended on the accessor string."""
    by_name, by_role = accessors
    assert by_name.to_dataframe(presentation=True, **OPTS).equals(
        by_role.to_dataframe(presentation=True, **OPTS))


def test_role_uri_accessor_still_renders_the_role_it_was_given(xbrl, accessors):
    """Guards the regression the first attempt at this fix introduced.

    Resolving the type into `canonical_type` would make render() pick a role by
    KIND rather than the one asked for. Selecting by role must stay exact.
    """
    by_name, by_role = accessors
    assert by_role.canonical_type is None, \
        "canonical_type also selects which role renders; it must stay unset here"
    assert by_role.classified_type == "CashFlowStatement"
    # Same role in, same rows out.
    assert [r.metadata.get("concept") for r in by_role.render(standard=False).rows] == \
           [r.metadata.get("concept") for r in by_name.render(standard=False).rows]


def test_positive_signs_are_untouched(accessors):
    """A preferred_sign of 1 must not be flipped by any accessor."""
    by_name, by_role = accessors
    for statement in (by_name, by_role):
        presented = statement.to_dataframe(presentation=True, **OPTS)
        raw = statement.to_dataframe(presentation=False, **OPTS)
        assert row(presented, OPERATING) == row(raw, OPERATING)


# --------------------------------------------------------------------------
# GH #1289 -- render(standard=False)
# --------------------------------------------------------------------------

def cash_flow_row(rendered):
    return next(r for r in rendered.rows
                if r.metadata.get("concept") == CAPEX and not r.is_dimension)


def test_render_standard_false_formats_the_negative_sign(accessors):
    by_name, _ = accessors
    rendered = by_name.render(standard=False)
    line = cash_flow_row(rendered)

    assert set(line.metadata["preferred_signs"].values()) == {-1}
    # cell.value stays as filed; only the display applies the sign.
    assert [c.value for c in line.cells] == FILED_CAPEX
    assert [c.get_formatted_value() for c in line.cells] == \
        ["$(10,959)", "$(10,708)", "$(11,085)"]


def test_render_agrees_with_itself_across_the_standard_flag(accessors):
    """`standard` selects labels; it is not a request for filed signs."""
    by_name, _ = accessors
    displays = []
    for standard in (False, True, False):
        rendered = by_name.render(standard=standard)
        assert rendered.statement_type == "CashFlowStatement"
        displays.append([c.get_formatted_value() for c in cash_flow_row(rendered).cells])
    assert displays[0] == displays[1] == displays[2]


def test_rendered_cells_agree_with_the_rendered_dataframe(accessors):
    """The two halves of one RenderedStatement disagreed; they must not."""
    by_name, _ = accessors
    for standard in (False, True):
        rendered = by_name.render(standard=standard)
        frame = rendered.to_dataframe(presentation=True)
        dates = [p.end_date for p in rendered.periods]
        assert frame.loc[frame["concept"] == CAPEX, dates].values.tolist()[0] == \
            [-v for v in FILED_CAPEX]
        assert all("(" in c.get_formatted_value()
                   for c in cash_flow_row(rendered).cells)


def test_every_negated_row_displays_negative_without_standardization(accessors):
    """Pin the mechanism across the whole statement, not one line.

    Every row the linkbase marks negated must display negative under
    standard=False, exactly as under standard=True.
    """
    by_name, _ = accessors
    for standard in (False, True):
        rendered = by_name.render(standard=standard)
        checked = 0
        for line in rendered.rows:
            signs = line.metadata.get("preferred_signs") or {}
            if not any(s == -1 for s in signs.values()):
                continue
            for cell in line.cells:
                if isinstance(cell.value, (int, float)) and cell.value > 0:
                    assert "(" in cell.get_formatted_value(), (
                        f"{line.metadata.get('concept')} displayed "
                        f"{cell.get_formatted_value()} with standard={standard}")
                    checked += 1
        assert checked > 0, "no negated rows found; the test would prove nothing"


def test_selecting_by_role_uri_does_not_change_which_rows_render():
    """Boeing pins the regression the first attempt at this fix introduced.

    Resolving the role's type into `canonical_type` made render() choose a role
    by kind, and this filed FY2020 asset impairment charge vanished from the
    frame. The value must survive selection by role URI.
    """
    xbrl = XBRL.from_directory("tests/fixtures/xbrl/special_cases/custom_taxonomy/ba")
    role = "http://www.boeing.com/role/ConsolidatedStatementsofCashFlows"
    statement = xbrl.statements[role]
    assert statement.classified_type == "CashFlowStatement"

    frame = statement.to_dataframe(presentation=True, **OPTS)
    columns = period_columns(frame)
    assert "2020-12-31 (FY)" in columns

    impairments = frame.loc[frame["concept"] == "us-gaap_AssetImpairmentCharges",
                            "2020-12-31 (FY)"].tolist()
    assert 24000000.0 in impairments
