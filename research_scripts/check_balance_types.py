"""
Check balance types in US-GAAP taxonomy schema files.

This script examines the US-GAAP taxonomy XSD files to understand why
balance types are showing as None in EdgarTools.
"""

import xml.etree.ElementTree as ET
from pathlib import Path


def check_test_fixture_balance_types():
    """Check balance types in Apple's test fixture schema."""

    # Check if there's a US-GAAP schema file in test fixtures
    test_dir = Path("/Users/dwight/PycharmProjects/edgartools/tests/fixtures/xbrl2/aapl/10k_2023")

    print("=" * 80)
    print("Checking Balance Types in XBRL Schema Files")
    print("=" * 80)

    # Find all XSD files
    xsd_files = list(test_dir.glob("*.xsd"))

    if not xsd_files:
        print("No XSD files found")
        return

    test_concepts = [
        "ResearchAndDevelopmentExpense",
        "IncomeTaxExpenseBenefit",
        "PaymentsOfDividends",
        "CostOfGoodsAndServicesSold"
    ]

    for xsd_file in xsd_files:
        print(f"\nAnalyzing: {xsd_file.name}")

        tree = ET.parse(xsd_file)
        root = tree.getroot()

        # Define namespaces
        ns = {
            'xs': 'http://www.w3.org/2001/XMLSchema',
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'link': 'http://www.xbrl.org/2003/linkbase'
        }

        # Find all element declarations
        elements = root.findall('.//xs:element', ns)

        print(f"  Found {len(elements)} element declarations")

        # Look for our test concepts
        for concept in test_concepts:
            for element in elements:
                name = element.get('name', '')
                elem_id = element.get('id', '')

                if concept in name or concept in elem_id:
                    print(f"\n  Found concept: {name or elem_id}")

                    # Check for balance attribute
                    balance = element.get('{http://www.xbrl.org/2003/instance}balance')
                    if balance:
                        print(f"    Balance (direct attribute): {balance}")
                    else:
                        # Check in annotation/appinfo
                        annotation = element.find('.//xs:annotation', ns)
                        if annotation is not None:
                            appinfo = annotation.find('.//xs:appinfo', ns)
                            if appinfo is not None:
                                balance_elem = appinfo.find('.//xbrli:balance', ns)
                                if balance_elem is not None:
                                    print(f"    Balance (in appinfo): {balance_elem.text}")
                                else:
                                    print(f"    Balance: NOT FOUND")
                        else:
                            print(f"    Balance: NOT FOUND (no annotation)")

                    # Check period type
                    period_type = element.get('{http://www.xbrl.org/2003/instance}periodType')
                    if period_type:
                        print(f"    PeriodType (direct): {period_type}")
                    else:
                        if annotation is not None and appinfo is not None:
                            period_elem = appinfo.find('.//xbrli:periodType', ns)
                            if period_elem is not None:
                                print(f"    PeriodType (in appinfo): {period_elem.text}")


def check_us_gaap_online():
    """
    Show how to access US-GAAP taxonomy online.

    The actual balance types are defined in the main US-GAAP taxonomy,
    not in company-specific extension schemas.
    """

    print("\n" + "=" * 80)
    print("US-GAAP Taxonomy Structure")
    print("=" * 80)

    print("""
The balance attribute is defined in the main US-GAAP taxonomy, not in
company extension schemas.

US-GAAP Taxonomy URL:
  https://xbrl.fasb.org/us-gaap/2023/elts/us-gaap-2023.xsd

Known balance types from XBRL 2.1 specification:

ResearchAndDevelopmentExpense:
  - Balance: debit
  - Rationale: Expenses increase with debits in double-entry accounting

IncomeTaxExpenseBenefit:
  - Balance: debit
  - Rationale: Tax expense is a debit account (like all expenses)

PaymentsOfDividends:
  - Balance: credit
  - Rationale: Dividends reduce equity (credit to cash, debit to retained earnings)
  - The "Payments" refers to cash side (credit/reduction)

CostOfGoodsAndServicesSold:
  - Balance: debit
  - Rationale: Expenses/costs have debit balances

Revenue:
  - Balance: credit
  - Rationale: Revenue increases with credits

Cash:
  - Balance: debit
  - Rationale: Assets have debit balances

AccountsPayable:
  - Balance: credit
  - Rationale: Liabilities have credit balances

Why EdgarTools shows Balance: None
===================================

EdgarTools parses COMPANY extension schemas (e.g., aapl-20230930.xsd),
which only define company-specific elements.

Standard US-GAAP concepts like "us-gaap:ResearchAndDevelopmentExpense"
are defined in the IMPORTED us-gaap taxonomy, which EdgarTools may not
be fully parsing.

Solution:
---------
1. Download and parse us-gaap-YYYY.xsd files
2. Cache balance types for standard concepts
3. Use taxonomy year from filing to get correct version
""")


if __name__ == "__main__":
    check_test_fixture_balance_types()
    check_us_gaap_online()
