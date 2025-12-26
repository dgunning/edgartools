"""
EdgarTools Table Extraction Examples

Demonstrates all 5 methods to extract tables from SEC filings.
"""

from edgar import Company
from edgar.llm_extraction import extract_filing_sections


def example1_xbrl_statements():
    """
    EXAMPLE 1: XBRL Financial Statements (BEST for financials)

    Use Case: Extract balance sheet, income statement, cash flow
    """
    print("=" * 80)
    print("EXAMPLE 1: XBRL Financial Statements")
    print("=" * 80)

    # Get Apple's latest 10-K
    company = Company("AAPL")
    filing = company.get_filings(form="10-K")[0]

    print(f"\nFiling: {filing.form} filed {filing.filing_date}")

    # Method 1: Via filing.xbrl()
    xbrl = filing.xbrl()

    # Get statements
    balance_sheet = xbrl.balance_sheet
    income_statement = xbrl.income_statement
    cash_flow = xbrl.cash_flow_statement

    print("\n[Balance Sheet]")
    print(balance_sheet)

    print("\n[Income Statement]")
    print(income_statement)

    # Convert to DataFrame
    df = balance_sheet.to_dataframe()
    print(f"\nDataFrame shape: {df.shape}")
    print(f"Columns (periods): {df.columns.tolist()}")

    # Export
    df.to_csv("apple_balance_sheet.csv")
    print("Saved to: apple_balance_sheet.csv")

    # Method 2: Via TenK shortcuts
    tenk = filing.obj()
    balance_sheet_v2 = tenk.balance_sheet
    income_statement_v2 = tenk.income_statement

    print(f"\nSame result via TenK: {balance_sheet_v2 == balance_sheet}")


def example2_document_tables():
    """
    EXAMPLE 2: Document.tables (All HTML tables)

    Use Case: Extract all tables including footnotes, schedules
    """
    print("\n\n")
    print("=" * 80)
    print("EXAMPLE 2: Document.tables (All HTML Tables)")
    print("=" * 80)

    company = Company("AAPL")
    filing = company.get_filings(form="10-K")[0]

    # Get document
    doc = filing.obj().document

    # Get all tables
    tables = doc.tables

    print(f"\nTotal tables in document: {len(tables)}")

    # Show first 5 tables
    for i, table in enumerate(tables[:5]):
        print(f"\nTable {i+1}:")
        print(f"  Caption: {table.caption or 'N/A'}")
        print(f"  Type: {table.table_type.name}")
        print(f"  Dimensions: {len(table.rows)} rows x {len(table.headers)} header rows")

        # Convert to DataFrame
        try:
            df = table.to_dataframe()
            print(f"  DataFrame: {df.shape}")

            # Show first few rows
            print("\n  Preview:")
            print(df.head(3).to_string(max_colwidth=30))
        except Exception as e:
            print(f"  Error: {e}")

    # Filter financial tables
    financial_tables = [t for t in tables if t.table_type.name == "FINANCIAL"]
    print(f"\nFinancial tables: {len(financial_tables)}")


def example3_llm_extraction():
    """
    EXAMPLE 3: llm_extraction (Markdown for Items)

    Use Case: Extract Item 8 as clean Markdown for LLM/AI
    """
    print("\n\n")
    print("=" * 80)
    print("EXAMPLE 3: llm_extraction (Markdown)")
    print("=" * 80)

    company = Company("AAPL")
    filing = company.get_filings(form="10-K")[0]

    # Extract Item 8 (Financial Statements)
    sections = extract_filing_sections(filing, item=["Item 8"])

    if sections:
        section = sections[0]

        print(f"\nExtracted: {section.title}")
        print(f"Source: {section.source}")
        print(f"Length: {len(section.markdown):,} characters")

        # Count tables
        table_count = section.markdown.count("| --- |")
        print(f"Tables found: {table_count}")

        # Show first 1000 chars
        print("\nPreview:")
        print("-" * 80)
        print(section.markdown[:1000])
        print("...")

        # Save to file
        output_file = "apple_item8.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# {section.title}\n\n")
            f.write(section.markdown)

        print(f"\nSaved to: {output_file}")


def example4_13f_holdings():
    """
    EXAMPLE 4: 13F Holdings Tables

    Use Case: Extract institutional holdings from 13F-HR
    """
    print("\n\n")
    print("=" * 80)
    print("EXAMPLE 4: 13F Holdings Tables")
    print("=" * 80)

    # Get Berkshire Hathaway's latest 13F
    company = Company("BRK-A")
    filings = company.get_filings(form="13F-HR")

    if not filings:
        print("No 13F-HR filings found")
        return

    filing = filings[0]
    print(f"\nFiling: {filing.form} filed {filing.filing_date}")

    # Get 13F object
    thirteenf = filing.obj()

    # Get holdings
    holdings = thirteenf.holdings

    print(f"\nTotal holdings: {len(holdings)}")

    # Convert to DataFrame
    df = holdings.to_dataframe()

    print(f"DataFrame shape: {df.shape}")
    print("\nTop 10 holdings:")
    print(df.head(10).to_string(max_colwidth=40))

    # Export
    df.to_csv("berkshire_holdings.csv")
    print("\nSaved to: berkshire_holdings.csv")


def example5_ownership_forms():
    """
    EXAMPLE 5: Ownership Forms (Insider Transactions)

    Use Case: Extract insider trading from Form 4
    """
    print("\n\n")
    print("=" * 80)
    print("EXAMPLE 5: Ownership Forms (Insider Transactions)")
    print("=" * 80)

    # Get Tesla's latest Form 4
    company = Company("TSLA")
    filings = company.get_filings(form="4")

    if not filings:
        print("No Form 4 filings found")
        return

    filing = filings[0]
    print(f"\nFiling: {filing.form} filed {filing.filing_date}")

    # Get Form 4 object
    form4 = filing.obj()

    # Get transactions
    transactions = form4.non_derivative_transactions

    print(f"\nNon-derivative transactions: {len(transactions)}")

    # Show transactions
    for i, txn in enumerate(transactions[:5]):
        print(f"\nTransaction {i+1}:")
        print(f"  Security: {txn.security_title}")
        print(f"  Date: {txn.transaction_date}")
        print(f"  Code: {txn.transaction_code}")
        print(f"  Shares: {txn.transaction_shares:,}")
        if txn.transaction_price_per_share:
            print(f"  Price: ${txn.transaction_price_per_share:.2f}")
        print(f"  Owned After: {txn.shares_owned_following_transaction:,}")


def example6_combined():
    """
    EXAMPLE 6: Combined Approach

    Use Case: Get all financial tables using multiple methods
    """
    print("\n\n")
    print("=" * 80)
    print("EXAMPLE 6: Combined Approach (All Methods)")
    print("=" * 80)

    company = Company("PLTR")
    filing = company.get_filings(form="10-K")[0]

    print(f"\nFiling: {filing.form} filed {filing.filing_date}")

    results = {}

    # 1. XBRL Statements
    print("\n[1] Extracting XBRL statements...")
    try:
        xbrl = filing.xbrl()
        results['xbrl_balance_sheet'] = xbrl.balance_sheet.to_dataframe()
        results['xbrl_income'] = xbrl.income_statement.to_dataframe()
        results['xbrl_cash_flow'] = xbrl.cash_flow_statement.to_dataframe()
        print(f"    Extracted {len(results)} XBRL statements")
    except Exception as e:
        print(f"    Error: {e}")

    # 2. HTML Tables
    print("\n[2] Extracting HTML tables...")
    try:
        doc = filing.obj().document
        tables = doc.tables

        # Get financial tables
        financial_tables = [t for t in tables if t.table_type.name == "FINANCIAL"]

        for i, table in enumerate(financial_tables[:5]):
            df = table.to_dataframe()
            results[f'html_table_{i}'] = df

        print(f"    Extracted {len(financial_tables)} financial tables")
    except Exception as e:
        print(f"    Error: {e}")

    # 3. Markdown Extraction
    print("\n[3] Extracting Item 8 as Markdown...")
    try:
        sections = extract_filing_sections(filing, item=["Item 8"])
        if sections:
            results['markdown_item8'] = sections[0].markdown
            table_count = sections[0].markdown.count("| --- |")
            print(f"    Extracted Item 8 with {table_count} tables")
    except Exception as e:
        print(f"    Error: {e}")

    # Summary
    print(f"\n" + "=" * 80)
    print(f"TOTAL EXTRACTED:")
    print("=" * 80)
    for key, value in results.items():
        if hasattr(value, 'shape'):
            print(f"  {key}: DataFrame {value.shape}")
        else:
            print(f"  {key}: {len(value):,} chars")


if __name__ == "__main__":
    print("\n")
    print("*" * 80)
    print("EDGARTOOLS TABLE EXTRACTION EXAMPLES")
    print("*" * 80)

    # Run examples
    example1_xbrl_statements()
    example2_document_tables()
    example3_llm_extraction()
    # example4_13f_holdings()  # Uncomment if you want to run
    # example5_ownership_forms()  # Uncomment if you want to run
    example6_combined()

    print("\n\n")
    print("*" * 80)
    print("ALL EXAMPLES COMPLETE")
    print("*" * 80)
