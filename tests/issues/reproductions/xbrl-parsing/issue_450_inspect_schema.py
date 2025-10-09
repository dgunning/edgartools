"""
Inspect Apple's XBRL schema to verify abstract attribute presence

This will help us understand if:
1. The schema has abstract="true" on the elements
2. Our parser is correctly reading it
"""

from edgar import Company
import re

def inspect_schema():
    print("=" * 80)
    print("ISSUE #450: Schema Abstract Attribute Inspection")
    print("=" * 80)
    print()

    # Get Apple's latest 10-Q
    company = Company("AAPL")
    tenq = company.get_filings(form="10-Q").latest(1)
    xbrl = tenq.xbrl()

    print(f"Filing: {tenq.form} - {tenq.filing_date}")
    print()

    # Check element catalog for specific concepts
    concepts_to_check = [
        'us-gaap_StatementOfStockholdersEquityAbstract',
        'us-gaap_IncreaseDecreaseInStockholdersEquityRollForward',
        'us-gaap_StockholdersEquity',
        'us-gaap_StatementTable',
        'us-gaap_StatementEquityComponentsAxis',
    ]

    print("Element Catalog Inspection:")
    print("-" * 80)

    for concept in concepts_to_check:
        if concept in xbrl.element_catalog:
            elem = xbrl.element_catalog[concept]
            print(f"{concept}:")
            print(f"  name: {elem.name}")
            print(f"  abstract: {elem.abstract}")
            print(f"  data_type: {elem.data_type}")
            print(f"  period_type: {elem.period_type}")
            print()
        else:
            print(f"{concept}: NOT IN CATALOG")
            print()

    print()
    print("=" * 80)
    print("SCHEMA FILE INSPECTION")
    print("=" * 80)
    print()

    # Try to access schema content directly from the parser
    if hasattr(xbrl, 'parser') and hasattr(xbrl.parser, 'schema_parser'):
        schema_parser = xbrl.parser.schema_parser

        # Look for schema files
        print("Schema parser element catalog size:", len(schema_parser.element_catalog))
        print()

        # Check if any elements have abstract=True
        abstract_count = sum(1 for elem in schema_parser.element_catalog.values() if elem.abstract)
        print(f"Elements with abstract=True: {abstract_count}")
        print()

        # Show some abstract elements if any exist
        if abstract_count > 0:
            print("Sample abstract elements:")
            count = 0
            for name, elem in schema_parser.element_catalog.items():
                if elem.abstract and count < 10:
                    print(f"  {name}: abstract={elem.abstract}")
                    count += 1
        else:
            print("⚠️  NO ABSTRACT ELEMENTS FOUND IN CATALOG!")

    print()

    # Try to fetch and inspect raw schema file
    print("=" * 80)
    print("RAW SCHEMA FILE CONTENT CHECK")
    print("=" * 80)
    print()

    # Get the filing object to access files
    try:
        # Try to get the schema file directly
        attachments = tenq.attachments

        # Look for .xsd files
        xsd_files = [att for att in attachments if att.document.endswith('.xsd')]

        print(f"Found {len(xsd_files)} .xsd files")
        print()

        if xsd_files:
            # Check the company-specific schema (usually aapl-*.xsd)
            company_xsd = [x for x in xsd_files if 'aapl' in x.document.lower()]

            if company_xsd:
                xsd_file = company_xsd[0]
                print(f"Inspecting: {xsd_file.document}")
                print()

                # Get the content
                content = xsd_file.download()

                # Search for abstract="true" in the content
                abstract_true_count = len(re.findall(r'abstract="true"', content, re.IGNORECASE))
                abstract_false_count = len(re.findall(r'abstract="false"', content, re.IGNORECASE))

                print(f'Occurrences of abstract="true": {abstract_true_count}')
                print(f'Occurrences of abstract="false": {abstract_false_count}')
                print()

                # Find specific concepts in the schema
                for concept in concepts_to_check[:3]:
                    # Extract just the local name (after the namespace)
                    local_name = concept.split('_', 1)[1] if '_' in concept else concept

                    # Search for this element definition
                    pattern = f'<xs:element[^>]+(?:name|id)="{local_name}"[^>]*>'
                    matches = re.findall(pattern, content, re.IGNORECASE)

                    if matches:
                        print(f"Found definition for {local_name}:")
                        for match in matches[:2]:  # Show first 2 matches
                            print(f"  {match}")
                        print()

    except Exception as e:
        print(f"Error accessing schema files: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    inspect_schema()
