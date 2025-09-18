"""
MCP Tool implementations for EdgarTools.

This module contains the actual implementations of MCP tools that wrap
EdgarTools functionality for AI agents.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

# Import EdgarTools functionality
try:
    from edgar import Company, find_company, get_current_filings, get_filings  # noqa: F401
    from edgar.search import search_companies  # noqa: F401
    EDGAR_AVAILABLE = True
except ImportError:
    EDGAR_AVAILABLE = False


logger = logging.getLogger(__name__)


class BaseTool:
    """Base class for MCP tools."""

    @staticmethod
    def format_error(error: Exception) -> Dict[str, Any]:
        """Format error responses consistently."""
        return {
            "error": str(error),
            "type": type(error).__name__,
            "suggestions": BaseTool._get_error_suggestions(error)
        }

    @staticmethod
    def _get_error_suggestions(error: Exception) -> List[str]:
        """Get helpful suggestions based on error type."""
        error_msg = str(error).lower()
        suggestions = []

        if "not found" in error_msg:
            suggestions.append("Try using the company's CIK number instead of ticker")
            suggestions.append("Search for the company first using edgar_search")
            suggestions.append("Check if the company name is spelled correctly")
        elif "no filings" in error_msg:
            suggestions.append("Try a different date range")
            suggestions.append("Check if the company files with the SEC")
            suggestions.append("Try a different form type")
        elif "timeout" in error_msg or "connection" in error_msg:
            suggestions.append("The SEC API may be experiencing high load")
            suggestions.append("Try again in a few moments")
            suggestions.append("Reduce the number of requested items")

        return suggestions


class CompanyTool(BaseTool):
    """Tool for retrieving company information."""

    @staticmethod
    def get_company(identifier: str, 
                   include_financials: bool = False,
                   include_filings: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive company information.

        Args:
            identifier: Company ticker, CIK, or name
            include_financials: Include latest financial data
            include_filings: Include recent filings list

        Returns:
            Dictionary with company information optimized for LLM consumption
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            # Get company object
            company = Company(identifier)

            # Basic company information
            result = {
                "name": company.name,
                "ticker": company.get_ticker(),
                "cik": company.cik,
                "industry": getattr(company, 'industry', 'Unknown'),
                "description": getattr(company, 'description', ''),
                "website": getattr(company, 'website', ''),
                "employees": getattr(company, 'employees', None),
                "state": getattr(company, 'state_of_incorporation', ''),
                "fiscal_year_end": getattr(company, 'fiscal_year_end', ''),
            }

            # Add context for LLM
            result["context"] = f"""
{company.name} ({company.get_ticker()}) is a company in the {result['industry']} industry.
CIK: {company.cik}
{result['description']}
"""

            # Include financials if requested
            if include_financials:
                try:
                    financials = company.get_financials()
                    if financials:
                        result["financials"] = {
                            "latest_revenue": getattr(financials, 'revenue', None),
                            "latest_net_income": getattr(financials, 'net_income', None),
                            "latest_assets": getattr(financials, 'assets', None),
                            "latest_liabilities": getattr(financials, 'liabilities', None),
                            "period": getattr(financials, 'period', 'Unknown')
                        }
                except Exception as e:
                    result["financials"] = {"error": str(e)}

            # Include recent filings if requested
            if include_filings:
                try:
                    recent_filings = company.get_filings(limit=10)
                    result["recent_filings"] = [
                        {
                            "form": f.form,
                            "filing_date": f.filing_date.isoformat() if f.filing_date else None,
                            "period": getattr(f, 'period_of_report', None),
                            "accession": f.accession_no
                        }
                        for f in recent_filings
                    ]
                except Exception as e:
                    result["recent_filings"] = {"error": str(e)}

            return result

        except Exception as e:
            return BaseTool.format_error(e)


class FilingsTool(BaseTool):
    """Tool for retrieving SEC filings."""

    @staticmethod
    def get_filings(company: str,
                   form_type: Optional[Union[str, List[str]]] = None,
                   date_from: Optional[str] = None,
                   date_to: Optional[str] = None,
                   limit: int = 10) -> Dict[str, Any]:
        """
        Retrieve SEC filings with filtering options.

        Args:
            company: Company identifier
            form_type: Form type(s) to filter by
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum number of filings

        Returns:
            Dictionary with filing information
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            # Get company
            company_obj = Company(company)

            # Get filings
            filings = company_obj.get_filings(
                form=form_type,
                limit=limit
            )

            # Filter by date if provided
            if date_from:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                filings = [f for f in filings if f.filing_date >= date_from_obj]

            if date_to:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                filings = [f for f in filings if f.filing_date <= date_to_obj]

            # Format results
            result = {
                "company": company_obj.name,
                "ticker": company_obj.get_ticker(),
                "total_found": len(filings),
                "filings": []
            }

            for filing in filings[:limit]:
                filing_data = {
                    "form": filing.form,
                    "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                    "period": getattr(filing, 'period_of_report', None),
                    "accession": filing.accession_no,
                    "description": filing.__str__(),
                }

                # Add LLM-friendly summary
                filing_data["summary"] = (
                    f"{filing.form} filed on {filing.filing_date} "
                    f"for period {getattr(filing, 'period_of_report', 'N/A')}"
                )

                result["filings"].append(filing_data)

            # Add context for LLM
            form_desc = f"form type {form_type}" if form_type else "all forms"
            result["context"] = (
                f"Found {len(result['filings'])} filings for {company_obj.name} "
                f"({form_desc}) in the specified date range."
            )

            return result

        except Exception as e:
            return BaseTool.format_error(e)


class FinancialsTool(BaseTool):
    """Tool for financial analysis."""

    @staticmethod
    def analyze_financials(company: str,
                          statement_type: str = "all",
                          periods: int = 4,
                          include_ratios: bool = True,
                          include_trends: bool = True) -> Dict[str, Any]:
        """
        Analyze financial statements and calculate metrics.

        Args:
            company: Company identifier
            statement_type: Type of statement(s) to analyze
            periods: Number of periods to analyze
            include_ratios: Calculate financial ratios
            include_trends: Include trend analysis

        Returns:
            Dictionary with financial analysis
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            # Get company
            company_obj = Company(company)

            # Get recent 10-K and 10-Q filings
            filings = company_obj.get_filings(form=["10-K", "10-Q"], limit=periods)

            result = {
                "company": company_obj.name,
                "ticker": company_obj.get_ticker(),
                "analysis_date": date.today().isoformat(),
                "periods_analyzed": 0,
                "financial_data": [],
                "ratios": {},
                "trends": {}
            }

            # Analyze each filing
            for filing in filings:
                try:
                    xbrl = filing.xbrl()
                    if not xbrl:
                        continue

                    period_data = {
                        "period": filing.period_of_report,
                        "form": filing.form,
                        "filing_date": filing.filing_date.isoformat()
                    }

                    # Get financial statements based on type
                    if statement_type in ["income", "all"]:
                        income = xbrl.income_statement
                        if income:
                            period_data["income_statement"] = {
                                "revenue": getattr(income, 'revenue', None),
                                "gross_profit": getattr(income, 'gross_profit', None),
                                "operating_income": getattr(income, 'operating_income', None),
                                "net_income": getattr(income, 'net_income', None),
                            }

                    if statement_type in ["balance", "all"]:
                        balance = xbrl.balance_sheet
                        if balance:
                            period_data["balance_sheet"] = {
                                "total_assets": getattr(balance, 'total_assets', None),
                                "current_assets": getattr(balance, 'current_assets', None),
                                "total_liabilities": getattr(balance, 'total_liabilities', None),
                                "shareholders_equity": getattr(balance, 'shareholders_equity', None),
                            }

                    if statement_type in ["cash_flow", "all"]:
                        cash_flow = xbrl.cash_flow_statement
                        if cash_flow:
                            period_data["cash_flow"] = {
                                "operating_cash_flow": getattr(cash_flow, 'operating_activities', None),
                                "investing_cash_flow": getattr(cash_flow, 'investing_activities', None),
                                "financing_cash_flow": getattr(cash_flow, 'financing_activities', None),
                            }

                    result["financial_data"].append(period_data)
                    result["periods_analyzed"] += 1

                except Exception as e:
                    logger.warning("Error processing filing: %s", e)
                    continue

            # Calculate ratios if requested
            if include_ratios and result["financial_data"]:
                latest = result["financial_data"][0]
                if "income_statement" in latest and "balance_sheet" in latest:
                    income = latest["income_statement"]
                    balance = latest["balance_sheet"]

                    result["ratios"] = FinancialsTool._calculate_ratios(income, balance)

            # Calculate trends if requested
            if include_trends and len(result["financial_data"]) > 1:
                result["trends"] = FinancialsTool._calculate_trends(result["financial_data"])

            # Add LLM context
            result["context"] = FinancialsTool._generate_analysis_context(result)

            return result

        except Exception as e:
            return BaseTool.format_error(e)

    @staticmethod
    def _calculate_ratios(income: Dict, balance: Dict) -> Dict[str, Any]:
        """Calculate financial ratios."""
        ratios = {}

        # Profitability ratios
        if income.get("net_income") and income.get("revenue"):
            ratios["net_margin"] = income["net_income"] / income["revenue"]

        if income.get("net_income") and balance.get("shareholders_equity"):
            ratios["roe"] = income["net_income"] / balance["shareholders_equity"]

        # Liquidity ratios
        if balance.get("current_assets") and balance.get("current_liabilities"):
            ratios["current_ratio"] = balance["current_assets"] / balance["current_liabilities"]

        # Leverage ratios
        if balance.get("total_liabilities") and balance.get("shareholders_equity"):
            ratios["debt_to_equity"] = balance["total_liabilities"] / balance["shareholders_equity"]

        return ratios

    @staticmethod
    def _calculate_trends(financial_data: List[Dict]) -> Dict[str, Any]:
        """Calculate financial trends."""
        trends = {}

        # Revenue trend
        revenues = []
        for period in financial_data:
            if "income_statement" in period and period["income_statement"].get("revenue"):
                revenues.append(period["income_statement"]["revenue"])

        if len(revenues) >= 2:
            trends["revenue_growth"] = (revenues[0] - revenues[-1]) / revenues[-1]

        return trends

    @staticmethod
    def _generate_analysis_context(result: Dict) -> str:
        """Generate natural language context for the analysis."""
        context_parts = [
            f"Financial analysis for {result['company']} ({result['ticker']})",
            f"covering {result['periods_analyzed']} periods."
        ]

        if result.get("ratios"):
            ratios = result["ratios"]
            if "net_margin" in ratios:
                context_parts.append(f"Net margin: {ratios['net_margin']:.1%}")
            if "roe" in ratios:
                context_parts.append(f"ROE: {ratios['roe']:.1%}")

        if result.get("trends"):
            trends = result["trends"]
            if "revenue_growth" in trends:
                growth = trends["revenue_growth"]
                direction = "increased" if growth > 0 else "decreased"
                context_parts.append(f"Revenue {direction} by {abs(growth):.1%}")

        return " ".join(context_parts)


class SearchTool(BaseTool):
    """Tool for searching companies and filings."""

    @staticmethod
    def search(query: str,
              search_type: str = "all",
              filters: Optional[Dict[str, Any]] = None,
              limit: int = 20) -> Dict[str, Any]:
        """
        Search for companies or filings.

        Args:
            query: Search query
            search_type: Type of search (companies/filings/all)
            filters: Additional filters
            limit: Maximum results

        Returns:
            Search results dictionary
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            result = {
                "query": query,
                "search_type": search_type,
                "results": [],
                "total_found": 0
            }

            # Search companies
            if search_type in ["companies", "all"]:
                try:
                    # Use find_company for simple search
                    companies = find_company(query)
                    if companies:
                        if not isinstance(companies, list):
                            companies = [companies]

                        for company in companies[:limit]:
                            result["results"].append({
                                "type": "company",
                                "name": company.name,
                                "ticker": company.get_ticker(),
                                "cik": company.cik,
                                "match_score": 1.0  # Simple match
                            })

                except Exception as e:
                    logger.warning("Company search error: %s", e)

            # Add context
            result["total_found"] = len(result["results"])
            result["context"] = f"Found {result['total_found']} results for '{query}'"

            return result

        except Exception as e:
            return BaseTool.format_error(e)


class CurrentFilingsTool(BaseTool):
    """Tool for monitoring current SEC filings."""

    @staticmethod
    def get_current_filings(form_type: Optional[str] = None,
                           limit: int = 20,
                           include_summary: bool = False) -> Dict[str, Any]:
        """
        Get the most recent SEC filings.

        Args:
            form_type: Filter by form type
            limit: Number of filings to return
            include_summary: Include AI summary of each filing

        Returns:
            Dictionary with current filings
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            # Get current filings
            filings = get_current_filings(
                form=form_type or "",
                page_size=min(limit, 100)
            )

            result = {
                "timestamp": datetime.now().isoformat(),
                "form_filter": form_type,
                "filings": []
            }

            # Convert filings to list
            filing_data = filings.data.to_pylist()

            for filing in filing_data[:limit]:
                filing_dict = {
                    "company": filing["company"],
                    "form": filing["form"],
                    "filing_date": filing["filing_date"],
                    "accepted": filing["accepted"],
                    "accession": filing["accession_number"],
                    "cik": filing["cik"]
                }

                # Add summary if requested
                if include_summary:
                    filing_dict["summary"] = (
                        f"{filing['company']} filed {filing['form']} on "
                        f"{filing['filing_date']}. "
                        f"This filing was accepted at {filing['accepted']}."
                    )

                result["filings"].append(filing_dict)

            # Add context
            result["total_returned"] = len(result["filings"])
            result["context"] = (
                f"Latest {len(result['filings'])} SEC filings"
                f"{f' (filtered by {form_type})' if form_type else ''}"
            )

            return result

        except Exception as e:
            return BaseTool.format_error(e)


class ScreeningTool(BaseTool):
    """Tool for stock screening based on fundamentals."""

    @staticmethod
    def screen_stocks(criteria: Dict[str, Any],
                     sort_by: str = "market_cap",
                     limit: int = 50) -> Dict[str, Any]:
        """
        Screen stocks based on fundamental criteria.

        Args:
            criteria: Screening criteria
            sort_by: Metric to sort by
            limit: Maximum results

        Returns:
            Screened stocks with metrics
        """
        if not EDGAR_AVAILABLE:
            return BaseTool.format_error(
                ImportError("EdgarTools not properly installed")
            )

        try:
            # This is a placeholder implementation
            # In a real implementation, this would query a database of pre-calculated metrics

            result = {
                "criteria": criteria,
                "sort_by": sort_by,
                "timestamp": datetime.now().isoformat(),
                "stocks": [],
                "context": "Stock screening requires pre-calculated metrics database"
            }

            # Example response structure
            result["example_structure"] = {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "metrics": {
                    "market_cap": 3000000000000,
                    "pe_ratio": 25.5,
                    "revenue": 400000000000,
                    "revenue_growth": 0.08,
                    "roe": 0.35,
                    "net_margin": 0.25
                },
                "matches_criteria": True
            }

            return result

        except Exception as e:
            return BaseTool.format_error(e)
