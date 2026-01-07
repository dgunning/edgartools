#!/usr/bin/env python3
"""
01_extract_meta_trees.py - Demo: Extract Calculation Trees from META's 10-K

This script demonstrates how to extract and visualize calculation trees
from a company's SEC filing using EdgarTools.

Key concepts:
- CalculationTree: A tree structure for one financial statement/schedule
- CalculationNode: A node with parent, children, and weight
- Weight: +1.0 means add, -1.0 means subtract

Usage:
    python 01_extract_meta_trees.py
"""

from edgar import Company, set_identity
from typing import Dict, List
import json

set_identity("Dev Gunning developer-gunning@gmail.com")


def print_tree(tree, indent=0, max_depth=4):
    """Recursively print a calculation tree."""
    if indent >= max_depth:
        return
    
    # Find root nodes (nodes with no parent)
    root_id = tree.root_element_id
    root_node = tree.all_nodes.get(root_id)
    
    if root_node:
        _print_node(tree, root_id, root_node, indent, max_depth)


def _print_node(tree, node_id, node, indent, max_depth):
    """Print a single node and its children."""
    if indent >= max_depth:
        if node.children:
            print("  " * indent + "  ...")
        return
    
    # Format the concept name (remove namespace prefix)
    name = node_id.replace('us-gaap_', '').replace('meta_', '[custom] ')
    weight_str = f" (×{node.weight:+.1f})" if node.weight != 1.0 else ""
    
    print("  " * indent + f"├── {name}{weight_str}")
    
    # Print children
    for child_id in node.children:
        child_node = tree.all_nodes.get(child_id)
        if child_node:
            _print_node(tree, child_id, child_node, indent + 1, max_depth)


def summarize_trees(calculation_trees: Dict) -> Dict:
    """Create a summary of all calculation trees."""
    summary = {
        'total_trees': len(calculation_trees),
        'trees': []
    }
    
    for role, tree in calculation_trees.items():
        name = role.split('/')[-1] if '/' in role else role
        summary['trees'].append({
            'name': name,
            'root': tree.root_element_id.replace('us-gaap_', '').replace('meta_', '[custom] '),
            'node_count': len(tree.all_nodes),
            'definition': tree.definition
        })
    
    return summary


def main():
    print("=" * 70)
    print("CALCULATION TREE EXTRACTION DEMO - META 10-K")
    print("=" * 70)
    
    # Get META's latest 10-K
    c = Company('META')
    filings = c.get_filings(form='10-K')
    f = filings[0]
    
    print(f"\nFiling: {f.accession_no}")
    print(f"Date: {f.filing_date}")
    
    # Parse XBRL
    xbrl = f.xbrl()
    
    # Get summary
    summary = summarize_trees(xbrl.calculation_trees)
    print(f"\nTotal calculation trees: {summary['total_trees']}")
    
    # Print summary table
    print("\n" + "-" * 70)
    print(f"{'Tree Name':<55} {'Root':<25} {'Nodes':>5}")
    print("-" * 70)
    
    for t in summary['trees']:
        name = t['name'][:54]
        root = t['root'][:24]
        print(f"{name:<55} {root:<25} {t['node_count']:>5}")
    
    # Print detailed trees for the 3 main financial statements
    main_statements = [
        'CONSOLIDATEDSTATEMENTSOFINCOME',
        'CONSOLIDATEDBALANCESHEETS', 
        'CONSOLIDATEDSTATEMENTSOFCASHFLOWS'
    ]
    
    for role, tree in xbrl.calculation_trees.items():
        name = role.split('/')[-1]
        if name in main_statements:
            print("\n" + "=" * 70)
            print(f"TREE: {tree.definition}")
            print(f"Root: {tree.root_element_id}")
            print("=" * 70)
            print_tree(tree, max_depth=5)
    
    # Save summary to JSON
    output_file = "meta_trees_summary.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n\nSummary saved to {output_file}")


if __name__ == "__main__":
    main()
