#!/usr/bin/env python3
"""
Analyze Mappings - Phase 3 Task 3

Analyzes mapping quality and coverage before production deployment.

Usage:
    python analyze_mappings.py --core map/map_core.json
    python analyze_mappings.py --core map/map_core.json --overlays map/map_overlays/*.json
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_mapping(file_path: Path) -> Dict[str, Any]:
    """Load a mapping JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def analyze_coverage(mapping: Dict[str, Any], field_specs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze mapping coverage.

    Returns:
        Dictionary with coverage metrics
    """
    mapped_fields = set(mapping.get('fields', {}).keys())
    all_fields = set(field_specs.keys())

    # Exclude computed-only fields from coverage requirements
    required_fields = set(f for f, spec in field_specs.items()
                         if spec.get('derivationPriority') != 'compute_only')

    mapped_required = mapped_fields & required_fields
    missing_required = required_fields - mapped_fields

    # Count fields with fallbacks
    fields_with_fallbacks = sum(1 for field_data in mapping['fields'].values()
                               if field_data.get('fallbacks'))

    return {
        'total_fields': len(all_fields),
        'required_fields': len(required_fields),
        'mapped_fields': len(mapped_fields),
        'mapped_required': len(mapped_required),
        'missing_required': sorted(missing_required),
        'coverage_rate': len(mapped_required) / len(required_fields) if required_fields else 0,
        'fields_with_fallbacks': fields_with_fallbacks,
        'fallback_rate': fields_with_fallbacks / len(mapped_fields) if mapped_fields else 0
    }


def analyze_confidence(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze mapping confidence distribution.

    Returns:
        Dictionary with confidence metrics
    """
    confidence_counts = Counter()
    occurrence_rates = []

    for field_name, field_data in mapping.get('fields', {}).items():
        confidence = field_data.get('confidence', 'unknown')
        confidence_counts[confidence] += 1

        occurrence = field_data.get('occurrence_rate', 0.0)
        occurrence_rates.append((field_name, occurrence))

    # Sort by occurrence rate
    occurrence_rates.sort(key=lambda x: x[1])

    # Identify low confidence mappings (<15%)
    low_confidence_mappings = [(f, r) for f, r in occurrence_rates if r < 0.15]

    return {
        'confidence_distribution': dict(confidence_counts),
        'high_confidence_count': confidence_counts.get('high', 0),
        'medium_confidence_count': confidence_counts.get('medium', 0),
        'low_confidence_count': confidence_counts.get('low', 0),
        'low_confidence_mappings': low_confidence_mappings,
        'mean_occurrence_rate': sum(r for _, r in occurrence_rates) / len(occurrence_rates) if occurrence_rates else 0,
        'min_occurrence_rate': occurrence_rates[0] if occurrence_rates else (None, 0),
        'max_occurrence_rate': occurrence_rates[-1] if occurrence_rates else (None, 0)
    }


def analyze_conflicts(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze potential mapping conflicts.

    Returns:
        Dictionary with conflict metrics
    """
    # Check for multiple fields mapping to same concept
    concept_to_fields = defaultdict(list)

    for field_name, field_data in mapping.get('fields', {}).items():
        primary = field_data.get('primary')
        if primary:
            concept_to_fields[primary].append(field_name)

    # Find conflicts (concept mapped by multiple fields)
    conflicts = {concept: fields for concept, fields in concept_to_fields.items()
                if len(fields) > 1}

    # Check for missing parent concepts (referenced but not mapped)
    all_concepts = set(concept_to_fields.keys())
    referenced_parents = set()

    for field_data in mapping.get('fields', {}).values():
        parent = field_data.get('metadata', {}).get('parent')
        if parent:
            referenced_parents.add(parent)

    missing_parents = referenced_parents - all_concepts

    return {
        'conflicts': conflicts,
        'conflict_count': len(conflicts),
        'missing_parents': sorted(missing_parents),
        'missing_parent_count': len(missing_parents)
    }


def compare_sector_to_core(
    core_mapping: Dict[str, Any],
    sector_mapping: Dict[str, Any],
    sector_name: str
) -> Dict[str, Any]:
    """
    Compare sector overlay to core mapping.

    Returns:
        Dictionary with comparison metrics
    """
    core_fields = core_mapping.get('fields', {})
    sector_fields = sector_mapping.get('fields', {})

    # Fields overridden in sector
    overridden = []
    for field_name, sector_data in sector_fields.items():
        if field_name in core_fields:
            core_concept = core_fields[field_name].get('primary')
            sector_concept = sector_data.get('primary')
            if core_concept != sector_concept:
                overridden.append({
                    'field': field_name,
                    'core_concept': core_concept,
                    'sector_concept': sector_concept,
                    'sector_occurrence': sector_data.get('occurrence_rate_sector', 0),
                    'global_occurrence': sector_data.get('occurrence_rate_global', 0)
                })

    # Sector-specific fields (not in core)
    sector_specific = [f for f in sector_fields if f not in core_fields]

    return {
        'sector': sector_name,
        'total_sector_fields': len(sector_fields),
        'overridden_fields': overridden,
        'override_count': len(overridden),
        'sector_specific_fields': sector_specific,
        'sector_specific_count': len(sector_specific)
    }


def generate_report(
    core_analysis: Dict[str, Any],
    sector_analyses: List[Dict[str, Any]],
    output_path: Path
):
    """Generate markdown quality report."""

    report = []
    report.append("# Mapping Quality Analysis Report")
    report.append(f"\n**Generated**: {Path().resolve()}")
    report.append("\n---\n")

    # Coverage Section
    report.append("## 1. Coverage Analysis")
    report.append("\n### Core Mapping")
    report.append(f"- **Total Fields**: {core_analysis['coverage']['total_fields']}")
    report.append(f"- **Required Fields**: {core_analysis['coverage']['required_fields']}")
    report.append(f"- **Mapped Fields**: {core_analysis['coverage']['mapped_fields']}")
    report.append(f"- **Coverage Rate**: {core_analysis['coverage']['coverage_rate']:.1%}")
    report.append(f"- **Fields with Fallbacks**: {core_analysis['coverage']['fields_with_fallbacks']} ({core_analysis['coverage']['fallback_rate']:.1%})")

    if core_analysis['coverage']['missing_required']:
        report.append("\n**Missing Required Fields**:")
        for field in core_analysis['coverage']['missing_required']:
            report.append(f"- `{field}`")

    # Confidence Section
    report.append("\n## 2. Confidence Analysis")
    report.append("\n### Distribution")
    conf = core_analysis['confidence']
    report.append(f"- **High Confidence** (≥30%): {conf['high_confidence_count']}")
    report.append(f"- **Medium Confidence** (15-30%): {conf['medium_confidence_count']}")
    report.append(f"- **Low Confidence** (<15%): {conf['low_confidence_count']}")
    report.append("\n### Occurrence Rates")
    report.append(f"- **Mean**: {conf['mean_occurrence_rate']:.1%}")
    report.append(f"- **Min**: {conf['min_occurrence_rate'][1]:.1%} (`{conf['min_occurrence_rate'][0]}`)")
    report.append(f"- **Max**: {conf['max_occurrence_rate'][1]:.1%} (`{conf['max_occurrence_rate'][0]}`)")

    if conf['low_confidence_mappings']:
        report.append("\n### Low Confidence Mappings")
        report.append("| Field | Occurrence Rate |")
        report.append("|-------|----------------|")
        for field, rate in conf['low_confidence_mappings']:
            report.append(f"| `{field}` | {rate:.1%} |")

    # Conflicts Section
    report.append("\n## 3. Conflict Analysis")
    conflicts = core_analysis['conflicts']

    if conflicts['conflicts']:
        report.append(f"\n**⚠️ Found {conflicts['conflict_count']} conflicts** (multiple fields mapping to same concept):")
        for concept, fields in conflicts['conflicts'].items():
            report.append(f"- `{concept}` ← {', '.join(f'`{f}`' for f in fields)}")
    else:
        report.append("\n✅ **No conflicts found**")

    if conflicts['missing_parents']:
        report.append(f"\n**Missing Parent Concepts** ({conflicts['missing_parent_count']}):")
        for parent in conflicts['missing_parents'][:10]:  # Limit to 10
            report.append(f"- `{parent}`")
        if conflicts['missing_parent_count'] > 10:
            report.append(f"- ... and {conflicts['missing_parent_count'] - 10} more")

    # Sector Comparison Section
    if sector_analyses:
        report.append("\n## 4. Sector Overlay Analysis")

        for sector_analysis in sector_analyses:
            sector = sector_analysis['sector']
            report.append(f"\n### {sector.title()}")
            report.append(f"- **Total Fields**: {sector_analysis['total_sector_fields']}")
            report.append(f"- **Overridden**: {sector_analysis['override_count']}")
            report.append(f"- **Sector-Specific**: {sector_analysis['sector_specific_count']}")

            if sector_analysis['overridden_fields']:
                report.append("\n**Overridden Mappings**:")
                report.append("| Field | Core Concept | Sector Concept | Sector Occ | Global Occ |")
                report.append("|-------|--------------|----------------|------------|------------|")
                for override in sector_analysis['overridden_fields']:
                    report.append(
                        f"| `{override['field']}` | "
                        f"`{override['core_concept']}` | "
                        f"`{override['sector_concept']}` | "
                        f"{override['sector_occurrence']:.1%} | "
                        f"{override['global_occurrence']:.1%} |"
                    )

    # Recommendations Section
    report.append("\n## 5. Recommendations")

    recommendations = []

    if core_analysis['coverage']['coverage_rate'] < 0.90:
        recommendations.append(
            f"- **Low coverage** ({core_analysis['coverage']['coverage_rate']:.1%}): "
            f"Consider lowering occurrence threshold or adding manual mappings for missing fields"
        )

    if conf['low_confidence_count'] > 3:
        recommendations.append(
            f"- **Multiple low-confidence mappings**: Review {conf['low_confidence_count']} fields "
            f"with <15% occurrence rate"
        )

    if conflicts['conflict_count'] > 0:
        recommendations.append(
            f"- **Resolve {conflicts['conflict_count']} conflicts**: "
            f"Multiple fields should not map to the same concept"
        )

    if not recommendations:
        recommendations.append("✅ **Mappings look good!** Ready for production deployment.")

    for rec in recommendations:
        report.append(rec)

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print(f"\n✅ Quality report saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze mapping quality and coverage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze core mapping only
  python analyze_mappings.py --core map/map_core.json

  # Analyze core + sector overlays
  python analyze_mappings.py \\
    --core map/map_core.json \\
    --overlays map/map_overlays/*.json
        """
    )

    parser.add_argument(
        '--core',
        type=Path,
        required=True,
        help='Path to core mapping JSON file'
    )

    parser.add_argument(
        '--overlays',
        nargs='*',
        type=Path,
        help='Paths to sector overlay JSON files'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('quant/xbrl_standardize/map/MAPPING_QUALITY_REPORT.md'),
        help='Output path for quality report'
    )

    args = parser.parse_args()

    # Validate input
    if not args.core.exists():
        print(f"❌ Core mapping not found: {args.core}")
        return 1

    print("="*70)
    print("ANALYZING MAPPINGS")
    print("="*70)

    # Load core mapping
    print(f"\n📥 Loading core mapping: {args.core}")
    core_mapping = load_mapping(args.core)

    # Load field specs
    print("📥 Loading field specifications...")
    try:
        from quant.xbrl_standardize.field_specs import INCOME_STATEMENT_FIELDS
        field_specs = INCOME_STATEMENT_FIELDS
    except ImportError as e:
        print(f"❌ Failed to import field_specs: {e}")
        return 1

    # Analyze core mapping
    print("\n🔍 Analyzing core mapping...")

    coverage = analyze_coverage(core_mapping, field_specs)
    print(f"  Coverage: {coverage['coverage_rate']:.1%} ({coverage['mapped_required']}/{coverage['required_fields']} required fields)")

    confidence = analyze_confidence(core_mapping)
    print(f"  Confidence: {confidence['high_confidence_count']} high, {confidence['medium_confidence_count']} medium, {confidence['low_confidence_count']} low")

    conflicts = analyze_conflicts(core_mapping)
    print(f"  Conflicts: {conflicts['conflict_count']} concept conflicts, {conflicts['missing_parent_count']} missing parents")

    core_analysis = {
        'coverage': coverage,
        'confidence': confidence,
        'conflicts': conflicts
    }

    # Analyze sector overlays
    sector_analyses = []
    if args.overlays:
        print("\n🔍 Analyzing sector overlays...")
        for overlay_path in args.overlays:
            if not overlay_path.exists():
                print(f"  ⚠️  Overlay not found: {overlay_path}")
                continue

            sector_name = overlay_path.stem
            print(f"  Analyzing {sector_name}...")

            sector_mapping = load_mapping(overlay_path)
            sector_analysis = compare_sector_to_core(core_mapping, sector_mapping, sector_name)
            sector_analyses.append(sector_analysis)

            print(f"    Overrides: {sector_analysis['override_count']}, Sector-specific: {sector_analysis['sector_specific_count']}")

    # Generate report
    print("\n📝 Generating quality report...")
    generate_report(core_analysis, sector_analyses, args.output)

    # Summary
    print("\n" + "="*70)
    print("✅ ANALYSIS COMPLETE")
    print("="*70)
    print("\nKey Metrics:")
    print(f"  Coverage: {coverage['coverage_rate']:.1%}")
    print(f"  High Confidence: {confidence['high_confidence_count']}/{len(core_mapping['fields'])}")
    print(f"  Conflicts: {conflicts['conflict_count']}")

    if coverage['coverage_rate'] >= 0.90 and conflicts['conflict_count'] == 0:
        print("\n✅ Quality: EXCELLENT - Ready for production")
        return 0
    elif coverage['coverage_rate'] >= 0.75 and conflicts['conflict_count'] <= 2:
        print("\n⚠️  Quality: GOOD - Minor issues to address")
        return 0
    else:
        print("\n❌ Quality: NEEDS IMPROVEMENT - Review report for details")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
