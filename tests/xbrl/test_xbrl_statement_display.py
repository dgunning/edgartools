"""
Tests for the enhanced statement display in __rich__ and __str__ methods.
"""
from pathlib import Path
import pytest
from edgar.xbrl.xbrl import XBRL


@pytest.fixture
def nflx_xbrl():
    # Netflix XBRL from 2010 has notes sections
    data_dir = Path("data/xbrl/datafiles/nflx/2010")
    return XBRL.from_directory(data_dir)


def test_rich_display(nflx_xbrl, capsys):
    """Test the rich display of statements with categories."""
    statements = nflx_xbrl.statements
    
    # Get rich representation (this just tests that it runs without errors)
    rich_repr = statements.__rich__()
    assert rich_repr is not None
    
    from rich.console import Console
    console = Console()
    console.print("\nRich representation of Statements:")
    console.print(rich_repr)
    
    # Capture and print the output for visibility in test logs
    captured = capsys.readouterr()
    print(captured.out)


def test_str_representation(nflx_xbrl, capsys):
    """Test the string representation of statements with categories."""
    statements = nflx_xbrl.statements

    # Get string representation
    str_repr = str(statements)
    assert str_repr is not None

    # Print for manual inspection during test runs
    print("\nString representation of Statements:")
    print(str_repr)

    # Verify the rich panel output contains key elements
    assert "Statements" in str_repr
    assert "Statement" in str_repr  # Column header
    assert ".search()" in str_repr  # Subtitle hint

    # Capture and print the output for visibility in test logs
    captured = capsys.readouterr()
    print(captured.out)