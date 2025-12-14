"""
EdgarTools Visual Inspector
Tools for visually inspecting statements, dataframes, and XBRL data

As a maintainer, you need to SEE what the data looks like quickly.
These tools provide rich visual output for rapid data inspection.

Usage:
    from tools.visual_inspector import show_statement, show_dataframe, show_xbrl

    # Quick visual inspection
    show_statement(filing, "cashflow")
    show_dataframe(df, title="Cash Flow Data")
    show_xbrl(xbrl, sections=["facts", "periods", "contexts"])
"""


import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure proper imports
try:
    from edgar import Company, get_by_accession_number, set_identity
except ImportError:
    print("Warning: Edgar imports not available. Some functionality may be limited.")

console = Console()

def show_statement(filing_or_accession, statement_type="cashflow", max_rows=20, max_cols=None):
    """
    Visually inspect a financial statement

    Args:
        filing_or_accession: Filing object or accession number
        statement_type: 'cashflow', 'income', 'balance'
        max_rows: Maximum rows to display
        max_cols: Maximum columns to display (None = all)
    """
    console.print(f"\n[bold blue]📊 {statement_type.title()} Statement Inspection[/bold blue]")

    try:
        # Get the filing
        if isinstance(filing_or_accession, str):
            filing = get_by_accession_number(filing_or_accession)
            console.print(f"Filing: {filing.accession_no}")
        else:
            filing = filing_or_accession

        console.print(f"Company: {filing.company}")
        console.print(f"Form: {filing.form} | Date: {filing.filing_date}")

        # Get the statement
        xbrl = filing.xbrl()
        statements = xbrl.statements

        if statement_type.lower() in ['cashflow', 'cash', 'cf']:
            stmt = statements.cashflow_statement()
            stmt_name = "Cash Flow Statement"
        elif statement_type.lower() in ['income', 'is', 'pnl']:
            stmt = statements.income_statement()
            stmt_name = "Income Statement"
        elif statement_type.lower() in ['balance', 'bs', 'balancesheet']:
            stmt = statements.balance_sheet()
            stmt_name = "Balance Sheet"
        else:
            raise ValueError(f"Unknown statement type: {statement_type}")

        console.print(f"\n[cyan]Statement: {stmt_name}[/cyan]")

        # Get dataframe
        df = stmt.to_dataframe()
        console.print(f"Shape: {df.shape}")

        # Show the actual statement (what user sees)
        console.print("\n[bold green]📋 What the user sees (rendered statement):[/bold green]")

        # Try to show the rendered statement
        try:
            # This is what the user actually sees when they print the statement
            console.print(Panel(str(stmt), title="Rendered Statement", expand=False))
        except Exception as e:
            console.print(f"[yellow]Could not render statement: {e}[/yellow]")

        # Show the dataframe structure
        show_dataframe(df, title=f"{stmt_name} DataFrame", max_rows=max_rows, max_cols=max_cols)

        # Period analysis
        data_cols = [col for col in df.columns
                    if col not in ['concept', 'label', 'level', 'abstract', 'dimension']]

        console.print("\n[bold yellow]📅 Period Analysis:[/bold yellow]")
        period_table = Table(title="Periods Found")
        period_table.add_column("Period", style="cyan")
        period_table.add_column("Data Points", style="green")
        period_table.add_column("Empty Values", style="red")
        period_table.add_column("Status", style="bold")

        for col in data_cols:
            series = df[col]
            non_null = series.notna().sum()
            null_count = series.isna().sum()

            # Check for empty strings (Issue #408 pattern)
            empty_strings = (series == '').sum()
            numeric_values = pd.to_numeric(series, errors='coerce').notna().sum()

            if numeric_values > 0:
                status = "✅ HAS DATA"
                status_style = "green"
            elif empty_strings > 0:
                status = "❌ EMPTY STRINGS"
                status_style = "red"
            else:
                status = "⚠️  NULL VALUES"
                status_style = "yellow"

            period_table.add_row(
                col,
                str(numeric_values),
                str(null_count + empty_strings),
                f"[{status_style}]{status}[/{status_style}]"
            )

        console.print(period_table)

        return {
            'statement': stmt,
            'dataframe': df,
            'periods': data_cols,
            'shape': df.shape
        }

    except Exception as e:
        console.print(f"[red]❌ Error inspecting statement: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        return None

def show_dataframe(df, title="DataFrame", max_rows=20, max_cols=None, show_dtypes=True):
    """
    Visually inspect a pandas DataFrame with rich formatting

    Args:
        df: Pandas DataFrame
        title: Title for the display
        max_rows: Maximum rows to show
        max_cols: Maximum columns to show (None = all)
        show_dtypes: Whether to show column data types
    """
    console.print(f"\n[bold blue]📊 {title}[/bold blue]")

    if df is None or df.empty:
        console.print("[red]❌ DataFrame is empty or None[/red]")
        return

    console.print(f"Shape: {df.shape}")

    # Show column info
    if show_dtypes:
        console.print("\n[cyan]📋 Column Info:[/cyan]")
        col_table = Table(title="Columns")
        col_table.add_column("Column", style="cyan")
        col_table.add_column("Type", style="green")
        col_table.add_column("Non-Null", style="blue")
        col_table.add_column("Sample Values", style="yellow")

        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].notna().sum()

            # Get sample values (first few non-null)
            sample_values = df[col].dropna().head(3).tolist()
            sample_str = ", ".join([str(v)[:30] for v in sample_values])
            if len(sample_str) > 50:
                sample_str = sample_str[:47] + "..."

            col_table.add_row(col, dtype, f"{non_null}/{len(df)}", sample_str)

        console.print(col_table)

    # Show the actual data
    console.print(f"\n[cyan]📊 Data Preview (first {min(max_rows, len(df))} rows):[/cyan]")

    # Limit columns if requested
    display_df = df
    if max_cols and len(df.columns) > max_cols:
        display_df = df.iloc[:, :max_cols]
        console.print(f"[yellow]Note: Showing first {max_cols} of {len(df.columns)} columns[/yellow]")

    # Limit rows
    display_df = display_df.head(max_rows)

    # Create rich table
    table = Table(title=f"{title} Data")

    # Add columns
    for col in display_df.columns:
        table.add_column(col, style="white", overflow="fold")

    # Add rows
    for _, row in display_df.iterrows():
        # Format values for display
        formatted_row = []
        for val in row:
            if pd.isna(val):
                formatted_row.append("[dim]NULL[/dim]")
            elif val == '':
                formatted_row.append("[red]''[/red]")  # Empty string highlighting
            elif isinstance(val, float) and abs(val) > 1000000:
                # Format large numbers
                formatted_row.append(f"{val:,.0f}")
            else:
                str_val = str(val)
                if len(str_val) > 30:
                    str_val = str_val[:27] + "..."
                formatted_row.append(str_val)

        table.add_row(*formatted_row)

    console.print(table)

    # Show summary stats for numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        console.print("\n[cyan]📈 Numeric Summary:[/cyan]")
        stats_df = df[numeric_cols].describe()
        show_dataframe(stats_df, title="Statistics", max_rows=10, show_dtypes=False)

def show_xbrl(xbrl, sections=None, max_items=10):
    """
    Visually inspect XBRL data structure

    Args:
        xbrl: XBRL object
        sections: List of sections to show ['facts', 'contexts', 'periods', 'elements']
        max_items: Maximum items to show per section
    """
    if sections is None:
        sections = ['basic', 'periods', 'facts', 'contexts']

    console.print("\n[bold blue]🔍 XBRL Structure Inspection[/bold blue]")

    try:
        # Basic info
        if 'basic' in sections:
            console.print("\n[cyan]📋 Basic Information:[/cyan]")
            basic_table = Table(title="XBRL Overview")
            basic_table.add_column("Property", style="cyan")
            basic_table.add_column("Value", style="green")

            if hasattr(xbrl, 'entity_name'):
                basic_table.add_row("Entity Name", str(xbrl.entity_name))
            if hasattr(xbrl, 'period_of_report'):
                basic_table.add_row("Period of Report", str(xbrl.period_of_report))
            if hasattr(xbrl, 'facts'):
                basic_table.add_row("Total Facts", str(len(xbrl.facts)))
            if hasattr(xbrl, 'contexts'):
                basic_table.add_row("Total Contexts", str(len(xbrl.contexts)))
            if hasattr(xbrl, 'reporting_periods'):
                basic_table.add_row("Reporting Periods", str(len(xbrl.reporting_periods)))

            console.print(basic_table)

        # Reporting periods
        if 'periods' in sections and hasattr(xbrl, 'reporting_periods'):
            console.print("\n[cyan]📅 Reporting Periods:[/cyan]")
            periods_table = Table(title="Available Periods")
            periods_table.add_column("Index", style="blue")
            periods_table.add_column("Key", style="cyan")
            periods_table.add_column("Label", style="green")
            periods_table.add_column("Type", style="yellow")

            for i, period in enumerate(xbrl.reporting_periods[:max_items]):
                key = period.get('key', 'N/A')
                label = period.get('label', 'N/A')
                period_type = period.get('type', 'N/A')

                periods_table.add_row(str(i), key, label, period_type)

            if len(xbrl.reporting_periods) > max_items:
                periods_table.add_row("...", f"({len(xbrl.reporting_periods) - max_items} more)", "", "")

            console.print(periods_table)

        # Facts overview
        if 'facts' in sections and hasattr(xbrl, 'facts'):
            console.print("\n[cyan]📊 Facts Overview:[/cyan]")
            facts = xbrl.facts

            # Sample facts
            facts_table = Table(title=f"Sample Facts (showing {min(max_items, len(facts))} of {len(facts)})")
            facts_table.add_column("Fact ID", style="blue")
            facts_table.add_column("Element", style="cyan")
            facts_table.add_column("Value", style="green")
            facts_table.add_column("Context", style="yellow")

            fact_items = list(facts.items())[:max_items]
            for fact_id, fact in fact_items:
                element = getattr(fact, 'element_id', 'N/A')
                value = getattr(fact, 'value', 'N/A')
                context = getattr(fact, 'context_ref', 'N/A')

                # Truncate long values
                if isinstance(value, str) and len(value) > 30:
                    value = value[:27] + "..."

                facts_table.add_row(fact_id[:20], element[:30], str(value), context[:20])

            console.print(facts_table)

        # Contexts overview
        if 'contexts' in sections and hasattr(xbrl, 'contexts'):
            console.print("\n[cyan]🗂️  Contexts Overview:[/cyan]")
            contexts = xbrl.contexts

            # Context types analysis
            instant_contexts = 0
            duration_contexts = 0

            contexts_table = Table(title=f"Sample Contexts (showing {min(max_items, len(contexts))} of {len(contexts)})")
            contexts_table.add_column("Context ID", style="blue")
            contexts_table.add_column("Period Type", style="cyan")
            contexts_table.add_column("Period Info", style="green")
            contexts_table.add_column("Dimensions", style="yellow")

            context_items = list(contexts.items())[:max_items]
            for context_id, context in context_items:
                try:
                    context_data = context.model_dump() if hasattr(context, 'model_dump') else {}
                    period = context_data.get('period', {})
                    period_type = period.get('type', 'Unknown')

                    if period_type == 'instant':
                        instant_contexts += 1
                        period_info = period.get('instant', 'N/A')
                    elif period_type == 'duration':
                        duration_contexts += 1
                        start = period.get('startDate', 'N/A')
                        end = period.get('endDate', 'N/A')
                        period_info = f"{start} to {end}"
                    else:
                        period_info = 'N/A'

                    # Check for dimensions
                    dimensions = context_data.get('dimensions', {})
                    dim_count = len(dimensions) if dimensions else 0
                    dim_info = f"{dim_count} dims" if dim_count > 0 else "No dims"

                    contexts_table.add_row(context_id[:20], period_type, period_info[:30], dim_info)

                except Exception as e:
                    contexts_table.add_row(context_id[:20], "Error", str(e)[:30], "N/A")

            console.print(contexts_table)

            # Context summary
            console.print(f"Context Types: {instant_contexts} instant, {duration_contexts} duration")

        # Elements (if available)
        if 'elements' in sections and hasattr(xbrl, 'element_catalog'):
            console.print("\n[cyan]🏷️  Element Catalog:[/cyan]")
            catalog = xbrl.element_catalog

            elements_table = Table(title=f"Sample Elements (showing {min(max_items, len(catalog))} of {len(catalog)})")
            elements_table.add_column("Element ID", style="blue")
            elements_table.add_column("Name", style="cyan")
            elements_table.add_column("Type", style="green")

            element_items = list(catalog.items())[:max_items]
            for element_id, element in element_items:
                name = getattr(element, 'name', 'N/A')
                element_type = getattr(element, 'type', 'N/A')

                elements_table.add_row(element_id[:30], name[:40], str(element_type))

            console.print(elements_table)

    except Exception as e:
        console.print(f"[red]❌ Error inspecting XBRL: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

def show_filing_overview(filing_or_accession):
    """
    Quick overview of a filing - what's available and accessible

    Args:
        filing_or_accession: Filing object or accession number
    """
    console.print("\n[bold blue]📄 Filing Overview[/bold blue]")

    try:
        # Get the filing
        if isinstance(filing_or_accession, str):
            filing = get_by_accession_number(filing_or_accession)
        else:
            filing = filing_or_accession

        # Basic filing info
        filing_table = Table(title="Filing Information")
        filing_table.add_column("Property", style="cyan")
        filing_table.add_column("Value", style="green")

        filing_table.add_row("Accession Number", filing.accession_no)
        filing_table.add_row("Company", filing.company)
        filing_table.add_row("Form Type", filing.form)
        filing_table.add_row("Filing Date", str(filing.filing_date))

        if hasattr(filing, 'cik'):
            filing_table.add_row("CIK", filing.cik)
        if hasattr(filing, 'period_of_report'):
            filing_table.add_row("Period of Report", str(filing.period_of_report))

        console.print(filing_table)

        # Test XBRL availability
        console.print("\n[cyan]🔍 XBRL Availability Test:[/cyan]")

        try:
            xbrl = filing.xbrl()
            console.print("✅ XBRL accessible")

            # Test statements
            if hasattr(xbrl, 'statements'):
                statements = xbrl.statements
                console.print("✅ Statements accessible")

                statement_tests = [
                    ('Cash Flow', 'cashflow_statement'),
                    ('Income Statement', 'income_statement'),
                    ('Balance Sheet', 'balance_sheet')
                ]

                for name, method in statement_tests:
                    try:
                        stmt = getattr(statements, method)()
                        df = stmt.to_dataframe()
                        console.print(f"  ✅ {name}: {df.shape}")
                    except Exception as e:
                        console.print(f"  ❌ {name}: {str(e)}")
            else:
                console.print("❌ Statements not accessible")

        except Exception as e:
            console.print(f"❌ XBRL not accessible: {str(e)}")

        return filing

    except Exception as e:
        console.print(f"[red]❌ Error accessing filing: {str(e)}[/red]")
        return None

def show_company_overview(ticker_or_cik):
    """
    Quick overview of a company - facts, statements, recent filings

    Args:
        ticker_or_cik: Company ticker or CIK
    """
    console.print("\n[bold blue]🏢 Company Overview[/bold blue]")

    try:
        company = Company(ticker_or_cik)

        # Basic company info
        company_table = Table(title="Company Information")
        company_table.add_column("Property", style="cyan")
        company_table.add_column("Value", style="green")

        company_table.add_row("Name", company.name)
        company_table.add_row("CIK", company.cik)

        if hasattr(company, 'ticker'):
            company_table.add_row("Ticker", company.ticker)
        if hasattr(company, 'exchange'):
            company_table.add_row("Exchange", company.exchange)

        console.print(company_table)

        # Test facts availability
        console.print("\n[cyan]📊 Facts Availability Test:[/cyan]")

        try:
            facts = company.facts
            console.print("✅ Facts accessible")

            # Test statements from facts
            statement_tests = [
                ('Income Statement', 'income_statement'),
                ('Balance Sheet', 'balance_sheet'),
                ('Cash Flow Statement', 'cash_flow_statement')
            ]

            for name, method in statement_tests:
                try:
                    stmt = getattr(facts, method)()
                    df = stmt.to_dataframe()
                    console.print(f"  ✅ {name}: {df.shape}")
                except Exception as e:
                    console.print(f"  ❌ {name}: {str(e)[:50]}")

        except Exception as e:
            console.print(f"❌ Facts not accessible: {str(e)}")

        # Recent filings
        console.print("\n[cyan]📄 Recent Filings:[/cyan]")

        try:
            recent_filings = company.get_filings(form=['10-K', '10-Q']).head(5)

            if not recent_filings.empty:
                filings_table = Table(title="Recent 10-K/10-Q Filings")
                filings_table.add_column("Form", style="blue")
                filings_table.add_column("Filing Date", style="cyan")
                filings_table.add_column("Accession", style="green")

                for _, filing in recent_filings.iterrows():
                    filings_table.add_row(
                        filing['form'],
                        str(filing['filing_date']),
                        filing['accession_number']
                    )

                console.print(filings_table)
            else:
                console.print("❌ No recent 10-K/10-Q filings found")

        except Exception as e:
            console.print(f"❌ Could not get recent filings: {str(e)}")

        return company

    except Exception as e:
        console.print(f"[red]❌ Error accessing company: {str(e)}[/red]")
        return None

def compare_statements_visually(accession1, accession2, statement_type="cashflow",
                              desc1="Filing 1", desc2="Filing 2"):
    """
    Visual side-by-side comparison of statements from two filings

    Args:
        accession1: First filing accession number
        accession2: Second filing accession number
        statement_type: Type of statement to compare
        desc1: Description for first filing
        desc2: Description for second filing
    """
    console.print("\n[bold blue]📊 Visual Statement Comparison[/bold blue]")
    console.print(f"Comparing {statement_type} statements:")
    console.print(f"  📄 {desc1}: {accession1}")
    console.print(f"  📄 {desc2}: {accession2}")

    results = {}

    for accession, desc in [(accession1, desc1), (accession2, desc2)]:
        console.print(f"\n[cyan]--- {desc} ---[/cyan]")

        try:
            result = show_statement(accession, statement_type, max_rows=15)
            results[desc] = result

        except Exception as e:
            console.print(f"[red]❌ Failed to load {desc}: {str(e)}[/red]")
            results[desc] = None

    # Summary comparison
    if all(results.values()):
        console.print("\n[bold green]📋 Summary Comparison[/bold green]")

        comparison_table = Table(title="Statement Comparison")
        comparison_table.add_column("Metric", style="cyan")
        comparison_table.add_column(desc1, style="blue")
        comparison_table.add_column(desc2, style="green")
        comparison_table.add_column("Difference", style="yellow")

        for desc in [desc1, desc2]:
            result = results[desc]
            if result:
                shape = result['shape']
                periods = len(result['periods'])

                if desc == desc1:
                    shape1, periods1 = shape, periods
                else:
                    shape2, periods2 = shape, periods

        comparison_table.add_row("DataFrame Shape", f"{shape1}", f"{shape2}",
                               f"Δ rows: {shape2[0] - shape1[0]}, Δ cols: {shape2[1] - shape1[1]}")
        comparison_table.add_row("Periods Count", f"{periods1}", f"{periods2}",
                               f"Δ: {periods2 - periods1}")

        console.print(comparison_table)

    return results

# Quick access functions for common inspection tasks

def quick_look(identifier, what="auto"):
    """
    Quick look at any EdgarTools object

    Args:
        identifier: Accession number, ticker, or object
        what: What to show ('auto', 'filing', 'company', 'statement')
    """
    if what == "auto":
        if isinstance(identifier, str):
            if len(identifier) > 15 and '-' in identifier:
                what = "filing"
            else:
                what = "company"
        else:
            what = "object"

    if what == "filing":
        return show_filing_overview(identifier)
    elif what == "company":
        return show_company_overview(identifier)
    elif what == "statement":
        return show_statement(identifier)
    else:
        console.print(f"[yellow]Unknown inspection type: {what}[/yellow]")
        return None

# Convenience aliases
def peek(identifier):
    """Quick peek at any EdgarTools identifier"""
    return quick_look(identifier)

def inspect_cashflow(accession):
    """Quick cash flow statement inspection"""
    return show_statement(accession, "cashflow")

def inspect_income(accession):
    """Quick income statement inspection"""
    return show_statement(accession, "income")

def inspect_balance(accession):
    """Quick balance sheet inspection"""
    return show_statement(accession, "balance")

if __name__ == "__main__":
    # Example usage
    console.print("[bold green]EdgarTools Visual Inspector[/bold green]")
    console.print("Available functions:")
    console.print("- show_statement(accession, 'cashflow')")
    console.print("- show_dataframe(df)")
    console.print("- show_xbrl(xbrl)")
    console.print("- show_filing_overview(accession)")
    console.print("- show_company_overview(ticker)")
    console.print("- compare_statements_visually(acc1, acc2)")
    console.print("- quick_look(identifier)  # Auto-detect what to show")
    console.print("- peek(identifier)  # Alias for quick_look")
