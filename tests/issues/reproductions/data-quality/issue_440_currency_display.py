"""
Issue #440 Reproduction: Incorrect currency display for non-US companies

Deutsche Bank (DB) shows amounts in USD ($) instead of EUR (€) in cash flow statements
from 20-F filings. This reproduction script confirms the issue and investigates the
root cause.

Expected: 29,493 million € (EURO)
Actual: 29,493 million $ (Dollar)

GitHub Issue: https://github.com/dgunning/edgartools/issues/440
"""

from edgar import Company, set_identity
import os

# Use environment identity for tests
if not os.getenv('EDGAR_IDENTITY'):
    set_identity("EdgarTools Test test@edgartools.dev")

def reproduce_currency_issue():
    """Reproduce the currency display issue with Deutsche Bank"""
    print("=== Issue #440 Reproduction: Deutsche Bank Currency Display ===\n")

    # Get Deutsche Bank company
    company = Company("DB")
    print(f"Company: {company.name} ({company.cik})")

    # Get latest 20-F filing
    filings = company.get_filings(form="20-F", amendments=False)
    latest_filing = filings.latest()
    print(f"Latest 20-F Filing: {latest_filing.accession_number} ({latest_filing.filing_date})")

    # Get XBRL and cash flow statement
    xbrl = latest_filing.xbrl()
    cashflow = xbrl.statements.cashflow_statement()

    print(f"\nCash Flow Statement:")
    print(f"Statement Type: {type(cashflow)}")
    print(f"Statement Currency Symbol: {getattr(cashflow, 'currency_symbol', 'N/A')}")
    print(f"Statement Currency: {getattr(cashflow, 'currency', 'N/A')}")

    # Check statement attributes
    statement_attrs = [attr for attr in dir(cashflow) if not attr.startswith('_')]
    print(f"Statement attributes: {statement_attrs}")

    # Look at the statement display to see currency
    print(f"\nCash Flow Statement Display:")
    print(cashflow)

    # Get dataframe to examine structure
    df = cashflow.to_dataframe()
    print(f"\nDataFrame shape: {df.shape}")
    print(f"DataFrame columns: {df.columns.tolist()}")
    print(f"DataFrame head:")
    print(df.head())

    # Check XBRL context and currency information
    print(f"\n=== XBRL Currency Analysis ===")
    print(f"XBRL Facts count: {len(xbrl.facts)}")

    # Check XBRL facts structure
    print(f"XBRL facts type: {type(xbrl.facts)}")
    print(f"XBRL facts attributes: {[attr for attr in dir(xbrl.facts) if not attr.startswith('_')]}")

    # Try to get facts using the get_facts method
    try:
        # Get some facts from the cash flow statement
        sample_facts = xbrl.facts.get_facts(concept="db_NetChangeInFinancialLiabilitiesDesignatedAtFairValueThroughProfitOrLossAndInvestmentContractLiabilities")

        print(f"Sample facts found: {len(sample_facts)}")
        for i, fact in enumerate(sample_facts):
            print(f"  Fact {i}: {type(fact)}")
            fact_attrs = [attr for attr in dir(fact) if not attr.startswith('_')]
            print(f"    Attributes: {fact_attrs}")

            if hasattr(fact, 'unit_ref'):
                print(f"    Unit ref: {fact.unit_ref}")
                # Look up the unit in the XBRL units registry
                if fact.unit_ref in xbrl.units:
                    unit_info = xbrl.units[fact.unit_ref]
                    print(f"    Unit info: {unit_info}")

            if hasattr(fact, 'concept'):
                print(f"    Concept: {fact.concept}")
            if hasattr(fact, 'value'):
                print(f"    Value: {fact.value}")
            if hasattr(fact, 'context_ref'):
                print(f"    Context ref: {fact.context_ref}")

    except Exception as e:
        print(f"Error accessing facts: {e}")

    # Try to get any facts to see unit references
    try:
        # Get all facts and check their unit references
        all_facts = xbrl.facts.to_dataframe()
        print(f"\nAll facts dataframe shape: {all_facts.shape}")
        if 'unit_ref' in all_facts.columns:
            unit_refs = all_facts['unit_ref'].unique()
            print(f"Unique unit references: {unit_refs}")

            # Show facts with each unit reference
            for unit_ref in unit_refs:
                if unit_ref and unit_ref in xbrl.units:
                    unit_info = xbrl.units[unit_ref]
                    print(f"  {unit_ref}: {unit_info}")
        else:
            print(f"Available columns: {all_facts.columns.tolist()}")

    except Exception as e:
        print(f"Error getting facts dataframe: {e}")

    # Check if XBRL has unit definitions
    if hasattr(xbrl, 'units'):
        print(f"\nXBRL units available: {xbrl.units}")
    elif hasattr(xbrl, 'unit_registry'):
        print(f"\nXBRL unit registry: {xbrl.unit_registry}")

    # Check raw XBRL data for currency info
    xbrl_attrs = [attr for attr in dir(xbrl) if not attr.startswith('_')]
    print(f"\nXBRL main attributes: {xbrl_attrs}")

    return cashflow, xbrl

def analyze_xbrl_currency_data(xbrl):
    """Analyze XBRL data to understand currency handling"""
    print(f"\n=== Detailed XBRL Currency Analysis ===")

    # Check if XBRL has unit information
    if hasattr(xbrl, 'units'):
        print(f"XBRL Units: {xbrl.units}")

    # Look for currency concepts in facts
    currency_related_facts = []
    for fact in xbrl.facts:
        if hasattr(fact, 'concept') and 'currency' in fact.concept.lower():
            currency_related_facts.append(fact)

    print(f"Currency-related facts found: {len(currency_related_facts)}")
    for fact in currency_related_facts[:3]:
        print(f"  {fact.concept}: {fact.value}")

    # Check for unit definitions in XBRL
    print(f"\nChecking XBRL structure for currency information...")
    print(f"XBRL attributes: {[attr for attr in dir(xbrl) if not attr.startswith('_')]}")

if __name__ == "__main__":
    cashflow, xbrl = reproduce_currency_issue()
    analyze_xbrl_currency_data(xbrl)