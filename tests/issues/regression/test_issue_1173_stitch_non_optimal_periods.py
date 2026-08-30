"""Regression test for issue #1173.

`XBRLS.get_statement(use_optimal_periods=False)` appended the three-item tuple
returned by `XBRL.find_statement()` to the list of statements handed to
`StatementStitcher`, which then called `.get()` on it.  The non-optimal path
raised `AttributeError: 'tuple' object has no attribute 'get'` and could never
return a statement.
"""

from edgar.xbrl import XBRLS

PERIOD = "duration_2024-01-01_2024-12-31"

STATEMENT = {
    "role": "role://income",
    "definition": "Income statement",
    "statement_type": "IncomeStatement",
    "periods": {PERIOD: {"label": "2024"}},
    "data": [
        {
            "concept": "us-gaap_Revenues",
            "label": "Revenues",
            "values": {PERIOD: 350018000000},
            "decimals": {PERIOD: -6},
        }
    ],
}


class StubXBRL:
    """The two calls stitch_statements() makes on an XBRL object."""

    entity_info = {
        "fiscal_period": "FY",
        "fiscal_year": 2024,
        "document_period_end_date": "2024-12-31",
    }
    reporting_periods = [
        {
            "key": PERIOD,
            "label": "Year Ended December 31, 2024",
            "type": "duration",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "duration_days": 365,
        }
    ]

    def find_statement(self, statement_type, is_parenthetical=False):
        # The real signature: (matching statements, role, actual type).
        return ([STATEMENT], STATEMENT["role"], statement_type)

    def get_statement_by_type(self, statement_type, include_dimensions=False):
        return STATEMENT


def test_non_optimal_path_returns_a_stitched_statement():
    xbrls = XBRLS.from_xbrl_objects([StubXBRL()])

    result = xbrls.get_statement(
        "IncomeStatement", max_periods=1, use_optimal_periods=False
    )

    assert isinstance(result, dict)
    assert result["periods"] == [(PERIOD, "2024")]
    assert result["statement_data"][0]["values"][PERIOD] == 350018000000


def test_non_optimal_path_agrees_with_the_optimal_path():
    xbrls = XBRLS.from_xbrl_objects([StubXBRL()])

    optimal = xbrls.get_statement("IncomeStatement", max_periods=1)
    non_optimal = xbrls.get_statement(
        "IncomeStatement", max_periods=1, use_optimal_periods=False
    )

    assert [row["values"] for row in non_optimal["statement_data"]] == [
        row["values"] for row in optimal["statement_data"]
    ]
