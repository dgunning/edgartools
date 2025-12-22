"""
Utilities for working with XBRL standardization mappings.

This module provides helper functions for:
- Exporting mappings to CSV for Excel editing
- Importing mappings from CSV files
- Validating mapping files for common issues
- Converting between formats

These utilities support the workflow described in the customizing-standardization.md guide.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from edgar.xbrl.standardization.core import MappingStore, StandardConcept
except ImportError:
    # Allow standalone usage for testing
    MappingStore = None
    StandardConcept = None


@dataclass
class ValidationIssue:
    """Represents a validation issue found in mapping files."""
    severity: str  # "error", "warning", "info"
    category: str  # "duplicate", "missing", "inconsistent", etc.
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    concept: Optional[str] = None


@dataclass
class ValidationReport:
    """Report of validation issues found in mappings."""
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get error-level issues."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get warning-level issues."""
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def info(self) -> List[ValidationIssue]:
        """Get info-level issues."""
        return [i for i in self.issues if i.severity == "info"]

    @property
    def has_errors(self) -> bool:
        """Check if any errors were found."""
        return len(self.errors) > 0

    def summary(self) -> str:
        """Get a summary of validation results."""
        return f"Validation: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info"

    def print_report(self, show_info: bool = False):
        """Print the validation report."""
        print(self.summary())
        print()

        if self.errors:
            print("ERRORS:")
            for issue in self.errors:
                self._print_issue(issue)
            print()

        if self.warnings:
            print("WARNINGS:")
            for issue in self.warnings:
                self._print_issue(issue)
            print()

        if show_info and self.info:
            print("INFO:")
            for issue in self.info:
                self._print_issue(issue)

    def _print_issue(self, issue: ValidationIssue):
        """Print a single validation issue."""
        location = []
        if issue.file:
            location.append(f"File: {issue.file}")
        if issue.line:
            location.append(f"Line: {issue.line}")
        if issue.concept:
            location.append(f"Concept: {issue.concept}")

        location_str = " | ".join(location) if location else ""
        print(f"  [{issue.category.upper()}] {issue.message}")
        if location_str:
            print(f"    {location_str}")


def export_mappings_to_csv(
    store: "MappingStore",
    output_path: str,
    include_metadata: bool = True
) -> None:
    """
    Export mapping store to CSV format for Excel editing.

    CSV Format:
        standard_concept,company_concept,cik,priority,source,notes
        Revenue,us-gaap_Revenue,,,core,Primary revenue concept
        Revenue,tsla_AutomotiveRevenue,1318605,2,company,Tesla automotive sales

    Args:
        store: MappingStore instance to export
        output_path: Path to write CSV file
        include_metadata: Include metadata rows (entity info, etc.)

    Example:
        >>> from edgar.xbrl.standardization.core import MappingStore
        >>> store = MappingStore()
        >>> export_mappings_to_csv(store, "mappings.csv")
    """
    rows = []

    # Export core mappings (priority 1)
    for standard_concept, company_concepts in store.mappings.items():
        for concept in sorted(company_concepts):
            rows.append({
                'standard_concept': standard_concept,
                'company_concept': concept,
                'cik': '',
                'priority': 1,
                'source': 'core',
                'notes': ''
            })

    # Export company-specific mappings (priority 2)
    for entity_id, company_data in store.company_mappings.items():
        # Extract metadata
        metadata = company_data.get('metadata', company_data.get('entity_info', {}))
        cik = metadata.get('cik', '')
        ticker = metadata.get('ticker', metadata.get('entity_identifier', entity_id))

        # Export concept mappings
        concept_mappings = company_data.get('concept_mappings', {})
        for standard_concept, company_concepts in concept_mappings.items():
            if isinstance(company_concepts, list):
                concepts_to_add = company_concepts
            elif isinstance(company_concepts, set):
                concepts_to_add = sorted(company_concepts)
            else:
                concepts_to_add = [company_concepts]

            for concept in concepts_to_add:
                rows.append({
                    'standard_concept': standard_concept,
                    'company_concept': concept,
                    'cik': cik,
                    'priority': 2,
                    'source': ticker,
                    'notes': ''
                })

    # Write CSV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['standard_concept', 'company_concept', 'cik', 'priority', 'source', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Exported {len(rows)} mappings to {output_path}")


def import_mappings_from_csv(
    csv_path: str,
    validate: bool = True
) -> Dict[str, any]:
    """
    Import mappings from CSV file.

    Returns a dictionary with:
        - 'core_mappings': Dict of core concept mappings
        - 'company_mappings': Dict of company-specific mappings by CIK/ticker
        - 'validation': ValidationReport if validate=True

    Args:
        csv_path: Path to CSV file
        validate: Run validation checks on imported data

    Returns:
        Dictionary with core_mappings, company_mappings, and optional validation report

    Example:
        >>> result = import_mappings_from_csv("mappings.csv")
        >>> if not result['validation'].has_errors:
        ...     core = result['core_mappings']
        ...     companies = result['company_mappings']
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    core_mappings = {}
    company_mappings = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for line_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            standard_concept = row['standard_concept'].strip()
            company_concept = row['company_concept'].strip()
            cik = row.get('cik', '').strip()
            priority = int(row.get('priority', 1))
            source = row.get('source', '').strip()

            if not standard_concept or not company_concept:
                continue  # Skip empty rows

            # Core mappings (priority 1, no CIK)
            if priority == 1 or (not cik and source == 'core'):
                if standard_concept not in core_mappings:
                    core_mappings[standard_concept] = set()
                core_mappings[standard_concept].add(company_concept)

            # Company-specific mappings
            else:
                # Use CIK if available, otherwise source/ticker
                entity_id = cik if cik else source

                if entity_id not in company_mappings:
                    company_mappings[entity_id] = {
                        'metadata': {
                            'cik': cik,
                            'entity_identifier': source,
                        },
                        'concept_mappings': {}
                    }

                mappings = company_mappings[entity_id]['concept_mappings']
                if standard_concept not in mappings:
                    mappings[standard_concept] = set()
                mappings[standard_concept].add(company_concept)

    # Convert sets to lists for JSON compatibility
    for concept in core_mappings:
        core_mappings[concept] = sorted(core_mappings[concept])

    for entity_id in company_mappings:
        for concept in company_mappings[entity_id]['concept_mappings']:
            company_mappings[entity_id]['concept_mappings'][concept] = sorted(
                company_mappings[entity_id]['concept_mappings'][concept]
            )

    result = {
        'core_mappings': core_mappings,
        'company_mappings': company_mappings
    }

    # Validate if requested
    if validate:
        report = validate_csv_mappings(csv_path)
        result['validation'] = report

        if report.has_errors:
            print(f"⚠️ Validation found {len(report.errors)} errors")
        else:
            print(f"✓ Imported {len(core_mappings)} core concepts")
            print(f"✓ Imported mappings for {len(company_mappings)} companies")

    return result


def validate_mappings(store: "MappingStore") -> ValidationReport:
    """
    Validate a MappingStore for common issues.

    Checks for:
    - Duplicate mappings
    - Enum/JSON consistency
    - CIK/ticker metadata consistency
    - Ambiguous mappings (same company concept mapped to multiple standard concepts)

    Args:
        store: MappingStore instance to validate

    Returns:
        ValidationReport with any issues found

    Example:
        >>> store = MappingStore()
        >>> report = validate_mappings(store)
        >>> if report.has_errors:
        ...     report.print_report()
    """
    report = ValidationReport()

    # Check for duplicate mappings in core
    _check_core_duplicates(store, report)

    # Check enum consistency
    if StandardConcept:
        _check_enum_consistency(store, report)

    # Check company mappings
    _check_company_mappings(store, report)

    # Check for reverse ambiguity (same company concept → multiple standards)
    _check_reverse_ambiguity(store, report)

    return report


def validate_csv_mappings(csv_path: str) -> ValidationReport:
    """
    Validate a CSV mapping file.

    Checks for:
    - File format issues
    - Duplicate rows
    - Missing required fields
    - Invalid priority values

    Args:
        csv_path: Path to CSV file

    Returns:
        ValidationReport with any issues found
    """
    report = ValidationReport()
    csv_path = Path(csv_path)

    if not csv_path.exists():
        report.issues.append(ValidationIssue(
            severity="error",
            category="missing",
            message=f"CSV file not found: {csv_path}",
            file=str(csv_path)
        ))
        return report

    # Track seen mappings for duplicate detection
    seen_mappings = set()
    required_fields = {'standard_concept', 'company_concept'}

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # Check headers
            if not required_fields.issubset(set(reader.fieldnames or [])):
                missing = required_fields - set(reader.fieldnames or [])
                report.issues.append(ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"Missing required CSV columns: {missing}",
                    file=str(csv_path),
                    line=1
                ))
                return report

            for line_num, row in enumerate(reader, start=2):
                # Check for empty required fields
                if not row['standard_concept'].strip():
                    report.issues.append(ValidationIssue(
                        severity="error",
                        category="missing",
                        message="Empty standard_concept field",
                        file=str(csv_path),
                        line=line_num
                    ))

                if not row['company_concept'].strip():
                    report.issues.append(ValidationIssue(
                        severity="error",
                        category="missing",
                        message="Empty company_concept field",
                        file=str(csv_path),
                        line=line_num
                    ))

                # Check for duplicates
                mapping_key = (
                    row['standard_concept'].strip(),
                    row['company_concept'].strip(),
                    row.get('cik', '').strip()
                )

                if mapping_key in seen_mappings:
                    report.issues.append(ValidationIssue(
                        severity="warning",
                        category="duplicate",
                        message=f"Duplicate mapping: {mapping_key[0]} → {mapping_key[1]}",
                        file=str(csv_path),
                        line=line_num,
                        concept=mapping_key[0]
                    ))

                seen_mappings.add(mapping_key)

                # Validate priority
                if 'priority' in row:
                    try:
                        priority = int(row['priority'])
                        if priority not in [1, 2, 3, 4]:
                            report.issues.append(ValidationIssue(
                                severity="warning",
                                category="invalid",
                                message=f"Invalid priority value: {priority} (should be 1-4)",
                                file=str(csv_path),
                                line=line_num
                            ))
                    except ValueError:
                        report.issues.append(ValidationIssue(
                            severity="error",
                            category="invalid",
                            message=f"Priority must be a number: {row['priority']}",
                            file=str(csv_path),
                            line=line_num
                        ))

    except Exception as e:
        report.issues.append(ValidationIssue(
            severity="error",
            category="format",
            message=f"Error reading CSV file: {e}",
            file=str(csv_path)
        ))

    return report


# Internal helper functions

def _check_core_duplicates(store: "MappingStore", report: ValidationReport):
    """Check for duplicate mappings in core mappings."""
    for standard_concept, company_concepts in store.mappings.items():
        # Check if company_concepts is a set/list and has duplicates
        if isinstance(company_concepts, (set, list)):
            concepts_list = list(company_concepts)
            if len(concepts_list) != len(set(concepts_list)):
                report.issues.append(ValidationIssue(
                    severity="warning",
                    category="duplicate",
                    message="Duplicate company concepts in core mappings",
                    concept=standard_concept
                ))


def _check_enum_consistency(store: "MappingStore", report: ValidationReport):
    """Check if StandardConcept enum values match core mapping keys."""
    if not StandardConcept:
        return

    enum_values = {e.value for e in StandardConcept}
    mapping_keys = set(store.mappings.keys())

    # Keys in mappings but not in enum
    extra_in_mappings = mapping_keys - enum_values
    if extra_in_mappings:
        report.issues.append(ValidationIssue(
            severity="info",
            category="inconsistent",
            message=f"Concepts in mappings but not in StandardConcept enum: {len(extra_in_mappings)} concepts",
        ))

    # Keys in enum but not in mappings
    missing_from_mappings = enum_values - mapping_keys
    if missing_from_mappings:
        report.issues.append(ValidationIssue(
            severity="warning",
            category="missing",
            message=f"StandardConcept enum values without mappings: {len(missing_from_mappings)} concepts",
        ))


def _check_company_mappings(store: "MappingStore", report: ValidationReport):
    """Check company-specific mappings for issues."""
    for entity_id, company_data in store.company_mappings.items():
        # Check metadata
        metadata = company_data.get('metadata', company_data.get('entity_info', {}))

        if not metadata:
            report.issues.append(ValidationIssue(
                severity="warning",
                category="missing",
                message="Company mapping missing metadata",
                file=f"{entity_id}_mappings.json"
            ))

        # Check CIK format if present
        cik = metadata.get('cik', '')
        if cik and not cik.isdigit():
            report.issues.append(ValidationIssue(
                severity="error",
                category="invalid",
                message=f"Invalid CIK format: {cik} (should be numeric)",
                file=f"{entity_id}_mappings.json"
            ))


def _check_reverse_ambiguity(store: "MappingStore", report: ValidationReport):
    """Check for company concepts that map to multiple standard concepts."""
    # Build reverse mapping: company_concept → [standard_concepts]
    reverse_map = {}

    # From core mappings
    for standard_concept, company_concepts in store.mappings.items():
        for company_concept in company_concepts:
            if company_concept not in reverse_map:
                reverse_map[company_concept] = set()
            reverse_map[company_concept].add(standard_concept)

    # From company mappings
    for entity_id, company_data in store.company_mappings.items():
        concept_mappings = company_data.get('concept_mappings', {})
        for standard_concept, company_concepts in concept_mappings.items():
            if isinstance(company_concepts, (list, set)):
                for company_concept in company_concepts:
                    if company_concept not in reverse_map:
                        reverse_map[company_concept] = set()
                    reverse_map[company_concept].add(standard_concept)

    # Report ambiguous mappings
    for company_concept, standard_concepts in reverse_map.items():
        if len(standard_concepts) > 1:
            report.issues.append(ValidationIssue(
                severity="info",
                category="ambiguous",
                message=f"Company concept maps to multiple standards: {company_concept} → {standard_concepts}",
                concept=company_concept
            ))


# Convenience functions

def save_mappings_to_json(mappings: Dict, output_path: str, indent: int = 2):
    """
    Save mappings dictionary to JSON file.

    Args:
        mappings: Dictionary of mappings (core or company-specific)
        output_path: Path to write JSON file
        indent: JSON indentation level
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert sets to lists for JSON serialization
    json_mappings = {}
    for key, value in mappings.items():
        if isinstance(value, set):
            json_mappings[key] = sorted(value)
        elif isinstance(value, dict):
            json_mappings[key] = {
                k: sorted(v) if isinstance(v, set) else v
                for k, v in value.items()
            }
        else:
            json_mappings[key] = value

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_mappings, f, indent=indent, ensure_ascii=False)

    print(f"✓ Saved mappings to {output_path}")


def load_mappings_from_json(json_path: str) -> Dict:
    """
    Load mappings from JSON file.

    Args:
        json_path: Path to JSON file

    Returns:
        Dictionary of mappings
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)
