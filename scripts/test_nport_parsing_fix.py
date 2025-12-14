"""Test script for NPORT-P parsing fix (edgartools-582)."""

from edgar import Filing


def test_nport_parsing():
    """Test that NPORT-P filing can be parsed without errors."""
    print("Testing NPORT-P parsing fix...")
    print("=" * 60)

    # Create the filing that was failing
    filing = Filing(
        form='NPORT-P',
        filing_date='2025-08-27',
        company='PRUDENTIAL SERIES FUND',
        cik=711175,
        accession_no='0001752724-25-208163'
    )

    print(f"Filing: {filing.form} - {filing.company}")
    print(f"CIK: {filing.cik}")
    print(f"Accession: {filing.accession_no}")
    print(f"Date: {filing.filing_date}")
    print()

    try:
        # This was causing AttributeError before the fix
        print("Attempting to parse document...")

        # For NPORT-P, we need to get the HTML first
        html = filing.html()
        print(f"✓ HTML retrieved ({len(html)} bytes)")

        # Now parse it with HTMLParser
        from edgar.documents import HTMLParser, ParserConfig

        config = ParserConfig(form='NPORT-P')
        parser = HTMLParser(config)

        print("Parsing with HTMLParser...")
        document = parser.parse(html)

        print("✓ SUCCESS: Document parsed without error!")
        print()
        print(f"Document type: {type(document)}")
        print(f"Document has {len(document.root.children) if hasattr(document.root, 'children') else 'N/A'} root children")

        if hasattr(document, 'sections'):
            print(f"Sections detected: {len(document.sections)}")
            if document.sections:
                print(f"Section keys: {list(document.sections.keys())[:5]}...")

        return True

    except AttributeError as e:
        print("✗ FAILED: AttributeError still occurs")
        print(f"Error: {e}")
        return False

    except Exception as e:
        print("✗ FAILED: Different error occurred")
        print(f"Error type: {type(e).__name__}")
        print(f"Error: {e}")
        return False


if __name__ == '__main__':
    success = test_nport_parsing()
    exit(0 if success else 1)
