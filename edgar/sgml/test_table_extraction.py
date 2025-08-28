"""
Test extraction of financial tables as DataFrames from HTML reports
"""

from pathlib import Path
from edgar.files.html import Document
from edgar.sgml.table_to_dataframe import FinancialTableExtractor, extract_statement_dataframe


def test_aapl_income_statement_extraction():
    """Test extracting AAPL income statement (R2.htm) as DataFrame"""
    
    # Read the R2.htm file
    r2_path = Path("tests/fixtures/attachments/aapl/20250329/R2.htm")
    with open(r2_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Extract DataFrame using convenience function
    df = extract_statement_dataframe(html_content)
    
    print("\n=== Extracted DataFrame ===")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Index (first 10): {list(df.index[:10])}")
    print("\nMetadata:")
    print(f"  Currency: {df.attrs.get('currency')}")
    print(f"  Units: {df.attrs.get('units')}")
    print(f"  Scaling Factor: {df.attrs.get('scaling_factor')}")
    print(f"  Period Type: {df.attrs.get('period_type')}")
    
    print("\n=== DataFrame Content ===")
    print(df.head(10))
    
    # Test specific extraction using Document class
    print("\n=== Using Document class directly ===")
    document = Document.parse(html_content)
    print(f"Number of tables found: {len(document.tables)}")
    
    if document.tables:
        table = document.tables[0]
        print(f"Table dimensions: {table.processed_row_count} rows x {table.processed_column_count} columns")
        
        # Extract using FinancialTableExtractor
        df2 = FinancialTableExtractor.extract_table_to_dataframe(table)
        print("\n=== Direct extraction result ===")
        print(df2.head())
        
        # Check data types
        print("\n=== Data types ===")
        print(df2.dtypes)
        
        # Sample some values
        print("\n=== Sample values ===")
        if not df2.empty:
            for col in df2.columns[:2]:  # First two period columns
                print(f"\n{col}:")
                # Check if column has numeric data
                if df2[col].dtype in ['float64', 'int64']:
                    numeric_values = df2[col].dropna()
                    if not numeric_values.empty:
                        print(f"  Min: {numeric_values.min():,.0f}")
                        print(f"  Max: {numeric_values.max():,.0f}")
                        print(f"  Mean: {numeric_values.mean():,.0f}")
                else:
                    print(f"  Data type: {df2[col].dtype}")
                    print(f"  Sample values: {df2[col].head(3).tolist()}")


def test_multi_level_headers():
    """Test handling of multi-level headers in financial tables"""
    
    # Create a simple test HTML with multi-level headers
    test_html = """
    <html>
    <body>
    <table>
    <tr>
        <th rowspan="2">Line Items</th>
        <th colspan="2">3 Months Ended</th>
        <th colspan="2">6 Months Ended</th>
    </tr>
    <tr>
        <th>Mar 31, 2025</th>
        <th>Mar 31, 2024</th>
        <th>Mar 31, 2025</th>
        <th>Mar 31, 2024</th>
    </tr>
    <tr>
        <td>Revenue</td>
        <td>$1,000</td>
        <td>$900</td>
        <td>$2,100</td>
        <td>$1,800</td>
    </tr>
    <tr>
        <td>Cost of Sales</td>
        <td>($600)</td>
        <td>($500)</td>
        <td>($1,200)</td>
        <td>($1,000)</td>
    </tr>
    </table>
    </body>
    </html>
    """
    
    df = extract_statement_dataframe(test_html)
    print("\n=== Multi-level header test ===")
    print(df)


def test_cover_page_r1():
    """Test extraction from R1.htm (Cover Page) which has vertical layout"""
    
    # Read the R1.htm file
    r1_path = Path("tests/fixtures/attachments/aapl/20250329/R1.htm")
    with open(r1_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print("\n=== Testing R1 (Cover Page) ===")
    
    # First look at the raw table structure
    document = Document.parse(html_content)
    if document.tables:
        table = document.tables[0]
        processed = table._processed
        if processed:
            print(f"Raw headers: {processed.headers}")
            print(f"Number of data rows: {len(processed.data_rows)}")
            if processed.data_rows:
                print(f"First data row: {processed.data_rows[0][:3]}")  # First 3 cells
                print(f"Second data row: {processed.data_rows[1][:3]}")
                print(f"Third data row: {processed.data_rows[2][:3]}")
    
    # Extract DataFrame
    df = extract_statement_dataframe(html_content)
    print(f"\nExtracted DataFrame shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Index (first 10): {list(df.index[:10])}")
    
    if not df.empty:
        print("\nFirst few rows:")
        print(df.head(10))
        
        # Check for duplication - the index values should not appear in the data
        print("\nChecking for duplication issue:")
        print(f"First index value: '{df.index[1]}'")
        print(f"First data value in first column: '{df.iloc[1, 0]}'")
        print(f"Are they the same? {df.index[1] == df.iloc[1, 0]}")
        
        # Show what we expect vs what we got
        print("\nExpected structure:")
        print("Index should contain: Document Type, Document Quarterly Report, etc.")
        print("Columns should contain the actual values: 10-Q, true, etc.")
        print("\nActual first row:")
        print(f"Index: {df.index[1]}, Values: {list(df.iloc[1])}")


def test_complex_report_r21():
    """Test extraction from R21.htm which has tables within tables"""
    
    # Read the R21.htm file
    r21_path = Path("tests/fixtures/attachments/aapl/20250329/R21.htm")
    with open(r21_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print("\n=== Testing R21 (Complex Table Structure) ===")
    
    # Parse document to see structure
    document = Document.parse(html_content)
    print(f"Number of tables found: {len(document.tables)}")
    
    for i, table in enumerate(document.tables[:3]):  # Look at first 3 tables
        print(f"\nTable {i}:")
        print(f"  Rows: {table.row_count}")
        print(f"  Approx columns: {table.approximate_column_count}")
        
    # Try extraction
    df = extract_statement_dataframe(html_content)
    print(f"\nExtracted DataFrame shape: {df.shape}")
    if not df.empty:
        print("\nFirst few rows:")
        print(df.head())
        print("\nData types:")
        print(df.dtypes)


if __name__ == "__main__":
    test_aapl_income_statement_extraction()
    print("\n" + "="*80 + "\n")
    test_multi_level_headers()
    print("\n" + "="*80 + "\n")
    test_cover_page_r1()
    print("\n" + "="*80 + "\n")
    test_complex_report_r21()