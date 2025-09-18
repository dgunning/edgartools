"""
Examples of using the new fund entity API.

This module demonstrates how to use the improved fund entity API
to work with fund companies, series, and classes.
"""

from edgar.funds import (
    find_fund,
    get_fund_class,
    get_fund_company,
    get_fund_series,
)


def demonstrate_find_fund():
    """Demonstrate the smart finder function."""

    # Find a fund company by CIK
    find_fund("0001048636")  # T. Rowe Price

    # Find a fund series by series ID
    find_fund("S000005029")  # Kinetics Internet Fund

    # Find a fund class by class ID
    find_fund("C000013712")  # Kinetics Internet Fund Advisor Class C

    # Find a fund class by ticker
    find_fund("KINCX")  # Kinetics Internet Fund Advisor Class C


def demonstrate_specialized_getters():
    """Demonstrate the specialized getter functions."""

    # Get a fund company
    get_fund_company("0001048636")  # T. Rowe Price

    # Get a fund series
    get_fund_series("S000005029")  # Kinetics Internet Fund

    # Get a fund class by ID
    get_fund_class("C000013712")  # Kinetics Internet Fund Advisor Class C

    # Get a fund class by ticker
    get_fund_class("KINCX")  # Should be the same as above


def demonstrate_entity_navigation():
    """Demonstrate navigation between related entities."""

    # Start with a fund class
    fund_class = get_fund_class("KINCX")

    # Navigate to its series
    series = fund_class.series

    # Navigate to the fund company
    company = fund_class.series.fund_company

    # Get all series for the company
    all_series = company.all_series
    for _s in all_series[:3]:  # Show first 3
        pass

    # Get all classes for a series
    if series:
        series_classes = series.get_classes()
        for _c in series_classes:
            pass


def main():
    """Main function to run all demonstrations."""

    demonstrate_find_fund()
    demonstrate_specialized_getters()
    demonstrate_entity_navigation()



if __name__ == "__main__":
    main()
