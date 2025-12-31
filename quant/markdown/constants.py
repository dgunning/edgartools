__all__ = ["STATEMENT_TITLES", "ITEM_BOUNDARIES"]

# Statement name mappings
STATEMENT_TITLES = {
    "IncomeStatement": "Income Statement",
    "BalanceSheet": "Balance Sheet",
    "CashFlowStatement": "Cash Flow Statement",
    "StatementOfEquity": "Statement of Equity",
    "ComprehensiveIncome": "Comprehensive Income",
    "CoverPage": "Cover Page",
}

# Item boundary patterns for LLM section extraction
# NOTE: Authoritative source for 10-K/10-Q structure is:
#   - edgar.company_reports.ten_k.TenK.structure (all 23 10-K items)
#   - edgar.company_reports.ten_q.TenQ.structure (all 11 10-Q items)
# This dict provides boundaries for section extraction in extract_markdown()
ITEM_BOUNDARIES = {
    "Item 1": ["Item 1A", "Item 1B", "Item 1C", "Item 2"],
    "Item 1A": ["Item 1B", "Item 1C", "Item 2"],
    "Item 1B": ["Item 1C", "Item 2"],
    "Item 1C": ["Item 2"],
    "Item 2": ["Item 3"],
    "Item 3": ["Item 4"],
    "Item 4": ["Item 5", "Part II"],
    "Item 5": ["Item 7"],
    "Item 7": ["Item 7A", "Item 8"],
    "Item 7A": ["Item 8"],
    "Item 8": ["Item 9", "Item 9A", "Item 9B"],
    "Item 9": ["Item 9A", "Item 9B", "Item 9C"],
    "Item 9A": ["Item 9B", "Item 9C"],
    "Item 9B": ["Item 9C", "Item 10", "Part III"],
    "Item 9C": ["Item 10", "Part III"],
    "Item 10": ["Item 11"],
    "Item 11": ["Item 12"],
    "Item 12": ["Item 13"],
    "Item 13": ["Item 14"],
    "Item 14": ["Item 15", "Part IV"],
    "Item 15": ["Item 16", "Signatures"],
    "Item 16": ["Signatures"],
}
