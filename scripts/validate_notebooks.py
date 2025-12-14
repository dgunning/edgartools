#!/usr/bin/env python3
"""
Notebook Validation Script for EdgarTools
Checks all notebooks for API compatibility and common issues
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class NotebookIssue:
    """Represents an issue found in a notebook"""
    notebook: str
    cell_index: int
    issue_type: str
    description: str
    code_snippet: str
    severity: str  # 'error', 'warning', 'info'

class NotebookValidator:
    """Validates Jupyter notebooks for API compatibility"""

    # Deprecated imports and their replacements
    DEPRECATED_IMPORTS = {
        'from edgar.files.html import': 'from edgar import',  # Document moved
        'get_entity': 'Company',  # get_entity deprecated in favor of Company
    }

    # API changes
    API_CHANGES = {
        '.get_facts()': 'Check if using new facts API correctly',
        'filing.financials': 'Should use filing.xbrl() or filing.obj()',
        'filing.homepage_url': 'Check if still valid',
    }

    # Common errors
    COMMON_ERRORS = [
        (r'Filing\(.*?\)', 'Direct Filing() construction - check if should use get_filings()'),
        (r'Entity\(', 'Entity() usage - check if should use Company()'),
        (r'\.get_entity\(', 'get_entity() is deprecated - use Company() instead'),
    ]

    def __init__(self, notebooks_dir: Path):
        self.notebooks_dir = notebooks_dir
        self.issues: List[NotebookIssue] = []

    def validate_all(self) -> List[NotebookIssue]:
        """Validate all notebooks in the directory"""
        notebooks = list(self.notebooks_dir.rglob('*.ipynb'))
        print(f"Found {len(notebooks)} notebooks to validate")

        for notebook_path in sorted(notebooks):
            self.validate_notebook(notebook_path)

        return self.issues

    def validate_notebook(self, notebook_path: Path):
        """Validate a single notebook"""
        relative_path = notebook_path.relative_to(self.notebooks_dir.parent)

        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
        except Exception as e:
            self.issues.append(NotebookIssue(
                notebook=str(relative_path),
                cell_index=-1,
                issue_type='parse_error',
                description=f'Failed to parse notebook: {e}',
                code_snippet='',
                severity='error'
            ))
            return

        cells = notebook.get('cells', [])
        code_cells = [(i, cell) for i, cell in enumerate(cells) if cell.get('cell_type') == 'code']

        for cell_index, cell in code_cells:
            source = self._get_cell_source(cell)
            if not source.strip():
                continue

            # Check for deprecated imports
            for deprecated, replacement in self.DEPRECATED_IMPORTS.items():
                if deprecated in source:
                    self.issues.append(NotebookIssue(
                        notebook=str(relative_path),
                        cell_index=cell_index,
                        issue_type='deprecated_import',
                        description=f'Deprecated import found. Use {replacement} instead',
                        code_snippet=self._truncate(source),
                        severity='warning'
                    ))

            # Check for API changes
            for pattern, description in self.API_CHANGES.items():
                if pattern in source:
                    self.issues.append(NotebookIssue(
                        notebook=str(relative_path),
                        cell_index=cell_index,
                        issue_type='api_change',
                        description=description,
                        code_snippet=self._truncate(source),
                        severity='info'
                    ))

            # Check for common errors
            for pattern, description in self.COMMON_ERRORS:
                if re.search(pattern, source):
                    self.issues.append(NotebookIssue(
                        notebook=str(relative_path),
                        cell_index=cell_index,
                        issue_type='potential_error',
                        description=description,
                        code_snippet=self._truncate(source),
                        severity='warning'
                    ))

    def _get_cell_source(self, cell: dict) -> str:
        """Extract source code from cell"""
        source = cell.get('source', [])
        if isinstance(source, list):
            return ''.join(source)
        return source

    def _truncate(self, text: str, max_length: int = 100) -> str:
        """Truncate text to max length"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + '...'

    def print_report(self):
        """Print validation report"""
        if not self.issues:
            print("\n✅ All notebooks are valid!")
            return

        print(f"\n⚠️  Found {len(self.issues)} issues:")
        print("=" * 80)

        # Group by notebook
        by_notebook = {}
        for issue in self.issues:
            if issue.notebook not in by_notebook:
                by_notebook[issue.notebook] = []
            by_notebook[issue.notebook].append(issue)

        for notebook, issues in sorted(by_notebook.items()):
            print(f"\n📓 {notebook} ({len(issues)} issues)")
            for issue in issues:
                severity_icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}[issue.severity]
                print(f"  {severity_icon} Cell {issue.cell_index}: {issue.description}")
                if issue.code_snippet:
                    print(f"     Code: {issue.code_snippet}")

    def get_summary(self) -> Dict[str, int]:
        """Get summary statistics"""
        summary = {
            'total_issues': len(self.issues),
            'errors': sum(1 for i in self.issues if i.severity == 'error'),
            'warnings': sum(1 for i in self.issues if i.severity == 'warning'),
            'info': sum(1 for i in self.issues if i.severity == 'info'),
            'affected_notebooks': len(set(i.notebook for i in self.issues))
        }
        return summary

def main():
    """Main entry point"""
    notebooks_dir = Path(__file__).parent.parent / 'notebooks'

    if not notebooks_dir.exists():
        print(f"❌ Notebooks directory not found: {notebooks_dir}")
        return 1

    validator = NotebookValidator(notebooks_dir)
    validator.validate_all()
    validator.print_report()

    summary = validator.get_summary()
    print("\n" + "=" * 80)
    print("📊 Summary:")
    print(f"   Total issues: {summary['total_issues']}")
    print(f"   Errors: {summary['errors']}")
    print(f"   Warnings: {summary['warnings']}")
    print(f"   Info: {summary['info']}")
    print(f"   Affected notebooks: {summary['affected_notebooks']}")

    return 0 if summary['errors'] == 0 else 1

if __name__ == '__main__':
    exit(main())
