#!/usr/bin/env python3
"""
Deploy Learning Outputs

Deploys trained mappings from training/output/ to edgar/entity/data/ for use
by the library at runtime.

Usage:
    # Deploy canonical mappings
    python -m edgar.entity.training.deploy --canonical

    # Deploy industry extensions
    python -m edgar.entity.training.deploy --industry banking
    python -m edgar.entity.training.deploy --industry-all

    # List available extensions
    python -m edgar.entity.training.deploy --list

    # Preview without copying
    python -m edgar.entity.training.deploy --canonical --dry-run
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import (
    INDUSTRIES,
    get_output_dir,
    get_industry_output_dir,
    get_entity_data_dir,
    get_industry_extensions_dir,
)


# Files to deploy for canonical mappings
CANONICAL_FILES = {
    'learned_mappings.json': 'Canonical concept-to-statement mappings',
    'virtual_trees.json': 'Hierarchical statement structures',
}

# Optional canonical files
OPTIONAL_CANONICAL_FILES = {
    'concept_linkages.json': 'Multi-statement concept relationships',
}


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.2f} MB"
    elif size_bytes >= 1000:
        return f"{size_bytes / 1000:.1f} KB"
    return f"{size_bytes} B"


def validate_canonical_source(source_dir: Path) -> Dict:
    """Validate canonical source files exist and return metadata."""
    results = {'valid': True, 'files': {}, 'errors': []}

    for filename, description in CANONICAL_FILES.items():
        filepath = source_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            count = None
            if filename == 'learned_mappings.json':
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                        count = len(data)
                except:
                    pass
            results['files'][filename] = {
                'exists': True,
                'size': size,
                'description': description,
                'count': count
            }
        else:
            results['valid'] = False
            results['errors'].append(f"Required file missing: {filename}")
            results['files'][filename] = {'exists': False, 'description': description}

    # Check optional files
    for filename, description in OPTIONAL_CANONICAL_FILES.items():
        filepath = source_dir / filename
        if filepath.exists():
            results['files'][filename] = {
                'exists': True,
                'size': filepath.stat().st_size,
                'description': description,
                'optional': True
            }

    return results


def deploy_canonical(source_dir: Path, dest_dir: Path, dry_run: bool = False) -> Dict:
    """Deploy canonical learning files."""
    results = {'deployed': [], 'skipped': [], 'errors': []}

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    all_files = {**CANONICAL_FILES, **OPTIONAL_CANONICAL_FILES}

    for filename, description in all_files.items():
        source_path = source_dir / filename
        dest_path = dest_dir / filename

        if not source_path.exists():
            if filename in CANONICAL_FILES:
                results['errors'].append(f"Required file missing: {filename}")
            else:
                results['skipped'].append(f"{filename} (not found, optional)")
            continue

        try:
            if dry_run:
                results['deployed'].append(f"{filename} -> {dest_path} (dry run)")
            else:
                shutil.copy2(source_path, dest_path)
                results['deployed'].append(f"{filename} ({format_size(source_path.stat().st_size)})")
        except Exception as e:
            results['errors'].append(f"Failed to copy {filename}: {e}")

    return results


def get_available_industry_extensions(source_dir: Path) -> Dict:
    """Find available industry extensions in source directory."""
    available = {}

    for industry in INDUSTRIES.keys():
        filename = f"{industry}_extension.json"
        filepath = source_dir / filename
        if filepath.exists():
            try:
                with open(filepath) as f:
                    data = json.load(f)
                metadata = data.get('metadata', {})
                concept_counts = {}
                for key in data:
                    if key != 'metadata' and isinstance(data[key], dict):
                        nodes = data[key].get('nodes', {})
                        concept_counts[key] = len(nodes)

                available[industry] = {
                    'source_file': filepath,
                    'size': filepath.stat().st_size,
                    'companies_analyzed': metadata.get('companies_analyzed', 0),
                    'generated': metadata.get('generated', 'unknown'),
                    'concept_counts': concept_counts,
                    'total_concepts': sum(concept_counts.values()),
                }
            except Exception as e:
                print(f"Warning: Could not read {filepath}: {e}")

    return available


def deploy_industry_extension(
    industry: str,
    source_dir: Path,
    dest_dir: Path,
    dry_run: bool = False
) -> Dict:
    """Deploy a single industry extension."""
    source_path = source_dir / f"{industry}_extension.json"
    dest_path = dest_dir / f"{industry}.json"

    if not source_path.exists():
        return {'success': False, 'error': f"Source file not found: {source_path}"}

    try:
        if dry_run:
            return {
                'success': True,
                'action': 'would deploy',
                'source': str(source_path),
                'dest': str(dest_path),
                'size': source_path.stat().st_size,
            }
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            return {
                'success': True,
                'action': 'deployed',
                'source': str(source_path),
                'dest': str(dest_path),
                'size': dest_path.stat().st_size,
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_available(canonical_source: Path, industry_source: Path):
    """List available deployments."""
    print("\n" + "=" * 60)
    print("AVAILABLE DEPLOYMENTS")
    print("=" * 60)

    # Canonical
    print("\nCANONICAL MAPPINGS")
    print("-" * 40)
    print(f"Source: {canonical_source}")
    validation = validate_canonical_source(canonical_source)
    for filename, info in validation['files'].items():
        if info.get('exists'):
            size_str = format_size(info['size'])
            count_str = f" ({info['count']} concepts)" if info.get('count') else ""
            optional_str = " [optional]" if info.get('optional') else ""
            print(f"  [OK] {filename}: {size_str}{count_str}{optional_str}")
        else:
            print(f"  [MISSING] {filename}")

    # Industry extensions
    print("\nINDUSTRY EXTENSIONS")
    print("-" * 40)
    print(f"Source: {industry_source}")

    available = get_available_industry_extensions(industry_source)
    if not available:
        print("  No industry extensions found.")
        print(f"\n  Run learning first:")
        print("    python -m edgar.entity.training.run_industry_learning --industry banking")
    else:
        for industry, info in available.items():
            print(f"\n  {industry.upper()}")
            print(f"    Size: {format_size(info['size'])}")
            print(f"    Companies: {info['companies_analyzed']}")
            print(f"    Concepts: {info['total_concepts']}")
            for stmt, count in info['concept_counts'].items():
                print(f"      {stmt}: {count}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='Deploy learning outputs to edgar/entity/data/'
    )

    # What to deploy
    deploy_group = parser.add_argument_group('deployment options')
    deploy_group.add_argument(
        '--canonical', '-c',
        action='store_true',
        help='Deploy canonical mappings (learned_mappings.json, virtual_trees.json)'
    )
    deploy_group.add_argument(
        '--industry', '-i',
        type=str,
        choices=list(INDUSTRIES.keys()),
        help='Deploy specific industry extension'
    )
    deploy_group.add_argument(
        '--industry-all', '-I',
        action='store_true',
        help='Deploy all available industry extensions'
    )

    # Options
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available deployments and exit'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview deployment without copying files'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Deploy even if validation warnings exist'
    )

    # Custom paths (advanced)
    path_group = parser.add_argument_group('custom paths (advanced)')
    path_group.add_argument(
        '--source',
        type=str,
        default=None,
        help='Custom source directory for canonical outputs'
    )
    path_group.add_argument(
        '--industry-source',
        type=str,
        default=None,
        help='Custom source directory for industry extensions'
    )

    args = parser.parse_args()

    # Resolve paths
    canonical_source = Path(args.source) if args.source else get_output_dir()
    industry_source = Path(args.industry_source) if args.industry_source else get_industry_output_dir()
    canonical_dest = get_entity_data_dir()
    industry_dest = get_industry_extensions_dir()

    # List mode
    if args.list:
        list_available(canonical_source, industry_source)
        return 0

    # Check if anything to deploy
    if not args.canonical and not args.industry and not args.industry_all:
        parser.print_help()
        print("\n" + "-" * 60)
        print("Examples:")
        print("  --canonical          Deploy canonical mappings")
        print("  --industry banking   Deploy banking extension")
        print("  --industry-all       Deploy all industry extensions")
        print("  --list               List available deployments")
        return 0

    print("=" * 60)
    print("DEPLOY LEARNING OUTPUTS")
    print("=" * 60)
    if args.dry_run:
        print("Mode: DRY RUN (no files will be copied)")
    print()

    errors = []

    # Deploy canonical
    if args.canonical:
        print("CANONICAL MAPPINGS")
        print(f"  Source:      {canonical_source}")
        print(f"  Destination: {canonical_dest}")

        validation = validate_canonical_source(canonical_source)
        if not validation['valid'] and not args.force:
            print("  [ERROR] Validation failed:")
            for err in validation['errors']:
                print(f"    - {err}")
            print("  Use --force to deploy anyway")
            errors.append("Canonical validation failed")
        else:
            results = deploy_canonical(canonical_source, canonical_dest, args.dry_run)
            for item in results['deployed']:
                print(f"  [OK] {item}")
            for item in results['skipped']:
                print(f"  [SKIP] {item}")
            for err in results['errors']:
                print(f"  [ERROR] {err}")
                errors.append(err)
        print()

    # Deploy industry extensions
    if args.industry or args.industry_all:
        available = get_available_industry_extensions(industry_source)

        if args.industry_all:
            to_deploy = list(available.keys())
        else:
            to_deploy = [args.industry]

        print("INDUSTRY EXTENSIONS")
        print(f"  Source:      {industry_source}")
        print(f"  Destination: {industry_dest}")

        for industry in to_deploy:
            if industry not in available:
                print(f"  [SKIP] {industry} (not found)")
                continue

            result = deploy_industry_extension(
                industry, industry_source, industry_dest, args.dry_run
            )

            if result['success']:
                info = available[industry]
                size = format_size(result['size'])
                action = result['action']
                print(f"  [OK] {industry}: {info['total_concepts']} concepts ({size}) [{action}]")
            else:
                print(f"  [ERROR] {industry}: {result['error']}")
                errors.append(f"{industry}: {result['error']}")

        print()

    print("=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were copied")
    elif errors:
        print("DEPLOYMENT COMPLETED WITH ERRORS")
        return 1
    else:
        print("DEPLOYMENT SUCCESSFUL")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    exit(main())
