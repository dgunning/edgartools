"""
XBRL2 Module - Enhanced XBRL Processing for EdgarTools

This module provides enhanced parsing and processing of XBRL data,
with support for statement standardization and multi-period statement stitching.

Example usage:

    from edgar import Company
    from edgar.xbrl import XBRL, XBRLS

    # Parse a single filing
    company = Company("AAPL")
    filing = company.latest_10k()
    xbrl = XBRL.from_filing(filing)

    # Access statements from a single filing
    balance_sheet = xbrl.statements.balance_sheet()
    income_statement = xbrl.statements.income_statement()

    # Render the statement or convert to DataFrame
    print(balance_sheet.render())
    df = income_statement.to_dataframe()

    # For multi-period analysis, use XBRLS to stitch statements together
    filings = company.latest("10-K", 3)  # Get 3 years of 10-K filings
    xbrls = XBRLS.from_filings(filings)

    # Access stitched statements showing multiple years of data
    stitched_income = xbrls.statements.income_statement()

    # Render the stitched statement or convert to DataFrame
    print(stitched_income.render())
    df = stitched_income.to_dataframe()
"""

from edgar.xbrl.facts import FactQuery, FactsView
from edgar.xbrl.rendering import RenderedStatement
from edgar.xbrl.standardization import StandardConcept
from edgar.xbrl.statements import Statement, Statements, StitchedStatement, StitchedStatements

# Export statement stitching functionality
from edgar.xbrl.stitching import (
    XBRLS,
    StatementStitcher,
    StitchedFactQuery,
    StitchedFactsView,
    render_stitched_statement,
    stitch_statements,
    to_pandas,
)
from edgar.xbrl.xbrl import XBRL, XBRLFilingWithNoXbrlData

__all__ = [
    'XBRL',
    'XBRLFilingWithNoXbrlData',
    'XBRLS',
    'Statements',
    'Statement',
    'StitchedStatements',
    'StitchedStatement',
    'StandardConcept',
    'StatementStitcher',
    'stitch_statements',
    'render_stitched_statement',
    'RenderedStatement',
    'to_pandas',
    'FactsView',
    'FactQuery',
    'StitchedFactsView',
    'StitchedFactQuery'
]
