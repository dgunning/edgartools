from rich.table import Table
from edgar.richtools import rich_to_svg
from rich.panel import Panel
from rich.tree import Tree


def test_rich_to_svg_table():
    """Test SVG export of a Rich Table"""
    # Create a test table
    table = Table(title="Test Table")
    table.add_column("Name", style="cyan")
    table.add_column("Age", justify="right", style="green")
    table.add_row("Alice", "25")
    table.add_row("Bob", "30")

    svg_output = rich_to_svg(table)

    # Basic validation of SVG output
    assert '<svg class="rich-terminal"' in svg_output
    assert svg_output.rstrip().endswith('</svg>')
    assert "Test&#160;Table" in svg_output  # Check for non-breaking space
    assert "Alice" in svg_output
    assert "Bob" in svg_output


def test_rich_to_svg_panel():
    """Test SVG export of a Rich Panel"""
    panel = Panel("Hello, World!", title="Test Panel")
    svg_output = rich_to_svg(panel)

    assert '<svg class="rich-terminal"' in svg_output
    assert svg_output.rstrip().endswith('</svg>')
    assert "Hello,&#160;World!" in svg_output
    assert "Test&#160;Panel" in svg_output


def test_rich_to_svg_tree():
    """Test SVG export of a Rich Tree"""
    tree = Tree("Root")
    tree.add("Child 1")
    tree.add("Child 2").add("Grandchild")

    svg_output = rich_to_svg(tree)

    assert '<svg class="rich-terminal"' in svg_output
    assert svg_output.rstrip().endswith('</svg>')
    assert "Root" in svg_output
    # Tree nodes might have special spacing
    assert "Child" in svg_output


def test_rich_to_svg_width():
    """Test width parameter of SVG export"""
    test_width = 80
    panel = Panel("Test content")
    svg_output = rich_to_svg(panel, width=test_width)

    # SVG should contain viewBox attribute with specified width
    assert 'viewBox' in svg_output


def test_rich_to_svg_html_entities():
    """Test that spaces and special characters are properly encoded"""
    table = Table(title="Test & Demo")
    table.add_column("Full Name")
    table.add_row("John Doe")

    svg_output = rich_to_svg(table)

    # Test for HTML entity encoding
    assert "Test&#160;&amp;&#160;Demo" in svg_output
    assert "John&#160;Doe" in svg_output


def test_rich_to_svg_empty_input():
    """Test SVG export with empty content"""
    panel = Panel("")
    svg_output = rich_to_svg(panel)

    assert '<svg class="rich-terminal"' in svg_output
    assert svg_output.rstrip().endswith('</svg>')


