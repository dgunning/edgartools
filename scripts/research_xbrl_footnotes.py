#!/usr/bin/env python3
"""
Research script to investigate undefined footnote arc references in pre-2016 XBRL filings.

Background:
- Issue #482 reports excessive warnings for undefined footnote references in older filings
- APD 2015 10-K: 20 unique undefined references (lbl_footnote_0 through lbl_footnote_19)
- Modern filings (2023+): No such issues

Research Questions:
1. Are footnote definitions actually missing from the XML?
2. Are they using different ID naming conventions?
3. When did SEC change footnote ID conventions?
4. Are we losing footnote data?

Related: GitHub #482, Beads edgartools-tm2
"""
import xml.etree.ElementTree as ET
from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from edgar import Company

console = Console()


def analyze_filing_footnotes(filing, company_name: str, year: int):
    """Analyze footnote structure in an XBRL filing."""

    console.print(f"\n[bold cyan]Analyzing {company_name} {year} 10-K[/bold cyan]")
    console.print(f"Accession: {filing.accession_no}")
    console.print(f"Filing Date: {filing.filing_date}")

    try:
        # Get XBRL data
        xbrl = filing.xbrl()
        console.print("[green]✓ XBRL parsed successfully[/green]")

        # Get the instance document XML
        # We need to download the actual XBRL instance file
        attachments = filing.attachments

        # Find the instance document (usually the .xml file)
        # Exclude linkbase files (_cal, _def, _lab, _pre)
        instance_file = None
        for att in attachments:
            if att.document_type == 'EX-101.INS':
                instance_file = att
                break

        if not instance_file:
            # Try to find the instance XML (not linkbase files)
            for att in attachments:
                if att.document.endswith('.xml'):
                    # Exclude linkbase files
                    if not any(suffix in att.document for suffix in ['_cal.xml', '_def.xml', '_lab.xml', '_pre.xml']):
                        instance_file = att
                        break

        if not instance_file:
            console.print("[red]✗ Could not find XBRL instance document[/red]")
            return None

        console.print(f"[green]✓ Found instance document: {instance_file.document}[/green]")

        # Download and parse XML
        xml_content = instance_file.download()
        console.print(f"[green]✓ Downloaded: {len(xml_content)} bytes[/green]")

        # Parse XML to examine footnote structure
        root = ET.fromstring(xml_content)

        # Define common XBRL namespaces
        namespaces = {
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'xbrldi': 'http://xbrl.org/2006/xbrldi',
        }

        # Find all footnoteLink elements
        footnote_links = root.findall('.//link:footnoteLink', namespaces)
        console.print(f"\n[bold]Found {len(footnote_links)} footnoteLink elements[/bold]")

        # Analyze footnotes and footnoteArcs
        footnote_ids = set()
        footnote_arc_refs = defaultdict(list)

        footnote_attrs = []  # Track all attributes for analysis

        for i, fn_link in enumerate(footnote_links):
            # Find all footnote elements (definitions)
            footnotes = fn_link.findall('.//link:footnote', namespaces)
            for fn in footnotes:
                # Check multiple ID attributes
                xlink_label = fn.get('{http://www.w3.org/1999/xlink}label')
                id_attr = fn.get('id')

                # Store what we found
                attrs = {
                    'xlink_label': xlink_label,
                    'id': id_attr,
                    'used_id': xlink_label or id_attr  # What the parser would use
                }
                footnote_attrs.append(attrs)

                # Add the ID that would be used by the parser
                if xlink_label:
                    footnote_ids.add(xlink_label)
                elif id_attr:
                    footnote_ids.add(id_attr)

            # Find all footnoteArc elements (references)
            footnote_arcs = fn_link.findall('.//link:footnoteArc', namespaces)
            for arc in footnote_arcs:
                arc_to = arc.get('{http://www.w3.org/1999/xlink}to')
                arc_from = arc.get('{http://www.w3.org/1999/xlink}from')
                if arc_to:
                    footnote_arc_refs[arc_to].append({
                        'from': arc_from,
                        'link_index': i
                    })

        console.print(f"[bold]Footnote Definitions Found:[/bold] {len(footnote_ids)}")
        console.print(f"[bold]Footnote Arc References:[/bold] {len(footnote_arc_refs)}")

        # Find undefined references
        undefined_refs = set(footnote_arc_refs.keys()) - footnote_ids

        if undefined_refs:
            console.print(f"\n[bold yellow]⚠ Found {len(undefined_refs)} undefined footnote references[/bold yellow]")

            # Show sample undefined references
            console.print("\n[dim]Sample undefined references:[/dim]")
            for ref in sorted(list(undefined_refs)[:10]):
                sources = footnote_arc_refs[ref]
                console.print(f"  • [yellow]{ref}[/yellow] (referenced {len(sources)} times)")
                if sources:
                    console.print(f"    From: {sources[0]['from']}")
        else:
            console.print("\n[bold green]✓ All footnote references are defined[/bold green]")

        # Show sample defined footnote IDs and their attributes
        if footnote_ids:
            console.print("\n[dim]Sample defined footnote IDs:[/dim]")
            for fn_id in sorted(list(footnote_ids)[:10]):
                console.print(f"  • [green]{fn_id}[/green]")

        # Show attribute analysis
        if footnote_attrs:
            console.print("\n[bold]Footnote ID Attribute Analysis:[/bold]")
            has_xlink_label = sum(1 for a in footnote_attrs if a['xlink_label'])
            has_id_attr = sum(1 for a in footnote_attrs if a['id'])
            has_both = sum(1 for a in footnote_attrs if a['xlink_label'] and a['id'])

            console.print(f"  • Footnotes with xlink:label: {has_xlink_label}/{len(footnote_attrs)}")
            console.print(f"  • Footnotes with id attribute: {has_id_attr}/{len(footnote_attrs)}")
            console.print(f"  • Footnotes with both: {has_both}/{len(footnote_attrs)}")

            # Show sample
            console.print("\n[dim]Sample footnote attributes:[/dim]")
            for attrs in footnote_attrs[:3]:
                console.print(f"  • xlink:label={attrs['xlink_label']}, id={attrs['id']}")

        return {
            'year': year,
            'company': company_name,
            'accession': filing.accession_no,
            'total_footnote_links': len(footnote_links),
            'defined_footnotes': len(footnote_ids),
            'footnote_arcs': len(footnote_arc_refs),
            'undefined_refs': len(undefined_refs),
            'undefined_ids': sorted(list(undefined_refs)),
            'defined_ids': sorted(list(footnote_ids)),
            'sample_arcs': {k: v for k, v in list(footnote_arc_refs.items())[:5]},
            'footnote_attrs': footnote_attrs
        }

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return None


def compare_filings(old_result, new_result):
    """Compare footnote structures between two filings."""

    console.print("\n" + "="*70)
    console.print("[bold cyan]COMPARISON ANALYSIS[/bold cyan]")
    console.print("="*70)

    table = Table(title="Footnote Structure Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column(f"{old_result['year']}", style="yellow")
    table.add_column(f"{new_result['year']}", style="green")
    table.add_column("Change", justify="right")

    # Compare metrics
    metrics = [
        ('Total Footnote Links', 'total_footnote_links'),
        ('Defined Footnotes', 'defined_footnotes'),
        ('Footnote Arcs', 'footnote_arcs'),
        ('Undefined References', 'undefined_refs'),
    ]

    for label, key in metrics:
        old_val = old_result[key]
        new_val = new_result[key]
        diff = new_val - old_val

        if diff > 0:
            change = f"[green]+{diff}[/green]"
        elif diff < 0:
            change = f"[red]{diff}[/red]"
        else:
            change = "—"

        table.add_row(label, str(old_val), str(new_val), change)

    console.print(table)

    # ID pattern analysis
    console.print("\n[bold]ID Naming Patterns:[/bold]")

    # Analyze old filing
    old_ids = old_result['defined_ids'][:5] if old_result['defined_ids'] else []
    old_undefined = old_result['undefined_ids'][:5] if old_result['undefined_ids'] else []

    console.print(f"\n[yellow]{old_result['year']} Defined IDs:[/yellow]")
    for id_val in old_ids:
        console.print(f"  • {id_val}")

    if old_undefined:
        console.print(f"\n[yellow]{old_result['year']} Undefined IDs:[/yellow]")
        for id_val in old_undefined:
            console.print(f"  • {id_val}")

    # Analyze new filing
    new_ids = new_result['defined_ids'][:5] if new_result['defined_ids'] else []
    new_undefined = new_result['undefined_ids'][:5] if new_result['undefined_ids'] else []

    console.print(f"\n[green]{new_result['year']} Defined IDs:[/green]")
    for id_val in new_ids:
        console.print(f"  • {id_val}")

    if new_undefined:
        console.print(f"\n[green]{new_result['year']} Undefined IDs:[/green]")
        for id_val in new_undefined:
            console.print(f"  • {id_val}")


def main():
    """Run the XBRL footnote investigation."""

    console.print(Panel.fit(
        "[bold cyan]XBRL Footnote Investigation[/bold cyan]\n"
        "Investigating undefined footnote references in pre-2016 filings\n"
        "Comparing APD 2015 vs 2023",
        border_style="cyan"
    ))

    # Get APD (Air Products and Chemicals)
    console.print("\n[bold]Fetching APD filings...[/bold]")
    apd = Company("APD")

    # Get 2015 10-K (the problematic one)
    console.print("\n[bold yellow]Phase 1: Analyze 2015 Filing[/bold yellow]")
    filings_2015 = apd.get_filings(form="10-K", filing_date="2015-01-01:2015-12-31")
    if len(filings_2015) > 0:
        filing_2015 = list(filings_2015)[0]
        result_2015 = analyze_filing_footnotes(filing_2015, "APD", 2015)
    else:
        console.print("[red]✗ Could not find 2015 10-K[/red]")
        result_2015 = None

    # Get 2023 10-K (modern, working one)
    console.print("\n[bold green]Phase 2: Analyze 2023 Filing[/bold green]")
    filings_2023 = apd.get_filings(form="10-K", filing_date="2023-01-01:2023-12-31")
    if len(filings_2023) > 0:
        filing_2023 = list(filings_2023)[0]
        result_2023 = analyze_filing_footnotes(filing_2023, "APD", 2023)
    else:
        console.print("[red]✗ Could not find 2023 10-K[/red]")
        result_2023 = None

    # Compare results
    if result_2015 and result_2023:
        compare_filings(result_2015, result_2023)

        # Final summary
        console.print("\n" + "="*70)
        console.print("[bold cyan]KEY FINDINGS[/bold cyan]")
        console.print("="*70)

        if result_2015['undefined_refs'] > 0 and result_2023['undefined_refs'] == 0:
            console.print(f"\n[bold yellow]✓ Confirmed:[/bold yellow] 2015 filing has {result_2015['undefined_refs']} undefined references")
            console.print("[bold green]✓ Confirmed:[/bold green] 2023 filing has no undefined references")
            console.print("\n[bold]Next Steps:[/bold]")
            console.print("  1. Examine the actual XML structure differences")
            console.print("  2. Research SEC XBRL taxonomy version changes")
            console.print("  3. Determine if data is actually lost or just poorly linked")
        else:
            console.print("\n[bold]Unexpected results - further investigation needed[/bold]")

    return result_2015, result_2023


if __name__ == "__main__":
    old_result, new_result = main()
