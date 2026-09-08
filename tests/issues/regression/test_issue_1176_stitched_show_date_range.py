"""Regression test for issue #1176.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1176

`StitchedStatements.income_statement(show_date_range=True)` stored the option on
the returned statement, but `StitchedStatement.render()` declared its own
`show_date_range: bool = False` parameter and never consulted the stored value.
`__rich__()` calls `render()` with no arguments, so ordinary Rich and `repr`
rendering showed "Dec 31, 2024" while an explicit
`statement.render(show_date_range=True)` showed "Jan 1, 2024 - Dec 31, 2024".

The parameter now defaults to `None` and falls back to the stored attribute, so
an explicit argument still wins in both directions.
"""

import pytest

from edgar.xbrl.statements import StitchedStatements

PERIOD = "duration_2024-01-01_2024-12-31"


class OfflineXBRLS:
    """The minimal stitched-statement source from the report."""

    entity_info = {"fiscal_period": "FY", "fiscal_year": 2024}

    def get_statement(self, *args, **kwargs):
        return {
            "periods": [(PERIOD, "Dec 31, 2024")],
            "statement_data": [{
                "label": "Revenue",
                "level": 0,
                "is_abstract": False,
                "is_total": False,
                "concept": "us-gaap_Revenue",
                "has_values": True,
                "values": {PERIOD: 100},
                "decimals": {PERIOD: 0},
            }],
        }


def _columns(rendered):
    return list(rendered.header.columns)


@pytest.fixture
def statements():
    return StitchedStatements(OfflineXBRLS())


def test_accessor_option_reaches_normal_rendering(statements):
    statement = statements.income_statement(show_date_range=True)

    assert statement.show_date_range is True
    assert _columns(statement.__rich__()) == ["Jan 1, 2024 - Dec 31, 2024"]
    assert "Jan 1, 2024" in repr(statement)


def test_explicit_argument_still_wins_in_both_directions(statements):
    on = statements.income_statement(show_date_range=True)
    off = statements.income_statement()

    assert _columns(on.render(show_date_range=False)) == ["Dec 31, 2024"]
    assert _columns(off.render(show_date_range=True)) == ["Jan 1, 2024 - Dec 31, 2024"]


def test_default_rendering_is_unchanged(statements):
    statement = statements.income_statement()

    assert statement.show_date_range is False
    assert _columns(statement.__rich__()) == ["Dec 31, 2024"]
