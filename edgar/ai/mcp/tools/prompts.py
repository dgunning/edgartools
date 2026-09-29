"""
MCP Prompts

Pre-built multi-step financial analysis workflows that chain EdgarTools
MCP tools together. These are user-initiated templates, not tool calls.
"""

from __future__ import annotations

from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

# =============================================================================
# PROMPT DEFINITIONS
# =============================================================================

PROMPTS = {
    "borrower_credit_review": Prompt(
        name="borrower_credit_review",
        description="Investigate a borrower's disclosed loan valuations, payment terms and non-accrual evidence from selected BDC filings.",
        arguments=[
            PromptArgument(name="borrower", description="Borrower name as reported in the BDC's holdings", required=True),
            PromptArgument(name="bdc", description="Reporting BDC ticker, CIK or name (e.g. ARCC)", required=True),
            PromptArgument(name="period", description="Reporting period end YYYY-MM-DD; defaults to the latest available 10-K or 10-Q", required=False),
            PromptArgument(name="comparison_period", description="Optional second reporting period end YYYY-MM-DD", required=False),
        ],
    ),
    "lender_protection_review": Prompt(
        name="lender_protection_review",
        description="Find and review filed agreements covering a borrower's collateral, guarantees and repayment priority, with source passages and qualifications.",
        arguments=[
            PromptArgument(name="borrower", description="Borrower whose financing protections should be investigated", required=True),
            PromptArgument(name="filing_or_url", description="Optional SEC accession number or HTTPS www.sec.gov filing/document URL", required=False),
            PromptArgument(name="focus", description="Optional topics such as collateral, guarantees or release provisions", required=False),
        ],
    ),
    "due_diligence": Prompt(
        name="due_diligence",
        description="Comprehensive company due diligence — profile, financials, recent filings, insider activity, and risk factors.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Company ticker (AAPL), CIK, or name",
                required=True,
            ),
        ],
    ),
    "earnings_analysis": Prompt(
        name="earnings_analysis",
        description="Analyze a company's recent earnings — latest 8-K, financial trends, and peer comparison.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Company ticker (AAPL), CIK, or name",
                required=True,
            ),
        ],
    ),
    "industry_overview": Prompt(
        name="industry_overview",
        description="Survey an industry sector — screen companies, compare top players, and identify trends.",
        arguments=[
            PromptArgument(
                name="industry",
                description="Industry keyword (e.g., 'semiconductor', 'pharmaceutical', 'banking')",
                required=True,
            ),
        ],
    ),
    "insider_monitor": Prompt(
        name="insider_monitor",
        description="Monitor insider trading activity for a company — recent Form 4 filings and transaction patterns.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Company ticker (AAPL), CIK, or name",
                required=True,
            ),
        ],
    ),
    "fund_analysis": Prompt(
        name="fund_analysis",
        description="Deep dive into a mutual fund or ETF — fund hierarchy, portfolio holdings, performance, and related company analysis.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Fund ticker (VFINX, SPY), series ID (S000002277), or CIK",
                required=True,
            ),
        ],
    ),
    "filing_comparison": Prompt(
        name="filing_comparison",
        description="Compare the same filing type across time periods or across companies — spot changes in risk factors, strategy, or financials.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Company ticker (AAPL), CIK, or name",
                required=True,
            ),
            PromptArgument(
                name="form",
                description="Filing form type to compare (default: 10-K)",
                required=False,
            ),
            PromptArgument(
                name="compare_to",
                description="Second company ticker for cross-company comparison (optional)",
                required=False,
            ),
        ],
    ),
    "activist_tracking": Prompt(
        name="activist_tracking",
        description="Track activist investor positions via SC 13D/G filings — identify activist stakes, monitor changes, and assess company impact.",
        arguments=[
            PromptArgument(
                name="identifier",
                description="Company ticker (AAPL), CIK, or name",
                required=True,
            ),
        ],
    ),
}


# =============================================================================
# PROMPT RENDERERS
# =============================================================================

def _render_borrower_credit_review(
    borrower: str, bdc: str, period: str = "", comparison_period: str = ""
) -> GetPromptResult:
    selection = (
        f"Select the filing with reporting period end {period}."
        if period else
        "List available 10-K and 10-Q filings and select the latest reporting period available."
    )
    comparison = (
        f"Repeat the evidence retrieval for reporting period end {comparison_period}. "
        "Present each period's original records side by side. Explain uncertainty about whether records represent "
        "the same facility; do not silently merge facilities or treat a valuation change as proof of deterioration."
        if comparison_period else
        "Review the selected period only; do not assume a comparison period."
    )
    return GetPromptResult(
        description=f"Borrower credit evidence for {borrower} reported by {bdc}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"""Investigate repayment concerns for borrower {borrower} using public evidence reported by BDC {bdc}.

1. **Select the evidence**: Resolve the BDC using edgar_fund action="bdc_search" if needed. Use edgar_search or edgar_company to list its 10-K and 10-Q filings. {selection} Distinguish reporting period from filing date and originals from amendments. Record the chosen form and accession number. If an explicit period is unavailable, explain the gap rather than substitute another filing.

2. **Retrieve loan holdings**: Use edgar_fund action="bdc_portfolio" with the chosen accession_number and borrower="{borrower}". Follow continuation through all matching extracted holdings. Keep distinct facilities separate and preserve reported borrower names, investment descriptions, principal, cost, fair value, interest rate, spread and PIK rate where available, with units. Confirm borrower-name matches rather than assuming substring matches identify the same legal entity.

3. **Retrieve non-accrual evidence**: Use edgar_fund action="bdc_nonaccrual" for the SAME accession number. This action returns filing-wide evidence; follow all investment evidence pages and identify any records relevant to the borrower from their reported names. Preserve supporting footnotes, evidence level, extraction method and warnings. Portfolio-level totals cannot establish an individual borrower's status. Non-accrual is an accounting status, not a legal default determination.

4. **Read supporting disclosures**: Use edgar_notes and edgar_read with that same accession number for relevant valuation, liquidity, payment and restructuring disclosures. Discover available notes/sections before selecting them. Follow relevant text and table pages beyond previews. For every continuation call, repeat the original selector and filters with the returned cursor. If evidence changes and a cursor becomes stale, restart that retrieval and report the issue.

5. **Period context**: {comparison}

6. **Report**: Provide a loan evidence table, disclosures warranting investigation, unresolved questions and source citations. Include the reporting lender, form, accession, reporting period, filing date and URLs, with note/table/passage locators where available. Distinguish reported facts, your interpretation and evidence gaps.

Explain PIK as interest added to debt rather than paid in cash; PIK alone does not establish distress. A BDC holding represents that lender's position, not the borrower's total debt. Distinguish reported zero, not disclosed, not extracted and retrieval failure. Absence from an extracted non-accrual list does not establish that a loan is performing. Report coverage limits and do not assign a risk score, predict default or estimate recoveries."""))],
    )


def _render_lender_protection_review(
    borrower: str, filing_or_url: str = "", focus: str = ""
) -> GetPromptResult:
    starting_point = (
        f"Start with this filing or document: {filing_or_url}. Use edgar_filing to establish filing context "
        "and retain any document_hint from the URL."
        if filing_or_url else
        "Use edgar_search and edgar_text_search to discover candidate filings and agreements mentioning the borrower."
    )
    topics = focus or "collateral, guarantees, repayment priority, release provisions and enforcement restrictions"
    return GetPromptResult(
        description=f"Lender protection evidence for {borrower}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"""Investigate what contractual protections are disclosed for financing of borrower {borrower}. Research focus: {topics}.

1. **Establish identity and financing**: {starting_point} Confirm the legal borrower, reporting filer, lender and relevant obligation from the retrieved evidence. If multiple entities or financings are plausible, present candidates and ask which to investigate before selecting one. A BDC's own borrowing agreements must not be mistaken for agreements covering a portfolio borrower.

2. **Identify documents**: Use edgar_document action="list" with the selected accession_number to enumerate attachments. Identify relevant agreements, guarantees and amendments by their titles, descriptions and parties. Preserve exact filenames, document types, accession numbers, dates and source URLs. When an exhibit type is ambiguous, select from the returned candidates by exact filename or sequence. Follow references to earlier filings where discoverable and explain which documents remain unavailable; do not claim a complete amendment history.

3. **Search each relevant document**: Use edgar_document action="search" with the accession_number and exact document filename, searching for the requested topics and related wording. For example, search for collateral, security interest, guarantor, subordination, intercreditor, release and remedies. Preserve each match's document-bound locator. A missing keyword match does not prove that a protection is absent.

4. **Read provisions in context**: Use edgar_document action="read" with the SAME accession and document selector and around set to the returned locator. Read headings, defined terms, exceptions, schedules and referenced sections needed to understand the passage. Continue relevant long documents with next_cursor, repeating the exact document selector; do not combine around and cursor. Search and read amendments for changes to the relevant provisions. Report unreadable content and unavailable referenced documents explicitly.

5. **Report the evidence**: Provide a document inventory and a table of topic, source passage, plain-language explanation, qualifications and citation. Cite exact documents and locators and identify the parties and obligations each passage covers. Include relevant financial notes using edgar_notes or edgar_read from the selected filing when useful.

Separate explicit reported wording from interpretation and unresolved questions. Explain how missing agreements, amendments, schedules or unreadable content limit the review. Do not equate a valuation mark with realized recovery, determine legal enforceability or estimate recovery amounts. Close with specific documents and questions the analyst should pursue to assess the protections further."""))],
    )

def _render_due_diligence(identifier: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Due diligence analysis for {identifier}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Perform a comprehensive due diligence analysis on {identifier}. Follow these steps:

1. **Company Profile**: Use edgar_company to get the full company profile including financials and recent filings.

2. **Financial Trends**: Use edgar_trends with concepts ["revenue", "net_income", "eps"] over 5 years to understand growth trajectory.

3. **Risk Factors**: Use edgar_read to read the latest 10-K risk_factors section.

4. **Recent Events**: Use edgar_read to check the latest 8-K for material events.

5. **Insider Activity**: Use edgar_ownership with analysis_type "insiders" to review recent insider transactions.

6. **Synthesis**: Summarize findings into:
   - Business overview and competitive position
   - Financial health and growth trends
   - Key risks and recent developments
   - Insider sentiment signal"""
                ),
            ),
        ],
    )


def _render_earnings_analysis(identifier: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Earnings analysis for {identifier}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Analyze recent earnings performance for {identifier}. Follow these steps:

1. **Latest Earnings**: Use edgar_read with form "8-K" and sections ["items", "earnings"] to find the most recent earnings release.

2. **Financial Trends**: Use edgar_trends with concepts ["revenue", "net_income", "eps", "gross_profit"] for both annual (5 years) and quarterly (8 quarters) to show the trajectory.

3. **Peer Comparison**: Use edgar_compare with {identifier} and 2-3 peer companies, comparing ["revenue", "net_income", "net_margin"].

4. **Management Commentary**: Use edgar_read with the latest 10-K or 10-Q, sections ["mda"] for management's discussion.

5. **Synthesis**: Provide:
   - Revenue and earnings growth trends (accelerating/decelerating?)
   - Margin analysis (expanding or contracting?)
   - Performance vs peers
   - Key takeaways from management commentary"""
                ),
            ),
        ],
    )


def _render_industry_overview(industry: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Industry overview for {industry}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Provide an industry overview for the {industry} sector. Follow these steps:

1. **Screen Companies**: Use edgar_screen with industry="{industry}" to discover companies in this sector.

2. **Top Players**: From the results, pick the 3-5 largest/most notable companies.

3. **Comparative Analysis**: Use edgar_compare with those companies, comparing ["revenue", "net_income", "net_margin", "assets"].

4. **Growth Trends**: Use edgar_trends for the top 2-3 companies to show how the sector leaders are growing.

5. **Recent Activity**: Use edgar_monitor to check for any recent filings from companies in this sector.

6. **Synthesis**: Provide:
   - Sector landscape and key players
   - Comparative financial performance
   - Growth dynamics (which companies are gaining/losing share?)
   - Recent SEC filing activity of note"""
                ),
            ),
        ],
    )


def _render_insider_monitor(identifier: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Insider activity monitor for {identifier}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Monitor and analyze insider trading activity for {identifier}. Follow these steps:

1. **Company Context**: Use edgar_company with include ["profile"] to understand the company.

2. **Insider Transactions**: Use edgar_ownership with analysis_type "insiders" to get recent Form 4 filings.

3. **Financial Context**: Use edgar_trends with concepts ["revenue", "net_income", "eps"] to see if insider activity aligns with financial trajectory.

4. **Recent Events**: Use edgar_monitor with form "4" to check for very recent insider filings across the market.

5. **Synthesis**: Analyze:
   - Who is buying/selling and in what amounts?
   - Is there a pattern (cluster buying, regular selling, etc.)?
   - Does insider activity align with or diverge from financial performance?
   - Any notable transactions that stand out?"""
                ),
            ),
        ],
    )


def _render_fund_analysis(identifier: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Fund analysis for {identifier}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Perform a deep-dive analysis on the fund identified by {identifier}. Follow these steps:

1. **Fund Lookup**: Use edgar_fund with action="lookup" and identifier="{identifier}" to get the fund hierarchy — company, series, share classes, and tickers.

2. **Portfolio Holdings**: Use edgar_fund with action="portfolio" and identifier="{identifier}" to get current holdings. Note the top positions and sector concentration.

3. **Money Market Check**: If this is a money market fund, use edgar_fund with action="money_market" to get yield data, WAM/WAL, and share class details instead of portfolio.

3a. **BDC Check**: If this is a Business Development Company, use edgar_fund with action="bdc_portfolio" (optionally with form/period to pin a specific filing, and borrower to filter) for Schedule of Investments holdings, and action="bdc_nonaccrual" for non-accrual evidence, instead of portfolio. Page through either with the cursor returned in page.next_cursor.

4. **Top Holdings Analysis**: For the top 3-5 portfolio holdings, use edgar_company to get brief profiles and recent financial performance.

5. **Related Funds**: Use edgar_fund with action="search" to find other funds from the same fund family or with similar names.

6. **Synthesis**: Provide:
   - Fund overview (type, family, share classes)
   - Portfolio composition and concentration analysis
   - Top holdings with brief company profiles
   - Key metrics (yield for money market, or asset allocation for equity/bond funds)
   - Related funds in the same family"""
                ),
            ),
        ],
    )


def _render_filing_comparison(identifier: str, form: str = "10-K", compare_to: str = "") -> GetPromptResult:
    if compare_to:
        description = f"Filing comparison: {identifier} vs {compare_to} ({form})"
        comparison_text = f"""Compare {form} filings between {identifier} and {compare_to}. Follow these steps:

1. **Company Profiles**: Use edgar_company for both {identifier} and {compare_to} with include ["profile"] to understand each company.

2. **Filing A**: Use edgar_read with identifier="{identifier}" and form="{form}" to get the latest {form} filing. Read sections ["business", "risk_factors", "mda"].

3. **Filing B**: Use edgar_read with identifier="{compare_to}" and form="{form}" to get the latest {form} filing. Read the same sections.

4. **Financial Comparison**: Use edgar_compare with identifiers ["{identifier}", "{compare_to}"] to compare financial metrics.

5. **Trend Context**: Use edgar_trends for both companies with concepts ["revenue", "net_income", "eps"] to understand growth trajectories.

6. **Synthesis**: Provide a structured comparison:
   - Business model and strategy differences
   - Risk factor comparison — what risks does one face that the other doesn't?
   - Financial performance comparison (revenue, margins, growth)
   - Management outlook differences from MD&A sections"""
    else:
        description = f"Filing comparison for {identifier} ({form}) across periods"
        comparison_text = f"""Compare {identifier}'s {form} filings across time periods to identify changes. Follow these steps:

1. **Company Profile**: Use edgar_company with identifier="{identifier}" and include ["profile"] for context.

2. **Latest Filing**: Use edgar_filing with identifier="{identifier}" and form="{form}" to get the latest filing context. Then use edgar_read with the same identifier and form, sections=["business", "risk_factors", "mda"] to extract content.

3. **Previous Filing**: Use edgar_search with identifier="{identifier}", form="{form}", search_type="filings" to list recent filings. Pick the second one's accession_number, then use edgar_read with that accession_number and sections=["business", "risk_factors", "mda"].

4. **Financial Trends**: Use edgar_trends with identifier="{identifier}" and concepts ["revenue", "net_income", "eps", "assets"] over 5 periods to see the trajectory.

5. **Recent Events**: Use edgar_read with form="8-K" for {identifier} to check for material events between the two filing periods.

6. **Synthesis**: Highlight year-over-year changes:
   - Business description changes — new products, markets, or strategy shifts
   - New or removed risk factors — what risks emerged or were resolved?
   - MD&A tone and outlook changes
   - Financial performance trajectory"""

    return GetPromptResult(
        description=description,
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=comparison_text),
            ),
        ],
    )


def _render_activist_tracking(identifier: str) -> GetPromptResult:
    return GetPromptResult(
        description=f"Activist investor tracking for {identifier}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"""Track activist investor activity for {identifier}. Follow these steps:

1. **Company Profile**: Use edgar_company with identifier="{identifier}" and include ["profile", "financials"] to understand the target company.

2. **SC 13D Filings**: Use edgar_read with identifier="{identifier}" and form="SC 13D" to find activist ownership filings (>5% stakes with intent to influence).

3. **SC 13G Filings**: Use edgar_read with identifier="{identifier}" and form="SC 13G" to find passive large holder filings (>5% stakes, passive intent).

4. **Proxy Context**: Use edgar_proxy with identifier="{identifier}" to get executive compensation and governance data — often a focus of activist campaigns.

5. **Full-Text Search**: Use edgar_text_search with query="activist" or query="board representation" and identifier="{identifier}" to find activist-related mentions in filings.

6. **Insider Activity**: Use edgar_ownership with identifier="{identifier}" and analysis_type="insiders" to check if insiders are buying or selling around activist activity.

7. **Synthesis**: Provide:
   - Active 13D filers — who holds >5% with activist intent?
   - Passive 13G filers — who holds large passive stakes?
   - Governance posture — is compensation aligned? Any policy concerns?
   - Timeline of activist events and filings
   - Assessment of activist pressure and likely outcomes"""
                ),
            ),
        ],
    )


# Map prompt names to renderer functions
PROMPT_RENDERERS = {
    "borrower_credit_review": _render_borrower_credit_review,
    "lender_protection_review": _render_lender_protection_review,
    "due_diligence": _render_due_diligence,
    "earnings_analysis": _render_earnings_analysis,
    "industry_overview": _render_industry_overview,
    "insider_monitor": _render_insider_monitor,
    "fund_analysis": _render_fund_analysis,
    "filing_comparison": _render_filing_comparison,
    "activist_tracking": _render_activist_tracking,
}


def list_prompts() -> list[Prompt]:
    """Return all available prompts."""
    return list(PROMPTS.values())


def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
    """Render a prompt with the given arguments."""
    if name not in PROMPT_RENDERERS:
        raise ValueError(
            f"Unknown prompt: {name}. "
            f"Available: {', '.join(PROMPTS.keys())}"
        )

    arguments = arguments or {}
    renderer = PROMPT_RENDERERS[name]

    # Pass arguments to renderer, validating required params
    import inspect
    sig = inspect.signature(renderer)
    kwargs = {}
    missing = []
    for param_name, param in sig.parameters.items():
        if param_name in arguments:
            kwargs[param_name] = arguments[param_name]
        elif param.default is inspect.Parameter.empty:
            missing.append(param_name)

    if missing:
        raise ValueError(
            f"Prompt '{name}' requires arguments: {', '.join(missing)}. "
            f"Example: arguments={{'{missing[0]}': 'AAPL'}}"
        )

    return renderer(**kwargs)
