"""Statement discovery must preserve a selected role and its processing rules.

GitHub PR: https://github.com/dgunning/edgartools/pull/1305

AAL FY2025 10-K 0000006201-26-000014 and Q2 2026 10-Q
0000006201-26-000052 each contain parent and subsidiary balance-sheet roles.
The subsidiary files OtherReceivablesNetCurrent of USD 9.896B / 8.187B
and USD 10.203B / 9.896B, respectively. The parent has no such line.
Integer/get/search/all/iteration selected the subsidiary, then populated
canonical_type and silently retrieved the parent. Clearing canonical_type
alone made DataFrames use duration periods and removed the prior-year balance.

AMZN Q2 2026 10-Q 0001018724-26-000026 independently files Assets of
USD 1,095.689B / 818.042B. Its role-URI DataFrame dropped the prior-year instant.
The AAL subsidiary Assets checks use its AmericanAirlinesInc member row; the
separate contamination of its plain totals is outside these assertions.

The fixture manifests identify the original unedited SEC XBRL files. Apple's
FY2023 10-K 0000320193-23-000106 supplies parenthetical shares/par-value,
signs, equity and analysis controls. Parenthetical selection must retain its
own role and instant comparison, without primary-statement sign processing.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.exceptions import StatementNotFoundError
from edgar.xbrl import XBRL
from edgar.xbrl.period_selector import select_periods
from edgar.xbrl.presentation import StatementView
from edgar.xbrl.statement_resolver import StatementResolver, statement_registry
from edgar.xbrl.statements import Statement, Statements

pytestmark = [pytest.mark.fast, pytest.mark.regression]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"
RECEIVABLES = "us-gaap_OtherReceivablesNetCurrent"
HELPERS = ("integer", "get", "search", "all", "iteration")
APPLE_PARENTHETICAL = "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETSParenthetical"
NAMED_ACCESSORS = (
    ("balance_sheet", "BalanceSheet"),
    ("income_statement", "IncomeStatement"),
    ("cash_flow_statement", "CashFlowStatement"),
    ("statement_of_equity", "StatementOfEquity"),
    ("comprehensive_income", "ComprehensiveIncome"),
    ("schedule_of_investments", "ScheduleOfInvestments"),
)
FILINGS = (
    {
        "folder": "10k_2025",
        "prefix": "aal-20251231",
        "role": "http://www.aa.com/role/ConsolidatedBalanceSheetsAmericanAirlinesInc",
        "periods": ("2025-12-31", "2024-12-31"),
        "receivables": (9_896_000_000, 8_187_000_000),
        "parent_assets": (61_774_000_000, 61_783_000_000),
        "subsidiary_assets": (70_247_000_000, 68_755_000_000),
    },
    {
        "folder": "10q_2026q2",
        "prefix": "aal-20260630",
        "role": "http://www.aa.com/role/CondensedConsolidatedBalanceSheetsAmericanAirlinesInc",
        "periods": ("2026-06-30", "2025-12-31"),
        "receivables": (10_203_000_000, 9_896_000_000),
        "parent_assets": (64_233_000_000, 61_774_000_000),
        "subsidiary_assets": (72_888_000_000, 70_247_000_000),
    },
)


@pytest.fixture(scope="module", params=FILINGS, ids=[case["folder"] for case in FILINGS])
def aal(request):
    case = request.param
    folder = FIXTURES / "aal" / case["folder"]
    assert folder.is_dir(), f"missing original SEC fixture: {folder}"
    return XBRL.from_directory(folder), case


@pytest.fixture(scope="module")
def apple():
    return XBRL.from_directory(FIXTURES / "aapl" / "10k_2023")


@pytest.fixture(scope="module")
def amazon():
    return XBRL.from_directory(FIXTURES / "amzn" / "10q_2026q2")


@pytest.fixture(scope="module")
def apple_without_definition():
    """An optional-linkbase path, using unmodified files from the tracked fixture."""
    folder = FIXTURES / "aapl" / "10k_2023"
    return XBRL.from_files(
        instance_file=folder / "aapl-20230930_htm.xml",
        schema_file=folder / "aapl-20230930.xsd",
        presentation_file=folder / "aapl-20230930_pre.xml",
        calculation_file=folder / "aapl-20230930_cal.xml",
        label_file=folder / "aapl-20230930_lab.xml",
    )


def _select(xbrl, role, helper):
    statements = xbrl.statements
    if helper == "integer":
        index = next(i for i, spec in enumerate(statements.statements) if spec["role"] == role)
        result = statements[index]
    elif helper == "get":
        result = statements.get(role.rsplit("/", 1)[-1])
    elif helper == "search":
        result = next(s for s in statements.search(role.rsplit("/", 1)[-1]) if s.role_or_type == role)
    elif helper == "all":
        result = next(s for s in statements.all() if s.role_or_type == role)
    else:
        assert helper == "iteration"
        result = next(s for s in statements if s.role_or_type == role)
    assert result is not None
    assert result.role_or_type == role
    return result


def _period_columns(frame):
    return [column for column in frame.columns if str(column)[:4].isdigit()]


def _plain_row(frame, concept):
    selected = frame.loc[frame["concept"].eq(concept) & ~frame["dimension"].fillna(False)]
    assert len(selected) == 1, f"expected the selected role's plain {concept} row, got {len(selected)}"
    return selected.iloc[0]


def _assert_balance_frame(statement, case, **options):
    frame = statement.to_dataframe(view="summary", standard=False, include_unit=True, **options)
    assert _period_columns(frame) == list(case["periods"]), frame.columns.tolist()
    row = _plain_row(frame, RECEIVABLES)
    assert [row[period] for period in case["periods"]] == list(case["receivables"])
    assert row["unit"] == "usd"


@pytest.mark.parametrize("helper", HELPERS)
def test_discovery_helpers_keep_the_selected_subsidiary_balance_sheet(aal, helper):
    xbrl, case = aal
    statement = _select(xbrl, case["role"], helper)
    rows = [row for row in statement.get_raw_data(view=StatementView.SUMMARY) if row["concept"] == RECEIVABLES and not row.get("is_dimension")]
    assert len(rows) == 1, f"{helper} lost the subsidiary-only receivables line"
    assert [rows[0]["values"]["instant_" + period] for period in case["periods"]] == list(case["receivables"])
    _assert_balance_frame(statement, case)

    rendered = statement.render(standard=False, view="summary")
    assert [period.end_date for period in rendered.periods] == list(case["periods"])
    selected = [row for row in rendered.rows if row.metadata.get("concept") == RECEIVABLES and not row.is_dimension]
    assert len(selected) == 1, f"{helper} rendered the parent instead of the subsidiary"
    assert [cell.value for cell in selected[0].cells] == list(case["receivables"])
    assert statement.classified_type == "BalanceSheet"


def test_role_uri_balance_sheet_keeps_its_instant_comparison(aal):
    xbrl, case = aal
    # URI is the selection control; its period policy must also match the filing.
    _assert_balance_frame(xbrl.statements[case["role"]], case)
    frame = xbrl.statements[case["role"]].to_dataframe(standard=False)
    assert _period_columns(frame) == list(case["periods"])
    subsidiary = frame.loc[frame["concept"].eq("us-gaap_Assets") & frame["dimension_member"].eq("aal_AmericanAirlinesIncMember")]
    assert len(subsidiary) == 1
    assert subsidiary[list(case["periods"])].iloc[0].tolist() == list(case["subsidiary_assets"])


def test_group_role_uri_balance_sheet_keeps_its_instant_comparison(aal):
    xbrl, case = aal
    role = case["role"].replace("AmericanAirlinesInc", "AmericanAirlinesGroupInc")
    frame = xbrl.statements[role].to_dataframe(standard=False)
    assert _period_columns(frame) == list(case["periods"])
    row = _plain_row(frame, "us-gaap_Assets")
    assert [row[period] for period in case["periods"]] == list(case["parent_assets"])


def test_amazon_role_uri_balance_sheet_keeps_filed_current_and_prior_assets(amazon):
    statement = amazon.statements["http://www.amazon.com/role/ConsolidatedBalanceSheets"]
    periods = ["2026-06-30", "2025-12-31"]
    expected = [1_095_689_000_000, 818_042_000_000]
    for standard in (False, True):
        frame = statement.to_dataframe(standard=standard)
        assert _period_columns(frame) == periods
        assert _plain_row(frame, "us-gaap_Assets")[periods].tolist() == expected
    named = amazon.statements.balance_sheet().to_dataframe(standard=False)
    assert _period_columns(named) == periods
    assert _plain_row(named, "us-gaap_Assets")[periods].tolist() == expected
    assert statement.classified_type == "BalanceSheet"


def test_named_balance_sheet_keeps_the_primary_role(aal):
    xbrl, case = aal
    primary_role = case["role"].replace("AmericanAirlinesInc", "AmericanAirlinesGroupInc")
    for statement in (
        xbrl.statements["BalanceSheet"],
        xbrl.statements.balance_sheet(),
        xbrl.statements.get("balancesheet"),
    ):
        assert statement is not None
        assert statement.canonical_type == "BalanceSheet"
        assert statement.role_or_type == primary_role
        frame = statement.to_dataframe(standard=False, view="summary")
        assert _period_columns(frame) == list(case["periods"])
        row = _plain_row(frame, "us-gaap_Assets")
        assert [row[period] for period in case["periods"]] == list(case["parent_assets"])
        assert not frame["concept"].eq(RECEIVABLES).any()


def test_standard_and_detailed_keep_legal_entity_receivables(aal):
    xbrl, case = aal
    statement = _select(xbrl, case["role"], "integer")
    for view in ("standard", "detailed"):
        for standard in (False, True):
            frame = statement.to_dataframe(view=view, standard=standard)
            assert _period_columns(frame) == list(case["periods"])
            rows = frame.loc[frame["concept"].eq(RECEIVABLES)]
            assert not rows.empty, (
                view,
                standard,
                "subsidiary receivables disappeared",
            )
            assert any([row[period] for period in case["periods"]] == list(case["receivables"]) for _, row in rows.iterrows())
            children = rows.loc[rows["dimension_member"].eq("aal_AmericanAirlinesIncMember")]
            assert not children.empty, (
                view,
                standard,
                "LegalEntityAxis child disappeared",
            )
            assert any([row[period] for period in case["periods"]] == list(case["receivables"]) for _, row in children.iterrows())


@pytest.mark.parametrize("helper", ("integer", "get"))
def test_helpers_keep_cash_flow_presentation_signs(apple, helper):
    role = apple.statements.cash_flow_statement().role_or_type
    statement = _select(apple, role, helper)
    capex = "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"
    expected = [10_959_000_000, 10_708_000_000, 11_085_000_000]
    for standard in (False, True):
        raw = statement.to_dataframe(standard=standard, view="summary", presentation=False)
        presented = statement.to_dataframe(standard=standard, view="summary", presentation=True)
        assert _period_columns(raw) == [
            "2023-09-30 (FY)",
            "2022-09-24 (FY)",
            "2021-09-25 (FY)",
        ]
        assert _plain_row(raw, capex)[_period_columns(raw)].tolist() == expected
        assert _plain_row(presented, capex)[_period_columns(presented)].tolist() == [-value for value in expected]
        rendered = statement.render(standard=standard)
        row = next(row for row in rendered.rows if row.metadata.get("concept") == capex and not row.is_dimension)
        assert [cell.get_formatted_value() for cell in row.cells] == [
            "$(10,959)",
            "$(10,708)",
            "$(11,085)",
        ]
    assert statement.classified_type == "CashFlowStatement"


@pytest.mark.parametrize("statement_type", ("BalanceSheet", "IncomeStatement"))
def test_helpers_keep_type_based_analysis(apple, statement_type):
    canonical = apple.statements[statement_type]
    expected_ratio = 143_566_000_000 / 145_308_000_000 if statement_type == "BalanceSheet" else 96_995_000_000 / 383_285_000_000
    ratio_name = "current_ratio" if statement_type == "BalanceSheet" else "net_margin"
    trend_name = "total_assets" if statement_type == "BalanceSheet" else "net_income"
    expected_current = 352_583_000_000 if statement_type == "BalanceSheet" else 96_995_000_000
    for helper in ("integer", "get"):
        statement = _select(apple, canonical.role_or_type, helper)
        ratios = statement.calculate_ratios()
        assert ratio_name in ratios, f"{helper} lost classified {statement_type} analysis"
        assert ratios[ratio_name] == pytest.approx(expected_ratio)
        trends = statement.analyze_trends(2)
        assert trend_name in trends
        assert trends[trend_name][0] == expected_current


def test_equity_helpers_keep_roll_forward_and_structural_dimensions(
    apple_without_definition,
):
    xbrl = apple_without_definition
    role = xbrl.statements.statement_of_equity().role_or_type
    for helper in ("integer", "get"):
        statement = _select(xbrl, role, helper)
        for view in ("standard", "detailed"):
            frame = statement.to_dataframe(standard=False, view=view)
            assert _period_columns(frame) == [
                "2023-09-30 (FY)",
                "2022-09-24 (FY)",
                "2021-09-25 (FY)",
            ]
            components = frame.loc[frame["dimension_axis"].eq("us-gaap:StatementEquityComponentsAxis")]
            assert not components.empty, f"{view} lost structural equity components"
            assert not components["is_breakdown"].any()
            beginning = components.loc[components["label"].eq("Common stock and additional paid-in capital - Beginning balance")]
            ending = components.loc[components["label"].eq("Common stock and additional paid-in capital - Ending balance")]
            assert beginning["2023-09-30 (FY)"].tolist() == [64_849_000_000]
            assert ending["2023-09-30 (FY)"].tolist() == [73_812_000_000]


@pytest.mark.parametrize("selection", ("named", "typed", "get", "uri", "blank"))
def test_apple_parenthetical_keeps_filed_share_and_par_value_instants(apple, selection):
    if selection == "named":
        statement = apple.statements.balance_sheet(parenthetical=True)
    elif selection == "typed":
        statement = apple.statements["BalanceSheetParenthetical"]
    elif selection == "get":
        statement = apple.statements.get("BalanceSheetParenthetical")
    elif selection == "uri":
        statement = apple.statements[APPLE_PARENTHETICAL]
    else:
        statement = Statement(apple, APPLE_PARENTHETICAL, canonical_type="")
    assert statement is not None
    assert statement.role_or_type == APPLE_PARENTHETICAL
    assert not statement.canonical_type
    assert statement.classified_type == "BalanceSheetParenthetical"
    periods = ["2023-09-30", "2022-09-24"]
    expected = {
        "us-gaap_CommonStockParOrStatedValuePerShare": ([0.00001, 0.00001], "usdPerShare"),
        "us-gaap_CommonStockSharesAuthorized": ([50_400_000_000, 50_400_000_000], "shares"),
        "us-gaap_CommonStockSharesIssued": ([15_550_061_000, 15_943_425_000], "shares"),
        "us-gaap_CommonStockSharesOutstanding": ([15_550_061_000, 15_943_425_000], "shares"),
    }
    raw = statement.get_raw_data(view=StatementView.SUMMARY)
    assert {row["concept"] for row in raw if not row.get("is_abstract")} == set(expected)
    for concept, (values, unit) in expected.items():
        row = next(row for row in raw if row["concept"] == concept)
        assert [row["values"]["instant_" + period] for period in periods] == values
        assert [row["units"]["instant_" + period] for period in periods] == [unit, unit]
    for standard in (False, True):
        frame = statement.to_dataframe(view="summary", standard=standard, include_unit=True)
        assert _period_columns(frame) == periods
        assert frame["concept"].tolist() == list(expected)
        rendered = statement.render(standard=standard, view="summary")
        assert rendered.title == "CONSOLIDATED BALANCE SHEETS (Parenthetical)"
        assert [period.key for period in rendered.periods] == ["instant_" + period for period in periods]
        assert rendered.statement_type == "BalanceSheetParenthetical"
        assert [row.metadata["concept"] for row in rendered.rows] == list(expected)
        for concept, (values, unit) in expected.items():
            assert _plain_row(frame, concept)[periods].tolist() == values
            assert _plain_row(frame, concept)["unit"] == unit
            row = next(row for row in rendered.rows if row.metadata["concept"] == concept)
            assert [cell.value for cell in row.cells] == values
            assert [row.metadata["units"]["instant_" + period] for period in periods] == [unit, unit]
    validation = statement.validate()
    assert validation.metadata["detected_type"] == "BalanceSheetParenthetical"
    assert [issue.code for issue in validation.issues] == ["NO_VALIDATOR"]


def _reset_statement_selection(apple, monkeypatch):
    monkeypatch.setattr(apple, "_statement_resolver", None)
    monkeypatch.setattr(apple, "_all_statements_cached", None)
    for name in (
        "_statement_indices",
        "_statement_by_standard_name",
        "_statement_by_primary_concept",
        "_statement_by_role_uri",
        "_statement_by_role_name",
    ):
        monkeypatch.setattr(apple, name, {})


@pytest.mark.parametrize(
    "uri",
    (
        "https://example.test/role/CONSOLIDATEDBALANCESHEETSParenthetical",
        "http://example.test/role/CONSOLIDATEDBALANCESHEETS",
        "HTTP://example.test/role/CONSOLIDATEDBALANCESHEETS",
        "HtTpS://example.test/role/CONSOLIDATEDBALANCESHEETS",
        "HTTP://example.test/role/CONSOLIDATEDBALANCESHEETSParenthetical",
        "HtTpS://example.test/role/CONSOLIDATEDBALANCESHEETSParenthetical",
    ),
)
def test_missing_literal_role_uri_does_not_select_the_primary_balance_sheet(apple, monkeypatch, uri):
    _reset_statement_selection(apple, monkeypatch)
    assert uri not in apple.presentation_trees
    assert apple.statements[uri] is None
    matching, selected_role, _kind = apple.find_statement(uri)
    assert matching == []
    assert selected_role is None
    assert apple.get_statement(uri) == []
    for standard in (False, True):
        assert apple.render_statement(uri, standard=standard) is None
        statement = Statement(apple, uri)
        assert statement.get_raw_data() == []
        assert statement.render(standard=standard) is None


@pytest.mark.parametrize("statement_type", ("ScheduleOfInvestmentsParenthetical", "FinancialHighlightsParenthetical"))
def test_other_instant_statement_parenthetical_types_keep_generic_duration_policy(apple, statement_type):
    """Synthetic type boundaries use Apple's actual periods, without claiming filed roles."""
    assert [key for key, _label in select_periods(apple, statement_type)] == [
        "duration_2022-09-25_2023-09-30",
        "duration_2021-09-26_2022-09-24",
        "duration_2020-09-27_2021-09-25",
    ]


@pytest.mark.parametrize("catalog_state", ("normal", "warm", "fresh", "fresh_indexes"))
def test_literal_role_uri_keeps_the_presentation_role_without_a_catalog_entry(apple, monkeypatch, catalog_state):
    entries = apple.get_all_statements()
    original = next(entry for entry in entries if entry["role"] == APPLE_PARENTHETICAL)
    tree = apple.presentation_trees[APPLE_PARENTHETICAL]
    if catalog_state != "normal":
        monkeypatch.setattr(apple, "_statement_resolver", StatementResolver(apple))
        monkeypatch.setattr(apple, "get_all_statements", lambda: [entry for entry in entries if entry["role"] != APPLE_PARENTHETICAL])
        if catalog_state == "fresh":
            monkeypatch.setattr(apple, "_statement_resolver", None)
        elif catalog_state == "fresh_indexes":
            _reset_statement_selection(apple, monkeypatch)
    expected_kind = "BalanceSheetParenthetical" if catalog_state == "normal" else None
    matching, selected_role, actual_kind = apple.find_statement(APPLE_PARENTHETICAL)
    assert selected_role == APPLE_PARENTHETICAL
    assert actual_kind == expected_kind
    assert len(matching) == 1
    assert matching[0]["role"] == APPLE_PARENTHETICAL
    assert matching[0]["definition"] == original["definition"]
    assert matching[0]["element_count"] == len(tree.all_nodes)
    if catalog_state == "normal":
        assert matching[0] == original
    expected_concepts = [
        "us-gaap_CommonStockParOrStatedValuePerShare",
        "us-gaap_CommonStockSharesAuthorized",
        "us-gaap_CommonStockSharesIssued",
        "us-gaap_CommonStockSharesOutstanding",
    ]
    for statement in (Statements(apple)[APPLE_PARENTHETICAL], Statement(apple, APPLE_PARENTHETICAL)):
        assert statement is not None
        assert statement.role_or_type == APPLE_PARENTHETICAL
        assert statement.canonical_type is None
        assert statement.classified_type == expected_kind
        raw = statement.get_raw_data(view=StatementView.SUMMARY)
        assert [row["concept"] for row in raw if not row.get("is_abstract") and not row.get("is_dimension")] == expected_concepts
        row = next(row for row in raw if row["concept"] == "us-gaap_CommonStockSharesOutstanding")
        assert [row["values"]["instant_" + date] for date in ("2023-09-30", "2022-09-24")] == [15_550_061_000, 15_943_425_000]
        assert [row["units"]["instant_" + date] for date in ("2023-09-30", "2022-09-24")] == ["shares", "shares"]
        assert apple.get_statement(APPLE_PARENTHETICAL, view=StatementView.SUMMARY) == raw
        for standard in (False, True):
            rendered = statement.render(standard=standard, view="summary")
            assert rendered.title == "CONSOLIDATED BALANCE SHEETS (Parenthetical)"
            assert rendered.statement_type == expected_kind
            assert [row.metadata["concept"] for row in rendered.rows] == expected_concepts
            direct = apple.render_statement(APPLE_PARENTHETICAL, standard=standard, view="summary")
            assert direct is not None
            assert direct.title == rendered.title
            assert [row.metadata["concept"] for row in direct.rows] == expected_concepts
            if expected_kind:
                assert [period.key for period in rendered.periods] == ["instant_2023-09-30", "instant_2022-09-24"]
            else:
                # An uncatalogued tree stays untyped, including its generic periods.
                assert all(period.key.startswith("duration_") for period in rendered.periods)


@pytest.mark.parametrize("kind", ("BalanceSheet", "CashFlowStatement", "StatementOfEquity"))
@pytest.mark.parametrize("selection", ("typed", "uri", "blank"))
def test_typed_uri_and_blank_selection_keep_classified_processing(apple, kind, selection):
    canonical = apple.statements[kind]
    role = canonical.role_or_type
    if selection == "typed":
        statement = canonical
    elif selection == "uri":
        statement = apple.statements[role]
    else:
        statement = Statement(apple, role, canonical_type="")
    assert statement.classified_type == kind
    frame = statement.to_dataframe(standard=False, view="summary", presentation=True)
    if kind == "BalanceSheet":
        periods = ["2023-09-30", "2022-09-24"]
        concept = "us-gaap_Assets"
        expected = [352_583_000_000, 352_755_000_000]
    else:
        periods = ["2023-09-30 (FY)", "2022-09-24 (FY)", "2021-09-25 (FY)"]
        if kind == "CashFlowStatement":
            concept = "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"
            expected = [-10_959_000_000, -10_708_000_000, -11_085_000_000]
        else:
            concept = "us-gaap_StockholdersEquity"
            beginning = frame.loc[frame["concept"].eq(concept) & frame["label"].eq("Beginning balances")]
            ending = frame.loc[frame["concept"].eq(concept) & frame["label"].eq("Ending balances")]
            assert beginning[periods[0]].tolist() == [50_672_000_000]
            assert ending[periods[0]].tolist() == [62_146_000_000]
            assert _period_columns(frame) == periods
            return
    assert _period_columns(frame) == periods
    assert _plain_row(frame, concept)[periods].tolist() == expected


@pytest.mark.parametrize("accessor, kind", NAMED_ACCESSORS)
@pytest.mark.parametrize("parenthetical", (False, True))
def test_every_named_accessor_keeps_its_requested_statement_family(accessor, kind, parenthetical):
    """One isolated resolver mapping covers parenthetical families absent from fixtures."""
    primary_role = "https://example.test/role/Primary"
    supplemental_role = "https://example.test/role/SupplementParenthetical"
    entries = [
        {"role": primary_role, "type": kind, "definition": "Primary", "role_name": "Primary"},
        {"role": supplemental_role, "type": kind + "Parenthetical", "definition": "Supplement", "role_name": "SupplementParenthetical"},
    ]

    def find_statement(name, is_parenthetical=False):
        entry = entries[1] if is_parenthetical or name == supplemental_role else entries[0]
        return [entry], entry["role"], entry["type"]

    def get_statement(name, **_options):
        _, selected_role, _ = find_statement(name)
        value = 504 if selected_role == supplemental_role else 100
        return [{"concept": "example_SelectedValue", "label": "Selected value", "values": {"instant_2023-09-30": value}}]

    xbrl = SimpleNamespace(get_all_statements=lambda: entries, presentation_trees={}, find_statement=find_statement, get_statement=get_statement)
    statement = getattr(Statements(xbrl), accessor)(parenthetical=parenthetical)
    assert statement is not None
    assert statement.role_or_type == (supplemental_role if parenthetical else primary_role)
    assert statement.canonical_type == (None if parenthetical else kind)
    assert statement.classified_type == (kind + "Parenthetical" if parenthetical else kind)
    assert statement.get_raw_data()[0]["values"]["instant_2023-09-30"] == (504 if parenthetical else 100)


def test_balance_sheet_parenthetical_resolver_fallback_keeps_the_resolved_role(apple, monkeypatch):
    statements = Statements(apple)
    monkeypatch.setattr(statements, "find_statement_by_primary_concept", lambda *_args, **_kwargs: None)
    statement = statements.balance_sheet(parenthetical=True)
    assert statement is not None
    assert statement.role_or_type == APPLE_PARENTHETICAL
    assert statement.canonical_type is None
    assert {row["concept"] for row in statement.get_raw_data(view=StatementView.SUMMARY) if not row.get("is_abstract")} == {
        "us-gaap_CommonStockParOrStatedValuePerShare",
        "us-gaap_CommonStockSharesAuthorized",
        "us-gaap_CommonStockSharesIssued",
        "us-gaap_CommonStockSharesOutstanding",
    }


@pytest.mark.parametrize("accessor, kind", NAMED_ACCESSORS)
def test_missing_parenthetical_does_not_fall_back_to_an_ordinary_statement(accessor, kind):
    xbrl = SimpleNamespace(get_all_statements=list, presentation_trees={}, find_statement=lambda *_args: ([], None, None))
    statements = Statements(xbrl)
    assert getattr(statements, accessor)(parenthetical=True) is None
    assert statements[kind + "Parenthetical"] is None
    assert statements.get(kind + "Parenthetical") is None


def test_role_selected_validation_uses_the_resolver_kind(apple, monkeypatch):
    role = "https://example.test/role/Position"
    original_get_statement = apple.get_statement
    primary_role = apple.statements.balance_sheet().role_or_type
    monkeypatch.setattr(apple, "get_all_statements", lambda: [{"role": role, "type": "BalanceSheet"}])
    monkeypatch.setattr(apple, "get_statement", lambda name, **options: original_get_statement(primary_role if name == role else name, **options))
    statement = Statements(apple)[0]
    assert statement is not None
    result = statement.validate()
    assert result.is_valid
    assert "fundamental_equation" in result.checks_performed


def test_role_selected_equity_matrix_and_context_keep_the_resolver_kind(apple, monkeypatch):
    role = "https://example.test/role/CapitalChanges"
    original_get_statement = apple.get_statement
    equity_role = apple.statements.statement_of_equity().role_or_type
    monkeypatch.setattr(apple, "get_all_statements", lambda: [{"role": role, "type": "StatementOfEquity"}])
    monkeypatch.setattr(apple, "get_statement", lambda name, **options: original_get_statement(equity_role if name == role else name, **options))
    statement = Statements(apple)[0]
    assert statement is not None
    matrix = statement.to_dataframe(matrix=True, standard=False)
    assert "Common stock and additional paid-in capital" in matrix.columns
    assert "Retained earnings/(Accumulated deficit)" in matrix.columns
    beginning = matrix.loc[matrix["label"].eq("Beginning balances")]
    assert beginning["Common stock and additional paid-in capital"].tolist() == [64_849_000_000]
    assert beginning["Retained earnings/(Accumulated deficit)"].tolist() == [-3_068_000_000]
    assert "Statement Type: StatementOfEquity" in statement.to_context(detail="full")


@pytest.mark.parametrize("selection", ("canonical", "uri", "uri_parenthetical"))
def test_direct_parenthetical_render_keeps_filed_share_and_par_value_instants(apple, selection):
    name = "BalanceSheet" if selection == "canonical" else APPLE_PARENTHETICAL
    expected = {
        "us-gaap_CommonStockParOrStatedValuePerShare": [0.00001, 0.00001],
        "us-gaap_CommonStockSharesAuthorized": [50_400_000_000, 50_400_000_000],
        "us-gaap_CommonStockSharesIssued": [15_550_061_000, 15_943_425_000],
        "us-gaap_CommonStockSharesOutstanding": [15_550_061_000, 15_943_425_000],
    }
    for standard in (False, True):
        rendered = apple.render_statement(name, parenthetical=selection != "uri", standard=standard, view="summary")
        assert rendered is not None
        assert rendered.title == "CONSOLIDATED BALANCE SHEETS (Parenthetical)"
        assert rendered.statement_type == "BalanceSheetParenthetical"
        assert [period.key for period in rendered.periods] == ["instant_2023-09-30", "instant_2022-09-24"]
        assert [row.metadata["concept"] for row in rendered.rows] == list(expected)
        for row in rendered.rows:
            assert [cell.value for cell in row.cells] == expected[row.metadata["concept"]]


def test_direct_missing_parenthetical_does_not_retrieve_primary_rows(apple, monkeypatch):
    original_find_statement = apple.find_statement

    def no_parenthetical(name, is_parenthetical=False):
        if is_parenthetical:
            return [], None, None
        return original_find_statement(name)

    monkeypatch.setattr(apple, "find_statement", no_parenthetical)
    assert apple.render_statement("BalanceSheet", parenthetical=True) is None


def test_parenthetical_processing_keeps_primary_presentation_signs_inactive(apple, monkeypatch):
    """A single synthetic sign isolates the gate; original Apple values are positive."""
    concept = "us-gaap_CommonStockSharesIssued"
    raw = deepcopy(next(row for row in apple.statements[APPLE_PARENTHETICAL].get_raw_data(view=StatementView.SUMMARY) if row["concept"] == concept))
    raw["preferred_signs"] = {key: -1 for key in raw["values"]}
    monkeypatch.setattr(apple, "get_statement", lambda *_args, **_options: [raw])
    statement = apple.statements[APPLE_PARENTHETICAL]
    for standard in (False, True):
        frame = statement.to_dataframe(standard=standard, presentation=True, view="summary")
        assert _plain_row(frame, concept)[["2023-09-30", "2022-09-24"]].tolist() == [15_550_061_000, 15_943_425_000]
        rendered = statement.render(standard=standard, view="summary")
        assert [cell.value for cell in rendered.rows[0].cells] == [15_550_061_000, 15_943_425_000]


def test_untyped_ibm_note_keeps_filed_facts_without_an_inferred_primary_kind():
    xbrl = XBRL.from_directory(FIXTURES / "ibm" / "10k_2024")
    role = "http://www.ibm.com/role/BorrowingsLongTermDebtComponentsDetails"
    statement = xbrl.statements[role]
    assert statement is not None
    assert statement.canonical_type is None
    assert statement.classified_type is None
    rows = [row for row in statement.get_raw_data(view=StatementView.SUMMARY) if row["concept"] == "us-gaap_DebtInstrumentUnamortizedDiscount"]
    assert len(rows) == 1
    assert [rows[0]["values"]["instant_" + period] for period in ("2024-12-31", "2023-12-31")] == [824_000_000, 838_000_000]


# Synthetic catalogue controls exercise the actual resolver, including registry
# families without a filed parenthetical role in the Apple fixture. They assert
# selection policy, rather than claiming that these are filed Apple statements.
PARENTHETICAL_REGISTRY_KINDS = (
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "StatementOfEquity",
    "ComprehensiveIncome",
    "Notes",
    "AccountingPolicies",
    "Disclosures",
    "SegmentDisclosure",
    "CoverPage",
    "ScheduleOfInvestments",
    "FinancialHighlights",
)
PARENTHETICAL_FILTER_SUPPORTED = {
    "BalanceSheet",
    "IncomeStatement",
    "StatementOfEquity",
    "ComprehensiveIncome",
    "ScheduleOfInvestments",
}
PARENTHETICAL_MATCHERS = (
    "_match_by_primary_concept",
    "_match_by_concept_pattern",
    "_match_by_role_pattern",
)


def _real_resolver_catalogue(kind, *, ordinary=True, parenthetical=True):
    entry = statement_registry[kind]
    concept = "us-gaap_StatementOfComprehensiveIncomeAbstract" if kind == "ComprehensiveIncome" else entry.primary_concepts[0]
    rows = []
    if ordinary:
        rows.append({"role": f"https://example.test/role/{kind}", "role_name": kind, "definition": kind, "primary_concept": concept, "type": None})
    if parenthetical:
        rows.append(
            {
                "role": f"https://example.test/role/{kind}Parenthetical",
                "role_name": kind + "Parenthetical",
                "definition": kind + " (Parenthetical)",
                "primary_concept": concept,
                "type": None,
            }
        )
    trees = {row["role"]: SimpleNamespace(all_nodes={concept: object()}) for row in rows}
    return StatementResolver(SimpleNamespace(get_all_statements=lambda: rows, presentation_trees=trees))


@pytest.mark.parametrize("kind", PARENTHETICAL_REGISTRY_KINDS)
@pytest.mark.parametrize("matcher", PARENTHETICAL_MATCHERS)
@pytest.mark.parametrize("parenthetical", (False, True))
def test_real_resolver_matchers_honour_positive_parenthetical_requests(kind, matcher, parenthetical):
    resolver = _real_resolver_catalogue(kind)
    matched, role, _confidence = getattr(resolver, matcher)(kind, parenthetical)
    expected = f"https://example.test/role/{kind}" + ("Parenthetical" if parenthetical else "")
    assert role == expected
    expected_roles = [expected]
    if not parenthetical and kind not in PARENTHETICAL_FILTER_SUPPORTED:
        expected_roles.append(f"https://example.test/role/{kind}Parenthetical")
    assert [row["role"] for row in matched] == expected_roles


@pytest.mark.parametrize("kind", PARENTHETICAL_REGISTRY_KINDS)
@pytest.mark.parametrize("matcher", PARENTHETICAL_MATCHERS)
def test_real_resolver_matchers_reject_ordinary_only_parenthetical_requests(kind, matcher):
    resolver = _real_resolver_catalogue(kind, parenthetical=False)
    assert getattr(resolver, matcher)(kind, True) == ([], None, 0.0)


@pytest.mark.parametrize("kind", PARENTHETICAL_REGISTRY_KINDS)
@pytest.mark.parametrize("matcher", PARENTHETICAL_MATCHERS)
def test_real_resolver_matchers_preserve_default_unsupported_family_policy(kind, matcher):
    resolver = _real_resolver_catalogue(kind, ordinary=False)
    matched, role, confidence = getattr(resolver, matcher)(kind, False)
    if kind in PARENTHETICAL_FILTER_SUPPORTED:
        assert (matched, role, confidence) == ([], None, 0.0)
    else:
        assert role == f"https://example.test/role/{kind}Parenthetical"
        assert [row["role"] for row in matched] == [role]


@pytest.mark.parametrize("kind", PARENTHETICAL_REGISTRY_KINDS)
def test_real_resolver_keeps_marked_parenthetical_without_exact_type_bucket(kind):
    resolver = _real_resolver_catalogue(kind)
    matched, role, actual_type, _confidence = resolver.find_statement(kind, True)
    assert role == f"https://example.test/role/{kind}Parenthetical"
    assert [row["role"] for row in matched] == [role]
    assert matched[0]["type"] is None
    assert actual_type == kind


def _real_filing_without_parenthetical_roles(xbrl):
    isolated = deepcopy(xbrl)
    catalogue = [
        row
        for row in isolated.get_all_statements()
        if "parenthetical" not in " ".join(str(row.get(key, "")) for key in ("role", "role_name", "definition", "type")).lower()
    ]
    isolated.parser.presentation_trees = {
        role: tree for role, tree in isolated.presentation_trees.items() if "parenthetical" not in (role + " " + str(tree.definition)).lower()
    }
    isolated.get_all_statements = lambda: catalogue
    isolated._statement_resolver = None
    for name, value in list(vars(isolated).items()):
        if name.startswith("_statement") and isinstance(value, dict):
            setattr(isolated, name, {})
    isolated._all_statements_cached = catalogue
    return isolated


@pytest.mark.parametrize("accessor, kind", NAMED_ACCESSORS)
@pytest.mark.parametrize("route", ("helper", "finder", "render"))
def test_real_apple_missing_parenthetical_families_never_return_ordinary_roles(apple, accessor, kind, route):
    """Retain actual nonempty Apple catalogue/trees, with parentheticals removed in memory."""
    isolated = _real_filing_without_parenthetical_roles(apple)
    assert isolated.get_all_statements()
    if route == "helper":
        assert getattr(isolated.statements, accessor)(parenthetical=True) is None
    elif route == "finder":
        with pytest.raises(StatementNotFoundError):
            isolated.find_statement(kind, True)
    else:
        with pytest.raises(StatementNotFoundError):
            isolated.render_statement(kind, parenthetical=True)


@pytest.fixture(scope="module")
def apple_2010_parenthetical_boundary():
    return XBRL.from_directory(FIXTURES / "aapl" / "10k_2010")


@pytest.mark.parametrize("route", ("helper", "finder", "render"))
def test_real_apple_2010_missing_parenthetical_ci_does_not_substitute_equity(apple_2010_parenthetical_boundary, route):
    """Apple FY2010 embeds ordinary comprehensive income in its equity statement."""
    isolated = _real_filing_without_parenthetical_roles(apple_2010_parenthetical_boundary)
    if route == "helper":
        assert isolated.statements.comprehensive_income(parenthetical=True) is None
    elif route == "finder":
        with pytest.raises(StatementNotFoundError):
            isolated.find_statement("ComprehensiveIncome", True)
    else:
        with pytest.raises(StatementNotFoundError):
            isolated.render_statement("ComprehensiveIncome", parenthetical=True)


def test_real_apple_2010_ordinary_ci_keeps_filed_equity_role(apple_2010_parenthetical_boundary):
    expected = "http://www.apple.com/taxonomy/role/StatementOfShareholdersEquityAndOtherComprehensiveIncome"
    matched, role, actual_type = apple_2010_parenthetical_boundary.find_statement("ComprehensiveIncome")
    assert role == expected
    assert actual_type == "ComprehensiveIncome"
    assert matched[0]["role"] == expected
    assert apple_2010_parenthetical_boundary.statements.comprehensive_income().role_or_type == expected


CASH_FLOW_PARENTHETICAL_FAMILY_NAMES = (
    "CashFlowParenthetical",
    "CashFlowsParenthetical",
    "CashFlowParentheticals",
    "CashFlowsParentheticals",
    "CashFlowStatementParenthetical",
    "CashFlowsStatementParenthetical",
    "CashFlowStatementsParentheticals",
    "ConsolidatedCashFlowParenthetical",
    "CondensedConsolidatedCashFlowsParenthetical",
    "StatementOfCashFlowsParenthetical",
    "ConsolidatedStatementsOfCashFlowsParenthetical",
    "CONSOLIDATEDSTATEMENTOFCASHFLOWSParenthetical",
    "ConsolidatedStatementsofCashFlowsunauditedParenthetical",
    "CondensedConsolidatedStatementsofCashFlowsAmericanAirlinesGroupIncParenthetical",
)
CASH_FLOW_PARENTHETICAL_OTHER_NAMES = (
    "CashFlowHedgesParenthetical",
    "CashFlowsHedgesParenthetical",
    "DisclosureGainsLossesRelatedToCashFlowHedgesParenthetical",
    "DisclosurePreTaxEffectOfDerivativeInstrumentsDesignatedAsCashFlowAndNetInvestmentHedgesParenthetical",
    "GainsLossesRelatedToCashFlowParenthetical",
    "DerivativeInstrumentsCashFlowsParenthetical",
    "NotCashFlowParenthetical",
    "CashFlowHedgeStatementParenthetical",
    "CashFlowParentheticalHedgeDetails",
)


def _untyped_cash_flow_name_resolver(name, form="both"):
    """A synthetic supplementary tree proves only family-name resolution."""
    role = "https://example.test/role/" + name
    role_name = name
    if form == "role_name_only":
        role = "https://example.test/role/UnclassifiedParenthetical"
    elif form in ("http_uri_only", "https_uri_only"):
        role = ("http://" if form == "http_uri_only" else "https://") + "example.test/role/" + name
        role_name = ""
    concept = "us-gaap_CommonStockNumberOfSharesParValueAndOtherDisclosuresAbstract"
    row = {"role": role, "role_name": role_name, "definition": name, "primary_concept": concept, "type": None}
    tree = SimpleNamespace(all_nodes={concept: object()})
    return StatementResolver(SimpleNamespace(get_all_statements=lambda: [row], presentation_trees={role: tree})), row


@pytest.mark.parametrize("name", CASH_FLOW_PARENTHETICAL_FAMILY_NAMES)
@pytest.mark.parametrize("form", ("role_name_only", "http_uri_only", "https_uri_only"))
def test_untyped_cash_flow_parenthetical_family_names_need_no_main_totals(name, form):
    resolver, row = _untyped_cash_flow_name_resolver(name, form)
    matched, role, _confidence = resolver._match_by_role_pattern("CashFlowStatement", True)
    assert matched == [row]
    assert role == row["role"]
    matched, role, actual_type, _confidence = resolver.find_statement("CashFlowStatement", True)
    assert matched == [row]
    assert role == row["role"]
    assert actual_type == "CashFlowStatement"
    assert row["type"] is None


@pytest.mark.parametrize("name", CASH_FLOW_PARENTHETICAL_OTHER_NAMES)
@pytest.mark.parametrize("form", ("role_name_only", "http_uri_only", "https_uri_only"))
def test_untyped_cash_flow_mentions_do_not_identify_parenthetical_family(name, form):
    resolver, _row = _untyped_cash_flow_name_resolver(name, form)
    assert resolver._match_by_role_pattern("CashFlowStatement", True) == ([], None, 0.0)
    with pytest.raises(StatementNotFoundError):
        resolver.find_statement("CashFlowStatement", True)


def test_cash_flow_default_role_pattern_preserves_legacy_substring_policy():
    """This synthetic matcher control preserves False policy, not a full statement classification."""
    resolver, row = _untyped_cash_flow_name_resolver("DisclosureGainsLossesRelatedToCashFlowHedgesParenthetical")
    matched, role, _confidence = resolver._match_by_role_pattern("CashFlowStatement", False)
    assert matched == [row]
    assert role == row["role"]


@pytest.fixture(scope="module", params=("aapl", "msft"))
def real_cash_flow_hedge_note_filing(request):
    company = request.param
    year = "10k_2010" if company == "aapl" else "10k_2015"
    xbrl = XBRL.from_directory(FIXTURES / company / year)
    stem = "http://www.apple.com/taxonomy/role/" if company == "aapl" else "http://www.microsoft.com/taxonomy/role/"
    note_name = (
        "DisclosurePreTaxEffectOfDerivativeInstrumentsDesignatedAsCashFlowAndNetInvestmentHedgesParenthetical"
        if company == "aapl"
        else "DisclosureGainsLossesRelatedToCashFlowHedgesParenthetical"
    )
    return xbrl, stem + note_name, stem + "StatementOfCashFlowsIndirect"


@pytest.mark.parametrize("route", ("helper", "finder", "render_plain", "render_standard"))
def test_real_cash_flow_parenthetical_request_does_not_select_hedge_note(real_cash_flow_hedge_note_filing, route):
    """Unmodified Apple FY2010 and Microsoft FY2015 contain parenthetical hedge notes."""
    xbrl, note_role, _ordinary_role = real_cash_flow_hedge_note_filing
    metadata = next(row for row in xbrl.get_all_statements() if row["role"] == note_role)
    assert metadata["type"] == "Disclosures"
    assert metadata["category"] == "disclosure"
    assert note_role in xbrl.presentation_trees
    if route == "helper":
        assert xbrl.statements.cash_flow_statement(parenthetical=True) is None
    elif route == "finder":
        with pytest.raises(StatementNotFoundError):
            xbrl.find_statement("CashFlowStatement", True)
    else:
        with pytest.raises(StatementNotFoundError):
            xbrl.render_statement("CashFlowStatement", parenthetical=True, standard=route == "render_standard")


def test_real_cash_flow_ordinary_request_keeps_filed_statement_role(real_cash_flow_hedge_note_filing):
    xbrl, _note_role, ordinary_role = real_cash_flow_hedge_note_filing
    matched, role, actual_type = xbrl.find_statement("CashFlowStatement", False)
    assert matched[0]["role"] == role == ordinary_role
    assert actual_type == "CashFlowStatement"
    assert xbrl.statements.cash_flow_statement().role_or_type == ordinary_role


@pytest.mark.parametrize("parenthetical", (False, True))
@pytest.mark.parametrize("standard", (False, True))
def test_real_cash_flow_hedge_note_literal_role_remains_exact(real_cash_flow_hedge_note_filing, parenthetical, standard):
    xbrl, note_role, _ordinary_role = real_cash_flow_hedge_note_filing
    matched, role, actual_type = xbrl.find_statement(note_role, parenthetical)
    assert matched[0]["role"] == role == note_role
    assert actual_type == "Disclosures"
    expected = xbrl.render_statement(note_role, parenthetical=False, standard=standard)
    actual = xbrl.render_statement(note_role, parenthetical=parenthetical, standard=standard)
    assert expected is not None
    assert actual is not None
    assert actual.title == expected.title
    assert actual.statement_type == expected.statement_type == "Disclosures"
    assert [period.key for period in actual.periods] == [period.key for period in expected.periods]
    assert [row.metadata.get("concept") for row in actual.rows] == [row.metadata.get("concept") for row in expected.rows]
    assert [[cell.value for cell in row.cells] for row in actual.rows] == [[cell.value for cell in row.cells] for row in expected.rows]
