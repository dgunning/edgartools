# EdgarTools Standardized Financial Data Contract

**Version:** 1.0
**Date:** 2026-04-04

## Scope

**Product A:** 8 core standardized financial metrics extracted from SEC 10-K filings via XBRL.

| # | Metric | Statement | Tier |
|---|--------|-----------|------|
| 1 | Revenue | Income Statement | headline |
| 2 | NetIncome | Income Statement | headline |
| 3 | OperatingIncome | Income Statement | headline |
| 4 | OperatingCashFlow | Cash Flow | headline |
| 5 | TotalAssets | Balance Sheet | headline |
| 6 | TotalLiabilities | Balance Sheet | headline |
| 7 | StockholdersEquity | Balance Sheet | headline |
| 8 | EarningsPerShareDiluted | Per Share | headline |

## Coverage

- **Current:** 100 S&P companies evaluated (EF-CQS 0.8544)
- **Target:** 500 S&P companies
- **Temporal scope:** Latest annual filing (10-K). Multi-period deferred.
- **Freshness:** Data available within 48 hours of EDGAR availability

## Accuracy Targets

- **Core metrics at `high` confidence:** 99% accuracy against SEC filings
- **All metrics:** 95% accuracy at `medium` confidence or above

## Confidence Levels

Every extracted metric carries a `publish_confidence` indicating reliability:

| Level | Meaning | Criteria |
|-------|---------|----------|
| `high` | Production-grade | Tree-resolved, known XBRL concept, no known divergence |
| `medium` | Usable with caution | Mapped via tree/facts/industry but reference differs or self-validated only |
| `low` | Unvalidated | Facts-search fallback or unverified source |
| `unverified` | Missing or unmapped | Value is None or metric unmapped |
| `not_applicable` | Excluded | Metric not applicable for this company/industry |

Each metric also carries an `evidence_tier` describing how it was resolved:

| Tier | Description |
|------|-------------|
| `tree_confirmed` | Found in XBRL calculation tree with known concept |
| `facts_search` | Found in XBRL facts (not in calc tree) |
| `industry` | Resolved via industry-specific extraction logic |
| `excluded` | Metric excluded for this company |
| `unverified` | No resolution path available |

## Definitional Choices

| Metric | Ambiguity | Resolution |
|--------|-----------|------------|
| OperatingIncome | With/without impairment charges | GAAP as reported (includes impairment) |
| TotalLiabilities | `us-gaap:Liabilities` vs composite | Composite `LiabilitiesAndStockholdersEquity - StockholdersEquity` when direct concept absent; NCI-inclusive preferred |
| StockholdersEquity | Parent-only vs NCI-inclusive | NCI-inclusive when available, parent-only fallback |
| EarningsPerShareDiluted | Basic vs diluted, GAAP vs adjusted | GAAP diluted as reported |

## Known Limitations

- ~11% of companies use composite formula for TotalLiabilities (direct `us-gaap:Liabilities` absent)
- Banking/financial companies may have sector-specific reporting that affects OperatingIncome and COGS
- Multi-period validation is limited to latest annual filing in current release
- Reference validation requires yfinance snapshots (opt-in Tier 2 only)
