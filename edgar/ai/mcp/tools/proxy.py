"""
Proxy Tool

Get executive compensation, pay vs performance, and governance data from DEF 14A proxy statements.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
    get_error_suggestions,
    classify_error,
)

logger = logging.getLogger(__name__)


def _decimal_to_float(value) -> Optional[float]:
    """Convert Decimal/numeric to float, handling None and NaN."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _df_to_records(df: pd.DataFrame, limit: int, columns: Optional[list[str]] = None) -> list[dict]:
    """DataFrame to list of dicts. Selects columns, caps rows, converts Decimal→float, NaN→None."""
    if df is None or df.empty:
        return []

    if columns:
        columns = [c for c in columns if c in df.columns]
        if columns:
            df = df[columns]

    records = []
    for _, row in df.head(limit).iterrows():
        record = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                record[k] = float(v)
            elif isinstance(v, float) and math.isnan(v):
                record[k] = None
            elif pd.isna(v):
                record[k] = None
            else:
                record[k] = v
        records.append(record)
    return records


@tool(
    name="edgar_proxy",
    description="""Use this for CEO compensation, executive pay, and corporate governance questions. Extracts compensation tables, pay-vs-performance metrics, and governance data from DEF 14A proxy statements.

Examples:
- CEO pay: identifier="AAPL"
- Compare pay: identifier="MSFT"
- Prior year: identifier="AAPL", filing_index=1""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker, CIK, or name"
        },
        "filing_index": {
            "type": "integer",
            "description": "Which proxy filing to use (0=latest, 1=previous, etc.)",
            "default": 0
        },
    },
    required=["identifier"]
)
async def edgar_proxy(
    identifier: str,
    filing_index: int = 0,
) -> Any:
    """Get proxy statement executive compensation and governance data."""
    try:
        company = resolve_company(identifier)

        # Get proxy filings — try DEF 14A first, then contested (DEFC14A) if none found
        filings = company.get_filings(form="DEF 14A")
        if filings is None or len(filings) == 0:
            filings = company.get_filings(form=["DEFC14A", "DEFN14A"])
        if filings is None or len(filings) == 0:
            return error(
                f"No proxy filings found for '{identifier}'",
                suggestions=[
                    "This company may not file proxy statements (e.g., foreign private issuers use 20-F)",
                    "Try edgar_read with form='DEF 14A' to search more broadly",
                    "Use edgar_company to verify the company identifier",
                ],
                error_code="NO_FILINGS"
            )

        # Validate filing_index
        filing_index = max(0, filing_index)
        if filing_index >= len(filings):
            return error(
                f"Only {len(filings)} proxy filings available, but index {filing_index} requested",
                suggestions=[f"Use filing_index between 0 and {len(filings) - 1}"],
                error_code="INVALID_ARGUMENTS"
            )

        filing = filings[filing_index]
        proxy = filing.obj()

        if proxy is None:
            return error(
                f"Could not parse proxy statement for '{identifier}' (filing {filing.accession_no})",
                suggestions=[
                    "The filing may not be parseable as a proxy statement",
                    "Use edgar_read with form='DEF 14A' to read the raw filing text",
                ],
                error_code="PARSE_ERROR"
            )

        # Build base result
        result: dict[str, Any] = {
            "company": proxy.company_name or company.name,
            "cik": proxy.cik,
            "form": proxy.form,
            "filing_date": proxy.filing_date,
            "fiscal_year_end": proxy.fiscal_year_end,
            "has_xbrl": proxy.has_xbrl,
        }

        # If no XBRL, return partial result with note
        if not proxy.has_xbrl:
            result["note"] = (
                "No XBRL data available. Executive compensation data requires XBRL "
                "(not available for smaller reporting companies, emerging growth companies, "
                "SPACs, or registered investment companies)."
            )
            return success(result, next_steps=[
                "Use edgar_read to read the proxy statement text directly",
                "Try a different company that is a large accelerated filer",
            ])

        # CEO compensation
        if proxy.peo_name is not None or proxy.peo_total_comp is not None:
            result["ceo"] = {
                "name": proxy.peo_name,
                "total_comp": _decimal_to_float(proxy.peo_total_comp),
                "actually_paid": _decimal_to_float(proxy.peo_actually_paid_comp),
            }

        # NEO average compensation
        if proxy.neo_avg_total_comp is not None or proxy.neo_avg_actually_paid_comp is not None:
            result["neo_average"] = {
                "total_comp": _decimal_to_float(proxy.neo_avg_total_comp),
                "actually_paid": _decimal_to_float(proxy.neo_avg_actually_paid_comp),
            }

        # Pay vs performance metrics
        pvp: dict[str, Any] = {}
        if proxy.total_shareholder_return is not None:
            pvp["company_tsr"] = _decimal_to_float(proxy.total_shareholder_return)
        if proxy.peer_group_tsr is not None:
            pvp["peer_tsr"] = _decimal_to_float(proxy.peer_group_tsr)
        if proxy.net_income is not None:
            pvp["net_income"] = _decimal_to_float(proxy.net_income)
        if proxy.company_selected_measure:
            pvp["company_measure"] = proxy.company_selected_measure
        if proxy.company_selected_measure_value is not None:
            pvp["company_measure_value"] = _decimal_to_float(proxy.company_selected_measure_value)
        if pvp:
            result["pay_vs_performance"] = pvp

        # Governance and award timing
        governance: dict[str, Any] = {}
        if proxy.insider_trading_policy_adopted is not None:
            governance["insider_trading_policy"] = proxy.insider_trading_policy_adopted
        if proxy.award_timing_mnpi_considered is not None:
            governance["award_timing_mnpi_considered"] = proxy.award_timing_mnpi_considered
        if proxy.award_dates_predetermined is not None:
            governance["award_dates_predetermined"] = proxy.award_dates_predetermined
        if proxy.mnpi_disclosure_timed_for_comp_value is not None:
            governance["mnpi_timed_for_comp_value"] = proxy.mnpi_disclosure_timed_for_comp_value
        if governance:
            result["governance"] = governance

        # Awards close to MNPI
        awards_df = proxy.awards_close_to_mnpi
        if awards_df is not None and not awards_df.empty:
            result["awards_close_to_mnpi"] = _df_to_records(awards_df, limit=20)

        # CEO Pay Ratio
        try:
            pay_ratio = proxy.ceo_pay_ratio
            if pay_ratio and pay_ratio.ratio:
                result["ceo_pay_ratio"] = {
                    "ceo_compensation": pay_ratio.ceo_compensation,
                    "median_employee_compensation": pay_ratio.median_employee_compensation,
                    "ratio": pay_ratio.ratio,
                }
        except Exception:
            pass

        # Performance measures
        if proxy.performance_measures:
            result["performance_measures"] = proxy.performance_measures

        # Summary Compensation Table (per-NEO, from HTML)
        try:
            sct_df = proxy.summary_compensation_table
            if sct_df is not None and not sct_df.empty:
                result["summary_compensation_table"] = _df_to_records(sct_df, limit=30)
        except Exception:
            pass

        # Beneficial Ownership (from HTML)
        try:
            own_df = proxy.beneficial_ownership
            if own_df is not None and not own_df.empty:
                result["beneficial_ownership"] = _df_to_records(own_df, limit=30)
        except Exception:
            pass

        # Director Compensation (from HTML)
        try:
            dir_df = proxy.director_compensation_table
            if dir_df is not None and not dir_df.empty:
                result["director_compensation"] = _df_to_records(dir_df, limit=20)
        except Exception:
            pass

        # Compensation history (multi-year DataFrame, from XBRL)
        comp_df = proxy.executive_compensation
        if comp_df is not None and not comp_df.empty:
            result["compensation_history"] = _df_to_records(comp_df, limit=10)

        # Named executives (if dimensional data available)
        if proxy.has_individual_executive_data:
            neos = proxy.named_executives
            if neos:
                result["named_executives"] = [
                    {
                        "name": neo.name,
                        "role": neo.role,
                        "member_id": neo.member_id,
                        "fiscal_year_end": neo.fiscal_year_end,
                    }
                    for neo in neos[:20]
                ]

        next_steps = [
            "Use edgar_company for full company profile and financials",
            "Use edgar_read with form='DEF 14A' to read proxy statement text",
            "Use edgar_compare to compare executive compensation across companies",
        ]

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_proxy")
        classified = classify_error(e)
        return error(
            classified["message"],
            suggestions=classified["suggestions"],
            error_code=classified["error_code"]
        )
