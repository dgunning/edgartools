"""
EntityFacts statements show a pure-unit percentage row as a percentage.

``FinancialStatement.format_value`` picks the percentage format from the row label
('percent', 'margin') and appended '%' to the raw value, so Apple's effective tax rate,
filed as the pure ratio 0.156, displayed as ``0.2%``. The label alone cannot decide the
scaling, because Apple captions its dollar gross profit "Gross margin". The pivot now
records each row's unit and only a pure ratio is multiplied by 100.

Ground truth: Apple Inc. (CIK 320193) 10-K 0000320193-25-000079, fiscal year
2024-09-29 .. 2025-09-27, from SEC company facts:

    us-gaap:EffectiveIncomeTaxRateContinuingOperations   0.156 pure  (15.6% in the filing)
    us-gaap:GrossProfit                         195,201,000,000 USD  ("Gross margin")

GitHub Issue: https://github.com/dgunning/edgartools/issues/1850
"""

import pytest

from edgar.entity.parser import EntityFactsParser

TAX_RATE_LABEL = "Effective Income Tax Rate Reconciliation, Percent"


def _row(val):
    return {"start": "2024-09-29", "end": "2025-09-27", "val": val,
            "accn": "0000320193-25-000079", "fy": 2025, "fp": "FY",
            "form": "10-K", "filed": "2025-10-31", "frame": "CY2025"}


def _statement(concept, label, unit, val):
    payload = {"cik": 320193, "entityName": "Apple Inc.",
               "facts": {"us-gaap": {concept: {"label": label, "units": {unit: [_row(val)]}}}}}
    return EntityFactsParser.parse_company_facts(payload).query().pivot_by_period()


@pytest.mark.fast
def test_pure_ratio_percentage_is_scaled_to_percent():
    statement = _statement("EffectiveIncomeTaxRateContinuingOperations", TAX_RATE_LABEL, "pure", 0.156)

    values = statement.to_llm_context()["line_items"][TAX_RATE_LABEL]["values"]["FY 2025"]
    assert values["raw_value"] == 0.156
    assert values["formatted_value"] == "15.6%"
    assert "15.6%" in str(statement)
    assert "15.6%" in statement._repr_html_()


@pytest.mark.fast
def test_dollar_row_labelled_margin_is_not_scaled():
    statement = _statement("GrossProfit", "Gross margin", "USD", 195_201_000_000)

    assert statement.format_value(195_201_000_000, "Gross margin") == "195201000000.0%"
