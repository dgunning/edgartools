"""
Example script demonstrating the new fund entity API.

This script shows how to use the new fund entity API to work with fund entities:
- FundCompany: Represents the legal entity (e.g., "Vanguard")
- FundSeries: Represents a specific fund product (e.g., "Vanguard 500 Index Fund")
- FundClass: Represents a specific share class (e.g., "Vanguard 500 Index Admiral Shares")

The new API provides:
1. A smart finder function (find_fund) that returns the appropriate entity type
2. Specialized getter functions for each entity type
3. Navigation between related entities
"""
from edgar.funds import (
    find_fund,
    get_fund_company,
    get_fund_series,
    get_fund_class,
    get_series_by_name,
    get_class_by_ticker,
    FundCompany,
    FundSeries,
    FundClass
)


def demonstrate_find_fund():
    """Demonstrate the smart finder function."""
    print("\n=== Smart Finder Examples ===")
    
    # Find a fund company by its CIK
    vanguard = find_fund("0000102909")
    print(f"By CIK 0000102909: {vanguard}")
    
    # Find a fund series by its Series ID
    s500_series = find_fund("S000584")
    print(f"By Series ID S000584: {s500_series}")
    
    # Find a fund class by its Class ID
    admiral_class = find_fund("C000065928")
    print(f"By Class ID C000065928: {admiral_class}")
    
    # Find a fund class by its ticker
    investor_class = find_fund("VFINX")
    print(f"By ticker VFINX: {investor_class}")


def demonstrate_specialized_getters():
    """Demonstrate the specialized getter functions."""
    print("\n=== Specialized Getter Examples ===")
    
    # Get a fund company directly
    vanguard = get_fund_company("0000102909")
    print(f"Fund Company: {vanguard}")
    
    # Get a fund series directly
    s500_series = get_fund_series("S000584")
    print(f"Fund Series: {s500_series}")
    
    # Get a fund class by class ID
    admiral_class = get_fund_class("C000065928")
    print(f"Fund Class by ID: {admiral_class}")
    
    # Get a fund class by ticker
    investor_class = get_class_by_ticker("VFINX")
    print(f"Fund Class by ticker: {investor_class}")
    
    # Get a series by name
    series = get_series_by_name(102909, "500 Index")
    print(f"Fund Series by name: {series}")


def demonstrate_entity_navigation():
    """Demonstrate navigation between related entities."""
    print("\n=== Entity Navigation Examples ===")
    
    # Start with a fund class
    vfinx = get_class_by_ticker("VFINX")
    print(f"Starting with fund class: {vfinx}")
    
    # Navigate to the parent fund series
    series = vfinx.series
    print(f"Parent fund series: {series}")
    
    # Navigate to the parent fund company
    company = vfinx.company
    print(f"Parent fund company: {company}")
    
    # Get all classes in this series
    classes = series.get_classes()
    print(f"All classes in this series: {[cls.ticker for cls in classes if cls.ticker]}")
    
    # Get all series offered by this company
    all_series = company.get_series()
    print(f"Number of series offered by this company: {len(all_series)}")
    print(f"First few series: {[s.name for s in all_series[:3]]}")


if __name__ == "__main__":
    try:
        demonstrate_find_fund()
        demonstrate_specialized_getters()
        demonstrate_entity_navigation()
    except Exception as e:
        print(f"Error: {e}")