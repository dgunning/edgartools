"""Test to understand placeholder column name issue."""
from bs4 import BeautifulSoup
import sys
sys.path.insert(0, '../')

from edgar.llm_helpers import html_to_json, list_of_dicts_to_table

# Test case 1: Table with quarter headers
html1 = """
<table>
<thead>
<tr>
<th></th>
<th colspan="3">Three Months Ended March 31,</th>
<th colspan="3">Three Months Ended June 30,</th>
</tr>
<tr>
<th></th>
<th>2024</th>
<th>2023</th>
<th>Change</th>
<th>2024</th>
<th>2023</th>
<th>Change</th>
</tr>
</thead>
<tbody>
<tr>
<td>Revenue</td>
<td>100</td>
<td>90</td>
<td>10%</td>
<td>110</td>
<td>95</td>
<td>15%</td>
</tr>
</tbody>
</table>
"""

# Test case 2: Table with simple quarter headers
html2 = """
<table>
<tr>
<td></td>
<td>Q1 2024</td>
<td>Q2 2024</td>
<td>Q3 2024</td>
<td>Q4 2024</td>
</tr>
<tr>
<td>Revenue</td>
<td>$100M</td>
<td>$110M</td>
<td>$120M</td>
<td>$130M</td>
</tr>
</table>
"""

# Test case 3: DAU table (from SNAP)
html3 = """
<table>
<thead>
<tr><th colspan="3"></th><th colspan="3" align="left">Quarterly Average Daily Active Users (1)
(in millions)</th><th colspan="3"></th></tr>
</thead>
<tbody>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td colspan="3"></td><td colspan="3" align="left">Global</td><td colspan="3"></td></tr>
<tr><td colspan="3"></td><td>2024</td><td>2023</td><td>2022</td><td></td><td></td><td></td></tr>
<tr><td>Q1</td><td></td><td></td><td>422</td><td>383</td><td>332</td><td></td><td></td><td></td></tr>
</tbody>
</table>
"""

def test_table(html, name):
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print('='*60)

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')

    text_blocks, records, title = html_to_json(table)

    print(f"\nTitle: {title}")
    print(f"Text blocks: {len(text_blocks)}")
    print(f"Records: {len(records)}")

    if records:
        print("\nFirst 3 records:")
        for i, rec in enumerate(records[:3]):
            print(f"  {i}: {rec}")

    markdown = list_of_dicts_to_table(records)
    print(f"\nMarkdown output:")
    print(markdown)

# Run tests
test_table(html1, "Multi-row headers with quarter periods")
test_table(html2, "Simple quarter headers in td tags")
test_table(html3, "SNAP DAU table")
