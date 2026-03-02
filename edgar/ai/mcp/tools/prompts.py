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


# Map prompt names to renderer functions
PROMPT_RENDERERS = {
    "due_diligence": _render_due_diligence,
    "earnings_analysis": _render_earnings_analysis,
    "industry_overview": _render_industry_overview,
    "insider_monitor": _render_insider_monitor,
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
