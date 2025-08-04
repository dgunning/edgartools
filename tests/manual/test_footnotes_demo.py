#!/usr/bin/env python3
"""
Demo script showing how to use the new XBRL footnote parsing functionality.
This addresses the feature request in edgar/xbrl/FootnotesParsing.md
"""

from pathlib import Path
from edgar.xbrl.parser import XBRLParser
from edgar.xbrl import XBRL
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def demo_footnote_parsing():
    """Demonstrate footnote parsing with a sample XBRL file."""
    
    # Use a test file that has facts with ID attributes
    test_file = Path("tests/fixtures/xbrl2/unp/unp-20121231.xml")
    
    if not test_file.exists():
        console.print(f"[red]Test file not found: {test_file}[/red]")
        return
    
    console.print("\n[bold cyan]XBRL Footnote Parsing Demo[/bold cyan]\n")
    console.print(f"Parsing file: {test_file.name}")
    
    # Parse using XBRLParser directly
    parser = XBRLParser()
    instance_content = test_file.read_text()
    parser.parse_instance_content(instance_content)
    
    # Display facts with IDs
    facts_with_ids = [fact for fact in parser.facts.values() if hasattr(fact, 'fact_id') and fact.fact_id]
    console.print(f"\n✓ Found [bold green]{len(facts_with_ids)}[/bold green] facts with ID attributes")
    
    if facts_with_ids:
        # Show sample facts with IDs
        table = Table(title="Sample Facts with IDs", show_header=True)
        table.add_column("Fact ID", style="cyan")
        table.add_column("Element", style="yellow")
        table.add_column("Value", style="white")
        table.add_column("Context", style="dim")
        
        for fact in facts_with_ids[:5]:  # Show first 5
            table.add_row(
                getattr(fact, 'fact_id', 'N/A') or "N/A",
                fact.element_id,
                fact.value[:50] if len(fact.value) > 50 else fact.value,
                fact.context_ref
            )
        
        console.print(table)
    
    # Display footnotes if any exist
    if hasattr(parser, 'footnotes') and parser.footnotes:
        console.print(f"\n✓ Found [bold green]{len(parser.footnotes)}[/bold green] footnotes")
        
        # Show footnote details
        footnote_table = Table(title="Footnotes", show_header=True)
        footnote_table.add_column("Footnote ID", style="cyan")
        footnote_table.add_column("Text (first 100 chars)", style="white", width=50)
        footnote_table.add_column("Related Facts", style="yellow")
        
        for footnote_id, footnote in list(parser.footnotes.items())[:3]:  # Show first 3
            text_preview = footnote.text[:100] + "..." if len(footnote.text) > 100 else footnote.text
            related_facts = ", ".join(footnote.related_fact_ids[:3])
            if len(footnote.related_fact_ids) > 3:
                related_facts += f" (+{len(footnote.related_fact_ids)-3} more)"
            
            footnote_table.add_row(
                footnote_id,
                text_preview,
                related_facts or "None"
            )
        
        console.print(footnote_table)
        
        # Show fact-footnote relationships
        facts_with_footnotes = [f for f in parser.facts.values() if hasattr(f, 'footnotes') and f.footnotes]
        if facts_with_footnotes:
            console.print(f"\n✓ [bold green]{len(facts_with_footnotes)}[/bold green] facts have footnotes")
    else:
        console.print("\n[yellow]No footnotes found in this document[/yellow]")
        console.print("[dim]Note: Not all XBRL documents contain footnotes[/dim]")
    
    # Demonstrate using XBRL class methods
    console.print("\n[bold cyan]Using XBRL Class Methods[/bold cyan]")
    
    xbrl = XBRL()
    xbrl.parser.parse_instance_content(instance_content)
    
    # Get facts with footnotes
    facts_with_footnotes = xbrl.get_facts_with_footnotes()
    if facts_with_footnotes:
        console.print(f"✓ get_facts_with_footnotes() returned {len(facts_with_footnotes)} facts")
        
        # Get footnotes for a specific fact
        sample_fact_id = next((getattr(f, 'fact_id', None) for f in xbrl.parser.facts.values() 
                               if hasattr(f, 'fact_id') and getattr(f, 'fact_id', None) and hasattr(f, 'footnotes') and f.footnotes), None)
        if sample_fact_id:
            footnotes = xbrl.get_footnotes_for_fact(sample_fact_id)
            console.print(f"✓ get_footnotes_for_fact('{sample_fact_id}') returned {len(footnotes)} footnotes")
    
    # Show string representation
    console.print(f"\n[dim]String representation:[/dim] {str(xbrl)}")


def demo_footnote_structure():
    """Show the structure of footnotes in XBRL."""
    
    console.print("\n[bold cyan]XBRL Footnote Structure[/bold cyan]\n")
    
    sample_xml = """
    <link:footnote id="fn-3" xlink:label="fn-3" xlink:role="http://www.xbrl.org/2003/role/footnote" xml:lang="en-US">
       <xhtml:div>
        <xhtml:span>Sample footnote text explaining the fact.</xhtml:span>
       </xhtml:div>
    </link:footnote>
    
    <link:footnoteArc xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote" 
                      xlink:from="fact-id-123" 
                      xlink:to="fn-3"/>
    """
    
    console.print("[bold]Sample XBRL Footnote XML:[/bold]")
    console.print(sample_xml, style="dim")
    
    console.print("\n[bold]How it works:[/bold]")
    console.print("1. Facts have an 'id' attribute (e.g., id=\"fact-id-123\")")
    console.print("2. Footnotes are defined with text content and an id")
    console.print("3. FootnoteArc elements link facts to footnotes via xlink:from and xlink:to")
    console.print("4. The parser preserves these relationships in the Fact and Footnote objects")


if __name__ == "__main__":
    demo_footnote_parsing()
    demo_footnote_structure()
    
    console.print("\n[bold green]✓ Footnote parsing feature successfully implemented![/bold green]")
    console.print("\n[dim]For more details, see the implementation in:[/dim]")
    console.print("  - edgar/xbrl/models.py (Fact and Footnote models)")
    console.print("  - edgar/xbrl/parser.py (_extract_footnotes method)")
    console.print("  - edgar/xbrl/xbrl.py (footnotes property and helper methods)")