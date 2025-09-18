"""
XBRL Statement Stitching Package

This package provides functionality to combine multiple XBRL statements 
across different time periods into a unified view, handling concept 
consistency issues and normalizing data representation.
"""

# Import standardize_statement for backwards compatibility with tests
from edgar.xbrl.standardization import standardize_statement
from edgar.xbrl.stitching.core import StatementStitcher, stitch_statements
from edgar.xbrl.stitching.periods import determine_optimal_periods
from edgar.xbrl.stitching.query import StitchedFactQuery, StitchedFactsView
from edgar.xbrl.stitching.utils import render_stitched_statement, to_pandas
from edgar.xbrl.stitching.xbrls import XBRLS

__all__ = [
    'XBRLS',
    'StatementStitcher', 
    'stitch_statements',
    'determine_optimal_periods',
    'render_stitched_statement',
    'to_pandas',
    'standardize_statement',
    'StitchedFactsView',
    'StitchedFactQuery'
]
