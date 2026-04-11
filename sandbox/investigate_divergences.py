"""
Divergence Root Cause Investigation Script

Investigates 4 known divergences by downloading actual SEC filings
and analyzing XBRL data using edgartools APIs.

Target divergences:
1. PFE Revenue (99.3% variance, 2024 only) - CRITICAL
2. COP Capex (913% variance) - CRITICAL
3. HON DepreciationAmortization (49.7% variance) - Tree parser priority issue
4. UNH Revenue (78.4% variance) - Insurance accounting

Date: 2026-01-27
"""

import sys
import warnings
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

warnings.filterwarnings("ignore")

from edgar import Company, set_identity

set_identity("EdgarTools Investigation research@edgartools.io")


def separator(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def subseparator(title: str):
    print(f"\n--- {title} ---\n")


def search_facts(xbrl, pattern: str, limit: int = 20):
    """Search facts by concept pattern and display results."""
    try:
        df = xbrl.facts.to_dataframe()
        if df is None or len(df) == 0:
            print(f"  No facts available")
            return None

        # Filter by concept pattern (case-insensitive)
        mask = df['concept'].str.contains(pattern, case=False, na=False)
        matched = df[mask]

        if len(matched) == 0:
            print(f"  No facts matching '{pattern}'")
            return None

        # Filter to non-dimensional facts for cleaner output
        if 'full_dimension_label' in matched.columns:
            base = matched[matched['full_dimension_label'].isna()]
            if len(base) > 0:
                matched = base

        # Show summary
        concepts_found = matched['concept'].unique()
        print(f"  Found {len(matched)} facts matching '{pattern}' ({len(concepts_found)} concepts):")
        for c in sorted(concepts_found):
            concept_facts = matched[matched['concept'] == c]
            # Get numeric values
            if 'numeric_value' in concept_facts.columns:
                vals = concept_facts['numeric_value'].dropna()
                if len(vals) > 0:
                    # Show latest value
                    latest = concept_facts.sort_values('period_end', ascending=False).iloc[0] if 'period_end' in concept_facts.columns else concept_facts.iloc[0]
                    val = latest.get('numeric_value', 'N/A')
                    period = latest.get('period_key', 'N/A')
                    if val != 'N/A' and val is not None:
                        print(f"    {c}: ${val/1e6:,.0f}M (period: {period})")
                    else:
                        print(f"    {c}: value=N/A (period: {period})")
                else:
                    print(f"    {c}: {len(concept_facts)} facts (no numeric values)")
            else:
                print(f"    {c}: {len(concept_facts)} facts")

        return matched

    except Exception as e:
        print(f"  Error searching facts: {e}")
        return None


def get_filing_and_xbrl(ticker: str, form: str = "10-K", index: int = 0):
    """Get a filing and its XBRL data."""
    company = Company(ticker)
    filings = company.get_filings(form=form)
    filing = filings[index]
    print(f"  Filing: {filing.accession_no}")
    print(f"  Date: {filing.filing_date}")
    print(f"  Period: {getattr(filing, 'period_of_report', 'N/A')}")
    xbrl = filing.xbrl()
    print(f"  XBRL loaded: {len(xbrl.facts.to_dataframe())} total facts")
    return filing, xbrl


def show_statement(xbrl, statement_type: str):
    """Display a financial statement."""
    try:
        if statement_type == "income":
            stmt = xbrl.statements.income_statement()
        elif statement_type == "cashflow":
            stmt = xbrl.statements.cash_flow_statement()
        elif statement_type == "balance":
            stmt = xbrl.statements.balance_sheet()
        else:
            print(f"  Unknown statement type: {statement_type}")
            return None

        if stmt is not None:
            print(stmt)
        else:
            print(f"  Statement not found: {statement_type}")
        return stmt
    except Exception as e:
        print(f"  Error getting {statement_type} statement: {e}")
        return None


def show_calc_tree_concepts(xbrl, pattern: str):
    """Show concepts in calculation trees matching a pattern."""
    print(f"\n  Calculation tree concepts matching '{pattern}':")
    found = False
    for role, tree in xbrl.calculation_trees.items():
        tree_name = role.split('/')[-1] if '/' in role else role
        for node_id, node in tree.all_nodes.items():
            if pattern.lower() in node_id.lower():
                parent_name = node.parent or "ROOT"
                children_str = ", ".join(node.children[:5]) if node.children else "none"
                print(f"    [{tree_name}] {node_id}")
                print(f"      parent={parent_name}, weight={node.weight}, children=[{children_str}]")
                found = True
    if not found:
        print(f"    No concepts found matching '{pattern}'")


# =============================================================================
# INVESTIGATION 1: PFE Revenue (CRITICAL - 99.3% variance, 2024 only)
# =============================================================================
def investigate_pfe():
    separator("INVESTIGATION 1: PFE (Pfizer) Revenue - 99.3% variance")

    print("Question: Why does 2024 10-K extract only $442M instead of $63.6B?")
    print("Expected: RevenueFromContractWithCustomerExcludingAssessedTax → ~$63.6B")
    print()

    # --- PFE 2024 10-K (the problematic filing) ---
    subseparator("PFE 2024 10-K (problematic)")
    print("Loading 2024 10-K (latest)...")
    filing_2024, xbrl_2024 = get_filing_and_xbrl("PFE", "10-K", 0)

    subseparator("Revenue-related facts in 2024 10-K")
    search_facts(xbrl_2024, "Revenue")
    search_facts(xbrl_2024, "Sales")
    search_facts(xbrl_2024, "NetSales")

    subseparator("Calculation tree: Revenue concepts in 2024")
    show_calc_tree_concepts(xbrl_2024, "Revenue")
    show_calc_tree_concepts(xbrl_2024, "Sales")

    subseparator("2024 Income Statement")
    show_statement(xbrl_2024, "income")

    # --- PFE 2023 10-K (comparison baseline) ---
    subseparator("PFE 2023 10-K (baseline comparison)")
    print("Loading 2023 10-K...")
    filing_2023, xbrl_2023 = get_filing_and_xbrl("PFE", "10-K", 1)

    subseparator("Revenue-related facts in 2023 10-K")
    search_facts(xbrl_2023, "Revenue")

    subseparator("Calculation tree: Revenue concepts in 2023")
    show_calc_tree_concepts(xbrl_2023, "Revenue")

    subseparator("2023 Income Statement")
    show_statement(xbrl_2023, "income")

    # --- Summary ---
    subseparator("PFE ANALYSIS SUMMARY")
    print("Compare 2024 vs 2023 revenue concepts to identify structural change.")
    print("Key questions:")
    print("  1. Is RevenueFromContractWithCustomerExcludingAssessedTax present in both years?")
    print("  2. What concept yields $442M? (likely a sub-category)")
    print("  3. Did PFE restructure their revenue disclosure in 2024?")


# =============================================================================
# INVESTIGATION 2: COP Capex (913% variance)
# =============================================================================
def investigate_cop():
    separator("INVESTIGATION 2: COP (ConocoPhillips) Capex - 913% variance")

    print("Question: Why does tree parser select 'Assets' instead of a Capex concept?")
    print("Extracted: -$122.8B (Total Assets). Expected: ~$12.1B")
    print()

    filing, xbrl = get_filing_and_xbrl("COP", "10-K", 0)

    subseparator("Capex-related facts")
    search_facts(xbrl, "Payment")
    search_facts(xbrl, "Acquire")
    search_facts(xbrl, "Capital")
    search_facts(xbrl, "PropertyPlant")

    subseparator("Calculation tree: Capex-related concepts")
    show_calc_tree_concepts(xbrl, "Payment")
    show_calc_tree_concepts(xbrl, "Acquire")
    show_calc_tree_concepts(xbrl, "Assets")
    show_calc_tree_concepts(xbrl, "Capital")

    subseparator("Cash Flow Statement")
    show_statement(xbrl, "cashflow")

    subseparator("COP ANALYSIS SUMMARY")
    print("Key questions:")
    print("  1. Does PaymentsToAcquirePropertyPlantAndEquipment exist in calc tree?")
    print("  2. Does PaymentsToAcquireProductiveAssets exist?")
    print("  3. Why would tree parser fall back to 'Assets'?")
    print("  4. Is the exclude_patterns list missing patterns needed for COP?")


# =============================================================================
# INVESTIGATION 3: HON DepreciationAmortization (49.7% variance)
# =============================================================================
def investigate_hon():
    separator("INVESTIGATION 3: HON (Honeywell) D&A - 49.7% variance")

    print("Question: Does HON report Depreciation and Amortization separately?")
    print("Extracted: ~$671M (Depreciation only). Expected: ~$1.33B (D&A combined)")
    print()

    filing, xbrl = get_filing_and_xbrl("HON", "10-K", 0)

    subseparator("D&A-related facts")
    search_facts(xbrl, "Depreci")
    search_facts(xbrl, "Amortiz")

    subseparator("Calculation tree: D&A concepts")
    show_calc_tree_concepts(xbrl, "Depreci")
    show_calc_tree_concepts(xbrl, "Amortiz")

    subseparator("Cash Flow Statement")
    show_statement(xbrl, "cashflow")

    subseparator("HON ANALYSIS SUMMARY")
    print("Key questions:")
    print("  1. Do both Depreciation AND DepreciationAndAmortization exist?")
    print("  2. Is Depreciation listed first in known_concepts priority?")
    print("  3. Does metrics.yaml list DepreciationDepletionAndAmortization first?")
    print("  4. What is the correct combined D&A value?")


# =============================================================================
# INVESTIGATION 4: UNH Revenue (78.4% variance)
# =============================================================================
def investigate_unh():
    separator("INVESTIGATION 4: UNH (UnitedHealth) Revenue - 78.4% variance")

    print("Question: Does UNH use PremiumsEarnedNet instead of standard Revenue?")
    print("Extracted: ~$86B (contract revenue only). Expected: ~$400B (total)")
    print()

    filing, xbrl = get_filing_and_xbrl("UNH", "10-K", 0)

    subseparator("Revenue-related facts")
    search_facts(xbrl, "Revenue")
    search_facts(xbrl, "Premium")
    search_facts(xbrl, "NetSales")

    subseparator("All concepts with large values (>$50B)")
    try:
        df = xbrl.facts.to_dataframe()
        if 'numeric_value' in df.columns and 'full_dimension_label' in df.columns:
            # Filter non-dimensional, large values
            base = df[df['full_dimension_label'].isna()]
            large = base[base['numeric_value'].abs() > 50e9]
            if len(large) > 0:
                for _, row in large.drop_duplicates(subset='concept').iterrows():
                    print(f"    {row['concept']}: ${row['numeric_value']/1e9:.1f}B")
            else:
                print("    No facts > $50B found (may need different filter)")
    except Exception as e:
        print(f"    Error: {e}")

    subseparator("Calculation tree: Revenue and Premium concepts")
    show_calc_tree_concepts(xbrl, "Revenue")
    show_calc_tree_concepts(xbrl, "Premium")

    subseparator("Income Statement")
    show_statement(xbrl, "income")

    subseparator("UNH ANALYSIS SUMMARY")
    print("Key questions:")
    print("  1. Is PremiumsEarnedNet in the filing? If so, what value?")
    print("  2. What is the total revenue concept (combining premiums + services)?")
    print("  3. Does Revenues concept exist with the full $400B value?")
    print("  4. Is this a tree parser issue or a structural insurance accounting issue?")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("="*80)
    print("  DIVERGENCE ROOT CAUSE INVESTIGATION")
    print("  Date: 2026-01-27")
    print("  Targets: PFE, COP, HON, UNH")
    print("="*80)

    # Run all investigations
    investigate_pfe()
    investigate_cop()
    investigate_hon()
    investigate_unh()

    separator("INVESTIGATION COMPLETE")
    print("Review output above to determine root causes.")
    print("Next steps:")
    print("  1. Update companies.yaml with specific concept names and values")
    print("  2. Determine remediation_status for each divergence")
    print("  3. Run E2E test to verify divergences are properly skipped")
