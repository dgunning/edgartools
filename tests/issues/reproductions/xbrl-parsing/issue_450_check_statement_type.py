"""
Check what statement_type value is being used in render_statement
"""

from edgar import Company
from edgar.xbrl import rendering

# Monkey-patch render_statement to log the statement_type
original_render_statement = rendering.render_statement

def patched_render_statement(statement_data, periods_to_display, statement_title, statement_type, *args, **kwargs):
    print(f"DEBUG: render_statement called with statement_type='{statement_type}', type={type(statement_type)}")
    print(f"  statement_title='{statement_title}'")
    print(f"  Matches 'StatementOfEquity': {statement_type == 'StatementOfEquity'}")
    return original_render_statement(statement_data, periods_to_display, statement_title, statement_type, *args, **kwargs)

rendering.render_statement = patched_render_statement

# Get Apple's 10-Q
company = Company("AAPL")
tenq = company.get_filings(form="10-Q").latest(1)
xbrl = tenq.xbrl()

# Get the equity statement
print("Getting statement of equity...")
equity_stmt = xbrl.statements.statement_of_equity()

print("\nConverting to dataframe...")
df = equity_stmt.to_dataframe()

print(f"\nDataFrame has {len(df)} rows")

# Check labels
equity_concept = 'us-gaap_StockholdersEquity'
equity_rows = df[df['concept'] == equity_concept]
print(f"\nTotal Stockholders' Equity rows: {len(equity_rows)}")
for idx, row in equity_rows.iterrows():
    print(f"  [{idx}] {row['label']}")
