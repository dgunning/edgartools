#!/usr/bin/env python3
"""
Migrated from gists/bugs/319-NetworkSgmlParser.py
Network Sgml Parser - Filing Access Issue

Original file: 319-NetworkSgmlParser.py
Category: filing-access
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
from pathlib import Path
from edgar.sgml.sgml_parser import SGMLParser

parser = SGMLParser()
#with gzip.open("20100701_7039_0000000000-10-037038.txt.gz", "rt") as f:
#    content = f.read()
content = Path('data/sgml/0000320193-24-000123.txt').read_text(encoding='utf-8')
submission = parser.parse(content)
header = FilingHeader.parse_from_sgml_text(submission["header"])
print(header)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
