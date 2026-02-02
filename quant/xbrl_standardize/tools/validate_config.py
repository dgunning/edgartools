#!/usr/bin/env python3
"""
Configuration Validation Script

Validates that the sector taxonomy and field specifications are correctly configured.
Run this after any changes to __init__.py or field_specs.py to ensure consistency.

Usage:
    python quant/xbrl_standardize/validate_config.py
"""

from typing import Any, Dict


def validate_sectors() -> Dict[str, Any]:
    """Validate sector configuration."""
    from quant.xbrl_standardize import SECTOR_PRIORITY, SECTORS, get_all_sector_keys, get_sector_by_sic

    issues = []
    warnings = []

    # Check all sectors are in priority list
    all_keys = set(get_all_sector_keys())
    priority_keys = set(SECTOR_PRIORITY)

    missing_from_priority = all_keys - priority_keys
    if missing_from_priority:
        issues.append(f"Sectors missing from SECTOR_PRIORITY: {missing_from_priority}")

    extra_in_priority = priority_keys - all_keys
    if extra_in_priority:
        issues.append(f"Unknown sectors in SECTOR_PRIORITY: {extra_in_priority}")

    # Validate each sector
    for sector_key, sector_info in SECTORS.items():
        # Check required fields
        required_fields = ['name', 'sic_ranges', 'key_concepts', 'min_companies', 'default_threshold', 'description']
        for field in required_fields:
            if field not in sector_info:
                issues.append(f"Sector '{sector_key}' missing required field: {field}")

        # Check SIC ranges
        if 'sic_ranges' in sector_info:
            if not sector_info['sic_ranges']:
                warnings.append(f"Sector '{sector_key}' has empty SIC ranges")
            for sic_start, sic_end in sector_info['sic_ranges']:
                if sic_start > sic_end:
                    issues.append(f"Sector '{sector_key}' has invalid SIC range: {sic_start}-{sic_end}")

        # Check threshold is reasonable
        if 'default_threshold' in sector_info:
            threshold = sector_info['default_threshold']
            if not (0.0 <= threshold <= 1.0):
                issues.append(f"Sector '{sector_key}' has invalid threshold: {threshold}")
            if threshold < 0.10:
                warnings.append(f"Sector '{sector_key}' has very low threshold: {threshold}")

    # Test SIC lookups for common codes
    test_sics = {
        6021: 'financials_banking',  # Commercial bank
        4920: 'energy_utilities',    # Electric utility
        7372: 'technology',          # Software
    }

    for sic, expected_sector in test_sics.items():
        found_sector = get_sector_by_sic(sic)
        if found_sector != expected_sector:
            issues.append(f"SIC {sic} mapped to '{found_sector}', expected '{expected_sector}'")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'total_sectors': len(SECTORS),
        'priority_order': len(SECTOR_PRIORITY),
    }


def validate_field_specs() -> Dict[str, Any]:
    """Validate field specifications."""
    from quant.xbrl_standardize.field_specs import (
        INCOME_STATEMENT_FIELDS,
        get_field_candidates,
        validate_field_spec,
    )

    # Use built-in validation
    result = validate_field_spec()

    # Additional checks
    issues = result.get('issues', [])
    warnings = []

    # Check sector-specific rules reference valid sectors
    from quant.xbrl_standardize import get_all_sector_keys
    valid_sectors = set(get_all_sector_keys())

    for field_name, field_spec in INCOME_STATEMENT_FIELDS.items():
        if 'sectorRules' in field_spec:
            for sector_key in field_spec['sectorRules'].keys():
                if sector_key not in valid_sectors:
                    issues.append(f"Field '{field_name}' references unknown sector: '{sector_key}'")

        # Check that candidateConcepts exist
        if 'candidateConcepts' in field_spec:
            if not field_spec['candidateConcepts']:
                warnings.append(f"Field '{field_name}' has empty candidateConcepts list")

    # Test getting candidates for fields with sector rules
    test_cases = [
        ('revenue', 'financials_banking'),
        ('revenue', None),
        ('costOfRevenue', 'financials_insurance'),
    ]

    for field_name, sector in test_cases:
        candidates = get_field_candidates(field_name, sector)
        context = f"with sector '{sector}'" if sector else "without sector"
        if not candidates:
            warnings.append(f"Field '{field_name}' {context} has no candidates")

    result['issues'] = issues
    result['warnings'] = warnings
    return result


def validate_directories() -> Dict[str, Any]:
    """Validate directory structure."""

    from quant.xbrl_standardize import get_map_dir, get_overlays_dir

    issues = []
    created = []

    # Check required directories
    map_dir = get_map_dir()
    if not map_dir.exists():
        issues.append(f"Map directory does not exist: {map_dir}")
    else:
        created.append(str(map_dir))

    overlays_dir = get_overlays_dir()
    if not overlays_dir.exists():
        issues.append(f"Overlays directory does not exist: {overlays_dir}")
    else:
        created.append(str(overlays_dir))

    # Check if is.py exists
    is_py = map_dir / "is.py"
    if not is_py.exists():
        issues.append(f"Missing is.py script: {is_py}")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'directories_created': created,
    }


def main():
    """Run all validation checks."""
    print("="*70)
    print("XBRL Standardization Configuration Validation")
    print("="*70)

    all_valid = True

    # Validate sectors
    print("\n[1/3] Validating sector taxonomy...")
    sector_result = validate_sectors()
    print(f"  Sectors defined: {sector_result['total_sectors']}")
    print(f"  Priority order: {sector_result['priority_order']}")

    if sector_result['issues']:
        all_valid = False
        print("  ❌ ISSUES:")
        for issue in sector_result['issues']:
            print(f"    - {issue}")

    if sector_result['warnings']:
        print("  ⚠️  WARNINGS:")
        for warning in sector_result['warnings']:
            print(f"    - {warning}")

    if sector_result['valid']:
        print("  ✅ Sector taxonomy valid")

    # Validate field specs
    print("\n[2/3] Validating field specifications...")
    field_result = validate_field_specs()
    print(f"  Fields defined: {field_result['total_fields']}")
    print(f"  Evaluation order: {field_result['evaluation_order_length']}")

    if field_result['issues']:
        all_valid = False
        print("  ❌ ISSUES:")
        for issue in field_result['issues']:
            print(f"    - {issue}")

    if field_result.get('warnings'):
        print("  ⚠️  WARNINGS:")
        for warning in field_result['warnings']:
            print(f"    - {warning}")

    if field_result['valid']:
        print("  ✅ Field specifications valid")

    # Validate directories
    print("\n[3/3] Validating directory structure...")
    dir_result = validate_directories()

    if dir_result['directories_created']:
        print("  Directories:")
        for dir_path in dir_result['directories_created']:
            print(f"    ✅ {dir_path}")

    if dir_result['issues']:
        all_valid = False
        print("  ❌ ISSUES:")
        for issue in dir_result['issues']:
            print(f"    - {issue}")

    if dir_result['valid']:
        print("  ✅ Directory structure valid")

    # Summary
    print("\n" + "="*70)
    if all_valid:
        print("✅ ALL VALIDATIONS PASSED - Configuration is ready for Phase 1")
    else:
        print("❌ VALIDATION FAILED - Please fix issues above")
    print("="*70)

    return 0 if all_valid else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
