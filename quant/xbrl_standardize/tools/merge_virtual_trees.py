#!/usr/bin/env python3
"""
Merge Virtual Trees - Phase 3 Task 1

Merges global and sector-specific virtual trees into a unified dataset with
per-industry occurrence rates.

Usage:
    python merge_virtual_trees.py --global PATH --sectors banking insurance utilities
    python merge_virtual_trees.py --input-dir training/output --output map/virtual_trees_merged.json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def load_virtual_trees(file_path: Path) -> Dict[str, Any]:
    """Load a virtual trees JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def merge_concept_nodes(
    global_node: Dict[str, Any],
    sector_nodes: Dict[str, Dict[str, Any]],
    concept: str
) -> Dict[str, Any]:
    """
    Merge a concept node from global and sector-specific trees.

    Args:
        global_node: Node from global virtual tree
        sector_nodes: Dict of {sector_name: node} from sector trees
        concept: Concept name being merged

    Returns:
        Merged node with occurrence_rate_by_industry
    """
    # Start with global node as base
    merged = global_node.copy()

    # Add global occurrence rate
    merged['occurrence_rate_global'] = global_node.get('occurrence_rate', 0.0)

    # Add per-industry occurrence rates
    merged['occurrence_rate_by_industry'] = {}
    for sector_name, sector_node in sector_nodes.items():
        if sector_node:
            merged['occurrence_rate_by_industry'][sector_name] = sector_node.get('occurrence_rate', 0.0)

    # Remove old occurrence_rate key (now split into global + by_industry)
    if 'occurrence_rate' in merged:
        del merged['occurrence_rate']

    return merged


def merge_statement_trees(
    global_stmt: Dict[str, Any],
    sector_stmts: Dict[str, Dict[str, Any]],
    statement_type: str
) -> Dict[str, Any]:
    """
    Merge trees for a single statement type across all sectors.

    Args:
        global_stmt: Global statement tree
        sector_stmts: Dict of {sector_name: statement_tree}
        statement_type: Statement type (e.g., "BalanceSheet")

    Returns:
        Merged statement tree
    """
    merged_stmt = {
        'statement_type': statement_type,
        'nodes': {}
    }

    # Get all concepts from global tree
    global_nodes = global_stmt.get('nodes', {})

    # Collect all unique concepts across all trees
    all_concepts = set(global_nodes.keys())
    for sector_stmt in sector_stmts.values():
        if sector_stmt:
            all_concepts.update(sector_stmt.get('nodes', {}).keys())

    # Merge each concept
    for concept in all_concepts:
        global_node = global_nodes.get(concept)
        sector_nodes = {}

        for sector_name, sector_stmt in sector_stmts.items():
            if sector_stmt:
                sector_nodes[sector_name] = sector_stmt.get('nodes', {}).get(concept)

        if global_node:
            # Merge with global as base
            merged_stmt['nodes'][concept] = merge_concept_nodes(global_node, sector_nodes, concept)
        elif sector_nodes:
            # Concept only exists in sector trees, use first available as base
            base_node = next(node for node in sector_nodes.values() if node is not None)
            merged_stmt['nodes'][concept] = merge_concept_nodes(base_node, sector_nodes, concept)
            # Mark that this is sector-specific
            merged_stmt['nodes'][concept]['occurrence_rate_global'] = 0.0

    return merged_stmt


def merge_virtual_trees(
    global_path: Path,
    sector_paths: Dict[str, Path]
) -> Dict[str, Any]:
    """
    Merge global and sector virtual trees.

    Args:
        global_path: Path to global virtual trees JSON
        sector_paths: Dict of {sector_name: path} for sector trees

    Returns:
        Merged virtual trees with global + per-industry occurrence rates
    """
    print(f"Loading global virtual trees from: {global_path}")
    global_trees = load_virtual_trees(global_path)

    # Load all sector trees
    sector_trees = {}
    for sector_name, sector_path in sector_paths.items():
        print(f"Loading {sector_name} virtual trees from: {sector_path}")
        sector_trees[sector_name] = load_virtual_trees(sector_path)

    # Get all statement types
    all_statement_types = set(global_trees.keys())
    for sector_tree in sector_trees.values():
        all_statement_types.update(sector_tree.keys())

    print(f"\nMerging {len(all_statement_types)} statement types:")
    print(f"  {', '.join(sorted(all_statement_types))}")

    # Merge each statement type
    merged_trees = {}
    for stmt_type in all_statement_types:
        print(f"\n  Merging {stmt_type}...")

        global_stmt = global_trees.get(stmt_type, {})
        sector_stmts = {
            sector_name: sector_tree.get(stmt_type)
            for sector_name, sector_tree in sector_trees.items()
        }

        merged_trees[stmt_type] = merge_statement_trees(global_stmt, sector_stmts, stmt_type)

        # Report statistics
        total_concepts = len(merged_trees[stmt_type]['nodes'])
        global_only = sum(1 for node in merged_trees[stmt_type]['nodes'].values()
                         if node['occurrence_rate_global'] > 0 and
                         all(v == 0 for v in node['occurrence_rate_by_industry'].values()))
        sector_only = sum(1 for node in merged_trees[stmt_type]['nodes'].values()
                         if node['occurrence_rate_global'] == 0)

        print(f"    Total concepts: {total_concepts}")
        print(f"    Global-only: {global_only}")
        print(f"    Sector-specific: {sector_only}")
        print(f"    Shared: {total_concepts - global_only - sector_only}")

    return merged_trees


def save_merged_trees(merged_trees: Dict[str, Any], output_path: Path):
    """Save merged virtual trees to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(merged_trees, f, indent=2)

    print(f"\n✅ Merged virtual trees saved to: {output_path}")
    print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description='Merge global and sector-specific virtual trees',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge global + 3 sectors
  python merge_virtual_trees.py \\
    --global training/output/virtual_trees_global.json \\
    --sectors banking insurance utilities

  # Use input directory (auto-discovers files)
  python merge_virtual_trees.py \\
    --input-dir training/output \\
    --output map/virtual_trees_merged.json
        """
    )

    parser.add_argument(
        '--global',
        dest='global_path',
        help='Path to global virtual trees JSON file'
    )

    parser.add_argument(
        '--sectors',
        nargs='+',
        help='Sector names to merge (e.g., banking insurance utilities)'
    )

    parser.add_argument(
        '--input-dir',
        type=Path,
        help='Directory containing virtual_trees_*.json files (auto-discovers)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('quant/xbrl_standardize/map/virtual_trees_merged.json'),
        help='Output path for merged trees (default: quant/xbrl_standardize/map/virtual_trees_merged.json)'
    )

    args = parser.parse_args()

    # Auto-discovery mode
    if args.input_dir:
        input_dir = args.input_dir
        if not input_dir.exists():
            print(f"❌ Input directory not found: {input_dir}")
            return 1

        # Find global tree
        global_path = input_dir / 'virtual_trees_global.json'
        if not global_path.exists():
            print(f"❌ Global virtual trees not found: {global_path}")
            return 1

        # Auto-discover sector trees
        sector_paths = {}
        for json_file in input_dir.glob('virtual_trees_*.json'):
            if json_file.name == 'virtual_trees_global.json':
                continue
            if json_file.name == 'virtual_trees_test.json':
                continue  # Skip test run
            if json_file.name == 'virtual_trees.json':
                continue  # Skip untagged run

            # Extract sector name from filename
            sector_name = json_file.stem.replace('virtual_trees_', '')
            sector_paths[sector_name] = json_file

        print(f"📁 Auto-discovered sectors: {', '.join(sorted(sector_paths.keys()))}")

    # Manual mode
    elif args.global_path and args.sectors:
        global_path = Path(args.global_path)
        if not global_path.exists():
            print(f"❌ Global virtual trees not found: {global_path}")
            return 1

        base_dir = global_path.parent
        sector_paths = {}
        for sector in args.sectors:
            sector_path = base_dir / f'virtual_trees_{sector}.json'
            if not sector_path.exists():
                print(f"⚠️  Warning: Sector tree not found: {sector_path}")
                continue
            sector_paths[sector] = sector_path

    else:
        print("❌ Must provide either --input-dir or (--global + --sectors)")
        parser.print_help()
        return 1

    # Validate we have at least one sector
    if not sector_paths:
        print("❌ No sector virtual trees found")
        return 1

    # Perform merge
    print("\n" + "="*70)
    print("MERGING VIRTUAL TREES")
    print("="*70)

    merged_trees = merge_virtual_trees(global_path, sector_paths)

    # Save output
    save_merged_trees(merged_trees, args.output)

    print("\n" + "="*70)
    print("✅ MERGE COMPLETE")
    print("="*70)

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
