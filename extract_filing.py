#!/usr/bin/env python
"""
SEC Filing Extraction Tool

Extract sections from SEC filings and save as markdown.

Usage:
    python extract_filing.py AAPL 10-K --items "Item 1,Item 7,Item 8"
    python extract_filing.py MSFT 10-Q --items "Item 2" --notes
    python extract_filing.py TSLA 10-K --statements "IncomeStatement,BalanceSheet"
    python extract_filing.py GOOG 10-K --all
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract sections from SEC filings and save as markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_filing.py AAPL 10-K --items "Item 1,Item 7"
  python extract_filing.py MSFT 10-Q --items "Item 2" --notes
  python extract_filing.py TSLA 10-K --statements "IncomeStatement,BalanceSheet"
  python extract_filing.py GOOG 10-K --category "Statements"
  python extract_filing.py NVDA 10-K --all
  python extract_filing.py AAPL 10-K --list-items  # Show available items

Available statement types:
  IncomeStatement, BalanceSheet, CashFlowStatement,
  StatementOfEquity, ComprehensiveIncome, CoverPage, AllStatements

Available categories:
  Statements, Notes, Cover, Financial
        """
    )

    parser.add_argument("ticker", help="Company ticker symbol (e.g., AAPL, MSFT)")
    parser.add_argument("form", help="Form type (e.g., 10-K, 10-Q, 20-F)")

    # Extraction options
    parser.add_argument(
        "--items", "-i",
        help="Comma-separated list of items to extract (e.g., 'Item 1,Item 7,Item 8')"
    )
    parser.add_argument(
        "--statements", "-s",
        help="Comma-separated list of statements (e.g., 'IncomeStatement,BalanceSheet')"
    )
    parser.add_argument(
        "--category", "-c",
        help="Category to extract (e.g., 'Statements', 'Notes')"
    )
    parser.add_argument(
        "--notes", "-n",
        action="store_true",
        help="Include notes sections"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Extract all available items for the form type"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output filename (default: auto-generated)"
    )
    parser.add_argument(
        "--max-reports",
        type=int,
        help="Maximum number of reports per category"
    )

    # Info options
    parser.add_argument(
        "--list-items",
        action="store_true",
        help="List available items for the form type and exit"
    )
    parser.add_argument(
        "--filing-index",
        type=int,
        default=0,
        help="Index of filing to use (0=latest, 1=second latest, etc.)"
    )

    return parser.parse_args()


def list_form_items(form_type: str):
    """List all available items for a form type."""
    from edgar.llm_extraction import get_form_items, get_item_info

    items = get_form_items(form_type)
    if not items:
        print(f"No item definitions found for form type: {form_type}")
        print("Supported forms: 10-K, 10-Q, 20-F, 8-K, 6-K")
        return

    print(f"\nAvailable items for {form_type}:")
    print("=" * 60)

    current_group = None
    for item in items:
        info = get_item_info(form_type, item)
        if info:
            # Handle both "part" (10-K, 10-Q, 20-F) and "section" (8-K)
            group = info.get("part", "") or info.get("section", "")
            if group != current_group:
                current_group = group
                print(f"\n{group}")
                print("-" * 40)

            title = info.get("title", "")[:50]
            parent = info.get("parent", "")
            indent = "    " if parent else "  "
            print(f"{indent}{item}: {title}")

    print()


def get_filing(ticker: str, form_type: str, index: int = 0):
    """Get a filing for the given ticker and form type."""
    from edgar import Company

    print(f"Fetching {form_type} for {ticker}...")
    company = Company(ticker)
    filings = company.get_filings(form=form_type)

    if not filings:
        print(f"No {form_type} filings found for {ticker}")
        return None

    if index >= len(filings):
        print(f"Only {len(filings)} filings available, using latest")
        index = 0

    filing = filings[index]
    print(f"Found: {filing.form} filed {filing.filing_date} ({filing.accession_no})")
    return filing


def extract_and_save(
    filing,
    items: Optional[List[str]] = None,
    statements: Optional[List[str]] = None,
    category: Optional[str] = None,
    notes: bool = False,
    max_reports: Optional[int] = None,
    output_file: Optional[str] = None,
):
    """Extract sections and save to markdown file."""
    from edgar.llm_extraction import extract_filing_sections

    # Build extraction parameters
    kwargs = {}
    if items:
        kwargs["item"] = items
    if statements:
        kwargs["statement"] = statements
    if category:
        kwargs["category"] = category
    if notes:
        kwargs["notes"] = True
    if max_reports:
        kwargs["max_reports"] = max_reports

    # If no extraction specified, default to statements
    if not any([items, statements, category]):
        kwargs["statement"] = ["AllStatements"]
        if notes:
            kwargs["notes"] = True

    print(f"\nExtracting with parameters: {kwargs}")

    sections = extract_filing_sections(filing, **kwargs)

    if not sections:
        print("No sections extracted!")
        return None

    # Generate output filename
    if not output_file:
        ticker = getattr(filing, "company", "UNKNOWN")
        # Clean up company name for filename
        if hasattr(filing, "cik"):
            ticker = str(filing.cik)
        form = filing.form.replace("/", "-")
        date = filing.filing_date
        output_file = f"extraction_{ticker}_{form}_{date}.md"

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        # Header
        f.write("# SEC Filing Extraction\n\n")
        f.write(f"**Company:** {getattr(filing, 'company', 'N/A')}\n\n")
        f.write(f"**Form:** {filing.form}\n\n")
        f.write(f"**Filing Date:** {filing.filing_date}\n\n")
        f.write(f"**Accession Number:** {filing.accession_no}\n\n")
        f.write(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        # Table of contents
        f.write("## Table of Contents\n\n")
        for i, section in enumerate(sections, 1):
            anchor = section.title.lower().replace(" ", "-").replace(".", "")
            f.write(f"{i}. [{section.title}](#{anchor})\n")
        f.write("\n---\n\n")

        # Sections
        for section in sections:
            print(f"  Writing: {section.title} ({len(section.markdown):,} chars)")

            f.write(f"## {section.title}\n\n")
            f.write(f"**Source:** {section.source}\n\n")
            f.write(f"**Length:** {len(section.markdown):,} characters\n\n")
            f.write("### Content\n\n")
            f.write(section.markdown)
            f.write("\n\n---\n\n")

    print(f"\nOutput saved to: {output_file}")
    print(f"Total sections: {len(sections)}")
    total_chars = sum(len(s.markdown) for s in sections)
    print(f"Total content: {total_chars:,} characters")

    return output_file


def main():
    args = parse_args()

    # List items mode
    if args.list_items:
        list_form_items(args.form.upper())
        return 0

    # Get the filing
    filing = get_filing(args.ticker.upper(), args.form.upper(), args.filing_index)
    if not filing:
        return 1

    # Parse extraction parameters
    items = None
    if args.items:
        items = [item.strip() for item in args.items.split(",")]

    statements = None
    if args.statements:
        statements = [stmt.strip() for stmt in args.statements.split(",")]

    # Handle --all flag
    if args.all:
        from edgar.llm_extraction import get_form_items
        items = get_form_items(args.form.upper())
        if not items:
            print(f"No item definitions for {args.form}, extracting statements instead")
            statements = ["AllStatements"]

    # Extract and save
    output = extract_and_save(
        filing,
        items=items,
        statements=statements,
        category=args.category,
        notes=args.notes,
        max_reports=args.max_reports,
        output_file=args.output,
    )

    return 0 if output else 1


if __name__ == "__main__":
    sys.exit(main())
