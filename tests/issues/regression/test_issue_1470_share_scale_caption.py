"""Share captions must describe the scale actually displayed by the renderer.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1470

Intuit's FY2026 10-K (0000896878-26-000037) files 276,000,000 basic
weighted-average shares with decimals=-6 and displays 276. Oracle's FY2026
10-K (0001193125-26-277521) files 2,860,000,000 shares with decimals=-6
and displays 2,860. CrowdStrike's FY2026 10-K (0001535527-26-000010)
files 250,576,000 shares with decimals=-3 and displays 250,576. These
reported facts are represented as renderer inputs below; they are not
substitutes for the unmodified SEC attachments used in the separate replay.

Other inputs are synthetic controls for scaling, raw counts, signs, EPS,
statement types, and both standardization modes. The negative share count
is a formatting control, not a reported company fact.
"""

import io
import json
import math
import pickle

import pytest
from rich.console import Console

from edgar.xbrl.core import PERIOD_END_LABEL
from edgar.xbrl.rendering import (
    RenderedStatement,
    eps_concepts,
    render_statement,
    share_concepts,
)

pytestmark = pytest.mark.fast

CURRENT = "duration_2025-08-01_2026-07-31"
PREVIOUS = "duration_2024-08-01_2025-07-31"
PERIODS = [(CURRENT, "Jul 31, 2026"), (PREVIOUS, "Jul 31, 2025")]
MISSING = object()
SCALES = [(-3, "thousands"), (-6, "millions"), (-9, "billions")]
BASIC = "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic"
DILUTED = "us-gaap_WeightedAverageNumberOfSharesOutstandingDiluted"
MONEY = "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"

# Literal domains keep production-list changes from deleting their oracles.
EXPECTED_SHARE_CONCEPTS = (
    "us-gaap_CommonStockSharesOutstanding",
    "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
    "us-gaap_WeightedAverageNumberOfSharesOutstandingDiluted",
    "us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
    "us-gaap_CommonStockSharesIssued",
)
EXPECTED_EPS_CONCEPTS = (
    "us-gaap_EarningsPerShareBasic",
    "us-gaap_EarningsPerShareDiluted",
    "us-gaap_EarningsPerShareBasicAndDiluted",
    "us-gaap_IncomeLossFromContinuingOperationsPerBasicShare",
    "us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare",
    "us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxPerBasicShare",
    "us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxPerDilutedShare",
    "us-gaap_NetAssetValuePerShare",
    "us-gaap_BookValuePerShare",
    "us-gaap_CommonStockDividendsPerShareDeclared",
    "us-gaap_CommonStockDividendsPerShareCashPaid",
    "us-gaap_CommonStockParOrStatedValuePerShare",
)


def _item(label, concept, value, decimals):
    return {
        "label": label,
        "concept": concept,
        "level": 0,
        "has_values": True,
        "is_abstract": False,
        "is_total": False,
        "values": {CURRENT: value, PREVIOUS: -value},
        "decimals": {} if decimals is MISSING else {CURRENT: decimals, PREVIOUS: decimals},
    }


def _render(scale, shares_decimals, raw_shares=276_000_000, *, standard=False, statement_type="IncomeStatement", concept=BASIC, include_share=True):
    monetary_value = 123 * 10 ** (-scale)
    items = [_item("Revenue", MONEY, monetary_value, scale)]
    if include_share:
        items.append(_item("Weighted-average shares", concept, raw_shares, shares_decimals))
    items.extend(_item("Per share data", name, 1.25, 2) for name in EXPECTED_EPS_CONCEPTS)
    return render_statement(
        items,
        PERIODS,
        "Share caption controls",
        statement_type,
        standard=standard,
    )


def _row(rendered, concept):
    return next(row for row in rendered.rows if row.metadata.get("concept") == concept)


def _assert_values(rendered, concept, raw_value, formatted):
    row = _row(rendered, concept)
    raw_by_period = {CURRENT: raw_value, PREVIOUS: -raw_value}
    display_by_period = {CURRENT: formatted, PREVIOUS: f"-{formatted}"}
    assert [cell.value for cell in row.cells] == [raw_by_period[key] for key in rendered.header.period_keys]
    assert [cell.get_formatted_value() for cell in row.cells] == [display_by_period[key] for key in rendered.header.period_keys]
    for presentation in (False, True):
        frame = rendered.to_dataframe(presentation=presentation)
        selected = frame.loc[frame["concept"].eq(concept)]
        assert selected["2026-07-31"].tolist() == [raw_value]
        assert selected["2025-07-31"].tolist() == [-raw_value]


def _assert_eps(rendered):
    for concept in EXPECTED_EPS_CONCEPTS:
        _assert_values(rendered, concept, 1.25, "1.25")


def _assert_caption_exports(rendered, expected_note):
    assert rendered.units_note == expected_note
    serialized = json.loads(json.dumps(rendered.to_dict(), allow_nan=False))
    assert serialized["units_note"] == expected_note
    restored = RenderedStatement.from_dict(serialized)
    assert restored.to_dict() == serialized
    assert restored.units_note == expected_note
    if not expected_note:
        return
    plain = expected_note.removeprefix("[italic]").removesuffix("[/italic]")
    for detail in ("standard", "full"):
        for optimize in (False, True):
            assert plain in rendered.to_markdown(detail=detail, optimize_for_llm=optimize)
            assert plain in restored.to_markdown(detail=detail, optimize_for_llm=optimize)
    output = io.StringIO()
    panel = rendered.__rich__()
    # The default panel fits the table and can crop its subtitle even when
    # the console is wide. Give this caption-export check a fixed wide panel.
    panel.width = 400
    panel.expand = True
    Console(file=output, width=400).print(panel)
    assert plain in output.getvalue()


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "scale,scale_name,raw_value,formatted",
    [
        pytest.param(-6, "millions", 276_000_000, "276", id="intu-0000896878-26-000037"),
        pytest.param(-6, "millions", 2_860_000_000, "2,860", id="orcl-0001193125-26-277521"),
        pytest.param(-3, "thousands", 250_576_000, "250,576", id="crwd-0001535527-26-000010"),
    ],
)
def test_reported_share_values_get_the_correct_caption(scale, scale_name, raw_value, formatted, standard):
    rendered = _render(scale, scale, raw_value, standard=standard)
    _assert_values(rendered, BASIC, raw_value, formatted)
    _assert_eps(rendered)
    _assert_caption_exports(rendered, f"[italic](In {scale_name}, except per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("statement_type", ["BalanceSheet", "IncomeStatement", "CashFlowStatement"])
@pytest.mark.parametrize("concept", EXPECTED_SHARE_CONCEPTS)
@pytest.mark.parametrize("scale,scale_name", SCALES)
def test_equal_share_and_money_scales_share_the_caption(scale, scale_name, concept, statement_type, standard):
    raw_value = 276 * 10 ** (-scale)
    rendered = _render(scale, scale, raw_value, standard=standard, statement_type=statement_type, concept=concept)
    assert rendered.header.metadata["dominant_scale"] == scale
    assert rendered.header.metadata["shares_scale"] == scale
    _assert_values(rendered, concept, raw_value, "276")
    _assert_eps(rendered)
    assert rendered.units_note == f"[italic](In {scale_name}, except per share data)[/italic]"


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "money_scale,money_name,share_scale,share_name",
    [
        (-3, "thousands", -6, "millions"),
        (-3, "thousands", -9, "billions"),
        (-6, "millions", -3, "thousands"),
        (-6, "millions", -9, "billions"),
        (-9, "billions", -3, "thousands"),
        (-9, "billions", -6, "millions"),
        (-6, "millions", -4, "units of 10,000"),
        (-6, "millions", -5, "units of 100,000"),
        (-6, "millions", -7, "units of 10,000,000"),
    ],
)
def test_different_share_scale_keeps_its_explicit_exception(money_scale, money_name, share_scale, share_name, standard):
    raw_value = 276 * 10 ** (-share_scale)
    rendered = _render(money_scale, share_scale, raw_value, standard=standard)
    _assert_values(rendered, BASIC, raw_value, "276")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, f"[italic](In {money_name}, except shares in {share_name} and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "decimals,shares_scale,exception",
    [
        pytest.param(0, 0, "shares in actual amounts and per share data", id="unscaled"),
        pytest.param("INF", 0, "shares in actual amounts and per share data", id="exact-inf"),
        pytest.param(None, 0, "shares in actual amounts and per share data", id="none-in-decimals-map"),
        pytest.param(-1, 0, "shares in actual amounts and per share data", id="tens-precision-unscaled"),
        pytest.param(-2, 0, "shares in actual amounts and per share data", id="hundreds-precision-unscaled"),
        pytest.param(2, 0, "shares in actual amounts and per share data", id="positive-precision"),
        pytest.param(MISSING, 0, "shares in actual amounts and per share data", id="missing-decimals"),
    ],
)
def test_raw_share_counts_get_explicit_actual_units(decimals, shares_scale, exception, standard):
    rendered = _render(-6, decimals, 38_818_536, standard=standard)
    assert rendered.header.metadata["shares_scale"] == shares_scale
    _assert_values(rendered, BASIC, 38_818_536, "38,818,536")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, f"[italic](In millions, except {exception})[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("scale,scale_name", SCALES)
def test_no_share_rows_keep_the_default_caption(scale, scale_name, standard):
    rendered = _render(scale, MISSING, standard=standard, include_share=False)
    assert rendered.header.metadata["shares_scale"] is None
    _assert_eps(rendered)
    _assert_caption_exports(rendered, f"[italic](In {scale_name}, except shares and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("statement_type", ["", "http://example.test/role/IncomeStatement", "Notes", "StatementOfEquity"])
def test_nonmonetary_types_keep_an_empty_caption(statement_type, standard):
    rendered = _render(-6, -6, standard=standard, statement_type=statement_type)
    _assert_values(rendered, BASIC, 276_000_000, "276")
    _assert_caption_exports(rendered, "")


@pytest.mark.parametrize("standard", [False, True])
def test_unscaled_money_keeps_an_empty_caption(standard):
    rendered = _render(0, 0, standard=standard)
    assert rendered.header.metadata["dominant_scale"] == 0
    _assert_values(rendered, BASIC, 276_000_000, "276,000,000")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "")


def _share_item(concept, values, decimals, **extra):
    return {
        "label": "Share count",
        "concept": concept,
        "level": 0,
        "has_values": True,
        "is_abstract": False,
        "is_total": False,
        "values": values,
        "decimals": decimals,
        **extra,
    }


def _render_custom_shares(shares, *, standard=False, statement_type="IncomeStatement", periods=PERIODS):
    items = [_item("Revenue", MONEY, 123_000_000, -6), *shares]
    items.extend(_item("Per share data", name, 1.25, 2) for name in EXPECTED_EPS_CONCEPTS)
    return render_statement(items, periods, "Share scale controls", statement_type, standard=standard)


def _assert_custom_share_cells(rendered, concept, raw_values, formatted):
    row = _row(rendered, concept)
    assert [cell.value for cell in row.cells] == raw_values
    assert [cell.get_formatted_value() for cell in row.cells] == formatted
    for presentation in (False, True):
        frame = rendered.to_dataframe(presentation=presentation)
        selected = frame.loc[frame["concept"].eq(concept)]
        for period, raw in zip(rendered.header.periods, raw_values, strict=True):
            assert selected[period.end_date].tolist() == [raw]


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("reverse_periods", [False, True])
def test_mixed_period_precisions_use_the_finest_share_unit(standard, reverse_periods):
    # Synthetic: neither period is made coarser than its former display.
    shares = [_share_item(concept, {CURRENT: 276_000_000, PREVIOUS: 280_000_000}, {CURRENT: -6, PREVIOUS: -3}) for concept in EXPECTED_SHARE_CONCEPTS]
    periods = list(reversed(PERIODS)) if reverse_periods else PERIODS
    rendered = _render_custom_shares(shares, standard=standard, periods=periods)
    raw = [280_000_000, 276_000_000] if reverse_periods else [276_000_000, 280_000_000]
    formatted = ["280,000", "276,000"] if reverse_periods else ["276,000", "280,000"]
    assert rendered.header.metadata["shares_scale"] == -3
    for concept in EXPECTED_SHARE_CONCEPTS:
        _assert_custom_share_cells(rendered, concept, raw, formatted)
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except shares in thousands and per share data)[/italic]")
    # This round trip only reads the object serialized in this expression.
    assert pickle.loads(pickle.dumps(rendered)).to_dict() == rendered.to_dict()  # noqa: S301


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "statement_type", ["BalanceSheet", "IncomeStatement", "CashFlowStatement", "", "http://example.test/role/IncomeStatement", "StatementOfEquity"]
)
@pytest.mark.parametrize("reverse_rows", [False, True])
def test_basic_and_diluted_share_units_agree(standard, statement_type, reverse_rows):
    shares = [
        _share_item(BASIC, {CURRENT: 276_000_000, PREVIOUS: -276_000_000}, {CURRENT: -6, PREVIOUS: -6}),
        _share_item(DILUTED, {CURRENT: 277_000_000, PREVIOUS: -277_000_000}, {CURRENT: -3, PREVIOUS: -3}),
    ]
    rendered = _render_custom_shares(list(reversed(shares)) if reverse_rows else shares, standard=standard, statement_type=statement_type)
    assert rendered.header.metadata["shares_scale"] == -3
    _assert_custom_share_cells(rendered, BASIC, [276_000_000, -276_000_000], ["276,000", "-276,000"])
    _assert_custom_share_cells(rendered, DILUTED, [277_000_000, -277_000_000], ["277,000", "-277,000"])
    _assert_eps(rendered)
    note = (
        "[italic](In millions, except shares in thousands and per share data)[/italic]"
        if statement_type in ("BalanceSheet", "IncomeStatement", "CashFlowStatement")
        else ""
    )
    _assert_caption_exports(rendered, note)


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "decimals",
    [
        pytest.param("INF", id="exact"),
        pytest.param(0, id="raw"),
        pytest.param(-1, id="tens"),
        pytest.param(-2, id="hundreds"),
        pytest.param(2, id="positive"),
        pytest.param(None, id="absent-precision"),
        pytest.param(MISSING, id="missing-map-key"),
        pytest.param(True, id="boolean-precision"),
        pytest.param(-6.0, id="float-precision"),
        pytest.param("-6", id="unnormalized-string-precision"),
        pytest.param("invalid", id="unsupported-precision"),
    ],
)
def test_raw_or_unsupported_precision_keeps_all_share_cells_unscaled(decimals, standard):
    raw_decimals = {} if decimals is MISSING else {CURRENT: decimals, PREVIOUS: decimals}
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: 276_000_000, PREVIOUS: -276_000_000}, {CURRENT: -6, PREVIOUS: -6}),
            _share_item(DILUTED, {CURRENT: 38_818_536, PREVIOUS: -38_818_536}, raw_decimals),
        ],
        standard=standard,
    )
    assert rendered.header.metadata["shares_scale"] == 0
    _assert_custom_share_cells(rendered, BASIC, [276_000_000, -276_000_000], ["276,000,000", "-276,000,000"])
    _assert_custom_share_cells(rendered, DILUTED, [38_818_536, -38_818_536], ["38,818,536", "-38,818,536"])
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except shares in actual amounts and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "first_decimals,second_decimals,raw,formatted,scale,note_unit",
    [
        pytest.param(-12, -9, 276_000_000_000_000, "276,000", -9, "billions", id="trillions-and-billions"),
        pytest.param(-7, -4, 2_760_000_000, "276,000", -4, "units of 10,000", id="generic-factors"),
        pytest.param(-12, -12, 276_000_000_000_000, "276", -12, "units of 1,000,000,000,000", id="homogeneous-trillions"),
    ],
)
def test_generic_negative_precisions_keep_their_exact_scale(first_decimals, second_decimals, raw, formatted, scale, note_unit, standard):
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: raw, PREVIOUS: -raw}, {CURRENT: first_decimals, PREVIOUS: second_decimals}),
        ],
        standard=standard,
    )
    assert rendered.header.metadata["shares_scale"] == scale
    _assert_custom_share_cells(rendered, BASIC, [raw, -raw], [formatted, f"-{formatted}"])
    _assert_eps(rendered)
    _assert_caption_exports(rendered, f"[italic](In millions, except shares in {note_unit} and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(0, "", id="zero-int"),
        pytest.param(0.0, "", id="zero-float"),
        pytest.param(-0.0, "", id="negative-zero"),
        pytest.param(None, "", id="none"),
        pytest.param("", "", id="empty-string"),
        pytest.param("276000000", "276000000", id="numeric-string"),
        pytest.param("not applicable", "not applicable", id="text"),
        pytest.param(True, "", id="boolean"),
    ],
)
def test_blank_and_non_numeric_share_cells_do_not_choose_units(value, expected, standard):
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: value, PREVIOUS: value}, {CURRENT: "INF", PREVIOUS: "INF"}),
            _share_item(DILUTED, {CURRENT: 277_000_000, PREVIOUS: -277_000_000}, {CURRENT: -6, PREVIOUS: -6}),
        ],
        standard=standard,
    )
    assert rendered.header.metadata["shares_scale"] == -6
    row = _row(rendered, BASIC)
    assert [cell.value for cell in row.cells] == [value, value]
    assert [cell.get_formatted_value() for cell in row.cells] == [expected, expected]
    _assert_values(rendered, DILUTED, 277_000_000, "277")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except per share data)[/italic]")


@pytest.mark.parametrize("value,formatted", [(float("inf"), "inf"), (float("-inf"), "-inf"), (float("nan"), "nan")])
def test_nonfinite_share_placeholders_do_not_choose_units(value, formatted):
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: value, PREVIOUS: value}, {CURRENT: "INF", PREVIOUS: "INF"}),
            _share_item(DILUTED, {CURRENT: 277_000_000, PREVIOUS: -277_000_000}, {CURRENT: -6, PREVIOUS: -6}),
        ]
    )
    assert rendered.header.metadata["shares_scale"] == -6
    row = _row(rendered, BASIC)
    assert all(not math.isfinite(cell.value) for cell in row.cells)
    assert [cell.get_formatted_value() for cell in row.cells] == [formatted, formatted]
    _assert_values(rendered, DILUTED, 277_000_000, "277")
    _assert_eps(rendered)
    assert rendered.units_note == "[italic](In millions, except per share data)[/italic]"
    # Existing nonfinite raw-cell JSON behavior is outside this caption fix.


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("value", [0, "", None])
def test_no_displayed_share_quantities_keep_the_default_caption(value, standard):
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: value, PREVIOUS: value}, {CURRENT: "INF", PREVIOUS: "INF"}),
        ],
        standard=standard,
    )
    assert rendered.header.metadata["shares_scale"] is None
    assert [cell.get_formatted_value() for cell in _row(rendered, BASIC).cells] == ["", ""]
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except shares and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
def test_finer_common_scale_keeps_digits_instead_of_adding_rounding(standard):
    rendered = _render_custom_shares(
        [
            _share_item(BASIC, {CURRENT: 276_500_000, PREVIOUS: -276_500_000}, {CURRENT: -6, PREVIOUS: -6}),
            _share_item(DILUTED, {CURRENT: 277_001_000, PREVIOUS: -277_001_000}, {CURRENT: -3, PREVIOUS: -3}),
        ],
        standard=standard,
    )
    assert rendered.header.metadata["shares_scale"] == -3
    _assert_custom_share_cells(rendered, BASIC, [276_500_000, -276_500_000], ["276,500", "-276,500"])
    _assert_custom_share_cells(rendered, DILUTED, [277_001_000, -277_001_000], ["277,001", "-277,001"])
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except shares in thousands and per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
def test_only_displayed_periods_and_rows_choose_the_share_scale(standard):
    undisplayed = "duration_2023-08-01_2024-07-31"
    filtered = _share_item(DILUTED, {CURRENT: 277_000_000}, {CURRENT: "INF"}, label="Shares [Axis]")
    rendered = _render_custom_shares(
        [
            _share_item(
                BASIC, {CURRENT: 276_000_000, PREVIOUS: -276_000_000, undisplayed: 280_000_000}, {CURRENT: -6, PREVIOUS: -6, undisplayed: "INF"}
            ),
            filtered,
            _share_item("us-gaap_CommonStockSharesIssued", {}, {CURRENT: "INF", PREVIOUS: "INF"}),
        ],
        standard=standard,
    )
    assert not any(row.metadata.get("concept") == DILUTED for row in rendered.rows)
    assert rendered.header.metadata["shares_scale"] == -6
    _assert_values(rendered, BASIC, 276_000_000, "276")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except per share data)[/italic]")


@pytest.mark.parametrize("standard", [False, True])
@pytest.mark.parametrize("statement_type", ["CashFlowStatement", "StatementOfEquity"])
def test_populated_instant_fallback_uses_the_displayed_cell_precision(standard, statement_type):
    # The formatter receives the displayed duration key, where this instant
    # row has no filed decimals. Its existing unscaled display must stay raw.
    fallback = _share_item(
        BASIC,
        {"instant_2026-07-31": 276_000_000, "instant_2025-07-31": 280_000_000},
        {"instant_2026-07-31": -6, "instant_2025-07-31": -6},
        preferred_label=PERIOD_END_LABEL,
    )
    rendered = _render_custom_shares(
        [
            fallback,
            _share_item(DILUTED, {CURRENT: 277_000_000, PREVIOUS: -277_000_000}, {CURRENT: -6, PREVIOUS: -6}),
        ],
        standard=standard,
        statement_type=statement_type,
    )
    assert rendered.header.metadata["shares_scale"] == 0
    # Equity's existing first-occurrence fallback prefers beginning balances;
    # leave that mapping unchanged while inspecting the actual displayed cells.
    raw = [280_000_000, 280_000_000] if statement_type == "StatementOfEquity" else [276_000_000, 280_000_000]
    formatted = ["280,000,000", "280,000,000"] if statement_type == "StatementOfEquity" else ["276,000,000", "280,000,000"]
    _assert_custom_share_cells(rendered, BASIC, raw, formatted)
    _assert_custom_share_cells(rendered, DILUTED, [277_000_000, -277_000_000], ["277,000,000", "-277,000,000"])
    _assert_eps(rendered)
    note = "[italic](In millions, except shares in actual amounts and per share data)[/italic]" if statement_type == "CashFlowStatement" else ""
    _assert_caption_exports(rendered, note)


@pytest.mark.parametrize("standard", [False, True])
def test_unrecognized_share_concepts_and_unit_names_keep_existing_formatting(standard):
    custom = _share_item(
        "company_CustomShareCount",
        {CURRENT: 276_000_000, PREVIOUS: -276_000_000},
        {CURRENT: -6, PREVIOUS: -6},
        units={CURRENT: "shares", PREVIOUS: "shares"},
    )
    recognized = _share_item(BASIC, {CURRENT: 277_000_000, PREVIOUS: -277_000_000}, {CURRENT: -6, PREVIOUS: -6})
    rendered = _render_custom_shares([custom, recognized], standard=standard)
    assert rendered.header.metadata["shares_scale"] == -6
    row = _row(rendered, "company_CustomShareCount")
    assert [cell.value for cell in row.cells] == [276_000_000, -276_000_000]
    assert [cell.get_formatted_value() for cell in row.cells] == ["$276", "$(276)"]
    _assert_values(rendered, BASIC, 277_000_000, "277")
    _assert_eps(rendered)
    _assert_caption_exports(rendered, "[italic](In millions, except per share data)[/italic]")


def test_recognized_share_and_per_share_domains_remain_explicit():
    assert share_concepts == list(EXPECTED_SHARE_CONCEPTS)
    assert eps_concepts == list(EXPECTED_EPS_CONCEPTS)
