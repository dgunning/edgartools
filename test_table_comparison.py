"""
Compare llm_extraction.py vs edgar.documents table extraction
Test Case: PLTR 10-K Item 8 (Financial Statements)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from edgar import Company
from edgar.llm_extraction import extract_filing_sections, ExtractedSection
from edgar.documents import HTMLParser, ParserConfig
import pandas as pd


def test_pltr_10k_item8():
    """Compare both approaches on PLTR 10-K Item 8"""

    print("=" * 80)
    print("TABLE EXTRACTION COMPARISON TEST")
    print("Test Case: Palantir Technologies (PLTR) 10-K Item 8")
    print("=" * 80)
    print()

    # Get PLTR's latest 10-K
    print("[*] Fetching PLTR latest 10-K...")
    company = Company("PLTR")
    filings = company.get_filings(form="10-K")

    if not filings:
        print("[X] No 10-K filings found")
        return

    filing = filings[0]
    print(f"[OK] Found: {filing.form} filed {filing.filing_date}")
    print(f"     Accession: {filing.accession_no}")
    print()

    # =========================================================================
    # APPROACH 1: llm_extraction.py
    # =========================================================================
    print("=" * 80)
    print("APPROACH 1: llm_extraction.py")
    print("=" * 80)
    print()

    print("[*] Extracting Item 8 using llm_extraction...")
    try:
        llm_sections = extract_filing_sections(filing, item=["Item 8"])

        if not llm_sections:
            print("[X] No sections extracted by llm_extraction")
            llm_markdown = None
            llm_table_count = 0
        else:
            llm_section = llm_sections[0]
            llm_markdown = llm_section.markdown

            # Count tables in markdown
            llm_table_count = llm_markdown.count("| --- |") if llm_markdown else 0

            print(f"[OK] Extracted: {llm_section.title}")
            print(f"     Source: {llm_section.source}")
            print(f"     Length: {len(llm_markdown):,} characters")
            print(f"     Tables found: {llm_table_count}")
            print()

            # Save to file
            output_file = "test_output_llm_extraction.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# {llm_section.title}\n\n")
                f.write(llm_markdown)
            print(f"[SAVE] Saved to: {output_file}")

            # Show first 2000 characters
            print("\n" + "-" * 80)
            print("PREVIEW (first 2000 chars):")
            print("-" * 80)
            print(llm_markdown[:2000])
            if len(llm_markdown) > 2000:
                print("\n... (truncated)")

    except Exception as e:
        print(f"[X] Error in llm_extraction: {e}")
        import traceback
        traceback.print_exc()
        llm_markdown = None
        llm_table_count = 0

    print("\n")

    # =========================================================================
    # APPROACH 2: edgar.documents
    # =========================================================================
    print("=" * 80)
    print("APPROACH 2: edgar.documents (TableNode + to_dataframe)")
    print("=" * 80)
    print()

    print("[*] Extracting Item 8 using edgar.documents...")
    item8_section = None
    section_tables = []
    try:
        # Get parsed document
        document = filing.obj().document

        print(f"[OK] Document parsed")
        print(f"     Total sections: {len(document.sections)}")
        print(f"     Total tables: {len(document.tables)}")
        print()

        # Get Item 8 section
        try:
            item8_section = document.sections.get_item("8")
        except Exception as e:
            print(f"[WARN] Could not get Item 8 via get_item: {e}")
            # Try alternative
            item8_section = document.get_section("item_8")

        if item8_section:
            print(f"[OK] Found Item 8 section: {item8_section.title}")

            # Get tables in this section
            section_tables = item8_section.tables()
            print(f"     Tables in Item 8: {len(section_tables)}")
            print()

            # Convert first few tables to DataFrame and markdown
            doc_outputs = []

            for i, table in enumerate(section_tables[:5]):  # First 5 tables
                print(f"\n[TABLE] Table {i+1}:")
                print(f"        Caption: {table.caption or 'N/A'}")
                print(f"        Type: {table.table_type.name}")
                print(f"        Dimensions: {len(table.rows)} rows")

                # Try to_dataframe
                try:
                    df = table.to_dataframe()
                    print(f"        [OK] DataFrame shape: {df.shape}")

                    # Save DataFrame as markdown
                    df_markdown = df.to_markdown(index=True)
                    doc_outputs.append(f"\n### Table {i+1}: {table.caption or 'Unnamed'}\n\n{df_markdown}\n")

                    # Show preview
                    print(f"\n   Preview (first 5 rows):")
                    print(df.head().to_string(max_colwidth=30))

                except Exception as e:
                    print(f"        [X] to_dataframe error: {e}")

            # Save combined output
            if doc_outputs:
                output_file = "test_output_edgar_documents.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"# {item8_section.title}\n\n")
                    f.write("".join(doc_outputs))
                print(f"\n[SAVE] Saved to: {output_file}")
        else:
            print("[X] Could not find Item 8 section")

    except Exception as e:
        print(f"[X] Error in edgar.documents: {e}")
        import traceback
        traceback.print_exc()

    print("\n")

    # =========================================================================
    # DETAILED TABLE ANALYSIS
    # =========================================================================
    print("=" * 80)
    print("DETAILED TABLE ANALYSIS")
    print("=" * 80)
    print()

    print("[ANALYZE] Analyzing first financial table from both approaches...")
    print()

    # Extract first table from each approach
    if llm_markdown:
        # Find first table in llm_extraction output
        lines = llm_markdown.split("\n")
        in_table = False
        llm_first_table = []

        for line in lines:
            if "| ---" in line or ("|" in line and not in_table):
                in_table = True

            if in_table:
                llm_first_table.append(line)

                # Stop after table ends
                if line.strip() == "" and len(llm_first_table) > 5:
                    break

        if llm_first_table:
            print("[OUTPUT] llm_extraction.py first table:")
            print("-" * 80)
            print("\n".join(llm_first_table[:20]))  # First 20 lines
            print("...")
            print()

    if item8_section and section_tables:
        first_table = section_tables[0]
        print("[OUTPUT] edgar.documents first table:")
        print("-" * 80)
        print(f"Caption: {first_table.caption}")
        print(f"Headers: {len(first_table.headers)} rows")
        print(f"Data rows: {len(first_table.rows)}")
        print()

        try:
            df = first_table.to_dataframe()
            print("DataFrame representation:")
            print(df.head(10).to_string(max_colwidth=30))
        except Exception as e:
            print(f"Error creating DataFrame: {e}")

    print("\n")
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("[FILES] Output files created:")
    print("   - test_output_llm_extraction.md")
    print("   - test_output_edgar_documents.md")
    print()
    print("[>>] Compare these files to see differences in:")
    print("   1. Currency cell merging ($)")
    print("   2. Percent cell merging (%)")
    print("   3. Column alignment")
    print("   4. Header handling")
    print()


if __name__ == "__main__":
    test_pltr_10k_item8()
