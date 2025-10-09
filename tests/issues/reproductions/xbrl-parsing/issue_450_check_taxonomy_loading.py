"""
Check which taxonomy files are being loaded for Apple's 10-Q
"""

from edgar import Company

def check_taxonomy_loading():
    print("=" * 80)
    print("ISSUE #450: Taxonomy File Loading Check")
    print("=" * 80)
    print()

    # Get Apple's latest 10-Q
    company = Company("AAPL")
    tenq = company.get_filings(form="10-Q").latest(1)

    print(f"Filing: {tenq.form} - {tenq.filing_date}")
    print()

    # List all XSD files in the filing
    attachments = tenq.attachments
    xsd_files = [att for att in attachments if att.document.endswith('.xsd')]

    print(f"Total .xsd files in filing: {len(xsd_files)}")
    print()

    print("Schema files:")
    print("-" * 80)
    for xsd in xsd_files:
        print(f"  {xsd.document}")
        print(f"    Description: {xsd.description}")
        print()

    print()

    # Now check what xbrl.parser has loaded
    xbrl = tenq.xbrl()

    if hasattr(xbrl, 'parser') and hasattr(xbrl.parser, 'schema_parser'):
        schema_parser = xbrl.parser.schema_parser

        print("Schema Parser State:")
        print("-" * 80)
        print(f"  Element catalog size: {len(schema_parser.element_catalog)}")
        print()

        # Check for us-gaap concepts
        us_gaap_count = sum(1 for name in schema_parser.element_catalog.keys() if name.startswith('us-gaap_'))
        dei_count = sum(1 for name in schema_parser.element_catalog.keys() if name.startswith('dei_'))
        aapl_count = sum(1 for name in schema_parser.element_catalog.keys() if name.startswith('aapl_'))

        print(f"  US-GAAP concepts: {us_gaap_count}")
        print(f"  DEI concepts: {dei_count}")
        print(f"  AAPL concepts: {aapl_count}")
        print()

        # Sample US-GAAP concepts
        print("Sample US-GAAP concepts in catalog:")
        count = 0
        for name in sorted(schema_parser.element_catalog.keys()):
            if name.startswith('us-gaap_') and count < 10:
                elem = schema_parser.element_catalog[name]
                print(f"  {name}: abstract={elem.abstract}, type={elem.data_type}")
                count += 1
        print()

    # Check if taxonomy schemas are accessible
    print("=" * 80)
    print("CHECKING FOR US-GAAP TAXONOMY SCHEMAS")
    print("=" * 80)
    print()

    # The us-gaap schemas should be referenced but might not be in attachments
    # They are typically external references to xbrl.fasb.org

    # Let's check what's referenced in the instance document
    try:
        # Get the instance XML
        instance_xml = None
        for att in attachments:
            if att.document.endswith('.xml') and not att.document.endswith('_cal.xml') and not att.document.endswith('_def.xml') and not att.document.endswith('_lab.xml') and not att.document.endswith('_pre.xml'):
                instance_xml = att
                break

        if instance_xml:
            print(f"Instance document: {instance_xml.document}")
            content = instance_xml.download()

            # Look for schema references
            import re
            schema_refs = re.findall(r'<link:schemaRef[^>]*xlink:href="([^"]+)"', content)

            print()
            print("Schema references in instance document:")
            for ref in schema_refs:
                print(f"  {ref}")

    except Exception as e:
        print(f"Error checking instance document: {e}")

    print()
    print("=" * 80)
    print("CHECK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    check_taxonomy_loading()
