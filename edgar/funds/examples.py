"""
Examples of using the new fund entity API.

This module demonstrates how to use the improved fund entity API
to work with fund companies, series, and classes.
"""

from edgar.funds import (
    find_fund,
    get_fund_company,
    get_fund_series,
    get_fund_class,
)


def demonstrate_find_fund():
    """Demonstrate the smart finder function."""
    print("\n=== Using find_fund() to find entities by different identifiers ===")
    
    # Find a fund company by CIK
    company = find_fund("0001048636")  # T. Rowe Price
    print(f"Found company: {company}")
    
    # Find a fund series by series ID
    series = find_fund("S000005029")  # Kinetics Internet Fund
    print(f"Found series: {series}")
    
    # Find a fund class by class ID
    class_by_id = find_fund("C000013712")  # Kinetics Internet Fund Advisor Class C
    print(f"Found class by ID: {class_by_id}")
    
    # Find a fund class by ticker
    class_by_ticker = find_fund("KINCX")  # Kinetics Internet Fund Advisor Class C
    print(f"Found class by ticker: {class_by_ticker}")


def demonstrate_specialized_getters():
    """Demonstrate the specialized getter functions."""
    print("\n=== Using specialized getters for each entity type ===")
    
    # Get a fund company
    company = get_fund_company("0001048636")  # T. Rowe Price
    print(f"Got company: {company}")
    
    # Get a fund series
    series = get_fund_series("S000005029")  # Kinetics Internet Fund
    print(f"Got series: {series}")
    
    # Get a fund class by ID
    class_by_id = get_fund_class("C000013712")  # Kinetics Internet Fund Advisor Class C
    print(f"Got class by ID: {class_by_id}")
    
    # Get a fund class by ticker
    class_by_ticker = get_fund_class("KINCX")  # Should be the same as above
    print(f"Got class by ticker: {class_by_ticker}")


def demonstrate_entity_navigation():
    """Demonstrate navigation between related entities."""
    print("\n=== Navigating between related entities ===")
    
    # Start with a fund class
    fund_class = get_fund_class("KINCX")
    print(f"Starting with class: {fund_class}")
    
    # Navigate to its series
    series = fund_class.series
    print(f"Parent series: {series}")
    
    # Navigate to the fund company
    company = fund_class.series.fund_company
    print(f"Parent company: {company}")
    
    # Get all series for the company
    all_series = company.all_series
    print(f"Company has {len(all_series)} series:")
    for s in all_series[:3]:  # Show first 3
        print(f"  - {s}")
    
    # Get all classes for a series
    if series:
        series_classes = series.get_classes()
        print(f"Series '{series.name}' has {len(series_classes)} classes:")
        for c in series_classes:
            print(f"  - {c}")


def main():
    """Main function to run all demonstrations."""
    print("=== Fund Entity API Examples ===")
    
    demonstrate_find_fund()
    demonstrate_specialized_getters()
    demonstrate_entity_navigation()
    
    print("\nDone!")


if __name__ == "__main__":
    main()