#!/usr/bin/env python3
"""
ML-Powered Mapping Auditor
Identifies component-before-total issues and other semantic problems using ML learnings.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

@dataclass
class ConceptInfo:
    concept: str
    is_total: bool
    occurrence_rate: float
    avg_depth: float
    label: str
    parent: Optional[str]

@dataclass
class AuditIssue:
    field: str
    rule_name: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    issue_type: str
    description: str
    recommendation: str
    concepts_affected: List[str]

class MLMappingAuditor:
    def __init__(self, ml_data_dir: Path, sector: str = 'global'):
        self.ml_data_dir = ml_data_dir
        self.sector = sector
        self.canonical = self._load_canonical_structures()
        self.learned = self._load_learned_mappings()

    def _load_canonical_structures(self) -> Dict[str, ConceptInfo]:
        """Load canonical structures for the sector."""
        filename = f'canonical_structures_{self.sector}.json'
        filepath = self.ml_data_dir / filename

        if not filepath.exists():
            print(f"Warning: {filename} not found, using global")
            filepath = self.ml_data_dir / 'canonical_structures_global.json'

        with open(filepath) as f:
            data = json.load(f)

        # Extract balance sheet concepts
        concepts = {}
        if 'BalanceSheet' in data:
            for item in data['BalanceSheet']:
                concept = item['concept']
                concepts[concept] = ConceptInfo(
                    concept=concept,
                    is_total=item.get('is_total', False),
                    occurrence_rate=item.get('occurrence_rate', 0),
                    avg_depth=item.get('avg_depth', 99),
                    label=item.get('label', ''),
                    parent=item.get('parent')
                )

        return concepts

    def _load_learned_mappings(self) -> Dict:
        """Load learned mappings for additional metadata."""
        filename = f'learned_mappings_{self.sector}.json'
        filepath = self.ml_data_dir / filename

        if not filepath.exists():
            filepath = self.ml_data_dir / 'learned_mappings_global.json'

        with open(filepath) as f:
            return json.load(f)

    def _extract_concept_name(self, full_concept: str) -> str:
        """Extract concept name from us-gaap:ConceptName or ifrs-full:ConceptName."""
        if ':' in full_concept:
            return full_concept.split(':', 1)[1]
        return full_concept

    def audit_selectany_order(self, field: str, rule_name: str, selectany: List[str]) -> List[AuditIssue]:
        """Check if selectAny array has components before totals."""
        issues = []

        # Get concept info for each item
        concept_infos = []
        for full_concept in selectany:
            concept = self._extract_concept_name(full_concept)
            info = self.canonical.get(concept)
            concept_infos.append((full_concept, info))

        # Check for component-before-total pattern
        for i, (concept1, info1) in enumerate(concept_infos):
            if info1 is None:
                continue

            # If this is a component (not total)
            if not info1.is_total:
                # Check if any totals come after it
                for j, (concept2, info2) in enumerate(concept_infos[i+1:], start=i+1):
                    if info2 and info2.is_total:
                        issues.append(AuditIssue(
                            field=field,
                            rule_name=rule_name,
                            severity='high',
                            issue_type='component_before_total',
                            description=f'Component concept {info1.concept} ({info1.occurrence_rate:.1%}) appears before total concept {info2.concept} ({info2.occurrence_rate:.1%})',
                            recommendation=f'Move {concept2} before {concept1} in selectAny array',
                            concepts_affected=[concept1, concept2]
                        ))

        return issues

    def audit_missing_concepts(self, field: str, rule_name: str, selectany: List[str]) -> List[AuditIssue]:
        """Check if high-occurrence concepts are missing from selectAny."""
        issues = []

        # Get existing concepts
        existing = set(self._extract_concept_name(c) for c in selectany)

        # Find high-occurrence concepts for this field (heuristic: similar name)
        field_keywords = field.lower().split('_')
        relevant_concepts = []

        for concept, info in self.canonical.items():
            concept_lower = concept.lower()
            # Check if concept name contains field keywords
            if any(kw in concept_lower for kw in field_keywords if len(kw) > 3):
                if concept not in existing and info.occurrence_rate > 0.15:  # 15% threshold
                    relevant_concepts.append((concept, info))

        # Sort by occurrence rate
        relevant_concepts.sort(key=lambda x: x[1].occurrence_rate, reverse=True)

        # Report top missing concepts
        for concept, info in relevant_concepts[:3]:  # Top 3 missing
            if info.is_total:  # Prioritize missing totals
                issues.append(AuditIssue(
                    field=field,
                    rule_name=rule_name,
                    severity='medium',
                    issue_type='missing_high_occurrence',
                    description=f'High-occurrence total concept {concept} ({info.occurrence_rate:.1%}) not in selectAny',
                    recommendation=f'Consider adding us-gaap:{concept} to selectAny array',
                    concepts_affected=[concept]
                ))

        return issues

    def audit_field(self, field: str, field_spec: Dict) -> List[AuditIssue]:
        """Audit a single field."""
        issues = []

        for rule in field_spec.get('rules', []):
            rule_name = rule.get('name', 'Unnamed rule')
            selectany = rule.get('selectAny', [])

            if selectany:
                # Check selectAny ordering
                issues.extend(self.audit_selectany_order(field, rule_name, selectany))

                # Check for missing concepts (only for non-computed rules)
                if not rule.get('computeAny'):
                    issues.extend(self.audit_missing_concepts(field, rule_name, selectany))

        return issues

    def audit_mapping(self, mapping_file: Path) -> Dict[str, Any]:
        """Audit entire mapping file."""
        with open(mapping_file) as f:
            mapping = json.load(f)

        all_issues = []
        fields_audited = 0

        for field, field_spec in mapping.get('fields', {}).items():
            fields_audited += 1
            issues = self.audit_field(field, field_spec)
            all_issues.extend(issues)

        # Categorize issues
        by_severity = {'critical': [], 'high': [], 'medium': [], 'low': []}
        by_type = {}

        for issue in all_issues:
            by_severity[issue.severity].append(issue)
            by_type.setdefault(issue.issue_type, []).append(issue)

        return {
            'fields_audited': fields_audited,
            'total_issues': len(all_issues),
            'issues': all_issues,
            'by_severity': by_severity,
            'by_type': by_type,
            'mapping_file': str(mapping_file),
            'ml_data_dir': str(self.ml_data_dir),
            'sector': self.sector
        }

    def suggest_optimal_order(self, selectany: List[str]) -> List[Tuple[str, float, bool]]:
        """Suggest optimal ordering for selectAny array."""
        concepts_with_info = []

        for full_concept in selectany:
            concept = self._extract_concept_name(full_concept)
            info = self.canonical.get(concept)

            if info:
                # Priority score: totals first, then by occurrence
                priority = (
                    0 if info.is_total else 1,  # Totals first
                    -info.occurrence_rate,       # Higher occurrence first
                    info.avg_depth               # Lower depth (parent) first
                )
                concepts_with_info.append((full_concept, info, priority))
            else:
                # Unknown concept - put at end
                concepts_with_info.append((full_concept, None, (2, 0, 99)))

        # Sort by priority
        concepts_with_info.sort(key=lambda x: x[2])

        return [(c, info.occurrence_rate if info else 0, info.is_total if info else False)
                for c, info, _ in concepts_with_info]

def format_report(audit_result: Dict, verbose: bool = False) -> str:
    """Format audit results as markdown report."""
    lines = ['# ML Mapping Audit Report\n']

    lines.append(f"**Mapping File**: `{audit_result['mapping_file']}`\n")
    lines.append(f"**ML Data**: `{audit_result['ml_data_dir']}`\n")
    lines.append(f"**Sector**: {audit_result['sector']}\n")
    lines.append(f"**Fields Audited**: {audit_result['fields_audited']}\n")
    lines.append(f"**Total Issues**: {audit_result['total_issues']}\n")
    lines.append('\n---\n')

    # Summary by severity
    lines.append('## Issues by Severity\n')
    for severity in ['critical', 'high', 'medium', 'low']:
        count = len(audit_result['by_severity'][severity])
        if count > 0:
            icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[severity]
            lines.append(f"- {icon} **{severity.upper()}**: {count}\n")
    lines.append('\n')

    # Summary by type
    lines.append('## Issues by Type\n')
    for issue_type, issues in audit_result['by_type'].items():
        lines.append(f"- **{issue_type.replace('_', ' ').title()}**: {len(issues)}\n")
    lines.append('\n---\n')

    # Detailed issues
    if audit_result['total_issues'] > 0:
        lines.append('## Detailed Issues\n')

        for i, issue in enumerate(audit_result['issues'], 1):
            severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[issue.severity]

            lines.append(f"\n### {i}. {severity_icon} {issue.field} - {issue.issue_type.replace('_', ' ').title()}\n")
            lines.append(f"**Rule**: {issue.rule_name}\n")
            lines.append(f"**Severity**: {issue.severity}\n")
            lines.append(f"**Description**: {issue.description}\n")
            lines.append(f"**Recommendation**: {issue.recommendation}\n")

            if verbose:
                lines.append(f"**Concepts Affected**: {', '.join(issue.concepts_affected)}\n")
    else:
        lines.append('## ✅ No Issues Found!\n')
        lines.append('\nAll fields pass ML validation checks.\n')

    return ''.join(lines)

def main():
    parser = argparse.ArgumentParser(description='Audit XBRL mapping using ML learnings')
    parser.add_argument('--mapping', required=True, help='Path to mapping JSON file')
    parser.add_argument('--ml-data', default='../ml_data', help='Path to ML data directory (default: ../ml_data/)')
    parser.add_argument('--sector', default='global', choices=['global', 'banking', 'insurance', 'utilities'],
                       help='Sector to use for ML data')
    parser.add_argument('--output', help='Output file for report (default: stdout)')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Create auditor
    auditor = MLMappingAuditor(Path(args.ml_data), args.sector)

    # Run audit
    print(f"Auditing {args.mapping} using ML data from {args.ml_data} (sector: {args.sector})...")
    result = auditor.audit_mapping(Path(args.mapping))

    # Format report
    report = format_report(result, args.verbose)

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Exit code based on severity
    if result['by_severity']['critical']:
        return 2
    elif result['by_severity']['high']:
        return 1
    else:
        return 0

if __name__ == '__main__':
    exit(main())
