# XBRL Financial Data

EdgarTools provides powerful, elegant tools for working with XBRL financial data from SEC filings. Extract financial statements, analyze multi-period trends, and work with complex dimensional data - all with a simple, intuitive API.

## Quick Start

New to XBRL in EdgarTools? Start here:

- **[Extract Financial Statements](../guides/extract-statements.md)** - Get balance sheets, income statements, and cash flows in 5 minutes (Beginner)
- **[Choosing the Right API](getting-started/choosing-the-right-api.md)** - Understand when to use `filing.xbrl()` vs `company.get_facts()` (Beginner)

## Common Tasks

Jump to what you need to do:

- **[Extract Financial Statements](../guides/extract-statements.md)** - Get standardized financial statements from any filing
- **[Multi-Period Analysis](guides/multi-period-analysis.md)** - Compare financials across quarters and years
- **[Analyze Segments](../guides/extract-statements.md#enhanced-dimensional-display)** - Work with geographic and business segment breakdowns (Intermediate)
- **[Query XBRL Facts](../api/xbrl.md#facts-and-filtering)** - Search and filter raw XBRL facts programmatically (Advanced)

## Understanding XBRL

Conceptual guides explaining how EdgarTools handles XBRL data:

- **[Dimension Handling](concepts/dimension-handling.md)** - How EdgarTools processes segments, scenarios, and other dimensions (Intermediate)
- **[Standardization](concepts/standardization.md)** - How financial statements are normalized across companies (Intermediate)

## API Reference

Detailed API documentation:

- **[XBRL API](../api/xbrl.md)** - Complete reference for the `XBRL` class and methods
- **[EntityFacts API](../api/entity-facts-reference.md)** - Reference for company-level facts API
- **[StatementType Quick Reference](../StatementType-Quick-Reference.md)** - All available statement types and their uses

## Getting Help

**Troubleshooting Tips:**

- **Statement not found?** Check if the filing contains XBRL data using `filing.xbrl()`
- **Unexpected dimensions?** See [Dimension Handling](concepts/dimension-handling.md) for filtering strategies
- **Missing values?** Some companies use non-standard tags - use `statement.facts` to explore raw data

**Need More Help?**

- [Open an issue on GitHub](https://github.com/dgunning/edgartools/issues) - Report bugs or request features
- [View Examples](../guides/) - Browse our collection of practical guides and examples

---

**Note:** EdgarTools handles the complexity of XBRL so you don't have to. If you're new to XBRL, don't worry - our guides assume no prior knowledge of XBRL or SEC filings.
