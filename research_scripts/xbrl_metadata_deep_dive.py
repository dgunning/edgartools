"""
Deep Dive XBRL Metadata Analysis for Issue #463

This script directly examines XBRL instance documents, calculation linkbases,
and presentation linkbases to understand how signs are determined.
"""

from edgar import Company
import xml.etree.ElementTree as ET
from pathlib import Path


def analyze_apple_filing():
    """Analyze Apple's latest 10-K in detail."""

    print("=" * 80)
    print("Deep Dive XBRL Metadata Analysis - Apple 10-K")
    print("=" * 80)

    # Get Apple's latest 10-K
    company = Company("AAPL")
    filing = company.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()

    print(f"\nFiling: {filing.accession_number}")
    print(f"Period: {filing.filing_date}")

    # Test concepts from Issue #463
    test_concepts = [
        "ResearchAndDevelopmentExpense",
        "IncomeTaxExpenseBenefit",
        "PaymentsOfDividends",
        "CostOfGoodsAndServicesSold"
    ]

    for concept_name in test_concepts:
        print("\n" + "=" * 80)
        print(f"Analyzing: {concept_name}")
        print("=" * 80)

        # 1. Check element catalog
        print("\n1. Element Catalog:")
        found_elem = None
        for variant in [f"us-gaap_{concept_name}", f"us_gaap_{concept_name}", concept_name]:
            if variant in xbrl.element_catalog:
                elem = xbrl.element_catalog[variant]
                found_elem = elem
                print(f"  Found as: {variant}")
                print(f"  Balance: {elem.balance}")
                print(f"  Period Type: {elem.period_type}")
                print(f"  Data Type: {elem.data_type}")
                print(f"  Abstract: {elem.abstract}")
                break

        if not found_elem:
            print(f"  NOT FOUND in element catalog")
            # Show what IS in the catalog
            matching = [k for k in xbrl.element_catalog.keys() if concept_name.lower() in k.lower()]
            if matching:
                print(f"  Similar concepts found: {matching[:5]}")

        # 2. Check calculation trees
        print("\n2. Calculation Linkbase:")
        found_in_calc = False
        for role_uri, calc_tree in xbrl.calculation_trees.items():
            for elem_id, node in calc_tree.all_nodes.items():
                if concept_name in elem_id:
                    found_in_calc = True
                    role_name = role_uri.split('/')[-1] if '/' in role_uri else role_uri
                    print(f"  Found in role: {role_name}")
                    print(f"    Element ID: {elem_id}")
                    print(f"    Weight: {node.weight}")
                    print(f"    Balance Type: {node.balance_type}")
                    print(f"    Period Type: {node.period_type}")
                    print(f"    Parent: {node.parent}")
                    print(f"    Children: {len(node.children)}")

        if not found_in_calc:
            print("  NOT FOUND in calculation linkbase")

        # 3. Check presentation trees
        print("\n3. Presentation Linkbase:")
        found_in_pres = False
        for role_uri, pres_tree in xbrl.presentation_trees.items():
            for elem_id, node in pres_tree.all_nodes.items():
                if concept_name in elem_id:
                    found_in_pres = True
                    role_name = role_uri.split('/')[-1] if '/' in role_uri else role_uri
                    print(f"  Found in role: {role_name}")
                    print(f"    Element ID: {elem_id}")
                    print(f"    Preferred Label: {node.preferred_label}")
                    print(f"    Depth: {node.depth}")
                    print(f"    Order: {node.order}")
                    print(f"    Is Abstract: {node.is_abstract}")

                    # Check for negation hints in preferred label
                    if node.preferred_label:
                        if 'negat' in node.preferred_label.lower():
                            print(f"    >>> NEGATION HINT FOUND in preferred label!")

        if not found_in_pres:
            print("  NOT FOUND in presentation linkbase")

        # 4. Check actual fact values
        print("\n4. Instance Facts:")
        facts_df = xbrl.facts.query().by_concept(concept_name).to_dataframe()

        if not facts_df.empty:
            # Get most recent annual fact
            annual_facts = facts_df[facts_df['period_type'] == 'duration']
            if not annual_facts.empty:
                recent = annual_facts.iloc[0]
                print(f"  Value: {recent['numeric_value']:,.0f}")
                print(f"  Period: {recent['period_start']} to {recent['period_end']}")
                print(f"  Sign: {'POSITIVE' if recent['numeric_value'] > 0 else 'NEGATIVE'}")
                print(f"  Unit: {recent.get('unit_ref', 'N/A')}")

                # Check what columns are available
                print(f"  Available columns: {list(facts_df.columns)}")
        else:
            print("  NO FACTS FOUND")


def check_presentation_linkbase_raw():
    """Check raw presentation linkbase XML for preferredLabel attributes."""

    print("\n" + "=" * 80)
    print("Raw Presentation Linkbase Analysis")
    print("=" * 80)

    # Check a test fixture
    test_file = Path("/Users/dwight/PycharmProjects/edgartools/tests/fixtures/xbrl2/aapl/10k_2023/aapl-20230930_pre.xml")

    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return

    print(f"\nAnalyzing: {test_file.name}")

    tree = ET.parse(test_file)
    root = tree.getroot()

    # Find presentationArc elements with preferredLabel
    ns = {
        'link': 'http://www.xbrl.org/2003/linkbase',
        'xlink': 'http://www.w3.org/1999/xlink'
    }

    arcs = root.findall('.//link:presentationArc[@preferredLabel]', ns)

    print(f"\nFound {len(arcs)} presentation arcs with preferredLabel attribute")

    # Group by preferredLabel type
    label_types = {}
    for arc in arcs:
        label = arc.get('preferredLabel')
        if label not in label_types:
            label_types[label] = 0
        label_types[label] += 1

    print("\npreferredLabel types found:")
    for label_type, count in sorted(label_types.items(), key=lambda x: -x[1]):
        print(f"  {label_type}: {count} occurrences")

        # Check if this is a negation-related label
        if 'negat' in label_type.lower():
            print(f"    >>> NEGATION LABEL!")

            # Find which concepts use this label
            negated_arcs = [arc for arc in arcs if arc.get('preferredLabel') == label_type]
            for neg_arc in negated_arcs[:5]:  # Show first 5
                to_ref = neg_arc.get('{http://www.w3.org/1999/xlink}to')
                print(f"      Used by: {to_ref}")


if __name__ == "__main__":
    analyze_apple_filing()
    check_presentation_linkbase_raw()
