"""
EdgarTools Investigation Toolkit
Reusable utilities for systematic issue investigation

Usage:
    from tools.investigation_toolkit import IssueAnalyzer, quick_analyze

    # Quick analysis
    result = quick_analyze("empty_periods", "0000320193-18-000070")

    # Comprehensive analysis
    analyzer = IssueAnalyzer(408)
    analyzer.add_test_case("problematic", accession="0000320193-18-000070")
    analyzer.add_test_case("working", accession="0000320193-25-000073")
    analyzer.run_comparative_analysis()
    analyzer.generate_report()
"""

from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
import pandas as pd
from datetime import datetime
import json
import traceback
from pathlib import Path

# Ensure proper imports
try:
    from edgar import set_identity, Company, get_by_accession_number
except ImportError:
    print("Warning: Edgar imports not available. Some functionality may be limited.")

@dataclass
class TestCase:
    """Represents a test case for investigation"""
    name: str
    description: str
    accession: Optional[str] = None
    company: Optional[str] = None
    ticker: Optional[str] = None
    cik: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    category: Optional[str] = None

@dataclass
class InvestigationResult:
    """Results from investigation analysis"""
    test_case: TestCase
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    analysis_type: str = "general"

class IssueAnalyzer:
    """
    Central analyzer for systematic issue investigation

    Provides structured approach to analyzing EdgarTools issues with:
    - Comparative analysis across test cases
    - Standard metrics extraction
    - Pattern recognition
    - Comprehensive reporting
    """

    def __init__(self, issue_number: int, auto_identity: bool = True):
        self.issue_number = issue_number
        self.console = Console()
        self.test_cases: List[TestCase] = []
        self.results: List[InvestigationResult] = []

        if auto_identity:
            try:
                set_identity("Research Team research@edgartools-investigation.com")
            except:
                pass  # Identity setting not available

    def add_test_case(self, name: str, **kwargs) -> TestCase:
        """Add a test case for analysis"""
        test_case = TestCase(name=name, **kwargs)
        self.test_cases.append(test_case)
        return test_case

    def add_standard_test_cases(self, issue_pattern: str):
        """Add standard test cases for common issue patterns"""
        if issue_pattern == "empty_periods":
            self.add_test_case(
                "recent_working",
                description="Recent Apple filing that should work",
                accession="0000320193-25-000073",
                category="working_baseline"
            )
            self.add_test_case(
                "older_problematic",
                description="Older Apple filing with empty period issue",
                accession="0000320193-18-000070",
                category="problematic"
            )
            self.add_test_case(
                "older_problematic_2",
                description="Another problematic Apple filing",
                accession="0000320193-17-000009",
                category="problematic"
            )

        elif issue_pattern == "filing_access":
            # Issue #374 pattern - pagination/filing access issues
            self.add_test_case(
                "msft_filings",
                description="Microsoft filings - should have >4000 total",
                ticker="MSFT",
                category="large_cap_historical"
            )
            self.add_test_case(
                "aapl_filings",
                description="Apple filings - should have >1000 total",
                ticker="AAPL",
                category="large_cap_historical"
            )
        elif issue_pattern == "entity_facts":
            self.add_test_case(
                "apple_facts",
                description="Apple entity facts",
                ticker="AAPL",
                category="large_cap"
            )
            self.add_test_case(
                "tesla_facts",
                description="Tesla entity facts",
                ticker="TSLA",
                category="complex_structure"
            )

        elif issue_pattern == "xbrl_parsing":
            # Add standard XBRL parsing test cases
            self.add_test_case(
                "complex_filing",
                description="Complex multi-entity filing",
                accession="0001628280-17-004790",
                category="complex"
            )

    def run_comparative_analysis(self):
        """Run analysis across all test cases"""
        self.console.print(f"\n[bold blue]Starting Issue #{self.issue_number} Investigation[/bold blue]")
        self.console.print(f"Test cases: {len(self.test_cases)}")

        for i, test_case in enumerate(self.test_cases, 1):
            self.console.print(f"\n[cyan]Analyzing case {i}/{len(self.test_cases)}: {test_case.name}[/cyan]")
            result = self._analyze_single_case(test_case)
            self.results.append(result)

        self.console.print(f"\n[green]✅ Analysis complete[/green]")

    def _analyze_single_case(self, test_case: TestCase) -> InvestigationResult:
        """Analyze a single test case"""
        result = InvestigationResult(test_case=test_case, success=True)

        try:
            # Filing-based analysis
            if test_case.accession:
                result.analysis_type = "filing"
                filing = get_by_accession_number(test_case.accession)
                result.data['filing'] = filing

                # Standard filing analysis
                result.metrics.update(self._analyze_filing(filing))

            # Company-based analysis
            elif test_case.ticker:
                result.analysis_type = "company"
                company = Company(test_case.ticker)
                result.data['company'] = company
                result.metrics.update(self._analyze_company(company))

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            result.notes.append(f"Analysis failed: {traceback.format_exc()}")

        return result

    def _analyze_filing(self, filing) -> Dict[str, Any]:
        """Comprehensive filing analysis"""
        metrics = {
            'form': filing.form,
            'company': filing.company,
            'filing_date': str(filing.filing_date),
            'accession': filing.accession_no
        }

        try:
            # XBRL analysis if available
            xbrl = filing.xbrl()
            metrics['has_xbrl'] = True

            # Reporting periods analysis
            if hasattr(xbrl, 'reporting_periods'):
                periods = xbrl.reporting_periods
                metrics['total_reporting_periods'] = len(periods)
                metrics['reporting_periods'] = [p.get('label', str(p)) for p in periods[:5]]  # First 5

            # Statements analysis
            if hasattr(xbrl, 'statements'):
                statements = xbrl.statements

                # Cash flow statement analysis (most common issue area)
                metrics.update(self._analyze_cashflow_statement(statements))

                # Income statement analysis
                metrics.update(self._analyze_income_statement(statements))

                # Balance sheet analysis
                metrics.update(self._analyze_balance_sheet(statements))

        except Exception as e:
            metrics['xbrl_error'] = str(e)
            metrics['has_xbrl'] = False

        return metrics

    def _analyze_cashflow_statement(self, statements) -> Dict[str, Any]:
        """Detailed cash flow statement analysis"""
        cf_metrics = {}

        try:
            if hasattr(statements, 'cashflow_statement'):
                cf = statements.cashflow_statement()
                df = cf.to_dataframe()

                # Period analysis
                data_cols = [col for col in df.columns
                           if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

                cf_metrics['cf_total_periods'] = len(data_cols)
                cf_metrics['cf_periods'] = data_cols

                # Empty period analysis (Issue #408 pattern)
                empty_periods = []
                meaningful_periods = []
                period_analysis = {}

                for col in data_cols:
                    series = df[col]

                    # Multiple types of emptiness analysis
                    null_count = series.isnull().sum()
                    empty_string_count = (series == '').sum()
                    whitespace_count = series.astype(str).str.strip().eq('').sum() - empty_string_count
                    numeric_values = pd.to_numeric(series, errors='coerce').notna().sum()
                    total_rows = len(series)

                    period_info = {
                        'null_count': null_count,
                        'empty_string_count': empty_string_count,
                        'whitespace_count': whitespace_count,
                        'numeric_values': numeric_values,
                        'total_rows': total_rows,
                        'is_meaningful': numeric_values > 0,
                        'emptiness_ratio': (null_count + empty_string_count) / total_rows if total_rows > 0 else 1.0
                    }

                    period_analysis[col] = period_info

                    if numeric_values == 0:
                        empty_periods.append(col)
                    else:
                        meaningful_periods.append(col)

                cf_metrics['cf_empty_periods'] = empty_periods
                cf_metrics['cf_meaningful_periods'] = meaningful_periods
                cf_metrics['cf_empty_period_count'] = len(empty_periods)
                cf_metrics['cf_meaningful_period_count'] = len(meaningful_periods)
                cf_metrics['cf_period_analysis'] = period_analysis

                # Issue #408 specific: empty string detection
                cf_metrics['cf_has_empty_string_issue'] = len(empty_periods) > 0

        except Exception as e:
            cf_metrics['cf_analysis_error'] = str(e)

        return cf_metrics

    def _analyze_income_statement(self, statements) -> Dict[str, Any]:
        """Income statement analysis"""
        is_metrics = {}

        try:
            if hasattr(statements, 'income_statement'):
                income = statements.income_statement()
                df = income.to_dataframe()

                data_cols = [col for col in df.columns
                           if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

                is_metrics['is_total_periods'] = len(data_cols)
                is_metrics['is_periods'] = data_cols

                # Look for standard concepts
                concepts = df['concept'].tolist() if 'concept' in df.columns else []
                revenue_concepts = [c for c in concepts if 'revenue' in c.lower() or 'sales' in c.lower()]
                is_metrics['is_has_revenue_concepts'] = len(revenue_concepts) > 0
                is_metrics['is_revenue_concepts'] = revenue_concepts[:3]  # First 3

        except Exception as e:
            is_metrics['is_analysis_error'] = str(e)

        return is_metrics

    def _analyze_balance_sheet(self, statements) -> Dict[str, Any]:
        """Balance sheet analysis"""
        bs_metrics = {}

        try:
            if hasattr(statements, 'balance_sheet'):
                balance = statements.balance_sheet()
                df = balance.to_dataframe()

                data_cols = [col for col in df.columns
                           if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

                bs_metrics['bs_total_periods'] = len(data_cols)
                bs_metrics['bs_periods'] = data_cols

        except Exception as e:
            bs_metrics['bs_analysis_error'] = str(e)

        return bs_metrics

    def _analyze_company(self, company) -> Dict[str, Any]:
        """Company-level analysis"""
        metrics = {
            'cik': company.cik,
            'name': company.name,
            'ticker': getattr(company, 'ticker', None)
        }

        try:
            # MAINTAINER INSIGHT: Check for pagination issues (Issue #374)
            # NOTE: This issue may not reproduce in all environments
            # If total filings ≈ 1000, user may be stuck on first page of SEC submissions API
            try:
                all_filings = company.get_filings()
                filing_count = len(all_filings)
                metrics['total_filings'] = filing_count

                # Pagination analysis - issue may be environment-specific
                if 900 <= filing_count <= 1100:
                    metrics['pagination_warning'] = True
                    metrics['pagination_note'] = f"Potential pagination issue: {filing_count} filings (Issue #374 pattern - may be environment-specific)"
                else:
                    metrics['pagination_warning'] = False

                if filing_count > 0:
                    date_range = all_filings.date_range
                    metrics['filing_date_range'] = str(date_range)
                    metrics['earliest_filing_year'] = date_range[0].year if date_range[0] else None

            except Exception as e:
                metrics['filings_error'] = str(e)

            # Facts analysis if available
            if hasattr(company, 'facts'):
                facts = company.facts
                metrics['has_facts'] = True

                # Statement availability
                for stmt_type in ['income_statement', 'balance_sheet', 'cash_flow_statement']:
                    try:
                        stmt = getattr(facts, stmt_type)()
                        metrics[f'has_{stmt_type}'] = True

                        # Basic statement metrics
                        if hasattr(stmt, 'to_dataframe'):
                            df = stmt.to_dataframe()
                            metrics[f'{stmt_type}_shape'] = df.shape
                    except Exception as e:
                        metrics[f'has_{stmt_type}'] = False
                        metrics[f'{stmt_type}_error'] = str(e)

        except Exception as e:
            metrics['facts_error'] = str(e)
            metrics['has_facts'] = False

        return metrics

    def generate_report(self) -> str:
        """Generate comprehensive investigation report"""
        self.console.print(f"\n[bold green]Issue #{self.issue_number} Investigation Report[/bold green]")

        # Summary table
        self._print_summary_table()

        # Detailed analysis
        self._print_detailed_analysis()

        # Pattern detection
        self._detect_patterns()

        # Generate markdown report
        markdown_report = self._generate_markdown_report()

        # Save report to file
        report_path = f"investigation_report_{self.issue_number}.md"
        with open(report_path, "w") as f:
            f.write(markdown_report)

        self.console.print(f"\n[bold]📄 Report saved to: {report_path}[/bold]")

        return markdown_report

    def _print_summary_table(self):
        """Print summary table of results"""
        table = Table(title=f"Issue #{self.issue_number} Test Case Results")
        table.add_column("Test Case", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Cash Flow Periods", style="yellow")
        table.add_column("Empty Periods", style="red")
        table.add_column("Issue Present", style="magenta")

        for result in self.results:
            status = "✅ SUCCESS" if result.success else "❌ ERROR"

            # Cash flow specific metrics
            total_periods = result.metrics.get('cf_total_periods', 'N/A')
            empty_count = result.metrics.get('cf_empty_period_count', 'N/A')

            # Determine if issue is present
            has_issue = result.metrics.get('cf_has_empty_string_issue', False)
            issue_present = "❌ YES" if has_issue else "✅ NO"

            table.add_row(
                result.test_case.name,
                result.analysis_type,
                status,
                str(total_periods),
                str(empty_count),
                issue_present
            )

        self.console.print(table)

    def _print_detailed_analysis(self):
        """Print detailed analysis findings"""
        working_cases = [r for r in self.results
                        if r.success and not r.metrics.get('cf_has_empty_string_issue', False)]
        broken_cases = [r for r in self.results
                       if r.success and r.metrics.get('cf_has_empty_string_issue', False)]

        self.console.print(f"\n[bold]Analysis Summary:[/bold]")
        self.console.print(f"✅ Working cases: {len(working_cases)}")
        self.console.print(f"❌ Broken cases: {len(broken_cases)}")

        if broken_cases:
            self.console.print(f"\n[bold red]🔍 Issue Pattern Identified:[/bold red]")
            for broken in broken_cases:
                empty_periods = broken.metrics.get('cf_empty_periods', [])
                self.console.print(f"  📁 {broken.test_case.name}: {len(empty_periods)} empty periods")
                if empty_periods:
                    for period in empty_periods[:3]:  # Show first 3
                        self.console.print(f"    • {period}")

        if working_cases and broken_cases:
            self.console.print(f"\n[bold green]💡 Recommended Action:[/bold green]")
            self.console.print("Implement empty period filtering to resolve the issue")

    def _detect_patterns(self):
        """Detect common issue patterns"""
        self.console.print(f"\n[bold blue]🔍 Pattern Detection[/bold blue]")

        # Empty periods pattern (Issue #408)
        empty_period_cases = [r for r in self.results
                             if r.metrics.get('cf_has_empty_string_issue', False)]

        if empty_period_cases:
            self.console.print("✅ Empty String Periods Pattern Detected")
            self.console.print("   Similar to Issue #408 - Cash flow statement missing values")
            self.console.print("   Root cause: Periods contain empty strings instead of null values")

        # XBRL parsing patterns
        xbrl_errors = [r for r in self.results if 'xbrl_error' in r.metrics]
        if xbrl_errors:
            self.console.print("✅ XBRL Parsing Issues Detected")
            for result in xbrl_errors:
                error = result.metrics['xbrl_error']
                self.console.print(f"   {result.test_case.name}: {error[:100]}...")

        # Entity facts patterns
        facts_errors = [r for r in self.results if 'facts_error' in r.metrics]
        if facts_errors:
            self.console.print("✅ Entity Facts Issues Detected")

    def _generate_markdown_report(self) -> str:
        """Generate markdown investigation report"""
        report_lines = [
            f"# Issue #{self.issue_number} Investigation Report",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Test Cases**: {len(self.test_cases)}",
            f"**Investigation Tool**: EdgarTools Investigation Toolkit",
            "",
            "## Executive Summary",
            ""
        ]

        # Quick summary
        working_count = len([r for r in self.results if r.success and not r.metrics.get('cf_has_empty_string_issue', False)])
        broken_count = len([r for r in self.results if r.success and r.metrics.get('cf_has_empty_string_issue', False)])

        report_lines.extend([
            f"- **Working cases**: {working_count}",
            f"- **Broken cases**: {broken_count}",
            f"- **Success rate**: {len([r for r in self.results if r.success])}/{len(self.results)}",
            ""
        ])

        # Test case details
        report_lines.extend([
            "## Test Case Results",
            ""
        ])

        for result in self.results:
            report_lines.extend([
                f"### {result.test_case.name}",
                f"**Status**: {'✅ Success' if result.success else '❌ Error'}",
                f"**Description**: {result.test_case.description}",
                f"**Analysis Type**: {result.analysis_type}",
                ""
            ])

            if result.test_case.accession:
                report_lines.append(f"**Accession**: {result.test_case.accession}")

            # Key metrics
            if result.metrics:
                cf_periods = result.metrics.get('cf_total_periods')
                cf_empty = result.metrics.get('cf_empty_period_count')
                has_issue = result.metrics.get('cf_has_empty_string_issue')

                if cf_periods is not None:
                    report_lines.extend([
                        f"**Cash Flow Periods**: {cf_periods}",
                        f"**Empty Periods**: {cf_empty}",
                        f"**Has Issue**: {'Yes' if has_issue else 'No'}",
                    ])

            if result.errors:
                report_lines.extend([
                    "**Errors**:",
                    ""
                ])
                for error in result.errors:
                    report_lines.append(f"- {error}")

            report_lines.append("")

        # Pattern analysis
        report_lines.extend([
            "## Pattern Analysis",
            ""
        ])

        empty_period_cases = [r for r in self.results if r.metrics.get('cf_has_empty_string_issue', False)]
        if empty_period_cases:
            report_lines.extend([
                "### Empty String Periods Pattern Detected",
                "",
                "This pattern is consistent with Issue #408 where cash flow statements show empty columns.",
                "",
                "**Root Cause**: XBRL periods contain empty strings ('') instead of null values",
                "**Solution**: Implement period filtering to exclude periods with only empty string values",
                ""
            ])

        return "\n".join(report_lines)

# Quick Analysis Functions

def quick_analyze(pattern: str, identifier: str, **kwargs) -> Dict[str, Any]:
    """
    Quick analysis for common patterns

    Args:
        pattern: Analysis pattern ('empty_periods', 'xbrl_parsing', 'entity_facts')
        identifier: Company ticker, CIK, or accession number
        **kwargs: Additional parameters

    Returns:
        Analysis results dictionary
    """
    try:
        set_identity("Research Team research@edgartools-investigation.com")
    except:
        pass

    if pattern == "empty_periods":
        return analyze_empty_periods(identifier)
    elif pattern == "entity_facts":
        return analyze_entity_facts(identifier)
    elif pattern == "xbrl_parsing":
        return analyze_xbrl_parsing(identifier)
    else:
        raise ValueError(f"Unknown pattern: {pattern}")

def analyze_empty_periods(accession_or_ticker: str) -> Dict[str, Any]:
    """
    Standard empty period analysis for Issue #408 pattern

    Args:
        accession_or_ticker: Filing accession number or company ticker

    Returns:
        Dictionary with period analysis results
    """
    console = Console()
    console.print(f"[cyan]🔍 Analyzing empty periods for: {accession_or_ticker}[/cyan]")

    try:
        # Determine if it's an accession number or ticker
        if len(accession_or_ticker) > 15 and '-' in accession_or_ticker:
            # It's an accession number
            filing = get_by_accession_number(accession_or_ticker)
            cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        else:
            # It's a ticker - get latest filing
            company = Company(accession_or_ticker)
            filings = company.get_filings(form='10-Q').head(1)
            if filings.empty:
                filings = company.get_filings(form='10-K').head(1)
            filing = filings.iloc[0]
            cashflow_stmt = filing.xbrl().statements.cashflow_statement()

        df = cashflow_stmt.to_dataframe()

        data_cols = [col for col in df.columns
                    if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

        analysis = {}
        for col in data_cols:
            series = df[col]

            # Multiple types of empty analysis
            null_count = series.isnull().sum()
            empty_string_count = (series == '').sum()
            whitespace_count = series.astype(str).str.strip().eq('').sum() - empty_string_count
            numeric_values = pd.to_numeric(series, errors='coerce').notna().sum()

            analysis[col] = {
                'null_count': null_count,
                'empty_string_count': empty_string_count,
                'whitespace_count': whitespace_count,
                'numeric_values': numeric_values,
                'is_meaningful': numeric_values > 0,
                'total_rows': len(series),
                'emptiness_ratio': (null_count + empty_string_count) / len(series) if len(series) > 0 else 1.0
            }

        # Summary
        meaningful_periods = [col for col, data in analysis.items() if data['is_meaningful']]
        empty_periods = [col for col, data in analysis.items() if not data['is_meaningful']]

        console.print(f"✅ Analysis complete: {len(meaningful_periods)} meaningful, {len(empty_periods)} empty periods")

        return {
            'identifier': accession_or_ticker,
            'total_periods': len(data_cols),
            'meaningful_periods': meaningful_periods,
            'empty_periods': empty_periods,
            'period_analysis': analysis,
            'has_empty_string_issue': len(empty_periods) > 0,
            'success': True
        }

    except Exception as e:
        console.print(f"❌ Analysis failed: {str(e)}")
        return {
            'identifier': accession_or_ticker,
            'error': str(e),
            'success': False
        }

def analyze_entity_facts(ticker: str) -> Dict[str, Any]:
    """Analyze entity facts for common issues"""
    console = Console()
    console.print(f"[cyan]🔍 Analyzing entity facts for: {ticker}[/cyan]")

    try:
        company = Company(ticker)
        facts = company.facts

        analysis = {
            'ticker': ticker,
            'cik': company.cik,
            'name': company.name,
            'has_facts': True,
            'success': True
        }

        # Test statement availability
        for stmt_type in ['income_statement', 'balance_sheet', 'cash_flow_statement']:
            try:
                stmt = getattr(facts, stmt_type)()
                analysis[f'has_{stmt_type}'] = True

                if hasattr(stmt, 'to_dataframe'):
                    df = stmt.to_dataframe()
                    analysis[f'{stmt_type}_shape'] = df.shape
            except Exception as e:
                analysis[f'has_{stmt_type}'] = False
                analysis[f'{stmt_type}_error'] = str(e)

        console.print(f"✅ Entity facts analysis complete")
        return analysis

    except Exception as e:
        console.print(f"❌ Entity facts analysis failed: {str(e)}")
        return {
            'ticker': ticker,
            'error': str(e),
            'success': False
        }

def analyze_xbrl_parsing(accession: str) -> Dict[str, Any]:
    """Analyze XBRL parsing for common issues"""
    console = Console()
    console.print(f"[cyan]🔍 Analyzing XBRL parsing for: {accession}[/cyan]")

    try:
        filing = get_by_accession_number(accession)
        xbrl = filing.xbrl()

        analysis = {
            'accession': accession,
            'form': filing.form,
            'company': filing.company,
            'has_xbrl': True,
            'success': True
        }

        # Basic XBRL metrics
        if hasattr(xbrl, 'reporting_periods'):
            analysis['reporting_periods_count'] = len(xbrl.reporting_periods)

        if hasattr(xbrl, 'facts'):
            analysis['facts_count'] = len(xbrl.facts)

        # Test statement access
        if hasattr(xbrl, 'statements'):
            statements = xbrl.statements
            analysis['has_statements'] = True

            for stmt_name in ['cashflow_statement', 'income_statement', 'balance_sheet']:
                try:
                    stmt = getattr(statements, stmt_name)()
                    analysis[f'has_{stmt_name}'] = True
                except Exception as e:
                    analysis[f'has_{stmt_name}'] = False
                    analysis[f'{stmt_name}_error'] = str(e)

        console.print(f"✅ XBRL parsing analysis complete")
        return analysis

    except Exception as e:
        console.print(f"❌ XBRL parsing analysis failed: {str(e)}")
        return {
            'accession': accession,
            'error': str(e),
            'success': False
        }

def compare_filings(accession1: str, accession2: str,
                   description1: str = "Filing 1", description2: str = "Filing 2") -> Dict[str, Any]:
    """
    Compare two filings for differences

    Args:
        accession1: First filing accession number
        accession2: Second filing accession number
        description1: Description for first filing
        description2: Description for second filing

    Returns:
        Comparison results dictionary
    """
    console = Console()

    console.print(f"\n[bold blue]📊 Comparative Analysis[/bold blue]")
    console.print(f"📁 {description1}: {accession1}")
    console.print(f"📁 {description2}: {accession2}")

    analysis1 = analyze_empty_periods(accession1)
    analysis2 = analyze_empty_periods(accession2)

    if not (analysis1['success'] and analysis2['success']):
        console.print("❌ One or both analyses failed")
        return {
            'analysis1': analysis1,
            'analysis2': analysis2,
            'comparison_failed': True
        }

    # Comparison table
    table = Table(title="Filing Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column(description1, style="blue")
    table.add_column(description2, style="green")
    table.add_column("Difference", style="magenta")

    periods1 = analysis1['total_periods']
    periods2 = analysis2['total_periods']
    meaningful1 = len(analysis1['meaningful_periods'])
    meaningful2 = len(analysis2['meaningful_periods'])
    empty1 = len(analysis1['empty_periods'])
    empty2 = len(analysis2['empty_periods'])

    table.add_row("Total Periods", str(periods1), str(periods2), str(periods2 - periods1))
    table.add_row("Meaningful Periods", str(meaningful1), str(meaningful2), str(meaningful2 - meaningful1))
    table.add_row("Empty Periods", str(empty1), str(empty2), str(empty2 - empty1))

    console.print(table)

    # Issue assessment
    issue1 = analysis1['has_empty_string_issue']
    issue2 = analysis2['has_empty_string_issue']

    if issue1 and not issue2:
        console.print(f"[red]🔍 Issue found in {description1} but not {description2}[/red]")
    elif issue2 and not issue1:
        console.print(f"[red]🔍 Issue found in {description2} but not {description1}[/red]")
    elif issue1 and issue2:
        console.print(f"[yellow]⚠️  Issue found in both filings[/yellow]")
    else:
        console.print(f"[green]✅ No issues found in either filing[/green]")

    return {
        'filing1': analysis1,
        'filing2': analysis2,
        'summary': {
            'periods_diff': periods2 - periods1,
            'meaningful_diff': meaningful2 - meaningful1,
            'empty_diff': empty2 - empty1,
            'issue_pattern': issue1 or issue2,
            'both_have_issues': issue1 and issue2,
            'neither_have_issues': not issue1 and not issue2
        }
    }

# Standard test company data
STANDARD_TEST_COMPANIES = {
    'AAPL': {
        'cik': '0000320193',
        'known_issues': ['empty_periods_2018'],
        'working_filings': ['0000320193-25-000073'],  # Q2 2025
        'problematic_filings': ['0000320193-18-000070', '0000320193-17-000009'],  # Q1 2018, Q3 2017
        'fiscal_year_end': 'September'
    },
    'MSFT': {
        'cik': '0001611878',
        'fiscal_year_end': 'June',
        'notes': 'Good for fiscal year boundary testing'
    },
    'TSLA': {
        'cik': '0001318605',
        'known_issues': ['complex_financials'],
        'notes': 'Complex multi-segment reporting'
    }
}

def get_test_company_info(ticker: str) -> Dict[str, Any]:
    """Get standard test company information"""
    return STANDARD_TEST_COMPANIES.get(ticker.upper(), {})

def visual_debug(identifier, issue_type="auto"):
    """
    Visual debugging - show what the user sees

    Args:
        identifier: Accession number, ticker, or filing
        issue_type: Type of issue to debug ('empty_periods', 'xbrl_parsing', 'entity_facts', 'auto')
    """
    from tools.visual_inspector import (
        show_statement, show_filing_overview, show_company_overview,
        show_xbrl, compare_statements_visually
    )

    console.print(f"\n[bold green]🔍 Visual Debug Session[/bold green]")
    console.print(f"Identifier: {identifier}")

    if issue_type == "auto":
        # Auto-detect what to show
        if isinstance(identifier, str):
            if len(identifier) > 15 and '-' in identifier:
                issue_type = "filing_analysis"
            else:
                issue_type = "company_analysis"

    if issue_type in ["empty_periods", "filing_analysis"]:
        # Show cash flow statement (most common empty periods issue)
        console.print(f"\n[cyan]📊 Cash Flow Statement Visual Analysis[/cyan]")
        show_statement(identifier, "cashflow")

        # Compare with a known working filing
        if identifier != "0000320193-25-000073":  # Don't compare with itself
            console.print(f"\n[cyan]📊 Comparison with Known Working Filing[/cyan]")
            compare_statements_visually(
                identifier,
                "0000320193-25-000073",  # Known working Apple filing
                "cashflow",
                "Your Filing",
                "Apple Q2 2025 (Working)"
            )

    elif issue_type in ["entity_facts", "company_analysis"]:
        # Show company facts analysis
        console.print(f"\n[cyan]🏢 Company Facts Visual Analysis[/cyan]")
        show_company_overview(identifier)

    elif issue_type == "xbrl_parsing":
        # Show XBRL structure analysis
        console.print(f"\n[cyan]🔍 XBRL Structure Analysis[/cyan]")
        filing = get_by_accession_number(identifier) if isinstance(identifier, str) else identifier
        show_filing_overview(filing)

        try:
            xbrl = filing.xbrl()
            show_xbrl(xbrl, sections=['basic', 'periods', 'facts'])
        except Exception as e:
            console.print(f"[red]❌ XBRL analysis failed: {str(e)}[/red]")

    else:
        # General analysis
        if isinstance(identifier, str) and len(identifier) > 15:
            show_filing_overview(identifier)
        else:
            show_company_overview(identifier)

# Quick visual debugging functions
def debug_empty_periods(accession):
    """Quick visual debug for empty periods issues"""
    return visual_debug(accession, "empty_periods")

def debug_entity_facts(ticker):
    """Quick visual debug for entity facts issues"""
    return visual_debug(ticker, "entity_facts")

def debug_xbrl_parsing(accession):
    """Quick visual debug for XBRL parsing issues"""
    return visual_debug(accession, "xbrl_parsing")

if __name__ == "__main__":
    # Example usage
    print("EdgarTools Investigation Toolkit")
    print("Available functions:")
    print("- quick_analyze(pattern, identifier)")
    print("- IssueAnalyzer(issue_number)")
    print("- compare_filings(accession1, accession2)")
    print("- analyze_empty_periods(accession_or_ticker)")
    print("")
    print("Visual debugging functions:")
    print("- visual_debug(identifier, issue_type)")
    print("- debug_empty_periods(accession)")
    print("- debug_entity_facts(ticker)")
    print("- debug_xbrl_parsing(accession)")