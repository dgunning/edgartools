#!/usr/bin/env python
"""
Test script to display fund information with rich formatting.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from edgar.funds.core import Fund
from rich.console import Console

console = Console()

if __name__ == "__main__":
    # Get CIK from command line or use default
    cik = sys.argv[1] if len(sys.argv) > 1 else "1083387"
    
    # Create and display fund with rich formatting
    fund = Fund(cik)
    console.print(fund)