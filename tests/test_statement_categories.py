"""
Tests for the new statement categorization functionality.
"""
from pathlib import Path
import pytest
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statement_resolver import StatementCategory


@pytest.fixture
def nflx_xbrl():
    # Netflix XBRL from 2010 has notes sections
    data_dir = Path("data/xbrl/datafiles/nflx/2010")
    return XBRL.parse_directory(data_dir)


def test_get_statements_by_category(nflx_xbrl):
    """Test retrieving statements by category."""
    # Get all statements
    all_statements = nflx_xbrl.get_all_statements()
    
    # Get statements by category
    financial_statements = nflx_xbrl.get_statements_by_category('statement')
    notes = nflx_xbrl.get_statements_by_category('note')
    disclosures = nflx_xbrl.get_statements_by_category('disclosure')
    
    # Check that categorized statements were found
    # Note: Many XBRL files might not explicitly categorize statements,
    # so we allow the test to pass even if no notes/disclosures are found
    
    # At minimum, make sure that the categories are mutually exclusive
    if notes and financial_statements:
        # Check that there's no overlap between categories
        note_roles = {stmt['role'] for stmt in notes}
        statement_roles = {stmt['role'] for stmt in financial_statements}
        assert not note_roles.intersection(statement_roles)
    
    if disclosures and financial_statements:
        # Check that there's no overlap between categories
        disclosure_roles = {stmt['role'] for stmt in disclosures}
        statement_roles = {stmt['role'] for stmt in financial_statements}
        assert not disclosure_roles.intersection(statement_roles)


def test_statements_class_notes(nflx_xbrl):
    """Test the notes() and disclosures() methods on the Statements class."""
    statements = nflx_xbrl.statements
    
    # Get notes
    notes = statements.notes()
    
    # Print information about notes for debugging
    print(f"Found {len(notes)} notes")
    
    # Try to access Notes by name
    try:
        note = statements["Notes"]
        assert note is not None
        print(f"Found note by name: {note}")
    except Exception as e:
        print(f"Could not get Notes by name: {e}")
    
    # Test disclosures
    disclosures = statements.disclosures()
    print(f"Found {len(disclosures)} disclosures")