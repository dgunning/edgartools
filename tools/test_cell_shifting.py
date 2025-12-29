"""
Test script for understanding llm_extraction.py cell shifting behavior.

Tests currency ($) and percent (%) cell preprocessing to verify:
1. Cells are correctly merged
2. Colspan is adjusted to maintain alignment
3. Edge cases are handled properly
"""

from bs4 import BeautifulSoup
from llm_extraction import preprocess_currency_cells, preprocess_percent_cells


def print_table_structure(soup, title):
    """Print table structure showing cells and colspan."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

    rows = soup.find_all("tr")
    for i, row in enumerate(rows, 1):
        cells = row.find_all(["td", "th"])
        print(f"Row {i}: ", end="")

        cell_info = []
        for cell in cells:
            text = cell.get_text(strip=True)
            colspan = cell.get("colspan", "1")
            cell_info.append(f"[{text}](cs={colspan})")

        print(" | ".join(cell_info))

        # Show total logical columns
        total_cols = sum(int(cell.get("colspan", 1)) for cell in cells)
        print(f"       Total columns: {total_cols}")


def test_case_1_basic_currency():
    """Test Case 1: Basic currency shifting - all rows have $ symbol."""
    print("\n" + "="*80)
    print("TEST CASE 1: Basic Currency Shifting")
    print("="*80)

    html = """
    <table>
      <tr><td>Metric</td><td>$</td><td>2023</td><td>$</td><td>2024</td></tr>
      <tr><td>Revenue</td><td>$</td><td>100</td><td>$</td><td>200</td></tr>
      <tr><td>Expenses</td><td>$</td><td>50</td><td>$</td><td>75</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_currency_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


def test_case_2_mixed_rows():
    """Test Case 2: Mixed rows - some with $, some with % or neither."""
    print("\n" + "="*80)
    print("TEST CASE 2: Mixed Currency/Percent Rows")
    print("="*80)

    html = """
    <table>
      <tr><td>Metric</td><td>Value</td><td>Change</td></tr>
      <tr><td>Revenue</td><td>$</td><td>100</td></tr>
      <tr><td>Growth</td><td>15</td><td>%</td></tr>
      <tr><td>Margin</td><td>20</td><td>%</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_currency_cells(table)
    preprocess_percent_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


def test_case_3_irregular_structure():
    """Test Case 3: Irregular structure with existing colspan."""
    print("\n" + "="*80)
    print("TEST CASE 3: Irregular Structure with Existing Colspan")
    print("="*80)

    html = """
    <table>
      <tr><td colspan="2">Header Span</td><td>Q1</td><td>Q2</td></tr>
      <tr><td>Revenue</td><td>$</td><td>100</td><td>$</td><td>120</td></tr>
      <tr><td colspan="2">Total Assets</td><td>$</td><td>500</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_currency_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


def test_case_4_edge_case_dollar_in_text():
    """Test Case 4: $ appears in text content (not standalone)."""
    print("\n" + "="*80)
    print("TEST CASE 4: Edge Case - $ in Text Content")
    print("="*80)

    html = """
    <table>
      <tr><td>Metric</td><td>Amount</td></tr>
      <tr><td>Price per share</td><td>$45.50</td></tr>
      <tr><td>Total</td><td>$</td><td>1000</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_currency_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


def test_case_5_percent_shifting():
    """Test Case 5: Percent shifting behavior."""
    print("\n" + "="*80)
    print("TEST CASE 5: Percent Shifting")
    print("="*80)

    html = """
    <table>
      <tr><td>Metric</td><td>2023</td><td>2024</td></tr>
      <tr><td>Growth Rate</td><td>15</td><td>%</td><td>20</td><td>%</td></tr>
      <tr><td>Margin</td><td>5.5</td><td>%</td><td>6.2</td><td>%</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_percent_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


def test_case_6_real_world_financial():
    """Test Case 6: Real-world financial statement structure."""
    print("\n" + "="*80)
    print("TEST CASE 6: Real-World Financial Statement")
    print("="*80)

    html = """
    <table>
      <tr><td></td><td colspan="2">2024</td><td colspan="2">2023</td></tr>
      <tr><td>Line Item</td><td>$</td><td>Amount</td><td>$</td><td>Amount</td></tr>
      <tr><td>Revenue</td><td>$</td><td>100,000</td><td>$</td><td>90,000</td></tr>
      <tr><td>Cost of Revenue</td><td>$</td><td>60,000</td><td>$</td><td>55,000</td></tr>
      <tr><td>Gross Profit</td><td>$</td><td>40,000</td><td>$</td><td>35,000</td></tr>
      <tr><td>Gross Margin</td><td>40</td><td>%</td><td>38.9</td><td>%</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    print_table_structure(table, "BEFORE preprocessing")

    preprocess_currency_cells(table)
    preprocess_percent_cells(table)

    print_table_structure(table, "AFTER preprocessing")

    # Verify alignment
    rows = table.find_all("tr")
    row_widths = [sum(int(cell.get("colspan", 1)) for cell in row.find_all(["td", "th"])) for row in rows]

    print(f"\nAlignment check: All rows have same width? {len(set(row_widths)) == 1}")
    print(f"Row widths: {row_widths}")


if __name__ == "__main__":
    print("="*80)
    print("CELL SHIFTING BEHAVIOR TEST SUITE")
    print("Testing llm_extraction.py preprocessing functions")
    print("="*80)

    try:
        test_case_1_basic_currency()
        test_case_2_mixed_rows()
        test_case_3_irregular_structure()
        test_case_4_edge_case_dollar_in_text()
        test_case_5_percent_shifting()
        test_case_6_real_world_financial()

        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)

    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
