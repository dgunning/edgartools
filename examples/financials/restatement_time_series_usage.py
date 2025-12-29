"""
Comprehensive usage example for restatement-aware time series.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional

import pandas as pd

from edgar import Company, set_identity


def _require_identity(identity: Optional[str]) -> None:
    if not identity:
        print("EDGAR_IDENTITY not set.")
        print("Example: setx EDGAR_IDENTITY \"Your Name your.email@domain.com\"")
        sys.exit(1)
    set_identity(identity)


def _print_table(title: str, df: pd.DataFrame, limit: int = 10) -> None:
    print(f"\n{title}")
    if df.empty:
        print("(no results)")
        return
    print(df.head(limit).to_string(index=False))


def _restated_concepts(facts, period_type: str, statement_type: Optional[str], limit: int) -> pd.DataFrame:
    df = facts.restated_concepts(period_type=period_type, statement_type=statement_type)
    _print_table(
        f"Restated concepts ({period_type}, statement={statement_type or 'all'})",
        df[["concept", "restatement_count"]]
        if not df.empty else df,
        limit=limit
    )
    return df


def _restatement_series(facts, concept: str, period_type: str, periods: int, restated_only: bool) -> pd.DataFrame:
    series = facts.restatement_time_series(
        concept,
        periods=periods,
        period_type=period_type,
        restated_only=restated_only
    )

    _print_table(
        f"Restatement time series for {concept} ({period_type})",
        series[[
            "period_end",
            "numeric_value",
            "filing_date",
            "form_type",
            "version",
            "versions",
            "value_changed"
        ]] if not series.empty else series,
        limit=periods * 3
    )
    return series


def _compare_latest_vs_prior(series: pd.DataFrame) -> pd.DataFrame:
    if series.empty:
        return series

    series_sorted = series.sort_values(["period_end", "filing_date"])

    latest = series_sorted.groupby("period_end").tail(1).copy()
    latest = latest.rename(columns={
        "numeric_value": "latest_value",
        "filing_date": "latest_filing_date",
        "form_type": "latest_form_type"
    })

    prior = series_sorted.groupby("period_end").nth(-2).reset_index()
    prior = prior.rename(columns={
        "numeric_value": "prior_value",
        "filing_date": "prior_filing_date",
        "form_type": "prior_form_type"
    })

    comparison = latest.merge(
        prior[["period_end", "prior_value", "prior_filing_date", "prior_form_type"]],
        on="period_end",
        how="left"
    )

    comparison["delta"] = comparison["latest_value"] - comparison["prior_value"]
    comparison["delta_pct"] = comparison["delta"] / comparison["prior_value"]

    return comparison[[
        "period_end",
        "latest_value",
        "prior_value",
        "delta",
        "delta_pct",
        "latest_filing_date",
        "latest_form_type"
    ]].sort_values("period_end", ascending=False)


def _print_concept_section(facts, title: str, concepts: Iterable[str], period_type: str, periods: int) -> None:
    print(f"\n{title}")
    for concept in concepts:
        series = _restatement_series(
            facts,
            concept=concept,
            period_type=period_type,
            periods=periods,
            restated_only=True
        )
        comparison = _compare_latest_vs_prior(series)
        _print_table(f"Latest vs prior for {concept}", comparison, limit=periods)


def _recent_8k_restatements(company: Company, limit: int = 10) -> pd.DataFrame:
    filings = company.get_filings(form=["8-K", "8-K/A"], trigger_full_load=False)
    if not filings:
        return pd.DataFrame()

    latest = filings.latest(limit)
    if latest is None:
        return pd.DataFrame()

    recent_filings = list(latest) if hasattr(latest, "__iter__") else [latest]
    results = []

    for filing in recent_filings:
        try:
            report = filing.obj()
        except Exception:
            continue

        item_text = report["Item 4.02"] if report else None
        if not item_text:
            continue

        snippet = item_text.strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."

        results.append({
            "filing_date": getattr(filing, "filing_date", None),
            "form_type": getattr(filing, "form", None),
            "accession": getattr(filing, "accession_no", None),
            "item_402_snippet": snippet
        })

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restatement-aware time series demo")
    parser.add_argument("--ticker", default="BA", help="Ticker or CIK (default: BA)")
    parser.add_argument("--identity", default=os.environ.get("EDGAR_IDENTITY"), help="SEC identity string")
    parser.add_argument("--period-type", default="quarterly", choices=["quarterly", "annual"])
    parser.add_argument("--statement-type", default="IncomeStatement", help="Statement type filter")
    parser.add_argument("--concept", default=None, help="Concept to inspect (e.g., us-gaap:Revenue)")
    parser.add_argument("--concepts", default=None, help="Comma-separated concept list to inspect")
    parser.add_argument("--periods", type=int, default=8, help="Number of periods")
    parser.add_argument("--restated-only", action="store_true", help="Only include restated periods")
    parser.add_argument("--limit", type=int, default=10, help="Row limit for summaries")
    parser.add_argument("--include-8k", action="store_true", help="Include 8-K Item 4.02 scan")
    parser.add_argument("--export-dir", default=None, help="Optional directory to save CSV outputs")
    args = parser.parse_args()

    _require_identity(args.identity)

    company = Company(args.ticker)
    facts = company.facts
    if not facts:
        print("No facts available for this company.")
        return

    eps_concepts = [
        "us-gaap:EarningsPerShareBasic",
        "us-gaap:EarningsPerShareDiluted",
        "us-gaap:EarningsPerShareBasicAndDiluted",
    ]
    revenue_margin_concepts = [
        "us-gaap:Revenues",
        "us-gaap:SalesRevenueNet",
        "us-gaap:GrossProfit",
        "us-gaap:OperatingIncomeLoss",
        "us-gaap:NetIncomeLoss",
    ]
    bank_concepts = [
        "us-gaap:InterestAndDividendIncomeOperating",
        "us-gaap:InterestIncome",
        "us-gaap:NetInterestIncome",
        "us-gaap:InterestIncomeExpenseNet",
        "us-gaap:ProvisionForCreditLosses",
        "us-gaap:AllowanceForCreditLosses",
    ]
    custom_concepts = []
    if args.concepts:
        custom_concepts = [item.strip() for item in args.concepts.split(",") if item.strip()]

    quarterly = _restated_concepts(facts, "quarterly", args.statement_type, args.limit)
    annual = _restated_concepts(facts, "annual", args.statement_type, args.limit)

    concept = args.concept
    if not concept:
        preferred = quarterly if args.period_type == "quarterly" else annual
        if not preferred.empty:
            concept = preferred.iloc[0]["concept"]
        elif not quarterly.empty:
            concept = quarterly.iloc[0]["concept"]
        elif not annual.empty:
            concept = annual.iloc[0]["concept"]
        else:
            concept = "us-gaap:Revenue"

    series = _restatement_series(
        facts,
        concept=concept,
        period_type=args.period_type,
        periods=args.periods,
        restated_only=args.restated_only
    )

    comparison = _compare_latest_vs_prior(series)
    _print_table("Latest vs prior per period", comparison, limit=args.periods)

    _print_concept_section(
        facts,
        title="EPS restatement workflow",
        concepts=eps_concepts,
        period_type=args.period_type,
        periods=args.periods
    )

    _print_concept_section(
        facts,
        title="Revenue and margin workflow",
        concepts=revenue_margin_concepts,
        period_type=args.period_type,
        periods=args.periods
    )

    _print_concept_section(
        facts,
        title="Banking sector workflow",
        concepts=bank_concepts,
        period_type=args.period_type,
        periods=args.periods
    )

    if custom_concepts:
        _print_concept_section(
            facts,
            title="Custom concept workflow",
            concepts=custom_concepts,
            period_type=args.period_type,
            periods=args.periods
        )

    if args.include_8k:
        restatement_8k = _recent_8k_restatements(company, limit=args.limit)
        _print_table("Recent 8-K Item 4.02 filings", restatement_8k, limit=args.limit)

    if args.export_dir:
        os.makedirs(args.export_dir, exist_ok=True)
        quarterly.to_csv(os.path.join(args.export_dir, "restated_concepts_quarterly.csv"), index=False)
        annual.to_csv(os.path.join(args.export_dir, "restated_concepts_annual.csv"), index=False)
        series.to_csv(os.path.join(args.export_dir, "restatement_time_series.csv"), index=False)
        comparison.to_csv(os.path.join(args.export_dir, "restatement_latest_vs_prior.csv"), index=False)
        if args.include_8k:
            restatement_8k.to_csv(os.path.join(args.export_dir, "restatement_item_402.csv"), index=False)
        print(f"\nSaved CSV outputs to {args.export_dir}")


if __name__ == "__main__":
    main()
