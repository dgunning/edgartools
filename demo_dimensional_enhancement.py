#!/usr/bin/env python3
"""
Quick demonstration of the dimensional display enhancement.

Shows before/after comparison for Microsoft's income statement.
"""

import sys
import os
sys.path.append('/Users/dwight/PycharmProjects/edgartools')

from edgar import Company


def main():
    print("=" * 80)
    print("EdgarTools Dimensional Display Enhancement Demo")
    print("=" * 80)
    
    # Get Microsoft's latest 10-K filing
    company = Company("MSFT")
    filing = company.get_filings(form="10-K").head(1)[0]
    xbrl = filing.xbrl()
    income_stmt = xbrl.statements.income_statement()
    
    print(f"Filing: {filing.accession_number} ({filing.filing_date})")
    print()
    
    print("WITHOUT Dimensional Data (include_dimensions=False):")
    print("-" * 60)
    stmt_no_dims = income_stmt.render(include_dimensions=False)
    df_no_dims = stmt_no_dims.to_dataframe()
    print(f"Rows: {len(df_no_dims)}")
    print(stmt_no_dims)
    print()
    
    print("WITH Dimensional Data (include_dimensions=True - Default):")
    print("-" * 60)
    stmt_with_dims = income_stmt.render(include_dimensions=True)  # This is the default
    df_with_dims = stmt_with_dims.to_dataframe()
    print(f"Rows: {len(df_with_dims)}")
    print(stmt_with_dims)
    print()
    
    additional_rows = len(df_with_dims) - len(df_no_dims)
    print("Enhancement Summary:")
    print(f"  • Standard statement: {len(df_no_dims)} rows")
    print(f"  • Enhanced statement: {len(df_with_dims)} rows")
    print(f"  • Additional segment data: {additional_rows} rows")
    print()
    print("Usage:")
    print("  # Default behavior - includes dimensional data")
    print("  income_stmt = xbrl.statements.income_statement()")
    print("  print(income_stmt)")
    print()
    print("  # Disable dimensional data if desired")
    print("  df = income_stmt.to_dataframe(include_dimensions=False)")


if __name__ == "__main__":
    main()