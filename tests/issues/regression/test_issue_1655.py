"""Regression: non-USD opening and closing cash balances displayed a "$" symbol.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1655

A cash-flow statement shows the opening and closing cash balance -- an instant
fact -- against a duration column. The renderer selected the right instant
value, then looked its currency up with the *duration* column key, found no
fact there, and fell through to the dollar default. Every EUR, DKK and GBP
filer's cash balances rendered as "$".

The selected cell now carries its own source fields (value, source instant,
unit_ref, decimals and preferred sign) out of the row's existing maps, and the
currency comes from ``xbrl.units[unit_ref]`` for that source instant. Nothing
searches the concept again, borrows another row's currency or guesses USD: a
missing unit shows the amount with an explicit "(unit unavailable)".

Ground truth (EUR/DKK/GBP millions, read from each filing's cash-flow R page):

- SAP 20-F FY2025, 0001104659-26-020058, R6: opening EUR 9,609, closing EUR 8,220
  (raw 9,609,000,000 / 8,220,000,000, decimals -6; opening from the 2024-12-31
  instant, closing from 2025-12-31).
- GSK 20-F FY2025, 0001131399-26-000004, R7: cash and bank overdrafts opening
  GBP 3,403, closing GBP 3,207 (CashAndCashEquivalentsIfDifferentFromStatementOfFinancialPosition).
- Novo Nordisk 20-F FY2025, 0000353278-26-000012, R5: opening DKK 15,655,
  closing DKK 26,464.
- Deutsche Bank 20-F FY2024, 0001159508-25-000020, R12: opening EUR 163,768,
  closing EUR 130,666.
"""

import pytest

from edgar.xbrl.rendering import render_statement

START = "http://www.xbrl.org/2003/role/periodStartLabel"
END = "http://www.xbrl.org/2003/role/periodEndLabel"
NEG_START = "http://www.xbrl.org/2009/role/negatedPeriodStartLabel"
CASH = "ifrs-full_CashAndCashEquivalents"
FY25 = "duration_2025-01-01_2025-12-31"
OPEN25 = "instant_2024-12-31"
CLOSE25 = "instant_2025-12-31"

UNITS = {
    "EUR": {"type": "simple", "measure": "iso4217:EUR"},
    "USD": {"type": "simple", "measure": "iso4217:USD"},
    "GBP": {"type": "simple", "measure": "iso4217:GBP"},
    "NZD": {"type": "simple", "measure": "iso4217:NZD"},
    "shares": {"type": "simple", "measure": "xbrli:shares"},
}


class _FakeXbrl:
    """Only what render_statement reads; a concept lookup returns a competing currency."""

    def __init__(self, competing="iso4217:USD"):
        self.units = UNITS
        self.competing = competing
        self.currency_lookups = []

    def get_currency_for_fact(self, element_name, period_key):
        self.currency_lookups.append((element_name, period_key))
        return self.competing


def _row(label, role, values, units=None, decimals=None, signs=None, concept=CASH, is_dimension=False):
    return {
        "concept": concept, "name": concept, "label": label, "level": 1,
        "is_abstract": False, "is_dimension": is_dimension, "has_values": True,
        "preferred_label": role, "values": values,
        "units": units if units is not None else {k: "EUR" for k in values},
        "decimals": decimals if decimals is not None else {k: -6 for k in values},
        "preferred_signs": signs or {},
        "period_types": {k: k.split("_")[0] for k in values},
    }


def _render(rows, xbrl=None, statement_type="CashFlowStatement", periods=((FY25, "FY 2025"),)):
    # A duration fact keeps the column from being dropped as empty
    filler = _row("Net change in cash", None, {FY25: -1_389_000_000}, concept="ifrs-full_IncreaseDecrease")
    data = [dict(r, statement_type=statement_type) for r in rows + [filler]]
    return render_statement(data, list(periods), "Cash flow", statement_type,
                            standard=False, show_comparisons=False,
                            xbrl_instance=xbrl or _FakeXbrl())


def _cells(rendered, label):
    row = next(r for r in rendered.rows if r.label == label)
    return row, [c.get_formatted_value() for c in row.cells]


# --- synthetic: each selection branch carries its own source fields ---------------

def test_prior_day_and_period_end_branches_use_their_own_unit():
    xbrl = _FakeXbrl(competing="iso4217:USD")
    rendered = _render([
        _row("Cash at beginning", START, {OPEN25: 9_609_000_000}),
        _row("Cash at end", END, {CLOSE25: 8_220_000_000}),
    ], xbrl)
    opening, text = _cells(rendered, "Cash at beginning")
    assert text == ["€9,609"]
    closing, text = _cells(rendered, "Cash at end")
    assert text == ["€8,220"]
    assert opening.metadata["selected_cells"][FY25] == {
        "value": 9_609_000_000, "source_period_key": OPEN25, "unit_ref": "EUR",
        "decimals": -6, "preferred_sign": None}
    assert closing.metadata["selected_cells"][FY25]["source_period_key"] == CLOSE25
    # The visible column keeps its identity
    assert rendered.header.period_keys == [FY25]
    # No broader concept/date search for the selected balance cells
    assert [name for name, _ in xbrl.currency_lookups if name == CASH] == []


def test_start_date_fallback_only_when_prior_day_key_is_absent():
    rendered = _render([_row("Cash at beginning", START, {"instant_2025-01-01": 5_000_000},
                             units={"instant_2025-01-01": "GBP"}, decimals={"instant_2025-01-01": -3})])
    row, text = _cells(rendered, "Cash at beginning")
    # Filed to thousands (decimals -3) and shown in millions: two places
    assert text == ["£5.00"]
    selected = row.metadata["selected_cells"][FY25]
    assert selected["source_period_key"] == "instant_2025-01-01"
    assert selected["unit_ref"] == "GBP"
    assert selected["decimals"] == -3


def test_present_valueless_prior_day_entry_is_terminal():
    rendered = _render([_row("Cash at beginning", START,
                             {OPEN25: "", "instant_2025-01-01": 7_000_000_000})])
    row, text = _cells(rendered, "Cash at beginning")
    assert text == [""]
    assert row.cells[0].value == ""
    assert row.metadata["selected_cells"][FY25]["source_period_key"] == OPEN25


def test_direct_entry_takes_precedence():
    """A value filed under the column's own key is shown as before, not replaced by an instant."""
    xbrl = _FakeXbrl(competing="iso4217:EUR")
    rendered = _render([_row("Cash at end", END, {FY25: 1_000_000_000, CLOSE25: 2_000_000_000})], xbrl)
    row, text = _cells(rendered, "Cash at end")
    assert text == ["€1,000"]
    assert row.cells[0].value == 1_000_000_000
    assert "selected_cells" not in row.metadata


def test_present_valueless_direct_entry_is_terminal():
    rendered = _render([_row("Cash at end", END, {FY25: "", CLOSE25: 2_000_000_000})])
    row, text = _cells(rendered, "Cash at end")
    assert text == [""]
    assert row.metadata["selected_cells"][FY25]["source_period_key"] == FY25


def test_row_owned_unit_wins_over_competing_currency_for_same_concept_and_date():
    """Another fact of the same concept/date is in USD; the row's own EUR fact wins."""
    xbrl = _FakeXbrl(competing="iso4217:USD")
    rendered = _render([
        _row("Cash at end", END, {CLOSE25: 8_220_000_000}, units={CLOSE25: "EUR"}),
        _row("Cash at end (USD)", END, {CLOSE25: 9_000_000_000}, units={CLOSE25: "USD"}),
    ], xbrl)
    assert _cells(rendered, "Cash at end")[1] == ["€8,220"]
    assert _cells(rendered, "Cash at end (USD)")[1] == ["$9,000"]


def test_zero_stays_selected_and_blank():
    rendered = _render([_row("Cash at end", END, {CLOSE25: 0, "instant_2025-06-30": 5})])
    row, text = _cells(rendered, "Cash at end")
    assert text == [""]
    assert row.cells[0].value == 0
    assert row.metadata["selected_cells"][FY25]["value"] == 0
    assert "\x14" not in rendered.to_markdown()


@pytest.mark.parametrize("units", [{}, {CLOSE25: None}, {CLOSE25: "not-a-unit"}])
def test_missing_or_invalid_unit_never_shows_a_dollar(units):
    rendered = _render([_row("Cash at end", END, {CLOSE25: 8_220_000_000}, units=units)])
    text = _cells(rendered, "Cash at end")[1]
    assert text == ["8,220 (unit unavailable)"]


def test_unmapped_iso_currency_shows_its_code():
    rendered = _render([_row("Cash at end", END, {CLOSE25: 8_220_000_000}, units={CLOSE25: "NZD"})])
    assert _cells(rendered, "Cash at end")[1] == ["NZD 8,220"]


def test_negated_period_start_sign_applied_once():
    rows = [_row("Cash at beginning", NEG_START, {OPEN25: 9_609_000_000}, signs={OPEN25: -1})]
    rendered = _render(rows)
    assert _cells(rendered, "Cash at beginning")[1] == ["€(9,609)"]
    assert rendered.rows[0].cells[0].value == 9_609_000_000  # raw value unchanged
    df = rendered.to_dataframe(presentation=True)
    assert df.loc[df.label == "Cash at beginning", "2025-12-31"].iloc[0] == -9_609_000_000
    df_raw = rendered.to_dataframe(presentation=False)
    assert df_raw.loc[df_raw.label == "Cash at beginning", "2025-12-31"].iloc[0] == 9_609_000_000


def test_differing_source_accuracy_comes_from_the_source_instant():
    """decimals is filed under the instant key; the duration column has none."""
    rendered = _render([
        _row("Cash at end", END, {CLOSE25: 8_225_000_000}, decimals={CLOSE25: -5}),
    ])
    assert _cells(rendered, "Cash at end")[1] == ["€8,225.0"]


def test_ordinary_usd_rows_unchanged():
    xbrl = _FakeXbrl(competing="iso4217:USD")
    rendered = _render([_row("Net cash from operating activities", None, {FY25: 1_234_000_000},
                             units={FY25: "USD"})], xbrl)
    row, text = _cells(rendered, "Net cash from operating activities")
    assert text == ["$1,234"]
    assert "selected_cells" not in row.metadata
    assert xbrl.currency_lookups  # ordinary cells keep their existing lookup


def test_dimensioned_rows_do_not_use_period_boundary_mapping():
    rendered = _render([_row("Segment cash", START, {OPEN25: 9_609_000_000}, is_dimension=True)])
    row = rendered.rows[0]
    assert "selected_cells" not in row.metadata
    assert row.cells[0].value == ""


def test_equity_roll_forward_branch_unchanged():
    """The StatementOfEquity first-occurrence branch keeps its existing behaviour."""
    xbrl = _FakeXbrl(competing="iso4217:EUR")
    concept = "us-gaap_StockholdersEquity"
    rendered = _render([
        _row("Equity", None, {OPEN25: 100_000_000, CLOSE25: 120_000_000}, concept=concept),
        _row("Net income", None, {FY25: 20_000_000}, concept="us-gaap_NetIncomeLoss"),
        _row("Equity", None, {OPEN25: 100_000_000, CLOSE25: 120_000_000}, concept=concept),
    ], xbrl, statement_type="StatementOfEquity")
    values = [r.cells[0].value for r in rendered.rows]
    assert values[:3] == [100_000_000, 20_000_000, 120_000_000]
    assert all("selected_cells" not in r.metadata for r in rendered.rows)


# --- real filings ------------------------------------------------------------------

def _cash_rows(accession, concept):
    from edgar import find
    rendered = find(accession).xbrl().statements.cash_flow_statement().render()
    rows = [r for r in rendered.rows
            if r.metadata.get("concept") == concept and not r.is_dimension
            and isinstance(r.cells[0].value, (int, float))]
    assert len(rows) == 2, [r.label for r in rows]
    return rendered, rows[0], rows[1]


@pytest.mark.network
@pytest.mark.vcr
def test_sap_fy2025_cash_balances_render_in_euros():
    """SAP 20-F FY2025, 0001104659-26-020058, R6."""
    rendered, opening, closing = _cash_rows("0001104659-26-020058", CASH)
    assert opening.cells[0].get_formatted_value() == "€9,609"
    assert closing.cells[0].get_formatted_value() == "€8,220"
    assert opening.cells[0].value == 9_609_000_000
    assert closing.cells[0].value == 8_220_000_000
    column = rendered.header.period_keys[0]
    assert column == FY25
    assert opening.metadata["selected_cells"][column] == {
        "value": 9_609_000_000, "source_period_key": OPEN25,
        "unit_ref": opening.metadata["units"][OPEN25], "decimals": -6, "preferred_sign": 1}
    assert closing.metadata["selected_cells"][column]["source_period_key"] == CLOSE25
    assert closing.metadata["selected_cells"][column]["decimals"] == -6
    assert not any("$" in c.get_formatted_value() for c in opening.cells + closing.cells)


@pytest.mark.network
@pytest.mark.vcr
def test_gsk_fy2025_cash_and_overdrafts_render_in_pounds():
    """GSK 20-F FY2025, 0001131399-26-000004, R7 -- keeps its cash-and-overdrafts concept."""
    _, opening, closing = _cash_rows(
        "0001131399-26-000004",
        "ifrs-full_CashAndCashEquivalentsIfDifferentFromStatementOfFinancialPosition")
    assert opening.cells[0].get_formatted_value() == "£3,403"
    assert closing.cells[0].get_formatted_value() == "£3,207"
    assert opening.cells[0].value == 3_403_000_000
    assert closing.cells[0].value == 3_207_000_000


@pytest.mark.network
@pytest.mark.vcr
def test_novo_nordisk_fy2025_cash_balances_render_in_kroner():
    """Novo Nordisk 20-F FY2025, 0000353278-26-000012, R5."""
    _, opening, closing = _cash_rows("0000353278-26-000012", CASH)
    assert opening.cells[0].get_formatted_value() == "kr15,655"
    assert closing.cells[0].get_formatted_value() == "kr26,464"


@pytest.mark.network
@pytest.mark.vcr
def test_deutsche_bank_fy2024_cash_balances_render_in_euros():
    """Deutsche Bank 20-F FY2024, 0001159508-25-000020, R12."""
    _, opening, closing = _cash_rows("0001159508-25-000020", CASH)
    assert opening.cells[0].get_formatted_value() == "€163,768"
    assert closing.cells[0].get_formatted_value() == "€130,666"
