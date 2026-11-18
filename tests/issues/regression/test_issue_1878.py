"""Verify liability reconstruction against the face of four SEC balance sheets.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1878
"""

from types import SimpleNamespace

import pandas as pd
import pytest

from edgar.financials import Financials, LiabilityDerivationError
from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.models import CalculationArc, CalculationTree
from edgar.xbrl.rendering import PeriodData

AMAZON = (1018724, "0001018724-26-000026", "amzn-20260630")
NIKE = (320187, "0000320187-26-000088", "nke-20260531")
DISNEY = (1744489, "0001744489-24-000276", "dis-20240928")
JPMORGAN = (19617, "0001628280-26-008131", "jpm-20251231")


@pytest.fixture(scope="module")
def financials_for(tmp_path_factory):
    cache = {}

    def load(spec):
        if spec not in cache:
            cik, accession, stem = spec
            folder = tmp_path_factory.mktemp(stem)
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
            for suffix in (".xsd", "_pre.xml", "_cal.xml", "_lab.xml", "_htm.xml"):
                name = stem + suffix
                (folder / name).write_text(download_file(f"{url}/{name}", as_text=True), encoding="utf-8")
            cache[spec] = Financials(XBRL.from_directory(folder), accession=accession)
        return cache[spec]

    return load


@pytest.mark.network
@pytest.mark.parametrize(
    "filing,offset,date,components,assets,equity,temporary",
    [
        # Each component is a separate line in the primary statement, in USD millions.
        (AMAZON, 0, "2026-06-30", (241_274, 128_894, 79_563, 94_338), 1_095_689, 551_620, None),
        (NIKE, 0, "2026-05-31", (12_547, 5_942, 2_443, 2_613), 38_410, 14_865, 0),
        (DISNEY, 0, "2024-09-28", (34_599, 38_970, 6_277, 10_851), 196_219, 105_522, 0),
        (DISNEY, 1, "2023-09-30", (31_139, 42_101, 7_258, 12_069), 205_579, 103_957, 9_055),
    ],
)
def test_reconcile_original_balance_sheet(financials_for, filing, offset, date, components, assets, equity, temporary):
    financials = financials_for(filing)
    result = financials.derive_total_liabilities(offset)
    assert (result.period, result.currency, result.accession) == (date, "USD", filing[1])
    assert result.value == result.component_total == result.identity_total == sum(components) * 1_000_000
    assert sorted(item.value for item in result.components) == sorted(
        value * 1_000_000 for value in components
    )
    expected_inputs = [assets, -equity]
    if temporary is not None:
        expected_inputs.append(-temporary)
    assert [item.value * item.weight for item in result.identity_inputs] == [
        value * 1_000_000 for value in expected_inputs
    ]
    if filing == DISNEY:
        # Consolidated equity includes regular NCI (4,826 / 4,680); the
        # redeemable NCI is a separate line (0 / 9,055).
        assert result.identity_inputs[1].concept.endswith("IncludingPortionAttributableToNoncontrollingInterest")
        assert result.identity_inputs[2].concept.endswith("RedeemableNoncontrollingInterestEquityCarryingAmount")
    assert financials.get_total_liabilities(offset) is None
    assert financials.get_financial_metrics()["debt_to_assets"] is None


@pytest.mark.network
def test_filed_total_and_ratio_still_work(financials_for):
    financials = financials_for(JPMORGAN)
    assert financials.get_total_liabilities() == 4_062_462_000_000
    assert financials.get_financial_metrics()["debt_to_assets"] == pytest.approx(4_062_462 / 4_424_900)
    with pytest.raises(LiabilityDerivationError, match="already-reported") as error:
        financials.derive_total_liabilities()
    assert error.value.reason == "already-reported"


@pytest.mark.fast
@pytest.mark.parametrize("reason", [
    "missing-component",
    "overlapping-components",
    "cross-check-mismatch",
    "ambiguous-noncontrolling-interest",
])
def test_refuses_incomplete_calculation(monkeypatch, reason):
    combined = "us-gaap_LiabilitiesAndStockholdersEquity"
    current = "us-gaap_LiabilitiesCurrent"
    payable = "us-gaap_AccountsPayableCurrent"
    period = "2026-06-30"
    key = f"instant_{period}"
    arcs = [CalculationArc(parent_id=combined, child_id=current)]
    rows = []
    if reason == "overlapping-components":
        arcs += [
            CalculationArc(parent_id=current, child_id=payable),
            CalculationArc(parent_id=combined, child_id=payable),
        ]
        rows = [{"concept": current, "balance": "credit", "label": "Current liabilities",
                 "values": {key: 100}, "units": {key: "usd"}}]
    if reason in ("cross-check-mismatch", "ambiguous-noncontrolling-interest"):
        equity = "us-gaap_StockholdersEquity"
        arcs.append(CalculationArc(parent_id=combined, child_id=equity))
        amounts = [
            ("us-gaap_Assets", 200), (current, 90), (equity, 100), (combined, 200),
        ]
        if reason == "ambiguous-noncontrolling-interest":
            amounts.insert(-1, ("us-gaap_MinorityInterest", 10))
        rows = [
            {"concept": concept, "balance": "credit", "label": concept,
             "values": {key: amount}, "units": {key: "usd"}}
            for concept, amount in amounts
        ]
    tree = CalculationTree(role_uri="balance", definition="", root_element_id=combined, all_arcs=arcs)
    xb = SimpleNamespace(
        calculation_trees={"balance": tree},
        get_statement=lambda *args, **kwargs: rows,
        find_statement=lambda _: ([], "balance", "BalanceSheet"),
        _currency_measure=lambda _: "iso4217:USD",
    )
    financials = Financials(xb)
    rendered = SimpleNamespace(periods=[PeriodData(key=key, label=period, end_date=period)])
    monkeypatch.setattr(financials, "_derivation_balance_sheet",
                        lambda: ("balance", rendered, pd.DataFrame(columns=[period])))
    monkeypatch.setattr(financials, "get_total_liabilities", lambda _: None)
    with pytest.raises(LiabilityDerivationError) as error:
        financials.derive_total_liabilities()
    assert error.value.reason == reason


@pytest.fixture
def derivation_statement():
    """Synthetic boundary cases; real filing amounts are tested above."""
    period = "2026-06-30"
    key = f"instant_{period}"
    combined = "us-gaap_LiabilitiesAndStockholdersEquity"
    current = "us-gaap_LiabilitiesCurrent"
    equity = "us-gaap_StockholdersEquity"
    rows = [
        {"concept": concept, "label": concept, "balance": "credit",
         "values": {key: amount}, "units": {key: "usd"}}
        for concept, amount in [("us-gaap_Assets", 200), (current, 90), (equity, 110), (combined, 200)]
    ]
    arcs = [CalculationArc(parent_id=combined, child_id=concept) for concept in (current, equity)]
    role = "http://example.com/role/SelectedBalanceSheet"
    tree = CalculationTree(role_uri=role, definition="", root_element_id=combined, all_arcs=arcs)
    xb = SimpleNamespace(calculation_trees={role: tree},
                         get_statement=lambda *args, **kwargs: rows,
                         _currency_measure=lambda _: "iso4217:USD")
    return xb, role, period, rows, tree


@pytest.mark.fast
@pytest.mark.parametrize("value", [None, "", 0, 0.0, "0.00", "0E-6", 1, "invalid"])
def test_commitments_missing_or_zero_only(derivation_statement, value):
    from edgar._liability_derivation import derive_from_balance_sheet

    xb, role, period, rows, tree = derivation_statement
    concept = "us-gaap_CommitmentsAndContingencies"
    rows.insert(-1, {"concept": concept, "values": {f"instant_{period}": value}})
    tree.all_arcs.append(CalculationArc(parent_id="us-gaap_LiabilitiesAndStockholdersEquity", child_id=concept))
    if value in (1, "invalid"):
        with pytest.raises(LiabilityDerivationError, match="unclassified-component"):
            derive_from_balance_sheet(xb, role, period, None)
    else:
        assert derive_from_balance_sheet(xb, role, period, None).value == 90


@pytest.mark.fast
@pytest.mark.parametrize("current_value", [None, "", 0, 10])
def test_nci_checks_selected_period(derivation_statement, current_value):
    from edgar._liability_derivation import derive_from_balance_sheet

    xb, role, period, rows, _ = derivation_statement
    rows.insert(-1, {"concept": "us-gaap_MinorityInterest", "values": {
        "instant_2025-06-30": 10, f"instant_{period}": current_value,
    }})
    if current_value in (None, ""):
        assert derive_from_balance_sheet(xb, role, period, None).value == 90
    else:
        with pytest.raises(LiabilityDerivationError, match="ambiguous-noncontrolling-interest"):
            derive_from_balance_sheet(xb, role, period, None)


@pytest.mark.fast
@pytest.mark.parametrize("filed_total", [None, 90])
def test_selected_role_and_frame_reused(monkeypatch, derivation_statement, filed_total):
    from unittest.mock import Mock

    xb, role, period, _, _ = derivation_statement
    # The generic resolver deliberately selects another role: it must not be used.
    xb.find_statement = Mock(return_value=([], "http://example.com/OtherBalance", "BalanceSheet"))
    frame = pd.DataFrame({"concept": ["us-gaap_Liabilities" if filed_total else "us-gaap_Assets"],
                          "label": ["Total Liabilities" if filed_total else "Assets"],
                          period: [filed_total if filed_total else 200]})
    rendered = SimpleNamespace(periods=[PeriodData(key=f"instant_{period}", label=period, end_date=period)],
                               to_dataframe=Mock(return_value=frame))
    xb.render_statement = Mock(return_value=rendered)
    financials = Financials(xb)
    monkeypatch.setattr(financials, "balance_sheet", lambda: SimpleNamespace(role_or_type=role))
    previous_memo = {"income": (None, None)}
    financials._statement_frame_memo = previous_memo
    if filed_total is not None:
        with pytest.raises(LiabilityDerivationError, match="already-reported"):
            financials.derive_total_liabilities()
    else:
        assert financials.derive_total_liabilities().value == 90
    xb.find_statement.assert_not_called()
    xb.render_statement.assert_called_once_with(role, standard=True)
    rendered.to_dataframe.assert_called_once_with(presentation=False)
    assert financials._statement_frame_memo is previous_memo


@pytest.mark.fast
@pytest.mark.parametrize("stage", ["lookup", "render", "dataframe"])
def test_render_errors_use_public_exception(monkeypatch, derivation_statement, stage):
    from unittest.mock import Mock

    xb, role, _, _, _ = derivation_statement
    original = RuntimeError("broken render input")
    financials = Financials(xb)
    lookup = Mock(return_value=SimpleNamespace(role_or_type=role))
    rendered = SimpleNamespace(to_dataframe=Mock(return_value=pd.DataFrame()))
    xb.render_statement = Mock(return_value=rendered)
    {"lookup": lookup, "render": xb.render_statement, "dataframe": rendered.to_dataframe}[stage].side_effect = original
    monkeypatch.setattr(financials, "balance_sheet", lookup)
    with pytest.raises(LiabilityDerivationError) as error:
        financials.derive_total_liabilities()
    assert error.value.reason == "render-failed"
    assert error.value.__cause__ is original
