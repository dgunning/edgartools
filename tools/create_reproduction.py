"""
Reproduction Script Generator

Automatically creates issue reproduction scripts from templates.

Usage:
    python tools/create_reproduction.py --issue 408 --pattern empty-periods --accession 0000320193-18-000070
    python tools/create_reproduction.py --issue 412 --pattern entity-facts --ticker AAPL
    python tools/create_reproduction.py --issue 334 --pattern xbrl-parsing --accession 0001628280-17-004790
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.panel import Panel

console = Console()

# Template mappings
PATTERN_TEMPLATES = {
    'empty-periods': 'empty_periods_reproduction.py',
    'xbrl-parsing': 'xbrl_parsing_reproduction.py',
    'entity-facts': 'entity_facts_reproduction.py'
}

# Category mapping for file organization
PATTERN_CATEGORIES = {
    'empty-periods': 'data-quality',
    'xbrl-parsing': 'xbrl-parsing',
    'entity-facts': 'entity-facts'
}

def get_template_path(pattern: str) -> Path:
    """Get the template file path for a pattern"""
    template_name = PATTERN_TEMPLATES.get(pattern)
    if not template_name:
        raise ValueError(f"Unknown pattern: {pattern}")

    template_path = Path(__file__).parent / "templates" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    return template_path

def get_output_path(issue_number: int, pattern: str, custom_name: str = None) -> Path:
    """Get the output file path for the reproduction script"""
    category = PATTERN_CATEGORIES.get(pattern, 'general')

    # Create the directory structure
    output_dir = project_root / "tests" / "issues" / "reproductions" / category
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    if custom_name:
        filename = f"issue_{issue_number}_{custom_name}.py"
    else:
        filename = f"issue_{issue_number}_{pattern.replace('-', '_')}_reproduction.py"

    return output_dir / filename

def create_reproduction_script(
    issue_number: int,
    pattern: str,
    reporter: str = None,
    accession: str = None,
    ticker: str = None,
    company_name: str = None,
    cik: str = None,
    expected_behavior: str = None,
    actual_behavior: str = None,
    error_message: str = None,
    custom_name: str = None
) -> Path:
    """
    Create a reproduction script from template

    Args:
        issue_number: GitHub issue number
        pattern: Investigation pattern (empty-periods, xbrl-parsing, entity-facts)
        reporter: GitHub username of issue reporter
        accession: Filing accession number
        ticker: Company ticker symbol
        company_name: Company name
        cik: Company CIK
        expected_behavior: What should happen
        actual_behavior: What actually happens
        error_message: Specific error message
        custom_name: Custom name for the output file

    Returns:
        Path to the created reproduction script
    """

    # Get template and output paths
    template_path = get_template_path(pattern)
    output_path = get_output_path(issue_number, pattern, custom_name)

    # Read template
    with open(template_path, 'r') as f:
        template_content = f.read()

    # Prepare replacements
    replacements = {
        'ISSUE_NUMBER': str(issue_number),
        'REPORTER_USERNAME': reporter or 'unknown',
        'ACCESSION_NUMBER': accession or 'REPLACE_WITH_ACCESSION',
        'COMPANY_TICKER': ticker or 'REPLACE_WITH_TICKER',
        'COMPANY_NAME': company_name or 'REPLACE_WITH_COMPANY_NAME',
        'COMPANY_CIK': cik or 'REPLACE_WITH_CIK',
        'EXPECTED_BEHAVIOR': expected_behavior or 'REPLACE_WITH_EXPECTED_BEHAVIOR',
        'ACTUAL_BEHAVIOR': actual_behavior or 'REPLACE_WITH_ACTUAL_BEHAVIOR',
        'ERROR_MESSAGE': error_message or 'REPLACE_WITH_ERROR_MESSAGE'
    }

    # Apply replacements
    content = template_content
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    # Write the reproduction script
    with open(output_path, 'w') as f:
        f.write(content)

    return output_path

def interactive_creation():
    """Interactive reproduction script creation"""
    console.print(Panel.fit(
        "[bold blue]Interactive Reproduction Script Creator[/bold blue]",
        border_style="blue"
    ))

    # Get basic information
    issue_number = int(console.input("Issue number: "))
    pattern = console.input("Pattern (empty-periods/xbrl-parsing/entity-facts): ")

    if pattern not in PATTERN_TEMPLATES:
        console.print(f"[red]Unknown pattern: {pattern}[/red]")
        console.print(f"Available patterns: {list(PATTERN_TEMPLATES.keys())}")
        return

    # Get optional information
    reporter = console.input("Reporter GitHub username (optional): ") or None
    company_name = console.input("Company name (optional): ") or None

    # Pattern-specific inputs
    if pattern in ['empty-periods', 'xbrl-parsing']:
        accession = console.input("Filing accession number: ") or None
        ticker = None
        cik = None
    elif pattern == 'entity-facts':
        ticker = console.input("Company ticker: ") or None
        cik = console.input("Company CIK (optional): ") or None
        accession = None

    expected_behavior = console.input("Expected behavior (optional): ") or None
    actual_behavior = console.input("Actual behavior (optional): ") or None
    error_message = console.input("Error message (optional): ") or None

    # Create the script
    try:
        output_path = create_reproduction_script(
            issue_number=issue_number,
            pattern=pattern,
            reporter=reporter,
            accession=accession,
            ticker=ticker,
            company_name=company_name,
            cik=cik,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            error_message=error_message
        )

        console.print("\n[green]✅ Reproduction script created:[/green]")
        console.print(f"   {output_path}")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("1. Review and customize the script")
        console.print(f"2. Run: python {output_path}")
        console.print("3. Use results to develop fix")

    except Exception as e:
        console.print(f"[red]❌ Failed to create script: {str(e)}[/red]")

def main():
    parser = argparse.ArgumentParser(description="Create issue reproduction scripts")

    # Required arguments
    parser.add_argument("--issue", type=int, required=True,
                       help="GitHub issue number")
    parser.add_argument("--pattern", choices=PATTERN_TEMPLATES.keys(), required=True,
                       help="Investigation pattern")

    # Optional arguments
    parser.add_argument("--reporter", type=str,
                       help="GitHub username of issue reporter")
    parser.add_argument("--accession", type=str,
                       help="Filing accession number")
    parser.add_argument("--ticker", type=str,
                       help="Company ticker symbol")
    parser.add_argument("--company-name", type=str,
                       help="Company name")
    parser.add_argument("--cik", type=str,
                       help="Company CIK")
    parser.add_argument("--expected", type=str,
                       help="Expected behavior")
    parser.add_argument("--actual", type=str,
                       help="Actual behavior")
    parser.add_argument("--error", type=str,
                       help="Error message")
    parser.add_argument("--name", type=str,
                       help="Custom name for output file")

    # Utility options
    parser.add_argument("--interactive", action="store_true",
                       help="Interactive mode")
    parser.add_argument("--list-templates", action="store_true",
                       help="List available templates")

    args = parser.parse_args()

    if args.list_templates:
        console.print("[bold blue]Available Templates[/bold blue]")
        for pattern, template in PATTERN_TEMPLATES.items():
            category = PATTERN_CATEGORIES[pattern]
            console.print(f"  {pattern} -> {category}/{template}")
        return

    if args.interactive:
        interactive_creation()
        return

    # Create reproduction script
    try:
        output_path = create_reproduction_script(
            issue_number=args.issue,
            pattern=args.pattern,
            reporter=args.reporter,
            accession=args.accession,
            ticker=args.ticker,
            company_name=args.company_name,
            cik=args.cik,
            expected_behavior=args.expected,
            actual_behavior=args.actual,
            error_message=args.error,
            custom_name=args.name
        )

        console.print("[green]✅ Reproduction script created:[/green]")
        console.print(f"   📄 {output_path}")

        # Show next steps
        console.print("\n[bold]Next Steps:[/bold]")
        console.print(f"1. Review script: [cyan]{output_path}[/cyan]")
        console.print("2. Customize placeholders if needed")
        console.print(f"3. Run script: [cyan]python {output_path}[/cyan]")
        console.print("4. Use results for issue analysis")

    except Exception as e:
        console.print(f"[red]❌ Failed to create reproduction script: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

if __name__ == "__main__":
    main()
