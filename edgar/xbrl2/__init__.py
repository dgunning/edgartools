"""
XBRL2 Module - Enhanced XBRL Processing for EdgarTools

This module provides enhanced parsing and processing of XBRL data,
with support for statement standardization and multi-period statement stitching.
"""

from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statements import Statements
from edgar.xbrl2.standardization import StandardConcept

# Export statement stitching functionality
from edgar.xbrl2.stitching import (
    StatementStitcher, 
    stitch_statements, 
    render_stitched_statement, 
    to_pandas
)

__all__ = [
    'XBRL', 
    'Statements',
    'StandardConcept',
    'StatementStitcher',
    'stitch_statements',
    'render_stitched_statement',
    'to_pandas'
]