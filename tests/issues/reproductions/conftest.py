"""Conftest for reproductions directory.

Files here are manual issue reproduction scripts, not automated tests.
Only files named test_*.py with actual test functions should be collected.
All other .py files (numbered issue scripts, debug scripts) are excluded.
"""
import os

# Exclude non-test scripts from pytest collection
# Only test_*.py files are collected (pytest default); this handles
# numbered scripts like 329-msftrevenue.py that aren't test files
collect_ignore = [
    f for f in os.listdir(os.path.dirname(__file__))
    if f.endswith('.py')
    and not f.startswith('test_')
    and f != 'conftest.py'
    and f != '__init__.py'
]

# Also exclude subdirectory scripts that aren't test files
for subdir in ['compatibility', 'data-quality', 'entity-facts', 'filing-access', 'filing-parsing', 'xbrl-parsing']:
    subdir_path = os.path.join(os.path.dirname(__file__), subdir)
    if os.path.isdir(subdir_path):
        for f in os.listdir(subdir_path):
            if f.endswith('.py') and not f.startswith('test_') and f != 'conftest.py' and f != '__init__.py':
                collect_ignore.append(os.path.join(subdir, f))
