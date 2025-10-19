"""
CompanyFacts API Sign Analysis for Issue #463

This script systematically compares SEC CompanyFacts API values with raw XBRL instance
values, calculation weights, and schema balance types to determine the standard logic
for XBRL concept display signs.

Research Objectives:
1. Does CompanyFacts apply transformation or show raw instance values?
2. Is there a standard rule based on balance type and statement type?
3. Can we derive a deterministic function that matches SEC behavior?
"""

import json
import requests
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from edgar import Company


@dataclass
class ConceptAnalysis:
    """Results of analyzing a concept across raw XBRL and CompanyFacts API."""
    concept: str
    company: str
    cik: str

    # CompanyFacts API data
    companyfacts_value: Optional[float]
    companyfacts_period: Optional[str]

    # Raw XBRL instance data
    instance_value: Optional[float]
    instance_period: Optional[str]

    # XBRL metadata
    calculation_weight: Optional[float]
    schema_balance: Optional[str]
    period_type: Optional[str]

    # Analysis results
    signs_match: Optional[bool]
    transformation_applied: Optional[str]  # "none", "negated", or "unknown"


def fetch_companyfacts(cik: str, concept: str) -> Optional[Dict]:
    """
    Fetch concept data from SEC CompanyFacts API.

    Args:
        cik: Company CIK (with leading zeros)
        concept: XBRL concept name (without us-gaap prefix)

    Returns:
        JSON data from CompanyFacts API or None if not found
    """
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
    headers = {
        'User-Agent': 'EdgarTools Research Script (contact@edgartools.io)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"  CompanyFacts: Concept {concept} not found for CIK {cik}")
            return None
        else:
            print(f"  CompanyFacts API error {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"  Request failed: {e}")
        return None


def analyze_concept(ticker: str, cik: str, concept_base: str,
                   form_type: str = "10-K", year: int = 2023) -> Optional[ConceptAnalysis]:
    """
    Analyze a concept by comparing CompanyFacts API with raw XBRL data.

    Args:
        ticker: Company ticker symbol
        cik: Company CIK (with leading zeros)
        concept_base: XBRL concept name without prefix (e.g., "ResearchAndDevelopmentExpense")
        form_type: Filing form type
        year: Filing year

    Returns:
        ConceptAnalysis object with comparison results
    """
    print(f"\nAnalyzing {ticker} - {concept_base}")

    # Fetch from CompanyFacts API
    print(f"  Fetching CompanyFacts API data...")
    cf_data = fetch_companyfacts(cik, concept_base)
    time.sleep(0.15)  # Rate limiting

    companyfacts_value = None
    companyfacts_period = None

    if cf_data and 'units' in cf_data and 'USD' in cf_data['units']:
        # Find most recent 10-K fact around target year
        facts = cf_data['units']['USD']
        annual_facts = [f for f in facts if f.get('form') == form_type and
                       f.get('fy') == year and f.get('fp') == 'FY']

        if annual_facts:
            # Take first matching fact
            fact = annual_facts[0]
            companyfacts_value = fact.get('val')
            companyfacts_period = fact.get('end')
            print(f"  CompanyFacts: {companyfacts_value:,.0f} for period ending {companyfacts_period}")

    # Fetch from EdgarTools raw XBRL
    print(f"  Fetching EdgarTools XBRL data...")
    try:
        company = Company(ticker)
        filings = company.get_filings(form=form_type, filing_date=f"{year}-01-01:{year+1}-12-31")

        if not filings:
            print(f"  No {form_type} filings found for {year}")
            return None

        filing = filings.latest()
        xbrl = filing.xbrl()

        # Get concept with various name formats
        concept_variants = [
            f"us-gaap_{concept_base}",
            f"us_gaap_{concept_base}",
            concept_base
        ]

        instance_value = None
        instance_period = None
        calculation_weight = None
        schema_balance = None
        period_type = None

        # Try to find the concept
        for variant in concept_variants:
            # Check instance values
            facts_df = xbrl.facts.query().by_concept(variant).to_dataframe()

            if not facts_df.empty:
                # Get annual fact (longest duration or FY fiscal period if available)
                annual_facts = facts_df[facts_df['period_type'] == 'duration']

                # Try to get FY facts if fiscal_period column exists
                if 'fiscal_period' in annual_facts.columns:
                    fy_facts = annual_facts[annual_facts['fiscal_period'] == 'FY']
                    if not fy_facts.empty:
                        annual_facts = fy_facts

                if not annual_facts.empty:
                    fact_row = annual_facts.iloc[0]
                    instance_value = fact_row['numeric_value']
                    instance_period = fact_row['period_end']
                    period_type = fact_row['period_type']
                    print(f"  Instance: {instance_value:,.0f} for period ending {instance_period}")
                    break

        # Get schema balance type - try multiple format variations
        for balance_variant in [f"us_gaap_{concept_base}", f"us-gaap_{concept_base}", concept_base]:
            if balance_variant in xbrl.element_catalog:
                elem = xbrl.element_catalog[balance_variant]
                schema_balance = elem.balance
                if schema_balance:
                    print(f"  Schema balance: {schema_balance}")
                break

        # Get calculation weight (check all calculation trees)
        for role_uri, calc_tree in xbrl.calculation_trees.items():
            for elem_id, node in calc_tree.all_nodes.items():
                if concept_base in elem_id:
                    calculation_weight = node.weight
                    print(f"  Calculation weight: {calculation_weight} (role: {role_uri.split('/')[-1]})")
                    break
            if calculation_weight is not None:
                break

        # Analyze transformation
        signs_match = None
        transformation = "unknown"

        if companyfacts_value is not None and instance_value is not None:
            signs_match = (companyfacts_value > 0) == (instance_value > 0)

            if abs(companyfacts_value - instance_value) < 0.01:
                transformation = "none"
            elif abs(companyfacts_value + instance_value) < 0.01:
                transformation = "negated"
            else:
                transformation = "different_value"

            print(f"  Analysis: signs_match={signs_match}, transformation={transformation}")

        return ConceptAnalysis(
            concept=concept_base,
            company=ticker,
            cik=cik,
            companyfacts_value=companyfacts_value,
            companyfacts_period=companyfacts_period,
            instance_value=instance_value,
            instance_period=instance_period,
            calculation_weight=calculation_weight,
            schema_balance=schema_balance,
            period_type=period_type,
            signs_match=signs_match,
            transformation_applied=transformation
        )

    except Exception as e:
        print(f"  Error fetching XBRL: {e}")
        return None


def main():
    """Run comprehensive CompanyFacts sign analysis."""

    print("=" * 80)
    print("CompanyFacts API Sign Analysis for Issue #463")
    print("=" * 80)

    # Test companies with known CIKs
    companies = [
        ("AAPL", "0000320193"),
        ("MSFT", "0000789019"),
        ("GOOGL", "0001652044"),
    ]

    # Test concepts - expenses that should be positive
    test_concepts = [
        "ResearchAndDevelopmentExpense",
        "CostOfRevenue",
        "IncomeTaxExpenseBenefit",
        "PaymentsOfDividends",
    ]

    results = []

    for ticker, cik in companies:
        for concept in test_concepts:
            result = analyze_concept(ticker, cik, concept, form_type="10-K", year=2023)
            if result:
                results.append(result)
            time.sleep(0.2)  # Rate limiting

    # Summary analysis
    print("\n" + "=" * 80)
    print("SUMMARY ANALYSIS")
    print("=" * 80)

    print("\n1. CompanyFacts vs Instance Value Comparison:")
    print("-" * 80)
    print(f"{'Company':<8} {'Concept':<35} {'CF Sign':<8} {'Inst Sign':<10} {'Match':<8} {'Transform':<12}")
    print("-" * 80)

    for r in results:
        if r.companyfacts_value is not None and r.instance_value is not None:
            cf_sign = "+" if r.companyfacts_value > 0 else "-"
            inst_sign = "+" if r.instance_value > 0 else "-"
            match = "YES" if r.signs_match else "NO"
            print(f"{r.company:<8} {r.concept:<35} {cf_sign:<8} {inst_sign:<10} {match:<8} {r.transformation_applied:<12}")

    print("\n2. Balance Type vs Sign Pattern:")
    print("-" * 80)
    print(f"{'Concept':<35} {'Balance':<10} {'Weight':<8} {'CF Sign':<10}")
    print("-" * 80)

    for r in results:
        if r.companyfacts_value is not None:
            cf_sign = "+" if r.companyfacts_value > 0 else "-"
            weight_str = f"{r.calculation_weight}" if r.calculation_weight is not None else "N/A"
            balance_str = r.schema_balance if r.schema_balance else "N/A"
            print(f"{r.concept:<35} {balance_str:<10} {weight_str:<8} {cf_sign:<10}")

    print("\n3. Key Findings:")
    print("-" * 80)

    # Check if all transformations are "none"
    all_no_transform = all(r.transformation_applied == "none"
                          for r in results if r.transformation_applied)

    if all_no_transform:
        print("✓ CompanyFacts shows RAW INSTANCE VALUES (no transformation)")
    else:
        print("✗ CompanyFacts applies transformations to some concepts")

    # Check balance type patterns
    debit_concepts = [r for r in results if r.schema_balance == "debit"]
    credit_concepts = [r for r in results if r.schema_balance == "credit"]

    print(f"\n  Debit balance concepts: {len(debit_concepts)}")
    for r in debit_concepts:
        if r.companyfacts_value:
            sign = "positive" if r.companyfacts_value > 0 else "negative"
            print(f"    {r.concept}: {sign} in CompanyFacts")

    print(f"\n  Credit balance concepts: {len(credit_concepts)}")
    for r in credit_concepts:
        if r.companyfacts_value:
            sign = "positive" if r.companyfacts_value > 0 else "negative"
            print(f"    {r.concept}: {sign} in CompanyFacts")

    print("\n" + "=" * 80)
    print("Analysis complete. See results above for patterns.")
    print("=" * 80)

    # Save results to JSON for further analysis
    results_data = []
    for r in results:
        results_data.append({
            'concept': r.concept,
            'company': r.company,
            'cik': r.cik,
            'companyfacts_value': r.companyfacts_value,
            'instance_value': r.instance_value,
            'calculation_weight': r.calculation_weight,
            'schema_balance': r.schema_balance,
            'signs_match': r.signs_match,
            'transformation_applied': r.transformation_applied
        })

    with open('/Users/dwight/PycharmProjects/edgartools/research_scripts/companyfacts_analysis_results.json', 'w') as f:
        json.dump(results_data, f, indent=2, default=str)

    print("\nResults saved to: research_scripts/companyfacts_analysis_results.json")


if __name__ == "__main__":
    main()
