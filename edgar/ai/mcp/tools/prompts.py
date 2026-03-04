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

3. **Risk Factors**: Use edgar_filing to read the latest 10-K risk_factors section.

4. **Recent Events**: Use edgar_filing to check the latest 8-K for material events.

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

1. **Latest Earnings**: Use edgar_filing with form "8-K" and sections ["items", "earnings"] to find the most recent earnings release.

2. **Financial Trends**: Use edgar_trends with concepts ["revenue", "net_income", "eps", "gross_profit"] for both annual (5 years) and quarterly (8 quarters) to show the trajectory.

3. **Peer Comparison**: Use edgar_compare with {identifier} and 2-3 peer companies, comparing ["revenue", "net_income", "net_margin"].

4. **Management Commentary**: Use edgar_filing with the latest 10-K or 10-Q, sections ["mda"] for management's discussion.

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

2. **Filing A**: Use edgar_filing with identifier="{identifier}" and form="{form}" to get the latest {form} filing. Read sections ["business", "risk_factors", "mda"].

3. **Filing B**: Use edgar_filing with identifier="{compare_to}" and form="{form}" to get the latest {form} filing. Read the same sections.

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

2. **Latest Filing**: Use edgar_filing with identifier="{identifier}", form="{form}", and filing_index=0. Read sections ["business", "risk_factors", "mda"].

3. **Previous Filing**: Use edgar_filing with identifier="{identifier}", form="{form}", and filing_index=1. Read the same sections.

4. **Financial Trends**: Use edgar_trends with identifier="{identifier}" and concepts ["revenue", "net_income", "eps", "assets"] over 5 periods to see the trajectory.

5. **Recent Events**: Use edgar_filing with form="8-K" for {identifier} to check for material events between the two filing periods.

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

2. **SC 13D Filings**: Use edgar_filing with identifier="{identifier}" and form="SC 13D" to find activist ownership filings (>5% stakes with intent to influence).

3. **SC 13G Filings**: Use edgar_filing with identifier="{identifier}" and form="SC 13G" to find passive large holder filings (>5% stakes, passive intent).

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

    # Pass arguments to renderer
    import inspect
    sig = inspect.signature(renderer)
    kwargs = {}
    for param_name in sig.parameters:
        if param_name in arguments:
            kwargs[param_name] = arguments[param_name]
    return renderer(**kwargs)
