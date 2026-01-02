#!/usr/bin/env python3
"""
Build Map Schema - Phase 3 Task 2

Generates production-ready map_core.json and sector overlays from merged virtual trees.

Usage:
    python build_map_schema.py --trees map/virtual_trees_merged.json
    python build_map_schema.py --trees map/virtual_trees_merged.json --output-dir map/
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict


def load_merged_trees(file_path: Path) -> Dict[str, Any]:
    """Load merged virtual trees JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def load_field_specs():
    """Load field specifications from field_specs.py."""
    try:
        from quant.xbrl_standardize.field_specs import (
            INCOME_STATEMENT_FIELDS,
            FIELD_EVALUATION_ORDER,
            get_field_candidates
        )
        return INCOME_STATEMENT_FIELDS, FIELD_EVALUATION_ORDER, get_field_candidates
    except ImportError as e:
        print(f"❌ Failed to import field_specs: {e}")
        print("   Make sure PYTHONPATH includes the project root")
        raise


def normalize_concept_name(concept: str) -> str:
    """
    Normalize concept name by removing namespace prefix.

    Example: "us-gaap:Revenues" -> "Revenues"
    """
    if ':' in concept:
        return concept.split(':', 1)[1]
    return concept


def rank_concepts_for_field(
    field_name: str,
    field_spec: Dict[str, Any],
    merged_trees: Dict[str, Any],
    sector: Optional[str] = None,
    min_occurrence: float = 0.05
) -> List[Tuple[str, float, Dict[str, Any]]]:
    """
    Rank candidate concepts for a field based on occurrence rates.

    Args:
        field_name: Field name (e.g., "revenue")
        field_spec: Field specification from INCOME_STATEMENT_FIELDS
        merged_trees: Merged virtual trees
        sector: Optional sector for sector-specific ranking
        min_occurrence: Minimum occurrence rate to include concept

    Returns:
        List of (concept, score, metadata) tuples, sorted by score descending
    """
    # Get candidate concepts for this field
    candidates = field_spec.get('candidateConcepts', [])

    # Add sector-specific candidates if sector provided
    if sector and 'sectorRules' in field_spec:
        sector_rules = field_spec['sectorRules'].get(sector, {})
        sector_candidates = sector_rules.get('candidateConcepts', [])
        # Prepend sector candidates (higher priority)
        candidates = sector_candidates + [c for c in candidates if c not in sector_candidates]

    if not candidates:
        return []

    # Find concepts in income statement tree
    income_stmt = merged_trees.get('IncomeStatement', {})
    nodes = income_stmt.get('nodes', {})

    ranked = []
    for candidate in candidates:
        # Normalize candidate name (remove namespace if present)
        normalized = normalize_concept_name(candidate)

        # Find in tree
        node = nodes.get(normalized)
        if not node:
            continue

        # Calculate score
        global_occ = node.get('occurrence_rate_global', 0.0)

        if sector:
            # For sector-specific, boost by sector occurrence
            by_industry = node.get('occurrence_rate_by_industry', {})
            sector_occ = by_industry.get(sector, 0.0)
            # Weighted score: 60% sector, 40% global
            score = 0.6 * sector_occ + 0.4 * global_occ
        else:
            # For global, use global occurrence
            score = global_occ

        # Skip if below minimum occurrence
        if score < min_occurrence:
            continue

        # Collect metadata
        metadata = {
            'label': node.get('label', normalized),
            'occurrence_global': global_occ,
            'occurrence_by_industry': node.get('occurrence_rate_by_industry', {}),
            'is_abstract': node.get('is_abstract', False),
            'is_total': node.get('is_total', False),
            'parent': node.get('parent'),
            'children': node.get('children', [])
        }

        # Add full concept name (with namespace)
        full_concept = candidate if ':' in candidate else f'us-gaap:{normalized}'

        ranked.append((full_concept, score, metadata))

    # Sort by score descending
    ranked.sort(key=lambda x: x[1], reverse=True)

    return ranked


def build_core_mappings(
    merged_trees: Dict[str, Any],
    field_specs: Dict[str, Any],
    min_occurrence: float = 0.10,
    max_candidates: int = 3
) -> Dict[str, Any]:
    """
    Build core mapping file (map_core.json).

    Args:
        merged_trees: Merged virtual trees
        field_specs: INCOME_STATEMENT_FIELDS
        min_occurrence: Minimum global occurrence rate
        max_candidates: Maximum fallback candidates per field

    Returns:
        Core mapping dictionary
    """
    core_map = {
        '_meta': {
            'version': '1.0.0',
            'generated_from': 'merged_virtual_trees',
            'min_occurrence_threshold': min_occurrence,
            'description': 'Core XBRL concept mappings for income statement fields'
        },
        'fields': {}
    }

    print("\nBuilding core mappings...")
    print(f"  Minimum occurrence: {min_occurrence}")
    print(f"  Max candidates per field: {max_candidates}")

    mapped_count = 0
    low_confidence_count = 0

    for field_name, field_spec in field_specs.items():
        # Skip computed fields
        if field_spec.get('derivationPriority') == 'compute_only':
            continue

        # Rank concepts for this field
        ranked = rank_concepts_for_field(
            field_name,
            field_spec,
            merged_trees,
            sector=None,  # Core mapping is global
            min_occurrence=min_occurrence
        )

        if not ranked:
            print(f"  ⚠️  {field_name}: No candidates found")
            continue

        # Take top N candidates
        top_candidates = ranked[:max_candidates]

        # Check confidence
        confidence = "high" if top_candidates[0][1] >= 0.30 else \
                    "medium" if top_candidates[0][1] >= 0.15 else "low"

        if confidence == "low":
            low_confidence_count += 1

        core_map['fields'][field_name] = {
            'primary': top_candidates[0][0],
            'confidence': confidence,
            'occurrence_rate': top_candidates[0][1],
            'label': top_candidates[0][2]['label'],
            'fallbacks': [c[0] for c in top_candidates[1:]] if len(top_candidates) > 1 else [],
            'metadata': top_candidates[0][2]
        }

        mapped_count += 1
        print(f"  ✓ {field_name}: {top_candidates[0][0]} ({top_candidates[0][1]:.2%})")

    print(f"\n  Mapped: {mapped_count}/{len(field_specs)} fields")
    print(f"  Low confidence: {low_confidence_count}")

    return core_map


def build_sector_overlay(
    sector_name: str,
    merged_trees: Dict[str, Any],
    field_specs: Dict[str, Any],
    min_occurrence: float = 0.05
) -> Dict[str, Any]:
    """
    Build sector-specific overlay mapping.

    Args:
        sector_name: Sector key (e.g., "banking")
        merged_trees: Merged virtual trees
        field_specs: INCOME_STATEMENT_FIELDS
        min_occurrence: Minimum sector occurrence rate

    Returns:
        Sector overlay dictionary
    """
    overlay = {
        '_meta': {
            'version': '1.0.0',
            'sector': sector_name,
            'generated_from': 'merged_virtual_trees',
            'min_occurrence_threshold': min_occurrence,
            'description': f'Sector-specific XBRL concept mappings for {sector_name}'
        },
        'fields': {}
    }

    print(f"\nBuilding {sector_name} overlay...")
    print(f"  Minimum occurrence: {min_occurrence}")

    mapped_count = 0

    for field_name, field_spec in field_specs.items():
        # Skip computed fields
        if field_spec.get('derivationPriority') == 'compute_only':
            continue

        # Check if field has sector-specific rules
        has_sector_rules = 'sectorRules' in field_spec and sector_name in field_spec['sectorRules']

        # Rank concepts for this field (sector-specific)
        ranked = rank_concepts_for_field(
            field_name,
            field_spec,
            merged_trees,
            sector=sector_name,
            min_occurrence=min_occurrence
        )

        if not ranked:
            continue

        # Only include in overlay if:
        # 1. Field has explicit sector rules, OR
        # 2. Top concept differs from core mapping significantly
        include_in_overlay = has_sector_rules or ranked[0][1] >= 0.20

        if not include_in_overlay:
            continue

        overlay['fields'][field_name] = {
            'primary': ranked[0][0],
            'confidence': "high" if ranked[0][1] >= 0.30 else "medium" if ranked[0][1] >= 0.15 else "low",
            'occurrence_rate_sector': ranked[0][1],
            'occurrence_rate_global': ranked[0][2]['occurrence_global'],
            'label': ranked[0][2]['label'],
            'sector_specific': has_sector_rules
        }

        mapped_count += 1
        print(f"  ✓ {field_name}: {ranked[0][0]} ({ranked[0][1]:.2%} sector, {ranked[0][2]['occurrence_global']:.2%} global)")

    print(f"  Mapped: {mapped_count} sector-specific fields")

    return overlay


def save_mapping(mapping: Dict[str, Any], output_path: Path):
    """Save mapping to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(mapping, f, indent=2)

    print(f"  ✅ Saved: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description='Build standardized map schema from merged virtual trees',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build all mappings (core + overlays)
  python build_map_schema.py --trees map/virtual_trees_merged.json

  # Custom output directory
  python build_map_schema.py \\
    --trees map/virtual_trees_merged.json \\
    --output-dir map/

  # Adjust occurrence thresholds
  python build_map_schema.py \\
    --trees map/virtual_trees_merged.json \\
    --min-core-occurrence 0.15 \\
    --min-sector-occurrence 0.10
        """
    )

    parser.add_argument(
        '--trees',
        type=Path,
        required=True,
        help='Path to merged virtual trees JSON file'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('quant/xbrl_standardize/map'),
        help='Output directory for mapping files (default: quant/xbrl_standardize/map/)'
    )

    parser.add_argument(
        '--min-core-occurrence',
        type=float,
        default=0.10,
        help='Minimum global occurrence rate for core mappings (default: 0.10)'
    )

    parser.add_argument(
        '--min-sector-occurrence',
        type=float,
        default=0.05,
        help='Minimum sector occurrence rate for overlays (default: 0.05)'
    )

    parser.add_argument(
        '--sectors',
        nargs='+',
        default=['banking', 'insurance', 'utilities'],
        help='Sectors to generate overlays for (default: banking insurance utilities)'
    )

    args = parser.parse_args()

    # Validate input
    if not args.trees.exists():
        print(f"❌ Merged virtual trees not found: {args.trees}")
        return 1

    print("="*70)
    print("BUILDING MAP SCHEMA")
    print("="*70)

    # Load merged trees
    print(f"\n📥 Loading merged virtual trees from: {args.trees}")
    merged_trees = load_merged_trees(args.trees)

    # Load field specifications
    print("📥 Loading field specifications...")
    try:
        field_specs, eval_order, get_candidates = load_field_specs()
        print(f"   Loaded {len(field_specs)} field specifications")
    except Exception as e:
        print(f"❌ Failed to load field specifications: {e}")
        return 1

    # Build core mappings
    core_map = build_core_mappings(
        merged_trees,
        field_specs,
        min_occurrence=args.min_core_occurrence
    )

    # Save core mapping
    core_output = args.output_dir / 'map_core.json'
    save_mapping(core_map, core_output)

    # Build sector overlays
    overlays_dir = args.output_dir / 'map_overlays'
    overlays_dir.mkdir(parents=True, exist_ok=True)

    for sector in args.sectors:
        overlay = build_sector_overlay(
            sector,
            merged_trees,
            field_specs,
            min_occurrence=args.min_sector_occurrence
        )

        if overlay['fields']:  # Only save if has mappings
            overlay_output = overlays_dir / f'{sector}.json'
            save_mapping(overlay, overlay_output)
        else:
            print(f"  ⚠️  No mappings for {sector}, skipping overlay")

    print("\n" + "="*70)
    print("✅ MAP SCHEMA BUILD COMPLETE")
    print("="*70)
    print(f"\nGenerated files:")
    print(f"  - Core: {core_output}")
    print(f"  - Overlays: {overlays_dir}/*.json")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
