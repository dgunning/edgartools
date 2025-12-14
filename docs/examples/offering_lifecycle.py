# /// script
# dependencies = [
#   "edgartools>=4.25.0",
# ]
# ///
"""
CAMPAIGN LIFECYCLE TRACKING WORKFLOW
====================================

This script demonstrates the complete campaign lifecycle tracking workflow
for Regulation CF crowdfunding using EdgarTools' streamlined API.

Research Goal: Track a crowdfunding campaign from inception through completion
or termination, answering:
- How do we navigate between related filings for the same campaign?
- What data is available at each stage of the lifecycle?
- What status information can we derive (active, funded, terminated)?
- Can we access all lifecycle stages: C → C/A → C-U → C-AR → C-TR?

Streamlined API Features Used:
- Company.get_filings() - Discovery
- filing.obj() → FormC - Parsing
- formc.issuer_name, .portal_name - Convenient property access
- formc.issuer → IssuerCompany - Cached issuer entity
- formc.get_offering() → Offering - Aggregation
- offering.initial_offering, .amendments, .updates, etc. - Lifecycle access
- offering.status - Status derivation
"""

from rich import print
from rich.console import Console
from rich.table import Table

from edgar import *
from edgar.offerings import *

console = Console()

# ============================================================================
# STEP 1: DISCOVER - Find all crowdfunding filings for a company
# ============================================================================
console.print("\n[bold cyan]═══ CAMPAIGN LIFECYCLE TRACKING ═══[/bold cyan]\n")

forms = ['C', 'C/A', 'C-U', 'C-AR', 'C-TR']
viit = Company(1881570)  # ViiT Health Inc
filings = viit.get_filings(form=forms)
print(filings.to_context())
console.print(f"✓ [green]Found {len(filings)} crowdfunding filings for {viit.name}[/green]\n")

# ============================================================================
# STEP 2: ISOLATE - Parse a specific filing
# ============================================================================
filing = filings.latest()
formc: FormC = filing.obj()
console.print(f"[yellow]Analyzing filing:[/yellow] {filing.form} on {filing.filing_date}")
console.print(f"  Issuer: {formc.issuer.name}")
console.print(f"  Portal: {formc.portal_name}\n")

# ============================================================================
# STEP 3: AGGREGATE - Get complete offering lifecycle
# ============================================================================
offering: Offering = formc.get_offering()
console.print("[blue]Offering Details:[/blue]")
console.print(f"  File Number: {offering.file_number}")
console.print(f"  Status: {offering.status}")
console.print(f"  Total Filings: {len(offering.all_filings)}\n")

# ============================================================================
# STEP 4: NAVIGATE - Access each lifecycle stage
# ============================================================================
lifecycle_table = Table(title="Campaign Lifecycle Stages")
lifecycle_table.add_column("Stage", style="cyan")
lifecycle_table.add_column("Form Type", style="yellow")
lifecycle_table.add_column("Count", style="green")
lifecycle_table.add_column("Latest Date", style="magenta")

stages = [
    ("Initial Offering", "C"),
    ("Amendments", "C/A"),
    ("Progress Updates", "C-U"),
    ("Annual Reports", "C-AR"),
    ("Termination", "C-TR"),
]

for stage_name, form_type in stages:
    stage_filings = offering.all_filings.filter(form=form_type)
    if stage_filings and len(stage_filings) > 0:
        latest = stage_filings.latest()
        lifecycle_table.add_row(
            stage_name,
            form_type,
            str(len(stage_filings)),
            str(latest.filing_date)
        )
    else:
        lifecycle_table.add_row(stage_name, form_type, "0", "—")

console.print(lifecycle_table)

# ============================================================================
# STEP 5: MULTI-CAMPAIGN - Analyze all offerings from this issuer
# ============================================================================
issuer: IssuerCompany = formc.issuer
all_offerings = issuer.get_offerings()

console.print(f"\n[yellow]Issuer Portfolio:[/yellow] {issuer.name}")
console.print(f"  Total Campaigns: {len(all_offerings)}\n")

if len(all_offerings) > 1:
    portfolio_table = Table(title=f"All Campaigns by {issuer.name}")
    portfolio_table.add_column("Campaign", style="cyan")
    portfolio_table.add_column("File Number", style="yellow")
    portfolio_table.add_column("Status", style="green")
    portfolio_table.add_column("Filings", style="magenta")
    portfolio_table.add_column("First Filed", style="blue")

    for idx, campaign in enumerate(all_offerings, 1):
        first_filing = campaign.all_filings[0] if len(campaign.all_filings) > 0 else None
        portfolio_table.add_row(
            str(idx),
            campaign.file_number,
            campaign.status,
            str(len(campaign.all_filings)),
            str(first_filing.filing_date) if first_filing else "—"
        )

    console.print(portfolio_table)

# ============================================================================
# SUMMARY
# ============================================================================
console.print("\n[bold green]✓ Campaign Lifecycle Tracking Complete[/bold green]")
console.print("\n[dim]Key API Features Demonstrated:[/dim]")
console.print("  • [cyan]Company.get_filings()[/cyan] - Discover all crowdfunding filings")
console.print("  • [cyan]filing.obj()[/cyan] - Parse structured FormC data")
console.print("  • [cyan]formc.issuer_name, .portal_name[/cyan] - Convenient property access")
console.print("  • [cyan]formc.issuer[/cyan] - Cached issuer entity (IssuerCompany)")
console.print("  • [cyan]formc.get_offering()[/cyan] - Aggregate related filings by file number")
console.print("  • [cyan]offering.initial_offering, .amendments, .updates, .annual_reports[/cyan] - Lifecycle access")
console.print("  • [cyan]offering.status[/cyan] - Derive campaign status")
console.print("  • [cyan]issuer.get_offerings()[/cyan] - Multi-campaign portfolio analysis\n")
